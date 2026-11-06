# ==================== SCHEDULER.PY ====================
# Deterministic, testable daily planning engine.
#
# Given tasks + class routine + study preferences + history-aware duration
# estimates, produce a feasible schedule with NO overlapping slots, NO class
# conflicts and valid start/end times. Tasks that genuinely cannot fit are
# reported with reasons - a task is never silently dropped, and overload is
# stated openly with alternatives.
#
# Every decision carries an explanation string ("reason"), so priorities are
# transparent rather than opaque rankings.

from dataclasses import dataclass, field

from focus_agent import dates as fdates
from focus_agent.estimator import estimate_minutes

MAX_BLOCK_MINUTES = 90       # longer tasks are split into blocks with breaks
HORIZON_DAYS = 7             # tasks due further out stay off today's plan

URGENCY_POINTS = {           # deadline urgency -> priority points
    "overdue": 40, "today": 30, "1d": 24, "2d": 18, "3-4d": 12, "5-7d": 6,
    "later": 2, "none": 0,
}
IMPORTANCE_POINTS = {1: 0, 2: 6, 3: 12}
DIFFICULTY_POINTS = {1: 0, 2: 3, 3: 6}
IMPORTANCE_NAMES = {1: "low", 2: "medium", 3: "high"}
DIFFICULTY_NAMES = {1: "easy", 2: "moderate", 3: "hard"}


@dataclass
class PlanSlot:
    task_id: str
    title: str
    start: str            # HH:MM
    end: str              # HH:MM
    reason: str
    fixed: bool = False   # already done/started -> preserved on reschedule
    chunk: int = 1
    chunks: int = 1

    def to_dict(self):
        return {"task_id": self.task_id, "title": self.title,
                "start": self.start, "end": self.end, "reason": self.reason,
                "fixed": self.fixed, "chunk": self.chunk, "chunks": self.chunks}


@dataclass
class PlanResult:
    date: str
    slots: list = field(default_factory=list)        # list[PlanSlot]
    unscheduled: list = field(default_factory=list)  # list[{task_id,title,reason}]
    overload: bool = False
    overload_minutes: int = 0
    notes: list = field(default_factory=list)

    def to_dict(self):
        return {
            "date": self.date,
            "slots": [s.to_dict() for s in self.slots],
            "unscheduled": list(self.unscheduled),
            "overload": self.overload,
            "overload_minutes": self.overload_minutes,
            "notes": list(self.notes),
        }


# ==================== PRIORITY ====================

def urgency_bucket(due_date, today):
    """Classify deadline urgency into a named bucket (explainable)."""
    if not due_date:
        return "none"
    try:
        from datetime import date as _d
        due = _d.fromisoformat(due_date)
    except (ValueError, TypeError):
        return "none"
    days = (due - today).days
    if days < 0:
        return "overdue"
    if days == 0:
        return "today"
    if days == 1:
        return "1d"
    if days == 2:
        return "2d"
    if days <= 4:
        return "3-4d"
    if days <= 7:
        return "5-7d"
    return "later"


def task_priority(task, today):
    """Score + human-readable reason for one task. Deterministic."""
    parts, score = [], 0

    bucket = urgency_bucket(task.get("date"), today)
    u = URGENCY_POINTS[bucket]
    score += u
    if bucket == "overdue":
        parts.append(f"OVERDUE since {task.get('date')} (+{u})")
    elif bucket != "none":
        parts.append(f"due {task.get('date')} ({bucket}, +{u})")

    imp = task.get("importance") if task.get("importance") in IMPORTANCE_POINTS else 2
    score += IMPORTANCE_POINTS[imp]
    parts.append(f"importance {IMPORTANCE_NAMES[imp]} (+{IMPORTANCE_POINTS[imp]})")

    diff = task.get("difficulty") if task.get("difficulty") in DIFFICULTY_POINTS else 2
    score += DIFFICULTY_POINTS[diff]
    parts.append(f"difficulty {DIFFICULTY_NAMES[diff]} (+{DIFFICULTY_POINTS[diff]})")

    hint = task.get("priority_hint")
    if isinstance(hint, (int, float)) and 0 <= hint <= 100:
        pts = round(hint / 10)
        score += pts
        parts.append(f"your priority hint (+{pts})")

    return score, "; ".join(parts)


def _task_estimate(task, data, settings):
    """Duration in minutes: user estimate adjusted by learned realism."""
    est = task.get("duration")
    if not isinstance(est, (int, float)) or est <= 0:
        return None, "no duration estimate"
    info = estimate_minutes(data, task, settings)
    adj = int(info["minutes"])
    if adj != int(est):
        note = ("adjusted to" if adj > est else "reduced to")
        return adj, f"{est}min estimate {note} {adj}min ({info['basis']})"
    return adj, f"{int(est)}min"


def _eligible_tasks(data, date_str, settings):
    """Tasks to consider for this date's plan, in priority order."""
    from datetime import date as _d
    today = _d.fromisoformat(date_str)
    out = []
    for t in data.get("tasks", []):
        if not isinstance(t, dict) or t.get("type") != "task":
            continue
        if t.get("status") in ("done", "archived", "missed"):
            continue
        due = t.get("date")
        # Day-wise roadmap tasks ("Day 2: ...", or linked to a goal) belong to their
        # target date and should not be pulled into earlier days to cause false overload.
        if due and due > date_str and (
            t.get("goal_id") or str(t.get("title") or "").strip().lower().startswith("day ")
        ):
            continue
        bucket = urgency_bucket(due, today)
        if bucket == "later":
            # far-future work only fills the plan if it has no pressing rivals;
            # still eligible but ranked low
            pass
        score, reason = task_priority(t, today)
        minutes, est_note = _task_estimate(t, data, settings)
        if minutes is None:
            out.append({"task": t, "score": score - 25,  # un-estimated: deprioritized
                        "reason": reason + "; no duration estimate", "minutes": None})
            continue
        out.append({"task": t, "score": score, "reason": f"{reason}; {est_note}",
                    "minutes": minutes})
    out.sort(key=lambda x: (-x["score"], x["task"].get("date") or "9999",
                            x["task"].get("title") or ""))
    return out


# ==================== AVAILABILITY ====================

def get_availability(data, date_str, settings=None):
    """Free intervals (minutes) for a date: study window minus classes.

    Returns (free_intervals, busy_intervals, window_info) with HH:MM strings.
    """
    settings = settings or (data.get("settings") or {})
    study = settings.get("study_hours") or {"start": "09:00", "end": "22:00"}
    win_start = fdates.hhmm_to_minutes(study.get("start", "09:00"))
    win_end = fdates.hhmm_to_minutes(study.get("end", "22:00"))
    if win_start is None or win_end is None or win_end <= win_start:
        win_start, win_end = 9 * 60, 22 * 60

    weekday = fdates.weekday_key(_to_date(date_str))
    busy = []
    for t in data.get("tasks", []):
        if t.get("type") != "class":
            continue
        sch = t.get("schedule") or {}
        if weekday not in (sch.get("days") or []):
            continue
        s, e = fdates.hhmm_to_minutes(sch.get("start")), fdates.hhmm_to_minutes(sch.get("end"))
        if s is None or e is None or e <= s:
            continue  # malformed routine entries are never fabricated into blocks
        busy.append({"start": s, "end": e, "title": t.get("title"),
                     "id": t.get("id")})
    busy.sort(key=lambda b: b["start"])

    # subtract busy from window
    free, cursor = [], win_start
    for b in busy:
        if b["end"] <= cursor or b["start"] >= win_end:
            continue
        if b["start"] > cursor:
            free.append({"start": cursor, "end": min(b["start"], win_end)})
        cursor = max(cursor, b["end"])
    if cursor < win_end:
        free.append({"start": cursor, "end": win_end})
    free = [iv for iv in free if iv["end"] - iv["start"] >= 15]

    info = {"window": f"{fdates.minutes_to_hhmm(win_start)}-{fdates.minutes_to_hhmm(win_end)}",
            "classes": [{"title": b["title"], "start": fdates.minutes_to_hhmm(b["start"]),
                         "end": fdates.minutes_to_hhmm(b["end"])} for b in busy]}
    return free, busy, info


def _to_date(date_str):
    from datetime import date as _d
    return _d.fromisoformat(date_str)


# ==================== PLANNING ====================

def generate_day_plan(data, date_str, settings=None, now=None,
                      preserve_slots=True, commit=False):
    """Build (and optionally commit) a feasible plan for one date.

    - preserve_slots: keep slots already done/started for that date.
    - commit: write slots into task['planned'] (only with preserve done first).
    Returns PlanResult.
    """
    settings = settings or (data.get("settings") or {})
    break_min = int(settings.get("break_minutes", 10) or 10)
    tz_now = now or fdates.now_here(settings)
    today = _to_date(date_str)
    is_today = tz_now.date() == today

    free, busy, info = get_availability(data, date_str, settings)
    now_min = tz_now.hour * 60 + tz_now.minute if is_today else -1

    # Fixed slots: previously planned AND already done/started -> preserved
    fixed_slots = []
    for t in data.get("tasks", []):
        p = t.get("planned") if isinstance(t, dict) else None
        if not isinstance(p, dict) or p.get("date") != date_str:
            continue
        s = fdates.hhmm_to_minutes(p.get("start"))
        e = fdates.hhmm_to_minutes(p.get("end"))
        if s is None or e is None:
            continue
        done = t.get("status") == "done"
        started = is_today and s <= now_min
        if done or (preserve_slots and started):
            fixed_slots.append(PlanSlot(
                task_id=t["id"], title=t.get("title", ""), start=fdates.minutes_to_hhmm(s),
                end=fdates.minutes_to_hhmm(e),
                reason="already completed" if done else "already started",
                fixed=True))
    fixed_slots.sort(key=lambda s: s.start)

    # remove fixed time from free intervals
    for f in fixed_slots:
        s, e = fdates.hhmm_to_minutes(f.start), fdates.hhmm_to_minutes(f.end)
        free = _subtract(free, s, e)

    # never place NEW slots in the past for today's plan
    if is_today and now_min >= 0:
        free = _subtract(free, 0, now_min)

    candidates = _eligible_tasks(data, date_str, settings)
    slots, unscheduled = [], []
    planned_ids = {}

    def place(minutes_needed, task):
        """Earliest-fit placement, splitting long tasks into <=90min blocks."""
        remaining = minutes_needed
        chunk_no = 0
        total_chunks = -(-minutes_needed // MAX_BLOCK_MINUTES)
        placed_any = False
        for iv in list(free):
            while remaining > 0:
                avail = iv["end"] - iv["start"]
                block = min(remaining, MAX_BLOCK_MINUTES, avail)
                if block < 15:
                    break
                s = iv["start"]
                e = s + block
                chunk_no += 1
                slots.append(PlanSlot(
                    task_id=task["task"]["id"], title=task["task"].get("title", ""),
                    start=fdates.minutes_to_hhmm(s), end=fdates.minutes_to_hhmm(e),
                    reason=task["reason"], chunk=chunk_no, chunks=total_chunks))
                planned_ids[task["task"]["id"]] = True
                iv["start"] = e
                remaining -= block
                placed_any = True
                if iv["end"] - iv["start"] < 15:
                    break
                # insert a break after each placed block (except end of interval)
                iv["start"] = min(iv["end"], e + break_min)
            if remaining <= 0:
                break
        return placed_any, remaining

    for cand in candidates:
        if cand["task"]["id"] in planned_ids:
            continue
        minutes = cand["minutes"]
        if minutes is None:
            unscheduled.append({
                "task_id": cand["task"]["id"], "title": cand["task"].get("title", ""),
                "reason": "no duration estimate - add one (e.g. 'it will take about 2 hours')"})
            continue
        placed, leftover = place(minutes, cand)
        if not placed:
            free_total = sum(iv["end"] - iv["start"] for iv in free)
            unscheduled.append({
                "task_id": cand["task"]["id"], "title": cand["task"].get("title", ""),
                "reason": (f"needs {minutes}min but only {free_total}min free "
                           f"({info['window']}, minus classes) - does not fit today")})
        elif leftover > 0:
            unscheduled.append({
                "task_id": cand["task"]["id"], "title": cand["task"].get("title", ""),
                "reason": f"partially scheduled; {leftover}min could not fit today"})

    slots.sort(key=lambda s: s.start)
    all_slots = sorted(fixed_slots + slots, key=lambda s: s.start)

    result = PlanResult(date=date_str, slots=all_slots, unscheduled=unscheduled)
    result.notes.append(f"Study window {info['window']}")
    if info["classes"]:
        result.notes.append("Classes: " + ", ".join(
            f"{c['title']} {c['start']}-{c['end']}" for c in info["classes"]))
    else:
        result.notes.append("No classes scheduled for this weekday")

    unsched_need = 0
    for u in unscheduled:
        t = next((c for c in candidates if c["task"]["id"] == u["task_id"]), None)
        if t and t["minutes"]:
            unsched_need += t["minutes"]
    if unsched_need > 0:
        result.overload = True
        result.overload_minutes = unsched_need
        result.notes.append(
            f"⚠ Today is overloaded by about {unsched_need}min of work that does not fit. "
            "Options: extend the study window in Settings, move lower-priority work to "
            "another day, or reduce scope of the largest task.")
    if commit:
        apply_plan(data, result)
    return result


def _subtract(intervals, s, e):
    out = []
    for iv in intervals:
        if e <= iv["start"] or s >= iv["end"]:
            out.append(dict(iv))
            continue
        if s > iv["start"]:
            out.append({"start": iv["start"], "end": min(s, iv["end"])})
        if e < iv["end"]:
            out.append({"start": max(e, iv["start"]), "end": iv["end"]})
    return [iv for iv in out if iv["end"] - iv["start"] >= 15]


def apply_plan(data, plan):
    """Persist a plan into task['planned'] (validated before call)."""
    from logic import save_data
    planned_by_task = {}
    for s in plan.slots:
        if s.fixed:
            continue
        planned_by_task.setdefault(s.task_id, []).append(s)
    for task_id, task_slots in planned_by_task.items():
        task = next((t for t in data.get("tasks", []) if t.get("id") == task_id), None)
        if not task:
            continue
        first = task_slots[0]
        task["planned"] = {
            "date": plan.date,
            "start": first.start,
            "end": task_slots[-1].end,
            "reason": first.reason,
        }
    save_data(data)


def reschedule_after_change(data, date_str=None, settings=None, now=None):
    """Recalculate the plan for a date after a delay/early completion.

    Completed/started work and fixed commitments are preserved; everything
    else is re-fit. Returns the new PlanResult (not committed until apply_plan).
    """
    return generate_day_plan(data, date_str, settings=settings, now=now,
                             preserve_slots=True, commit=False)


def explain_priorities(data, date_str=None, settings=None, now=None):
    """Priority-ordered task list with reasons (no slots)."""
    settings = settings or (data.get("settings") or {})
    tz_now = now or fdates.now_here(settings)
    date_str = date_str or tz_now.date().isoformat()
    ranked = _eligible_tasks(data, date_str, settings)
    out = []
    for i, cand in enumerate(ranked, 1):
        t = cand["task"]
        out.append({
            "rank": i,
            "task_id": t.get("id"),
            "title": t.get("title", ""),
            "score": cand["score"],
            "due_date": t.get("date"),
            "minutes": cand["minutes"],
            "reason": cand["reason"],
            "status": t.get("status"),
        })
    return out
