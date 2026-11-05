# Focus Agent V2 — Evaluation Results

All numbers below are **computed at run time** by `evaluate.py` against the fixed
dataset in `tests/eval_dataset.json` (32 cases, including the 8 scenarios from the
official project proposal). Nothing in this document is hand-written data.

Reproduce:

```bash
.venv/bin/python evaluate.py           # deterministic, no LLM needed
.venv/bin/python evaluate.py --live    # + extraction/understanding through Ollama
.venv/bin/python -m pytest tests/ -q   # 199 unit/integration tests
```

Environment for the live run: Ollama on localhost, model `qwen3:4b` (2.5 GB,
Qwen3 family), `OLLAMA_TIMEOUT=90`, reference date 2026-10-23 (Friday), JSON mode
(`temperature=0`, `format:"json"`) with the deterministic merge rules of
`extractor.extract()` applied on top (keyword dates and structural intents beat
model inference).

## Official metrics (spec §12)

| Metric | Deterministic | Live LLM (`qwen3:4b`) | How measured |
| :--- | :--- | :--- | :--- |
| Task extraction accuracy | **32/32 (100%)** | **32/32 (100%)** | intent + n-tasks + task_ref + duration fields over the dataset |
| Deadline extraction accuracy | **11/11 (100%)** | **11/11 (100%)** | exact `YYYY-MM-DD` match for every dated case |
| Subject classification accuracy | **5/5 (100%)** | — (deterministic matcher) | auto-assign vs ask vs refuse-to-guess thresholds |
| Scheduling quality | **8/8 + 3/3 range checks (100%)** | — (deterministic planner) | no overlaps, classes/blocks respected, no past slots, capacity honored |
| Deadline handling | **3/3 + 1/1 (100%)** | **1/1 (100%)** | deadline-sensitive task without a date must ask, never invent |
| Duration estimation error | **cold 51 min → learned 0 min** (truth 120) | — | synthetic history with known true ratio (2× estimates) |
| Tool execution success | **11/11 (100%)** | **11/11 (100%)** | validation, permissions, confirmation, idempotency, destructive flows |
| Memory effectiveness | **improvement verified** | — | estimate error shrinks 51→0 min with ≥3 observations; adherence 1/2 computed from real records |

## Section detail (deterministic run)

```
EXTRACTION 7/7 · DEADLINE HANDLING 3/3 · SUBJECT ASSIGNMENT 5/5 ·
SCHEDULE 8/8 · TOOL ACTIONS 11/11 · ESTIMATION 4/4 ·
DATASET 5 sections 32 cases (extraction/deadlines/capacity/blocks/ask) ·
PLANNER_CAPACITY/BLOCKS/OVERLAPS/OVERFLOW 4/4 ·
MEMORY_EFFECTIVENESS + MEMORY_ADHERENCE 2/2
OVERALL: 49/49 (100%)
```

Live run (`--live`): the same dataset through the real model +
deterministic merge: **OVERALL 59/59 (100%)** — legacy sections re-run live
(extraction 7/7, tool actions 11/11) plus the 32-case dataset.

## Known model limitations (documented, guarded in production)

1. **Ambiguous bare imperatives** ("complete the networking task") can be read
   as done-marking *or* task creation. qwen3:4b sometimes picks completion.
   Production is safe under both readings: completion on a non-existent task
   triggers the candidate-choice clarification instead of an error.
2. **Class attendance durations**: the model occasionally copies a sibling
   task's duration onto a class-attendance item; suppressed deterministically
   (`looks_like_class_attendance`).
3. **Structural intents**: the model sometimes answers "goal" for concrete task
   requests ("prepare for a quiz next Wednesday, ~90 minutes"); the merge rule
   trusts the local parser when the model found nothing actionable, and explicit
   keyword intents ("plan my day", "reschedule", "don't schedule X to Y") always
   win — measured by the dataset cases above.

## Unit / integration suite

`pytest tests/ -q` → **199 passed** (models, repositories, config, storage
migration v3→v4, extraction, subjects, dates, scheduler, planner, tools
(38 registered incl. aliases), agent loop (budgets, verification, repeat guard,
parked questions), memory/learning patterns, controller flows, regressions).

## Honesty rules the evaluation enforces

- Cold-start estimates are labeled defaults (`reliable: false`), never claimed
  as learned (asserted by tests).
- Productive hours need ≥45 min of *attributed* focus before the planner uses
  them; the unattributed bucket cannot fake learning.
- Adherence needs committed past plans; with none, the tool says so.
- The planner reports infeasible work with reasons instead of dropping it.
