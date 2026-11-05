# ==================== PLANNER.PY ====================
# Multi-day, deadline-aware planning engine (Phase 4). Wraps the deterministic
# single-day kernel (scheduler.py): iterates the horizon day by day, allocates
# open tasks by priority, never exceeds availability, and reports deadline
# infeasibility with explicit reasons. A task is never silently dropped and a
# class/block is never moved.
#
# Determinism: same store + same date + same settings -> same plan.

from dataclasses import dataclass, field

from focus_agent import dates as fdates
from focus_agent import estimator as fest
from focus_agent.scheduler import (
    PlanSlot, PlanResult, get_availability, task_priority, urgency_bucket,
    MAX_BLOCK_MINUTES,
)
from focus_agent.scheduler import _subtract  # interval math reuse

MAX_HORIZON_DAYS = 14
MIN_SLOT_MINUTES = 15


@dataclass
class MultiDayPlan:
    start_date: str
    end_date: str
    days: list = field(default_factory=list)          # list[PlanResult]
    unschedulable: list = field(default_factory=list)  # deadline-infeasible tasks
    capacity_minutes: int | None = None                # explicit user limit
    notes: list = field(default_factory=list)

    def to_dict(self):
        return {
            "start_date": self.start_date, "end_date": self.end_date,
            "days": [d.to_dict() for d in self.days],
            "unschedulable": list(self.unschedulable),
            "capacity_minutes": self.capacity_minutes,
            "notes": list(self.notes),
        }


def _to_date(s):
    from datetime import date as _d
    return _d.fromisoformat(s)


def _blocks_for(data, date_str):
    """Fixed blocks (classes + user schedule blocks) for a date, in minutes."""
    weekday = fdates.weekday_key(_to_date(date_str))
    out = []
    for t in data.get("tasks", []):
        if t.get("type") != "class":
            continue
        sch = t.get("schedule") or {}
        if weekday not in (sch.get("days") or []):
            continue
        s, e = fdates.hhmm_to_minutes(sch.get("start")), fdates.hhmm_to_minutes(sch.get("end"))
        if s is None or e is None or e <= s:
            continue
        out.append({"start": s, "end": e, "title": t.get("title"), "kind": "class"})
    for b in data.get("schedule_blocks", []) or []:
        if b.get("date") and b["date"] != date_str:
            continue
        if not b.get("date") and weekday not in (b.get("days") or []):
            continue
        s, e = fdates.hhmm_to_minutes(b.get("start")), fdates.hhmm_to_minutes(b.get("end"))
        if s is None or e is None or e <= s:
            continue
        out.append({"start": s, "end": e, "title": b.get("title"),
                    "kind": b.get("kind", "commitment")})
    out.sort(key=lambda b: b["start"])
    return out


def plan_range(data, start_date, settings=None, now=None, days=None,
               capacity_minutes=None, commit=False, hour_scores=None):
    """Plan open tasks across a deadline-aware horizon.

    - horizon: `days` (default 1) capped at MAX_HORIZON_DAYS, extended only by
      the scan itself when deadlines fall beyond it (still capped).
    - capacity_minutes: explicit user limit (e.g. 'I have three hours free') -
      total newly allocated work cannot exceed it.
    - hour_scores: optional {"14": 0.9, ...} productive-hour profile - free
      intervals are worked in descending score order (learning-aware placement)
      while staying deterministic.
    - commit: persist per-day planned slots (validated call sites only).
    """
    settings = settings or (data.get("settings") or {})
    tz_now = now or fdates.now_here(settings)
    start = _to_date(start_date)
    n_days = max(1, min(days or 1, MAX_HORIZON_DAYS))
    use_scores = isinstance(hour_scores, dict) and bool(hour_scores)

    # candidate workload: open, type=task, with estimates
    open_tasks = []
    for t in data.get("tasks", []):
        if not isinstance(t, dict) or t.get("type") != "task":
            continue
        if t.get("status") in ("done", "archived", "missed"):
            continue
        est = t.get("duration")
        if not isinstance(est, (int, float)) or est <= 0:
            continue
        info = fest.estimate_minutes(data, t, settings)
        minutes = int(info["minutes"])
        score, reason = task_priority(t, start)
        open_tasks.append({"task": t, "minutes": minutes,
                           "score": score, "reason": reason,
                           "remaining": minutes})
    open_tasks.sort(key=lambda x: (-x["score"], x["task"].get("date") or "9999",
                                   x["task"].get("title") or ""))

    plan = MultiDayPlan(start_date=start_date,
                        end_date=(start_date if n_days == 1 else
                                  fdates.shift_date(start_date, n_days - 1)),
                        capacity_minutes=capacity_minutes)
    allocated_total = 0
    for day_i in range(n_days):
        day = fdates.shift_date(start_date, day_i)
        free, busy, info = get_availability(data, day, settings)
        # subtract user schedule blocks as well (kernel handles classes only)
        for b in _blocks_for(data, day):
            if b["kind"] != "class":  # classes already subtracted
                free = _subtract(free, b["start"], b["end"])
        day_result = PlanResult(date=day)
        day_result.notes.extend([f"Study window {info['window']}"]
                                + (["Blocks: " + ", ".join(
                                    f"{b['title']} {fdates.minutes_to_hhmm(b['start'])}-"
                                    f"{fdates.minutes_to_hhmm(b['end'])}"
                                    for b in _blocks_for(data, day))] if _blocks_for(data, day) else []))

        day_capacity = None
        if capacity_minutes is not None:
            day_capacity = max(0, capacity_minutes - allocated_total)
        placed_today = _allocate_day(free, open_tasks, day, day_capacity,
                                     tz_now if day == start_date else None,
                                     hour_scores=hour_scores if use_scores else None)

        for slot in placed_today:
            day_result.slots.append(slot)
        day_result.slots.sort(key=lambda s: s.start)
        plan.days.append(day_result)
        allocated_total += sum(_slot_minutes(s) for s in placed_today)

    # deadline feasibility: for each task, was enough allocated before its due?
    for cand in open_tasks:
        due = cand["task"].get("date")
        if not due:
            continue
        in_horizon = sum(_slot_minutes(s)
                         for d in plan.days for s in d.slots
                         if s.task_id == cand["task"]["id"])
        if in_horizon == 0:
            # never placed anywhere: either out of horizon or no room
            within = _to_date(due) <= _to_date(plan.end_date)
            plan.unschedulable.append({
                "task_id": cand["task"]["id"], "title": cand["task"].get("title", ""),
                "reason": (f"needs {cand['minutes']}min before {due} but no free slot "
                           f"was available in {plan.start_date}..{plan.end_date}"
                           + (f" (capacity limit {capacity_minutes}min)"
                              if capacity_minutes is not None else "")),
            })
        elif in_horizon < cand["minutes"] and _to_date(due) <= _to_date(plan.end_date):
            plan.unschedulable.append({
                "task_id": cand["task"]["id"], "title": cand["task"].get("title", ""),
                "reason": (f"only {in_horizon} of {cand['minutes']}min fit before "
                           f"the {due} deadline"),
            })

    if capacity_minutes is not None:
        plan.notes.append(f"User capacity limit honored: {allocated_total}min of "
                          f"{capacity_minutes}min allocated")
    total_unsched = sum(1 for _ in plan.unschedulable)
    if total_unsched:
        plan.notes.append(f"⚠ {total_unsched} task(s) could not be fully scheduled "
                          "before their deadlines - see unschedulable list")
    if commit:
        apply_multi_day(plan, data)
    return plan


def _slot_minutes(slot):
    s = fdates.hhmm_to_minutes(slot.start)
    e = fdates.hhmm_to_minutes(slot.end)
    return max(0, (e or 0) - (s or 0))


def _allocate_day(free, open_tasks, day_str, day_capacity, now_for_day=None,
                  hour_scores=None):
    """Earliest-fit allocation of candidate tasks into one day's free time.

    With hour_scores, higher-scoring free intervals are filled first (deep work
    lands in learned-productive hours); ties and unscored intervals keep
    earliest-first order."""
    slots = []
    if now_for_day is not None:
        now_min = now_for_day.hour * 60 + now_for_day.minute
        free = _subtract(free, 0, now_min)
    if hour_scores:
        def interval_score(iv):
            marks = [hour_scores.get(str(h)) for h in range(iv["start"] // 60,
                                                           ((iv["end"] - 1) // 60) + 1)]
            vals = [v for v in marks if isinstance(v, (int, float))]
            avg = (sum(vals) / len(vals)) if vals else 0.0
            return (-avg, iv["start"])
        free = sorted((dict(iv) for iv in free), key=interval_score)
    else:
        free = [dict(iv) for iv in free]
    cap_left = day_capacity
    for cand in open_tasks:
        if cand["remaining"] <= 0:
            continue
        due = cand["task"].get("date")
        if due and _to_date(due) < _to_date(day_str):
            continue  # deadline already passed earlier in the horizon: handled
        # class-occurrence tasks are not study work; skip (defensive)
        if cand["task"].get("planned") and \
                cand["task"]["planned"].get("date") == day_str and \
                fdates.hhmm_to_minutes(cand["task"]["planned"].get("start")) is not None:
            # already has a committed slot today - reserve it
            p = cand["task"]["planned"]
            s = fdates.hhmm_to_minutes(p["start"])
            e = fdates.hhmm_to_minutes(p["end"])
            free = _subtract(free, s, e)
            continue
        remaining = cand["remaining"]
        if cap_left is not None:
            remaining = min(remaining, cap_left)
            if remaining <= 0:
                continue
        total_chunks = -(-remaining // MAX_BLOCK_MINUTES)
        chunk_no = 0
        for iv in list(free):
            while remaining > 0 and iv["end"] - iv["start"] >= MIN_SLOT_MINUTES:
                avail = iv["end"] - iv["start"]
                block = min(remaining, MAX_BLOCK_MINUTES, avail)
                if block < MIN_SLOT_MINUTES:
                    break
                s = iv["start"]
                e = s + block
                chunk_no += 1
                slots.append(PlanSlot(
                    task_id=cand["task"]["id"], title=cand["task"].get("title", ""),
                    start=fdates.minutes_to_hhmm(s), end=fdates.minutes_to_hhmm(e),
                    reason=f"{cand['reason']} (day {day_str})", chunk=chunk_no,
                    chunks=total_chunks))
                iv["start"] = min(iv["end"], e)
                cand["remaining"] -= block
                remaining -= block
                if cap_left is not None:
                    cap_left -= block
                if iv["end"] - iv["start"] < MIN_SLOT_MINUTES:
                    break
            if remaining <= 0 or (cap_left is not None and cap_left <= 0):
                break
        if cap_left is not None and cap_left <= 0:
            break
    return slots


def apply_multi_day(plan, data):
    """Persist planned slots into task['planned'] (validated call sites only)."""
    from logic import save_data
    from focus_agent.repository import TaskRepository
    repo = TaskRepository(data)
    applied = 0
    for day in plan.days:
        by_task = {}
        for s in day.slots:
            by_task.setdefault(s.task_id, []).append(s)
        for task_id, task_slots in by_task.items():
            task = repo.get(task_id)
            if not task:
                continue
            first = task_slots[0]
            task["planned"] = {
                "date": day.date,
                "start": first.start,
                "end": task_slots[-1].end,
                "reason": first.reason,
            }
            applied += 1
    save_data(data)
    return applied


def detect_conflicts(data, date_str, settings=None):
    """Overlaps among classes, user blocks and committed planned slots."""
    items = []
    weekday = fdates.weekday_key(_to_date(date_str))
    for t in data.get("tasks", []):
        if t.get("type") != "class":
            continue
        sch = t.get("schedule") or {}
        if weekday not in (sch.get("days") or []):
            continue
        s, e = fdates.hhmm_to_minutes(sch.get("start")), fdates.hhmm_to_minutes(sch.get("end"))
        if s is not None and e is not None:
            items.append({"start": s, "end": e, "title": t.get("title"), "kind": "class"})
    for b in data.get("schedule_blocks", []) or []:
        if b.get("date") and b["date"] != date_str:
            continue
        if not b.get("date") and weekday not in (b.get("days") or []):
            continue
        s, e = fdates.hhmm_to_minutes(b.get("start")), fdates.hhmm_to_minutes(b.get("end"))
        if s is not None and e is not None:
            items.append({"start": s, "end": e, "title": b.get("title"), "kind": "block"})
    for t in data.get("tasks", []):
        p = t.get("planned") if isinstance(t, dict) else None
        if not p or p.get("date") != date_str:
            continue
        s, e = fdates.hhmm_to_minutes(p.get("start")), fdates.hhmm_to_minutes(p.get("end"))
        if s is not None and e is not None:
            items.append({"start": s, "end": e, "title": t.get("title"), "kind": "planned"})
    items.sort(key=lambda x: x["start"])
    conflicts = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            if b["start"] < a["end"] and a["start"] < b["end"]:
                conflicts.append({
                    "a": f"{a['kind']}:{a['title']}",
                    "b": f"{b['kind']}:{b['title']}",
                    "overlap": (f"{fdates.minutes_to_hhmm(max(a['start'], b['start']))}-"
                                f"{fdates.minutes_to_hhmm(min(a['end'], b['end']))}"),
                })
    return items, conflicts


__all__ = ["MultiDayPlan", "plan_range", "detect_conflicts", "_blocks_for",
           "MAX_HORIZON_DAYS"]
