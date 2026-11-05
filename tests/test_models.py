"""Domain model contracts: validation, round-trips, v4 fields (Phase 1)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from focus_agent import models as m


def _task(**kw):
    base = {"id": "t-1", "title": "Essay", "date": "2026-11-10",
            "duration": 60, "importance": 3, "difficulty": 2}
    base.update(kw)
    return m.Task(**base)


def test_task_roundtrip_preserves_unknown_fields():
    raw = {"id": "t-9", "title": "Legacy task", "duration": 60,
           "legacy_field": "must survive"}
    inst = m.Task(**raw)
    out = inst.to_store()
    assert out["legacy_field"] == "must survive", "extra=allow must keep unknown keys"
    assert out["title"] == "Legacy task"


def test_task_rejects_bad_dates_and_importance():
    with pytest.raises(Exception):
        _task(date="10/11/2026")
    with pytest.raises(Exception):
        _task(importance=5)
    with pytest.raises(Exception):
        _task(duration=3)          # below ge=5
    with pytest.raises(Exception):
        _task(due_time="25:00")


def test_task_status_and_type_literales():
    with pytest.raises(Exception):
        _task(status="deleted")     # not in the allowed set
    with pytest.raises(Exception):
        _task(type="personal")      # legacy type was normalized on load


def test_schedule_block_ordering_and_days():
    b = m.ScheduleBlock(id="b1", title="Math class", start="10:00", end="12:00",
                        days=["fri"])
    assert b.to_store()["days"] == ["fri"]
    with pytest.raises(Exception):
        m.ScheduleBlock(id="b2", title="x", start="12:00", end="10:00")
    with pytest.raises(Exception):
        m.ScheduleBlock(id="b3", title="x", start="10:00", end="12:00",
                        days=["funday"])


def test_goal_milestone_validation():
    g = m.Goal(id="g1", title="Learn AI", milestones=[
        {"id": "ms1", "title": "Basics", "target_date": "2026-12-01"}])
    assert g.milestones[0].done is False
    with pytest.raises(Exception):
        m.Goal(id="g2", title="x", milestones=[{"id": "ms2", "title": "y",
                                                "target_date": "soon"}])


def test_agent_memory_and_action_models():
    a = m.AgentAction(call_id="c1", tool="create_task", ok=True, ts=1,
                      summary="ok", verified=True)
    conv = m.AgentConversation(id="cv1", started_at=1, turns=[
        {"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}])
    assert conv.turns[0].role == "user"
    with pytest.raises(Exception):
        m.AgentAction(call_id="c2", tool="x", ok="not-a-bool", ts=1)


def test_focus_session_record():
    r = m.FocusSessionRecord(date="2026-11-05", minutes=25, kind="focus",
                             task_id="t-1", started_hhmm="14:00")
    assert r.started_hhmm == "14:00"
    with pytest.raises(Exception):
        m.FocusSessionRecord(date="bad", minutes=25)
    with pytest.raises(Exception):
        m.FocusSessionRecord(date="2026-11-05", minutes=0)


def test_extra_allow_keeps_nested_passthrough():
    raw = {"id": "t-1", "title": "X", "duration": 30,
           "subtasks": [{"title": "a", "done": False, "extra": 1}]}
    inst = m.Task(**raw)
    assert inst.to_store()["subtasks"][0].get("extra") == 1, \
        "subtask extras survive the model round-trip"
