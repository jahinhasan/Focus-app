"""Natural-language task extraction (spec N.1) and malformed LLM handling (N.4)."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from focus_agent import extractor as fe
from focus_agent.llm import BadResponse
from conftest import MockProvider, OfflineProvider, GarbageProvider, NOW


def test_spec_example_assignment_two_hours():
    r = fe.extract_deterministic(
        "Tomorrow submit my AI assignment; it will take about two hours", now=NOW)
    assert r.intent == "add_task"
    assert len(r.tasks) == 1
    t = r.tasks[0]
    assert t.due_date == "2026-10-24"
    assert t.estimated_minutes == 120
    assert "assignment" in t.title.lower()
    assert t.subject == "ai"


def test_spec_example_practice_tonight():
    r = fe.extract_deterministic("Add a 45-minute Python practice task for tonight", now=NOW)
    assert r.intent == "add_task"
    t = r.tasks[0]
    assert t.estimated_minutes == 45
    assert t.due_date == "2026-10-23"


def test_spec_example_exam_revision_plan():
    r = fe.extract_deterministic("I have an exam next Monday; prepare a revision plan", now=NOW)
    assert r.intent == "plan_day"


def test_spec_example_move_task():
    r = fe.extract_deterministic(
        "Move the unfinished database task to my next available study slot", now=NOW)
    assert r.intent == "reschedule"
    assert r.tasks and "database" in (r.tasks[0].task_ref or "")


def test_multiple_tasks_one_request():
    r = fe.extract_deterministic(
        "Add math homework; also create a physics reading task for tomorrow", now=NOW)
    assert r.intent == "add_task"
    assert len(r.tasks) == 2
    assert r.tasks[1].due_date == "2026-10-24"


def test_duration_word_forms():
    assert fe.extract_duration("about two hours") == (120, "two hours")
    assert fe.extract_duration("45 minutes")[0] == 45
    assert fe.extract_duration("45-minute session")[0] == 45
    assert fe.extract_duration("1.5 hours")[0] == 90
    assert fe.extract_duration("half an hour")[0] == 30
    assert fe.extract_duration("no time given") == (None, None)


def test_importance_and_priority_hints():
    imp, hint = fe.extract_importance("this is urgent")
    assert imp == 3 and hint == 90
    imp, hint = fe.extract_importance("no rush, whenever")
    assert imp == 1 and hint == 20


def test_deadline_sensitive_without_date_asks():
    r = fe.extract_deterministic("I need to submit the AI project", now=NOW)
    assert r.intent == "add_task"
    assert r.question and "due" in r.question.lower()


def test_backlog_task_without_date_is_valid():
    r = fe.extract_deterministic("Add a task to reorganize notes", now=NOW)
    assert r.intent == "add_task"
    assert r.tasks[0].due_date is None
    assert r.question is None  # not deadline-sensitive -> no nagging


def test_unknown_values_are_none_not_invented():
    r = fe.extract_deterministic("Add a task called weird-thing-xyz", now=NOW)
    t = r.tasks[0]
    assert t.due_date is None
    assert t.estimated_minutes is None
    assert t.importance is None
    assert t.difficulty is None


def test_intent_classification():
    assert fe.detect_intent("what should I do today")[0] == "plan_day"
    assert fe.detect_intent("plan my day")[0] == "plan_day"
    assert fe.detect_intent("how much XP do I have")[0] == "query"
    assert fe.detect_intent("hello")[0] == "chat"
    assert fe.detect_intent("delete the math task")[0] == "delete_task"
    assert fe.detect_intent("mark the essay as finished")[0] == "complete_task"
    assert fe.detect_intent("I want to learn robotics")[0] == "goal"


# ---------------- LLM extraction paths ----------------

def _llm_response():
    return {
        "intent": "add_task",
        "tasks": [{
            "title": "Submit AI assignment",
            "subject": "AI",
            "due_date": "2026-10-24",
            "estimated_minutes": 120,
            "importance": 3,
        }],
    }


def test_llm_extraction_validated():
    r = fe.extract("Tomorrow submit my AI assignment; it will take about two hours",
                   provider=MockProvider(_llm_response()), now=NOW)
    assert r.source == "llm"
    assert r.tasks[0].title == "Submit AI assignment"
    assert r.tasks[0].estimated_minutes == 120


def test_llm_malformed_output_falls_back():
    r = fe.extract("Add math homework", provider=GarbageProvider(), now=NOW)
    assert r.source == "local"
    assert r.tasks, "deterministic fallback must still extract the task"
    assert any("LLM" in w for w in r.warnings)


def test_llm_invalid_fields_dropped():
    bad = {
        "intent": "add_task",
        "tasks": [{"title": "Bad dates", "due_date": "not-a-date",
                   "estimated_minutes": 99999, "importance": 11}],
    }
    r = fe.extract("add a task", provider=MockProvider(bad), now=NOW)
    t = r.tasks[0]
    assert t.title == "Bad dates"
    assert t.due_date is None          # invalid -> None, never executed
    assert t.estimated_minutes is None
    assert t.importance is None
    assert r.warnings  # and the user learns why


def test_llm_offline_falls_back_gracefully():
    r = fe.extract("Add math homework", provider=OfflineProvider(), now=NOW)
    assert r.source == "local"
    assert r.tasks


def test_deterministic_date_wins_over_llm_conflict():
    # model misresolves "tonight" -> tomorrow; the keyword resolver must win
    bad = {"intent": "add_task", "tasks": [
        {"title": "Python practice", "due_date": "2026-10-24", "estimated_minutes": 45}]}
    r = fe.extract("Add a 45-minute Python practice task for tonight",
                   provider=MockProvider(bad), now=NOW)
    assert r.tasks[0].due_date == "2026-10-23"
    assert any("local resolver" in w for w in r.warnings)


def test_unknown_llm_intent_rescued_by_deterministic():
    # model invents an intent outside the schema ("move_task") -> "unknown";
    # the deterministic classifier must rescue the request
    bad = {"intent": "move_task", "tasks": [{"task_ref": "database"}]}
    r = fe.extract("Move the unfinished database task to my next available study slot",
                   provider=MockProvider(bad), now=NOW)
    assert r.intent == "reschedule"
    assert r.tasks and r.tasks[0].task_ref == "database"


def test_json_extraction_from_fences_and_prose():
    from focus_agent.llm import extract_json
    obj = extract_json('Sure! {"a": 1}\n```json\n{"b": {"c": 2}}\n```')
    assert obj["b"]["c"] == 2
    obj2 = extract_json('prefix text {"x": "with \\"escaped\\" quotes"} suffix')
    assert obj2["x"] == 'with "escaped" quotes'
    try:
        extract_json("no json at all")
        assert False, "expected BadResponse"
    except BadResponse:
        pass
    try:
        extract_json("")
        assert False, "expected BadResponse"
    except BadResponse:
        pass
