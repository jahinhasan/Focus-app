"""Agent loop contracts: multi-step flows, verification, budgets, parking (Phase 2)."""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from focus_agent import AgentController
from focus_agent.agent_loop import AgentLoop, Step, LoopOutcome
from focus_agent.repository import TaskRepository
from conftest import MockProvider, OfflineProvider, NOW


def _mk_task(data, title="Networking assignment", date=None):
    r = TaskRepository(data)
    return r.create(title, deadline=date, duration=120, importance=2, difficulty=2)


def test_move_task_multi_step_flow(sample_data):
    """'Move my networking assignment to Friday' -> resolve -> update -> replan."""
    import logic
    _mk_task(sample_data, "Networking assignment", date="2026-10-28")
    c = AgentController(sample_data)
    reply = c.handle("Move my networking assignment to Friday",
                     provider=OfflineProvider(), now=NOW)
    reloaded = logic.load_data()
    t = next(t for t in reloaded["tasks"] if t["title"] == "Networking assignment")
    assert t["date"] == "2026-10-30", "next Friday after Oct 23 is Oct 30"
    assert any(tr.tool == "update_task" and tr.ok for tr in reply.tool_results)
    hist = t.get("reschedule_history") or []
    # history is written by the repository on move (see tool layer wiring)
    assert reply.events, "loop must emit events for the UI"


def test_move_without_date_asks_which(sample_data):
    _mk_task(sample_data, "Database assignment", date="2026-10-28")
    c = AgentController(sample_data)
    reply = c.handle("move my database assignment", provider=OfflineProvider(), now=NOW)
    assert reply.status == "asked_user" and "?" in reply.message
    # pending question is parked in memory
    conv = c.memory.latest_conversation()
    assert conv and conv.get("pending"), "clarification must be parked"
    # answering it completes the move
    reply2 = c.handle("tomorrow", provider=OfflineProvider(), now=NOW)
    import logic
    reloaded = logic.load_data()
    t = next(t for t in reloaded["tasks"] if t["title"] == "Database assignment")
    assert t["date"] == "2026-10-24", "answer 'tomorrow' resolved the parked move"
    assert any(tr.ok for tr in reply2.tool_results)


def test_verification_demotes_false_success(sample_data, monkeypatch):
    """If a write lies about success, the loop must report failure."""
    from focus_agent import tools as ftools
    from focus_agent.schemas import ToolResult
    from focus_agent.schemas import ToolResult
    _mk_task(sample_data, "Essay", date="2026-10-28")

    task = TaskRepository(data := sample_data)
    rec = next(t for t in sample_data["tasks"] if t["title"] == "Essay")

    def lying_handler(d, args, ctx):
        # claims success but silently does NOT apply the update
        return ToolResult(True, "update_task", message="Updated 'Essay'",
                                 data={"task_id": rec["id"],
                                       "updated": dict(args)})

    import dataclasses
    monkeypatch.setitem(ftools.REGISTRY, "update_task",
                        dataclasses.replace(ftools.REGISTRY["update_task"],
                                            handler=lying_handler))
    loop = AgentLoop(sample_data, ctx={"settings": {}, "now": NOW})
    outcome = loop.run([Step("tool", "update_task",
                             {"task_ref": "Essay", "due_date": "2026-10-30"},
                             verify={"fields": {"due_date": "2026-10-30"}})])
    r = outcome.tool_results[0]
    assert not r.ok and "verification failed" in (r.error or "")
    assert any(e.type == "error" for e in outcome.events)


def test_repeat_detection_blocks_duplicate_calls(sample_data):
    _mk_task(sample_data, "Essay", date="2026-10-28")
    loop = AgentLoop(sample_data, ctx={"settings": {}, "now": NOW})
    step = Step("tool", "update_task", {"task_ref": "Essay", "due_date": "2026-10-29"})
    outcome = loop.run([step, step])
    assert outcome.ok_count == 1
    assert any(e.type == "repeat" for e in outcome.events)


def test_tool_budget_stops_turn(sample_data, monkeypatch):
    monkeypatch.setenv("FOCUS_AGENT_MAX_TOOL_CALLS", "1")
    _mk_task(sample_data, "T1", date="2026-10-28")
    _mk_task(sample_data, "T2", date="2026-10-28")
    loop = AgentLoop(sample_data, ctx={"settings": {}, "now": NOW})
    outcome = loop.run([
        Step("tool", "update_task", {"task_ref": "T1", "due_date": "2026-10-29"}),
        Step("tool", "update_task", {"task_ref": "T2", "due_date": "2026-10-29"}),
    ])
    assert outcome.status == "budget_exhausted"
    assert outcome.ok_count == 1
    assert any(e.type == "budget" for e in outcome.events)


def test_actions_persisted_with_verification_flag(sample_data, data_env):
    _mk_task(sample_data, "Essay", date="2026-10-28")
    loop = AgentLoop(sample_data, ctx={"settings": {}, "now": NOW},
                     conversation_id="conv-test")
    loop.run([Step("tool", "update_task", {"task_ref": "Essay", "due_date": "2026-10-30"},
                   verify={"fields": {"due_date": "2026-10-30"}})])
    actions = loop.memory.recent_actions(5)
    assert len(actions) == 1 and actions[-1]["tool"] == "update_task"
    assert actions[-1]["verified"] is True
    assert actions[-1]["conversation_id"] == "conv-test"


def test_task_choice_disambiguation_flow(sample_data):
    """Two matching tasks -> asks which -> ordinal answer executes the right one."""
    import logic
    _mk_task(sample_data, "Networking assignment", date="2026-10-28")
    _mk_task(sample_data, "Networking quiz prep", date="2026-10-29")
    c = AgentController(sample_data)
    reply = c.handle("I completed the networking task", provider=OfflineProvider(), now=NOW)
    assert reply.status == "asked_user" and "which one" in reply.message.lower()
    reply2 = c.handle("the first one", provider=OfflineProvider(), now=NOW)
    reloaded = logic.load_data()
    done = next(t for t in reloaded["tasks"] if t["title"] == "Networking assignment")
    assert done["status"] == "done"
    other = next(t for t in reloaded["tasks"] if t["title"] == "Networking quiz prep")
    assert other["status"] != "done"


def test_llm_garbage_step_decision_falls_back(sample_data):
    """MockProvider returns extraction-shaped JSON for step prompts too; the
    loop must degrade to the deterministic plan instead of crashing."""
    _mk_task(sample_data, "Essay", date="2026-10-28")
    loop = AgentLoop(sample_data, ctx={"settings": {}, "now": NOW},
                     provider=MockProvider({"intent": "add_task"}))
    from focus_agent.prompts import build_context_pack
    pack = build_context_pack(sample_data, NOW)
    decision = loop.provider and None  # provider presence must not matter
    from focus_agent.agent_loop import llm_decide_step
    d = llm_decide_step(MockProvider({"intent": "add_task"}), pack,
                        [{"name": "update_task"}])
    assert d is None, "non-step JSON must yield None (use deterministic plan)"


def test_offline_conversation_turns_persist(sample_data, data_env):
    c = AgentController(sample_data)
    c.handle("Add a 30-minute reading task tonight", provider=OfflineProvider(), now=NOW)
    with open(data_env["data_file"], encoding="utf-8") as fh:
        store = json.load(fh)
    convs = store["agent_memory"]["conversations"]
    assert convs, "conversation must persist"
    roles = [t["role"] for t in convs[-1]["turns"]]
    assert "user" in roles and "assistant" in roles


def test_pending_resume_for_new_task_creation(sample_data, data_env):
    """Deadline-sensitive add with no date: task created + question; answer
    sets the deadline via parked flow."""
    import logic
    c = AgentController(sample_data)
    r1 = c.handle("I need to submit the statistics project",
                  provider=OfflineProvider(), now=NOW)
    assert "?" in r1.message
    store = json.load(open(data_env["data_file"], encoding="utf-8"))
    created = [t for t in store["tasks"] if "statistics project" in (t["title"] or "").lower()]
    assert created and created[0]["date"] in ("", None)
    r2 = c.handle("next tuesday", provider=OfflineProvider(), now=NOW)
    store = json.load(open(data_env["data_file"], encoding="utf-8"))
    t = next(t for t in store["tasks"] if "statistics project" in (t["title"] or "").lower())
    assert t["date"] == "2026-10-27", "next Tuesday after Oct 23 is Oct 27"
    assert any(tr.ok for tr in r2.tool_results)
