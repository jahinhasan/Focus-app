# ==================== TOOLS.PY ====================
# Validated agent tool layer - the ONLY way model-proposed actions touch data.
#
# Every tool declares a typed schema, a permission class, and whether it needs
# user confirmation. Execution path: validate args -> check confirmation ->
# run bounded handler -> explicit ToolResult -> audit log. No shell, no SQL,
# no eval, no arbitrary file access, no direct DB writes from the model.

from dataclasses import dataclass

from logic import (
    add_task_logic, delete_task_logic, update_task_logic, complete_task_logic,
    reopen_task_logic, record_actual_duration, get_task_by_id, add_subtask,
    add_subject, add_xp, get_today_focus_stats, get_analytics_data,
)
from focus_agent import dates as fdates
from focus_agent import subjects as fsubjects
from focus_agent import scheduler as fsched
from focus_agent import estimator as fest
from focus_agent import goals as fgoals
from focus_agent import memory as fmemory
from focus_agent.schemas import ToolResult, validate_tool_args, clean_str


@dataclass
class ToolSpec:
    name: str
    description: str
    schema: dict                       # field -> {type, required, ...}
    permission: str = "read"           # read | write | destructive
    requires_confirmation: bool = False
    confirm_fn: object = None          # callable(data, args) -> (bool, reason)
    handler: object = None


REGISTRY = {}


def tool(name, description, schema, permission="read", requires_confirmation=False,
         confirm_fn=None):
    def deco(fn):
        REGISTRY[name] = ToolSpec(
            name=name, description=description, schema=schema,
            permission=permission, requires_confirmation=requires_confirmation,
            confirm_fn=confirm_fn, handler=fn)
        return fn
    return deco


def list_tools():
    """Tool catalog for prompts and docs (sorted, bounded)."""
    return [{"name": s.name, "description": s.description, "schema": s.schema,
             "permission": s.permission,
             "requires_confirmation": s.requires_confirmation}
            for s in (REGISTRY[k] for k in sorted(REGISTRY))]


def execute_tool(data, call, ctx=None, confirm_callback=None):
    """Validate + execute one ToolCall. Never raises; returns ToolResult.

    - ctx: dict with at least {'settings', 'now'} (timezone-aware now).
    - confirm_callback(question) -> bool: invoked for confirmation-required tools.
    - Idempotency: repeated call_id within the session returns the cached
      outcome instead of executing twice.
    """
    ctx = ctx or {}
    settings = ctx.get("settings") or (data.get("settings") or {})
    spec = REGISTRY.get(call.tool)
    if spec is None:
        return ToolResult(False, call.tool, error=f"Unknown tool '{call.tool}'")

    # Idempotency guard (retry protection)
    if call.call_id and not fmemory.remember_call(data, call.call_id):
        return ToolResult(True, call.tool,
                          message="Already executed (duplicate request ignored).",
                          data={"duplicate": True})

    args, errors = validate_tool_args(spec, call.args)
    if errors:
        fmemory.forget_call(data, call.call_id) if call.call_id else None
        return ToolResult(False, call.tool,
                          error="Invalid arguments: " + "; ".join(errors[:5]))

    confirmed = False
    if spec.requires_confirmation:
        reason = ""
        if spec.confirm_fn is not None:
            allowed, reason = spec.confirm_fn(data, args)
            if not allowed:
                if call.call_id:
                    fmemory.forget_call(data, call.call_id)
                return ToolResult(False, call.tool,
                                  error=f"Not allowed: {reason}")
        question = reason or f"Allow '{spec.name}' with {args}?"
        if confirm_callback is None:
            if call.call_id:
                fmemory.forget_call(data, call.call_id)
            return ToolResult(False, call.tool,
                              error="Confirmation required but no UI available - ask the user first.",
                              data={"needs_confirmation": True, "question": question})
        confirmed = bool(confirm_callback(question))
        if not confirmed:
            if call.call_id:
                fmemory.forget_call(data, call.call_id)
            return ToolResult(False, call.tool, message="User declined this action.",
                              data={"declined": True}, confirmed=False)

    try:
        result = spec.handler(data, args, {"settings": settings, "now": ctx.get("now")})
    except Exception as e:  # bounded: any handler crash becomes a ToolResult
        if call.call_id:
            fmemory.forget_call(data, call.call_id)
        return ToolResult(False, call.tool,
                          error=f"Tool failed: {e.__class__.__name__}")
    result.confirmed = confirmed
    if call.call_id:
        fmemory.log_tool_execution(data, call.call_id, call.tool, args,
                                   result.ok, result.message or result.error or "")
    return result


# ==================== HELPERS ====================

def _find_task_fuzzy(data, ref):
    """Find a task by exact id, then substring title match (best effort)."""
    if not ref:
        return None
    tasks = data.get("tasks", []) + data.get("archived_tasks", [])
    t = get_task_by_id(data, ref)
    if t:
        return t
    frag = ref.lower().strip()
    matches = [t for t in tasks if frag in (t.get("title") or "").lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return sorted(matches, key=lambda t: t.get("updated_at") or "", reverse=True)[0]
    return None


def _subject_names(data):
    return list(fsubjects.get_known_subjects(data).keys())


def _match_or_none(data, mention):
    if not mention:
        return None, None
    m = fsubjects.match_subject(mention, data)
    if m and m["auto"]:
        return m["subject"], m
    return None, m


# ==================== TASK TOOLS ====================

@tool("list_tasks", "List tasks with optional filters (status, subject, due date range, text search).",
      {"status": {"type": "str"}, "subject": {"type": "str"},
       "search": {"type": "str"}, "due_before": {"type": "date"},
       "due_after": {"type": "date"}, "limit": {"type": "int", "min": 1, "max": 100, "default": 25}})
def tool_list_tasks(data, args, ctx):
    tasks = list(data.get("tasks", []))
    if args.get("status"):
        tasks = [t for t in tasks if t.get("status") == args["status"]]
    if args.get("subject"):
        subj = args["subject"].lower()
        tasks = [t for t in tasks if subj in (t.get("subject") or "").lower()]
    if args.get("search"):
        q = args["search"].lower()
        tasks = [t for t in tasks if q in (t.get("title") or "").lower()
                 or q in (t.get("notes") or "").lower()]
    if args.get("due_before"):
        tasks = [t for t in tasks if t.get("date") and t["date"] <= args["due_before"]]
    if args.get("due_after"):
        tasks = [t for t in tasks if t.get("date") and t["date"] >= args["due_after"]]
    tasks.sort(key=lambda t: (t.get("date") or "9999", -(t.get("importance") or 2)))
    out = [{
        "id": t.get("id"), "title": t.get("title"), "status": t.get("status"),
        "subject": t.get("subject"), "due_date": t.get("date"),
        "duration_minutes": t.get("duration"), "type": t.get("type"),
        "importance": t.get("importance"), "difficulty": t.get("difficulty"),
    } for t in tasks[:args.get("limit", 25)]]
    total = len(tasks)
    return ToolResult(True, "list_tasks", message=f"{total} task(s) matched",
                      data={"count": total, "tasks": out})


@tool("get_task", "Inspect one task's full details by id or title fragment.",
      {"task_ref": {"type": "str", "required": True, "max": 200}})
def tool_get_task(data, args, ctx):
    t = _find_task_fuzzy(data, args["task_ref"])
    if not t:
        return ToolResult(False, "get_task", error=f"No task matching {args['task_ref']!r}")
    return ToolResult(True, "get_task", message=t.get("title", ""), data={"task": t})


@tool("create_task", "Create a task. Subject auto-matches the class routine; ambiguous matches ask first.",
      {"title": {"type": "str", "required": True, "max": 200},
       "description": {"type": "str", "max": 1000},
       "subject": {"type": "str", "max": 120},
       "due_date": {"type": "date"}, "due_time": {"type": "hhmm"},
       "duration_minutes": {"type": "int", "min": 5, "max": 960},
       "importance": {"type": "int", "min": 1, "max": 3},
       "difficulty": {"type": "int", "min": 1, "max": 3},
       "priority_hint": {"type": "int", "min": 0, "max": 100},
       "subtasks": {"type": "str_list"},
       "goal_title": {"type": "str", "max": 200},
       "recurrence": {"type": "any"}},
      permission="write")
def tool_create_task(data, args, ctx):
    title = args["title"]
    subject_assigned, match_info = _match_or_none(data, args.get("subject"))
    subject_note = None
    if args.get("subject") and subject_assigned is None:
        m = match_info
        if m:
            subject_note = (f"Subject not auto-assigned: '{args['subject']}' resembles "
                            f"'{m['subject']}' (confidence {m['confidence']:.2f}) - "
                            "confirm the subject in the Vault or restate it exactly.")
        else:
            subject_note = (f"No subject matches '{args['subject']}' - left unassigned. "
                            "Create it from the Vault if needed.")
        subject_assigned = None

    goal_id = None
    if args.get("goal_title"):
        g = fgoals.find_goal_by_title(data, args["goal_title"])
        goal_id = g.get("id") if g else None

    recurrence = args.get("recurrence")
    if isinstance(recurrence, dict) and recurrence.get("type") not in ("daily", "weekly"):
        recurrence = None

    task = add_task_logic(
        data, title,
        deadline=args.get("due_date"),
        duration=args.get("duration_minutes"),
        subject=subject_assigned,
        notes=clean_str(args.get("description"), 1000) or "",
    )
    if not task:
        return ToolResult(False, "create_task", error="Task title was empty")
    # enriched fields (add_task_logic covers the V1 subset)
    updates = {}
    if args.get("due_time"):
        updates["due_time"] = args["due_time"]
    if args.get("importance") is not None:
        updates["importance"] = args["importance"]
    if args.get("difficulty") is not None:
        updates["difficulty"] = args["difficulty"]
    if args.get("priority_hint") is not None:
        updates["priority_hint"] = args["priority_hint"]
    if goal_id:
        updates["goal_id"] = goal_id
    if recurrence:
        updates["recurrence"] = recurrence
    if updates:
        update_task_logic(data, task["id"], **updates)

    for st in (args.get("subtasks") or [])[:20]:
        add_subtask(data, task["id"], st)

    due_txt = f", due {args.get('due_date')}" if args.get("due_date") else " (no deadline)"
    dur_txt = f", ~{args['duration_minutes']}min" if args.get("duration_minutes") else ""
    msg = f"Created task '{title}'{due_txt}{dur_txt}"
    if subject_assigned:
        msg += f" [subject: {subject_assigned}]"
    payload = {"task_id": task["id"], "title": title,
               "subject": subject_assigned, "due_date": args.get("due_date")}
    if subject_note:
        payload["subject_note"] = subject_note
        msg += ". " + subject_note
    return ToolResult(True, "create_task", message=msg, data=payload)


@tool("update_task", "Update an existing task's fields (deadline, duration, subject, priority, notes).",
      {"task_ref": {"type": "str", "required": True, "max": 200},
       "title": {"type": "str", "max": 200},
       "due_date": {"type": "date"}, "duration_minutes": {"type": "int", "min": 5, "max": 960},
       "subject": {"type": "str", "max": 120},
       "importance": {"type": "int", "min": 1, "max": 3},
       "difficulty": {"type": "int", "min": 1, "max": 3},
       "notes": {"type": "str", "max": 1000}},
      permission="write")
def tool_update_task(data, args, ctx):
    t = _find_task_fuzzy(data, args["task_ref"])
    if not t:
        return ToolResult(False, "update_task", error=f"No task matching {args['task_ref']!r}")
    updates = {}
    for arg_key, field_key in (("title", "title"), ("due_date", "date"),
                               ("duration_minutes", "duration"), ("notes", "notes"),
                               ("importance", "importance"), ("difficulty", "difficulty")):
        if args.get(arg_key) is not None:
            updates[field_key] = args[arg_key]
    subject_assigned, match_info = None, None
    if args.get("subject"):
        subject_assigned, match_info = _match_or_none(data, args["subject"])
        if subject_assigned:
            updates["subject"] = subject_assigned
    if not updates:
        return ToolResult(False, "update_task", error="Nothing to update")
    update_task_logic(data, t["id"], **updates)
    msg = f"Updated '{t.get('title')}' ({', '.join(sorted(updates))})"
    if args.get("subject") and not subject_assigned:
        msg += (f" - subject '{args['subject']}' was not auto-assigned"
                + (f"; closest is '{match_info['subject']}' - confirm it"
                   if match_info else " (no similar subject exists)"))
    return ToolResult(True, "update_task", message=msg,
                      data={"task_id": t["id"], "updated": updates})


@tool("complete_task", "Mark a task as done and record focus outcomes.",
      {"task_ref": {"type": "str", "required": True, "max": 200},
       "actual_minutes": {"type": "int", "min": 1, "max": 1440}},
      permission="write")
def tool_complete_task(data, args, ctx):
    t = _find_task_fuzzy(data, args["task_ref"])
    if not t:
        return ToolResult(False, "complete_task", error=f"No task matching {args['task_ref']!r}")
    if t.get("status") == "done":
        return ToolResult(True, "complete_task",
                          message=f"'{t.get('title')}' is already done.",
                          data={"task_id": t["id"], "already_done": True})
    if args.get("actual_minutes"):
        record_actual_duration(data, t["id"], args["actual_minutes"])
    complete_task_logic(data, t["id"])
    msg = f"Completed '{t.get('title')}' (+10 XP)"
    if args.get("actual_minutes"):
        est = t.get("duration")
        if est:
            diff = args["actual_minutes"] - est
            msg += f". Actual {args['actual_minutes']}min vs estimated {est}min "
            msg += f"({abs(diff)}min {'over' if diff > 0 else 'under'})"
    return ToolResult(True, "complete_task", message=msg, data={"task_id": t["id"]})


@tool("reopen_task", "Reopen a completed task.", {"task_ref": {"type": "str", "required": True, "max": 200}},
      permission="write")
def tool_reopen_task(data, args, ctx):
    t = _find_task_fuzzy(data, args["task_ref"])
    if not t:
        return ToolResult(False, "reopen_task", error=f"No task matching {args['task_ref']!r}")
    if reopen_task_logic(data, t["id"]):
        return ToolResult(True, "reopen_task", message=f"Reopened '{t.get('title')}'")
    return ToolResult(False, "reopen_task", error="Task cannot be reopened")


@tool("delete_task", "Delete a task permanently.", {"task_ref": {"type": "str", "required": True, "max": 200}},
      permission="destructive", requires_confirmation=True)
def tool_delete_task(data, args, ctx):
    t = _find_task_fuzzy(data, args["task_ref"])
    if not t:
        return ToolResult(False, "delete_task", error=f"No task matching {args['task_ref']!r}")
    delete_task_logic(data, t["id"])
    return ToolResult(True, "delete_task", message=f"Deleted '{t.get('title')}'",
                      data={"task_id": t["id"]})


@tool("add_subtask", "Add a subtask to a task.",
      {"task_ref": {"type": "str", "required": True, "max": 200},
       "title": {"type": "str", "required": True, "max": 200}},
      permission="write")
def tool_add_subtask(data, args, ctx):
    t = _find_task_fuzzy(data, args["task_ref"])
    if not t:
        return ToolResult(False, "add_subtask", error=f"No task matching {args['task_ref']!r}")
    add_subtask(data, t["id"], args["title"])
    return ToolResult(True, "add_subtask",
                      message=f"Added subtask '{args['title']}' to '{t.get('title')}'",
                      data={"task_id": t["id"]})


# ==================== SUBJECT / ROUTINE TOOLS ====================

@tool("list_subjects", "List known subjects and where they come from.", {})
def tool_list_subjects(data, args, ctx):
    known = fsubjects.get_known_subjects(data)
    items = [{"name": n, "source": s} for n, s in sorted(known.items())]
    return ToolResult(True, "list_subjects", message=f"{len(items)} subject(s)",
                      data={"subjects": items})


@tool("create_subject", "Create a new subject in the Vault.",
      {"name": {"type": "str", "required": True, "max": 120}},
      permission="write", requires_confirmation=True)
def tool_create_subject(data, args, ctx):
    name = args["name"]
    if add_subject(data, name):
        return ToolResult(True, "create_subject", message=f"Created subject '{name}'")
    return ToolResult(True, "create_subject", message=f"Subject '{name}' already exists",
                      data={"existed": True})


@tool("assign_subject", "Attach a task to a subject (fuzzy match must be confident).",
      {"task_ref": {"type": "str", "required": True, "max": 200},
       "subject": {"type": "str", "required": True, "max": 120}},
      permission="write")
def tool_assign_subject(data, args, ctx):
    t = _find_task_fuzzy(data, args["task_ref"])
    if not t:
        return ToolResult(False, "assign_subject", error=f"No task matching {args['task_ref']!r}")
    m = fsubjects.match_subject(args["subject"], data)
    if not m:
        return ToolResult(False, "assign_subject",
                          error=(f"No subject matches '{args['subject']}'. Create it first "
                                 "(I will ask for confirmation) or check the spelling."))
    update_task_logic(data, t["id"], subject=m["subject"])
    conf = "" if m["auto"] else f" (low confidence {m['confidence']:.2f} - verify)"
    return ToolResult(True, "assign_subject",
                      message=f"'{t.get('title')}' assigned to subject '{m['subject']}'{conf}",
                      data={"task_id": t["id"], "subject": m["subject"],
                            "confidence": m["confidence"]})


@tool("get_routine", "Read the weekly class routine.", {"day": {"type": "str"}})
def tool_get_routine(data, args, ctx):
    week = fsubjects.subjects_for_routine(data)
    if args.get("day"):
        day = args["day"].lower()[:3]
        if day not in week:
            return ToolResult(False, "get_routine", error="day must be mon..sun")
        return ToolResult(True, "get_routine", message=f"{len(week[day])} class(es) on {day}",
                          data={"day": day, "classes": week[day]})
    total = sum(len(v) for v in week.values())
    return ToolResult(True, "get_routine", message=f"{total} classes/week",
                      data={"week": week})


@tool("add_class", "Add a recurring class to the routine.",
      {"title": {"type": "str", "required": True, "max": 120},
       "days": {"type": "str_list", "required": True},
       "start": {"type": "hhmm", "required": True},
       "end": {"type": "hhmm", "required": True}},
      permission="write")
def tool_add_class(data, args, ctx):
    days = [d for d in (str(x).lower()[:3] for x in args["days"])
            if d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")]
    if not days:
        return ToolResult(False, "add_class", error="days must include at least one of mon..sun")
    if args["start"] >= args["end"]:
        return ToolResult(False, "add_class", error="start must be before end")
    sch = {"days": sorted(set(days)), "start": args["start"], "end": args["end"]}
    task = add_task_logic(data, args["title"], category="class", days=sch["days"],
                          schedule=sch, subject=args["title"])
    return ToolResult(True, "add_class",
                      message=f"Added class '{args['title']}' {', '.join(sch['days'])} "
                              f"{args['start']}-{args['end']}",
                      data={"class_id": task["id"]})


# ==================== PLANNING TOOLS ====================

@tool("get_availability", "Read free/busy intervals for a date.",
      {"date": {"type": "date"}})
def tool_get_availability(data, args, ctx):
    date_str = args.get("date") or fdates.today_str(ctx.get("settings"))
    free, busy, info = fsched.get_availability(data, date_str, ctx.get("settings"))
    free_fmt = [{"start": fdates.minutes_to_hhmm(iv["start"]),
                 "end": fdates.minutes_to_hhmm(iv["end"]),
                 "minutes": iv["end"] - iv["start"]} for iv in free]
    return ToolResult(True, "get_availability",
                      message=f"{sum(i['minutes'] for i in free_fmt)}min free on {date_str}",
                      data={"date": date_str, "free": free_fmt, "classes": info["classes"]})


@tool("generate_daily_plan", "Build the day's schedule from priorities, classes and free time.",
      {"date": {"type": "date"}, "commit": {"type": "bool", "default": False}},
      permission="write", requires_confirmation=True)
def tool_generate_daily_plan(data, args, ctx):
    date_str = args.get("date") or fdates.today_str(ctx.get("settings"))
    plan = fsched.generate_day_plan(data, date_str, settings=ctx.get("settings"),
                                    now=ctx.get("now"), commit=False)
    if args.get("commit"):
        fsched.apply_plan(data, plan)
        fmemory.log_plan(data, plan.to_dict())
    return ToolResult(True, "generate_daily_plan",
                      message=(f"Plan for {date_str}: {len(plan.slots)} slot(s), "
                               f"{len(plan.unscheduled)} unscheduled"),
                      data={"plan": plan.to_dict(), "committed": bool(args.get("commit"))})


@tool("explain_priorities", "Ranked task list with transparent reasons.",
      {"date": {"type": "date"}})
def tool_explain_priorities(data, args, ctx):
    date_str = args.get("date") or fdates.today_str(ctx.get("settings"))
    ranked = fsched.explain_priorities(data, date_str, settings=ctx.get("settings"),
                                       now=ctx.get("now"))
    return ToolResult(True, "explain_priorities",
                      message=f"{len(ranked)} open task(s) ranked",
                      data={"date": date_str, "ranked": ranked[:30]})


@tool("reschedule_day", "Rebuild the remaining schedule after delays or early finishes (preserves done/started work).",
      {"date": {"type": "date"}, "commit": {"type": "bool", "default": False}},
      permission="write", requires_confirmation=True)
def tool_reschedule_day(data, args, ctx):
    date_str = args.get("date") or fdates.today_str(ctx.get("settings"))
    plan = fsched.reschedule_after_change(data, date_str, settings=ctx.get("settings"),
                                          now=ctx.get("now"))
    if args.get("commit"):
        fsched.apply_plan(data, plan)
        fmemory.log_plan(data, plan.to_dict())
    return ToolResult(True, "reschedule_day",
                      message=(f"Proposed revised plan for {date_str}: "
                               f"{len(plan.slots)} slot(s), {len(plan.unscheduled)} unscheduled"),
                      data={"plan": plan.to_dict(), "committed": bool(args.get("commit"))})


# ==================== GOALS TOOLS ====================

@tool("list_goals", "List goals with progress and upcoming milestones.", {})
def tool_list_goals(data, args, ctx):
    out = []
    for g in data.get("goals", []):
        prog = fgoals.goal_progress(data, g)
        out.append({"id": g["id"], "title": g["title"], "status": g["status"],
                    "target_date": g.get("target_date"), "progress": prog})
    return ToolResult(True, "list_goals", message=f"{len(out)} goal(s)",
                      data={"goals": out})


@tool("create_goal", "Create a long-term goal, optionally with milestones.",
      {"title": {"type": "str", "required": True, "max": 200},
       "description": {"type": "str", "max": 2000},
       "target_date": {"type": "date"},
       "subject": {"type": "str", "max": 120},
       "milestones": {"type": "str_list"}},
      permission="write")
def tool_create_goal(data, args, ctx):
    ms = [{"title": t} for t in (args.get("milestones") or [])]
    goal, err = fgoals.add_goal(data, args["title"], args.get("description"),
                                args.get("target_date"), args.get("subject"), ms)
    if err:
        return ToolResult(False, "create_goal", error=err)
    return ToolResult(True, "create_goal",
                      message=(f"Created goal '{goal['title']}' with "
                               f"{len(goal['milestones'])} milestone(s)"),
                      data={"goal_id": goal["id"]})


@tool("update_goal", "Update, pause, complete or edit a goal.",
      {"goal_ref": {"type": "str", "required": True, "max": 200},
       "status": {"type": "str"}, "title": {"type": "str", "max": 200},
       "description": {"type": "str", "max": 2000}, "target_date": {"type": "date"}},
      permission="write")
def tool_update_goal(data, args, ctx):
    g = fgoals.find_goal_by_title(data, args["goal_ref"])
    if not g:
        return ToolResult(False, "update_goal", error=f"No goal matching {args['goal_ref']!r}")
    ok, err = fgoals.update_goal(data, g["id"], status=args.get("status"),
                                 title=args.get("title"),
                                 description=args.get("description"),
                                 target_date=args.get("target_date"))
    if not ok:
        return ToolResult(False, "update_goal", error=err or "Update failed")
    return ToolResult(True, "update_goal", message=f"Updated goal '{g['title']}'",
                      data={"goal_id": g["id"]})


@tool("add_milestone", "Add a milestone to a goal.",
      {"goal_ref": {"type": "str", "required": True, "max": 200},
       "title": {"type": "str", "required": True, "max": 200},
       "target_date": {"type": "date"},
       "estimated_minutes": {"type": "int", "min": 5, "max": 10000}},
      permission="write")
def tool_add_milestone(data, args, ctx):
    g = fgoals.find_goal_by_title(data, args["goal_ref"])
    if not g:
        return ToolResult(False, "add_milestone", error=f"No goal matching {args['goal_ref']!r}")
    ms, err = fgoals.add_milestone(data, g["id"], args["title"],
                                   args.get("target_date"), args.get("estimated_minutes"))
    if err:
        return ToolResult(False, "add_milestone", error=err)
    return ToolResult(True, "add_milestone",
                      message=f"Added milestone '{ms['title']}' to '{g['title']}'",
                      data={"goal_id": g["id"], "milestone_id": ms["id"]})


@tool("complete_milestone", "Mark a milestone done.",
      {"goal_ref": {"type": "str", "required": True, "max": 200},
       "milestone_ref": {"type": "str", "required": True, "max": 200}},
      permission="write")
def tool_complete_milestone(data, args, ctx):
    g = fgoals.find_goal_by_title(data, args["goal_ref"])
    if not g:
        return ToolResult(False, "complete_milestone", error=f"No goal matching {args['goal_ref']!r}")
    frag = args["milestone_ref"].lower()
    ms = next((m for m in g["milestones"] if frag in (m.get("title") or "").lower()
               or m.get("id") == args["milestone_ref"]), None)
    if not ms:
        return ToolResult(False, "complete_milestone",
                          error=f"No milestone matching {args['milestone_ref']!r}")
    fgoals.update_milestone(data, g["id"], ms["id"], done=True)
    add_xp(data, 25)
    return ToolResult(True, "complete_milestone",
                      message=f"Milestone '{ms['title']}' completed on '{g['title']}' (+25 XP)",
                      data={"goal_id": g["id"], "milestone_id": ms["id"]})


# ==================== HISTORY / ANALYTICS TOOLS ====================

@tool("get_focus_history", "Focus-session totals and recent days.",
      {"days": {"type": "int", "min": 1, "max": 90, "default": 7}})
def tool_get_focus_history(data, args, ctx):
    today_stats = get_today_focus_stats(data)
    focus = data.get("focus_sessions", {})
    days = sorted(focus.keys())[-args.get("days", 7):]
    out = [{"date": d,
            "focus_minutes": round(focus[d].get("total_seconds", 0) / 60),
            "class_minutes": round(focus[d].get("class_seconds", 0) / 60),
            "sessions": focus[d].get("sessions", 0)} for d in days]
    return ToolResult(True, "get_focus_history", message=f"{len(out)} day(s) of focus data",
                      data={"today": today_stats, "days": out})


@tool("get_analytics", "Productivity analytics: estimation accuracy, completion, focus distribution.", {})
def tool_get_analytics(data, args, ctx):
    est = fest.estimation_analytics(data)
    comp = fest.completion_analytics(data)
    dist = get_analytics_data(data)
    return ToolResult(True, "get_analytics", message="Analytics computed",
                      data={"estimation": est, "completion": comp,
                            "subject_time": dist.get("subject_time", {}),
                            "daily_focus": dist.get("daily_focus", {})})


@tool("record_focus_time", "Record actual focus minutes spent on a task (from the timer).",
      {"task_ref": {"type": "str", "required": True, "max": 200},
       "minutes": {"type": "int", "required": True, "min": 1, "max": 1440}},
      permission="write")
def tool_record_focus_time(data, args, ctx):
    t = _find_task_fuzzy(data, args["task_ref"])
    if not t:
        return ToolResult(False, "record_focus_time", error=f"No task matching {args['task_ref']!r}")
    if record_actual_duration(data, t["id"], args["minutes"]):
        return ToolResult(True, "record_focus_time",
                          message=f"Recorded {args['minutes']}min on '{t.get('title')}'",
                          data={"task_id": t["id"]})
    return ToolResult(False, "record_focus_time", error="Invalid minutes")


@tool("generate_report", "A short recommendations report from current state and history.", {})
def tool_generate_report(data, args, ctx):
    est = fest.estimation_analytics(data)
    comp = fest.completion_analytics(data)
    ranked = fsched.explain_priorities(data, settings=ctx.get("settings"), now=ctx.get("now"))
    recs = []
    if ranked:
        top = ranked[0]
        recs.append(f"Start with '{top['title']}' - {top['reason']}")
    if comp.get("done_ratio") is not None and comp["done_ratio"] < 0.5 and comp["tasks_total"] >= 4:
        recs.append("Less than half of your tasks complete - consider moving some to tomorrow "
                    "instead of carrying them all.")
    if est.get("mean_error_ratio") and est["mean_error_ratio"] > 1.25 and est["n"] >= 3:
        recs.append(f"History shows tasks run ~{int((est['mean_error_ratio']-1)*100)}% longer than "
                    "estimated - the planner already pads estimates for you.")
    if est.get("n", 0) < 3:
        recs.append("Complete a few timed tasks so I can learn your real pace "
                    "(needs 3+ tasks with estimates and actuals).")
    streak = data.get("streak", 0)
    if streak >= 2:
        recs.append(f"🔥 {streak}-day activity streak - keep it alive today.")
    return ToolResult(True, "generate_report", message="Report generated",
                      data={"recommendations": recs[:6], "estimation": est, "completion": comp,
                            "top_priorities": ranked[:5]})
