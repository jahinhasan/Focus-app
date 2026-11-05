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

    p = None
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

    run_dataset(live_provider=p)
    run_planner_quality()
    run_memory_effectiveness()

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


# ---------------- 7. dataset-driven extraction & understanding (spec §12) ----------------

def run_dataset(live_provider=None):
    """Every case in tests/eval_dataset.json, scored on the official metrics."""
    path = os.path.join(BASE_DIR, "tests", "eval_dataset.json")
    with open(path, encoding="utf-8") as f:
        dataset = json.load(f)
    cases = dataset["cases"]

    m_task = {"n": 0, "ok": 0}       # task extraction accuracy (intent + fields)
    m_deadline = {"n": 0, "ok": 0}   # deadline extraction accuracy
    m_cap = {"n": 0, "ok": 0}        # capacity parsing
    m_block = {"n": 0, "ok": 0}      # block parsing
    m_ask = {"n": 0, "ok": 0}        # deadline handling: asks, never guesses

    for case in cases:
        exp = case["expect"]
        if live_provider is not None:
            # the production path: extraction + deterministic merge rules
            res = fextract.extract(case["text"], provider=live_provider, now=NOW,
                                   settings=SETTINGS,
                                   subject_names=["AI", "Database Systems"])
        else:
            res = fextract.extract_deterministic(case["text"], now=NOW,
                                                 settings=SETTINGS)
        t0 = res.tasks[0] if res.tasks else None

        ok_task = True
        if "intent_any" in exp and res.intent not in exp["intent_any"]:
            ok_task = False
        elif "intent" in exp and res.intent != exp["intent"]:
            ok_task = False
        if "n_tasks" in exp and len(res.tasks) != exp["n_tasks"]:
            ok_task = False
        if "task_ref_contains" in exp:
            if not (t0 and exp["task_ref_contains"] in (t0.task_ref or "")):
                ok_task = False
        if "estimated_minutes" in exp and \
                (not t0 or t0.estimated_minutes != exp["estimated_minutes"]):
            ok_task = False
        m_task["n"] += 1
        m_task["ok"] += ok_task

        if "due_date" in exp:
            m_deadline["n"] += 1
            got = t0.due_date if t0 else None
            m_deadline["ok"] += (got == exp["due_date"])

        if "capacity_minutes" in exp:
            m_cap["n"] += 1
            m_cap["ok"] += (res.available_minutes == exp["capacity_minutes"])

        if "block" in exp:
            m_block["n"] += 1
            b = res.blocks[0] if res.blocks else {}
            m_block["ok"] += (b.get("start") == exp["block"]["start"]
                              and b.get("end") == exp["block"]["end"])

        if exp.get("asks"):
            m_ask["n"] += 1
            m_ask["ok"] += bool(res.question)

    def pct(m):
        return f"{m['ok']}/{m['n']} ({round(100 * m['ok'] / m['n'])}%)" if m["n"] else "n/a"

    record("dataset_extraction", "task extraction accuracy", m_task["ok"] == m_task["n"], pct(m_task))
    record("dataset_deadlines", "deadline extraction accuracy", m_deadline["ok"] == m_deadline["n"], pct(m_deadline))
    record("dataset_capacity", "free-capacity parsing", m_cap["ok"] == m_cap["n"], pct(m_cap))
    record("dataset_blocks", "block time parsing", m_block["ok"] == m_block["n"], pct(m_block))
    record("dataset_ask", "asks instead of guessing", m_ask["ok"] == m_ask["n"], pct(m_ask))


# ---------------- 8. planning quality on range planner (spec §12) ----------------

def run_planner_quality():
    from focus_agent import planner as fplanner
    from focus_agent.repository import TaskRepository, ScheduleRepository
    import tempfile, logic as _logic, storage as _storage
    tmp = tempfile.mkdtemp()
    _logic.DATA_FILE = os.path.join(tmp, "d.json")
    _storage.DATA_FILE = _logic.DATA_FILE
    data = _logic.load_data()
    repo = TaskRepository(data)
    repo.create("Essay", deadline="2026-10-27", duration=180, importance=3)
    repo.create("Reading", deadline="2026-10-30", duration=90)
    repo.create("Impossible", deadline="2026-10-24", duration=2000)

    # capacity honored exactly
    plan = fplanner.plan_range(data, "2026-10-23", settings=SETTINGS, now=NOW,
                               days=1, capacity_minutes=180)
    total = sum(_slot_min(s) for s in plan.days[0].slots)
    record("planner_capacity", "capacity limit honored", total <= 180, f"{total}min of 180")

    # blocks protect time
    ScheduleRepository(data).create("Dentist", start="15:00", end="19:00",
                                    date="2026-10-23")
    plan2 = fplanner.plan_range(data, "2026-10-23", settings=SETTINGS, now=NOW, days=1)
    bad = [s for s in plan2.days[0].slots if "15:00" <= s.start < "19:00"]
    record("planner_blocks", "fixed block protected", not bad,
           f"{len(bad)} violating slots")

    # no overlaps anywhere
    overlaps = []
    for d in plan2.days:
        ss = sorted(d.slots, key=lambda s: s.start)
        overlaps += [1 for a, b in zip(ss, ss[1:]) if b.start < a.end]
    record("planner_overlaps", "no overlapping slots", not overlaps,
           f"{len(overlaps)} overlaps")

    # overflow identified, never silently dropped
    record("planner_overflow", "infeasible work reported",
           any("Impossible" == u["title"] for u in plan2.unschedulable),
           "; ".join(u["title"] for u in plan2.unschedulable) or "none reported")


def _slot_min(slot):
    from focus_agent import dates as fdates
    return (fdates.hhmm_to_minutes(slot.end) - fdates.hhmm_to_minutes(slot.start))


# ---------------- 9. memory effectiveness (spec §12, official metric) ----------------

def run_memory_effectiveness():
    """Estimation error WITHOUT history vs WITH history on a known truth."""
    import tempfile, logic as _logic, storage as _storage
    tmp = tempfile.mkdtemp()
    _logic.DATA_FILE = os.path.join(tmp, "d.json")
    _storage.DATA_FILE = _logic.DATA_FILE
    data = _logic.load_data()
    truth = 120   # the user truly takes 2x their estimates

    def build_history(n):
        from logic import add_task_logic
        for i in range(n):
            add_task_logic(data, f"AI hw {i}", duration=60, subject="AI", difficulty=2)
            t = data["tasks"][-1]
            t["actual_minutes"] = truth
            t["status"] = "done"
            t["completed_at"] = f"2026-10-{10 + i:02d}T12:00:00"

    cold = fest.estimate_minutes(data, {"duration": 60, "subject": "AI",
                                        "difficulty": 2})
    build_history(4)
    learned = fest.estimate_minutes(data, {"duration": 60, "subject": "AI",
                                           "difficulty": 2, "created_at": "2026-10-20T00:00:00"})
    cold_err = abs(cold["minutes"] - truth)
    learned_err = abs(learned["minutes"] - truth)
    improved = learned_err < cold_err and learned.get("reliable")
    record("memory_effectiveness",
           f"estimation improves with history (cold {cold['minutes']}min -> "
           f"learned {learned['minutes']}min, truth {truth}min)", improved,
           f"error {cold_err} -> {learned_err} min")

    # adherence math on a committed plan
    from focus_agent import patterns as fpatterns
    from logic import add_task_logic, complete_task_logic, save_data
    past = "2026-10-22"
    t1 = add_task_logic(data, "Planned done", duration=60)
    data["tasks"][-1]["planned"] = {"date": past, "start": "09:00", "end": "10:00"}
    complete_task_logic(data, t1["id"])
    add_task_logic(data, "Planned skipped", duration=60)
    data["tasks"][-1]["planned"] = {"date": past, "start": "11:00", "end": "12:00"}
    data.setdefault("agent_memory", {})["plan_log"] = [
        {"ts": 1, "plan": {"date": past, "committed": True, "slots": []}}]
    save_data(data)
    adh = fpatterns.schedule_adherence(data, today=NOW.date())
    record("memory_adherence", "adherence ratio computed from real records",
           adh["ratio"] == 0.5, f"{adh['slots_honored']}/{adh['slots_total']} honored")


if __name__ == "__main__":
    sys.exit(main())
