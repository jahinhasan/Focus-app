# ==================== TOOLS/ANALYTICS.PY ====================
# Productivity/analytics tools: focus history, statistics, reports. Reads are
# computed from real records only - numbers are never invented.

from logic import (
    get_today_focus_stats, get_analytics_data, record_actual_duration,
)
from focus_agent import estimator as fest
from focus_agent import scheduler as fsched
from focus_agent.tools.base import ToolResult, tool, find_task_fuzzy


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
    t = find_task_fuzzy(data, args["task_ref"])
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


@tool("estimate_task_duration", "Learned duration estimate for a task (or a free description with minutes), with the basis disclosed.",
      {"task_ref": {"type": "str", "max": 200},
       "minutes": {"type": "int", "min": 5, "max": 960}})
def tool_estimate_task_duration(data, args, ctx):
    t = find_task_fuzzy(data, args["task_ref"]) if args.get("task_ref") else None
    if t is None and not args.get("minutes"):
        return ToolResult(False, "estimate_task_duration",
                          error="Provide 'task_ref' (existing task) or 'minutes' (rough estimate)")
    task = dict(t or {})
    if task.get("duration") is None and args.get("minutes"):
        task["duration"] = args["minutes"]
        task.setdefault("subject", None)
        task.setdefault("difficulty", 2)
    if t is not None:
        task["created_at"] = t.get("created_at")
    info = fest.estimate_minutes(data, task, ctx.get("settings"))
    label = f"'{t.get('title')}'" if t else "the described work"
    reliability = "learned" if info.get("reliable") else "default (not enough history)"
    return ToolResult(True, "estimate_task_duration",
                      message=(f"Estimated {info['minutes']}min for {label} - {reliability}. "
                               f"Basis: {info['basis']}"),
                      data={"minutes": info["minutes"], "basis": info["basis"],
                            "samples": info["samples"], "reliable": info["reliable"]})
