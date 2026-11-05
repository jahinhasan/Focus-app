"""Phase 3 tools: search, decomposition, subject detection, aliases, progress."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from focus_agent import tools as ft
from focus_agent.schemas import ToolCall
from conftest import NOW

CTX = {"settings": {"study_hours": {"start": "09:00", "end": "22:00"}}, "now": NOW}


_SEQ = {"n": 0}


def _run(data, name, args, call_id=None, confirm=None):
    _SEQ["n"] += 1
    call_id = call_id or f"tc-{_SEQ['n']}"
    return ft.execute_tool(data, ToolCall(tool=name, args=args, call_id=call_id),
                           ctx=CTX, confirm_callback=confirm)


def test_search_tasks_ranked_and_readonly(data, data_env):
    from logic import add_task_logic
    add_task_logic(data, "Networking assignment", deadline="2026-11-20", duration=60)
    add_task_logic(data, "Networking exam prep", duration=45)
    add_task_logic(data, "Cook dinner", duration=30)
    r = _run(data, "search_tasks", {"query": "networking"})
    assert r.ok and len(r.data["results"]) == 2
    scores = [x["score"] for x in r.data["results"]]
    assert scores == sorted(scores, reverse=True)
    assert all("Cook" not in x["title"] for x in r.data["results"])


def test_decompose_task_creates_ordered_subtasks(data, data_env):
    from logic import add_task_logic, get_task_by_id
    t = add_task_logic(data, "DBMS project", deadline="2026-11-20", duration=120)
    r = _run(data, "decompose_task", {"task_ref": "DBMS project",
                                      "subtasks": ["ER diagram", "Schema design",
                                                   "ER diagram"]})
    assert r.ok
    fresh = get_task_by_id(data, t["id"])
    titles = [s["title"] for s in fresh["subtasks"]]
    assert titles == ["ER diagram", "Schema design"], "duplicate step skipped"
    assert "1. ER diagram" in r.message


def test_decompose_task_requires_existing_task(data, data_env):
    r = _run(data, "decompose_task", {"task_ref": "ghost",
                                      "subtasks": ["a"]})
    assert not r.ok and "No task matching" in r.error


def test_detect_task_subject_readonly_with_confidence(sample_data):
    r = _run(sample_data, "detect_task_subject", {"mention": "AI homework chapter 3"})
    assert r.ok
    cands = r.data["candidates"]
    assert cands and cands[0]["subject"] == "AI"
    assert cands[0]["auto"] is True
    # read-only: no mutation
    tasks_before = len(sample_data["tasks"])
    _run(sample_data, "detect_task_subject", {"task_ref": "AI assignment"})
    assert len(sample_data["tasks"]) == tasks_before


def test_detect_task_subject_no_match_honest(data, data_env):
    from logic import add_subject
    add_subject(data, "Database Systems")
    r = _run(data, "detect_task_subject", {"mention": "bake a cake"})
    assert r.ok and r.data["verdict"].startswith("no match")


def test_update_subject_rename_and_keywords(data, data_env):
    from logic import add_subject, add_task_logic
    add_subject(data, "AI")
    add_task_logic(data, "Essay", subject="AI", duration=60)
    r = _run(data, "update_subject", {"subject": "AI", "new_name": "Artificial Intelligence",
                                      "keywords": ["ml", "ai"]})
    assert r.ok
    assert "Artificial Intelligence" in data["subjects"]
    assert data["tasks"][0]["subject"] == "Artificial Intelligence", "rename cascades"
    assert data["subjects"]["Artificial Intelligence"]["keywords"] == ["ml", "ai"]


def test_spec_aliases_registered_and_work(sample_data):
    for alias, target in (("get_class_routine", "get_routine"),
                          ("assign_task_subject", "assign_subject"),
                          ("get_goals", "list_goals"),
                          ("get_available_slots", "get_availability"),
                          ("get_productivity_statistics", "get_analytics")):
        assert alias in ft.REGISTRY and alias != target
    r = _run(sample_data, "get_class_routine", {"day": "fri"})
    assert r.ok and r.data["day"] == "fri"
    r2 = _run(sample_data, "get_goals", {})
    assert r2.ok and "goals" in r2.data


def test_decompose_goal_spreads_milestones(data, data_env):
    from focus_agent.goals import add_goal
    goal, err = add_goal(data, "Learn Python", None, "2027-01-31", None, [])
    assert not err
    r = _run(data, "decompose_goal", {"goal_ref": "Learn Python",
                                      "milestones": ["Syntax basics", "OOP", "Projects"]})
    assert r.ok
    g = next(g for g in data["goals"] if g["title"] == "Learn Python")
    assert len(g["milestones"]) == 3
    targets = [m["target_date"] for m in g["milestones"]]
    assert all(t for t in targets), "milestones get spread target dates"
    assert targets == sorted(targets), "milestones are ordered by date"


def test_track_goal_progress_math(data, data_env):
    from focus_agent.goals import add_goal, update_milestone
    from logic import add_task_logic, complete_task_logic
    goal, _ = add_goal(data, "Learn ML", None, "2027-02-01", None,
                       [{"title": "M1"}, {"title": "M2"}])
    add_task_logic(data, "ML task 1", duration=60, goal_id=None)
    # link the task manually
    data["tasks"][-1]["goal_id"] = goal["id"]
    g = next(g for g in data["goals"] if g["title"] == "Learn ML")
    update_milestone(data, g["id"], g["milestones"][0]["id"], done=True)
    complete_task_logic(data, data["tasks"][-1]["id"])
    r = _run(data, "track_goal_progress", {"goal_ref": "Learn ML"})
    assert r.ok
    p = r.data["progress"]
    assert p["milestones_done"] == 1 and p["milestones_total"] == 2
    assert p["linked_tasks_done"] == 1
    assert "on track" in r.message or "behind" in r.message


def test_estimate_task_duration_discloses_basis(data, data_env):
    from logic import add_task_logic
    add_task_logic(data, "Unknown task", duration=60)
    r = _run(data, "estimate_task_duration", {"task_ref": "Unknown task"})
    assert r.ok
    assert r.data["reliable"] is False, "cold start must be labeled a default"
    assert "no history" in r.data["basis"] or "default" in r.data["basis"]


def test_estimate_task_duration_learns_from_history(data, data_env):
    from logic import add_task_logic
    for i in range(4):
        t = add_task_logic(data, f"AI hw {i}", duration=60, subject="AI", difficulty=2)
        data["tasks"][-1]["actual_minutes"] = 120
        data["tasks"][-1]["status"] = "done"
        data["tasks"][-1]["completed_at"] = f"2026-10-{10+i}T10:00:00"
    t = add_task_logic(data, "AI hw new", duration=60, subject="AI", difficulty=2)
    r = _run(data, "estimate_task_duration", {"task_ref": "AI hw new"})
    assert r.ok and r.data["reliable"] is True
    assert r.data["minutes"] == 120, "learned 2x ratio applied"
    assert "median ratio 2.00x" in r.data["basis"]
