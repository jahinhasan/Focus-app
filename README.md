# ✦ Focus Agent V2 — Intelligent Agent-Based Student Productivity System

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Ollama](https://img.shields.io/badge/LLM-Auto--Hybrid_(Local_Ollama_%2B_Online_Knowledge)-654FF0)](https://ollama.com)
[![Languages](https://img.shields.io/badge/NLU-English_%7C_Bangla_%7C_Banglish-059669)](#3-natural-language-commands-english--banglish--%E0%A6%AC%E0%A6%BE%E0%A6%82%E0%A6%B2%E0%A6%BE)
[![Tests](https://img.shields.io/badge/Tests-230_Passing-brightgreen)](#8-running-tests--evaluation-benchmark)
[![Benchmark](https://img.shields.io/badge/Benchmark-49%2F49_(100%25)-success)](docs/EVALUATION.md)

**Focus Agent V2** is an **Agent-Based Intelligent Student Productivity Management System** built with Python, CustomTkinter, Pydantic, and an **Auto-Hybrid AI Engine** (Local Ollama `qwen3:4b` + Live Online Topic Knowledge + Deterministic NLU).

Unlike ordinary to-do lists or simple chatbots, Focus Agent V2 uses a **structured autonomous AI agent loop** that understands natural-language instructions in **English, বাংলা (Bengali), and Banglish**, automatically detects academic subjects from your class routine, generates **full learning roadmaps with milestones + Day-Wise Dashboard study sessions**, imports course syllabi from PDFs, accepts voice commands, calibrates time estimates from your historical completion data, and builds conflict-free daily study schedules around your classes and deadlines.

---

## 📑 Table of Contents

1. [Key Features](#-1-key-features)
2. [One-Click Auto-Setup & Launch (Windows & Linux)](#-2-one-click-auto-setup--launch-windows--linux)
3. [Natural-Language Commands (English, Banglish & বাংলা)](#-3-natural-language-commands-english--banglish--বাংলা)
4. [AI Agent Architecture & Workflow](#-4-ai-agent-architecture--workflow)
5. [Project Directory Structure](#-5-project-directory-structure)
6. [Workspace Views Overview](#-6-workspace-views-overview)
7. [How to Customize or Extend the Agent](#-7-how-to-customize-or-extend-the-agent)
8. [Running Tests & Evaluation Benchmark](#-8-running-tests--evaluation-benchmark)
9. [Data Storage & Migration Safety](#-9-data-storage--migration-safety)

---

## ✨ 1. Key Features

- **⚡ True One-Click Auto-Installer & Launcher (`run_windows.bat` & `run_linux.sh`)**:
  - Automatically creates the Python virtual environment (`.venv`), installs all Python dependencies (`requirements.txt`), installs & starts **Ollama**, pulls the local **`qwen3:4b`** AI model if missing, and launches the app with a single click!
- **🌐 Auto-Hybrid AI Routing (Local LLM + Live Online Knowledge — Zero API Key Required)**:
  - Automatically combines local `Ollama (qwen3:4b)` inference with live online encyclopedic knowledge (Wikipedia REST API) for any study topic or roadmap without requiring the user to manually switch providers or pay for API keys.
  - Also supports optional cloud acceleration (`GROQ_API_KEY`, `GEMINI_API_KEY`, or `OPENAI_API_KEY`) automatically when present in environment variables.
- **🎯 Smart Goal Roadmaps + Automatic Day-Wise Dashboard Scheduling**:
  - Say *"ami networking shikte cai amk a full milestone soho banay dao"* or *"I want to learn Machine Learning"* — the agent creates a 6-milestone curriculum in **Goals & Roadmaps** AND automatically schedules **Day 1 (Today), Day 2 (Tomorrow), Day 3...** study tasks directly onto your **Dashboard**!
- **📄 Syllabus PDF Import & 🎤 Multilingual Voice Input**:
  - Upload any Course Syllabus or Assignment `.pdf` / `.docx` / `.txt` in the AI Agent Console (`📄 Syllabus PDF`) to automatically generate a Goal Roadmap and Day-Wise study tasks.
  - Click `🎤 Voice` on the Dashboard or AI Agent Console to speak commands in Bangla or English.
- **🎓 Smart Exam Countdown & Conflict-Free Daily Planner (`.ics` Export)**:
  - Automatically detects upcoming exams (`exam`, `midterm`, `final`, `porikkha`, `পরীক্ষা`) and displays a live **Exam Countdown Banner** on your Dashboard.
  - Generates conflict-free daily study blocks around your class routine and exports schedules to `.ics` (Google Calendar / Outlook / Apple Calendar) in one click.
- **🧠 Historical Learning & Duration Calibration**:
  - Tracks estimated vs. actual completion time per subject and automatically adjusts future study time estimates (`focus_agent/estimator.py`) as it learns your real working pace.
- **🎨 Responsive Modern Academic UI (Light & Dark Mode)**:
  - Live reactive typography (`CTkFont`), adaptive sidebar (always keeping icon + label readable), responsive KPI grid (`2×2` on compact screens, `1×4` on wide screens), and 1-click **`▶ Start`** timer integration from both Task Cards and Daily Planner slots.

---

## 🚀 2. One-Click Auto-Setup & Launch (Windows & Linux)

When you clone this project on **any new Windows or Linux computer**, you do **NOT** need to manually install packages or download the LLM — a single script does everything automatically!

### ⚡ Option A: One-Click Automatic Setup & Run (Recommended)

#### 🐧 On Linux / macOS:
```bash
git clone https://github.com/jahinhasan/Focus-app.git
cd Focus-app
./run_linux.sh
```

#### 🪟 On Windows (Double-Click or Command Prompt):
Simply **double-click `run_windows.bat`** in File Explorer, or run in Command Prompt / PowerShell:
```cmd
git clone https://github.com/jahinhasan/Focus-app.git
cd Focus-app
run_windows.bat
```

#### 🐍 Universal Cross-Platform Python Bootstrap:
```bash
python3 setup_and_run.py
```
*(What it does automatically: creates `.venv` → installs `requirements.txt` → installs & starts `Ollama` → pulls `qwen3:4b` local AI model → launches `main.py`!)*

---

### 🛠️ Option B: Manual Step-by-Step Setup

#### Step 1: Clone the Repository
```bash
git clone https://github.com/jahinhasan/Focus-app.git
cd Focus-app
```

#### Step 2: Create and Activate a Virtual Environment
- **Linux / macOS:**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```
- **Windows (Command Prompt / PowerShell):**
  ```cmd
  python -m venv .venv
  .venv\Scripts\activate
  ```

#### Step 3: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### Step 4: Set Up Local AI with Ollama *(Automatic via `setup_and_run.py`, or manual below)*
1. Download and install [Ollama](https://ollama.com/download).
2. Pull the default lightweight model (`qwen3:4b`):
   ```bash
   ollama pull qwen3:4b
   ```
3. Launch Focus Agent V2:
   ```bash
   python main.py
   ```

---

## 💬 3. Natural-Language Commands (English, Banglish & বাংলা)

You can type commands in the **Dashboard Quick Agent Command Bar** or in the **🤖 AI Agent Console**:

| Language | Example Prompt You Can Type | What Focus Agent V2 Does |
| :--- | :--- | :--- |
| **English** | `"I have a Data Communication assignment due next Thursday. It is difficult and will take 3 hours."` | Extracts title, deadline, `180m` duration, `Hard (3)` difficulty, matches subject `Data Communication`, and creates the task |
| **English** | `"Move my Data Communication assignment to Friday"` | Finds the existing task and updates its deadline to Friday |
| **English** | `"Plan my day"` or `"I have 3 hours free tomorrow, plan my tasks"` | Generates a conflict-free schedule around your classes |
| **English** | `"I want to learn Machine Learning in 6 weeks"` | Creates a long-term goal with weekly milestones |
| **Banglish** | `"amar kal math assignment joma dite hobe rat 8 tar modhe"` | Creates `'Math Assignment'`, Subject=`Mathematics`, Due=`Tomorrow`, Due Time=`20:00` |
| **Banglish** | `"porshu dbms lab report dite hobe bikal 5 tay, 2 ghonta lagbe, kothin"` | Creates `'Dbms Lab Report'`, Subject=`Database Systems`, Due=`Day after tomorrow`, Time=`17:00`, Duration=`120m`, Difficulty=`Hard` |
| **Banglish** | `"math assignment porshu kore dao"` | Reschedules the existing Math Assignment to the day after tomorrow |
| **Banglish** | `"math assignment shesh korechi"` | Marks the Math Assignment as completed and awards XP |
| **Banglish** | `"ajker plan koro"` | Generates today's study schedule |
| **বাংলা** | `"আগামীকাল গণিত অ্যাসাইনমেন্ট জমা দিতে হবে রাত ৮টার মধ্যে, ২ ঘণ্টা লাগবে"` | Creates the task with Subject=`Mathematics`, Due=`Tomorrow`, Time=`20:00`, Duration=`120m` |
| **বাংলা** | `"আজকের প্ল্যান করো"` | Builds today's conflict-free study plan |

---

## 🧠 4. AI Agent Architecture & Workflow

```text
User Input (English / Banglish / বাংলা)
   │
   ▼
1. AgentController.handle() ────► [focus_agent/controller.py]
   │  (Builds compact context: today, routine subjects, open tasks, recent turns)
   │
   ├──► 2. Extractor.extract() ─► [focus_agent/extractor.py]
   │       ├─ Local LLM JSON Extraction + Anti-Hallucination Guard ([focus_agent/llm.py])
   │       ├─ Natural Date & Time Parser ([focus_agent/dates.py])
   │       └─ Routine & Alias Subject Matcher ([focus_agent/subjects.py])
   │
   ├──► 3. Duration Estimator ──► [focus_agent/estimator.py]
   │       (Calibrates duration using historical estimated-vs-actual completion ratios)
   │
   ├──► 4. Tool Execution ──────► [focus_agent/tools/]
   │       ├─ Task Tools        ([focus_agent/tools/tasks.py])
   │       ├─ Schedule Tools    ([focus_agent/tools/schedule.py] + [focus_agent/scheduler.py])
   │       ├─ Goal Tools        ([focus_agent/tools/goals_tool.py] + [focus_agent/goals.py])
   │       └─ Analytics Tools   ([focus_agent/tools/analytics.py])
   │
   └──► 5. Memory & Audit Log ──► [focus_agent/memory.py]
           (Saves conversation turn, action audit log, and returns AgentReply + Agent Trace)
```

---

## 📂 5. Project Directory Structure

```text
Focus-app/
├── main.py                      # Application entry point (launches FocusApp)
├── logic.py                     # Core task, routine, XP, timer, and analytics operations
├── models.py                    # Pydantic v2 domain models & schema validation
├── repositories.py              # Validated data access repositories
├── storage.py                   # Atomic JSON persistence, v3→v4 migration & auto-backups
├── evaluate.py                  # Official 8-metric academic benchmark runner (49/49 checks)
├── requirements.txt             # Python dependencies
├── setup.sh / setup.bat         # One-command setup scripts for Linux/macOS and Windows
│
├── focus_agent/                 # 🧠 V2 AI Agent Core Package
│   ├── controller.py            # Main AgentController loop, context builder & tool dispatcher
│   ├── extractor.py             # Hybrid LLM + deterministic NLU (English, বাংলা, Banglish)
│   ├── dates.py                 # Natural date & time-of-day parser (English, বাংলা, Banglish)
│   ├── subjects.py              # Class-routine subject detector & academic alias matcher
│   ├── scheduler.py             # Priority-based conflict-free daily & multi-day planner
│   ├── estimator.py             # Historical duration learning & pace calibration engine
│   ├── goals.py                 # Long-term goal decomposition & milestone progress tracker
│   ├── memory.py                # Conversation history, tool action audit log & plan log
│   ├── llm.py                   # Ollama & OpenAI-compatible HTTP client
│   ├── prompts.py               # System prompts for structured extraction & agent replies
│   ├── schemas.py               # Dataclasses (ExtractionResult, PlanSlot, DayPlan, AgentReply)
│   ├── media_import.py          # Routine image OCR, PDF summary & AI subtask breakdown
│   └── tools/                   # Structured Agent Tools
│       ├── registry.py          # ToolRegistry with schema validation & idempotency
│       ├── tasks.py             # create_task, update_task, complete_task, delete_task
│       ├── schedule.py          # plan_day, check_conflicts, schedule block tools
│       ├── goals_tool.py        # create_goal, decompose_goal, milestone tools
│       └── analytics.py         # productivity summary, estimation accuracy & insights tools
│
├── ui/                          # 🖥️ Responsive CustomTkinter Desktop UI Package
│   ├── app.py                   # Main window, responsive sidebar, live timer & view router
│   ├── theme.py                 # Academic Light/Dark palette & reactive CTkFont scaling
│   ├── widgets.py               # Responsive SidebarButton, XPBar, TimePicker, DaySelector
│   ├── views_today.py           # Dashboard: Quick Agent Bar, Morning Briefing, KPIs, Tasks
│   ├── views_chat.py            # AI Agent Console with live Agent Reasoning Trace
│   ├── views_planner.py         # Daily Planner view with 1-click Start Focus
│   ├── views_routine.py         # Weekly Class Routine manager & OCR/text import
│   ├── views_goals.py           # Goals & Roadmaps view with milestone tracking
│   ├── views_misc.py            # Subject Vault & document summarizer
│   ├── views_history.py         # Unified Analytics, 365-Day Heatmap, Memory & Live Benchmark
│   └── views_settings.py        # LLM provider/model config, Pomodoro, Study Window & Backups
│
├── tests/                       # 🧪 Automated Pytest Suite (227 unit & integration tests)
└── docs/                        # 📖 Architecture & Academic Documentation
    ├── V1_AUDIT.md              # Repository audit of V1 and migration strategy
    ├── ARCHITECTURE.md          # System architecture & layered design
    ├── AGENT_DESIGN.md          # Agent loop, guardrails, tool schemas & memory design
    ├── IMPLEMENTATION_PLAN.md   # Phased engineering implementation plan
    └── EVALUATION.md            # Benchmark methodology & results
```

---

## 🖥️ 6. Workspace Views Overview

1. **🏠 Dashboard (`views_today.py`)**:
   - **Quick Agent Command Bar** with instant **`🔍 Agent Trace`**, **Proactive Morning Briefing & Deadline Radar**, **4 Responsive KPI Cards**, **Today's Schedule & Upcoming Deadlines**, and **Daily Habits** strip.
2. **🤖 AI Agent Console (`views_chat.py`)**:
   - Full conversational workspace with quick-prompt chips, provider status indicator, and transparent **`🔍 Agent Trace`** under every agent reply.
3. **🗓️ Daily Planner (`views_planner.py`)**:
   - Generates conflict-free study slots around your fixed classes, explains *why* each task was prioritized, and lets you start the focus timer directly from any slot (`▶ Start Focus`).
4. **📅 Class Routine (`views_routine.py`)**:
   - Weekly timetable grid with manual entry and AI/OCR import from routine images or text.
5. **🎯 Goals & Roadmaps (`views_goals.py`)**:
   - Long-term academic/learning goals broken down into trackable milestones that convert into actionable tasks in 1 click.
6. **📚 Subject Vault (`views_misc.py`)**:
   - Organizes PDFs, notes, and study materials per subject with built-in AI document summarization.
7. **📊 Analytics & Insights (`views_history.py`)**:
   - Includes the **Live Agent Evaluation Benchmark Card**, **Daily Focus Bar Chart**, **365-Day Focus Consistency Heatmap**, **Subject Breakdown**, **Estimation vs. Reality Calibration Insights**, and **Daily Completion Log**.
8. **⚙️ Settings (`views_settings.py`)**:
   - Configure Local Ollama / Cloud LLM provider, test connection, customize Pomodoro durations, set daily study windows, and restore automatic data backups.

---

## 🛠️ 7. How to Customize or Extend the Agent

- **Add New Subject Aliases:** Edit `SUBJECT_ALIAS_GROUPS` in [`focus_agent/subjects.py`](focus_agent/subjects.py).
- **Add New Keywords / Intents (English, Banglish, or বাংলা):** Edit pattern lists in [`focus_agent/extractor.py`](focus_agent/extractor.py) and [`focus_agent/dates.py`](focus_agent/dates.py).
- **Register a New Agent Tool:**
  1. Write a tool function returning `ToolResult` in `focus_agent/tools/`.
  2. Register it in `default_registry()` inside [`focus_agent/tools/registry.py`](focus_agent/tools/registry.py).
  3. Dispatch it in `_dispatch()` inside [`focus_agent/controller.py`](focus_agent/controller.py).
- **Customize Daily Planner Priority Weights:** Modify `priority_score()` in [`focus_agent/scheduler.py`](focus_agent/scheduler.py).
- **Modify System Prompts:** Edit `EXTRACTION_SYSTEM_PROMPT` and `CHAT_SYSTEM_PROMPT` in [`focus_agent/prompts.py`](focus_agent/prompts.py).

---

## 🧪 8. Running Tests & Evaluation Benchmark

Run the full automated test suite (227 tests across NLU extraction, Banglish/Bengali parsing, date/time resolution, subject detection, scheduler, estimator, tools, and storage):

```bash
.venv/bin/python -m pytest tests/ -q
```

Run the official academic evaluation benchmark (`49/49` deterministic checks, or `--live` with Ollama running):

```bash
.venv/bin/python evaluate.py
.venv/bin/python evaluate.py --live
```

| Evaluation Area | Score |
| :--- | :--- |
| Task Extraction Accuracy | 100% |
| Deadline & Time Resolution | 100% |
| Subject Classification Accuracy | 100% |
| Conflict-Free Scheduling Quality | 100% |
| Ambiguity & Missing-Deadline Handling | 100% |
| Historical Duration Calibration | 100% |
| Verified Tool Execution | 100% |
| **Overall Benchmark Score** | **49 / 49 (100.0%)** |

---

## 🗄️ 9. Data Storage & Migration Safety

- User data is stored locally in `data.json` (excluded from Git via `.gitignore` so personal tasks and API keys are never pushed).
- Upgrading from V1 (`schema v3`) to V2 (`schema v4`) is automatic and non-destructive, creating a timestamped backup in `backups/` before migrating.

---

## 📜 License

MIT License — Designed and built as an Intelligent Agent-Based Student Productivity System.
