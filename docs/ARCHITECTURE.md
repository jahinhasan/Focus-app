# Focus Agent V2 — Architecture

This document defines the V2 target architecture: layers, contracts, invariants, and
the repository layout. The current state of the code is documented in
[V1_AUDIT.md](V1_AUDIT.md); the agent's internal design is detailed in
[AGENT_DESIGN.md](AGENT_DESIGN.md); the delivery sequence lives in
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## 1. Design principles

1. **The agent is the product.** Every feature must be reachable through natural
   language + tools, not only through screens.
2. **Deterministic-first.** Parsing, scheduling, validation, estimation, and
   analytics are plain Python and work with the LLM offline. The LLM adds
   understanding; it never owns state changes.
3. **The LLM never touches storage.** The only write path is validated tools.
   The controller enforces the same rule on itself (audit issue #13).
4. **Unknown ≠ invented.** Missing fields stay `null`; ambiguity produces a
   clarifying question; low-confidence matches are flagged, never silently applied.
5. **Local-first & private.** Ollama/Qwen is the primary provider; the online
   provider is opt-in, env-keyed, and always disclosed. The app is fully usable
   with `provider=none`.
6. **Additive data evolution.** Storage migrations never delete or rewrite user
   data; every migration writes a timestamped backup first.
7. **Measure, don't claim.** Evaluation numbers come from running code.

## 2. Layer map (V2 target)

```text
┌────────────────────────────────────────────────────────────────────┐
│ 1. UI (ui/ package, CustomTkinter)                                 │
│    chat · dashboard · tasks · subjects · routine · planner ·       │
│    goals · timer · analytics · settings                            │
│    renders AgentEvent stream: steps, tool calls, confirmations      │
└──────────────┬─────────────────────────────────────────────────────┘
               │ AgentController.handle(text) -> AgentTurn
┌──────────────▼─────────────────────────────────────────────────────┐
│ 2. AGENT CONTROLLER (focus_agent/controller.py)                    │
│    AgentLoop: context → reasoning → ToolCall → validate → execute  │
│    → observe → repeat (budgeted) → final reply                     │
│    guards: step budget · repeat detection · verify-before-claim     │
│    pending-question state across turns                             │
└──────┬──────────────────┬───────────────────┬─────────────────────┘
       │                  │                   │
┌──────▼───────┐  ┌───────▼─────────┐  ┌──────▼──────────────────┐
│ 3. LLM       │  │ 4. UNDERSTANDING│  │ 5. TOOL REGISTRY        │
│ providers    │  │ extractor.py    │  │ tools/ package          │
│ llm.py       │  │ subjects.py     │  │ 47 tools (incl. aliases), typed schema │
│ ollama ·     │  │ dates.py        │  │ permission classes      │
│ online · null│  │ intent, tasks,  │  │ confirmation policy     │
│ typed errors │  │ goals, ref-res  │  │ idempotency · audit     │
└──────┬───────┘  └───────┬─────────┘  └──────┬──────────────────┘
       │                  │                   │ ToolCall/ToolResult
       │          ┌───────▼──────────┐  ┌─────▼───────────────────┐
       │          │ 6. PLANNING      │  │ 7. REPOSITORIES         │
       │          │ planner.py       │  │ repository.py           │
       │          │ priority ·       │  │ typed facades over      │
       │          │ multi-day slots ·│  │ tasks/subjects/goals/   │
       │          │ conflicts ·      │  │ schedule/focus/memory   │
       │          │ feasibility ·    │  └─────┬───────────────────┘
       │          │ explanations     │        │ domain models only
       │          └───────┬──────────┘  ┌─────▼───────────────────┐
┌──────▼──────────────────▼─────────────┤ 8. DOMAIN MODELS        │
│ 9. MEMORY & LEARNING                  │ models.py (pydantic)    │
│ memory.py + patterns.py               │ Task Subject ClassRoutine│
│ conversations · actions · adherence · │ Goal GoalMilestone       │
│ hourly focus buckets · estimation     │ ScheduleBlock FocusSession│
│ (estimator.py) with disclosed basis   │ ProductivityRecord …     │
└──────────────┬────────────────────────┴─────────────────────────┘
               │ additive schema migrations + backups
┌──────────────▼─────────────────────────────────────────────────────┐
│ 10. PERSISTENCE  storage.py → data.json (schema v4)                │
│ 11. OPTIONAL online research (env-keyed, disclosed)                │
└────────────────────────────────────────────────────────────────────┘
```

### Invariants

- Tools are the **only** writers. UI, controller, LLM, planner all mutate state
  through repositories/services; `logic.py` becomes an implementation detail of
  the repositories, not a peer import surface.
- The planner is deterministic and pure where possible: `plan(date) -> PlanResult`
  with explanations; committing a plan is a separate validated tool call.
- Every agent-visible number that is learned (durations, productive hours,
  adherence) carries its `basis` — sample count and rule — so the UI can show
  "learned vs default".
- Failed tool execution leaves no residue: call IDs are released on failure so
  retries are possible (existing behavior, kept).

## 3. Target repository layout

```text
focus-app/
├── main.py                    # entry point (unchanged role)
├── storage.py                 # persistence + schema migration (v3→v4)
├── evaluate.py                # benchmark harness (extended, Phase 7)
├── requirements.txt           # runtime deps (legacy cloud deps → extras)
├── docs/                      # V1_AUDIT · ARCHITECTURE · AGENT_DESIGN ·
│                              # IMPLEMENTATION_PLAN · EVALUATION
├── focus_agent/
│   ├── __init__.py
│   ├── config.py              # centralized settings access (Phase 1)
│   ├── models.py              # pydantic domain models + dict bridges (Phase 1)
│   ├── repository.py          # typed data services (Phase 1)
│   ├── llm.py                 # providers (kept, extended for tool-calls Phase 2)
│   ├── schemas.py             # ToolCall/ToolResult + validation (kept)
│   ├── controller.py          # agent loop (Phase 2 rewrite)
│   ├── prompts.py             # all prompt templates (Phase 2)
│   ├── extractor.py           # NL understanding (kept, extended Phase 3)
│   ├── subjects.py            # subject detection (kept, extended Phase 3)
│   ├── dates.py               # date parsing (kept)
│   ├── estimator.py           # duration learning (kept, extended Phase 5)
│   ├── goals.py               # goal logic + roadmap drafts (kept, Phase 3)
│   ├── memory/
│   │   ├── __init__.py        # memory engine facade (Phase 5)
│   │   ├── store.py           # conversations, actions, adherence stores
│   │   └── patterns.py        # productive hours, missed-task patterns
│   ├── planner.py             # multi-day planning engine (Phase 4; scheduler.py
│   │                          # remains as the single-day kernel it wraps)
│   ├── scheduler.py           # single-day deterministic kernel (kept)
│   └── tools/
│       ├── __init__.py        # registry shell (execute_tool, ToolSpec)
│       ├── tasks.py           # task tools
│       ├── subjects.py        # subject/routine tools
│       ├── schedule.py        # schedule/planning tools
│       ├── goals.py           # goal tools
│       └── analytics.py       # productivity/analytics tools
├── ui/                        # split from ui.py (Phase 6)
│   ├── app.py                 # FocusApp shell
│   ├── chat.py                # agent chat + event rendering
│   ├── dashboard.py · tasks.py · subjects.py · routine.py
│   ├── planner.py · goals.py · timer.py · analytics.py · settings.py
│   └── widgets.py             # shared widgets (XPBar, TimePicker, …)
├── tests/                     # pytest suite (per-phase growth)
├── android/                   # Flutter companion (untouched in V2 core)
└── data.json                  # user store (gitignored)
```

The `focus_agent/` + flat-module layout stays import-compatible during the
transition: Phase 1 introduces new modules without moving old ones; Phase 2
replaces the controller in place; the `tools/` package supersedes the flat
`tools.py` with a compatibility import so existing tests keep passing until
updated in the same commit that moves them.

## 4. Domain models (spec §9)

`models.py` defines pydantic models; each has `from_dict()/to_dict()` bridges so
the JSON store keeps its dict shape. Required models and their key fields:

| Model | Key fields | Store location today |
| :-- | :-- | :-- |
| `UserProfile` | xp, level, streak, settings links, timezone | top-level `xp/level/streak/settings` |
| `Subject` | name, source (vault/routine), keywords | `subjects` dict |
| `ClassRoutine` | weekday → {title, subject, start, end} | `tasks[type=class].schedule` |
| `Task` | id, title, type, subject, status, due date/time, estimate, actual, importance, difficulty, subtasks, planned slot, recurrence, goal_id, reschedule history | `tasks[type=task]` |
| `Subtask` | title, done | `tasks[].subtasks` |
| `Goal` | id, title, status, target_date, milestones | `goals` |
| `GoalMilestone` | title, done, target_date, estimate | `goals[].milestones` |
| `ScheduleBlock` | date, start, end, kind (class/task/custom), source | NEW: `schedule_blocks` (custom fixed commitments) |
| `FocusSession` | date, start/end or duration, task_id, kind | NEW per-session records; day aggregates stay |
| `ProductivityRecord` | date, hour_bucket, focus_minutes, tasks_done | NEW hourly buckets under `focus_sessions` |
| `AgentConversation` | id, started_at, turns[] | NEW: `agent_memory.conversations` |
| `AgentAction` | call_id, tool, args, ok, ts, turn ref | promoted from `tool_log` |
| `AgentMemory` | estimation records, patterns, adherence, plan log | `agent_memory` (extended) |

Migration v4 adds only new keys/sections; the v3 reader in `storage.py` keeps
working, and `tests/test_storage_migration.py` extends to cover v3→v4 with a
realistic v2-era file.

## 5. Data flow — one agent turn (target)

```text
user text
  │
  ▼
AgentController.handle()
  │ 1. persist AgentConversation turn
  │ 2. pending-question check (clarification continuation)
  │ 3. deterministic fast paths (greetings, stats, next class)   ← no LLM
  │ 4. loop (budget: max_steps, max_llm_calls, no-repeat guard):
  │      context pack → LLM decides {tool_call | ask_user | final_answer}
  │        ├── tool_call → validate schema → permission/confirmation
  │        │      → execute via tools/ → ToolResult → observe
  │        │      → verify critical effects (re-read state) before success
  │        ├── ask_user → surface question, park state, end turn
  │        └── final_answer → compose with tool results + explanations
  │ 5. persist AgentAction records + turn outcome
  ▼
AgentTurn {reply, tool_results[], plan?, status, events[]}
```

The offline path (provider unavailable or `provider=none`) skips step 4's LLM and
uses the deterministic extractor + fixed intent routing — identical to today's
behavior, which the existing tests pin down.

## 6. Configuration

Single precedence chain, implemented in `config.py` (Phase 1), replacing scattered
lookups:

`environment variable` → `data.settings.agent` → `default`
(`FOCUS_LLM_PROVIDER`, `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`,
`ONLINE_LLM_*`, `FOCUS_TZ`, loop budgets `FOCUS_AGENT_MAX_STEPS`,
`FOCUS_AGENT_MAX_LLM_CALLS`). Secrets never enter `data.json` — online keys are
env-only (unchanged rule).

## 7. UI integration contract

The chat view receives an `AgentTurn` and renders its `events[]` — real loop steps
only ("Checking your class routine…", "Created task 'X' ✓"). The UI must never
display a step that did not happen; proposed-but-unconfirmed plans render as
proposals with an explicit apply action. This is a hardening of the existing
ChatView behavior, kept thread-safe via the existing worker-thread + queue bridge.

## 8. Non-goals (explicit)

- No multi-agent orchestration: one controller loop, specialized tools (spec §11).
- No framework adoption (LangChain etc.): the custom loop stays auditable.
- No server/database engine: `data.json` + atomic writes remain sufficient for a
  single-user desktop app; the repository layer is where a future store change
  would happen.
- No removal of V1 features (vault, habits, store, timer, mobile port) — they are
  outside the agent path and stay untouched except for UI packaging.
