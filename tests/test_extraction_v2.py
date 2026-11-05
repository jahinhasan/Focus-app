"""Phase 3 extraction: spec dataset cases, class-attendance guard, ref cleanup."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from focus_agent import extractor as fe

NOW = datetime(2026, 10, 23, 14, 0)  # Friday


def test_class_attendance_carries_no_copied_duration():
    assert fe.looks_like_class_attendance("Attend networking class")
    assert fe.looks_like_class_attendance("go to the math class tomorrow")
    assert not fe.looks_like_class_attendance("study for the networking class")
    assert not fe.looks_like_class_attendance("Finish data communication assignment")


def test_clean_task_ref_variants():
    assert fe.clean_task_ref("Move my networking assignment to") == "networking assignment"
    assert fe.clean_task_ref("the unfinished database task") == "unfinished database task"
    assert fe.clean_task_ref("my essay") == "essay"
    assert fe.clean_task_ref("networking assignment") == "networking assignment"


def test_move_extraction_ref_is_clean():
    r = fe.extract_deterministic("Move my networking assignment to Friday", now=NOW)
    assert r.intent == "reschedule"
    assert r.tasks[0].task_ref == "networking assignment"
    assert r.tasks[0].due_date == "2026-10-30", "bare weekday = next occurrence"


def test_spec_case_three_hours_free_tomorrow_plans():
    r = fe.extract_deterministic("I have three hours free tomorrow. Plan my pending tasks.",
                                 now=NOW)
    assert r.intent == "plan_day"


def test_spec_case_analyze_productivity_is_query():
    r = fe.extract_deterministic("Analyze my productivity over the last seven days",
                                 now=NOW)
    assert r.intent in ("query", "chat")


def test_spec_case_imperative_complete():
    r = fe.extract_deterministic("complete the networking task", now=NOW)
    assert r.intent == "complete_task"
    assert r.tasks[0].task_ref == "networking task"


def test_need_to_title_cleanup():
    r = fe.extract_deterministic("I need to submit the statistics project", now=NOW)
    assert r.intent == "add_task"
    assert "statistics project" in (r.tasks[0].title or "").lower()
    assert "need to" not in (r.tasks[0].title or "").lower()


def test_llm_class_artifact_suppressed(monkeypatch):
    from conftest import MockProvider
    payload = {"intent": "add_task", "tasks": [
        {"title": "Complete Data Communication assignment", "due_date": "2026-11-12",
         "estimated_minutes": 180},
        {"title": "Attend networking class", "due_date": "2026-11-06",
         "estimated_minutes": 180},   # model copied the sibling estimate
    ]}
    r = fe.extract("I have a Data Communication assignment due next Thursday; "
                   "it will take 3 hours. I also have a networking class tomorrow.",
                   provider=MockProvider(payload), now=NOW)
    by_title = {t.title: t for t in r.tasks}
    assert by_title["Complete Data Communication assignment"].estimated_minutes == 180
    assert by_title["Attend networking class"].estimated_minutes is None, \
        "class attendance must not inherit a study duration"
