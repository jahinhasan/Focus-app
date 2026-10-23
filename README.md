# 🎯 Focus — To Do Agent (V2)

[![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Ollama](https://img.shields.io/badge/LLM-Ollama_(local)-654FF0)](https://ollama.com)
[![Tests](https://img.shields.io/badge/tests-128_passing-brightgreen)](#-tests--evaluation-measured-not-claimed)

**V1's Focus Dashboard, upgraded into an agentic productivity system.** You talk to it
in plain English; it understands, asks when unsure, and actually does the work —
creating tasks, reading your class routine, planning your day around classes, and
learning your real working pace — all with a **local LLM via Ollama** so your data
never leaves your machine.

> Everything V1 had is still here: the Today dashboard, class routine with
> photo import, Smart Vault, gamified XP/levels, habits, Pomodoro/stopwatch
> timer, and the Flutter mobile companion. V2 adds the agent layer on top —
> nothing was removed, and your existing data.json upgrades in place.

---

## ✨ What the agent can do

| You say | It does |
| :--- | :--- |
| "Tomorrow submit my AI assignment; it will take about two hours" | Creates the task with due date **2026-10-24**, ~120 min, subject auto-matched from your routine |
| "I have an exam next Monday; prepare a revision plan" | Proposes a class-aware day plan you can apply with one click |
| "Move the unfinished database task to my next available study slot" | Finds the task, moves it, rebuilds the rest of the day |
| "I want to learn machine learning by December" | Creates a goal with an editable milestone roadmap |
| "What should I prioritize?" | Explains ranked priorities with transparent reasons |

The agent **asks instead of guessing**: a deadline-sensitive task with no date gets a
follow-up question; an ambiguous subject match is flagged, never silently assigned;
unknown values stay null and are never invented.

---

## 🚀 Getting started

### One-command setup (new PC)

Copy the project folder to any PC, then run **one** command:

| OS | Command |
| :--- | :--- |
| Windows | double-click `setup.bat` (or run it in cmd) |
| Linux / macOS | `bash setup.sh` |

The script creates a virtual environment, installs every requirement, checks
the GUI libraries and Ollama (with exact fix hints if anything is missing),
and launches the app. Re-running it is always safe.

Manual install, if you prefer:

### 1. Install the app

```bash
git clone https://github.com/jahinhasan/Focus-app.git
cd Focus-app
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set up the local AI (Ollama)

1. Install Ollama: <https://ollama.com/download>
2. Pull a model (default is **qwen3:4b** — any Qwen tag works, or edit the model
   field in Settings → AI):

   ```bash
   ollama pull qwen3:4b
   ```

3. Verify:

   ```bash
   ollama list
   curl http://localhost:11434/api/tags
   ```

That's it — no API keys, no cloud accounts. The model runs on your machine.

### 3. Run

```bash
python main.py
```

First launch of the chat view shows the AI provider status. If Ollama isn't
running, the app says so and every feature still works — planning, scheduling,
tools, and analytics are deterministic and never require the model.

### Environment variables (all optional)

| Variable | Purpose | Default |
| :--- | :--- | :--- |
| `OLLAMA_HOST` | Ollama endpoint | `http://localhost:11434` |
| `OLLAMA_MODEL` | Model tag to use | `qwen3:4b` |
| `OLLAMA_TIMEOUT` | Chat timeout (seconds) | `120` |
| `FOCUS_LLM_PROVIDER` | Force provider: `ollama` / `online` / `none` | from Settings |
| `FOCUS_TZ` | IANA timezone for dates/deadlines | `local` |
| `ONLINE_LLM_API_KEY` | **Optional** online adapter (OpenAI-compatible). Env-only; never stored in data files | unset |
| `ONLINE_LLM_BASE_URL` | Online adapter endpoint | `https://api.openai.com/v1` |
| `ONLINE_LLM_MODEL` | Online adapter model | `gpt-4o-mini` |

See [.env.example](.env.example) for annotated placeholders. **Never** put real
keys in data.json, task records, or committed files.

---

## 🧪 Tests & evaluation (measured, not claimed)

```bash
# 128 deterministic tests - no LLM needed, run anywhere
.venv/bin/python -m pytest tests/ -q

# Reproducible benchmark: extraction, subjects, scheduling, tools, estimation
.venv/bin/python evaluate.py

# Same benchmark + extraction through the real local model
.venv/bin/python evaluate.py --live
```

Actual measured results from the last run in this repo
(Ollama `qwen3:4b` on localhost; deterministic reference = built-in parser):

| Area | Deterministic | Live LLM pass |
| :--- | :--- | :--- |
| Extraction (spec examples) | 7/7 | 7/7 |
| Deadline handling (asks, never guesses) | 3/3 | 3/3 (deterministic layer) |
| Subject assignment (incl. refusing to guess) | 5/5 | — |
| Schedule feasibility (overlaps, classes, past, no drops) | 8/8 | — |
| Tool actions (validation, permissions, idempotency) | 11/11 | 11/11 |
| Estimation (learning, generalization, cold start, leakage) | 4/4 | — |
| **Overall** | **38/38 (100%)** | **48/48 (100%)** |

The evaluation is part of CI; numbers are computed at run time, never hand-written.

---

## 🗄️ Your data & migration safety

- Storage stays a human-readable `data.json` (local-first, same as V1).
- First launch after upgrading **migrates in place** to schema v3: additive
  fields only, all V1 values, IDs, and settings are preserved — verified by
  [tests/test_storage_migration.py](tests/test_storage_migration.py).
- Before any migration a **timestamped backup** is written to `backups/`
  (gitignored). Rollback = copy the backup over `data.json` (Settings → Data &
  Backups → Restore).
- Corrupt files are never overwritten: a bad data.json is moved aside to
  `data.json.corrupt-<timestamp>` and a fresh store is served.
- **Important:** if you used the old mobile app, revoke the Gemini API key that
  ships in its git history (`android/lib/ai_parser_port.dart` in older commits)
  — current code reads the key from `--dart-define=GEMINI_API_KEY` instead.

---

## 🏗️ Architecture

Eight modular layers (details and data flow in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)):

```text
UI / chat ─▶ AgentController ─▶ LLM abstraction ─▶ structured extraction
     │              │                  │                     │
     │              ▼                  ▼                     ▼
 memory/analytics ◀─ validated tool execution ◀─ intent + args
                        │
                        ▼
            deterministic scheduler ◀─ class routine / study hours
                        │
                        ▼
              optional online research (disclosed, env-keyed)
```

**Deterministic-first:** parsing, scheduling, estimation, and analytics work with
no model at all; the LLM adds understanding, and its output is always validated
before anything touches your data. On date conflicts, keyword evidence ("tonight",
"next wednesday") wins over model inference.

### Agent tools (validated schema, permission classes)

| Tool | Permission | Confirmation |
| :--- | :--- | :--- |
| `list_tasks`, `get_task`, `list_subjects`, `get_routine`, `get_availability`, `explain_priorities`, `list_goals`, `get_focus_history`, `get_analytics`, `generate_report` | read | — |
| `create_task`, `update_task`, `complete_task`, `reopen_task`, `add_subtask`, `assign_subject`, `add_class`, `record_focus_time`, `create_goal`, `update_goal`, `add_milestone`, `complete_milestone` | write | — |
| `delete_task`, `create_subject`, `generate_daily_plan` (commit), `reschedule_day` | write/destructive | ✅ required |

Every call is schema-validated (unknown arguments rejected), idempotent on
retries via call IDs, audit-logged, and confirmed when destructive. The LLM
never touches storage directly — the only path to your data is through these
tools.

---

## 📱 Mobile companion (Flutter)

```bash
cd android
flutter pub get
flutter run --dart-define=GEMINI_API_KEY=<key>   # optional; OfflineBrain works without
```

---

## 📜 License

MIT — built for students who value their time.
