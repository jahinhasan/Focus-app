# Focus Agent V2 — Agent Design

The normative design of the agent: characteristics, components, execution loop,
tool registry, memory, and safety rules. Architecture context:
[ARCHITECTURE.md](ARCHITECTURE.md).

## 1. Agent characteristics (spec §4.2) and where they live

| Characteristic | Concrete mechanism in this codebase |
| :-- | :-- |
| **Goal-based** | `goals` store + `goal_id` links on tasks; `create_goal`/`decompose_goal`/`track_goal_progress` tools; priority scoring adds goal-relevance points (Phase 4); roadmap drafts with disclosed assumptions (`goals.py`) |
| **Utility-based** | `planner.task_priority`: deadline urgency bucket → importance → difficulty → user priority hint → goal relevance → historical completion pattern; every point carries a human-readable reason string; deterministic and unit-tested |
| **Learning** | `estimator.py` median-ratio realism (subject/difficulty grouped, MIN_SAMPLES, leakage guard); Phase 5 adds productive-hour detection from hourly focus buckets, schedule adherence tracking, missed-task patterns; every learned value reports `{basis, samples, reliable}` |

## 2. Components (spec §4.2 → modules)

1. **Agent Controller** — `controller.py`: owns the loop, budgets, guards,
   conversation context, clarification parking, verification of critical effects.
2. **LLM Reasoning Engine** — `llm.py` providers + `prompts.py`: decides the next
   step as strict JSON (`{"action": "tool_call"|"ask_user"|"final", ...}`).
3. **Tool Registry** — `tools/` package: catalog, schemas, permission classes,
   confirmation policy, idempotency, audit log (existing `tools.py` shell, split).
4. **Task Understanding Engine** — `extractor.py` + `dates.py`: NL → structured
   tasks/intents with deterministic fallback and merge rules.
5. **Subject Detection Engine** — `subjects.py`: normalization, token overlap +
   fuzzy scoring, AUTO/ASK thresholds, routine-derived subjects.
6. **Planning Engine** — `planner.py` (multi-day) over `scheduler.py` (single-day
   kernel): priorities, availability, allocation, conflicts, feasibility,
   explanations.
7. **Memory & Learning Engine** — `patterns.py` + `memory.py` + `estimator.py`: bounded
   persistent stores, statistics only, no LLM writes.
8. **Agent Response Engine** — controller's reply composer + UI event stream:
   results, decisions, changes, recommendations — only from real ToolResults.

## 3. Execution loop (spec §4.3)

```text
        user message
             │
             ▼
 ┌── context retrieval ────────────────────────────────────────────┐
 │  compact profile · open tasks (bounded) · today's classes ·     │
 │  relevant memory (recent turns, pending question, learned       │
 │  estimation summary) · known subjects · tool catalog            │
 └──────────────────────────────────┬──────────────────────────────┘
             ▼                      │
 │ intent fast path? (greeting/query stats/next class → answer, 0 LLM calls)
 ├── yes → reply
 └── no
             ▼
 ╔══ agent loop (repeat ≤ MAX_STEPS) ══════════════════════════════╗
 ║  LLM step decision (strict JSON, temperature 0):                ║
 ║   {"action":"tool_call","tool":…,"args":{…},"why":…}            ║
 ║   {"action":"ask_user","question":…}                            ║
 ║   {"action":"final","reply":…}                                  ║
 ║        │                                                        ║
 ║   ├── tool_call → guards:                                       ║
 ║   │     • tool exists? schema valid? (reject → error back to LLM)║
 ║   │     • repeated call? (same tool+normalized args twice →     ║
 ║   │       blocked, forced to final/ask)                         ║
 ║   │     • destructive? → confirm_callback (never auto-yes)      ║
 ║   │     • budget left? else force final                         ║
 ║   │   execute → ToolResult → verify (read-back for create/update║
 ║   │   on critical intents) → observation appended to context    ║
 ║   ├── ask_user → park pending question + partial results,       ║
 ║   │                end turn (resumes next message)              ║
 ║   └── final → compose reply from ToolResults + plan + reasons    ║
 ╚═════════════════════════════════════════════════════════════════╝
             │
             ▼
 state/memory update (conversations, actions, adherence)
             │
             ▼
        AgentTurn → UI
```

### Loop budgets & guards (defaults, env-overridable)

| Guard | Default | Rationale |
| :-- | :-- | :-- |
| `max_steps` | 6 | one instruction should rarely need more; hard stop prevents runaway loops |
| `max_llm_calls` | 4 | cost/latency ceiling per turn |
| `max_tool_calls` | 8 | typing/rate safety |
| repeat detection | 2 identical (tool, normalized args) | blocks model thrash; cached ToolResult is returned instead |
| step timeout | provider timeout (120 s default) | unchanged |
| invalid-arg retries | 1 (error feedback to LLM, then deterministic assist) | self-correction without infinite loops |

### Determinism & fallback ladder

1. Deterministic fast paths (no LLM): greetings, stats, next class, today list.
2. Deterministic intent + extraction (existing, tested) used when provider is
   offline, fails, or returns garbage — plus a warning in the reply.
3. Hybrid merge kept from V1: keyword-resolved dates beat model dates; unknown
   LLM intent is repaired from the parser.
4. `provider=none` → the whole app runs deterministically (existing guarantee).

### Verification before claiming success

For `create_task`, `update_task`, `complete_task`, `reschedule_task` the loop
re-reads the affected record via the repository after the tool returns OK and
checks the intended invariant (title/field/date present). A mismatch downgrades
the result to an error rather than reporting success. (Fixes audit gap: today the
loop trusts ToolResult.ok alone for multi-step flows.)

### Clarification protocol

- Extraction-level ambiguity (deadline-sensitive task with no date; low-confidence
  subject) already produces `question` — kept, and now **parked**: pending
  question + partial tool results persist in `AgentConversation`, and the next
  user message is interpreted as the answer first (slot-filling continuation).
- Destructive tools still require explicit per-call confirmation through the UI
  bridge; `ask_user` never substitutes for that confirmation.

## 4. Tool registry specification

Shell (unchanged contracts): typed schema validation (unknown args rejected),
permission classes `read | write | destructive`, `requires_confirmation` +
`confirm_fn` prechecks, call-ID idempotency, bounded audit logging, handlers that
never raise (crash → ToolResult).

Legend: **P** = permission, **C** = requires user confirmation, ★ = new in V2.

### Task tools (tasks.py)

| Tool | P | C | Notes |
| :-- | :-- | :-- | :-- |
| `create_task` | write | | auto subject match w/ thresholds (exists) |
| `get_task` | read | | id or title fragment (exists) |
| `list_tasks` | read | | filters: status/subject/dates/search (exists) |
| `update_task` | write | | field updates (exists) |
| `complete_task` | write | | records actual minutes (exists) |
| `delete_task` | destructive | ✓ | (exists) |
| `search_tasks` ★ | read | | ranked text search across title/notes/subject with match reasons (wraps repository query; complements `list_tasks`) |
| `decompose_task` ★ | write | | splits a task into ordered subtasks (LLM-assisted draft, deterministic dedupe; subtasks are the only write) |
| `reopen_task`, `add_subtask` | write | | (exist; stay) |

### Subject & routine tools (subjects.py)

| Tool | P | C | Notes |
| :-- | :-- | :-- | :-- |
| `create_subject` | write | ✓ | (exists) |
| `list_subjects` | read | | (exists) |
| `update_subject` ★ | write | | rename / add keywords; routine-linked subjects update their class tasks |
| `get_class_routine` | read | | = existing `get_routine` (renamed, alias kept) |
| `add_class` | write | | (exists) |
| `detect_task_subject` ★ | read | | pure classifier: mention/known-subjects/routine → ranked candidates with confidences, no writes |
| `assign_task_subject` | write | | = existing `assign_subject` (renamed, alias kept) |

### Schedule tools (schedule.py)

| Tool | P | C | Notes |
| :-- | :-- | :-- | :-- |
| `get_daily_schedule` ★ | read | | committed plan + fixed blocks for a date |
| `get_available_slots` | read | | = existing `get_availability` |
| `create_schedule_block` ★ | write | ✓ for recurring | custom fixed commitment (spec: "I have a class 10–12, don't schedule anything") |
| `update_schedule_block` ★ | write | | move/edit a block; protected blocks never silently move |
| `delete_schedule_block` ★ | destructive | ✓ | |
| `reschedule_task` ★ | write | | single-task move with validation (target slot free? deadline sane?) + replan of the affected day |
| `detect_schedule_conflicts` ★ | read | | overlaps among blocks/committed plan for a date range |
| `generate_daily_plan` | write | ✓ on commit | (exists; uncommitted drafts stay confirmation-free) |
| `reschedule_day` | write | ✓ on commit | (exists) |

### Goal tools (goals.py)

| Tool | P | C | Notes |
| :-- | :-- | :-- | :-- |
| `create_goal`, `update_goal`, `add_milestone`, `complete_milestone` | write | | (exist) |
| `get_goals` | read | | = existing `list_goals` (renamed, alias kept) |
| `decompose_goal` ★ | write | | roadmap milestone draft → persisted only after this explicit call (controller no longer auto-attaches) |
| `track_goal_progress` ★ | read | | progress %, milestone status, linked tasks, pace vs target date |

### Productivity & analytics tools (analytics.py)

| Tool | P | C | Notes |
| :-- | :-- | :-- | :-- |
| `get_focus_history` | read | | (exists) |
| `get_productivity_statistics` | read | | = existing `get_analytics` (renamed, alias kept) |
| `get_task_completion_history` ★ | read | | completed/missed tasks over a window with rates by subject/difficulty |
| `compare_estimated_actual_duration` ★ | read | | est-vs-act for completed tasks (overall/by subject), mean error ratio |
| `analyze_productivity_patterns` ★ | read | | productive hours, weekday effects, adherence trend (Phase 5 data) |
| `estimate_task_duration` ★ | read | | learned estimate for a described/linked task with `{basis, samples, reliable}` |
| `record_focus_time`, `generate_report`, `explain_priorities` | read/write | | (exist; stay) |

Renames ship with backwards-compatible aliases registered in the registry for one
release, and the README table is updated when they land.

## 5. Context management & privacy

- The LLM sees a **compact pack**: profile line, ≤25 open tasks (id, title, due,
  estimate, status), today's classes, known subjects, recent 3 turns, the pending
  question if any, learned-estimate summary line, tool catalog. Never raw
  `data.json`, never vault file contents, never focus logs beyond aggregates.
- History truncation per provider (existing `[-8:]`, 2000-char clamp) is kept.
- Online provider only for research-shaped chat, only when configured, always
  disclosed in the reply text (existing rule, unchanged).

## 6. Failure handling matrix

| Failure | Behavior |
| :-- | :-- |
| Ollama down / model missing / timeout | typed `LLMError` → deterministic path → reply notes degraded mode (existing, kept) |
| Malformed LLM step JSON | one re-ask with error; then deterministic intent routing |
| Invalid tool args | schema errors fed back once; then assist from extractor |
| Unknown tool | error observation to LLM; deterministic router still available |
| Repeated identical call | cached result returned; loop forced toward final |
| Handler crash | caught → ToolResult error; call ID released for retry (existing) |
| Confirmation refused | action skipped, turn continues with declined status (existing) |
| Budget exhausted | turn ends with completed-so-far summary + explicit "couldn't finish" note |

## 7. Memory & learning design (spec §7)

Persistent, bounded, app-controlled. The LLM never writes memory directly.

| Store | Contents | Cap | Used by |
| :-- | :-- | :-- | :-- |
| `conversations` | turns, parked questions, outcomes | 50 recent | clarification continuation, context |
| `actions` | AgentAction records (promoted tool_log) | 500 | audit, adherence analytics |
| `plans` | generated plans + commit status | 200 | adherence: planned vs actually done |
| `hourly_focus` | `ProductivityRecord` buckets (date,hour → minutes) | none needed (compact) | productive-hours detection |
| `estimation_records` | est/actual tuples (existing) + subject/difficulty | — | `estimator.py` (existing) |
| `patterns` | computed views: productive hours, per-subject completion, adherence trend, missed-task reasons | recomputed on demand | planner placement, report, `analyze_productivity_patterns` |

Learning rules (transparent statistics only):

- **Duration realism** — existing median-ratio estimator, unchanged semantics.
- **Productive hours** — from Phase 5 onward, hourly buckets feed a smoothed
  per-hour score; planner prefers high-score hours inside the study window for
  deep/difficult work; cold start (insufficient data) = neutral placement, and
  the reply says so.
- **Adherence** — plans record commit status; completion of planned slots vs
  total yields an adherence ratio that modulates how aggressively the planner
  packs a day (under-adherent → fewer, shorter blocks + note).
- **Missed tasks** — overdue-and-un-done tasks feed "carry-over" suggestions and
  priority weighting, never silent auto-deletion.

## 8. Response style rules

- Report every executed tool with its real result; proposed (unconfirmed) plans
  are labeled as proposals with the apply action.
- Explain scheduling decisions from the planner's reason strings — no invented
  rationale.
- Concise recommendations ≤ 6 bullets; learned numbers always annotated with
  sample basis ("learned from 4 tasks", or "default — no history yet").
- Errors are user-presentable (provider layer's typed exceptions) with the
  recovery hint ("run: ollama pull qwen3:4b").
