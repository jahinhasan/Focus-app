# ==================== CONTROLLER.PY ====================
# Agent controller / conversation orchestration.
#
# Flow: message -> (fast deterministic answers) -> LLM extraction (validated,
# with local fallback) -> route by intent -> validated tool calls (with user
# confirmation for anything destructive or schedule-changing) -> reply with
# explicit tool results.
#
# The LLM never writes to storage and never sees the whole database - context
# is a small, explicit summary. When the provider is offline, every core
# workflow still works through the deterministic paths.

from focus_agent import dates as fdates
from focus_agent import extractor as fextract
from focus_agent import scheduler as fsched
from focus_agent import subjects as fsubjects
from focus_agent import goals as fgoals
from focus_agent.llm import (
    get_providers, LLMError, new_call_id,
)
from focus_agent import tools as ftools
from focus_agent.schemas import ToolCall, ToolResult

from logic import (
    get_level_progress, get_today_tasks, get_today_focus_stats,
)

RESEARCH_HINTS = ("explain", "what is", "how do i", "best way", "resources",
                  "tutorial", "research", "compare", "recommend", "examples of")


class AgentReply:
    """What the UI receives: text + structured actions + plan proposals."""

    def __init__(self, message, tool_results=None, extraction=None, plan=None,
                 status="ok"):
        self.message = message
        self.tool_results = tool_results or []   # list[ToolResult]
        self.extraction = extraction             # ExtractionResult or None
        self.plan = plan                         # PlanResult.to_dict() or None
        self.status = status                     # ok | provider_offline | declined | error

    def to_dict(self):
        return {
            "message": self.message,
            "tool_results": [t.to_dict() for t in self.tool_results],
            "extraction": self.extraction.to_dict() if self.extraction else None,
            "plan": self.plan,
            "status": self.status,
        }


class AgentController:
    def __init__(self, data):
        self.data = data  # live reference to the app's loaded data dict

    # ---------------- context (minimal, privacy-preserving) ----------------

    def _compact_context(self):
        data = self.data
        lvl, xp, _ = get_level_progress(data)
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

    # ---------------- public entry ----------------

    def handle(self, text, history=None, confirm_callback=None, provider=None, now=None):
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

        # 1. Deterministic intent; fast paths answer without any model
        det_intent, det_action = fextract.detect_intent(text)
        if det_intent == "chat" and re_greeting(text):
            return AgentReply(
                "Hey! I'm your Focus agent. Try:\n"
                "• 'Tomorrow submit my AI assignment; it will take about two hours'\n"
                "• 'Plan my day'  • 'What should I prioritize?'  • 'I want to learn robotics'")
        if det_intent == "query":
            return self._answer_query(det_action or _guess_query_action(text), now)

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

        # 3. Route
        intent = extraction.intent
        handler = {
            "add_task": self._route_tasks,
            "update_task": self._route_tasks,
            "complete_task": self._route_task_ref,
            "delete_task": self._route_task_ref,
            "reschedule": self._route_reschedule,
            "plan_day": self._route_plan,
            "goal": self._route_goal,
            "query": self._route_query_llm,
            "chat": self._route_chat,
        }.get(intent)
        if handler is None:
            handler = self._route_chat

        reply = handler(text, extraction, now, primary, online, confirm_callback,
                        history)
        if provider_offline and reply.status == "ok":
            reply.message += "\n\n_(AI provider offline - used the built-in local parser.)_"
            reply.status = "provider_offline"
        return reply

    # ---------------- deterministic query answers ----------------

    def _answer_query(self, action, now):
        data = self.data
        if action == "stats":
            lvl, xp, pct = get_level_progress(data)
            focus = get_today_focus_stats(data)
            streak = data.get("streak", 0)
            return AgentReply(
                f"📊 **Your Stats**\n"
                f"⭐ Level {lvl} — {xp} XP ({int(pct)}% to next level)\n"
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

    # ---------------- task creation/update ----------------

    def _route_tasks(self, text, extraction, now, primary, online, confirm_cb,
                     history):
        if not extraction.tasks:
            if extraction.question:
                return AgentReply(extraction.question, extraction=extraction)
            return AgentReply("I couldn't find a task in that - try phrasing it like "
                              "'Add math homework due Friday, about 1 hour'.",
                              extraction=extraction)
        results = []
        for t in extraction.tasks:
            call = ToolCall(
                tool="create_task",
                args={
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
                },
                call_id=new_call_id(), source=extraction.source)
            results.append(ftools.execute_tool(self.data, call,
                                               ctx=self._ctx(now),
                                               confirm_callback=confirm_cb))
        msg = "\n".join(r.message or r.error for r in results if r)
        if extraction.question:
            msg += f"\n\n❓ {extraction.question}"
        return AgentReply(msg, tool_results=results, extraction=extraction)

    def _route_task_ref(self, text, extraction, now, primary, online, confirm_cb,
                        history):
        t0 = extraction.tasks[0] if extraction.tasks else None
        if not t0 or not t0.task_ref:
            return AgentReply("Which task? Give me part of its title, e.g. "
                              "\"complete database assignment\".", extraction=extraction)
        tool_name = {"complete_task": "complete_task", "delete_task": "delete_task",
                     "reschedule": "reschedule_day"}.get(extraction.intent,
                                                         "complete_task")
        args = {"task_ref": t0.task_ref}
        if extraction.intent == "complete_task" and t0.estimated_minutes:
            args["actual_minutes"] = t0.estimated_minutes
        call = ToolCall(tool=tool_name, args=args, call_id=new_call_id(),
                        source=extraction.source)
        result = ftools.execute_tool(self.data, call, ctx=self._ctx(now),
                                     confirm_callback=confirm_cb)
        reply_msg = result.message or result.error
        # completing work affects the rest of the day -> propose a refresh
        if result.ok and extraction.intent == "complete_task":
            settings = self.data.get("settings") or {}
            plan = fsched.reschedule_after_change(self.data, fdates.today_str(settings),
                                                  settings=settings, now=now)
            if plan.slots:
                reply_msg += (f"\n\n💡 I can reshuffle the rest of today ({len(plan.slots)} "
                              "slot(s) proposed) - say 'reschedule my day' to apply.")
        return AgentReply(reply_msg, tool_results=[result], extraction=extraction)

    def _route_reschedule(self, text, extraction, now, primary, online, confirm_cb,
                          history):
        t0 = extraction.tasks[0] if extraction.tasks else None
        results = []
        if t0 and t0.task_ref and "next available" in (text or "").lower():
            # move unfinished task to next feasible slot: update its date then replan
            task = ftools._find_task_fuzzy(self.data, t0.task_ref)
            if not task:
                return AgentReply(f"I couldn't find a task matching '{t0.task_ref}'.",
                                  extraction=extraction, status="error")
            from logic import update_task_logic
            update_task_logic(self.data, task["id"],
                              date=fdates.today_str(self.data.get("settings")))
            results.append(ToolResult(
                True, "update_task",
                message=f"Moved '{task.get('title')}' into today's candidate pool"))
        call = ToolCall(tool="reschedule_day", args={"date": fdates.today_str(self.data.get("settings"))},
                        call_id=new_call_id(), source="local")
        result = ftools.execute_tool(self.data, call, ctx=self._ctx(now),
                                     confirm_callback=confirm_cb)
        results.append(result)
        plan = (result.data or {}).get("plan")
        msg = result.message or result.error or ""
        if plan and not result.data.get("committed"):
            msg += "\nReview the proposed schedule below - apply it to commit."
        return AgentReply(msg, tool_results=results, extraction=extraction, plan=plan)

    # ---------------- planning ----------------

    def _route_plan(self, text, extraction, now, primary, online, confirm_cb,
                    history):
        date_str = fdates.today_str(self.data.get("settings"))
        plan = fsched.generate_day_plan(self.data, date_str,
                                        settings=self.data.get("settings"),
                                        now=now, commit=False)
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

    # ---------------- goals ----------------

    def _route_goal(self, text, extraction, now, primary, online, confirm_cb,
                    history):
        goal_info = extraction.goal or {}
        title = goal_info.get("title") or (extraction.tasks[0].title if extraction.tasks else None)
        if not title:
            return AgentReply("What's the goal? e.g. 'I want to learn AI/ML by December'.",
                              extraction=extraction)
        call = ToolCall(tool="create_goal",
                        args={"title": title, "description": goal_info.get("description"),
                              "target_date": goal_info.get("target_date")},
                        call_id=new_call_id(), source=extraction.source)
        result = ftools.execute_tool(self.data, call, ctx=self._ctx(now),
                                     confirm_callback=confirm_cb)
        msg = result.message or result.error
        # propose an editable roadmap draft (labeled assumptions, not persisted as fact)
        weeks = 8
        if goal_info.get("target_date"):
            try:
                from datetime import date as _d
                delta = (_d.fromisoformat(goal_info["target_date"]) - now.date()).days
                weeks = max(2, min(26, delta // 7 or 2))
            except (ValueError, TypeError):
                pass
        draft, err = fgoals.generate_roadmap_draft(title, weeks=weeks,
                                                   hours_per_week=8)
        if draft:
            draft["goal_id"] = (result.data or {}).get("goal_id")
            msg += ("\n\n**Draft roadmap** (assumptions: " + "; ".join(draft["assumptions"]) + "):\n"
                    + "\n".join(f"• {m['title']} → by {m['target_date']}"
                                for m in draft["milestones"])
                    + "\nEdit milestones in the Goals tab - nothing is set in stone.")
        return AgentReply(msg, tool_results=[result], extraction=extraction)

    # ---------------- query / chat via LLM ----------------

    def _route_query_llm(self, text, extraction, now, primary, online, confirm_cb,
                         history):
        if extraction.query_action:
            return self._answer_query(extraction.query_action, now)
        return self._route_chat(text, extraction, now, primary, online,
                                confirm_cb, history)

    def _route_chat(self, text, extraction, now, primary, online, confirm_cb,
                    history):
        # research-shaped questions may use the online provider - with disclosure
        low = text.lower()
        wants_research = any(h in low for h in RESEARCH_HINTS)
        use_provider = None
        disclosure = ""
        if wants_research and online is not None:
            use_provider = online
            disclosure = "🌐 _This answer used your configured online provider._\n\n"
        elif wants_research and online is None:
            disclosure = ("_No online research provider is configured, so this is a "
                          "local answer without web research._\n\n")
        provider = use_provider or primary
        try:
            answer = provider.chat(
                system=("You are the Focus Dashboard assistant for a student. "
                        "Be concise, practical and encouraging. "
                        f"User context: {self._compact_context()}. "
                        "You cannot change data directly - suggest commands like "
                        "'add task ...', 'plan my day', 'reschedule'."),
                user=text, history=history, temperature=0.4, max_tokens=700)
            return AgentReply(disclosure + answer, extraction=extraction)
        except LLMError as e:
            fallback = (f"I can't reach the AI provider right now ({e}).\n"
                        "Everything else keeps working - I can still:\n"
                        "• add tasks from plain text (local parser)\n"
                        "• plan and reschedule your day\n"
                        "• answer questions about your stats and routine")
            return AgentReply(fallback, extraction=extraction, status="provider_offline")

    # ---------------- utils ----------------

    def _ctx(self, now):
        return {"settings": self.data.get("settings") or {}, "now": now}


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
