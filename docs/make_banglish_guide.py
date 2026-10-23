#!/usr/bin/env python3
"""Build docs/PROJECT_GUIDE_BANGLISH.docx - a Banglish guide to the whole
codebase with live line-number references pulled from the actual source."""
import os
import re
import sys

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "docs", "PROJECT_GUIDE_BANGLISH.docx")

_line_cache = {}


def loc(fname, pattern):
    """Line number (1-based) of the first regex match in a source file."""
    key = (fname, pattern)
    if key not in _line_cache:
        path = os.path.join(BASE, fname)
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if re.search(pattern, line):
                    _line_cache[key] = i
                    break
            else:
                _line_cache[key] = 0
    return _line_cache[key]


def refs(fname, pairs):
    """'file.py:23' style refs for a list of (label, pattern) pairs."""
    out = []
    for label, pattern in pairs:
        n = loc(fname, pattern)
        out.append(f"{label}: {fname}:{n}" if n else f"{label}: {fname} (not found)")
    return out


ACCENT = RGBColor(0x6C, 0x4B, 0xC7)   # purple-ish, app er theme
DARK = RGBColor(0x22, 0x22, 0x22)

doc = Document()
style = doc.styles["Normal"]
style.font.name = "Calibri"
style.font.size = Pt(10.5)


def h1(text):
    p = doc.add_heading(text, level=1)
    for r in p.runs:
        r.font.color.rgb = ACCENT
    return p


def h2(text):
    p = doc.add_heading(text, level=2)
    for r in p.runs:
        r.font.color.rgb = DARK
    return p


def para(text, bold=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = bold
    return p


def bullets(items):
    for it in items:
        doc.add_paragraph(it, style="List Bullet")


def numbered(items):
    for it in items:
        doc.add_paragraph(it, style="List Number")


def code(lines):
    for ln in lines:
        p = doc.add_paragraph()
        r = p.add_run("    " + ln)
        r.font.name = "Consolas"
        r.font.size = Pt(9)
        p.paragraph_format.space_after = Pt(0)


def table(headers, rows):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    for i, htxt in enumerate(headers):
        t.rows[0].cells[i].text = htxt
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = str(val)
    doc.add_paragraph()
    return t


# ==================== COVER ====================
title = doc.add_heading("Focus V2 - To Do Agent", level=0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sub.add_run("Puro project er Banglish guide:\nkon code kon line e ki kore,\n"
                "ar AI Agent ta kivabe kaj kore")
r.font.size = Pt(13)
r.font.color.rgb = DARK
note = doc.add_paragraph()
note.alignment = WD_ALIGN_PARAGRAPH.CENTER
note.add_run("(sob line number auto-generate hoyeche actual source theke - "
             "ei document ta build korar somoy er exact code onujayi)").italic = True
doc.add_paragraph()

# ==================== 1. PROJECT OVERVIEW ====================
h1("1. Project ta ek kothay: Overview")
para("Focus V2 ekta desktop productivity app (Python + CustomTkinter) jeta ekta "
     "AI AGENT hishebe kaj kore. Simple kotha: tumi kotha bolba (normal English/Banglish), "
     "agent ta bujhbe, apnar data (task, class routine, focus history) dekhe DECISION "
     "NIBE, ar kaj ta kore dibe.", bold=True)
para("Ekta important kotha mathay rakho: LLM (Ollama er qwen3:4b model) sudho "
     "LANGUAGE BUJHE - tumi ki bolso sheta structured data te convert kore. Kintu "
     "SOB DECISION ney app er nijer deterministic code (rule-based logic). Tai AI "
     "off thakleo app full kaj kore, ar AI bhul korleo agent take thik kore dey.")
h2("Ekta task er jibon: data kothay thake")
bullets([
    "SOB data ekta file e thake: data.json (human-readable, apnar PC te local)",
    "data load hoy: logic.py er load_data() -> storage.py er migrate_data() (schema v3)",
    "data save hoy: logic.py er save_data() - ATOMIC write (age .tmp e lekhe, tarpor "
    "os.replace() diye file rename - kono crash holeo file nosto hoy na)",
    "Task/class/subject/goal - sob kichu ek same JSON structure er bhitore",
])

# ==================== 2. FILE MAP ====================
h1("2. File map: kon file ki kaj kore")
table(
    ["File", "Ki kaj kore (ek line e)"],
    [
        ["main.py", "App start - window khole dey"],
        ["ui.py", "Sob screen/dashboard er design + button logic (~2800 line)"],
        ["logic.py", "V1 er business logic: task/XP/streak/history sob operation"],
        ["storage.py", "Data file load/save, schema migration, backup/restore"],
        ["utils.py", "Choto choto helper (path, file open etc.)"],
        ["file_parser.py", "Routine er photo/text parse kore class ber kore (OCR)"],
        ["ace_integration.py", "Skillbook (XP store) er integration"],
        ["ai_parser.py", "V1 er cloud AI parser (Gemini/Groq) - ekhon optional"],
        ["focus_agent/", "V2 er AI AGENT - 12 ta module, nicher section e detail"],
        ["tests/", "128 ta automated test - LLM chara chole"],
        ["evaluate.py", "Performance measure korar benchmark script"],
        ["setup.sh / setup.bat", "Notun PC te 1 command e full setup"],
        ["android/", "Flutter mobile companion app"],
    ],
)

# ==================== 3. APP START FLOW ====================
h1("3. App start howar flow (step by step)")
numbered([
    f"main.py:{loc('main.py', r'main\(')} -> FocusApp class run kore",
    f"ui.py:{loc('ui.py', r'class FocusApp')} -> FocusApp window banay, sidebar nav banay "
    f"(Today, Tasks, Routine, Chat, Planner, Goals, Vault, Reports, Settings...)",
    f"ui.py:{loc('ui.py', r'class ChatView')} -> ChatView (AI agent er screen) toiri hoy",
    f"logic.py:{loc('logic.py', r'def load_data')} -> data.json pore; na thakle notun default data banay",
    f"storage.py:{loc('storage.py', r'def migrate_data')} -> purano data ke notun schema v3 te "
    "upgrade kore (notun field add hoy, purano kichu delete hoy NA); age backup o hoy",
    f"logic.py:{loc('logic.py', r'def process_daily_automation')} -> roz er automation: "
    "ajker class gulo add hoy, completed task archive hoy",
])
para("Ekhon user ki dekhe: ekta dashboard jekhane ajker task + class, timer, XP, streak sob dekha jay. "
     "Chat tab e giye agent er sathe kotha bola jay.")

# ==================== 4. AI AGENT (MAIN SECTION) ====================
h1("4. AI AGENT - kivabe kaj kore (main section)")

para("Agent ta 8 ta layer e vaz kore. Ekta request ekdom upor theke nichomukhi "
     "vabe jay. Protita layer er code kothay ache, line number soho dekhao hocche:", bold=True)

h2("4.1 Layer 1: UI/Chat screen - ui.py")
bullets(refs("ui.py", [
    ("ChatView class", r"class ChatView"),
    ("user message pathano (send_message)", r"def send_message"),
    ("agent er background thread", r"def worker"),
    ("confirmation dialog bridge", r"def _confirm_from_ui"),
    ("agent er uttor UI te dekhano", r"def _deliver"),
    ("tool er result chip dekhano", r"def _add_tool_chip"),
    ("plan er preview chip", r"def _add_plan_chip"),
    ("AI status check", r"def _check_provider_status_async"),
]) + [
    "Kaj: user er lekha agent controller e pathay, thread e (jate UI freeze na hoy).",
    "Jokhon agent 'delete task' er moto risky kaj chacche, tkinter er messagebox e "
    "Yes/No ashe - user er answer queue diye abar agent er thread e fire jay. "
    "Ei thread-bridge ta _confirm_from_ui + queue.Queue diye hoy.",
])

h2("4.2 Layer 2: Controller (agent er brain) - focus_agent/controller.py")
bullets(refs("focus_agent/controller.py", [
    ("AgentReply class (agent er uttor)", r"class AgentReply"),
    ("handle() - SOB request er entry point", r"def handle"),
    ("deterministic query answer (LLM chara)", r"def _answer_query"),
    ("task banano route", r"def _route_tasks"),
    ("complete/delete route", r"def _route_task_ref"),
    ("task move route", r"def _route_reschedule"),
    ("day plan route", r"def _route_plan"),
    ("goal route", r"def _route_goal"),
    ("normal chat route", r"def _route_chat"),
]) + [
    "handle() er kaj: (1) greeting ba 'how much XP' type question hole LLM CHARAI "
    "answer dey _answer_query() diye. (2) na hole intent bujhe onujayi route e pathay.",
    "Routing table handle() er bhitore ache - kon intent -> kon function.",
    "provider_offline hole reply er sheshe disclosure add kore: "
    "'(AI provider offline - used the built-in local parser.)' - user ke mitha bola hoy na.",
])

h2("4.3 Layer 3: LLM abstraction - focus_agent/llm.py")
bullets(refs("focus_agent/llm.py", [
    ("base provider class", r"class LLMProvider"),
    ("HTTP call + typed error mapping", r"def _post_json"),
    ("JSON ber kora model output theke", r"def extract_json"),
    ("Ollama provider (LOCAL, main AI)", r"class OllamaProvider"),
    ("Ollama te chat request", r"def chat", ),
    ("online provider (optional, env key)", r"class OnlineProvider"),
    ("provider OFF korle", r"class NullProvider"),
    ("settings/env theke provider banano", r"def get_providers"),
]) + [
    "OllamaProvider kothay connect kore: http://localhost:11434/api/chat",
    "Payload e 'think': false deya hoy - karon qwen3 ekta thinking model, eta na "
    "dile <think> tag er bhitor atke jay.",
    "Error mapping: net off -> ProviderUnavailable, model install nai -> "
    "ModelNotInstalled, busy -> 503 error. UI te friendly message dekhay.",
    "Online provider er API key SHUDHO environment variable (ONLINE_LLM_API_KEY) "
    "theke ney - data.json e kokhono lekha hoy na, log o hoy na.",
])

h2("4.4 Layer 4: Extraction (kotha theke task ber kora) - focus_agent/extractor.py")
bullets(refs("focus_agent/extractor.py", [
    ("intent classify (rule-based!)", r"def detect_intent"),
    ("multi-task text bhanga", r"def split_requests"),
    ("duration bujha ('two hours'=120)", r"def extract_duration"),
    ("importance bujha (urgent=high)", r"def extract_importance"),
    ("subject er nam ber kora", r"def extract_subject_mention"),
    ("ek segment theke task banano", r"def parse_task_segment"),
    ("DETERMINISTIC extraction (LLM chara)", r"def extract_deterministic"),
    ("LLM extraction", r"def extract_with_llm"),
    ("duita merge kora (hybrid)", r"def extract"),
    ("deadline-sensitive keyword list", r"DEADLINE_SENSITIVE"),
    ("LLM er prompt", r"EXTRACTION_SYSTEM_PROMPT"),
]) + [
    "DETERMINISTIC parser regex diye bujhe: 'tomorrow', 'tonight', 'next monday', "
    "'two hours', 'urgent' - egula LLM chara-i bujha jay.",
    "extract() er MERGE RULE (eta khub important): LLM er output aste, kintu date "
    "conflict hole deterministic (keyword-based) date JITE - karon 'tonight' er moto "
    "keyword evidence model er inference theke beshi bissposto. Live test e dekha geche "
    "qwen model 'tonight' ke kal hishebe bhul bujhechilo, agent take thik kore dey.",
    "Unknown jinish SHUDHO None thake - kokhono banano date/duration bosha hoy na.",
    "Deadline-sensitive task (submit/exam/application) r date na thakle QUESTION "
    "generate hoy: 'When is this due?'",
])

h2("4.5 Layer 5: Validation (AI er output check kora) - focus_agent/schemas.py")
bullets(refs("focus_agent/schemas.py", [
    ("ExtractedTask structure", r"class ExtractedTask"),
    ("ekta task validate kora", r"def validate_extracted_task"),
    ("tool er argument validate kora", r"def validate_tool_args"),
    ("date validator", r"def valid_date"),
    ("text cleaner (dangerous char bad)", r"def clean_str"),
]) + [
    "LLM je date bole (jemon '2026-13-45') valid_date() check kore - bhul hole None "
    "+ warning. Bhul data kokhono execute hoy na.",
    "validate_tool_args() tool er schema check kore: bhul type, out-of-range number, "
    "BA UNKNOWN argument (LLM nijer moto field banaleo) - sob reject hoy.",
])

h2("4.6 Layer 6: Tool execution (agent er haat) - focus_agent/tools.py")
bullets(refs("focus_agent/tools.py", [
    ("ToolSpec (tool er schema)", r"class ToolSpec"),
    ("tool registry/decorator", r"def tool"),
    ("EXECUTION PIPELINE (sob security ekhane)", r"def execute_tool"),
    ("task khunje ber kora (fuzzy)", r"def _find_task_fuzzy"),
    ("create_task tool", r"def tool_create_task"),
    ("delete_task tool (confirm lage)", r"def tool_delete_task"),
    ("generate_daily_plan tool", r"def tool_generate_daily_plan"),
]) + [
    "execute_tool() er PIPELINE (order khub important):",
])
code([
    "1. Tool ta registry te ache?      na -> 'Unknown tool' reject",
    "2. Same call_id age eshechilo?    ha -> duplicate, age er result dey (idempotency)",
    "3. Argument schema valid?         na -> 'Invalid arguments' reject",
    "4. Destructive/commit tool?       -> confirmation lagbe (user Yes/No)",
    "5. Handler run kora (try/except)  crash hole o safe ToolResult error",
    "6. Audit log e lekha (agent_memory)",
])
para("26 ta tool ache - task CRUD, subject, routine, planning, goals, analytics. "
     "Prottekta tool er permission class ache: read / write / destructive. "
     "LLM SOBDOKHONO direct data.json e likhte pare na - shudhu ei tool gulo diye "
     "jegulo validation + confirmation cross kore sekhan theke jete pare.")

h2("4.7 Layer 7: Deterministic core (agent er decision engine)")
para("Ei jaygay AGENT SOB DECISION NEY - ekhane LLM er kono bhumika nei:")
bullets(refs("focus_agent/subjects.py", [
    ("subject match scoring", r"def match_subject"),
    ("class title theke subject match", r"matched_on"),
    ("known subjects (vault + routine)", r"def get_known_subjects"),
]) + refs("focus_agent/scheduler.py", [
    ("urgency point table", r"URGENCY_POINTS"),
    ("deadline theke urgency", r"def urgency_bucket"),
    ("priority score + REASON", r"def task_priority"),
    ("free time ber kora (class bad)", r"def get_availability"),
    ("DIN ER PLAN banano", r"def generate_day_plan"),
    ("plan data te apply kora", r"def apply_plan"),
    ("reschedule (done work preserve)", r"def reschedule_after_change"),
    ("priority explain kora", r"def explain_priorities"),
]) + refs("focus_agent/estimator.py", [
    ("history theke observation joma", r"def collect_observations"),
    ("duration ESTIMATE kora", r"def estimate_minutes"),
    ("estimation analytics (MAE)", r"def estimation_analytics"),
]) + refs("focus_agent/dates.py", [
    ("relative date ('tomorrow' etc)", r"def resolve_relative_date"),
    ("timezone setup", r"def get_timezone"),
]))
bullets([
    "subjects.py: match er confidence score thake. >= 0.82 hole auto-assign; "
    "0.55-0.82 hole flag kore jigges kore; < 0.55 hole ABARJONA - guess kore na. "
    "Class routine er title (jemon 'CSE 3202') o subject hishebe count hoy.",
    "scheduler.py: prottek task er score = urgency points (overdue=40, today=30, "
    "..., no deadline=0) + importance + difficulty points. Class er somoy free time "
    "theke BAD deya hoy. 90 min er beshi task bhange jay, majhe break dey. Ajker "
    "already-gesa somoy e kichu bosay na. Overload hole boldey + alternative dey.",
    "estimator.py: ager task gulor estimated vs actual ratio theke SHEKHE - median "
    "ratio by subject+difficulty (3 tar kom sample hole subject -> difficulty -> "
    "global -> default x1.15). FUTURE data ager prediction e dhuke na (leakage guard) "
    "- created_at diye cutoff hoy.",
])

h2("4.8 Layer 8: Goals + Memory + Storage")
bullets(refs("focus_agent/goals.py", [
    ("goal banano", r"def add_goal"),
    ("goal edit/pause", r"def update_goal"),
    ("milestone add", r"def add_milestone"),
    ("progress calculate", r"def goal_progress"),
    ("roadmap DRAFT banano", r"def generate_roadmap_draft"),
]) + refs("focus_agent/memory.py", [
    ("tool execution audit log", r"def log_tool_execution"),
    ("idempotency check (duplicate call)", r"def remember_call"),
    ("plan log", r"def log_plan"),
]) + refs("storage.py", [
    ("schema version (v3)", r"SCHEMA_VERSION"),
    ("agent default settings", r"DEFAULT_AGENT_SETTINGS"),
    ("backup toiri", r"def make_backup"),
    ("backup theke restore", r"def restore_backup"),
    ("data migration", r"def migrate_data"),
]) + [
    "goals.py: roadmap draft banale assumptions CLEARLY lekha thake "
    "('-week horizon at about Xh/week') - app mitha bole na je eta user er plan, "
    "eta sudho editable draft.",
    "memory.py: prottek tool call ekta log e jay (ki call holo, ok na fail) - "
    "eta audit trail. 500 entry er beshi hole purano purge hoy.",
    "storage.py: migration ADDITIVE - purano field/value/ID sob thake, notun gulo "
    "add hoy. Migration er age timestamped backup. Corrupt file hole "
    "'data.json.corrupt-<time>' nam e save hoye fresh data ase - data LOSE hoy na.",
])

# ==================== 5. END TO END EXAMPLE ====================
h1("5. End-to-end example: ekta request er পুরো journey")
para("User Chat e likhlo: \"Tomorrow submit my AI assignment; it will take about two hours\"")
steps = [
    ("ui.py ChatView._send_message", "lekha queue te agent thread e jay (UI freeze hoy na)"),
    (f"controller.py:{loc('focus_agent/controller.py', r'def handle')} handle()",
     "greeting na, query na -> extraction e jabe"),
    (f"extractor.py:{loc('focus_agent/extractor.py', r'def extract')} extract()",
     "age deterministic parser chalay: 'tomorrow'->kal er date, 'two hours'->120min, "
     "'assignment'->task noun, 'AI'->subject mention; tarpor LLM ke o pathay"),
    (f"llm.py:{loc('focus_agent/llm.py', r'def chat')} OllamaProvider.chat",
     "localhost:11434 te qwen3:4b chalay, JSON format e output chay"),
    ("schemas.py validate_extracted_task",
     "LLM er sob field check: date format thik? duration 5-960 er moddhe? na thakle None"),
    (f"extractor.py merge rules (extract())",
     "LLM + deterministic merge; date conflict hole keyword date jite"),
    (f"tools.py:{loc('focus_agent/tools.py', r'def execute_tool')} execute_tool",
     "create_task tool: schema validate -> (confirm lagbe na, write permission) -> handler"),
    (f"subjects.py:{loc('focus_agent/subjects.py', r'def match_subject')} match_subject",
     "'AI' routine e ache -> confidence 1.0 -> subject assign"),
    (f"logic.py:{loc('logic.py', r'def add_task_logic')} add_task_logic",
     "task data.json e save (atomic write)"),
    ("controller reply", "user dekhe: \"Created task 'Submit AI assignment', due 2026-10-24, "
     "~120min [subject: AI]\" + UI refresh + tool chip"),
]
table(["Code e kothay", "Ki ghote"], [[a, b] for a, b in steps])

# ==================== 6. UI PARTS ====================
h1("6. UI er sob ongsho (ui.py)")
table(
    ["Class/View", "Ki kore"],
    [
        ["FocusApp", "Main window + sidebar navigation + sob view manage kore"],
        ["TodayView", "Ajker dashboard: task + class + timer"],
        ["ChatView", "AI agent er chat screen: async thread, tool chip, plan chip, confirmation"],
        ["PlannerView", f"Din er plan dekhay + 'Apply to Tasks' button (line {loc('ui.py', r'class PlannerView')})"],
        ["GoalsView", f"Goal card + progress bar + milestone checkbox (line {loc('ui.py', r'class GoalsView')})"],
        ["SettingsView", f"AI settings: provider/model/endpoint + Test Connection + backup/restore (line {loc('ui.py', r'class SettingsView')})"],
        ["ReportView", "Analytics + estimation accuracy card + streak"],
        ["HistoryView", "Daily focus history + heatmap"],
        ["VaultView/HabitView", "Subject file storage + habit tracker (V1 theke)"],
    ],
)

# ==================== 7. DATA SAFETY ====================
h1("7. Data safety (keno bhoy nei)")
bullets([
    "Atomic write: save_data() age .tmp file e likhe, tarpor os.replace() - "
    "hothot app crash korleo purano data safe thake",
    "Migration backup: schema v3 te upgrade howar AGE automatic timestamped backup",
    "Corrupt recovery: bhanga JSON hole 'data.json.corrupt-<time>' nam e preserve hoy",
    "Rollback: Settings -> Data & Backups -> Restore, ba backup file ta data.json er "
    "jaygay copy",
    "API key kokhono data.json e jay na - shudho environment variable",
])

# ==================== 8. TEST/EVAL ====================
h1("8. Test ar Evaluation")
bullets([
    "tests/ folder e 128 ta test (pytest) - SOB deterministic, LLM lagbe na",
    "Cholano:  python -m pytest tests/ -q",
    "evaluate.py: benchmark - extraction/subject/schedule/tools/estimation accuracy "
    "measure kore (deterministic: 38/38, live qwen3:4b: 48/48)",
    "Cholano:  python evaluate.py   ba   python evaluate.py --live",
    "AI er bhul dhora jay kivabe: test_llm_adapter.py te mock provider diye "
    "malformed output, offline, timeout sob case test kora hoy",
])

# ==================== 9. ONE COMMAND SETUP ====================
h1("9. Notun PC te setup (1 command)")
table(
    ["OS", "Ki korba"],
    [
        ["Windows", "Project folder copy koro -> setup.bat double-click"],
        ["Linux/Mac", "Project folder copy koro -> terminal e:  bash setup.sh"],
    ],
)
para("Script ta nije: (1) Python check korbe, (2) .venv banabe, (3) sob requirement "
     "install korbe, (4) tkinter/Ollama check korbe + thik korar instruction dekhabe, "
     "(5) app launch korbe. Bar bar chalano completely safe.")

# ==================== 10. VIVA ====================
h1("10. Common question (viva preparation)")
qa = [
    ("LLM ki agent? Na agent ki LLM?",
     "Agent ta main. LLM sudho ekta module (language perception). Agent nijer "
     "deterministic logic diye decision ney - scheduler, estimator, threshold sob "
     "rule-based. Proof: AI off korleo app full kaj kore."),
    ("Agent kivabe shekhe (learning)?",
     "Estimator: prottek completed task er estimated vs actual time er ratio theke "
     "median ratio ber kore (subject+difficulty onujayi). Porerbar oi ratio diye "
     "notun task er somoy predict kore. No ML library lagbe - sudho statistics."),
    ("AI bhul bolle ki hobe?",
     "Validation layer schemas.py te: bhul date/number None hoye jay. Date conflict "
     "hole deterministic (keyword) jite. Unknown intent hole deterministic classifier "
     "rescue kore. Destructive kajer age confirmation lage."),
    ("Kono task harale?",
     "Scheduler overload report kore - kon task bosay nai + keno + alternative "
     "suggestion. Completed task delete hoy na, archive hoy."),
    ("Data security?",
     "Local-first (data.json apnar PC te). API key env-only. LLM output untrusted - "
     "sob validate hoye tool gate cross kore. Prompt injection test kora ache "
     "(test_controller.py: injection message diye destructive tool call block hoy)."),
    ("Keno Ollama/Qwen?",
     "Local: data bahire jay na, free, offline chole. Proposal eo ei choice chilo. "
     "Model settings page theke change kora jay (jemon qwen3:8b)."),
]
for q, a in qa:
    p = doc.add_paragraph()
    r = p.add_run("Q: " + q)
    r.bold = True
    doc.add_paragraph("A: " + a)

doc.save(OUT)
print("saved:", OUT)
