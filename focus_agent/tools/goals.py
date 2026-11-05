# ==================== TOOLS/GOALS.PY ====================
# Goal tools: CRUD, milestones, explicit roadmap decomposition, progress with
# pace analysis. Roadmaps are persisted only through decompose_goal (explicit).

from datetime import date as _date, timedelta

from logic import add_xp
from focus_agent import goals as fgoals
from focus_agent.tools.base import ToolResult, tool, find_task_fuzzy


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


@tool("decompose_goal", "Split a goal into ordered milestones spread evenly between now and the goal's target date (explicitly persisted roadmap).",
      {"goal_ref": {"type": "str", "required": True, "max": 200},
       "milestones": {"type": "str_list", "required": True}},
      permission="write")
def tool_decompose_goal(data, args, ctx):
    g = fgoals.find_goal_by_title(data, args["goal_ref"])
    if not g:
        return ToolResult(False, "decompose_goal", error=f"No goal matching {args['goal_ref']!r}")
    titles = [t for t in (args.get("milestones") or [])[:12] if (t or "").strip()]
    if not titles:
        return ToolResult(False, "decompose_goal", error="milestones must be a non-empty list")
    existing = {(m.get("title") or "").lower() for m in g.get("milestones", [])}
    try:
        target = _date.fromisoformat(g.get("target_date")) if g.get("target_date") else None
    except (ValueError, TypeError):
        target = None
    today = _date.today()
    added, dates = [], []
    n = len(titles)
    for i, title in enumerate(titles):
        if title.lower() in existing:
            continue
        ms_target = None
        if target and target > today:
            # even spread: milestone i of n gets (i+1)/n of the remaining span
            span = (target - today).days
            ms_target = (today + timedelta(days=round(span * (i + 1) / n))).isoformat()
        ms, err = fgoals.add_milestone(data, g["id"], title, ms_target, None)
        if err:
            continue
        added.append(ms["title"])
        dates.append(ms_target or "no date")
    if not added:
        return ToolResult(True, "decompose_goal",
                          message=f"Goal '{g['title']}' already covers those milestones.",
                          data={"goal_id": g["id"], "added": []})
    lines = "\n".join(f"• {t} → by {d}" for t, d in zip(added, dates))
    return ToolResult(True, "decompose_goal",
                      message=(f"Roadmap for '{g['title']}' ({len(added)} milestone(s)):\n{lines}\n"
                               "Edit in the Goals tab - assumptions, not promises."),
                      data={"goal_id": g["id"], "added": added, "dates": dates})


@tool("track_goal_progress", "Goal progress: milestone completion, linked task completion, pace vs target date.",
      {"goal_ref": {"type": "str", "required": True, "max": 200}})
def tool_track_goal_progress(data, args, ctx):
    g = fgoals.find_goal_by_title(data, args["goal_ref"])
    if not g:
        return ToolResult(False, "track_goal_progress", error=f"No goal matching {args['goal_ref']!r}")
    milestones = g.get("milestones", [])
    ms_done = sum(1 for m in milestones if m.get("done"))
    linked = [t for t in data.get("tasks", []) if t.get("goal_id") == g["id"]
              and t.get("type") == "task"]
    t_done = sum(1 for t in linked if t.get("status") == "done")
    progress = {"milestones_done": ms_done, "milestones_total": len(milestones),
                "linked_tasks_done": t_done, "linked_tasks_total": len(linked)}
    pace = {}
    if g.get("target_date"):
        try:
            target = _date.fromisoformat(g["target_date"])
            days_left = (target - _date.today()).days
            overall = (ms_done + t_done)
            total = len(milestones) + len(linked)
            frac_done = (overall / total) if total else 0.0
            pace = {"days_left": days_left,
                    "percent_complete": round(frac_done * 100),
                    "on_track": None}
            if days_left < 0:
                pace["on_track"] = False
                pace["note"] = "target date has passed"
            elif total:
                # a goal should be ~half done when half the time is gone
                span_total = max(1, (target - _date.fromisoformat(
                    g.get("created_at") or (target - timedelta(days=60)).isoformat())).days)
                elapsed_frac = 1 - (days_left / max(1, span_total))
                pace["on_track"] = frac_done >= elapsed_frac - 0.15
                pace["note"] = (f"{round(frac_done*100)}% done vs ~{round(elapsed_frac*100)}%"
                                " of the time used")
        except (ValueError, TypeError):
            pace = {}
    done_flags = "on track" if pace.get("on_track") is True else \
                 ("behind" if pace.get("on_track") is False else "no target date")
    return ToolResult(True, "track_goal_progress",
                      message=(f"'{g['title']}': {ms_done}/{len(milestones)} milestones, "
                               f"{t_done}/{len(linked)} linked tasks - {done_flags}"),
                      data={"goal_id": g["id"], "progress": progress, "pace": pace})


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
