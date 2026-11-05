# 🎯 Focus Agent V2 — Agent-Based Student Productivity System

[![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Ollama](https://img.shields.io/badge/LLM-Ollama_(local)-654FF0)](https://ollama.com)
[![Tests](https://img.shields.io/badge/tests-199_passing-brightgreen)](#-evaluation-measured-not-claimed)
[![Benchmark](https://img.shields.io/badge/benchmark-49%2F49_det_·_59%2F59_live-success)](docs/EVALUATION.md)

A personal academic productivity **agent** — not a chatbot bolted onto a to-do
list. You talk to it in plain English; an agent loop decides steps, executes
**validated tools**, verifies its own writes, learns your real working pace
from focus history, and plans your days around classes, fixed commitments and
deadlines — all **locally via Ollama**, so your data never leaves your machine.

> Everything V1 had is still here: the Today dashboard, class routine with photo
> import, Smart Vault, XP/levels, habits, Pomodoro timer, and the Flutter mobile
> companion. V2 adds the deep agent layer — nothing was removed, and your
> `data.json` upgrades in place (schema v3 → v4, additive, backed up first).

---

## ✨ What the agent can do

| You say | It does |
| :--- | :--- |
| "I have a Data Communication assignment due next Thursday. It is difficult and will probably take 3 hours. I also have a networking class tomorrow." | Extracts **both** items, correct relative dates, difficulty/importance, creates verified tasks, flags unknown subjects instead of guessing |
| "Move my networking assignment to Friday." | Resolves the task (asks *which* when ambiguous), updates the deadline, proposes a rebuilt day — verified before reporting |
| "I have three hours free tomorrow. Plan my pending tasks." | Multi-day planner honors the **exact 180-min capacity**, skips classes and fixed blocks, reports anything that couldn't fit and why |
| "I have a class from 10 AM to 12 PM tomorrow. Don't schedule anything during that time." | Creates a protected schedule block the planner never books over |
| "I want to learn Python in two months. Create a roadmap." | Goal + milestone roadmap spread to the target date (`decompose_goal`) |
| "What should I prioritize?" / "Analyze my productivity over the last seven days." | Transparent priority reasons; learned stats with disclosed sample basis |
| "I completed the assignment in four hours, although the estimate was two hours." | Records the actual time — the **estimator learns** your realism ratio per subject/difficulty |

The agent **asks instead of guessing**: deadline-sensitive tasks without a date
get a follow-up question that persists across turns; ambiguous task references
trigger a choice; unknown values stay null and are never invented. Destructive
actions always require explicit confirmation.

## 🤖 The agent architecture (the actual product)

```text
user message
  → context pack (compact, privacy-preserving)
  → understanding (deterministic parser + local LLM extraction, merged)
  → step plan → AGENT LOOP: validate → execute tool → verify by read-back
                → observe → repeat (budgeted: max 6 steps / 4 LLM calls)
  → honest event stream + reply composed only from real tool results
```

- **47 registered tools** (tasks, subjects/routine, schedule, goals, analytics)
  with typed schemas, permission classes, confirmation policy, call-ID
  idempotency, and an audit log. The LLM never touches storage.
- **Deterministic-first**: parsing, scheduling, estimation and analytics work
  with the model offline; `provider=none` keeps every feature usable.
- **Learning, disclosed**: duration realism (median ratio per subject/difficulty,
  cold-start labeled as default), productive-hour detection (needs 45 min of
  attributed focus), schedule adherence (needs committed plans), missed-task
  carry-overs. Every learned number reports `{basis, samples, reliable}`.

## 🚀 Getting started

| OS | One command |
| :--- | :--- |
| Windows | double-click `setup.bat` |
| Linux / macOS | `bash setup.sh` |

Manual:

```bash
git clone https://github.com/jahinhasan/Focus-app.git
cd Focus-app
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Local AI (recommended): install [Ollama](https://ollama.com/download), then
`ollama pull qwen3:4b` (any Qwen tag works; configurable in Settings → AI).
Verify: `curl http://localhost:11434/api/tags`. No API keys, no cloud.

Optional environment variables (see [.env.example](.env.example)):
`OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `FOCUS_LLM_PROVIDER`
(`ollama`/`online`/`none`), `FOCUS_TZ`, `ONLINE_LLM_API_KEY` (env-only, never
stored), loop budgets `FOCUS_AGENT_MAX_STEPS` / `FOCUS_AGENT_MAX_LLM_CALLS` /
`FOCUS_AGENT_MAX_TOOL_CALLS`. Legacy cloud routine-import is now an optional
extra (`pip install groq openai google-genai`); the agent never needs it.

## 📊 Evaluation (measured, not claimed)

Full methodology and per-section detail: [docs/EVALUATION.md](docs/EVALUATION.md).

| Metric (spec §12) | Deterministic | Live `qwen3:4b` |
| :--- | :--- | :--- |
| Task extraction accuracy | 32/32 | 32/32 |
| Deadline extraction accuracy | 11/11 | 11/11 |
| Subject classification accuracy | 5/5 | — (deterministic matcher) |
| Scheduling quality | 11/11 checks | — (deterministic planner) |
| Deadline handling (asks, never guesses) | 4/4 | 4/4 |
| Duration estimation error | 51 min → **0 min** with history (truth 120) | — |
| Tool execution success | 11/11 | 11/11 |
| Memory effectiveness | verified (51→0 min; adherence from real records) | — |
| **Overall benchmark** | **49/49 (100%)** | **59/59 (100%)** |

```bash
.venv/bin/python -m pytest tests/ -q     # 199 tests, no LLM needed
.venv/bin/python evaluate.py             # deterministic benchmark
.venv/bin/python evaluate.py --live      # + real model pass
```

## 🗄️ Your data & migration safety

- Human-readable `data.json`, local-first. Schema **v4**: additive migration
  from v3 with a timestamped backup in `backups/` before the first save
  (Settings → Data & Backups → Restore to roll back). Corrupt files are
  quarantined, never overwritten — verified by tests.
- New in v4: schedule blocks, per-session focus records, hourly focus buckets,
  agent conversations/actions (bounded), task reschedule history.

## 🏗️ Documentation & architecture

- [docs/V1_AUDIT.md](docs/V1_AUDIT.md) — audit of the inherited codebase
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — layers, layout, models, invariants
- [docs/AGENT_DESIGN.md](docs/AGENT_DESIGN.md) — loop, guards, full tool registry, memory
- [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) — phases, decisions log
- [docs/EVALUATION.md](docs/EVALUATION.md) — metrics & methodology

```text
UI (ui/ package) → AgentController (loop) → LLM (Ollama) → structured steps
                          │                       │
                          ▼                       ▼
        validated tools (47) → repositories → typed models → data.json (v4)
                          │
        planner (multi-day, deadline-aware) ← patterns (learned, disclosed)
```

## 📱 Mobile companion (Flutter)

```bash
cd android && flutter pub get
flutter run --dart-define=GEMINI_API_KEY=<key>   # optional; OfflineBrain works without
```

## 📜 License

MIT — built for students who value their time.
