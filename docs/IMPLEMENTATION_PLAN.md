# Focus Agent V2 — Implementation Plan

Phase-by-phase delivery sequence. Each phase lists objective, work items, tests,
and done-criteria. Ground rules from the master prompt apply throughout: no
breaking V1 data, tests green before every commit, no fabricated results, agent
work branches off `develop/v2-agent-architecture`.

## Branch model

- Integration branch: `develop/v2-agent-architecture` (created in Phase 0).
- Feature branches per phase: `feature/v2-foundation`, `feature/v2-agent-core`,
  `feature/v2-task-understanding`, `feature/v2-intelligent-planner`,
  `feature/v2-memory-learning`, `feature/v2-ui-integration`,
  `feature/v2-evaluation` — merged into the develop branch when their tests pass.

---

## Phase 0 — Repository audit & architecture ✅ (this delivery)

- Full audit → [V1_AUDIT.md](V1_AUDIT.md); target architecture →
  [ARCHITECTURE.md](ARCHITECTURE.md); agent design →
  [AGENT_DESIGN.md](AGENT_DESIGN.md).
- Repo hygiene: 1780 junk files (committed `venv/`, Android debug logs) untracked;
  no history rewritten.
- Verified: 128/128 tests pass on a fresh venv; benchmark 38/38; live Ollama
  `qwen3:4b` JSON round-trip OK.
- **Done when:** the four docs exist, hygiene commit is on the develop branch.

## Phase 1 — Core application foundation (`feature/v2-foundation`)

Objective: typed models + repository layer over the existing store, without
changing behavior.

1. `focus_agent/models.py` — pydantic domain models (spec §9 set) with dict
   bridges; explicit `Task`, `Subject`, `Goal`, `GoalMilestone`, `ScheduleBlock`,
   `FocusSession`, `ProductivityRecord`, `AgentConversation`, `AgentAction`,
   `AgentMemory`, `UserProfile`, `ClassRoutine`, `Subtask`.
2. `focus_agent/repository.py` — typed facades (Tasks, Subjects, Routine, Goals,
   Schedule, Focus, Memory) wrapping today's `logic.py` functions; validation at
   the boundary; `logic.py` stays as the implementation core.
3. `focus_agent/config.py` — centralized env→settings→default resolution
   (provider, model, endpoint, timeout, timezone, loop budgets).
4. `storage.py` — schema **v4** migration: additive only (`schedule_blocks`,
   `agent_memory` extensions, per-session focus records, hourly buckets);
   backup-on-migrate kept; corrupt-quarantine kept.
5. `requirements.txt` — move `groq/openai/google-genai` to a documented optional
   extras section; add nothing else heavy (pydantic already a transitive dep —
   now explicit).
6. Tests: model round-trips, repository validation errors, v3→v4 migration on a
   realistic v2-era fixture (backup created, zero data loss), config precedence.
- **Done when:** all existing 128 tests still pass + new foundation tests pass;
  app boots (`python main.py`) unchanged for the user.

## Phase 2 — Core AI agent (`feature/v2-agent-core`) — highest priority

Objective: replace the single-pass controller with the real agent loop
([AGENT_DESIGN.md §3](AGENT_DESIGN.md)).

1. `focus_agent/prompts.py` — step-decision prompt (strict JSON
   tool_call/ask_user/final), context pack builder, extraction prompt relocated.
2. `controller.py` — loop with budgets (`max_steps=6`, `max_llm_calls=4`,
   `max_tool_calls=8`), repeat detection, verification read-backs, pending
   question parking/resume, event stream for the UI; deterministic fallback
   ladder preserved exactly (existing tests keep passing).
3. `tools/` package — registry shell moves in (flat `tools.py` keeps a compat
   import); conversation/action persistence wired into `execute_tool`.
4. Offline behavior: provider off → identical deterministic flow (pin with
   tests); `provider=none` honored.
5. Tests: loop budgets, repeat blocking, verify-before-success (inject fault),
   clarification resume, multi-step "move X to Friday" via scripted LLM stub,
   offline fallback equivalence.
- **Done when:** scripted multi-step scenarios execute through the loop with
  persisted actions; all prior tests green; live smoke test with `qwen3:4b`
  documented (exact transcript, no embellishment).

## Phase 3 — Task understanding & subject detection (`feature/v2-task-understanding`)

1. `extractor.py` — richer fields (deadline+time, difficulty from adjectives,
   multi-task bounds), "update" intents resolved through the loop instead of
   hard-coded routes.
2. New tools: `search_tasks`, `decompose_task`, `detect_task_subject`,
   `update_subject`, plus renamed aliases (`get_class_routine`,
   `assign_task_subject`).
3. `goals.py` — `decompose_goal` as an explicit persisted tool call (controller's
   auto-attach removed); `get_goals` alias.
4. Ambiguity handling: parked-question flows for subject and deadline cases.
5. Tests: extraction accuracy cases from the spec's dataset (§12), subject
   classification incl. refusal-to-guess, decompose flows.

## Phase 4 — Intelligent planning (`feature/v2-intelligent-planner`)

1. `planner.py` — multi-day, deadline-aware: horizon scan, per-day allocation
   using the existing `scheduler.generate_day_plan` kernel, deadline feasibility
   warnings, overflow identification with reasons, partial rescheduling (only
   affected days rebuilt).
2. Priority upgrade: goal relevance + historical completion/adherence factors;
   all weights documented and unit-tested.
3. Schedule blocks: `create/update/delete_schedule_block`,
   `detect_schedule_conflicts`, `get_daily_schedule`, `reschedule_task`
   (validated single-task move + day replan).
4. Productivity-period placement hook (no-op until Phase 5 data exists).
5. Tests: no-overlap invariant, class protection, conflict detection, deadline
   infeasibility messaging, partial reschedule isolation, spec case "3 hours
   free tomorrow".

## Phase 5 — Memory & learning (`feature/v2-memory-learning`)

1. `memory/` package: conversations, actions, plans, adherence, hourly focus
   buckets; `patterns.py` (productive hours, weekday effects, subject rates).
2. Focus timer writes per-session records + hourly buckets (additive; aggregates
   keep flowing for existing views).
3. Planner consumes: productive-hour placement (with disclosed basis), adherence
   modulation, carry-over suggestions for missed tasks.
4. New analytics tools: `get_task_completion_history`,
   `compare_estimated_actual_duration`, `analyze_productivity_patterns`,
   `estimate_task_duration`, `track_goal_progress`.
5. `ace_integration.py` skillbook data imported into the memory store (compat
   read), module retired from the agent path.
6. Tests: pattern math on synthetic histories, adherence effect on packing,
   memory-effectiveness check (estimate error with vs without history).

## Phase 6 — UI integration (`feature/v2-ui-integration`)

1. Split `ui.py` → `ui/` package (widgets, app shell, 10 views per spec).
2. Chat view renders the real event stream (loop steps, tool results,
   confirmations, parked questions); proposals clearly separated from committed
   state; no fabricated statuses (existing honesty rule, now structural).
3. Dashboard, tasks, subjects, routine, planner, goals, timer, analytics,
   settings views re-wired to repositories; behavior parity checks against the
   V1 screens.
4. Tests: UI-logic unit tests (view models), manual smoke checklist documented;
   the 14 existing views' functionality preserved.

## Phase 7 — Evaluation & refinement (`feature/v2-evaluation`)

1. `tests/eval_dataset.json` — the 8 spec scenarios + extensions (≈40 cases)
   with expected structured outcomes.
2. `evaluate.py` extension → `docs/EVALUATION.md` with all 8 official metrics:
   task extraction accuracy, deadline extraction accuracy, subject
   classification accuracy, scheduling quality (feasibility), deadline handling,
   duration-estimation error (MAE/ratio), tool execution success, memory
   effectiveness (with/without history delta).
3. Live-LLM runs documented with environment details; deterministic runs stay
   CI-able.
4. README refresh; docs cross-checked against reality; release tag.

## Risks & mitigations

| Risk | Mitigation |
| :-- | :-- |
| Loop regressions break the working single-pass flow | deterministic fallback ladder pinned by existing tests; loop ships behind identical public API (`AgentController.handle`) |
| Small local model (qwen3:4b) produces weak step JSON | strict JSON mode + one repair round + deterministic assists; offline path always works; document measured live results honestly |
| Storage v4 migration damages user data | additive-only keys, auto-backup, quarantine, fixture-based migration tests (existing machinery, extended) |
| UI split breaks 14 working views | split is mechanical, view-by-view, with parity checklist; chat redesign isolated from layout code |
| Scope creep into multi-agent territory | explicitly a non-goal (ARCHITECTURE.md §8) |
| Hidden coupling on `logic.py` imports | repository layer absorbs `logic.py`; grep-gate: controller/tools must not import `logic` directly (Phase 2+) |

## Technical decisions log

| # | Decision | Rationale |
| :-- | :-- | :-- |
| D1 | Evolve the current Python agent app; no rewrite | `main` already implements most of the proposal; rewrite would discard tested machinery (audit §4) |
| D2 | pydantic for domain models | spec allows "Pydantic or equivalent"; already a transitive dependency; typed validation at repository boundaries |
| D3 | Keep single `data.json` store | single-user desktop app; repository layer is the future swap point |
| D4 | Custom loop, no agent framework | auditability, offline determinism, spec §11 |
| D5 | Rename tools with aliases kept one release | spec names win long-term; V1-era tests/scripts keep working |
| D6 | Committed venv untracked (index-only) | 123 MiB junk, non-portable; history untouched (audit issue #8) |
| D7 | Legacy cloud parsers stay, moved to extras | spec rule: don't remove V1 functionality without justification; offline-first preserved |
