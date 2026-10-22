"""V1 regression: every pre-V2 behavior still works on the migrated model (spec N.12, L)."""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logic


def test_fresh_store_has_v1_skeleton(data):
    for key in ("tasks", "history", "settings"):
        assert key in data
    assert "xp" in data and "level" in data  # V1 keeps these at top level
    assert data["tasks"] == []


def test_task_lifecycle_awards_xp_and_history(data):
    logic.add_task_logic(data, "V1 essay", duration=60)
    t = data["tasks"][0]
    assert t["status"] == "pending" and t["duration"] == 60
    xp_before = data["xp"]
    logic.complete_task_logic(data, t["id"])
    assert data["xp"] > xp_before
    assert logic.get_task_by_id(data, t["id"])["status"] == "done"


def test_focus_logging_still_works(data):
    logic.log_focus_time(data, 25)
    today_key = datetime.now().strftime("%Y-%m-%d")
    assert data["history"][today_key]["focus_minutes"] >= 25


def test_focus_session_flow(data):
    logic.log_focus_session(data, 30 * 60, "focus")
    stats = logic.get_today_focus_stats(data)
    assert stats["sessions"] >= 1
    assert stats["total_seconds"] == 30 * 60


def test_levels_progress_monotonic(data):
    lvl0, xp0, _ = logic.get_level_progress(data)
    logic.add_xp(data, 500)
    lvl1, xp1, _ = logic.get_level_progress(data)
    assert lvl1 >= lvl0 and xp1 >= xp0


def test_delete_only_target(data):
    logic.add_task_logic(data, "Keep me", duration=30)
    logic.add_task_logic(data, "Delete me", duration=30)
    victim = next(t for t in data["tasks"] if t["title"] == "Delete me")
    logic.delete_task_logic(data, victim["id"])
    titles = [t["title"] for t in data["tasks"]]
    assert "Delete me" not in titles and "Keep me" in titles


def test_class_routine_and_today_view(data):
    logic.add_class_task(data, title="CSE 1001", subject="Intro",
                         days=["mon", "fri"], start_time="09:00", end_time="10:00")
    today_tasks = logic.get_today_tasks(data)
    # the class is recurring: visible in the today view on matching weekdays
    wk = datetime.now().strftime("%a").lower()
    if wk in ("mon", "fri"):
        assert any(t["title"] == "CSE 1001" for t in today_tasks)
    weekly = logic.get_weekly_class_tasks(data)
    # week view is day-keyed
    assert any(c["title"] == "CSE 1001"
               for day in weekly.values() for c in day)


def test_daily_automation_archives_done_not_deletes(data):
    logic.add_task_logic(data, "Finished yesterday", duration=30)
    t = data["tasks"][0]
    t["status"] = "done"
    t["completed_at"] = "2026-10-20T10:00:00"
    t["date"] = "2026-10-20"
    logic.process_daily_automation(data)
    all_known = data["tasks"] + data.get("archived_tasks", [])
    assert any(x["title"] == "Finished yesterday" for x in all_known), \
        "completed work must be archived, never silently deleted"


def test_streak_computation(data):
    from datetime import timedelta
    today = datetime.now().date()
    for i in range(3):
        key = (today - timedelta(days=i)).isoformat()
        data["history"].setdefault(key, {})["xp_gained"] = 10
    cur, best = logic.compute_streak(data)
    assert cur == 3


def test_subject_vault_operations(data):
    assert logic.add_subject(data, "Networks")
    assert "Networks" in data["subjects"]
    logic.rename_subject(data, "Networks", "Computer Networks")
    assert "Computer Networks" in data["subjects"] and "Networks" not in data["subjects"]


def test_habits_still_work(data):
    h = logic.add_habit(data, "Read 20 pages")
    logic.toggle_habit_today(data, h["id"])
    today_key = datetime.now().strftime("%Y-%m-%d")
    assert today_key in data["habits"][0]["history"]
    assert logic.get_habit_streak(data["habits"][0]) >= 1


def test_pomodoro_settings_persist(data):
    logic.update_pomodoro_settings(data, 25, 5, 15)
    pom = logic.get_pomodoro_settings(data)
    assert (pom["work"], pom["short_break"], pom["long_break"]) == (25, 5, 15)


def test_saved_file_is_valid_json_after_operations(data_env):
    data = logic.load_data()
    logic.add_task_logic(data, "Persist check", duration=30)
    with open(data_env["data_file"], encoding="utf-8") as f:
        on_disk = json.load(f)
    assert any(t["title"] == "Persist check" for t in on_disk["tasks"])
    # atomic write leaves no temp files behind
    leftovers = [p for p in os.listdir(os.path.dirname(data_env["data_file"]))
                 if p.endswith(".tmp")]
    assert not leftovers


def test_class_validation_rejects_bad_input():
    ok, err = logic.validate_class_input("X", "AI", ["funday"], "10:00", "11:00")
    assert not ok and err
    ok2, err2 = logic.validate_class_input("X", "AI", ["mon"], "11:00", "10:00")
    assert not ok2 and err2
    ok3, _ = logic.validate_class_input("Real Class", "AI", ["mon"], "10:00", "11:00")
    assert ok3
