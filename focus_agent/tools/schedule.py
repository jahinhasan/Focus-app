# ==================== TOOLS/SCHEDULE.PY ====================
# Planning/schedule tools: availability, day plans, rescheduling. The planner
# itself is deterministic (scheduler.py / planner.py); these tools only expose
# it with validation and commit confirmations.

from logic import save_data
from focus_agent import dates as fdates
from focus_agent import scheduler as fsched
from focus_agent import memory as fmemory
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
