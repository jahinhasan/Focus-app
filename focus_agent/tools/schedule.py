# ==================== TOOLS/SCHEDULE.PY ====================
# Planning/schedule tools: availability, day plans, rescheduling. The planner
# itself is deterministic (scheduler.py / planner.py); these tools only expose
# it with validation and commit confirmations.

from logic import save_data
from focus_agent import dates as fdates
from focus_agent import scheduler as fsched
from focus_agent import memory as fmemory
from focus_agent import planner as fplanner
from focus_agent.repository import ScheduleRepository, TaskRepository, ValidationError
from focus_agent.tools.base import ToolResult, tool


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


# ==================== V2 SCHEDULE TOOLS (Phase 4) ====================

@tool("get_daily_schedule", "The full picture for a date: classes, blocks, committed task slots, free time.",
      {"date": {"type": "date"}})
def tool_get_daily_schedule(data, args, ctx):
    date_str = args.get("date") or fdates.today_str(ctx.get("settings"))
    free, busy, info = fsched.get_availability(data, date_str, ctx.get("settings"))
    blocks = fplanner._blocks_for(data, date_str)
    committed = []
    for t in data.get("tasks", []):
        p = t.get("planned") if isinstance(t, dict) else None
        if p and p.get("date") == date_str:
            committed.append({"task_id": t.get("id"), "title": t.get("title"),
                              "start": p.get("start"), "end": p.get("end"),
                              "reason": p.get("reason")})
    committed.sort(key=lambda c: c.get("start") or "")
    free_fmt = [{"start": fdates.minutes_to_hhmm(iv["start"]),
                 "end": fdates.minutes_to_hhmm(iv["end"]),
                 "minutes": iv["end"] - iv["start"]} for iv in free]
    n = len(committed) + len(blocks) + len(info["classes"])
    return ToolResult(True, "get_daily_schedule",
                      message=f"{date_str}: {len(committed)} planned slot(s), "
                              f"{len(blocks) + len(info['classes'])} fixed item(s), "
                              f"{sum(i['minutes'] for i in free_fmt)}min free",
                      data={"date": date_str, "planned": committed,
                            "classes": info["classes"],
                            "blocks": [{"title": b["title"],
                                        "start": fdates.minutes_to_hhmm(b["start"]),
                                        "end": fdates.minutes_to_hhmm(b["end"]),
                                        "kind": b["kind"]} for b in blocks],
                            "free": free_fmt})


@tool("create_schedule_block", "Claim a fixed time commitment (e.g. 'I have a class 10-12, don't schedule anything'). Recurring via days, or one-off via date.",
      {"title": {"type": "str", "required": True, "max": 200},
       "start": {"type": "hhmm", "required": True},
       "end": {"type": "hhmm", "required": True},
       "days": {"type": "str_list"},
       "date": {"type": "date"},
       "kind": {"type": "str"}},
      permission="write")
def tool_create_schedule_block(data, args, ctx):
    if not args.get("days") and not args.get("date"):
        return ToolResult(False, "create_schedule_block",
                          error="Provide 'days' (e.g. ['fri']) or 'date' (YYYY-MM-DD)")
    kind = args.get("kind") or "commitment"
    if kind not in ("class", "commitment", "busy"):
        kind = "commitment"
    repo = ScheduleRepository(data)
    try:
        block = repo.create(args["title"], args["start"], args["end"],
                            days=args.get("days"), date=args.get("date"),
                            kind=kind)
    except ValidationError as e:
        return ToolResult(False, "create_schedule_block", error=str(e))
    when = f"every {', '.join(block['days'])}" if block.get("days") \
        else f"on {block['date']}"
    # does it collide with anything existing?
    _, conflicts = fplanner.detect_conflicts(
        data, block.get("date") or fdates.today_str(ctx.get("settings")),
        ctx.get("settings"))
    relevant = [c for c in conflicts if args["title"] in (c["a"] + c["b"])]
    msg = (f"Blocked {args['start']}-{args['end']} {when} for '{args['title']}' - "
           "the planner will never schedule over it.")
    if relevant:
        msg += f" ⚠ It overlaps: {relevant[0]['a']} vs {relevant[0]['b']} at {relevant[0]['overlap']}"
    return ToolResult(True, "create_schedule_block", message=msg,
                      data={"block_id": block["id"], "conflicts": relevant})


@tool("update_schedule_block", "Move or edit a fixed time block.",
      {"block_ref": {"type": "str", "required": True, "max": 200},
       "start": {"type": "hhmm"}, "end": {"type": "hhmm"},
       "title": {"type": "str", "max": 200},
       "date": {"type": "date"}},
      permission="write")
def tool_update_schedule_block(data, args, ctx):
    repo = ScheduleRepository(data)
    blocks = repo.list()
    frag = args["block_ref"].lower()
    block = next((b for b in blocks if b.get("id") == args["block_ref"]
                  or frag in (b.get("title") or "").lower()), None)
    if not block:
        return ToolResult(False, "update_schedule_block",
                          error=f"No schedule block matching {args['block_ref']!r}")
    fields = {k: v for k, v in (("start", args.get("start")),
                                ("end", args.get("end")),
                                ("title", args.get("title")),
                                ("date", args.get("date"))) if v is not None}
    if not fields:
        return ToolResult(False, "update_schedule_block", error="Nothing to update")
    try:
        updated = repo.update(block["id"], **fields)
    except ValidationError as e:
        return ToolResult(False, "update_schedule_block", error=str(e))
    return ToolResult(True, "update_schedule_block",
                      message=(f"Updated block '{updated['title']}' "
                               f"({updated['start']}-{updated['end']})"),
                      data={"block_id": updated["id"], "updated": fields})


@tool("delete_schedule_block", "Remove a fixed time block (frees the time for planning again).",
      {"block_ref": {"type": "str", "required": True, "max": 200}},
      permission="destructive", requires_confirmation=True)
def tool_delete_schedule_block(data, args, ctx):
    repo = ScheduleRepository(data)
    blocks = repo.list()
    frag = args["block_ref"].lower()
    block = next((b for b in blocks if b.get("id") == args["block_ref"]
                  or frag in (b.get("title") or "").lower()), None)
    if not block:
        return ToolResult(False, "delete_schedule_block",
                          error=f"No schedule block matching {args['block_ref']!r}")
    repo.delete(block["id"])
    return ToolResult(True, "delete_schedule_block",
                      message=f"Removed block '{block['title']}'",
                      data={"block_id": block["id"]})


@tool("reschedule_task", "Move ONE task to a specific date (optionally a time), validating conflicts, then propose a replan of the affected day.",
      {"task_ref": {"type": "str", "required": True, "max": 200},
       "to_date": {"type": "date", "required": True},
       "to_time": {"type": "hhmm"},
       "commit_plan": {"type": "bool", "default": False}},
      permission="write")
def tool_reschedule_task(data, args, ctx):
    repo = TaskRepository(data)
    t = repo.find_fuzzy(args["task_ref"])
    if not t:
        return ToolResult(False, "reschedule_task", error=f"No task matching {args['task_ref']!r}")
    if t.get("type") == "class":
        return ToolResult(False, "reschedule_task",
                          error="'{0}' is a recurring class - edit the routine instead "
                                "(classes are never moved silently).".format(t.get("title")))
    to_time = args.get("to_time")
    if to_time:
        # target slot must be free: classes, blocks, other committed slots
        _, conflicts = fplanner.detect_conflicts(data, args["to_date"], ctx.get("settings"))
        s = fdates.hhmm_to_minutes(to_time)
        est = t.get("duration") or 60
        e = s + int(est)
        colliding = []
        items, _ = fplanner.detect_conflicts(data, args["to_date"], ctx.get("settings"))
        for it in items:
            if it["start"] < e and s < it["end"]:
                colliding.append(f"{it['title']} "
                                 f"{fdates.minutes_to_hhmm(it['start'])}-"
                                 f"{fdates.minutes_to_hhmm(it['end'])}")
        if colliding:
            return ToolResult(False, "reschedule_task",
                              error=(f"{to_time} on {args['to_date']} collides with: "
                                     + ", ".join(colliding[:4]) +
                                     " - pick another time or omit to_time"))
    old_date = t.get("date")
    repo.update(t["id"], due_date=args["to_date"])
    repo.add_reschedule_entry(t["id"], {"from": old_date, "to": args["to_date"],
                                        "source": "reschedule_task"})
    if to_time:
        t2 = repo.get(t["id"])
        t2["planned"] = {"date": args["to_date"], "start": to_time,
                         "end": fdates.minutes_to_hhmm(
                             fdates.hhmm_to_minutes(to_time) + int(t2.get("duration") or 60)),
                         "reason": "user-requested slot"}
        save_data(data)
    msg = (f"Moved '{t.get('title')}' from {old_date or 'no date'} to {args['to_date']}"
           + (f" at {to_time}" if to_time else ""))
    # propose a replan of the target day (not committed unless asked)
    plan = fsched.reschedule_after_change(data, args["to_date"],
                                          settings=ctx.get("settings"), now=ctx.get("now"))
    plan_dict = None
    if plan.slots:
        if args.get("commit_plan"):
            fsched.apply_plan(data, plan)
            fmemory.log_plan(data, plan.to_dict())
            msg += f"; replanned {args['to_date']} ({len(plan.slots)} slot(s), committed)"
        else:
            plan_dict = plan.to_dict()
            msg += (f"; proposed {len(plan.slots)} slot(s) for {args['to_date']} - "
                    "review and apply to commit")
    return ToolResult(True, "reschedule_task", message=msg,
                      data={"task_id": t["id"], "from": old_date, "to": args["to_date"],
                            "plan": plan_dict})


@tool("detect_schedule_conflicts", "Find overlapping classes, blocks and committed slots for a date.",
      {"date": {"type": "date"}})
def tool_detect_schedule_conflicts(data, args, ctx):
    date_str = args.get("date") or fdates.today_str(ctx.get("settings"))
    items, conflicts = fplanner.detect_conflicts(data, date_str, ctx.get("settings"))
    if not conflicts:
        return ToolResult(True, "detect_schedule_conflicts",
                          message=f"No conflicts on {date_str} "
                                  f"({len(items)} fixed/planned items checked)",
                          data={"date": date_str, "conflicts": [],
                                "items_checked": len(items)})
    fmt = [f"{c['a']} ↔ {c['b']} at {c['overlap']}" for c in conflicts]
    return ToolResult(True, "detect_schedule_conflicts",
                      message=f"{len(conflicts)} conflict(s) on {date_str}: " + "; ".join(fmt[:4]),
                      data={"date": date_str, "conflicts": conflicts})
