# Focus V2 — Architecture

This document describes how the To Do Agent is built: the layers, the contracts
between them, and the invariants that keep the agent safe and honest.

## Layer map

```text
┌──────────────────────────────────────────────────────────────────┐
│ 1. UI / chat (ui.py, CustomTkinter)                              │
│    async worker + confirmation bridge, plan/goal/settings views  │
└──────────────┬───────────────────────────────────────────────────┘
               │ AgentController.handle(text) -> AgentReply
┌──────────────▼───────────────────────────────────────────────────┐
│ 2. Controller (focus_agent/controller.py)                        │
│    intent routing, fast paths, provider lifecycle, disclosures   │
└──────┬──────────────────┬───────────────────────┬────────────────┘
       │                  │                       │
┌──────▼───────┐  ┌───────▼────────┐  ┌──────────▼──────────────┐
│ 3. LLM       │  │ 4. Extraction  │  │ 5. Tools                │
│ abstraction  │  │ (extractor.py) │  │ (tools.py + schemas.py) │
│ (llm.py)     │  └───────┬────────┘  └──────────┬──────────────┘
└──────┬───────┘          │                      │
       │           ┌──────▼────────┐  ┌──────────▼──────────────┐
       │           │ 6. Deterministic parsing & scheduling           │
       │           │ (dates.py, subjects.py, scheduler.py)           │
       │           └───────────────┘  └──────────┬──────────────┘
┌──────▼──────────────────────────────────────────▼───────────────┐
│ 7. Memory & analytics (memory.py, estimator.py, logic.py)       │
│    audit log, idempotency cache, estimation, streaks, XP        │
└──────────────┬───────────────────────────────────────────────────┘
               │ only via storage.py (atomic writes, migration)
┌──────────────▼───────────────────────────────────────────────────┐
│ 8. Optional online research (OnlineProvider, env-keyed)         │
└──────────────────────────────────────────────────────────────────┘
```

## 1. UI layer

The chat view runs each agent turn on a worker thread so the tkinter main loop
never blocks on a 15-second model call. Confirmations bridge worker → UI →
worker through a `queue.Queue` so destructive tool calls always get a real
user decision (or none, if no UI exists — the tool then refuses).

New views: **Planner** (day plan with per-slot reasons, apply button), **Goals**
(progress bars, milestone checkboxes, editable roadmaps), AI **Settings**
(provider, endpoint, model, Test Connection, study window, backups), estimation
analytics in Reports, and a streak line in History.

## 2. Controller

`AgentController.handle()` is the single entry point. It answers greetings and
stats/class queries deterministically (no model round-trip), then classifies
intent, extracts, and routes to handlers that call tools. Providers are
injectable for tests (`provider=`, `now=`).

Routing table: `add_task` → create per extracted task (+ follow-up question if
the extraction raised one), `complete/delete` → `_route_task_ref`, `reschedule`
→ move + `reschedule_day`, `plan_day` → uncommitted plan proposal, `goal` →
create + roadmap draft, `chat` → local answer or disclosed online research.

## 3. LLM abstraction

Providers implement `chat()` / `chat_json()` / `status()` / `capabilities()`.
`OllamaProvider` (primary) posts to `/api/chat` with `think:false` (thinking
models like qwen3 emit `<think>` blocks otherwise) and `format:"json"` in
json mode. `OnlineProvider` reads its key **only** from the environment, sends
it exclusively as an Authorization header, and is opt-in. `NullProvider`
backing provider="none". All failure modes — unreachable, timeout, 404 model
missing, 429/503 busy, malformed output, empty output — map to typed errors
(`ProviderUnavailable`, `ModelNotInstalled`, `BadResponse`) that the UI can
explain. Env vars override stored settings; `FOCUS_LLM_PROVIDER=none` forces
fully-deterministic operation.

## 4. Structured extraction

Extraction always runs the deterministic parser (`extract_deterministic`) and
tries the LLM pass (`extract_with_llm`). Merge rules favor evidence:

- LLM fields fill gaps in the deterministic result; deterministic keyword dates
  beat model-inferred dates on conflict (measured: qwen3 misresolved "tonight"
  and "next wednesday"; the resolver does not).
- An LLM intent outside the schema ("unknown") is rescued by the deterministic
  classifier.
- Every LLM field is validated independently (`validate_extracted_task`):
  invalid dates/durations/intensities become null with a warning — never
  executed, never invented.

Material ambiguity produces follow-up questions: deadline-sensitive keywords
(submit, exam, application, register, …) with no date ask "When is this due?"
instead of guessing.

## 5. Tool layer

26 tools registered with typed schemas (`ToolSpec`). `execute_tool` runs an
ordered pipeline: unknown-tool rejection → idempotency (`call_id` dedup cache
in `agent_memory.executed_calls`) → schema validation (unknown arguments
rejected) → confirmation gate (destructive/committing tools, with a
`confirm_fn` for conditional cases) → handler → audit log. Any handler crash
becomes a `ToolResult` error — the agent never raises into the UI. The model
never sees a database connection or shell; the only path to storage is these
handlers.

## 6. Deterministic core

- `dates.py` — timezone-aware relative dates (today/tonight/tomorrow/next
  weekday/in-N-days/23-11), rule: weekday = next occurrence strictly after
  today; ambiguous numeric dates (10-11) are ignored without a date keyword.
- `subjects.py` — confidence-scored matching (exact 1.0 / contains 0.9 /
  token-overlap / fuzzy) with AUTO threshold 0.82; class routine titles count
  as subject evidence ("CSE 3202" → that class's subject); below threshold the
  agent flags instead of assigning.
- `scheduler.py` — urgency buckets (overdue 40 … none 0) + importance/difficulty
  scoring with human-readable reasons; earliest-fit placement inside the study
  window minus class intervals; long tasks split into ≤90-min chunks with
  breaks; today's past is clipped; done/started slots preserved on reschedule;
  overload is reported with alternatives, never silently dropped; tasks without
  estimates are explained, not scheduled.

## 7. Memory & analytics

`agent_memory` (capped logs) records every tool execution and plan for audit.
The estimator learns a median actual/estimated ratio per subject+difficulty
(≥3 samples), falls back subject → difficulty → global median → a disclosed
default ×1.15, with a created-at leakage guard so future completions never
influence past predictions. Streaks compute from history day keys.

## 8. Online research (opt-in)

Only when configured via env and the user's message needs research. The reply
discloses online use. Unavailable → local fallback answer, clearly labeled.

## Storage & migration

Flat `data.json`, atomic writes (`.tmp` + `os.replace`). Migration to schema
v3 is additive (new fields defaulted, none removed) with a timestamped backup
in `backups/` (gitignored). Corrupt files are moved to
`data.json.corrupt-<ts>`, never overwritten. Rollback: restore a backup from
Settings → Data & Backups, or copy the file manually.

## Security invariants

- API keys: environment variables only; never in data files, task records, or
  logs; the online adapter sends the key only as an Authorization header.
- Model output is untrusted: validated field-by-field, JSON extracted
  defensively (fences, balanced-brace scan), and executed only through
  schema-checked tools with confirmation for destructive actions.
- Prompt-injection containment: user text is data, not instructions; the chat
  route never chains destructive tools, verified by test.
- Local-first: with provider=none or Ollama down, the entire app remains
  functional.
