"""Subject detection and ambiguous-subject handling (spec N.3, F)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from focus_agent import subjects as fs


def _data():
    return {
        "subjects": {"AI": {"notes": "", "documents": []},
                     "Database Systems": {"notes": "", "documents": []}},
        "tasks": [
            {"type": "class", "title": "CSE 3202", "subject": "AI",
             "schedule": {"days": ["fri"], "start": "10:00", "end": "11:30"}},
            {"type": "class", "title": "CSE 3521", "subject": "Database Systems",
             "schedule": {"days": ["sun"], "start": "14:00", "end": "15:30"}},
        ],
    }


def test_exact_match_is_auto():
    m = fs.match_subject("AI", _data())
    assert m and m["subject"] == "AI" and m["auto"]


def test_case_and_course_code_normalized():
    m = fs.match_subject("ai", _data())
    assert m and m["subject"] == "AI"
    m2 = fs.match_subject("cse 3521 database systems", _data())
    assert m2 and m2["subject"] == "Database Systems"


def test_fuzzy_match_confident():
    m = fs.match_subject("Databases", _data())
    assert m and m["subject"] == "Database Systems"


def test_routine_entries_count_as_subjects():
    d = {"subjects": {}, "tasks": _data()["tasks"]}
    m = fs.match_subject("CSE 3202", d)
    assert m and m["source"] == "routine"


def test_no_match_returns_none_not_a_guess():
    assert fs.match_subject("Quantum Underwater Basket", _data()) is None
    assert fs.match_subject("", _data()) is None
    assert fs.match_subject(None, _data()) is None


def test_empty_data_no_fabrication():
    assert fs.match_subject("AI", {"subjects": {}, "tasks": []}) is None


def test_propose_new_subject_blocks_when_similar_exists():
    allowed, reason = fs.propose_new_subject("Databse Systems", _data())  # typo'd
    assert not allowed, "similar existing subject must be confirmed, not duplicated"
    allowed2, _ = fs.propose_new_subject("Robotics", _data())
    assert allowed2


def test_routine_week_view_sorted():
    week = fs.subjects_for_routine(_data())
    assert week["fri"][0]["start"] == "10:00"
    assert week["sun"][0]["subject"] == "Database Systems"
