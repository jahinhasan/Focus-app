#!/usr/bin/env python3
"""Reproducible evaluation for the Focus To-Do Agent (spec O).

Measures - on fixed benchmarks, no fabricated numbers:
  1. NL task extraction accuracy (deterministic parser, and live LLM with --live)
  2. Subject assignment accuracy (incl. refusal to guess)
  3. Schedule feasibility (no overlaps, classes respected, no past slots,
     every task accounted for)
  4. Deadline handling (asks instead of guessing on deadline-sensitive tasks)
  5. Tool-action success on a scripted scenario (validation, permissions,
     idempotency)
  6. Estimation error against synthetic history with a KNOWN true ratio

Usage:
  .venv/bin/python evaluate.py            # deterministic (no LLM required)
  .venv/bin/python evaluate.py --live     # also runs extraction through Ollama
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from focus_agent import extractor as fextract
from focus_agent import scheduler as fsched
from focus_agent import subjects as fsubjects
from focus_agent import estimator as fest
from focus_agent import tools as ftools
from focus_agent.schemas import ToolCall

NOW = datetime(2026, 10, 23, 14, 0)  # fixed reference: a Friday
SETTINGS = {"study_hours": {"start": "09:00", "end": "22:00"},
            "break_minutes": 10, "timezone": "local"}

results = []


def record(area, name, ok, detail=""):
    results.append({"area": area, "case": name, "pass": bool(ok), "detail": detail})


# ---------------- 1. extraction benchmark ----------------

EXTRACTION_CASES = [
    ("Tomorrow submit my AI assignment; it will take about two hours",
     {"due_date": "2026-10-24", "estimated_minutes": 120}),
    ("Add a 45-minute Python practice task for tonight",
     {"due_date": "2026-10-23", "estimated_minutes": 45}),
    ("I have an exam next Monday; prepare a revision plan",
     {"intent": "plan_day"}),
    ("Move the unfinished database task to my next available study slot",
     {"intent": "reschedule", "task_ref": "database"}),
    ("Add math homework; also create a physics reading task for tomorrow",
     {"n_tasks": 2, "any_due": "2026-10-24"}),
    ("This is urgent - finish the lab report by wednesday, around 2 hours",
     {"due_date": "2026-10-28", "estimated_minutes": 120}),
    ("Add a task to reorganize my notes",  # backlog: valid, no date invented
     {"due_date": None, "estimated_minutes": None}),
]

DEADLINE_SENSITIVE_CASES = [
    "I need to submit the AI project",
    "Finish the scholarship application",
    "Register for the workshop",
]


def run_extraction(live_provider=None):
    for text, expect in EXTRACTION_CASES:
        if live_provider is not None:
            r = fextract.extract(text, provider=live_provider, now=NOW, settings=SETTINGS,
                                 subject_names=["AI", "Database Systems"])
        else:
            r = fextract.extract_deterministic(text, now=NOW, settings=SETTINGS)
        name = text[:46] + ("..." if len(text) > 46 else "")
        detail = (f"intent={r.intent} n={len(r.tasks)}"
                  + (f" [LLM:{r.source}]" if live_provider else ""))
        ok = True
        if "intent" in expect:
            ok &= r.intent == expect["intent"]
        if "n_tasks" in expect:
            ok &= len(r.tasks) == expect["n_tasks"]
            if expect.get("any_due"):
                ok &= any(t.due_date == expect["any_due"] for t in r.tasks)
                detail += f" dues={[t.due_date for t in r.tasks]}"
        if r.tasks:
            t = r.tasks[0]
            if "due_date" in expect:
                ok &= t.due_date == expect["due_date"]
                detail += f" due={t.due_date}"
            if "estimated_minutes" in expect:
                ok &= t.estimated_minutes == expect["estimated_minutes"]
                detail += f" est={t.estimated_minutes}"
            if "task_ref" in expect:
                ok &= bool(t.task_ref) and expect["task_ref"] in (t.task_ref or "").lower()
        record("extraction", name, ok, detail)

    for text in DEADLINE_SENSITIVE_CASES:
        r = fextract.extract_deterministic(text, now=NOW, settings=SETTINGS)
        asked = bool(r.question) and "?" in r.question
        no_guess = all(not t.due_date for t in r.tasks)
        record("deadline handling", text[:40], asked and no_guess,
               f"question={bool(r.question)} date_left_null={no_guess}")


def run_subject_assignment():
    data = {"subjects": {"AI": {}, "Database Systems": {}}, "tasks": [
        {"type": "class", "title": "CSE 3202", "subject": "AI",
         "schedule": {"days": ["fri"], "start": "10:00", "end": "11:30"}}]}
    cases = [
        ("AI", "AI", True),
        ("ai", "AI", True),
        ("Databases", "Database Systems", True),      # fuzzy match
        ("CSE 3202", "AI", True),                      # via class routine
        ("Quantum Underwater Basket", None, False),    # must refuse to guess
    ]
    for mention, expected, should_match in cases:
        m = fsubjects.match_subject(mention, data)
        if should_match:
            ok = m is not None and m["subject"] == expected
        else:
            ok = m is None
        record("subject assignment", mention, ok,
               f"matched={m['subject'] if m else None} conf={m['confidence'] if m else '-'}")


# ---------------- 3. schedule feasibility ----------------

def _mk_store():
    import logic
    tmp = tempfile.mkdtemp(prefix="focus-eval-")
    logic.DATA_FILE = os.path.join(tmp, "data.json")
    data = logic.load_data()
    logic.add_subject(data, "AI")
    logic.add_class_task(data, title="CSE 3202", subject="AI", days=["fri"],
                         start_time="10:00", end_time="11:30")
    logic.add_task_logic(data, "AI assignment", deadline="2026-10-24", duration=120,
                         subject="AI", importance=3)
    logic.add_task_logic(data, "Python practice", deadline="2026-10-23", duration=45)
    logic.add_task_logic(data, "Database reading", deadline="2026-10-25", duration=60)
    logic.add_task_logic(data, "Marathon cleanup", deadline="2026-10-26", duration=200)
    return data


def run_schedule_feasibility():
    data = _mk_store()
    for label, date_str, now in [("today (past clipped)", "2026-10-23", NOW),
                                 ("future day", "2026-10-26",
                                  datetime(2026, 10, 26, 8, 0))]:
        plan = fsched.generate_day_plan(data, date_str, settings=SETTINGS, now=now)
        slots = sorted(plan.slots, key=lambda s: s.start)
        no_overlap = all(a.end <= b.start for a, b in zip(slots, slots[1:]))
        valid = all(s.end > s.start for s in slots)
        # Friday class 10:00-11:30 must stay free
        class_free = True
        if datetime.fromisoformat(date_str).weekday() == 4:
            class_free = not any(s.start < "11:30" and s.end > "10:00" for s in slots)
        accounted = (len({s.task_id for s in slots} |
                         {u["task_id"] for u in plan.unscheduled}) >=
                     len({t["id"] for t in data["tasks"] if t.get("type") != "class"}))
        record("schedule", f"{label}: no overlaps", no_overlap,
               f"{len(slots)} slots")
        record("schedule", f"{label}: valid intervals", valid)
        record("schedule", f"{label}: class time respected", class_free)
        record("schedule", f"{label}: no task silently dropped", accounted,
               f"{len(plan.unscheduled)} explained as unscheduled")


# ---------------- 5. tool-action scenario ----------------

def run_tool_scenario():
    data = _mk_store()
    ctx = {"settings": SETTINGS, "now": NOW}
    seq = [
        ("list_tasks", {}, None, True),
        ("create_task", {"title": "Eval task", "due_date": "2026-10-27",
                         "duration_minutes": 60}, None, True),
        ("create_task", {"title": "", }, None, False),                    # invalid
        ("create_task", {"title": "X", "due_date": "27-10-2026"}, None, False),  # bad date
        ("get_task", {"task_ref": "eval"}, None, True),
        ("delete_task", {"task_ref": "Eval task"}, None, False),          # needs confirm
        ("delete_task", {"task_ref": "Eval task"}, lambda q: False, False),  # declined
        ("delete_task", {"task_ref": "Eval task"}, lambda q: True, True),    # approved
        ("complete_task", {"task_ref": "Python practice"}, None, True),
        ("generate_daily_plan", {"commit": True}, None, False),           # needs confirm
        ("generate_daily_plan", {"commit": True}, lambda q: True, True),
    ]
    n = 0
    for tool, args, confirm, expect_ok in seq:
        n += 1
        r = ftools.execute_tool(data, ToolCall(tool=tool, args=args, call_id=f"eval-{n}"),
                                ctx=ctx, confirm_callback=confirm)
        ok = r.ok == expect_ok
        record("tool actions", f"{tool} {json.dumps(args)[:30]}", ok,
               (r.message or r.error or "")[:70])


# ---------------- 6. estimation error ----------------

def run_estimation():
    import logic
    data = logic.load_data()

    # TRUE cold start first, before any history exists: honest default
    logic.add_task_logic(data, "Brand new kind of task", duration=60, difficulty=1)
    cold = fest.estimate_minutes(data, data["tasks"][-1])
    record("estimation", "cold start uses disclosed default",
           not cold["reliable"] and cold["samples"] == 0,
           f"predicted={cold['minutes']} basis={cold['basis']}")

    # synthetic history with a KNOWN true pattern: AI tasks always take 2x estimate
    for i in range(4):
        logic.add_task_logic(data, f"AI hw {i}", duration=60, subject="AI")
        t = data["tasks"][-1]
        t["status"], t["actual_minutes"] = "done", 120
        t["completed_at"] = f"2026-10-{10 + i:02d}T09:00:00"
        t["created_at"] = f"2026-10-{10 + i:02d}"
    logic.add_task_logic(data, "AI essay", duration=60, subject="AI")
    info = fest.estimate_minutes(data, data["tasks"][-1])
    record("estimation", "learns 2x AI pattern (truth=120min)",
           info["minutes"] == 120 and info["reliable"],
           f"predicted={info['minutes']} basis={info['basis']}")

    # known difficulty group generalizes when the subject is new to the agent
    logic.add_task_logic(data, "New subject task", duration=60, difficulty=2)
    diff_based = fest.estimate_minutes(data, data["tasks"][-1])
    record("estimation", "difficulty group generalizes (truth=120min)",
           diff_based["minutes"] == 120 and diff_based["reliable"],
           f"predicted={diff_based['minutes']} basis={diff_based['basis']}")

    # leakage guard: future observations must not affect a past prediction
    for i in range(3):
        logic.add_task_logic(data, f"Future AI {i}", duration=60, subject="AI")
        t = data["tasks"][-1]
        t["status"], t["actual_minutes"] = "done", 300
        t["completed_at"] = "2026-11-01T09:00:00"
        t["created_at"] = "2026-11-01"
    logic.add_task_logic(data, "Past AI task", duration=60, subject="AI")
    past = data["tasks"][-1]
    past["created_at"] = "2026-10-01"
    info2 = fest.estimate_minutes(data, past, ref_created_at="2026-10-20")
    record("estimation", "no leakage from future data", info2["minutes"] != 300,
           f"predicted={info2['minutes']}")


# ---------------- main ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="also run extraction through the configured Ollama model")
    args = ap.parse_args()

    run_extraction()
    run_subject_assignment()
    run_schedule_feasibility()
    run_tool_scenario()
    run_estimation()

    if args.live:
        from focus_agent.llm import OllamaProvider
        p = OllamaProvider(timeout=90)
        ok, detail = p.status()
        if ok:
            t0 = datetime.now()
            run_extraction(live_provider=p)
            dt = (datetime.now() - t0).total_seconds()
            print(f"(live LLM pass: {detail}, {dt:.1f}s total)")
        else:
            print(f"(live pass skipped: {detail})")

    by_area = {}
    for r in results:
        by_area.setdefault(r["area"], []).append(r)

    print("\n" + "=" * 74)
    print("FOCUS AGENT EVALUATION - measured results (no numbers are hand-written)")
    print("=" * 74)
    total_pass = total = 0
    for area, items in by_area.items():
        p = sum(1 for i in items if i["pass"])
        total_pass += p
        total += len(items)
        print(f"\n{area.upper()}  {p}/{len(items)} ({100 * p / len(items):.0f}%)")
        for i in items:
            mark = "PASS" if i["pass"] else "FAIL"
            print(f"  [{mark}] {i['case']:<52} {i['detail']}")
    print("\n" + "-" * 74)
    print(f"OVERALL: {total_pass}/{total} ({100 * total_pass / total:.0f}%)")
    return 0 if total_pass == total else 1


if __name__ == "__main__":
    sys.exit(main())
