# ==================== AGENT_LOOP.PY ====================
# The agent execution loop (spec §4.3): plans steps, executes validated tools,
# verifies critical effects by read-back, guards budgets and repeats, parks
# clarifying questions, and reports an honest event stream the UI can render.
#
# Split of responsibility:
# - UNDERSTANDING stays in extractor.py (deterministic + LLM extraction).
# - DECIDING has two sources: deterministic per-intent step plans (always
#   available) and an optional LLM step decider (prompts.build_step_decision_
#   prompt) used when the provider is up and the deterministic plan is
#   incomplete. Any LLM failure degrades to the deterministic chain.
# - EXECUTING is this module. Tools are the only writers (execute_tool already
#   enforces schema/permission/confirmation/idempotency).

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from focus_agent import models as m
from focus_agent.repository import TaskRepository, MemoryRepository, ValidationError
from focus_agent.config import get_loop_budgets
from focus_agent import tools as ftools
from focus_agent.schemas import ToolCall, ToolResult

# tools whose success the loop double-checks by re-reading the store
VERIFY_TOOLS = {"create_task", "update_task", "complete_task", "reopen_task",
                "delete_task", "reschedule_task"}


@dataclass
class Step:
    """One planned action. kind: tool | ask | note."""
    kind: str
    tool: str | None = None
    args: dict = field(default_factory=dict)
    note: str = ""                      # honest status text shown before executing
    verify: dict = field(default_factory=dict)   # read-back expectations


@dataclass
class AgentEvent:
    type: str            # status | tool_result | verification | question | budget | repeat | error
    text: str
    data: dict = field(default_factory=dict)

    def to_dict(self):
        return {"type": self.type, "text": self.text, "data": self.data}


@dataclass
class LoopOutcome:
    events: list = field(default_factory=list)        # list[AgentEvent]
    tool_results: list = field(default_factory=list)  # list[ToolResult]
    status: str = "ok"            # ok | budget_exhausted | asked_user | error
    pending: dict | None = None   # AgentPendingQuestion-shaped dict when parked
    task_id: str | None = None    # primary affected task (conversation context)

    @property
    def ok_count(self):
        return sum(1 for r in self.tool_results if r.ok)

    def add(self, etype, text, data=None):
        self.events.append(AgentEvent(etype, text, data or {}))


def _canonical(args: dict) -> str:
    try:
        return json.dumps(args, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return repr(args)


class AgentLoop:
    """Executes a step plan with budgets, guards, verification, persistence."""

    def __init__(self, data, ctx=None, confirm_callback=None, budgets=None,
                 conversation_id=None, provider=None):
        self.data = data
        self.ctx = ctx or {}
        self.confirm_callback = confirm_callback
        self.budgets = budgets or get_loop_budgets()
        self.provider = provider
        self.repo = TaskRepository(data)
        self.memory = MemoryRepository(data)
        self.conversation_id = conversation_id
        self._seen_calls: set = set()

    # ---------------- main ----------------

    def run(self, steps, outcome: LoopOutcome | None = None) -> LoopOutcome:
        outcome = outcome or LoopOutcome()
        tools_run = 0
        for step in steps:
            if tools_run >= self.budgets.max_tool_calls:
                outcome.status = "budget_exhausted"
                outcome.add("budget", f"Tool budget ({self.budgets.max_tool_calls}) "
                                      "reached - stopping this turn early.")
                break
            if step.kind == "note":
                outcome.add("status", step.note)
                continue
            if step.kind == "ask":
                self._park_question(step, outcome)
                return outcome
            # kind == "tool"
            outcome.add("status", step.note or f"Running {step.tool}...")
            key = (step.tool, _canonical(step.args))
            if key in self._seen_calls:
                outcome.add("repeat", f"Skipped repeated {step.tool} call "
                                      "(identical arguments already executed).")
                continue
            self._seen_calls.add(key)

            call_id = uuid_call_id()
            result = ftools.execute_tool(
                self.data, ToolCall(tool=step.tool, args=step.args,
                                    call_id=call_id, source="local"),
                ctx=self.ctx, confirm_callback=self.confirm_callback)
            tools_run += 1
            outcome.tool_results.append(result)
            outcome.add("tool_result",
                        (result.message or result.error or "").split("\n")[0][:200],
                        {"tool": step.tool, "ok": result.ok})

            if not result.ok:
                self._log_action(call_id, step, result, verified=None)
                continue
            verified = self._verify(step, result, outcome)
            # single audit record per call, with the final ok + verification
            self._log_action(call_id, step, result, verified=verified)
            if step.args.get("task_ref") or result.data:
                tid = (result.data or {}).get("task_id") or None
                if tid:
                    outcome.task_id = tid
        else:
            if steps and steps[-1].kind != "ask":
                outcome.status = outcome.status or "ok"
        return outcome

    # ---------------- verification ----------------

    def _verify(self, step, result: ToolResult, outcome: LoopOutcome) -> bool | None:
        """Read-back check for critical writes. A lie demotes the result."""
        if step.tool not in VERIFY_TOOLS:
            return None
        repo = self.repo
        tid = (result.data or {}).get("task_id")
        check = step.verify or {}
        try:
            if step.tool == "create_task":
                t = repo.get(tid) if tid else None
                ok = bool(t) and (not check.get("title")
                                  or (t.get("title") or "").lower() == check["title"].lower())
                expect = f"task '{check.get('title', tid)}' exists"
            elif step.tool in ("update_task", "reschedule_task"):
                t = repo.get(tid) if tid else None
                ok = bool(t)
                for field, expected in (check.get("fields") or {}).items():
                    store_key = "date" if field == "due_date" else field
                    if expected is not None and t.get(store_key) != expected:
                        ok = False
                expect = "fields applied: " + ", ".join((check.get("fields") or {}))
            elif step.tool in ("complete_task", "reopen_task"):
                t = repo.get(tid) if tid else None
                want = "done" if step.tool == "complete_task" else "pending"
                ok = bool(t) and t.get("status") == want
                expect = f"status is {want}"
            elif step.tool == "delete_task":
                t = repo.get(tid) if tid else None
                ok = t is None
                expect = "task removed"
            else:
                return None
        except ValidationError:
            ok, expect = False, "record readable"
        if ok:
            outcome.add("verification", f"Verified: {expect}.")
        else:
            outcome.add("error", f"Verification FAILED after {step.tool} "
                                 f"(expected {expect}) - reporting as failed.")
            result.ok = False
            result.error = f"verification failed: {expect}"
        return ok

    # ---------------- persistence ----------------

    def _log_action(self, call_id, step, result: ToolResult, verified=None):
        try:
            self.memory.log_action(m.AgentAction(
                call_id=call_id, tool=step.tool or "?", args=step.args,
                ok=bool(result.ok), ts=int(time.time()),
                summary=(result.message or result.error or "")[:200],
                conversation_id=self.conversation_id, verified=verified))
        except Exception:
            pass  # audit logging must never break the turn

    def _park_question(self, step: Step, outcome: LoopOutcome):
        question = step.args.get("question", "Could you clarify?")
        draft = dict(step.args.get("draft") or {})
        # link the parked draft to any task created earlier this turn so the
        # resumed answer can target the right record
        if outcome.task_id and "task_id" not in draft:
            draft["task_id"] = outcome.task_id
        pending = m.AgentPendingQuestion(
            question=question,
            intent=step.args.get("intent"),
            draft=draft,
            asked_at=int(time.time()))
        outcome.status = "asked_user"
        outcome.add("question", question, {"intent": pending.intent})
        outcome.pending = pending.to_store()
        if self.conversation_id:
            try:
                self.memory.set_pending_question(self.conversation_id, pending)
            except Exception:
                pass


def uuid_call_id() -> str:
    import uuid
    return uuid.uuid4().hex[:16]


def llm_decide_step(provider, context_pack: str, tool_catalog, budgets=None):
    """Optional LLM step decision. Returns a dict or None on ANY failure -
    callers must treat None as 'use the deterministic plan'."""
    if provider is None:
        return None
    try:
        from focus_agent.prompts import build_step_decision_prompt
        payload = build_step_decision_prompt(context_pack, tool_catalog)
        raw = provider.chat_json(payload, "", temperature=0.0, max_tokens=500)
        if not isinstance(raw, dict):
            return None
        action = raw.get("action")
        if action == "tool_call" and raw.get("tool"):
            return {"action": "tool_call", "tool": raw["tool"],
                    "args": raw.get("args") or {}, "why": raw.get("why") or ""}
        if action in ("final", "ask_user"):
            return raw
        return None
    except Exception:
        return None


__all__ = ["AgentLoop", "Step", "AgentEvent", "LoopOutcome", "llm_decide_step",
           "VERIFY_TOOLS"]
