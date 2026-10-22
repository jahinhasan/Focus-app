"""Tool schema validation, permissions/confirmation, idempotency, CRUD (spec N.5, N.6)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from focus_agent import tools as ft
from focus_agent.schemas import ToolCall
from conftest import NOW

CTX = {"settings": {"study_hours": {"start": "09:00", "end": "22:00"}}, "now": NOW}


def _run(data, tool_name, args, call_id="t1", confirm=None):
    return ft.execute_tool(data, ToolCall(tool=tool_name, args=args, call_id=call_id),
                           ctx=CTX, confirm_callback=confirm)


def test_task_crud_and_persistence(data, data_env):
    import logic
    r = _run(data, "create_task", {"title": "Write essay", "due_date": "2026-10-25",
                                   "duration_minutes": 90, "importance": 3}, call_id="c1")
    assert r.ok and r.data["task_id"]
    reloaded = logic.load_data()
    assert any(t["title"] == "Write essay" for t in reloaded["tasks"])
    t = reloaded["tasks"][0]
    assert t["duration"] == 90 and t["importance"] == 3 and t["date"] == "2026-10-25"

    r2 = _run(reloaded, "update_task", {"task_ref": "essay", "due_date": "2026-10-26"}, call_id="c2")
    assert r2.ok
    t2 = logic.get_task_by_id(reloaded, t["id"])
    assert t2["date"] == "2026-10-26"

    r3 = _run(reloaded, "complete_task", {"task_ref": "essay"}, call_id="c3")
    assert r3.ok
    t3 = logic.get_task_by_id(reloaded, t["id"])
    assert t3["status"] == "done" and t3["completed_at"]

    r4 = _run(reloaded, "reopen_task", {"task_ref": "essay"}, call_id="c4")
    assert r4.ok and logic.get_task_by_id(reloaded, t["id"])["status"] == "pending"


def test_schema_validation_rejects_bad_args(data):
    r = _run(data, "create_task", {"title": ""}, call_id="b1")
    assert not r.ok and "non-empty" in (r.error or "")
    r2 = _run(data, "create_task", {"title": "x", "due_date": "25-12-2026"}, call_id="b2")
    assert not r2.ok and "YYYY-MM-DD" in (r2.error or "")
    r3 = _run(data, "create_task", {"title": "x", "evil": "arg"}, call_id="b3")
    assert not r3.ok and "unknown argument" in (r3.error or "")
    r4 = _run(data, "create_task", {"title": "x", "duration_minutes": 5000}, call_id="b4")
    assert not r4.ok


def test_unknown_tool_rejected(data):
    r = _run(data, "run_shell_command", {"cmd": "rm -rf /"}, call_id="u1")
    assert not r.ok and "Unknown tool" in (r.error or "")
    r2 = _run(data, "execute_sql", {"query": "DROP TABLE tasks"}, call_id="u2")
    assert not r2.ok


def test_destructive_requires_confirmation(data):
    import logic
    logic.add_task_logic(data, "Precious task", duration=30)
    victim_id = data["tasks"][0]["id"]
    # no callback -> refuses to act
    r = _run(data, "delete_task", {"task_ref": "Precious"}, call_id="d1", confirm=None)
    assert not r.ok
    assert logic.get_task_by_id(data, victim_id) is not None
    # user declines -> nothing deleted
    r2 = _run(data, "delete_task", {"task_ref": "Precious"}, call_id="d2", confirm=lambda q: False)
    assert not r2.ok
    # user approves -> deleted
    r3 = _run(data, "delete_task", {"task_ref": "Precious"}, call_id="d3", confirm=lambda q: True)
    assert r3.ok and r3.confirmed
    assert not logic.get_task_by_id(data, victim_id)


def test_idempotency_on_retried_call(data):
    args = {"title": "Once only", "due_date": "2026-10-26"}
    r1 = _run(data, "create_task", args, call_id="same-id")
    assert r1.ok
    r2 = _run(data, "create_task", args, call_id="same-id")
    assert r2.ok and r2.data.get("duplicate")
    titles = [t["title"] for t in data["tasks"]]
    assert titles.count("Once only") == 1


def test_failed_execution_releases_call_id(data):
    # bad args with a call id -> retrying the same id later must work
    r1 = _run(data, "create_task", {"due_date": "bad"}, call_id="retry-me")
    assert not r1.ok
    r2 = _run(data, "create_task", {"title": "Fine now"}, call_id="retry-me")
    assert r2.ok


def test_subject_ambiguity_not_silently_assigned(sample_data):
    r = _run(sample_data, "create_task",
             {"title": "Chapter summary", "subject": "Databases"}, call_id="s1")
    assert r.ok
    assert r.data.get("subject") is None, "uncertain match must not auto-assign"
    assert "subject_note" in r.data

    r2 = _run(sample_data, "create_task",
              {"title": "Chapter summary", "subject": "AI"}, call_id="s2")
    assert r2.ok and r2.data.get("subject") == "AI"  # confident match assigns

    r3 = _run(sample_data, "assign_subject",
              {"task_ref": "Chapter summary", "subject": "Totally Unknown"}, call_id="s3")
    assert not r3.ok  # never fabricates a subject


def test_create_subject_confirmed(data):
    r = _run(data, "create_subject", {"name": "Robotics"}, call_id="cs1",
             confirm=lambda q: True)
    assert r.ok and "Robotics" in data.get("subjects", {})
    r2 = _run(data, "create_subject", {"name": "Vision"}, call_id="cs2", confirm=None)
    assert not r2.ok  # no confirmation -> no creation


def test_fuzzy_task_ref_resolution(data):
    import logic
    logic.add_task_logic(data, "Finish database normalization worksheet", duration=45)
    r = _run(data, "get_task", {"task_ref": "normalization"}, call_id="f1")
    assert r.ok and "database" in r.data["task"]["title"].lower()
    r2 = _run(data, "get_task", {"task_ref": "nonexistent thing"}, call_id="f2")
    assert not r2.ok


def test_plan_tool_needs_confirmation_to_commit(sample_data):
    r = _run(sample_data, "generate_daily_plan", {"commit": True}, call_id="p1",
             confirm=None)
    assert not r.ok  # commit=True requires confirmation
    r2 = _run(sample_data, "generate_daily_plan", {"commit": True}, call_id="p2",
              confirm=lambda q: True)
    assert r2.ok and r2.data["committed"]


def test_analytics_and_report_tools(data):
    import logic
    logic.add_task_logic(data, "Timed task", duration=60)
    t = data["tasks"][0]
    t["status"] = "done"
    t["actual_minutes"] = 90
    t["completed_at"] = "2026-10-23T10:00:00"
    r = _run(data, "get_analytics", {}, call_id="a1")
    assert r.ok and r.data["estimation"]["n"] == 1
    r2 = _run(data, "generate_report", {}, call_id="a2")
    assert r2.ok and r2.data["recommendations"]


def test_record_focus_time(data):
    import logic
    logic.add_task_logic(data, "Timer task", duration=45)
    r = _run(data, "record_focus_time", {"task_ref": "Timer task", "minutes": 52}, call_id="rf1")
    assert r.ok and data["tasks"][0]["actual_minutes"] == 52
    r2 = _run(data, "record_focus_time", {"task_ref": "Timer task", "minutes": -5}, call_id="rf2")
    assert not r2.ok


def test_tool_catalog_complete():
    names = {t["name"] for t in ft.list_tools()}
    required = {"list_tasks", "get_task", "create_task", "update_task", "complete_task",
                "reopen_task", "delete_task", "add_subtask", "list_subjects",
                "create_subject", "assign_subject", "get_routine", "add_class",
                "get_availability", "generate_daily_plan", "explain_priorities",
                "reschedule_day", "list_goals", "create_goal", "update_goal",
                "add_milestone", "complete_milestone", "get_focus_history",
                "get_analytics", "record_focus_time", "generate_report"}
    assert required <= names, f"missing tools: {required - names}"
