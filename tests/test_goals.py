"""Goals, milestones, progress, roadmaps (spec N.10, E)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from focus_agent import goals as fg


def test_goal_lifecycle_and_persistence(data, data_env):
    import logic
    goal, err = fg.add_goal(data, "Learn machine learning", description="Semester project",
                            target_date="2026-12-15", milestones=[
                                {"title": "Linear algebra refresher"},
                                {"title": "First classifier"}])
    assert not err and goal["id"]
    reloaded = logic.load_data()
    assert reloaded["goals"] and reloaded["goals"][0]["title"] == "Learn machine learning"
    assert len(reloaded["goals"][0]["milestones"]) == 2

    ok, err = fg.update_goal(reloaded, goal["id"], status="paused")
    assert ok
    assert fg.get_goal(reloaded, goal["id"])["status"] == "paused"
    fg.update_goal(reloaded, goal["id"], status="active")


def test_milestone_check_updates_progress(data):
    goal, _ = fg.add_goal(data, "Thesis", milestones=[
        {"title": "Outline"}, {"title": "Chapter 1"}, {"title": "Chapter 2"}])
    fg.update_milestone(data, goal["id"], goal["milestones"][0]["id"], done=True)
    prog = fg.goal_progress(data, goal)
    assert prog["percent"] > 0
    assert not prog["overdue"]
    for ms in goal["milestones"][1:]:
        fg.update_milestone(data, goal["id"], ms["id"], done=True)
    assert fg.goal_progress(data, goal)["percent"] == 100


def test_overdue_goal_detected(data):
    goal, _ = fg.add_goal(data, "Old goal", target_date="2026-01-01",
                          milestones=[{"title": "Never done"}])
    prog = fg.goal_progress(data, goal)
    assert prog["overdue"]


def test_linked_tasks_count_toward_progress(data):
    import logic
    goal, _ = fg.add_goal(data, "Robotics", milestones=[{"title": "Build chassis"}])
    task = logic.add_task_logic(data, "Buy motors", duration=30, goal_id=goal["id"])
    task["status"] = "done"
    logic.complete_task_logic(data, task["id"])
    prog = fg.goal_progress(data, goal)
    assert prog["percent"] >= 25  # milestone 0% + done linked task blended


def test_delete_goal_unlinks_but_keeps_tasks(data):
    import logic
    goal, _ = fg.add_goal(data, "Temp goal")
    task = logic.add_task_logic(data, "Orphan-to-be", duration=30, goal_id=goal["id"])
    fg.delete_goal(data, goal["id"])
    assert fg.get_goal(data, goal["id"]) is None
    t = logic.get_task_by_id(data, task["id"])
    assert t is not None and t.get("goal_id") is None


def test_roadmap_draft_is_labeled_assumptions():
    draft, err = fg.generate_roadmap_draft("Learn Vulkan graphics", weeks=6,
                                           hours_per_week=5)
    assert not err
    assert draft["goal_title"] == "Learn Vulkan graphics"
    assert draft["assumptions"]  # discloses that it assumed the weekly load
    assert len(draft["milestones"]) >= 4
    for m in draft["milestones"]:
        assert m["title"] and m["target_date"] and m["estimated_minutes"] > 0


def test_goal_input_validation(data):
    goal, err = fg.add_goal(data, "")
    assert goal is None and err  # empty title refused, not created
    goal2, _ = fg.add_goal(data, "Cap", milestones=[{"title": f"m{i}"} for i in range(31)])
    assert len(goal2["milestones"]) == 30  # capped, not an error
