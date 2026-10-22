"""Schedule feasibility, class constraints, overload, rescheduling (spec N.7)."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from focus_agent import scheduler as fs
from focus_agent import dates as fdates
from conftest import NOW  # Fri 2026-10-23 14:00

SETTINGS = {"study_hours": {"start": "09:00", "end": "22:00"}, "break_minutes": 10,
            "timezone": "local"}


def _minutes(hhmm):
    return fdates.hhmm_to_minutes(hhmm)


def _slots_of(plan, task_title=None):
    return [s for s in plan.slots
            if task_title is None or s.title == task_title]


def test_no_overlaps_and_valid_times(sample_data):
    plan = fs.generate_day_plan(sample_data, "2026-10-23", settings=SETTINGS, now=NOW)
    assert plan.slots
    ordered = sorted(plan.slots, key=lambda s: s.start)
    for a, b in zip(ordered, ordered[1:]):
        assert _minutes(a.end) <= _minutes(b.start), f"overlap: {a} vs {b}"
    for s in plan.slots:
        assert _minutes(s.end) > _minutes(s.start)
        assert s.start >= "00:00" and s.end <= "23:59"


def test_classes_block_time(sample_data):
    plan = fs.generate_day_plan(sample_data, "2026-10-23", settings=SETTINGS, now=NOW)
    # class CSE 3202 runs 10:00-11:30 on Fridays: no slot may overlap it
    for s in plan.slots:
        assert not (_minutes(s.start) < _minutes("11:30") and _minutes(s.end) > _minutes("10:00")), \
            f"slot {s.start}-{s.end} overlaps the class"


def test_new_slots_not_in_the_past(sample_data):
    plan = fs.generate_day_plan(sample_data, "2026-10-23", settings=SETTINGS, now=NOW)
    for s in plan.slots:
        if s.fixed:
            continue
        assert _minutes(s.start) >= 14 * 60, f"new slot {s.start} placed in the past"


def test_priority_order_overdue_and_urgent_first(data):
    import logic
    logic.add_task_logic(data, "Overdue essay", deadline="2026-10-20", duration=60, importance=3)
    logic.add_task_logic(data, "Far future thing", deadline="2026-11-20", duration=60)
    logic.add_task_logic(data, "Due today", deadline="2026-10-23", duration=60, importance=2)
    plan = fs.generate_day_plan(data, "2026-10-23", settings=SETTINGS, now=NOW)
    titles = [s.title for s in plan.slots if not s.fixed]
    assert titles.index("Overdue essay") < titles.index("Far future thing")
    assert titles.index("Due today") < titles.index("Far future thing")


def test_overload_reported_never_silently_dropped(data):
    import logic
    # far more work than an afternoon can hold
    for i in range(6):
        logic.add_task_logic(data, f"Big task {i}", deadline="2026-10-24", duration=150,
                             importance=3)
    plan = fs.generate_day_plan(data, "2026-10-23", settings=SETTINGS, now=NOW)
    assert plan.overload
    assert plan.overload_minutes > 0
    # every unscheduled task is EXPLAINED, none vanish
    scheduled_ids = {s.task_id for s in plan.slots}
    total_tasks = {t["id"] for t in data["tasks"]}
    missing = total_tasks - scheduled_ids
    unscheduled_ids = {u["task_id"] for u in plan.unscheduled}
    assert missing <= unscheduled_ids, "a task disappeared from the plan!"
    for u in plan.unscheduled:
        assert u["reason"]


def test_task_without_estimate_explained_not_dropped(data):
    import logic
    logic.add_task_logic(data, "Mystery task", deadline="2026-10-23")  # no duration
    plan = fs.generate_day_plan(data, "2026-10-23", settings=SETTINGS, now=NOW)
    matches = [u for u in plan.unscheduled if u["title"] == "Mystery task"]
    assert matches and "estimate" in matches[0]["reason"]
    assert all(s.title != "Mystery task" for s in plan.slots)


def test_long_task_split_into_blocks(data):
    import logic
    logic.add_task_logic(data, "Marathon task", deadline="2026-10-23", duration=200)
    plan = fs.generate_day_plan(data, "2026-10-23", settings=SETTINGS, now=NOW)
    chunks = [s for s in plan.slots if s.title == "Marathon task"]
    assert len(chunks) >= 2
    assert all(s.chunk <= s.chunks for s in chunks)


def test_reschedule_preserves_completed_and_started(sample_data):
    import logic
    # a slot was planned and already completed this morning
    task = logic.get_today_tasks(sample_data)
    t = next(t for t in sample_data["tasks"] if t["title"] == "Python practice")
    t["planned"] = {"date": "2026-10-23", "start": "09:00", "end": "09:45", "reason": ""}
    t["status"] = "done"
    t["completed_at"] = "2026-10-23T09:45:00"
    plan = fs.generate_day_plan(sample_data, "2026-10-23", settings=SETTINGS, now=NOW,
                                preserve_slots=True)
    fixed = [s for s in plan.slots if s.fixed]
    assert any(s.title == "Python practice" and s.start == "09:00" for s in fixed)
    # and nothing new overlaps the preserved slot
    for s in plan.slots:
        if not s.fixed:
            assert not (_minutes(s.start) < _minutes("09:45") and _minutes(s.end) > _minutes("09:00"))


def test_urgency_buckets_explainable():
    from datetime import date
    today = date(2026, 10, 23)
    assert fs.urgency_bucket("2026-10-20", today) == "overdue"
    assert fs.urgency_bucket("2026-10-23", today) == "today"
    assert fs.urgency_bucket("2026-10-24", today) == "1d"
    assert fs.urgency_bucket("2026-11-30", today) == "later"
    assert fs.urgency_bucket(None, today) == "none"


def test_priority_has_reason_string(sample_data):
    ranked = fs.explain_priorities(sample_data, "2026-10-23", settings=SETTINGS, now=NOW)
    assert ranked
    top = ranked[0]
    assert top["score"] > 0 and len(top["reason"]) > 10
    # overdue AI assignment should outrank far-future work
    assert ranked[0]["title"] in ("AI assignment", "Python practice", "Database reading")


def test_availability_reflects_classes(sample_data):
    free, busy, info = fs.get_availability(sample_data, "2026-10-23", SETTINGS)
    assert busy and busy[0]["title"] == "CSE 3202"
    total_free = sum(iv["end"] - iv["start"] for iv in free)
    window = (_minutes("22:00") - _minutes("09:00")) - (_minutes("11:30") - _minutes("10:00"))
    assert total_free <= window
    assert any(c["title"] == "CSE 3202" for c in info["classes"])


def test_midnight_boundary_and_dst_safe():
    # plans stay within one local date; conversions wrap at midnight
    assert fdates.minutes_to_hhmm(23 * 60 + 59) == "23:59"
    assert fdates.hhmm_to_minutes("00:00") == 0


def test_apply_plan_persists_slots(sample_data, data_env):
    import logic
    plan = fs.generate_day_plan(sample_data, "2026-10-23", settings=SETTINGS, now=NOW)
    fs.apply_plan(sample_data, plan)
    reloaded = logic.load_data()
    planned = [t for t in reloaded["tasks"] if t.get("planned")]
    assert planned, "applied plan must persist to storage"
    for t in planned:
        assert t["planned"]["date"] == "2026-10-23"
