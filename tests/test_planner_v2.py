"""Phase 4: multi-day planning, blocks, conflicts, capacity, reschedule_task."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from focus_agent import planner
from focus_agent import AgentController
from focus_agent.repository import TaskRepository, ScheduleRepository
from conftest import OfflineProvider, NOW  # NOW = Fri 2026-10-23 14:00


def _mk(data, title, due, minutes, **kw):
    r = TaskRepository(data)
    return r.create(title, deadline=due, duration=minutes, **kw)


def test_plan_range_respects_deadline_priority(sample_data):
    plan = planner.plan_range(sample_data, "2026-10-23",
                              settings=sample_data["settings"], now=NOW, days=3)
    assert plan.days and plan.days[0].date == "2026-10-23"
    all_slots = [s for d in plan.days for s in d.slots]
    assert all_slots, "open tasks must be planned"
    # no overlapping slots within a day
    for d in plan.days:
        ss = sorted(d.slots, key=lambda s: s.start)
        for a, b in zip(ss, ss[1:]):
            assert b.start >= a.end, f"overlap {a.start}-{a.end} vs {b.start}-{b.end}"


def test_blocks_protect_time_from_planning(data, data_env):
    _mk(data, "Essay", "2026-10-30", 120)
    s = ScheduleRepository(data)
    s.create("Family event", start="15:00", end="19:00", date="2026-10-23")
    plan = planner.plan_range(data, "2026-10-23", settings=data["settings"],
                              now=datetime(2026, 10, 23, 9, 0), days=1)
    slots = plan.days[0].slots
    for slot in slots:
        assert not ("15:00" <= slot.start < "19:00"), \
            "no slot may start inside the blocked window"
    # free time 15-19 must be excluded -> allocations skip it
    starts = [slot.start for slot in slots]
    assert not any("15:00" <= st < "19:00" for st in starts)


def test_spec_case_block_from_class_time(sample_data):
    """'I have a class from 10 AM to 12 PM. Don't schedule anything during that time.'"""
    c = AgentController(sample_data)
    reply = c.handle("I have a class from 10 AM to 12 PM tomorrow. "
                     "Don't schedule anything during that time.",
                     provider=OfflineProvider(), now=NOW)
    assert any(tr.ok and tr.tool == "create_schedule_block"
               for tr in reply.tool_results)
    blocks = sample_data["schedule_blocks"]
    assert blocks and blocks[-1]["start"] == "10:00" and blocks[-1]["end"] == "12:00"
    # and the planner honors it for that date
    plan = planner.plan_range(sample_data, "2026-10-24",
                              settings=sample_data["settings"], days=1)
    for d in plan.days:
        for slot in d.slots:
            assert not ("10:00" <= slot.start < "12:00")


def test_capacity_limit_three_hours_free(sample_data):
    """'I have three hours free tomorrow. Plan my pending tasks.'"""
    c = AgentController(sample_data)
    reply = c.handle("I have three hours free tomorrow. Plan my pending tasks.",
                     provider=OfflineProvider(), now=NOW)
    assert reply.plan is not None
    assert reply.plan.get("capacity_minutes") == 180
    slots = reply.plan["days"][0]["slots"]
    total = sum(_mins(s) for s in slots)
    assert total <= 180, f"capacity exceeded: {total}min"
    assert "180" in reply.message or "three hours" in reply.message.lower() \
        or "you said you have" in reply.message


def _mins(slot):
    from focus_agent import dates as fdates
    return (fdates.hhmm_to_minutes(slot["end"]) - fdates.hhmm_to_minutes(slot["start"]))


def test_deadline_infeasibility_reported(sample_data):
    # far more work than the horizon can hold, deadlines inside horizon
    _mk(sample_data, "Huge task A", "2026-10-24", 600)
    _mk(sample_data, "Huge task B", "2026-10-24", 600)
    plan = planner.plan_range(sample_data, "2026-10-23",
                              settings=sample_data["settings"],
                              now=datetime(2026, 10, 23, 20, 0), days=1)
    assert plan.unschedulable, "overflow must be identified, not dropped silently"
    assert any("only" in u["reason"] or "no free slot" in u["reason"]
               for u in plan.unschedulable)


def test_detect_conflicts_finds_overlap(data, data_env):
    from logic import add_class_task
    add_class_task(data, title="CSE 3202", subject="AI", days=["fri"],
                   start_time="10:00", end_time="11:30")
    s = ScheduleRepository(data)
    s.create("Overlapping meeting", start="11:00", end="12:00", days=["fri"])
    items, conflicts = planner.detect_conflicts(data, "2026-10-23")
    assert conflicts, "11:00-11:30 overlap must be found"
    assert any("CSE 3202" in c["a"] and "Overlapping meeting" in c["b"]
               for c in conflicts)


def test_reschedule_task_tool_validates_and_moves(data, data_env):
    from focus_agent import tools as ft
    from focus_agent.schemas import ToolCall
    from logic import add_class_task
    add_class_task(data, title="CSE 3202", subject="AI", days=["fri"],
                   start_time="10:00", end_time="11:30")
    _mk(data, "Networking assignment", "2026-10-28", 120)
    ctx = {"settings": data["settings"], "now": NOW}
    # colliding to_time refused
    r1 = ft.execute_tool(data, ToolCall(tool="reschedule_task", args={
        "task_ref": "Networking assignment", "to_date": "2026-10-30",
        "to_time": "10:30"}, call_id="rt1"), ctx=ctx)
    assert not r1.ok and "collides" in (r1.error or ""), r1.message
    # clean move works and records history
    r2 = ft.execute_tool(data, ToolCall(tool="reschedule_task", args={
        "task_ref": "Networking assignment", "to_date": "2026-10-26"},
        call_id="rt2"), ctx=ctx)
    assert r2.ok
    t = TaskRepository(data).find_fuzzy("Networking assignment")
    assert t["date"] == "2026-10-26"
    hist = t.get("reschedule_history") or []
    assert hist and hist[-1]["to"] == "2026-10-26"


def test_reschedule_task_never_moves_classes(data, data_env):
    from focus_agent import tools as ft
    from focus_agent.schemas import ToolCall
    from logic import add_class_task
    add_class_task(data, title="CSE 3202", subject="AI", days=["fri"],
                   start_time="10:00", end_time="11:30")
    r = ft.execute_tool(data, ToolCall(tool="reschedule_task", args={
        "task_ref": "CSE 3202", "to_date": "2026-10-26"}, call_id="rc1"),
        ctx={"settings": data["settings"], "now": NOW})
    assert not r.ok and "class" in r.error.lower()
    sch = data["tasks"][0]["schedule"]
    assert sch["days"] == ["fri"], "routine untouched"


def test_get_daily_schedule_view(data, data_env):
    from focus_agent import tools as ft
    from focus_agent.schemas import ToolCall
    from logic import add_class_task
    add_class_task(data, title="CSE 3202", subject="AI", days=["fri"],
                   start_time="10:00", end_time="11:30")
    _mk(data, "Essay", "2026-10-23", 60)
    t = TaskRepository(data).find_fuzzy("Essay")
    t["planned"] = {"date": "2026-10-23", "start": "14:00", "end": "15:00",
                    "reason": "test"}
    from logic import save_data
    save_data(data)
    r = ft.execute_tool(data, ToolCall(tool="get_daily_schedule", args={
        "date": "2026-10-23"}, call_id="gd1"),
        ctx={"settings": data["settings"], "now": NOW})
    assert r.ok
    assert any(c["title"] == "Essay" for c in r.data["planned"])
    assert any(c["title"] == "CSE 3202" for c in r.data["classes"])
