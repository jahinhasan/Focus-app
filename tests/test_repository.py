"""Repository contracts: validation boundaries, v4 stores, focus buckets (Phase 1)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from focus_agent.repository import (
    TaskRepository, SubjectRepository, ScheduleRepository, GoalRepository,
    FocusRepository, MemoryRepository, ValidationError,
)
from focus_agent.models import AgentTurnRecord, AgentPendingQuestion, AgentAction


def test_task_repo_create_get_update(data, data_env):
    repo = TaskRepository(data)
    t = repo.create("Write essay", deadline="2026-11-20", duration=90,
                    importance=3, difficulty=2, subtasks=["outline", "draft"])
    assert t["title"] == "Write essay" and t["importance"] == 3
    assert len(t["subtasks"] or []) == 2
    got = repo.get(t["id"])
    assert got and got["date"] == "2026-11-20"
    with pytest.raises(ValidationError):
        repo.update(t["id"], importance=9)
    assert repo.get(t["id"])["importance"] == 3


def test_task_repo_validation_guards(data, data_env):
    r = TaskRepository(data)
    with pytest.raises(ValidationError):
        r.create("")
    with pytest.raises(ValidationError):
        r.update("missing-id", title="nope")
    with pytest.raises(ValidationError):
        r.delete("missing-id")


def test_fuzzy_find_and_search(data, data_env):
    r = TaskRepository(data)
    r.create("Networking assignment", deadline="2022-01-01", duration=60)
    r.create("Networking exam prep", deadline="2022-01-02", duration=45)
    r.create("Other task", duration=30)
    hits = r.search("networking")
    titles = [h["task"]["title"] for h in hits]
    assert titles == ["Networking assignment", "Networking exam prep"]
    assert r.find_fuzzy("networking assignment")["title"] == "Networking assignment"


def test_schedule_blocks_crud(data, data_env):
    s = ScheduleRepository(data)
    b = s.create("Guard duty", start="10:00", end="12:00", days=["fri"])
    assert b["days"] == ["fri"]
    with pytest.raises(ValidationError):
        s.create("Bad block", start="12:00", end="10:00")
    s.update(b["id"], end="13:00")
    assert s.list()[0]["end"] == "13:00"
    s.delete(b["id"])
    assert s.list() == []


def test_goal_repo_milestone(data, data_env):
    g = GoalRepository(data)
    from focus_agent.goals import add_goal
    goal, err = add_goal(data, "Learn AI", None, "2026-12-01", None, [])
    assert not err
    ms = g.add_milestone(goal["id"], "Basics", target_date="2026-12-10")
    assert ms["target_date"] == "2026-12-10"


def test_focus_repo_writes_buckets_and_log(data, data_env):
    f = FocusRepository(data)
    rec = f.log_session("2026-11-05", 25, kind="focus", task_id="t-1",
                        started_hhmm="14:00")
    assert rec.minutes == 25
    assert f.hourly_focus("2026-11-06") == {}
    assert data["focus_session_log"][-1]["task_id"] == "t-1"
    assert "2026-11-05" in data["hourly_focus"]


def test_memory_repo_conversations_actions(data, data_env):
    mem = MemoryRepository(data)
    conv = mem.open_conversation()
    mem.append_turn(conv.id, AgentTurnRecord(role="user", content="hello", ts=1))
    mem.set_pending_question(conv.id, AgentPendingQuestion(
        question="When is it due?", intent="add_task", draft={"title": "essay"}))
    with open(data_env["data_file"], encoding="utf-8") as fh:
        reloaded = json.load(fh)
    pend = reloaded["agent_memory"]["conversations"][-1]["pending"]
    assert pend and pend["question"] == "When is it due?"
    mem.log_action(AgentAction(call_id="c1", tool="create_task", ok=True, ts=1))
    assert mem.recent_actions(5)[0]["tool"] == "create_task"
