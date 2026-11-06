# ==================== CONTROLLER.PY ====================
# Agent controller: understanding, step planning, loop orchestration, replies.
#
# Flow (spec §4.3): message -> pending-question resume? -> deterministic fast
# paths -> extraction (validated, LLM + local fallback) -> per-intent STEP PLAN
# -> AgentLoop executes with budgets/guards/verification -> reply composed from
# real ToolResults only.
#
# The LLM never writes to storage and never sees the raw store - context is a
# compact pack (prompts.py). When the provider is offline, every core workflow
# still runs through the deterministic plans.

from focus_agent import dates as fdates
from focus_agent import extractor as fextract
from focus_agent import scheduler as fsched
from focus_agent import planner as fplanner
from focus_agent import subjects as fsubjects
from focus_agent import goals as fgoals
from focus_agent.llm import (
    get_providers, LLMError, new_call_id,
)
from focus_agent import tools as ftools
from focus_agent.schemas import ToolCall, ToolResult
from focus_agent.agent_loop import AgentLoop, Step, LoopOutcome, llm_decide_step
from focus_agent.repository import TaskRepository, MemoryRepository
from focus_agent import models as m

from logic import (
    get_level_progress, get_today_tasks, get_today_focus_stats,
)

RESEARCH_HINTS = ("explain", "what is", "how do i", "best way", "resources",
                  "tutorial", "research", "compare", "recommend", "examples of")

# verbs/possessives stripped from task_ref candidates in the deterministic pass
_REF_LEAD_WORDS = ("move", "reschedule", "push", "shift", "postpone", "delay",
                   "delete", "remove", "cancel", "complete", "finish", "do",
                   "mark", "done with", "can you", "could you", "please")
_REF_TAIL_WORDS = ("to", "for", "by", "until", "till", "on")
_DATEISH_TOKENS = ("today", "tonight", "tomorrow", "next", "mon", "tue", "wed",
                   "thu", "fri", "sat", "sun", "monday", "tuesday", "wednesday",
                   "thursday", "friday", "saturday", "sunday")


class AgentReply:
    """What the UI receives: text + structured actions + plan + loop events."""

    def __init__(self, message, tool_results=None, extraction=None, plan=None,
                 status="ok", events=None):
        self.message = message
        self.tool_results = tool_results or []   # list[ToolResult]
        self.extraction = extraction             # ExtractionResult or None
        self.plan = plan                         # PlanResult.to_dict() or None
        self.status = status                     # ok | provider_offline | declined | asked_user | error
        self.events = events or []               # list[AgentEvent.to_dict()]

    def to_dict(self):
        return {
            "message": self.message,
            "tool_results": [t.to_dict() for t in self.tool_results],
            "extraction": self.extraction.to_dict() if self.extraction else None,
            "plan": self.plan,
            "status": self.status,
            "events": list(self.events),
        }


class AgentController:
    def __init__(self, data):
        self.data = data  # live reference to the app's loaded data dict
        self.repo = TaskRepository(data)
        self.memory = MemoryRepository(data)
        self._conversation_id = None

    # ---------------- context (minimal, privacy-preserving) ----------------

    def _compact_context(self):
        data = self.data
        lvl = data.get("level", 1)
        xp = data.get("xp", 0)
        settings = data.get("settings") or {}
        now = fdates.now_here(settings)
        today_tasks = [t for t in get_today_tasks(data) if t.get("type") != "class"]
        classes = [t for t in get_today_tasks(data) if t.get("type") == "class"]
        classes.sort(key=lambda t: (t.get("schedule") or {}).get("start", ""))
        next_cls = ""
        for c in classes:
            sch = c.get("schedule") or {}
            if sch.get("start", "99") >= now.strftime("%H:%M"):
                next_cls = f", next class '{c['title']}' at {sch.get('start')}"
                break
        return (f"Level {lvl}, {xp} XP. {len(today_tasks)} open task(s) today"
                f"{next_cls}. Date: {now.date().isoformat()} ({now.strftime('%A')}).")

    # ---------------- conversation helpers ----------------

    def _conversation(self):
        """Rolling conversation record for memory (created lazily)."""
        if self._conversation_id:
            return self._conversation_id
        latest = self.memory.latest_conversation()
        if latest and latest.get("status") == "open":
            self._conversation_id = latest["id"]
        else:
            conv = self.memory.open_conversation()
            self._conversation_id = conv.id
        return self._conversation_id

    def _remember_turn(self, role, content, tool_call_ids=None):
        try:
            self.memory.append_turn(self._conversation(),
                                    m.AgentTurnRecord(role=role, content=content[:2000],
                                                      ts=int(fdates.now_here({}).timestamp()),
                                                      tool_calls=tool_call_ids or []))
        except Exception:
            pass  # memory must never break a turn

    # ---------------- pending question resume ----------------

    def _try_pending_resume(self, text, now):
        """If a clarifying question is parked, try to consume `text` as the
        answer. Returns an AgentReply or None to fall through to normal flow."""
        conv = self.memory.latest_conversation()
        pending = (conv or {}).get("pending")
        if not pending:
            return None
        need = (pending.get("draft") or {}).get("need")
        draft = pending.get("draft") or {}
        settings = self.data.get("settings") or {}

        resolved = None  # (reply_builder)

        if need == "due_date":
            date_str, _matched = fdates.resolve_relative_date(text, now=now,
                                                              settings=settings)
            if not date_str:
                det = fextract.extract_deterministic(text, now=now, settings=settings)
                t0 = det.tasks[0] if det.tasks else None
                date_str = t0.due_date if t0 else None
            if date_str:
                resolved = self._resume_due_date(draft, date_str, now)
            elif any(w in text.lower() for w in ("no", "don't", "dont", "nope", "unknown", "not sure")):
                resolved = self._resume_due_date(draft, None, now)

        elif need == "task_choice":
            match = self._choose_candidate(text, draft.get("candidates") or [])
            if match:
                resolved = self._resume_task_choice(draft, match, now)

        elif need == "date_for_move":
            date_str, _matched = fdates.resolve_relative_date(text, now=now,
                                                              settings=settings)
            if not date_str:
                det = fextract.extract_deterministic(text, now=now, settings=settings)
                t0 = det.tasks[0] if det.tasks else None
                date_str = t0.due_date if t0 else None
            if date_str and draft.get("task_id"):
                resolved = self._resume_move(draft["task_id"], date_str, now)

        elif need == "subject_choice":
            match = fsubjects.match_subject(text, self.data)
            if match:
                resolved = self._resume_subject_choice(draft, match["subject"], now)

        if resolved is None:
            return None  # couldn't interpret; keep pending and fall through

        # consume the pending question
        try:
            self.memory.set_pending_question(self._conversation(), None)
        except Exception:
            pass
        return resolved

    def _choose_candidate(self, text, candidates):
        low = (text or "").lower().strip()
        if not low or not candidates:
            return None
        exact = next((c for c in candidates
                      if c.get("title", "").lower() == low), None)
        if exact:
            return exact
        hits = [c for c in candidates
                if any(w in c.get("title", "").lower()
                       for w in low.split() if len(w) > 2)]
        if len(hits) == 1:
            return hits[0]
        # ordinal pick: "the first one", "2"
        for idx_word, idx in (("first", 0), ("second", 1), ("third", 2)):
            if idx_word in low and len(candidates) > idx:
                return candidates[idx]
        if low.isdigit() and len(candidates) >= int(low) >= 1:
            return candidates[int(low) - 1]
        return None

    def _resume_due_date(self, draft, date_str, now):
        """Complete a parked create/update with the answered deadline."""
        task_id = draft.get("task_id")
        loop = AgentLoop(self.data, ctx=self._ctx(now),
                         conversation_id=self._conversation())
        if task_id and self.repo.get(task_id):
            if date_str:
                steps = [Step("tool", "update_task",
                              {"task_ref": task_id, "due_date": date_str},
                              note=f"Setting the deadline to {date_str}...",
                              verify={"fields": {"due_date": date_str}})]
                outcome = loop.run(steps)
                msg = outcome.tool_results[0].message if outcome.tool_results else ""
                return AgentReply(f"Done - deadline set to {date_str}. {msg}".strip(),
                                  tool_results=outcome.tool_results,
                                  status="ok", events=[e.to_dict() for e in outcome.events])
            return AgentReply("Okay, leaving the deadline open. You can set it "
                              "later by saying 'set the deadline for <task>'.")
        # no task yet (creation was never executed): create now
        args = dict(draft.get("args") or {})
        if date_str:
            args["due_date"] = date_str
        steps = [Step("tool", "create_task", args,
                      note="Creating your task...",
                      verify={"title": args.get("title", "")})]
        outcome = loop.run(steps)
        r = outcome.tool_results[0] if outcome.tool_results else ToolResult(
            False, "create_task", error="could not create task")
        return AgentReply(r.message or r.error or "Task saved.",
                          tool_results=outcome.tool_results,
                          status="ok" if r.ok else "error",
                          events=[e.to_dict() for e in outcome.events])

    def _resume_move(self, task_id, date_str, now):
        """Complete a parked move: update the date, then propose a replan."""
        loop = AgentLoop(self.data, ctx=self._ctx(now),
                         conversation_id=self._conversation())
        steps = [
            Step("tool", "update_task", {"task_ref": task_id, "due_date": date_str},
                 note=f"Moving to {date_str}...",
                 verify={"fields": {"due_date": date_str}}),
            Step("note", note="Rebuilding the affected day..."),
            Step("tool", "reschedule_day", {"date": date_str, "commit": False}),
        ]
        outcome = loop.run(steps)
        r = next((x for x in outcome.tool_results if x.tool == "update_task"), None)
        msg = (r.message or r.error or "Task moved.") if r else "Task moved."
        plan = next((x.data.get("plan") for x in outcome.tool_results
                     if x.tool == "reschedule_day" and x.ok and x.data), None)
        if plan and not plan.get("_committed") and "apply it to commit" not in msg:
            msg += "\nReview the proposed schedule - apply it to commit."
        return AgentReply(msg, tool_results=outcome.tool_results,
                          plan=plan, status="ok",
                          events=[e.to_dict() for e in outcome.events])

    def _resume_task_choice(self, draft, chosen, now):
        action = draft.get("action") or "update_task"
        if action == "reschedule_task" and not (draft.get("args") or {}).get("due_date"):
            # the move target is known; the date is still missing -> ask next
            question = (f"Move '{chosen.get('title')}' to which date? "
                        "(e.g. 'friday', 'next monday')")
            pending = m.AgentPendingQuestion(
                question=question, intent="reschedule",
                draft={"need": "date_for_move", "task_id": chosen.get("id")},
                asked_at=int(fdates.now_here({}).timestamp()))
            try:
                self.memory.set_pending_question(self._conversation(), pending)
            except Exception:
                pass
            return AgentReply(question, status="asked_user")
        loop = AgentLoop(self.data, ctx=self._ctx(now),
                         conversation_id=self._conversation())
        args = dict(draft.get("args") or {})
        args["task_ref"] = chosen.get("id") or chosen.get("title")
        steps = [Step("tool", action, args,
                      note=f"{action.replace('_', ' ').capitalize()} '{chosen.get('title')}'...",
                      verify=self._verify_for(action))]
        outcome = loop.run(steps)
        r = outcome.tool_results[0] if outcome.tool_results else None
        msg = (r.message or r.error or "Done.") if r else "Done."
        return AgentReply(msg, tool_results=outcome.tool_results,
                          status="ok" if (r and r.ok) else "error",
                          events=[e.to_dict() for e in outcome.events])

    def _resume_subject_choice(self, draft, subject, now):
        loop = AgentLoop(self.data, ctx=self._ctx(now),
                         conversation_id=self._conversation())
        task_id = draft.get("task_id")
        steps = [Step("tool", "assign_subject",
                      {"task_ref": task_id, "subject": subject},
                      note=f"Assigning subject '{subject}'...")]
        outcome = loop.run(steps)
        r = outcome.tool_results[0] if outcome.tool_results else None
        return AgentReply((r.message or r.error or "Subject assigned."),
                          tool_results=outcome.tool_results,
                          status="ok" if (r and r.ok) else "error",
                          events=[e.to_dict() for e in outcome.events])

    @staticmethod
    def _verify_for(action):
        if action == "complete_task":
            return {"status": "done"}
        if action == "delete_task":
            return {"removed": True}
        return {}

    # ---------------- public entry ----------------

    def handle(self, text, history=None, confirm_callback=None, provider=None,
               now=None):
        """Process one user message. Always returns an AgentReply.

        provider/now are injectable for tests; production callers omit them.
        """
        text = (text or "").strip()
        if not text:
            return AgentReply("Say something and I'll help - try 'Add a 45-minute "
                              "Python practice task for tonight'.")
        settings = self.data.get("settings") or {}
        now = now or fdates.now_here(settings)
        primary, online = get_providers(settings)
        if provider is not None:
            primary = provider
        self._active_provider = primary
        self._active_online = online
        self._remember_turn("user", text)

        # 0. parked clarification resume
        resumed = self._try_pending_resume(text, now)
        if resumed is not None:
            self._remember_turn("assistant", resumed.message)
            return resumed

        # 1. Deterministic intent; fast paths answer without any model
        det_intent, det_action = fextract.detect_intent(text)
        if det_intent == "chat" and re_greeting(text):
            reply = AgentReply(
                "Hey! I'm your Focus agent. Try:\n"
                "• 'Tomorrow submit my AI assignment; it will take about two hours'\n"
                "• 'Plan my day'  • 'What should I prioritize?'  • 'I want to learn robotics'")
            self._remember_turn("assistant", reply.message)
            return reply
        if det_intent == "query":
            reply = self._answer_query(det_action or _guess_query_action(text), now)
            self._remember_turn("assistant", reply.message)
            return reply

        # 2. Extraction (LLM when available; deterministic otherwise)
        subject_names = fsubjects.get_known_subjects(self.data).keys()
        try:
            extraction = fextract.extract(
                text, provider=primary, now=now, settings=settings,
                subject_names=subject_names)
        except LLMError as e:
            extraction = fextract.extract_deterministic(text, now=now, settings=settings)
            extraction.warnings.append(f"AI provider unavailable: {e}")

        provider_offline = any("provider unavailable" in w.lower()
                               for w in extraction.warnings)

        # 3. Plan steps per intent, run the loop, compose the reply
        intent = extraction.intent
        planner = {
            "add_task": self._plan_tasks,
            "update_task": self._plan_tasks,
            "complete_task": self._plan_task_ref,
            "delete_task": self._plan_task_ref,
            "reschedule": self._plan_reschedule,
            "block_time": self._plan_blocks,
            "plan_day": None,                      # read-only, handled directly
            "goal": self._plan_goal,
            "query": None,
            "chat": None,
        }.get(intent, "chat")

        if intent == "plan_day":
            reply = self._reply_plan(text, extraction, now)
        elif intent == "block_time":
            steps = self._plan_blocks(text, extraction, now)
            loop = AgentLoop(self.data, ctx=self._ctx(now),
                             confirm_callback=confirm_callback,
                             conversation_id=self._conversation())
            outcome = loop.run(steps)
            reply = self._compose("block_time", extraction, outcome, now)
        elif intent == "query":
            reply = self._answer_query(extraction.query_action
                                       or _guess_query_action(text), now)
        elif intent == "chat":
            reply = self._route_chat(text, extraction, now, primary, online, history)
        elif planner == "chat" or planner is None:
            reply = self._route_chat(text, extraction, now, primary, online, history)
        else:
            steps = planner(text, extraction, now)
            loop = AgentLoop(self.data, ctx=self._ctx(now),
                             confirm_callback=confirm_callback,
                             conversation_id=self._conversation())
            outcome = loop.run(steps)
            reply = self._compose(intent, extraction, outcome, now)

        if provider_offline and reply.status == "ok":
            reply.message += "\n\n_(AI provider offline - used the built-in local parser.)_"
            reply.status = "provider_offline"
        self._remember_turn("assistant", reply.message,
                            [f"{tr.tool}:{tr.ok}" for tr in reply.tool_results])
        return reply

    # ---------------- deterministic query answers ----------------

    def _answer_query(self, action, now):
        data = self.data
        if action == "productivity":
            from focus_agent import estimator as fest
            est = fest.estimation_analytics(data)
            comp = fest.completion_analytics(data)
            focus = data.get("focus_sessions", {})
            week = sorted(focus.keys())[-7:]
            week_min = sum(round(focus[d].get("total_seconds", 0) / 60) for d in week)
            lines = ["📊 **Last 7 days**"]
            lines.append(f"⏱ Focus time: {week_min}min across {len(week)} active day(s)")
            if est.get("n"):
                lines.append(f"🎯 Estimation: actuals ran {est['mean_error_ratio']}x "
                             f"estimates on average ({est['n']} completed tasks, "
                             f"MAE {est['mae_minutes']}min)")
            else:
                lines.append("🎯 No estimate-vs-actual data yet - complete timed tasks "
                             "and I'll learn your pace.")
            if comp.get("done_ratio") is not None:
                lines.append(f"✅ Completion: {comp['done_ratio']:.0%} of tasks done "
                             f"({comp['completed_total']} total)")
            return AgentReply("\n".join(lines))
        if action == "stats":
            curr, req, pct = get_level_progress(data)
            lvl = data.get("level", 1)
            xp = data.get("xp", 0)
            focus = get_today_focus_stats(data)
            streak = data.get("streak", 0)
            return AgentReply(
                f"📊 **Your Stats**\n"
                f"⭐ Level {lvl} — {xp} XP ({curr}/{req} XP, {int(pct)}% to next level)\n"
                f"🔥 {streak}-day activity streak\n"
                f"⏱ Today: {focus['formatted_total']} focus"
                + (f" + {focus['formatted_class']} class time" if focus["class_seconds"] else ""))
        if action == "next_class":
            today = now.strftime("%a").lower()[:3]
            t_str = now.strftime("%H:%M")
            classes = []
            for t in data.get("tasks", []):
                if t.get("type") != "class":
                    continue
                sch = t.get("schedule") or {}
                if today in sch.get("days", []) and sch.get("start", "") >= t_str:
                    classes.append((sch["start"], sch.get("end"), t["title"]))
            classes.sort()
            if not classes:
                return AgentReply("🎉 No more classes today.")
            s, e, title = classes[0]
            return AgentReply(f"📅 Your next class is **{title}**, {s}–{e}.")
        if action == "weekly_classes":
            week = fsubjects.subjects_for_routine(data)
            lines = ["📅 **This week's classes**"]
            any_cls = False
            for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
                for c in week[day]:
                    any_cls = True
                    lines.append(f"• **{day}** {c['start']}–{c['end']}: {c['title']}")
            return AgentReply("\n".join(lines) if any_cls else
                              "No classes in your routine yet - add them in the Routine tab.")
        # default: today
        items = get_today_tasks(data)
        tasks = [t for t in items if t.get("type") != "class"]
        classes = sorted([t for t in items if t.get("type") == "class"],
                         key=lambda t: (t.get("schedule") or {}).get("start", ""))
        lines = [f"📅 **Today ({now.date().isoformat()})**"]
        for c in classes:
            sch = c.get("schedule") or {}
            lines.append(f"📘 {c['title']} {sch.get('start')}–{sch.get('end')}")
        for t in tasks[:12]:
            due = f" (due {t['date']})" if t.get("date") else ""
            dur = f" ~{t['duration']}m" if t.get("duration") else ""
            lines.append(f"📝 {t['title']}{due}{dur}")
        if len(lines) == 1:
            lines.append("Nothing scheduled - a good moment to plan or add tasks!")
        return AgentReply("\n".join(lines))

    # ---------------- step planning: tasks ----------------

    def _plan_tasks(self, text, extraction, now):
        """Steps for add/update intents. Ambiguous subject -> ask step."""
        steps: list[Step] = []
        if not extraction.tasks:
            if extraction.question:
                steps.append(Step("ask", args={"question": extraction.question,
                                               "intent": "add_task"}))
                return steps
            steps.append(Step("note", note="Looking for a task in that..."))
            return steps
        for t in extraction.tasks:
            args = {
                "title": t.title or "New Task",
                "description": getattr(t, "description", None),
                "subject": t.subject,
                "due_date": t.due_date,
                "due_time": t.due_time,
                "duration_minutes": t.estimated_minutes,
                "importance": t.importance,
                "difficulty": t.difficulty,
                "priority_hint": t.priority_hint,
                "subtasks": t.subtasks,
                "recurrence": t.recurrence,
                "goal_title": t.goal_title,
            }
            steps.append(Step("tool", "create_task", args,
                              note=f"Creating task '{args['title']}'...",
                              verify={"title": args["title"]}))
        # material ambiguity AFTER creation (task exists, deadline unknown)
        q = extraction.question or self._material_question(text, extraction)
        if q:
            first = extraction.tasks[0]
            steps.append(Step("ask", args={
                "question": q, "intent": "add_task",
                "draft": {"need": "due_date",
                          "args": {"title": first.title or "New Task",
                                   "duration_minutes": first.estimated_minutes,
                                   "subject": first.subject,
                                   "importance": first.importance}},
            }))
        return steps

    def _material_question(self, text, extraction):
        """Deadline-sensitive created task with no date -> follow-up question."""
        first = extraction.tasks[0] if extraction.tasks else None
        if first and first.task_ref is None and not first.due_date:
            low = (text or "").lower()
            if any(k in low for k in fextract.DEADLINE_SENSITIVE):
                return ("When is this due? (e.g. 'tomorrow', 'next monday', "
                        "or a date) - I don't want to guess a deadline.")
        return None

    # ---------------- step planning: complete/delete ----------------

    def _plan_task_ref(self, text, extraction, now):
        t0 = extraction.tasks[0] if extraction.tasks else None
        ref = t0.task_ref if t0 else None
        intent = extraction.intent
        action = {"complete_task": "complete_task", "delete_task": "delete_task",
                  "reschedule": "reschedule_task"}.get(intent, "complete_task")
        # resolve the ref to exactly one task, else disambiguate
        task = self.repo.find_fuzzy(ref) if ref else None
        if task:
            args = {"task_ref": task["id"]}
            if intent == "complete_task" and t0.estimated_minutes:
                args["actual_minutes"] = t0.estimated_minutes
            return [Step("tool", action, args,
                         note=f"{action.replace('_', ' ').capitalize()} "
                              f"'{task.get('title')}'...",
                         verify=self._verify_for(action))]
        candidates = self._candidate_tasks(ref or "")
        if candidates:
            return [Step("note", note="Looking for that task..."),
                    self._ask_task_choice(extraction, candidates)]
        return [Step("note", note="Which task? Give me part of its title, "
                                  "e.g. \"complete database assignment\".")]

    def _candidate_tasks(self, ref):
        """Open tasks matching a fuzzy ref, for disambiguation asks."""
        tasks = [t for t in self.data.get("tasks", [])
                 if t.get("type") == "task" and t.get("status") not in ("done", "archived")]
        if ref:
            frag = ref.lower().strip()
            words = [w for w in frag.split() if len(w) > 2]
            scored = [t for t in tasks
                      if any(w in (t.get("title") or "").lower() for w in words)]
            if scored:
                return scored[:5]
        return tasks[:5]

    def _ask_task_choice(self, extraction, candidates):
        lines = [f"• {c.get('title')} (due {c.get('date') or 'no date'})"
                 for c in candidates]
        question = ("I found more than one matching task - which one?\n"
                    + "\n".join(lines))
        return Step("ask", args={
            "question": question,
            "intent": extraction.intent,
            "draft": {"need": "task_choice", "action": _ACTION_FOR_INTENT[extraction.intent],
                      "candidates": [{"id": c.get("id"), "title": c.get("title")}
                                     for c in candidates],
                      "args": _REF_ARGS_FOR_INTENT.get(extraction.intent, {})},
        })

    # ---------------- step planning: reschedule ----------------

    def _plan_reschedule(self, text, extraction, now):
        """Move a task: resolve -> update date -> propose replan."""
        steps: list[Step] = []
        t0 = extraction.tasks[0] if extraction.tasks else None
        ref = t0.task_ref if t0 else None
        low = (text or "").lower()
        target_date = t0.due_date if t0 else None

        task = self.repo.find_fuzzy(ref) if ref else None
        if not task:
            candidates = self._candidate_tasks(ref or "")
            if candidates:
                steps.append(Step("note", note="Looking for that task..."))
                steps.append(self._ask_task_choice(extraction, candidates))
                return steps
            return [Step("note", note=f"I couldn't find a task matching "
                                      f"'{ref}'. Check the Tasks tab or rephrase.")]

        steps.append(Step("note", note=f"Found '{task.get('title')}' - checking "
                                       "the new date..."))
        if not target_date:
            if "next available" in low or not low.strip():
                target_date = fdates.today_str(self.data.get("settings"))
            else:
                steps.append(Step("ask", args={
                    "question": f"Move '{task.get('title')}' to which date? "
                                "(e.g. 'friday', 'next monday')",
                    "intent": "reschedule",
                    "draft": {"need": "date_for_move",
                              "task_id": task.get("id")},
                }))
                return steps
        steps.append(Step("tool", "update_task",
                          {"task_ref": task["id"], "due_date": target_date},
                          note=f"Moving to {target_date}...",
                          verify={"fields": {"due_date": target_date}}))
        steps.append(Step("note", note="Rebuilding the affected day..."))
        steps.append(Step("tool", "reschedule_day",
                          {"date": target_date, "commit": False}))
        return steps

    # ---------------- step planning: goals ----------------

    def _plan_goal(self, text, extraction, now):
        goal_info = dict(extraction.goal or {})
        raw_title = goal_info.get("title") or (extraction.tasks[0].title if extraction.tasks else None)
        cleaned = fextract.clean_goal_title(text)
        if not raw_title:
            title = cleaned
        else:
            low_raw = raw_title.lower()
            if any(w in low_raw for w in ("shikte", "sikhte", "shokte", "millstone", "mailstone",
                                          "milestone", "banay", "dao", "want to", "amk")):
                title = cleaned
            elif raw_title.islower():
                title = raw_title.title()
            else:
                title = raw_title
        if not title:
            return [Step("ask", args={
                "question": "What's the goal? e.g. 'I want to learn AI/ML by December'.",
                "intent": "goal",
                "draft": {"need": "goal_title"},
            })]
        goal_info["title"] = title
        extraction.goal = goal_info

        weeks = 8
        if goal_info.get("target_date"):
            try:
                from datetime import date as _d
                delta = (_d.fromisoformat(goal_info["target_date"]) - now.date()).days
                weeks = max(2, min(26, delta // 7 or 2))
            except (ValueError, TypeError):
                pass
        prov = getattr(self, "_active_provider", None)
        if getattr(prov, "name", "") not in ("ollama", "online"):
            prov = None
        draft, _ = fgoals.generate_roadmap_draft(
            title, weeks=weeks, hours_per_week=8,
            start_date=now.date().isoformat(), provider=prov
        )
        self._last_goal_draft = draft
        ms_titles = [m["title"] for m in (draft.get("milestones") if draft else [])]

        # If an older empty goal with the same title exists (0 milestones), remove it first
        existing = [
            g for g in self.data.get("goals", [])
            if (g.get("title") or "").strip().lower() == title.strip().lower()
            and not g.get("milestones")
        ]
        for eg in existing:
            self.data["goals"].remove(eg)

        return [Step("tool", "create_goal",
                     {"title": title,
                      "description": goal_info.get("description"),
                      "target_date": goal_info.get("target_date"),
                      "milestones": ms_titles},
                     note=f"Creating goal '{title}' with {len(ms_titles)} milestones...",
                     verify={})]

    # ---------------- compose replies from outcomes ----------------

    def _compose(self, intent, extraction, outcome: LoopOutcome, now):
        msg = "\n".join((r.message or r.error or "") for r in outcome.tool_results
                        if r).strip()
        # a parked question is the reply when no tool work happened this turn
        q = outcome.pending.get("question") if outcome.pending else None
        if q and not msg:
            msg = q
        elif q:
            msg = f"{msg}\n\n❓ {q}"
        if intent == "complete_task" and outcome.ok_count:
            settings = self.data.get("settings") or {}
            plan = fsched.reschedule_after_change(self.data, fdates.today_str(settings),
                                                  settings=settings, now=now)
            if plan.slots:
                msg += (f"\n\n💡 I can reshuffle the rest of today ({len(plan.slots)} "
                        "slot(s) proposed) - say 'reschedule my day' to apply.")
        if intent == "reschedule":
            plan_result = next((r for r in outcome.tool_results
                                if r.tool == "reschedule_day" and r.ok), None)
            plan = (plan_result.data or {}).get("plan") if plan_result else None
            if plan and not plan_result.data.get("committed"):
                msg += "\nReview the proposed schedule below - apply it to commit."
            reply = AgentReply(msg or "Task moved.",
                               tool_results=outcome.tool_results,
                               extraction=extraction, plan=plan,
                               status="ok" if outcome.status != "asked_user" else "asked_user",
                               events=[e.to_dict() for e in outcome.events])
            return reply
        if intent == "goal":
            msg = self._goal_roadmap_addendum(extraction, outcome, msg, now)
        status = "ok"
        if outcome.status == "asked_user":
            status = "asked_user"
        elif outcome.status == "budget_exhausted":
            status = "ok"  # partial work still reported honestly in events
        elif any((not r.ok) for r in outcome.tool_results):
            status = "error"
        return AgentReply(msg or "Done.", tool_results=outcome.tool_results,
                          extraction=extraction, status=status,
                          events=[e.to_dict() for e in outcome.events])

    def _goal_roadmap_addendum(self, extraction, outcome, msg, now):
        """Persist target dates/hours on the created goal's milestones and return a clear, friendly summary."""
        if not any(r.ok for r in outcome.tool_results if r.tool == "create_goal"):
            return msg
        goal_info = extraction.goal or {}
        title = goal_info.get("title") or (extraction.tasks[0].title if extraction.tasks else "")
        draft = getattr(self, "_last_goal_draft", None)
        if not draft:
            weeks = 8
            if goal_info.get("target_date"):
                try:
                    from datetime import date as _d
                    delta = (_d.fromisoformat(goal_info["target_date"]) - now.date()).days
                    weeks = max(2, min(26, delta // 7 or 2))
                except (ValueError, TypeError):
                    pass
            draft, _ = fgoals.generate_roadmap_draft(
                title, weeks=weeks, hours_per_week=8, start_date=now.date().isoformat()
            )
        if not draft:
            return msg

        created = next((r for r in outcome.tool_results
                        if r.tool == "create_goal" and r.ok), None)
        goal_id = (created.data or {}).get("goal_id") if created else None
        if goal_id:
            goal_obj = fgoals.get_goal(self.data, goal_id)
            if goal_obj:
                if not goal_obj.get("milestones"):
                    for mm in draft["milestones"]:
                        goal_obj["milestones"].append(fgoals._new_milestone(
                            mm["title"], mm.get("target_date"), mm.get("estimated_minutes")
                        ))
                else:
                    for ms_obj, mm in zip(goal_obj["milestones"], draft["milestones"]):
                        ms_obj["target_date"] = mm.get("target_date")
                        ms_obj["estimated_minutes"] = mm.get("estimated_minutes")
                if not goal_obj.get("target_date") and draft["milestones"]:
                    goal_obj["target_date"] = draft["milestones"][-1].get("target_date")
                from logic import save_data
                save_data(self.data)
                if created:
                    created.message = (
                        f"Created goal '{goal_obj['title']}' with "
                        f"{len(goal_obj['milestones'])} milestone(s)"
                    )

        ms_lines = []
        for idx, mm in enumerate(draft["milestones"], start=1):
            m_title = mm["title"]
            # Avoid double numbering like "1. 1. ..."
            if not _re.match(r"^\d+[\.\)]\s*", m_title):
                m_title = f"{idx}. {m_title}"
            hrs = round((mm.get("estimated_minutes") or 360) / 60, 1)
            hrs_txt = f"{int(hrs)}h" if hrs == int(hrs) else f"{hrs}h"
            ms_lines.append(f"• **{m_title}**  _(📅 Target: {mm['target_date']} · ~{hrs_txt} study)_")

        friendly = (
            f"🎯 **Goal & Roadmap Created: {title}**\n"
            f"I have created your goal with **{len(draft['milestones'])} step-by-step milestones** "
            f"and saved everything to your **Goals & Roadmaps** tab:\n\n"
            + "\n".join(ms_lines)
            + "\n\n💡 _Tip: Open the **🎯 Goals & Roadmaps** tab from the sidebar anytime to track your progress and check off each milestone as you finish it!_"
        )
        return friendly

    # ---------------- planning (read-only proposal) ----------------

    def _plan_blocks(self, text, extraction, now):
        """Steps for 'don't schedule X to Y' requests."""
        if not extraction.blocks:
            q = extraction.question or ("What time should I keep free? "
                                        "(e.g. 'from 10 AM to 12 PM')")
            return [Step("ask", args={"question": q, "intent": "block_time",
                                      "draft": {"need": "block_times"}})]
        steps: list[Step] = []
        for b in extraction.blocks[:3]:
            args = {"title": b["title"], "start": b["start"], "end": b["end"]}
            if b.get("days"):
                args["days"] = b["days"]
            if b.get("date"):
                args["date"] = b["date"]
            steps.append(Step("tool", "create_schedule_block", args,
                              note=f"Blocking {b['start']}–{b['end']} for "
                                   f"'{b['title']}'...",
                              verify={}))
        return steps

    def _reply_plan(self, text, extraction, now):
        settings = self.data.get("settings") or {}
        capacity = extraction.available_minutes
        low = (text or "").lower()
        # explicit capacity ("three hours free") or a named day -> range planner
        day_str, _m = fdates.resolve_relative_date(text, now=now, settings=settings)
        multi_day = "week" in low
        if capacity or multi_day or (day_str and day_str != now.date().isoformat()):
            start = day_str or fdates.today_str(settings)
            # learned productive hours shape where work lands (disclosed)
            from focus_agent import patterns as fpatterns
            hours = fpatterns.productive_hours(self.data)
            hour_scores = hours["hours"] if hours.get("reliable") else None
            plan = fplanner.plan_range(self.data, start, settings=settings,
                                       now=now, days=7 if multi_day else 1,
                                       capacity_minutes=capacity, commit=False,
                                       hour_scores=hour_scores)
            if hour_scores:
                plan.notes.append(f"Placed work using learned productive hours "
                                  f"({hours['basis']})")
            lines = [f"🗓 **Plan from {plan.start_date}"
                     + (f" to {plan.end_date}**" if multi_day else "**")]
            for d in plan.days:
                if d.slots:
                    lines.append(f"_{d.date}_")
                for s in d.slots:
                    lines.append(f"• **{s.start}–{s.end}** {s.title}")
            for u in plan.unschedulable:
                lines.append(f"⚠ **{u['title']}**: {u['reason']}")
            lines.extend(plan.notes)
            if capacity:
                lines.append(f"(limited to the {capacity}min you said you have)")
            lines.append("\nSay **'apply the plan'** (or open the Planner tab) to commit it.")
            return AgentReply("\n".join(lines), extraction=extraction,
                              plan=plan.to_dict())
        # default: today's single-day kernel proposal (legacy behavior)
        date_str = fdates.today_str(settings)
        plan = fsched.generate_day_plan(self.data, date_str,
                                        settings=settings, now=now, commit=False)
        lines = [f"🗓 **Plan for {date_str}**"]
        for s in plan.slots:
            fixed = "✅" if s.fixed else "•"
            chunk = (f" (part {s.chunk}/{s.chunks})" if s.chunks > 1 else "")
            lines.append(f"{fixed} **{s.start}–{s.end}** {s.title}{chunk}")
        for u in plan.unscheduled:
            lines.append(f"⚠ **{u['title']}**: {u['reason']}")
        lines.extend(plan.notes)
        lines.append("\nSay **'apply the plan'** (or open the Planner tab) to commit it.")
        return AgentReply("\n".join(lines), extraction=extraction,
                          plan=plan.to_dict())

    # ---------------- query / chat via LLM ----------------

    def _route_chat(self, text, extraction, now, primary, online, history):
        # Autonomous Hybrid Router: automatically combines online knowledge / cloud LLM
        # and local AI without requiring manual user switching.
        low = text.lower()
        wants_research = any(h in low for h in RESEARCH_HINTS) or any(
            k in low for k in ("explain", "what is", "how to", "how does", "ki", "kivabe",
                               "keno", "learn", "study", "roadmap", "syllabus", "guide")
        )
        use_provider = None
        disclosure = ""
        online_context = ""

        if wants_research and online is not None:
            use_provider = online
            disclosure = "🌐 _Auto-Routed: Online Cloud AI_\n\n"
        elif wants_research and getattr(primary, "name", "") in ("ollama", "online"):
            from focus_agent.llm import fetch_online_topic_summary
            online_context = fetch_online_topic_summary(text)
            if online_context:
                disclosure = "🌐 _Auto-Hybrid AI (Live Online Knowledge + Local AI)_\n\n"

        provider = use_provider or primary
        try:
            sys_prompt = (
                "You are the Focus Agent assistant for a student. "
                "Write in clear, warm, friendly language that a non-technical student can easily understand. "
                "If the user writes in Bangla or Banglish, reply naturally in clear Bangla/Banglish (with English technical terms where helpful). "
                f"User context: {self._compact_context()}. "
            )
            if online_context:
                sys_prompt += f"\nLive Online Reference Knowledge:\n{online_context}\n"
            sys_prompt += (
                "For task/schedule/goal actions, remind them they can also say "
                "'add task ...', 'plan my day', or 'I want to learn <topic> with milestones'."
            )
            answer = provider.chat(
                system=sys_prompt,
                user=text, history=history, temperature=0.4, max_tokens=700)
            return AgentReply(disclosure + answer, extraction=extraction)
        except LLMError as e:
            fallback = (f"I can't reach the AI model right now ({e}).\n"
                        "Everything else keeps working — you can still:\n"
                        "• Add tasks: e.g. 'Tomorrow math assignment due at 8 PM, 2 hours'\n"
                        "• Create learning roadmaps: e.g. 'I want to learn networking with milestones'\n"
                        "• Plan your day: say 'Plan my day'")
            return AgentReply(fallback, extraction=extraction, status="provider_offline")

    # ---------------- utils ----------------

    def _ctx(self, now):
        return {"settings": self.data.get("settings") or {}, "now": now}


_ACTION_FOR_INTENT = {"complete_task": "complete_task", "delete_task": "delete_task",
                      "reschedule": "reschedule_task"}
_REF_ARGS_FOR_INTENT = {"complete_task": {}, "delete_task": {}, "reschedule": {}}


import re as _re  # noqa: E402  (used by route helpers)


def re_greeting(text):
    return bool(_re.match(r"^\s*(hi|hello|hey|yo|thanks|thank you|good\s+(morning|evening|afternoon))\b",
                          (text or "").lower()))


def _guess_query_action(text):
    low = (text or "").lower()
    if "xp" in low or "level" in low:
        return "stats"
    if "next class" in low:
        return "next_class"
    if "week" in low:
        return "weekly_classes"
    return "today_tasks"
