"""Comprehensive 25+ Demo Scenarios & V2 Upgrade Tests (Banglish, Bangla, English, Typos, Hallucination Guards)."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from focus_agent import AgentController
from focus_agent import extractor as fe
from focus_agent import dates as fdates
from focus_agent import subjects as fsubjects
from conftest import MockProvider, OfflineProvider

REF_NOW = datetime(2026, 11, 5, 22, 0)  # Thursday, Nov 5, 2026


def _rich_student_data():
    return {
        "level": 2,
        "xp": 140,
        "subjects": {
            "Mathematics": {"notes": "", "documents": []},
            "Database Systems": {"notes": "", "documents": []},
            "Artificial Intelligence": {"notes": "", "documents": []},
            "Data Communication": {"notes": "", "documents": []},
            "Operating Systems": {"notes": "", "documents": []},
            "Software Engineering": {"notes": "", "documents": []},
            "Physics": {"notes": "", "documents": []},
        },
        "tasks": [
            {
                "id": "cls-math",
                "type": "class",
                "title": "MAT 2101 Calculus",
                "subject": "Mathematics",
                "schedule": {"days": ["sun", "tue"], "start": "09:00", "end": "10:30"},
            },
            {
                "id": "cls-dbms",
                "type": "class",
                "title": "CSE 3521 DBMS",
                "subject": "Database Systems",
                "schedule": {"days": ["mon", "wed"], "start": "11:00", "end": "12:30"},
            },
            {
                "id": "cls-ai",
                "type": "class",
                "title": "CSE 3202 AI",
                "subject": "Artificial Intelligence",
                "schedule": {"days": ["thu"], "start": "14:00", "end": "15:30"},
            },
        ],
        "goals": [],
        "history": {},
        "focus_sessions": {},
        "settings": {"timezone": "local", "study_hours": {"start": "09:00", "end": "22:00"}},
    }


# ==================== 25+ DEMO EXTRACTION SCENARIOS ====================

DEMO_EXTRACTION_CASES = [
    # 1. Exact user bug report case (Banglish + typo "assignmant" + "rat 8 tar modhe")
    (
        "amar kal math assignmant joma dite hobe rat 8 tar modhe",
        {"intent": "add_task", "due_date": "2026-11-06", "due_time": "20:00", "subject": "math", "title_contains": "assignment"},
    ),
    # 2. Banglish with duration & difficulty
    (
        "kal amar AI assignment ache, 2 ghonta lagbe, kothin",
        {"intent": "add_task", "due_date": "2026-11-06", "estimated_minutes": 120, "difficulty": 3, "subject": "ai"},
    ),
    # 3. Banglish day after tomorrow (porshu) + morning time
    (
        "porshu shokal 10 tay physics quiz ache, 45 minit lagbe",
        {"intent": "add_task", "due_date": "2026-11-07", "due_time": "10:00", "estimated_minutes": 45, "subject": "physics"},
    ),
    # 4. Banglish today night (ajke raate) + easy difficulty
    (
        "ajke raate database lab report korte hobe, 1 ghonta lagbe, sohoj",
        {"intent": "add_task", "due_date": "2026-11-05", "due_time": "20:00", "estimated_minutes": 60, "difficulty": 1},
    ),
    # 5. Banglish afternoon time (bikal 5 tay) + urgent
    (
        "agami kal bikal 5 tay networking project submission, khub joruri, 3 ghonta",
        {"intent": "add_task", "due_date": "2026-11-06", "due_time": "17:00", "estimated_minutes": 180, "importance": 3},
    ),
    # 6. Banglish weekday (shombar = Monday -> 2026-11-09)
    (
        "agami shombar OS presentation ache, der ghonta lagbe",
        {"intent": "add_task", "due_date": "2026-11-09", "estimated_minutes": 90},
    ),
    # 7. Banglish weekday (robibar = Sunday -> 2026-11-08)
    (
        "robibar dupur 2 tay software engineering exam",
        {"intent": "add_task", "due_date": "2026-11-08", "due_time": "14:00"},
    ),
    # 8. Bangla script (বাংলা) task creation with Bengali digits
    (
        "কাল আমার AI অ্যাসাইনমেন্ট আছে, ২ ঘণ্টা লাগবে, কঠিন",
        {"intent": "add_task", "due_date": "2026-11-06", "estimated_minutes": 120, "difficulty": 3},
    ),
    # 9. Bangla script with time ("রাত ৮টার মধ্যে")
    (
        "কাল রাত ৮টার মধ্যে গণিত অ্যাসাইনমেন্ট জমা দিতে হবে, ৯০ মিনিট লাগবে",
        {"intent": "add_task", "due_date": "2026-11-06", "due_time": "20:00", "estimated_minutes": 90},
    ),
    # 10. Bangla script day after tomorrow ("পরশু")
    (
        "পরশু সকালে ডাটাবেস পরীক্ষা আছে, ৩ ঘণ্টা লাগবে",
        {"intent": "add_task", "due_date": "2026-11-07", "due_time": "09:00", "estimated_minutes": 180},
    ),
    # 11. English with typo "tommorow" and "assinment"
    (
        "I have a math assinment due tommorow at 8pm, it will take 2 hours",
        {"intent": "add_task", "due_date": "2026-11-06", "due_time": "20:00", "estimated_minutes": 120, "subject": "math"},
    ),
    # 12. English Master Prompt example
    (
        "I have a Data Communication assignment due next Thursday, 3 hours, hard",
        {"intent": "add_task", "due_date": "2026-11-12", "estimated_minutes": 180, "difficulty": 3},
    ),
    # 13. Banglish Plan Day intent
    (
        "ajker plan koro",
        {"intent": "plan_day"},
    ),
    # 14. Bangla Plan Day intent
    (
        "আজকের প্ল্যান করো",
        {"intent": "plan_day"},
    ),
    # 15. Banglish Tomorrow Plan intent
    (
        "kalker routine koro",
        {"intent": "plan_day"},
    ),
    # 16. Banglish Goal creation
    (
        "ami machine learning shikhte chai",
        {"intent": "goal"},
    ),
    # 17. Bangla Goal creation
    (
        "আমি পাইথন শিখতে চাই",
        {"intent": "goal"},
    ),
    # 18. Banglish Complete Task
    (
        "math assignment shesh korechi",
        {"intent": "complete_task"},
    ),
    # 19. Bangla Complete Task
    (
        "ডাটাবেস অ্যাসাইনমেন্ট শেষ করেছি",
        {"intent": "complete_task"},
    ),
    # 20. Banglish Reschedule
    (
        "reschedule math assignment to shukrobar",
        {"intent": "reschedule", "due_date": "2026-11-06"},
    ),
    # 21. Banglish Query Next Class
    (
        "kokhon amar porer class?",
        {"intent": "query"},
    ),
    # 22. Bangla Query Today's work
    (
        "আজকে কী কী কাজ আছে?",
        {"intent": "query"},
    ),
    # 23. Banglish "N din por" relative date
    (
        "3 din por algorithm quiz ache, adha ghonta lagbe",
        {"intent": "add_task", "due_date": "2026-11-08", "estimated_minutes": 30},
    ),
    # 24. Banglish number words ("tin ghonta")
    (
        "kal compiler project ache, tin ghonta lagbe, khub kothin",
        {"intent": "add_task", "due_date": "2026-11-06", "estimated_minutes": 180, "difficulty": 3},
    ),
    # 25. English block time intent
    (
        "Don't schedule anything from 2pm to 4pm tomorrow, I am busy",
        {"intent": "block_time"},
    ),
]


@pytest.mark.parametrize("prompt,expect", DEMO_EXTRACTION_CASES)
def test_25_demo_extraction_scenarios(prompt, expect):
    res = fe.extract_deterministic(prompt, now=REF_NOW)
    assert res.intent == expect["intent"], f"Failed intent for: {prompt!r}"
    if expect.get("due_date"):
        assert res.tasks and res.tasks[0].due_date == expect["due_date"], f"Failed due_date for: {prompt!r}"
    if expect.get("due_time"):
        assert res.tasks and res.tasks[0].due_time == expect["due_time"], f"Failed due_time for: {prompt!r}"
    if expect.get("estimated_minutes"):
        assert res.tasks and res.tasks[0].estimated_minutes == expect["estimated_minutes"], f"Failed duration for: {prompt!r}"
    if expect.get("difficulty"):
        assert res.tasks and res.tasks[0].difficulty == expect["difficulty"], f"Failed difficulty for: {prompt!r}"
    if expect.get("importance"):
        assert res.tasks and res.tasks[0].importance == expect["importance"], f"Failed importance for: {prompt!r}"
    if expect.get("subject"):
        assert res.tasks and (res.tasks[0].subject or "").lower() == expect["subject"], f"Failed subject for: {prompt!r}"
    if expect.get("title_contains"):
        assert res.tasks and expect["title_contains"] in (res.tasks[0].title or "").lower()


def test_llm_hallucinated_database_subject_is_rejected(data_env):
    """Verify the exact bug reported by the user: when the LLM hallucinates
    'Complete Database Systems assignment' and 'Database Systems' for a Math prompt,
    the extractor overrides both with the user's true title, subject, date, and time!"""
    data = _rich_student_data()
    hallucinating_llm = MockProvider({
        "intent": "add_task",
        "question": "What is the due date for the assignment?",
        "tasks": [{
            "title": "Complete Database Systems assignment",
            "description": "amar kal math assignmant joma dite hobe rat 8 tar modhe",
            "subject": "Database Systems",
            "due_date": None,
            "due_time": "20:00",
        }],
    })
    ctrl = AgentController(data)
    reply = ctrl.handle(
        "amar kal math assignmant joma dite hobe rat 8 tar modhe",
        provider=hallucinating_llm,
        now=REF_NOW,
    )
    assert reply.status == "ok"
    assert "Database Systems" not in reply.message
    assert "Mathematics" in reply.message
    assert "2026-11-06" in reply.message
    assert "20:00" in reply.message
    # Question must be cleared since 'kal' resolved the due date!
    assert "❓" not in reply.message

    created = [t for t in data["tasks"] if t.get("type") == "task"]
    assert len(created) == 1
    t = created[0]
    assert t["title"] == "Math assignment"
    assert t["subject"] == "Mathematics"
    assert t["date"] == "2026-11-06"
    assert t["due_time"] == "20:00"


def test_subject_aliases_match_accurately():
    data = _rich_student_data()
    for mention, expected in [
        ("math", "Mathematics"),
        ("maths", "Mathematics"),
        ("গণিত", "Mathematics"),
        ("dbms", "Database Systems"),
        ("ai", "Artificial Intelligence"),
        ("networking", "Data Communication"),
        ("data comm", "Data Communication"),
        ("os", "Operating Systems"),
        ("se", "Software Engineering"),
        ("phy", "Physics"),
    ]:
        m = fsubjects.match_subject(mention, data)
        assert m is not None and m["subject"] == expected and m["auto"], f"Failed alias match for {mention!r}"


def test_evaluate_benchmark_summary_safe():
    import evaluate
    summary = evaluate.run_benchmark_summary()
    assert summary["passed"] == summary["total"]
    assert summary["pct"] == 100.0

