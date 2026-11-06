# ==================== TOOLS/TASKS.PY ====================
# Task tools: CRUD + search + decomposition. All writes go through the task
# repository/logic layer; the subject matcher enforces ask-don't-guess.

from logic import (
    add_task_logic, delete_task_logic, update_task_logic, complete_task_logic,
    reopen_task_logic, record_actual_duration, get_task_by_id, add_subtask,
)
from focus_agent import subjects as fsubjects
from focus_agent import goals as fgoals
from focus_agent.repository import TaskRepository
from focus_agent.tools.base import (
    ToolResult, clean_str, tool, find_task_fuzzy, match_or_none,
)


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


@tool("search_tasks", "Ranked text search across task titles, notes and subjects, with match scores.",
      {"query": {"type": "str", "required": True, "max": 200},
       "limit": {"type": "int", "min": 1, "max": 25, "default": 10}})
def tool_search_tasks(data, args, ctx):
    repo = TaskRepository(data)
    hits = repo.search(args["query"], limit=args.get("limit", 10))
    out = [{"id": h["task"].get("id"), "title": h["task"].get("title"),
            "score": h["score"], "status": h["task"].get("status"),
            "due_date": h["task"].get("date"), "subject": h["task"].get("subject")}
           for h in hits]
    return ToolResult(True, "search_tasks",
                      message=f"{len(out)} match(es) for {args['query']!r}",
                      data={"query": args["query"], "results": out})


@tool("get_task", "Inspect one task's full details by id or title fragment.",
      {"task_ref": {"type": "str", "required": True, "max": 200}})
def tool_get_task(data, args, ctx):
    t = find_task_fuzzy(data, args["task_ref"])
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
    subject_assigned, match_info = match_or_none(data, args.get("subject"))
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
    if args.get("due_time"):
        due_txt += f" at {args['due_time']}"
    dur_txt = f", ~{args['duration_minutes']}min" if args.get("duration_minutes") else ""
    msg = f"Created task '{title}'{due_txt}{dur_txt}"
    if subject_assigned:
        msg += f" [subject: {subject_assigned}]"
    payload = {"task_id": task["id"], "title": title,
               "subject": subject_assigned, "due_date": args.get("due_date"),
               "due_time": args.get("due_time")}
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
    t = find_task_fuzzy(data, args["task_ref"])
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
        subject_assigned, match_info = match_or_none(data, args["subject"])
        if subject_assigned:
            updates["subject"] = subject_assigned
    if not updates:
        return ToolResult(False, "update_task", error="Nothing to update")
    # a date change is a reschedule: record it in the task's move history (v4)
    if "date" in updates and updates["date"] != t.get("date"):
        repo = TaskRepository(data)
        repo.add_reschedule_entry(t["id"], {
            "from": t.get("date"), "to": updates["date"],
            "source": args.get("source", "agent"),
        })
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
    t = find_task_fuzzy(data, args["task_ref"])
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
    t = find_task_fuzzy(data, args["task_ref"])
    if not t:
        return ToolResult(False, "reopen_task", error=f"No task matching {args['task_ref']!r}")
    if reopen_task_logic(data, t["id"]):
        return ToolResult(True, "reopen_task", message=f"Reopened '{t.get('title')}'")
    return ToolResult(False, "reopen_task", error="Task cannot be reopened")


@tool("delete_task", "Delete a task permanently.", {"task_ref": {"type": "str", "required": True, "max": 200}},
      permission="destructive", requires_confirmation=True)
def tool_delete_task(data, args, ctx):
    t = find_task_fuzzy(data, args["task_ref"])
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
    t = find_task_fuzzy(data, args["task_ref"])
    if not t:
        return ToolResult(False, "add_subtask", error=f"No task matching {args['task_ref']!r}")
    add_subtask(data, t["id"], args["title"])
    return ToolResult(True, "add_subtask",
                      message=f"Added subtask '{args['title']}' to '{t.get('title')}'",
                      data={"task_id": t["id"]})


@tool("decompose_task", "Split a task into ordered subtasks (duplicates of existing subtasks are skipped).",
      {"task_ref": {"type": "str", "required": True, "max": 200},
       "subtasks": {"type": "str_list", "required": True}},
      permission="write")
def tool_decompose_task(data, args, ctx):
    t = find_task_fuzzy(data, args["task_ref"])
    if not t:
        return ToolResult(False, "decompose_task", error=f"No task matching {args['task_ref']!r}")
    existing = {(s.get("title") or "").lower() for s in t.get("subtasks", [])}
    added = []
    for raw in (args.get("subtasks") or [])[:15]:
        title = clean_str(raw, 200)
        if not title or title.lower() in existing:
            continue
        add_subtask(data, t["id"], title)
        existing.add(title.lower())
        added.append(title)
    if not added:
        return ToolResult(True, "decompose_task",
                          message=f"'{t.get('title')}' already covers those steps.",
                          data={"task_id": t["id"], "added": []})
    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(added))
    return ToolResult(True, "decompose_task",
                      message=f"Decomposed '{t.get('title')}' into {len(added)} step(s):\n{numbered}",
                      data={"task_id": t["id"], "added": added})
