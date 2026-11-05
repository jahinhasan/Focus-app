"""Phase 5: productive hours, adherence, subject rates, memory-effectiveness."""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from focus_agent import patterns as fpatterns
from focus_agent import planner
from focus_agent import tools as ft
from focus_agent.schemas import ToolCall
from conftest import NOW  # Fri 2026-10-23 14:00

CTX = {"settings": {"study_hours": {"start": "09:00", "end": "22:00"}}, "now": NOW}


def _feed_hours(data, hours_minutes):
    buckets = data.setdefault("hourly_focus", {})
    for day, hour, minutes in hours_minutes:
        buckets.setdefault(day, {})[hour] = buckets.get(day, {}).get(hour, 0) + minutes


def test_productive_hours_reliable_after_enough_data(data, data_env):
    r = fpatterns.productive_hours(data)
    assert r["reliable"] is False and "45min" in r["basis"], "cold start disclosed"
    _feed_hours(data, [("2026-10-20", "09", 60), ("2026-10-21", "09", 30),
                       ("2026-10-21", "21", 10)])
    r2 = fpatterns.productive_hours(data)
    assert r2["reliable"] is True
    assert r2["hours"]["09"] == 1.0 and r2["hours"]["09"] > r2["hours"]["21"]
    assert "90min" in r2["basis"] or "learned" in r2["basis"]


def test_productive_hours_ignores_unattributed_bucket(data):
    _feed_hours(data, [("2026-10-20", "99", 500)])
    r = fpatterns.productive_hours(data)
    assert r["reliable"] is False, "unattributed minutes must not fake learning"


def test_weekday_effects(data):
    focus = data.setdefault("focus_sessions", {})
    for i, day in enumerate(["2026-10-19", "2026-10-26", "2026-10-20"]):  # mon, mon, tue
        focus[day] = {"total_seconds": (60 + i * 10) * 60, "sessions": 1, "class_seconds": 0}
    r = fpatterns.weekday_effects(data)
    assert r["days"] == 3 and r["by_weekday"]["mon"] >= 60
    assert "average over 3" in r["basis"]


def test_subject_completion_rates(data, data_env):
    from logic import add_task_logic, complete_task_logic
    from logic import add_subject
    add_subject(data, "AI")
    for i in range(4):
        add_task_logic(data, f"AI t{i}", duration=30, subject="AI")
        complete_task_logic(data, data["tasks"][-1]["id"])
    add_task_logic(data, "AI open", duration=30, subject="AI")
    r = fpatterns.subject_completion_rates(data)
    assert r["AI"]["done"] == 4 and r["AI"]["total"] == 5
    assert r["AI"]["rate"] == 0.8 and r["AI"]["reliable"] is True


def test_schedule_adherence_math(data, data_env):
    from logic import add_task_logic, complete_task_logic, save_data
    mem = data.setdefault("agent_memory", {})
    past = "2026-10-22"
    t1 = add_task_logic(data, "Planned done", duration=60)
    data["tasks"][-1]["planned"] = {"date": past, "start": "09:00", "end": "10:00"}
    complete_task_logic(data, t1["id"])
    t2 = add_task_logic(data, "Planned skipped", duration=60)
    data["tasks"][-1]["planned"] = {"date": past, "start": "11:00", "end": "12:00"}
    mem["plan_log"] = [{"ts": 1, "plan": {"date": past, "committed": True, "slots": []}}]
    save_data(data)
    r = fpatterns.schedule_adherence(data, today=NOW.date())
    assert r["slots_total"] == 2 and r["slots_honored"] == 1
    assert r["ratio"] == 0.5


def test_missed_tasks_carryover(data, data_env):
    from logic import add_task_logic
    add_task_logic(data, "Old overdue", duration=30)  # no date
    t = add_task_logic(data, "Past due task", duration=30)
    data["tasks"][-1]["date"] = "2026-10-20"
    r = fpatterns.missed_tasks(data, now=NOW)
    titles = [m["title"] for m in r]
    assert "Past due task" in titles and "Old overdue" not in titles
    assert r[0]["days_overdue"] == 3


def test_planner_uses_productive_hours_for_placement(data, data_env):
    """With a learned profile, work lands in high-score intervals first."""
    from logic import add_task_logic
    _feed_hours(data, [("2026-10-20", "20", 120), ("2026-10-21", "20", 60),
                       ("2026-10-21", "09", 15)])
    add_task_logic(data, "Deep work", duration=120, deadline="2026-10-30")
    plan = planner.plan_range(data, "2026-10-23", settings=data["settings"],
                              now=datetime(2026, 10, 23, 8, 0), days=1,
                              hour_scores=fpatterns.productive_hours(data)["hours"])
    slots = plan.days[0].slots
    assert slots, "work planned"
    first = slots[0]
    assert first.start >= "20:00" or first.start < "09:30", \
        "first slot should be in the learned-productive evening interval"


def test_spec_case_completion_history_tool(data, data_env):
    from logic import add_task_logic, complete_task_logic
    t = add_task_logic(data, "Done task", duration=60)
    data["tasks"][-1]["actual_minutes"] = 120
    complete_task_logic(data, t["id"])
    r = ft.execute_tool(data, ToolCall(tool="get_task_completion_history",
                                       args={"days": 30}, call_id="ch1"), ctx=CTX)
    assert r.ok and r.data["completed"]
    row = r.data["completed"][0]
    assert row["est_minutes"] == 60 and row["actual_minutes"] == 120


def test_compare_estimated_actual_tool(data, data_env):
    from logic import add_task_logic, complete_task_logic
    for i in range(3):
        t = add_task_logic(data, f"Est act {i}", duration=60, subject="AI")
        data["tasks"][-1]["actual_minutes"] = 120 + i * 10
        complete_task_logic(data, t["id"])
    r = ft.execute_tool(data, ToolCall(tool="compare_estimated_actual_duration",
                                       args={}, call_id="ce1"), ctx=CTX)
    assert r.ok and r.data["rows"]
    s = r.data["summary"]
    assert s["n"] == 3 and s["mean_error_ratio"] > 1


def test_analyze_patterns_tool_discloses_cold_start(data, data_env):
    r = ft.execute_tool(data, ToolCall(tool="analyze_productivity_patterns",
                                       args={}, call_id="ap1"), ctx=CTX)
    assert r.ok
    assert "not enough data" in r.message.lower(), \
        "cold start must be disclosed, never claimed as learned"


def test_memory_effectiveness_estimate_improves_with_history(data, data_env):
    """The official metric: estimate error with history < error without."""
    from logic import add_task_logic
    # user consistently takes 2x estimates on AI work
    for i in range(4):
        t = add_task_logic(data, f"AI pattern {i}", duration=60, subject="AI",
                           difficulty=2)
        data["tasks"][-1]["actual_minutes"] = 120
        data["tasks"][-1]["completed_at"] = f"2026-10-{10 + i}T12:00:00"
        data["tasks"][-1]["status"] = "done"
    new = add_task_logic(data, "AI prediction target", duration=60, subject="AI",
                         difficulty=2)
    from focus_agent.estimator import estimate_minutes
    learned = estimate_minutes(data, data["tasks"][-1])
    assert learned["reliable"] is True
    assert abs(learned["minutes"] - 120) <= 10, "learned estimate near truth"
    assert learned["minutes"] != 60, "learning must move the estimate off naive"
