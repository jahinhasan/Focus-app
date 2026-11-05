# V1 Repository Audit — Focus App → Focus Agent V2

Audited: 2026-11-05 · Commit audited: `c3535cb4` (branch `main`) · Auditor: Phase 0 of the V2 program.

## 0. Executive summary

The repository at `main` is **not the original V1 desktop dashboard anymore**. Git history shows
three eras:

| Era | Evidence | What it was |
| :-- | :-- | :-- |
| V1 dashboard (Flutter era) | commits up to `62da40c1`…`028d9bf7` | Python desktop dashboard + hardcoded Gemini keys + Flutter Android port |
| **"V2: To Do Agent" rewrite** | `2da8480c` | Full Python agent app: `focus_agent/` package, Ollama, validated tools, deterministic scheduler, test suite |
| Bug pass & packaging | `c3535cb4` (HEAD) | Project-wide bug pass, setup scripts, Banglish guide |

The current `main` therefore already implements a large part of the V2 proposal:
Ollama/Qwen integration, a validated tool registry, a deterministic scheduler, statistical
duration learning, subject detection with confidence thresholds, storage migration, and
**128 passing tests + a 38/38 deterministic benchmark** (both re-verified during this audit).

The remaining work for Focus Agent V2 is not "build an agent from scratch" — it is
**deepening the agent**: a real iterative execution loop, the missing ~12 tools from the
official tool list, multi-day deadline-aware planning, richer persistent memory
(productive hours, adherence, conversations), a typed domain-model + repository layer,
UI modularization, and measurable evaluation per the official metrics table.

## 1. Existing architecture (as found on `main`)

```text
┌──────────────────────────────────────────────────────────────────┐
│ 1. UI / chat (ui.py — 3548 lines, CustomTkinter)                 │
│    14 view classes + FocusApp shell, worker thread + confirm Q    │
└──────────────┬───────────────────────────────────────────────────┘
               │ AgentController.handle(text) -> AgentReply
┌──────────────▼───────────────────────────────────────────────────┐
│ 2. Controller (focus_agent/controller.py — 403 lines)            │
│    single-pass: intent fast-paths → extract → route → tools      │
└──────┬──────────────────┬───────────────────────┬────────────────┘
       │                  │                       │
┌──────▼───────┐  ┌───────▼────────┐  ┌──────────▼──────────────┐
│ 3. LLM       │  │ 4. Extraction  │  │ 5. Tools (tools.py,     │
│ abstraction  │  │ extractor.py:  │  │ schemas.py): 24 tools,  │
│ (llm.py):    │  │ regex + LLM    │  │ schema/permission/      │
│ Ollama +     │  │ with merge +   │  │ confirm, idempotency,   │
│ online + null│  │ validation     │  │ audit log               │
└──────┬───────┘  └───────┬────────┘  └──────────┬──────────────┘
       │           ┌──────▼────────┐  ┌──────────▼──────────────┐
       │           │ 6. Deterministic engines        │
       │           │ dates.py, subjects.py (fuzzy +  │
       │           │ thresholds), scheduler.py       │
       │           └───────────────┘  └──────────┬──────────────┘
┌──────▼──────────────────────────────────────────▼───────────────┐
│ 7. Business logic & memory (logic.py 1077 lines, memory.py,     │
│    estimator.py, goals.py) — streaks, XP, focus log, analytics  │
└──────────────┬───────────────────────────────────────────────────┘
               │ only via storage.py (schema v3, backups, atomic)
┌──────────────▼───────────────────────────────────────────────────┐
│ 8. data.json (single JSON store)  +  optional online research    │
└──────────────────────────────────────────────────────────────────┘
```

## 2. Existing features

Preserved V1 features (verified in `ui.py` / `logic.py`):

- Today dashboard with XP/levels, streak, gamified rewards
- Class routine management (manual + photo/file import via legacy `ai_parser.py`)
- Smart Vault (per-subject file attachments, PDF/DOCX parsing via `file_parser.py`)
- Habits tracking, Pomodoro/stopwatch timer, store/gamification
- History and reports views
- Flutter mobile companion in `android/` (Gemini key now via `--dart-define`)

Agent-era features (the `2da8480c` rewrite):

- Chat agent (`AgentController`) with deterministic fast paths, NL task extraction
  (LLM + regex fallback), subject auto-matching with ask-don't-guess thresholds,
  deadline-ambiguity follow-up questions, day planning and rescheduling proposals,
  goal creation with roadmap drafts
- 24 validated agent tools (see §5)
- Estimation analytics and a recommendations report
- AI settings view with provider test-connection, study window, backups/restore

## 3. Technology stack (actual)

| Concern | Choice | Notes |
| :-- | :-- | :-- |
| Language | Python 3.12+ (runs on 3.14) | matches V2 proposal |
| UI | CustomTkinter + tkcalendar + darkdetect | desktop, single-window |
| LLM runtime | Ollama HTTP (`/api/chat`, `format: json`) | model configurable (`qwen3:4b` default) |
| Online LLM | OpenAI-compatible adapter, env-keyed | optional, disclosed in replies |
| Validation | Hand-rolled validators in `schemas.py` | **pydantic is not used** (only a transitive dep) |
| Storage | single `data.json`, schema v3, additive migration + timestamped backups | no DB engine |
| Parsing extras | pypdf, python-docx, pytesseract | vault file import |
| Legacy cloud | groq, openai, google-genai clients in `ai_parser.py` | V1 leftovers, optional |
| Tests | pytest, 128 tests, `evaluate.py` benchmark | deterministic, no LLM needed |

## 4. Reusable components — keep / extend / rework

### Keep as-is (stable, tested)
- `focus_agent/llm.py` — provider abstraction, typed errors (`ProviderUnavailable`,
  `ModelNotInstalled`, `BadResponse`), JSON extraction from fenced/prose output,
  env-keyed online adapter, `NullProvider` for offline mode.
- `focus_agent/subjects.py` — normalization, course-code stripping, token-overlap +
  fuzzy scoring, AUTO/ASK thresholds, routine-derived subjects.
- `focus_agent/dates.py` — relative-date resolution, timezone handling.
- `focus_agent/estimator.py` — median-ratio duration realism learning with subject/
  difficulty grouping, MIN_SAMPLES floor, leakage guard, disclosed fallbacks.
- `focus_agent/scheduler.py` — deterministic single-day planner: availability from
  study window minus classes, ≤90-min blocks with breaks, fixed-slot preservation,
  overload reporting with reasons, `explain_priorities`.
- `storage.py` — schema versioning, additive migration, backup/restore, corrupt-file
  quarantine.
- `focus_agent/tools.py` execution shell — schema validation, permission classes,
  confirmation bridge, idempotency via call IDs, audit logging.
- `logic.py` — XP/streak/history/focus-session machinery (V1 core, still sound).
- Test suite (128 tests) and `evaluate.py` benchmark harness.

### Extend in V2
- `focus_agent/controller.py` — currently a single-pass router; needs the real
  iterative agent loop (§6.1).
- `focus_agent/tools.py` — add the missing official tools (§5.2).
- `focus_agent/scheduler.py` — multi-day deadline-aware planning, productivity-period
  placement, custom fixed blocks, conflict detection tool.
- `focus_agent/memory.py` — conversation/action persistence, adherence tracking,
  productive-hour buckets, missed-task patterns.
- `ui.py` — split into a `ui/` package; wire honest step/status display for the loop.

### Rework / new
- **Domain models + repositories** (new `focus_agent/models.py`, `repository.py`):
  spec §9 requires typed models (UserProfile, Subject, ClassRoutine, Task, Subtask,
  Goal, GoalMilestone, ScheduleBlock, FocusSession, ProductivityRecord,
  AgentConversation, AgentAction, AgentMemory) with validation; today everything is
  untyped dicts. A pydantic model layer with dict bridges preserves data.json compat.
- **Config** (new `focus_agent/config.py`): centralized, typed settings access
  (env + data.settings precedence is currently scattered).

## 5. Existing AI integrations

1. **Ollama provider** (primary): `/api/chat`, JSON mode for extraction
   (`temperature=0` → `format:"json"`), `think:false` for Qwen3, status probe via
   `/api/tags`, timeout via env/settings. Verified live in this audit: `qwen3:4b`
   (installed locally, daemon was started, JSON round-trip OK).
2. **Extraction**: single-shot structured prompt (`EXTRACTION_SYSTEM_PROMPT`) →
   validated `ExtractionResult`; deterministic parser merged in (keyword dates beat
   model dates; unknown intent repaired from parser).
3. **Optional online provider**: OpenAI-compatible, env-keyed, used only for
   research-hinted chat, always disclosed in the reply.
4. **Legacy** (`ai_parser.py`, 942 lines): Groq/OpenAI/Gemini clients for routine
   photo import; still wired into `ui.py` but irrelevant to the agent path. Keep,
   isolated, optional (feature parity rule), but never on the agent's critical path.
5. **`ace_integration.py`**: local "skillbook" persistence + query counters; minimal
   real use. Candidate for consolidation into the V2 memory engine (documented
   decision, nothing deleted).

## 6. Data storage & schema

- Single `data.json` (gitignored), schema **v3**, additive migration with automatic
  timestamped backups in `backups/`, corrupt-file quarantine
  (`data.json.corrupt-<ts>`), in-app restore.
- Key sections: `tasks` (tasks AND recurring classes in one list, discriminated by
  `type`), `subjects` (vault dict), `goals`, `habits`, `vault` (files),
  `focus_sessions` (**daily aggregates only**), `history` (per-day totals),
  `agent_memory` (`tool_log`, `plan_log`, `executed_calls`,
  `estimation_records`), `settings` (`agent`, `study_hours`, `break_minutes`,
  `timezone`), `xp`/`level`/`streak`.
- Compat requirement: V2 must migrate v3 → v4 additively (new keys only), keep
  backup-on-migration, and keep every V1 value readable. Verified existing
  guarantees in `tests/test_storage_migration.py` must keep passing.

## 7. Known issues (found in this audit)

| # | Issue | Impact | V2 resolution |
| :-- | :-- | :-- | :-- |
| 1 | `ui.py` is a 3548-line monolith mixing 14 views + glue logic | unmaintainable; violates "no business logic in UI" | split into `ui/` package (Phase 6) |
| 2 | Controller is single-pass: one extraction → one route → tools | multi-step requests ("move X to Friday" = find+update+replan) are hard-coded per-intent, not looped | implement real agent loop with budgets/guards (Phase 2) |
| 3 | No conversation persistence; actions only in a capped `tool_log` | no AgentConversation/AgentAction records (spec §9) | memory engine v4 schema (Phase 5) |
| 4 | `focus_sessions` are daily aggregates — no hourly buckets or per-session records | productive-period detection (spec §7) impossible from existing data | additive hourly buckets + per-session records (Phase 5) |
| 5 | Planner is single-day only | "due next Thursday" cannot be spread across days; deadline feasibility unchecked beyond today | multi-day planner (Phase 4) |
| 6 | Priority scoring ignores goal relevance and historical completion patterns | spec §6 planning factors incomplete | extend `task_priority` (Phase 4/5) |
| 7 | ~12 official tools missing (decompose_task, detect_task_subject, reschedule_task, detect_schedule_conflicts, create/update_schedule, get_daily_schedule, decompose_goal, track_goal_progress, get_task_completion_history, compare_estimated_actual_duration, analyze_productivity_patterns, estimate_task_duration) | spec §5 tool catalog incomplete | Phase 2/3/4/5 |
| 8 | 1780 junk files tracked in git: a committed `venv/` (built on the original author's machine, Python 3.12, path `/home/jahinhasan/...`) + Android debug logs; pack ≈ 123 MiB | clone bloat, non-portable venv | **fixed in this audit**: untracked from index on `develop/v2-agent-architecture` (history untouched) |
| 9 | No typed domain models or repository abstraction; `logic.py` mutates dicts directly | storage can't evolve without touching every layer (spec §9) | pydantic models + repository facade (Phase 1) |
| 10 | Legacy cloud-parser deps (`groq`, `openai`, `google-genai`) in requirements | attack surface + install weight for an offline-first app | move to extras (`pip install .[cloud-import]`), documented (Phase 1) |
| 11 | `ace_integration.py` skillbook overlaps the agent memory | two "learning" stores, one barely used | consolidate into memory engine; keep file import compat (Phase 5) |
| 12 | Docs: no V1_AUDIT / AGENT_DESIGN / IMPLEMENTATION_PLAN | Phase 0 deliverables missing | this document set |
| 13 | `focus_agent/controller.py` imports `re` mid-file and reaches into `tools._find_task_fuzzy` / `logic.update_task_logic` directly | layering violations (controller bypasses the tool boundary it enforces for the LLM) | controller must use tools/repositories only (Phase 2) |
| 14 | Evaluation covers extraction/subjects/scheduling/tools/estimation, but not adherence, deadline-handling breadth, or memory-effectiveness deltas | spec §12 metrics incomplete | Phase 7 |

## 8. Recommended V2 architecture (summary)

Detailed in [ARCHITECTURE.md](ARCHITECTURE.md) and [AGENT_DESIGN.md](AGENT_DESIGN.md):

1. Keep the 8-layer shape, but insert: an **AgentLoop** (multi-step, budgeted) inside
   the controller, a **typed domain-model layer** with **repository services**
   between tools and `logic.py`, and a **memory engine** with conversational,
   behavioral, and planning stores.
2. Grow the tool registry from 24 → the official catalog (~36 tools) with the same
   validation/permission/confirmation shell.
3. Upgrade the planner to deadline-aware multi-day scheduling that reuses the
   existing deterministic day-builder as its inner step.
4. Migrate storage v3 → v4 additively (agent memory, hourly focus buckets,
   schedule blocks, conversations/actions) with the existing backup machinery.
5. Split `ui.py` into a package; render real loop step events in the chat view.
6. Extend `evaluate.py` to cover all 8 official metrics.

## 9. Verification performed during this audit

- Cloned fresh at `c3535cb4`; inspected history (`git log`), structure, all core
  modules (`controller`, `llm`, `tools`, `schemas`, `extractor`, `scheduler`,
  `estimator`, `subjects`, `memory`, `dates`, `goals`, `storage`, `logic`, `ui`
  structure, legacy `ai_parser`/`ace_integration` usage).
- Created a clean venv on this machine (Python 3.14.9): `pytest tests/ -q` →
  **128 passed** (the 1 previously-skipped live-Ollama test now runs because the
  daemon is up).
- `python evaluate.py` → **38/38 (100%)** deterministic benchmark.
- Live LLM check: Ollama `qwen3:4b` installed locally; JSON-mode chat round-trip OK.
- Git hygiene: untracked 1778 `venv/` files + 2 Android debug logs (index-only
  change; no history rewrite), restored the legitimate Flutter test that was
  initially swept up.
