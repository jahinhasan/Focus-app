# ==================== PROMPTS.PY ====================
# All LLM prompt templates + the compact, privacy-preserving context pack the
# agent loop sends with each step decision. The pack is explicit and bounded -
# the model never sees the raw store (rule: LLM never touches storage).

from __future__ import annotations

import json

MAX_CONTEXT_TASKS = 25


def build_context_pack(data, now, *, pending=None, known_subjects=None,
                       recent_turns=None) -> str:
    """Compact text pack: profile line, open tasks, today's classes, memory."""
    from logic import get_today_tasks
    settings = data.get("settings") or {}
    from focus_agent import dates as fdates
    today = now.date().isoformat()

    lines = [f"DATE: {today} ({now.strftime('%A')})"]
    lvl, xp, _ = (data.get("level", 1), data.get("xp", 0), 0)
    streak = data.get("streak", 0)
    lines.append(f"PROFILE: level {lvl}, {xp} XP, {streak}-day streak")

    # open tasks (bounded, no notes/IDs beyond what tools need)
    open_tasks = []
    for t in data.get("tasks", []):
        if t.get("type") != "task" or t.get("status") in ("done", "archived"):
            continue
        open_tasks.append(t)
    open_tasks.sort(key=lambda t: (t.get("date") or "9999", -(t.get("importance") or 2)))
    frag = []
    for t in open_tasks[:MAX_CONTEXT_TASKS]:
        parts = [f'id={t.get("id")}', repr(t.get("title", ""))]
        if t.get("date"):
            parts.append(f"due={t['date']}")
        if t.get("duration"):
            parts.append(f"~{t['duration']}m")
        if t.get("subject"):
            parts.append(f"subject={t['subject']}")
        frag.append("- " + ", ".join(parts))
    lines.append("OPEN TASKS:" if frag else "OPEN TASKS: none")
    lines.extend(frag)

    classes = [t for t in get_today_tasks(data) if t.get("type") == "class"]
    classes.sort(key=lambda t: (t.get("schedule") or {}).get("start", ""))
    if classes:
        cl = [f"- {c['title']} {(c.get('schedule') or {}).get('start')}-"
              f"{(c.get('schedule') or {}).get('end')}" for c in classes]
        lines.append("TODAY'S CLASSES:")
        lines.extend(cl)

    if known_subjects:
        lines.append("KNOWN SUBJECTS: " + ", ".join(list(known_subjects)[:25]))

    if recent_turns:
        lines.append("RECENT CONVERSATION:")
        for r in recent_turns[-4:]:
            who = "USER" if r.get("role") == "user" else "AGENT"
            lines.append(f"- {who}: {str(r.get('content'))[:160]}")

    if pending:
        lines.append(f"PENDING QUESTION YOU ASKED: {pending.get('question')}")
        if pending.get("draft"):
            lines.append(f"PENDING CONTEXT: {json.dumps(pending['draft'])[:300]}")

    return "\n".join(lines)


STEP_SYSTEM_PROMPT = """You are the decision module of a student productivity agent.
Each turn you receive a CONTEXT pack and must decide the NEXT single step.
Respond with ONLY one JSON object:

{"action": "tool_call", "tool": "<name>", "args": {...}, "why": "<short reason>"}
{"action": "final", "reply": "<final user-facing summary>"}
{"action": "ask_user", "question": "<one concise question>"}

Rules:
- Tools are the only way to change anything. Choose from the TOOL CATALOG given.
- Use null for unknown values. NEVER invent dates, durations, or subjects.
- If required information is missing and cannot be found in CONTEXT, ask the user.
- Do not repeat a tool call whose result is already in CONTEXT.
- Prefer the smallest correct action; stop with "final" once the goal is met."""


def build_step_decision_prompt(context_pack: str, tool_catalog, history_note="") -> str:
    """One user-message payload for the step decision call."""
    catalog = []
    for t in tool_catalog:
        schema = t.get("schema") or {}
        fields = ", ".join(
            f"{k}:{r.get('type', 'str')}{'!' if r.get('required') else ''}"
            for k, r in list(schema.items())[:10])
        catalog.append(f"- {t['name']}({fields}): {t['description']}"
                       + (" [needs user confirmation]" if t.get("requires_confirmation") else ""))
    parts = [STEP_SYSTEM_PROMPT, "",
             "TOOL CATALOG:", *catalog, "",
             "CONTEXT:", context_pack]
    if history_note:
        parts += ["", "NOTE: " + history_note]
    return "\n".join(parts)


__all__ = ["build_context_pack", "build_step_decision_prompt", "STEP_SYSTEM_PROMPT"]
