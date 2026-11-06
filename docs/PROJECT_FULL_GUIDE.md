# 📘 Focus Agent V2 — Complete Project Guide, Architecture, Workflow & Code Reference

> **প্রজেক্টের নাম:** Focus Agent V2 — Intelligent Agent-Based Student Productivity System  
> **ভাষা ও টেকনোলজি:** Python 3.10+, CustomTkinter (Modern Responsive GUI), Pydantic (Schema Validation), Ollama (`qwen3:4b` Local LLM), Wikipedia Live REST API (Online Knowledge), PyPDF, python-docx, SpeechRecognition, Pytest  
> **টেস্ট ও বেঞ্চমার্ক স্ট্যাটাস:** `230/230` Unit Tests Passing (`100%`) · `49/49` Evaluation Benchmark (`100%`)

---

## সূচিপত্র (Table of Contents)

1. [প্রজেক্টের মূল ধারণা (Project Overview)](#১-প্রজেক্টের-মূল-ধারণা-project-overview)
2. [১-ক্লিক ইনস্টলেশন ও রান করার নিয়ম (One-Click Setup & Run)](#২-১-ক্লিক-ইনস্টলেশন-ও-রান-করার-নিয়ম-one-click-setup--run)
3. [প্রজেক্টের ফোল্ডার ও ফাইল স্ট্রাকচার (Full Directory Structure)](#৩-প্রজেক্টের-ফোল্ডার-ও-ফাইল-স্ট্রাকচার-full-directory-structure)
4. [AI Agent-এর সম্পূর্ণ ওয়ার্কফ্লো (End-to-End Agent Workflow)](#৪-ai-agent-এর-সম্পূর্ণ-ওয়ার্কফ্লো-end-to-end-agent-workflow)
5. [Agent-এর প্রতিটি Core Code ফাইলের বিস্তারিত ব্যাখ্যা (Core Code Deep-Dive)](#৫-agent-এর-প্রতিটি-core-code-ফাইলের-বিস্তারিত-ব্যাখ্যা-core-code-deep-dive)
6. [UI (User Interface) ফাইলগুলোর কাজ ও রেসপনসিভ ডিজাইন](#৬-ui-user-interface-ফাইলগুলোর-কাজ-ও-রেসপনসিভ-ডিজাইন)
7. [ডাটাবেস ও স্টোরেজ সিস্টেম (`data.json`, `storage.py`, `logic.py`)](#৭-ডাটাবেস-ও-স্টোরেজ-সিস্টেম-datajson-storagepy-logicpy)
8. [কোথায় কীভাবে কোড পরিবর্তন করবেন? (Developer Customization Guide)](#৮-কোথায়-কীভাবে-কোড-পরিবর্তন-করবেন-developer-customization-guide)
9. [ভাইভা ও প্রজেক্ট ডিফেন্সের গুরুত্বপূর্ণ প্রশ্ন ও উত্তর (Viva Q&A Guide)](#৯-ভাইভা-ও-প্রজেক্ট-ডিফেন্সের-গুরুত্বপূর্ণ-প্রশ্ন-ও-উত্তর-viva-qa-guide)

---

## ১. প্রজেক্টের মূল ধারণা (Project Overview)

সাধারণ To-Do অ্যাপে ইউজারকে নিজে হাতে ফর্ম পূরণ করে টাস্কের নাম, তারিখ, সময়, সাবজেক্ট ও রুটিন বানাতে হয়। আর সাধারণ চ্যাটবট শুধু কথার উত্তর দেয়, কিন্তু অ্যাপের ভেতরে সত্যিকারের কোনো কাজ করতে পারে না।

**Focus Agent V2** হলো একটি **Autonomous Hybrid AI Agent**, যা:
1. **বাংলা, বাংলিশ (Banglish) এবং ইংরেজি**—তিন ভাষাতেই ইউজারের স্বাভাবিক নির্দেশ (Natural Language) এবং কণ্ঠস্বর (`🎤 Voice`) বুঝতে পারে।
2. **Auto-Hybrid AI Routing** ব্যবহার করে নিজে থেকেই সিদ্ধান্ত নেয় কখন পিসির লোকাল মডেল (`Ollama qwen3:4b`), কখন লাইভ অনলাইন নলেজ (`Wikipedia REST API`), এবং কখন রুল-বেসড স্মার্ট পার্সার (`Deterministic Engine`) ব্যবহার করতে হবে।
3. **Verified Tool Execution Loop** দিয়ে সরাসরি অ্যাপের ডাটাবেসে টাস্ক তৈরি, রিশিডিউল, সাবজেক্ট ম্যাচিং, গোল ও মাইলস্টোন রোডম্যাপ তৈরি এবং **Dashboard-এ Day-Wise স্টাডি প্ল্যান** সাজিয়ে দেয়।
4. **Course Syllabus PDF (`📄 Syllabus PDF`)** আপলোড করলে সেটি পড়ে নিজে থেকেই মাইলস্টোন ও প্রতিদিনের পড়ার রুটিন তৈরি করে।
5. **Historical Pace Learning (`estimator.py`)** ব্যবহার করে ইউজারের আগের কাজের সময় দেখে ভবিষ্যতের কাজের সময়ের অনুমান (Duration Estimate) স্বয়ংক্রিয়ভাবে নিখুঁত করে।

---

## ২. ১-ক্লিক ইনস্টলেশন ও রান করার নিয়ম (One-Click Setup & Run)

যেকোনো নতুন কম্পিউটারে প্রজেক্টটি ডাউনলোড বা ক্লোন করার পর শুধু **একটি স্ক্রিপ্ট** চালালেই `.venv` তৈরি, সব Python লাইব্রেরি ইনস্টল, **Ollama** ইনস্টল ও চালু, এবং **`qwen3:4b`** লোকাল AI মডেল ডাউনলোড হয়ে অ্যাপটি ওপেন হবে:

- **Linux / macOS-এ:**
  ```bash
  ./run_linux.sh
  ```
- **Windows-এ:**
  `run_windows.bat` ফাইলে ডাবল-ক্লিক করুন অথবা টার্মিনালে লিখুন:
  ```cmd
  run_windows.bat
  ```
- **সরাসরি Python দিয়ে (যেকোনো OS-এ):**
  ```bash
  python3 setup_and_run.py
  ```

---

## ৩. প্রজেক্টের ফোল্ডার ও ফাইল স্ট্রাকচার (Full Directory Structure)

```text
focus-app/
│
├── main.py                      # অ্যাপের মূল এন্ট্রি পয়েন্ট (Application Entry Point)
├── setup_and_run.py             # Universal 1-Click Auto-Installer & Launcher (Windows + Linux)
├── run_linux.sh                 # Linux/macOS 1-Click Launcher Script
├── run_windows.bat              # Windows 1-Click Double-Clickable Launcher
├── requirements.txt             # সব প্রয়োজনীয় Python প্যাকেজের তালিকা
├── logic.py                     # কোর বিজনেস লজিক (XP, Level, Streak, Tasks, Habits, Analytics)
├── storage.py                   # JSON ডাটাবেস রিড/রাইট, অটো-ব্যাকআপ এবং স্কিমা মাইগ্রেশন (v1 -> v3)
├── file_parser.py               # PDF, DOCX, TXT এবং Image (OCR) থেকে টেক্সট রিডার
├── evaluate.py                  # ৪৯টি টেস্টের লাইভ ইভ্যালুয়েশন বেঞ্চমার্ক স্যুট (100% Accuracy)
│
├── focus_agent/                 # 🧠 কোর AI AGENT ইঞ্জিন (Autonomous Agent Layer)
│   ├── __init__.py              # AgentController ও মূল ক্লাস এক্সপোর্ট
│   ├── controller.py            # এজেন্টের মস্তিষ্ক (Orchestrator: Intent -> Plan -> Loop -> Reply)
│   ├── extractor.py             # NLU & Entity Extractor (Bangla/Banglish/English + Anti-Hallucination)
│   ├── llm.py                   # Auto-Hybrid AI Layer (Local Ollama + Online Cloud + Wikipedia API)
│   ├── loop.py                  # Multi-Step Tool Execution & Read-Back Verification Loop
│   ├── dates.py                 # তারিখ ও সময় পার্সার (kal, porshu, আগামীকাল, rat 8 ta, next friday)
│   ├── subjects.py              # সাবজেক্ট ডিটেকশন ও ফাজি/অ্যালিয়াস ম্যাচিং (math -> Mathematics)
│   ├── scheduler.py             # Daily Planner অ্যালগরিদম (Urgency + Importance + Difficulty + Breaks)
│   ├── planner.py               # Multi-Day / Weekly ক্যাপাসিটি প্ল্যানার
│   ├── goals.py                 # Goal, Milestone ও Domain Curriculum / AI Roadmap জেনারেটর
│   ├── estimator.py             # Historical Pace Learner (আগের কাজের সময় দেখে নতুন কাজের সময় অনুমান)
│   ├── patterns.py              # ইউজারের সবচেয়ে প্রোডাক্টিভ ঘণ্টা (Productive Hours) বিশ্লেষণ
│   ├── media_import.py          # Syllabus PDF Import, Voice Input (Speech-to-Text), .ics Export, Routine OCR
│   ├── memory.py                # এজেন্টের কনভার্সেশন মেমোরি ও টুল অডিট লগ
│   ├── models.py                # Pydantic Domain Models (Task, Goal, Milestone, AgentAction)
│   ├── repository.py            # ভ্যালিডেটেড ডাটা রিপোজিটরি (TaskRepo, GoalRepo, MemoryRepo)
│   ├── schemas.py               # ইনপুট স্যানিটাইজেশন ও টাইপ ভ্যালিডেশন হেল্পার
│   └── tools/                   # 🔧 এজেন্টের ১৮+ ভ্যালিডেটেড টুলস (Tool Registry)
│       ├── __init__.py          # সব টুল রেজিস্টার ও পারমিশন চেক (read / write / destructive)
│       ├── base.py              # @tool ডেকোরেটর, আর্গুমেন্ট ভ্যালিডেটর এবং ToolResult ক্লাস
│       ├── tasks.py             # create_task, update_task, complete_task, delete_task, list_tasks
│       ├── schedule.py          # generate_daily_plan, reschedule_day, create_schedule_block
│       ├── goals.py             # create_goal, update_goal, add_milestone, decompose_goal
│       └── analytics.py         # get_productivity_report, get_focus_history
│
├── ui/                          # 🎨 রেসপনসিভ ইউজার ইন্টারফেস (CustomTkinter Views)
│   ├── app.py                   # মেইন উইন্ডো, সাইডবার নেভিগেশন, ফোকাস টাইমার ও রেসপনসিভ স্কেলিং
│   ├── theme.py                 # কালার প্যালেট (Dark/Light) ও ডাইনামিক CTkFont স্কেলিং ইঞ্জিন
│   ├── widgets.py               # কাস্টম উইজেট (SidebarButton, TimePicker, DaySelector, Tooltip)
│   ├── dialogs.py               # পপআপ ডায়ালগ (ModernFileSelector, RoutineReviewDialog)
│   ├── views_today.py           # 🏠 Dashboard (Quick Agent, Exam/Proactive Alert, KPIs, Day-Wise Tasks)
│   ├── views_chat.py            # 🤖 AI Agent Console (Chat, Voice, Syllabus PDF, Routine Image, Trace)
│   ├── views_planner.py         # 🗓️ Daily Planner (Time Slots, Start Focus, Export .ics, Priority Why)
│   ├── views_routine.py         # 📅 Class Routine (7-Day Grid, AI Schedule Import)
│   ├── views_goals.py           # 🎯 Goals & Roadmaps (Progress Bar, Milestones, Day-Wise Sync)
│   ├── views_misc.py            # 📚 Subject Vault (Course Files & AI Document Summarizer)
│   ├── views_history.py         # 📊 Analytics & Memory (Live Benchmark, Focus Chart, 365-Day Heatmap)
│   └── views_settings.py        # ⚙️ Settings (Theme, Pomodoro, AI Provider/Model, Backup/Restore)
│
└── tests/                       # 🧪 ২৩০টি অটোমেটেড ইউনিট ও ইন্টিগ্রেশন টেস্ট
```

---

## ৪. AI Agent-এর সম্পূর্ণ ওয়ার্কফ্লো (End-to-End Agent Workflow)

ইউজার যখন বাংলা, বাংলিশ বা ইংরেজিতে কোনো নির্দেশ দেয় (যেমন: `"amar kal math assignment joma dite hobe rat 8 tar modhe"` অথবা `"ami networking shikte cai amk a full milestone soho banay dao"`), তখন এজেন্টের ভেতরে নিচের **৬টি ধাপে** কাজটি সম্পন্ন হয়:

```text
User Input (Text / 🎤 Voice / 📄 Syllabus PDF in Bangla, Banglish, or English)
   │
   ▼
[Step 1] AgentController.handle()  ──► (focus_agent/controller.py)
   │     • কনভার্সেশন মেমোরিতে ইউজারের মেসেজ সেভ করে
   │     • যদি আগের কোনো প্রশ্নের উত্তর (Pending Clarification) হয়, তা রিজিউম করে
   │
   ▼
[Step 2] Hybrid NLU Extraction     ──► (focus_agent/extractor.py + llm.py + dates.py + subjects.py)
   │     ├─ 2a. Deterministic Pass : রুল ও ডিকশনারি দিয়ে তারিখ (kal -> tomorrow), সময় (rat 8 ta -> 20:00),
   │     │                           সাবজেক্ট (math -> Mathematics) এবং Intent বের করে
   │     ├─ 2b. LLM JSON Pass      : Ollama (qwen3:4b) থেকে স্ট্রাকচারড JSON আউটপুট নেয়
   │     └─ 2c. Hallucination Guard: LLM যদি ভুল সাবজেক্ট বা ভুল তারিখ দেয়, তবে লোকাল পার্সার দিয়ে তা সংশোধন করে
   │
   ▼
[Step 3] Action Step Planner       ──► (focus_agent/controller.py)
   │     • Intent অনুযায়ী কাজের ধাপ (`Step("tool", ...)`) তৈরি করে:
   │       - add_task      -> _plan_tasks() (ডিফল্ট 60m duration সহ)
   │       - goal          -> _plan_goal() (generate_roadmap_draft দিয়ে ৬টি মাইলস্টোন তৈরি)
   │       - plan_day      -> _reply_plan() (ক্লাস রুটিন বাঁচিয়ে পড়ার স্লট তৈরি)
   │       - reschedule    -> _plan_reschedule() (টাস্ক নতুন তারিখে সরিয়ে প্ল্যান আপডেট)
   │       - chat/research -> _route_chat() (Wikipedia Online Knowledge + Local AI উত্তর)
   │
   ▼
[Step 4] AgentLoop & Tool Registry ──► (focus_agent/loop.py + focus_agent/tools/)
   │     • প্রতিটি টুল কল করার আগে আর্গুমেন্ট ভ্যালিডেট করে (`schemas.py`)
   │     • Destructive টুল হলে (`delete_task`) ইউজারের কনফার্মেশন পপআপ দেখায়
   │     • টুল এক্সিকিউট হওয়ার পর `data.json`-এ সত্যিই সেভ হয়েছে কি না তা Read-Back Verification করে
   │
   ▼
[Step 5] Day-Wise Dashboard Sync   ──► (focus_agent/controller.py -> _goal_roadmap_addendum)
   │     • নতুন Goal/Roadmap তৈরি হলে তার ৬টি মাইলস্টোনকে Day 1 (Today), Day 2 (Tomorrow)... হিসেবে
   │       সরাসরি Dashboard-এর টাস্ক লিস্টে (`data["tasks"]`) যুক্ত করে দেয়
   │
   ▼
[Step 6] Friendly Reply & UI Refresh ──► (ui/views_chat.py + ui/views_today.py)
         • সহজ ও বন্ধুসুলভ ভাষায় রিপ্লাই তৈরি করে এবং নিচে 🔍 Agent Trace কার্ড দেখায়
         • Dashboard, Goals এবং Routine পেজ অটোমেটিক রিফ্রেশ করে
```

---

## ৫. Agent-এর প্রতিটি Core Code ফাইলের বিস্তারিত ব্যাখ্যা (Core Code Deep-Dive)

### ৫.১ `focus_agent/controller.py` — এজেন্টের মস্তিষ্ক (Main Orchestrator)
এই ফাইলটি পুরো এজেন্টকে নিয়ন্ত্রণ করে। এর প্রধান মেথডগুলো হলো:
- **`AgentController.handle(text, history, confirm_callback, provider, now)`**:
  ইউজারের যেকোনো মেসেজ প্রথমে এখানে আসে। এটি `fextract.extract()` কল করে ইউজারের উদ্দেশ্য (`intent`) বোঝে এবং সঠিক প্ল্যানার ফাংশনে পাঠায়।
- **`_plan_tasks(text, extraction, now)`**:
  টাস্ক যোগ করার জন্য `Step("tool", "create_task", args)` তৈরি করে। ইউজার যদি সময় উল্লেখ না করে, তবে `t.estimated_minutes or 60` (ডিফল্ট ১ ঘণ্টা) সেট করে যাতে প্ল্যানারে কোনো সমস্যা না হয়।
- **`_plan_goal(text, extraction, now)` এবং `_goal_roadmap_addendum(...)`**:
  ইউজার যখন নতুন কিছু শিখতে চায় (যেমন: `"ami networking shikte cai"`), তখন এটি প্রথমে নামটি পরিষ্কার করে (`"Learn Networking"`), এরপর `fgoals.generate_roadmap_draft()` কল করে ৬টি মাইলস্টোন তৈরি করে এবং **প্রতিটি মাইলস্টোনের জন্য `Day 1`, `Day 2`... হিসেবে Dashboard-এ স্টাডি টাস্ক তৈরি করে দেয়**।
- **`_route_chat(text, extraction, now, primary, online, history)`**:
  পড়াশোনার যেকোনো প্রশ্ন বা সাধারণ চ্যাটের জন্য **Auto-Hybrid AI Routing** চালায়। ইন্টারনেট থাকলে স্বয়ংক্রিয়ভাবে `fetch_online_topic_summary(text)` দিয়ে লাইভ তথ্য এনে লোকাল `Ollama (qwen3:4b)`-এর প্রম্পটে যুক্ত করে উত্তর দেয়।

---

### ৫.২ `focus_agent/extractor.py` — ভাষা বোঝার ইঞ্জিন (Multilingual NLU & Anti-Hallucination)
এই ফাইলটি বাংলা, বাংলিশ ও ইংরেজি বাক্য থেকে তথ্য বের করে:
- **`detect_intent(text)`**:
  বাক্যটি পড়ে বোঝে ইউজার কী করতে চাচ্ছে:
  - `add_task`: নতুন কাজ যোগ করা (`assignment`, `homework`, `joma dite hobe`, `জমা দিতে হবে`, `porte hobe`)
  - `goal`: দীর্ঘমেয়াদী লক্ষ্য বা রোডম্যাপ (`shikte cai`, `sikhte chai`, `learn`, `milestone`, `millstone`, `roadmap`, `মাইলস্টোন`)
  - `plan_day`: রুটিন বা প্ল্যান করা (`plan my day`, `ajker plan koro`, `আজকের প্ল্যান`)
  - `reschedule`: কাজ পেছানো (`move`, `reschedule`, `porshu kore dao`, `পিছিয়ে দাও`)
  - `complete_task`: কাজ শেষ করা (`finished`, `done`, `shesh korechi`, `শেষ করেছি`)
  - `delete_task`: কাজ মুছে ফেলা (`delete`, `remove`, `muche felo`, `মুছে ফেলো`)
  - `block_time`: নির্দিষ্ট সময় ব্যস্ত রাখা (`don't schedule from 2pm to 4pm`)
  - `query`: স্ট্যাটাস বা ক্লাস সম্পর্কে জানা (`how much XP`, `next class`, `আজকে কী কাজ আছে`)
- **`extract(text, provider, now, settings, subject_names)`**:
  প্রথমে `extract_deterministic()` চালায়, তারপর `extract_with_llm()` চালায় এবং দুইয়ের ফলাফল মার্জ করে।
  - **Anti-Hallucination Guard:** ছোট ৪-বিলিয়ন প্যারামিটারের LLM কখনো কখনো ইউজারের রুটিনে থাকা অন্য সাবজেক্ট (যেমন `math`-এর বদলে `Database Systems`) ভুল করে বসিয়ে দিতে পারে। `extract()` ফাংশনটি চেক করে যে LLM-এর দেওয়া সাবজেক্ট ও টাইটেল ইউজারের মূল বাক্যে সত্যিই ছিল কি না—না থাকলে সাথে সাথে লোকাল পার্সারের সঠিক সাবজেক্ট (`Mathematics`) ও টাইটেল (`Math assignment`) বসিয়ে দেয়!

---

### ৫.৩ `focus_agent/dates.py` ও `focus_agent/subjects.py` — তারিখ, সময় ও সাবজেক্ট ম্যাচিং
- **`dates.py`**:
  - `resolve_relative_date(text, now)`: ইংরেজি (`today`, `tomorrow`, `next thursday`, `in 3 days`), বাংলিশ (`aj`, `ajke`, `kal`, `kalke`, `porshu`, `shukrobar`, `3 din por`), এবং বাংলা (`আজ`, `আগামীকাল`, `পরশু`, `শুক্রবার`) তারিখকে সঠিক `YYYY-MM-DD` ফরম্যাটে রূপান্তর করে।
  - `extract_due_time(text)`: `"by 8pm"`, `"rat 8 tar modhe"`, `"bikal 5 tay"`, `"রাত ৮টার মধ্যে"` থেকে ২৪-ঘণ্টার সময় (`20:00`, `17:00`) বের করে।
- **`subjects.py`**:
  - `BUILTIN_SUBJECT_ALIASES` ডিকশনারি এবং টোকেন/ফাজি সিমিলারিটি ব্যবহার করে `"math"` → `"Mathematics"`, `"dbms"` → `"Database Systems"`, `"cn"` / `"networking"` → `"Data Communication"`, `"os"` → `"Operating Systems"` স্বয়ংক্রিয়ভাবে ম্যাচ করে।

---

### ৫.৪ `focus_agent/llm.py` — Auto-Hybrid AI Provider (Local + Online)
- **`OllamaProvider`**: লোকাল `http://localhost:11434/api/chat` এন্ডপয়েন্টে `qwen3:4b` মডেলের সাথে কথা বলে।
- **`OnlineProvider`**: কোনো ক্লাউড API Key (`GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, বা `ONLINE_LLM_API_KEY`) এনভায়রনমেন্টে থাকলে স্বয়ংক্রিয়ভাবে ক্লাউড মডেল ব্যবহার করে।
- **`fetch_online_topic_summary(query)`**: কোনো API Key ছাড়াই Wikipedia-এর OpenSearch ও REST Summary API থেকে যেকোনো নতুন শিক্ষণীয় বিষয়ের সারসংক্ষেপ অনলাইন থেকে নিয়ে আসে, যাতে এজেন্ট যেকোনো বিষয়ের ওপর নির্ভুল রোডম্যাপ ও উত্তর তৈরি করতে পারে।

---

### ৫.৫ `focus_agent/goals.py` — Goal & Roadmap Curriculum Generator
- **`DOMAIN_ROADMAPS`**: কম্পিউটার সায়েন্স ও প্রকৌশলের প্রধান বিষয়গুলোর (`networking`, `python`, `database`, `machine_learning`, `dsa`, `web`, `os`, `security`, `robotics`) জন্য ৬-ধাপের প্রফেশনাল কারিকুলাম।
- **`_llm_or_topic_phases(goal_title, provider)`**: ইউজার যদি ডিকশনারির বাইরে যেকোনো নতুন বিষয় বলে (যেমন `"Learn Quantum Computing"` বা `"IELTS Preparation"`), তবে এটি অনলাইন নলেজ + লোকাল LLM ব্যবহার করে ডাইনামিকালি ৬টি ধাপ তৈরি করে।
- **`generate_roadmap_draft(goal_title, weeks, hours_per_week)`**: প্রতিটি মাইলস্টোনের জন্য নির্দিষ্ট `target_date` এবং `estimated_minutes` হিসাব করে পূর্ণাঙ্গ রোডম্যাপ ড্রাফট তৈরি করে।

---

### ৫.৬ `focus_agent/scheduler.py` ও `focus_agent/estimator.py` — স্মার্ট প্ল্যানার ও পেস লার্নিং
- **Priority Scoring (`task_priority` in `scheduler.py`)**:
  প্রতিটি টাস্ককে নিচের ফর্মুলায় পয়েন্ট দেওয়া হয়:
  $$\text{Priority Score} = \text{Urgency Points} + \text{Importance Points} + \text{Difficulty Points} + \text{User Hint}$$
  যেখানে Overdue = `+40`, Due Today = `+30`, Due Tomorrow = `+24`, High Importance = `+12`, Hard Difficulty = `+6`।
- **Conflict-Free Placement (`generate_day_plan` in `scheduler.py`)**:
  ১. প্রথমে ইউজারের স্টাডি উইন্ডো (`09:00–22:00`, অথবা রাত ১০টার পর প্ল্যান করলে `23:59` পর্যন্ত) থেকে ওই দিনের **Class Routine**-এর সময়গুলো বাদ দেয়।
  ২. এরপর সর্বোচ্চ প্রায়োরিটির কাজগুলো আগে বসায়। কোনো কাজ ৯০ মিনিটের বেশি বড় হলে সেটিকে ভেঙে একাধিক ব্লকে ভাগ করে এবং মাঝখানে ১০ মিনিটের ব্রেক (`break_minutes`) রাখে।
  ৩. ভবিষ্যৎ দিনের রোডম্যাপ টাস্ক (`Day 2`, `Day 3`...) শুধু তাদের নিজস্ব দিনেই রাখে, যাতে আজকের প্ল্যান ওভারলোড না হয়।
- **Historical Duration Estimator (`estimator.py`)**:
  ইউজার আগে কোনো সাবজেক্টের কাজ শেষ করতে অনুমানের চেয়ে কত গুণ সময় নিয়েছে ($\text{Actual} / \text{Estimated}$-এর Median Ratio) তা হিসাব করে নতুন কাজের সময় স্বয়ংক্রিয়ভাবে অ্যাডজাস্ট করে।

---

### ৫.৭ `focus_agent/loop.py` ও `focus_agent/tools/` — ভেরিফায়েড টুল এক্সিকিউশন
- **`AgentLoop.run(steps)`**:
  এজেন্ট কখনো সরাসরি ডাটাবেস পরিবর্তন করে না। প্রতিটি অ্যাকশন `focus_agent/tools/`-এর রেজিস্টার্ড টুলের মাধ্যমে চলে:
  - টুল রান করার পর `loop.py` আবার ডাটাবেস চেক করে (`_verify`) নিশ্চিত হয় যে টাস্ক বা গোলটি আসলেই সঠিক নামে ও তারিখে সেভ হয়েছে।

---

### ৫.৮ `focus_agent/media_import.py` — Syllabus PDF, Voice Input ও Calendar Export
- **`import_syllabus_pdf(file_path, data)`**: PDF, DOCX বা TXT সিলেবাস ফাইল পড়ে স্বয়ংক্রিয়ভাবে Goal, Milestones এবং Day-Wise Dashboard Tasks তৈরি করে।
- **`record_and_transcribe_voice(duration_sec=5)`**: মাইক্রোফোন থেকে ৫ সেকেন্ডের অডিও রেকর্ড করে বাংলা (`bn-BD`) ও ইংরেজি (`en-IN` / `en-US`) ভয়েসকে টেক্সটে রূপান্তর করে।
- **`export_plan_to_ics(plan, file_path)`**: Daily Planner-এর শিডিউলকে RFC-5545 স্ট্যান্ডার্ড `.ics` ক্যালেন্ডার ফাইলে এক্সপোর্ট করে।

---

## ৬. UI (User Interface) ফাইলগুলোর কাজ ও রেসপনসিভ ডিজাইন

| ফাইল | পেজের নাম | প্রধান কাজ |
| :--- | :--- | :--- |
| `ui/app.py` | **Main Window & Sidebar** | বাম পাশের রেসপনসিভ সাইডবার (আইকন + নাম সবসময় দৃশ্যমান), ফোকাস টাইমার, উপরের XP/Level বার এবং উইন্ডো রিসাইজ হ্যান্ডলার (`_on_window_resize`)। |
| `ui/theme.py` | **Theme & Font Scaling** | Dark/Light কালার প্যালেট এবং উইন্ডোর মাপ অনুযায়ী সব ফন্ট (`CTkFont`) লাইভ ছোট-বড় করার ফাংশন (`apply_font_scale`)। |
| `ui/views_today.py` | **🏠 Dashboard** | Quick Agent Command বার (`🎤` ভয়েসসহ), Proactive Exam Countdown / Conflict Alert ব্যানার, রেসপনসিভ KPI কার্ড (`2×2` / `1×4`), আজকের টাস্ক এবং **🗓️ Day-Wise Upcoming Schedule**। |
| `ui/views_chat.py` | **🤖 AI Agent Console** | চ্যাট ইন্টারফেস, ১-ক্লিক প্রম্পট চিপস, `🎤 Voice`, `📄 Syllabus PDF` আপলোড, `📎 Routine` ইমেজ স্ক্যানার এবং `🔍 Agent Trace` কার্ড। ট্যাব পরিবর্তন করলেও চ্যাট হিস্ট্রি ও স্ট্যাটাস অক্ষুণ্ণ থাকে। |
| `ui/views_planner.py` | **🗓️ Daily Planner** | ওপেন করলেই অটোমেটিক আজকের প্ল্যান দেখায়; ২-লাইনের পরিষ্কার স্লট কার্ড, `▶ Start (Xm)` টাইমার বাটন, `📅 Export .ics` এবং `✅ Apply to Tasks`। |
| `ui/views_routine.py` | **📅 Class Routine** | সপ্তাহের ৭ দিনের ক্লাসের রুটিন গ্রিড এবং টেক্সট/ছবি থেকে AI দিয়ে রুটিন ইমপোর্ট। |
| `ui/views_goals.py` | **🎯 Goals & Roadmaps** | দীর্ঘমেয়াদী লক্ষ্য, প্রোগ্রেস বার (`%`), মাইলস্টোন চেকলিস্ট এবং নতুন গোল তৈরি করলে অটোমেটিক ৬টি মাইলস্টোন ও Day-Wise টাস্ক তৈরি। |
| `ui/views_misc.py` | **📚 Subject Vault** | প্রতিটি সাবজেক্টের নোট ও PDF ফাইল সংরক্ষণ এবং ১-ক্লিকে AI Document Summary তৈরি। |
| `ui/views_history.py` | **📊 Analytics & Memory** | **🧪 Live Agent Evaluation Benchmark (`49/49`)**, ৭-দিনের ফোকাস গ্রাফ, ৩৬৫-দিনের অ্যাক্টিভিটি হিটম্যাপ এবং এজেন্টের লার্নিং অ্যাকুরেসি। |
| `ui/views_settings.py` | **⚙️ Settings** | Dark/Light থিম, Pomodoro টাইমার সেটিংস, AI মডেল (`ollama` / `online` / `none`) কনফিগারেশন এবং ডাটা ব্যাকআপ/রিস্টোর। |

---

## ৭. ডাটাবেস ও স্টোরেজ সিস্টেম (`data.json`, `storage.py`, `logic.py`)

- প্রজেক্টের সব ডাটা লোকালি `data.json` ফাইলে সংরক্ষিত থাকে (কোনো এক্সটার্নাল ডাটাবেস সার্ভার সেটআপ করার প্রয়োজন নেই)।
- **`storage.py`**:
  - অ্যাপ ওপেন হওয়ার সময় পুরনো ডাটা ফরম্যাট থাকলে স্বয়ংক্রিয়ভাবে `backups/` ফোল্ডারে টাইমস্ট্যাম্পসহ ব্যাকআপ রেখে Schema v3-তে মাইগ্রেট করে।
  - প্রতিটি সেভ অপারেশন নিরাপদভাবে সম্পন্ন করে যাতে ফাইল কখনো করাপ্ট না হয়।

---

## ৮. কোথায় কীভাবে কোড পরিবর্তন করবেন? (Developer Customization Guide)

আপনি যদি ভবিষ্যতে প্রজেক্টের কোনো অংশ পরিবর্তন বা কাস্টমাইজ করতে চান, তবে নিচের তালিকা দেখে সরাসরি সেই ফাইলে চলে যাবেন:

1. **নতুন বাংলা/বাংলিশ শব্দ বা নতুন সাবজেক্টের নাম যোগ করতে চাইলে:**
   - তারিখ ও সময়ের শব্দের জন্য: `focus_agent/dates.py`-এর `BANGLISH_NUMBERS` বা `resolve_relative_date()` ফাংশন।
   - সাবজেক্টের শর্টকাট নামের জন্য: `focus_agent/subjects.py`-এর `BUILTIN_SUBJECT_ALIASES` ডিকশনারি।
2. **নতুন কোনো বিষয়ের রেডিমেড রোডম্যাপ (Milestones) যোগ করতে চাইলে:**
   - `focus_agent/goals.py` ফাইলের `DOMAIN_ROADMAPS` ডিকশনারিতে নতুন কী-ওয়ার্ড ও ৬টি ধাপের তালিকা যোগ করুন।
3. **এজেন্টের চ্যাট রিপ্লাই বা কথা বলার ধরন পরিবর্তন করতে চাইলে:**
   - গোল ও রোডম্যাপের মেসেজের জন্য: `focus_agent/controller.py`-এর `_goal_roadmap_addendum()` মেথড।
   - সাধারণ চ্যাট ও প্রশ্নের উত্তরের জন্য: `focus_agent/controller.py`-এর `_route_chat()` মেথড।
4. **AI মডেল পরিবর্তন করতে চাইলে (`qwen3:4b`-এর বদলে অন্য মডেল):**
   - অ্যাপের ভেতরে **⚙️ Settings → AI Agent**-এ মডেলের নাম লিখে `Save Settings` চাপুন, অথবা `focus_agent/llm.py`-এর `OllamaProvider.__init__`-এ ডিফল্ট মডেলের নাম পরিবর্তন করুন।
5. **অ্যাপের রঙ (Colors) বা ফন্ট সাইজ পরিবর্তন করতে চাইলে:**
   - `ui/theme.py` ফাইলে `COLORS` ডিকশনারি এবং ` _BASE_FONT_SPECS` পরিবর্তন করুন।

---

## ৯. ভাইভা ও প্রজেক্ট ডিফেন্সের গুরুত্বপূর্ণ প্রশ্ন ও উত্তর (Viva Q&A Guide)

**প্রশ্ন ১: আপনার প্রজেক্টটি সাধারণ চ্যাটবট বা সাধারণ To-Do অ্যাপ থেকে কীভাবে আলাদা?**  
**উত্তর:** সাধারণ চ্যাটবট শুধু টেক্সট জেনারেট করে, আর সাধারণ To-Do অ্যাপে সব কাজ ম্যানুয়ালি ইনপুট দিতে হয়। আমাদের **Focus Agent V2** একটি **Tool-Augmented Autonomous Agent**। এটি বাংলা, বাংলিশ ও ইংরেজি নির্দেশ বুঝে ভ্যালিডেটেড টুল কলের মাধ্যমে সরাসরি টাস্ক তৈরি, ক্লাসের রুটিন বাঁচিয়ে কনফ্লিক্ট-ফ্রি শিডিউল তৈরি, সিলেবাস PDF থেকে রোডম্যাপ তৈরি এবং ইউজারের কাজের ইতিহাস থেকে সময়ের অনুমান (Duration Calibration) নিজে নিজে শেখে।

**প্রশ্ন ২: ছোট লোকাল LLM (যেমন `qwen3:4b`) ভুল করলে বা ইন্টারনেট না থাকলে আপনার এজেন্ট কীভাবে কাজ করে?**  
**উত্তর:** আমাদের সিস্টেমে **Hybrid Neuro-Symbolic Architecture** ব্যবহার করা হয়েছে। LLM-এর পাশাপাশি আমাদের একটি শক্তিশালী **Deterministic NLU & Anti-Hallucination Validator** (`extractor.py`) আছে। LLM যদি কখনো ভুল সাবজেক্ট বা ভুল তারিখ অনুমান করে, ভ্যালিডেটর তা ধরে ফেলে এবং লোকাল পার্সার দিয়ে ঠিক করে দেয়। আর ইন্টারনেট বা LLM সম্পূর্ণ বন্ধ থাকলেও Deterministic Engine দিয়ে ১০০% কাজ সম্পন্ন হয়।

**প্রশ্ন ৩: আপনার এজেন্ট কীভাবে প্রতিদিনের রুটিন (Daily Schedule) তৈরি করে?**  
**উত্তর:** `scheduler.py`-এ আমরা একটি **Multi-Factor Priority & Earliest-Fit Interval Scheduling Algorithm** তৈরি করেছি। এটি প্রথমে প্রতিদিনের স্টাডি উইন্ডো (`09:00–22:00`) থেকে ক্লাসের সময়গুলো বাদ দিয়ে ফাঁকা ইন্টারভ্যাল বের করে। এরপর প্রতিটি টাস্কের **Urgency (ডেডলাইন কত কাছে), Importance এবং Difficulty** যোগ করে স্কোরিং করে এবং বড় টাস্কগুলোকে সর্বোচ্চ ৯০ মিনিটের ব্লকে ভেঙে মাঝখানে ১০ মিনিটের ব্রেক দিয়ে সাজায়।

**প্রশ্ন ৪: এজেন্ট কীভাবে ইউজারের কাজের গতি (Working Pace) শেখে?**  
**উত্তর:** `estimator.py`-এ আমরা **Historical Estimation Error Calibration** ব্যবহার করেছি। ইউজার যখন কোনো কাজ শেষ করে, তখন তার অনুমান করা সময় (`estimated_minutes`) এবং প্রকৃত লাগা সময়ের (`actual_minutes`) অনুপাত ($\text{Ratio} = \text{Actual} / \text{Estimated}$) মেমোরিতে সেভ হয়। পরবর্তীতে একই সাবজেক্ট বা সমমানের কঠিন কাজ দিলে এজেন্ট আগের কাজের **Median Error Ratio** দিয়ে সময়টি অটোমেটিক অ্যাডজাস্ট করে নেয়।

**প্রশ্ন ৫: আপনারা কীভাবে প্রমাণ করেছেন যে এজেন্টটি সঠিকভাবে কাজ করে?**  
**উত্তর:** আমাদের প্রজেক্টে `evaluate.py` এবং `tests/`-এ **২৩০টি ইউনিট টেস্ট** এবং **৪৯টি রিয়েল-ওয়ার্ল্ড বেঞ্চমার্ক টেস্ট** আছে (যার মধ্যে Extraction Accuracy, Deadline Ambiguity Handling, Subject Matching, Conflict-Free Scheduling, Tool Safety এবং Memory Effectiveness পরীক্ষা করা হয়েছে)। অ্যাপের **📊 Analytics** ট্যাব থেকে ১ ক্লিকেই লাইভ ইভ্যালুয়েশন চালিয়ে **100% (`49/49`)** রেজাল্ট দেখা যায়।
