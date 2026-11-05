# ==================== PATTERNS.PY ====================
# Learning views computed from persistent records (Phase 5). Transparent
# statistics only: every result carries sample counts and a `reliable` flag so
# the planner and the UI can disclose "learned" vs "not enough data".
#
# Sources (all additive, schema v4):
# - hourly_focus: date -> {hour: focus minutes}   (timer / focus tools)
# - focus_session_log: per-session records
# - plan_log + task['planned']: schedule adherence
# - tasks/archived_tasks: completion rates by subject

from __future__ import annotations

from collections import defaultdict
from datetime import date as _d

from focus_agent import dates as fdates

MIN_MINUTES_FOR_HOURS = 45      # total minutes needed before hours are "learned"
MIN_SESSIONS_FOR_ADHERENCE = 3  # committed plans needed before adherence is used
RELIABLE_N = 3                  # generic sample floor


def productive_hours(data, top=None):
    """Hour-of-day focus profile from hourly_focus buckets.

    Returns {"hours": {hour_str: normalized_score}, "total_minutes": n,
             "reliable": bool, "basis": str}. Score 0..1 relative to the best
    hour; hours with no data score 0. Reliable only with enough total focus.
    """
    buckets = data.get("hourly_focus", {}) or {}
    totals = defaultdict(float)
    total = 0.0
    for _day, hours in buckets.items():
        if not isinstance(hours, dict):
            continue
        for hour, minutes in hours.items():
            try:
                m = float(minutes)
            except (TypeError, ValueError):
                continue
            if hour == "99":       # unattributed (no start time known)
                continue
            totals[hour] += m
            total += m
    reliable = total >= MIN_MINUTES_FOR_HOURS
    scores = {}
    if reliable and totals:
        best = max(totals.values())
        for hour in sorted(totals):
            scores[hour] = round(totals[hour] / best, 2)
    out = {"hours": scores, "total_minutes": round(total),
           "reliable": reliable,
           "basis": (f"learned from {round(total)}min of timed focus across "
                     f"{len(buckets)} day(s)"
                     if reliable else
                     f"only {round(total)}min of timed focus - using neutral "
                     "placement (need 45min+ across logged sessions)")}
    if top and reliable:
        out["best_hours"] = sorted(scores, key=scores.get, reverse=True)[:top]
    return out


def weekday_effects(data):
    """Average focus minutes per weekday from day aggregates.

    Returns {"by_weekday": {mon..sun: minutes}, "days": n, "reliable": bool,
    "basis": str}."""
    focus = data.get("focus_sessions", {}) or {}
    per_day = {}
    for day, rec in focus.items():
        try:
            wd = fdates.weekday_key(_d.fromisoformat(day))
        except (ValueError, TypeError):
            continue
        per_day[day] = (wd, round((rec.get("total_seconds") or 0) / 60))
    if not per_day:
        return {"by_weekday": {}, "days": 0, "reliable": False,
                "basis": "no focus history yet"}
    sums = defaultdict(list)
    for _day, (wd, minutes) in per_day.items():
        sums[wd].append(minutes)
    by_weekday = {wd: round(sum(v) / len(v)) for wd, v in sorted(sums.items())}
    return {"by_weekday": by_weekday, "days": len(per_day),
            "reliable": len(per_day) >= RELIABLE_N,
            "basis": f"average over {len(per_day)} recorded day(s)"}


def subject_completion_rates(data):
    """Done vs total per subject over tasks + archive."""
    counts = defaultdict(lambda: {"done": 0, "total": 0})
    for t in list(data.get("tasks", [])) + list(data.get("archived_tasks", [])):
        if not isinstance(t, dict) or t.get("type") != "task":
            continue
        subj = t.get("subject") or "Unassigned"
        counts[subj]["total"] += 1
        if t.get("status") == "done":
            counts[subj]["done"] += 1
    out = {}
    for subj, c in sorted(counts.items()):
        rate = round(c["done"] / c["total"], 2) if c["total"] else None
        out[subj] = {"done": c["done"], "total": c["total"], "rate": rate,
                     "reliable": c["total"] >= RELIABLE_N}
    return out


def schedule_adherence(data, today=None):
    """How well committed plans were followed.

    For past dates with a committed plan (plan_log), a slot counts as honored
    when its task is done or its planned slot was kept. Returns ratio +
    sample count; unreliable below MIN_SESSIONS_FOR_ADHERENCE plans.
    """
    today = today or fdates.now_here({}).date()
    from focus_agent.repository import TaskRepository
    repo = TaskRepository(data)
    plan_log = (data.get("agent_memory", {}) or {}).get("plan_log", []) or []
    checked_dates = []
    for entry in plan_log:
        p = entry.get("plan") or {}
        if p.get("date") and p.get("committed"):
            try:
                if _d.fromisoformat(p["date"]) < today:
                    checked_dates.append(p["date"])
            except (ValueError, TypeError):
                continue
    checked_dates = sorted(set(checked_dates))
    total_slots = honored = 0
    for date_str in checked_dates:
        for t in data.get("tasks", []):
            p = t.get("planned") if isinstance(t, dict) else None
            if not p or p.get("date") != date_str:
                continue
            total_slots += 1
            if t.get("status") == "done":
                honored += 1
    ratio = round(honored / total_slots, 2) if total_slots else None
    reliable = len(checked_dates) >= MIN_SESSIONS_FOR_ADHERENCE and total_slots > 0
    return {"dates_checked": len(checked_dates), "slots_total": total_slots,
            "slots_honored": honored, "ratio": ratio, "reliable": reliable,
            "basis": (f"{honored}/{total_slots} planned slots honored across "
                      f"{len(checked_dates)} committed past day(s)"
                      if total_slots else "no committed past plans yet")}


def missed_tasks(data, now=None):
    """Open tasks whose deadline has passed (carry-over candidates)."""
    now = now or fdates.now_here({})
    today = now.date().isoformat()
    out = []
    for t in data.get("tasks", []):
        if not isinstance(t, dict) or t.get("type") != "task":
            continue
        if t.get("status") in ("done", "archived", "missed"):
            continue
        due = t.get("date")
        if due and due < today:
            hist = t.get("reschedule_history") or []
            out.append({"task_id": t.get("id"), "title": t.get("title"),
                        "due": due, "days_overdue": (now.date() - _d.fromisoformat(due)).days,
                        "moved_before": len(hist)})
    out.sort(key=lambda x: x["due"])
    return out


def pattern_summary(data, now=None):
    """Composite view for the analytics tool and the planner."""
    hours = productive_hours(data)
    return {
        "productive_hours": hours,
        "weekday_effects": weekday_effects(data),
        "subject_completion": subject_completion_rates(data),
        "adherence": schedule_adherence(data),
        "missed_tasks": missed_tasks(data, now=now),
    }


__all__ = ["productive_hours", "weekday_effects", "subject_completion_rates",
           "schedule_adherence", "missed_tasks", "pattern_summary"]
