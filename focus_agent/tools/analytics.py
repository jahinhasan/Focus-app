# ==================== TOOLS/ANALYTICS.PY ====================
# Productivity/analytics tools: focus history, statistics, reports. Reads are
# computed from real records only - numbers are never invented.

from logic import (
    get_today_focus_stats, get_analytics_data, record_actual_duration,
)
from focus_agent import dates as fdates
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
        try:
            now = ctx.get("now")
            from focus_agent.repository import FocusRepository
            started = now.strftime("%H:%M") if now is not None else None
            date_str = now.date().isoformat() if now is not None else \
                fdates.today_str(ctx.get("settings"))
            FocusRepository(data).log_session(date_str, args["minutes"],
                                              kind="focus", task_id=t.get("id"),
                                              started_hhmm=started)
        except Exception:
            pass  # learning feed must not break recording
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


# ==================== V2 ANALYTICS TOOLS (Phase 5) ====================

@tool("get_task_completion_history", "Completed and missed tasks over a window, with rates by subject.",
      {"days": {"type": "int", "min": 1, "max": 365, "default": 30}})
def tool_get_task_completion_history(data, args, ctx):
    from focus_agent import patterns as fpatterns
    days = args.get("days", 30)
    now = ctx.get("now")
    cutoff = ""
    if now is not None:
        from datetime import timedelta
        cutoff = (now.date() - timedelta(days=days)).isoformat()
    completed, missed = [], []
    for t in list(data.get("tasks", [])) + list(data.get("archived_tasks", [])):
        if not isinstance(t, dict) or t.get("type") != "task":
            continue
        if t.get("status") == "done":
            done_at = (t.get("completed_at") or "")[:10]
            if cutoff and done_at and done_at < cutoff:
                continue
            completed.append({"title": t.get("title"), "subject": t.get("subject"),
                              "completed_on": done_at or None,
                              "est_minutes": t.get("duration"),
                              "actual_minutes": t.get("actual_minutes")})
        elif t.get("date") and cutoff and t["date"] < cutoff \
                and t.get("status") not in ("done", "archived"):
            missed.append({"title": t.get("title"), "subject": t.get("subject"),
                           "due": t["date"]})
    rates = fpatterns.subject_completion_rates(data)
    total_done = len(completed)
    return ToolResult(True, "get_task_completion_history",
                      message=(f"{total_done} completed, {len(missed)} overdue-"
                               f"un-done in the last {days} day(s)"),
                      data={"days": days, "completed": completed[:40],
                            "overdue_undone": missed[:40],
                            "subject_rates": rates})


@tool("compare_estimated_actual_duration", "Estimated vs actual duration for completed tasks (overall and per subject), with mean error ratio.",
      {"subject": {"type": "str", "max": 120}})
def tool_compare_estimated_actual_duration(data, args, ctx):
    est = fest.estimation_analytics(data)
    subject = args.get("subject")
    rows = []
    for t in list(data.get("tasks", [])) + list(data.get("archived_tasks", [])):
        if not isinstance(t, dict) or t.get("status") != "done":
            continue
        e, a = t.get("duration"), t.get("actual_minutes")
        if not isinstance(e, (int, float)) or not isinstance(a, (int, float)) or e <= 0:
            continue
        if subject and (t.get("subject") or "").lower() != subject.lower():
            continue
        rows.append({"title": t.get("title"), "subject": t.get("subject"),
                     "estimated_minutes": int(e), "actual_minutes": int(a),
                     "difference_minutes": int(a - e)})
    if subject and est.get("by_subject"):
        key = next((k for k in est["by_subject"] if k.lower() == subject.lower()), None)
        scoped = est["by_subject"].get(key) if key else None
        summary = scoped or {"n": 0, "mae_minutes": None}
    else:
        summary = {"n": est.get("n", 0), "mae_minutes": est.get("mae_minutes"),
                   "mean_error_ratio": est.get("mean_error_ratio"),
                   "on_time_rate": est.get("on_time_rate")}
    if not rows:
        return ToolResult(True, "compare_estimated_actual_duration",
                          message="No completed tasks with both an estimate and an "
                                  "actual time yet - complete timed tasks to build this.",
                          data={"rows": [], "summary": summary})
    return ToolResult(True, "compare_estimated_actual_duration",
                      message=(f"{len(rows)} completed task(s) compared; mean error "
                               f"ratio {summary.get('mean_error_ratio', 'n/a')}"),
                      data={"rows": rows[:40], "summary": summary})


@tool("analyze_productivity_patterns", "Learned patterns: productive hours, weekday effects, schedule adherence, missed-task carry-overs. Discloses when data is insufficient.",
      {})
def tool_analyze_productivity_patterns(data, args, ctx):
    from focus_agent import patterns as fpatterns
    summary = fpatterns.pattern_summary(data, now=ctx.get("now"))
    hours = summary["productive_hours"]
    best = hours.get("hours")
    msg_parts = []
    if hours.get("reliable") and best:
        top = sorted(best, key=best.get, reverse=True)[:3]
        msg_parts.append(f"Most productive around "
                         f"{', '.join(h + ':00' for h in top)} "
                         f"({hours['basis']})")
    else:
        msg_parts.append(f"Productive hours: not enough data yet ({hours['basis']})")
    adh = summary["adherence"]
    if adh.get("reliable"):
        msg_parts.append(f"Plan adherence {adh['ratio']:.0%} ({adh['basis']})")
    else:
        msg_parts.append(f"Plan adherence: not enough committed plans yet "
                         f"({adh['basis']})")
    missed = summary["missed_tasks"]
    if missed:
        titles = ", ".join(m["title"] for m in missed[:3])
        msg_parts.append(f"{len(missed)} task(s) past due: {titles}")
    return ToolResult(True, "analyze_productivity_patterns",
                      message=" | ".join(msg_parts),
                      data=summary)
