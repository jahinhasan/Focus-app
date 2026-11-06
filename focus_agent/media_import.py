# ==================== MEDIA_IMPORT.PY ====================
# V2 helper module for routine file/image import, document summarization,
# and subtask decomposition using the V2 provider layer (with offline fallbacks).

import re
from logic import load_data
from focus_agent import extractor as fextract
from focus_agent.llm import get_providers

_DAY_MAP = {
    "mon": ["mon"], "monday": ["mon"], "shombar": ["mon"], "sombar": ["mon"],
    "tue": ["tue"], "tues": ["tue"], "tuesday": ["tue"], "mongolbar": ["tue"],
    "wed": ["wed"], "wednesday": ["wed"], "budhbar": ["wed"],
    "thu": ["thu"], "thur": ["thu"], "thurs": ["thu"], "thursday": ["thu"], "brihoshpotibar": ["thu"],
    "fri": ["fri"], "friday": ["fri"], "shukrobar": ["fri"],
    "sat": ["sat"], "saturday": ["sat"], "shonibar": ["sat"],
    "sun": ["sun"], "sunday": ["sun"], "robibar": ["sun"],
    "daily": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
    "everyday": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
    "weekdays": ["mon", "tue", "wed", "thu", "fri"],
    "weekends": ["sat", "sun"],
}


def parse_routine_line(line: str):
    """Extract {title, subject, days, start, end} from a single routine line."""
    line = (line or "").strip()
    if not line:
        return None
    start, end = fextract.extract_time_range(line)
    if not start or not end:
        return None

    found_days = []
    for w in re.split(r"[\s,/|-]+", line.lower()):
        w_clean = w.strip(".,:;()[]{}")
        if w_clean in _DAY_MAP:
            for d in _DAY_MAP[w_clean]:
                if d not in found_days:
                    found_days.append(d)
    if not found_days:
        return None

    # Clean title by removing time range and day words
    clean_text = re.sub(
        r"(\d{1,2}(?:[:.]\d{2})?(?:\s*[ap]m)?)\s*(?:-|–|to|until)\s*(\d{1,2}(?:[:.]\d{2})?(?:\s*[ap]m)?)",
        " ", line, flags=re.IGNORECASE
    )
    title_words = []
    for w in clean_text.split():
        w_low = w.lower().strip(".,:;()[]{}")
        if w_low not in _DAY_MAP and w_low not in ("from", "at", "on", "to", "in", "class"):
            title_words.append(w)
    title = " ".join(title_words).strip(" -:,.()") or "Class"
    return {
        "intent": "class",
        "title": title,
        "subject": title,
        "days": found_days,
        "start": start,
        "end": end,
        "confidence": 0.9,
    }


def parse_routine_text(raw_text: str) -> list:
    """Parse multi-line routine text into a list of class dicts."""
    classes = []
    for ln in (raw_text or "").splitlines():
        item = parse_routine_line(ln)
        if item:
            classes.append(item)
    return classes


def parse_file_with_ai(file_path: str) -> dict:
    """Extract a class routine from a PDF, image, or text file."""
    try:
        from file_parser import FileParser
        raw_text = FileParser().extract_text(file_path)
    except Exception as e:
        return {"intent": "chat", "message": f"Error reading file: {e}"}

    if not raw_text or not raw_text.strip():
        return {"intent": "chat", "message": "Could not extract readable text from file."}

    # Try local/configured V2 LLM provider first
    try:
        data = load_data()
        primary, _ = get_providers(data.get("settings"))
        if primary.name != "none":
            sys_prompt = (
                "Extract the university class schedule from the text. "
                "Normalize days to 3-letter lowercase ('mon','tue','wed','thu','fri','sat','sun') "
                "and times to 24h 'HH:MM'. Output JSON ONLY: "
                "{\"intent\": \"schedule_file\", \"classes\": [{\"title\": \"...\", \"days\": [\"mon\"], \"start\": \"09:00\", \"end\": \"10:30\"}]}"
            )
            res = primary.chat_json(sys_prompt, raw_text[:6000])
            if isinstance(res, dict) and isinstance(res.get("classes"), list) and res["classes"]:
                return {
                    "intent": "schedule_file",
                    "classes": res["classes"],
                    "message": f"Extracted {len(res['classes'])} class(es) via AI Agent.",
                }
    except Exception:
        pass

    # Deterministic fallback
    found = parse_routine_text(raw_text)
    if found:
        return {
            "intent": "schedule_file",
            "classes": found,
            "message": f"Found {len(found)} class(es) from file.",
        }
    return {"intent": "chat", "message": "Could not detect a clear class schedule in the file."}


def summarize_with_ai(file_path: str) -> str:
    """Summarize a document using the V2 LLM provider with extractive offline fallback."""
    try:
        from file_parser import FileParser
        raw_text = FileParser().extract_text(file_path)
    except Exception as e:
        return f"Error reading document: {e}"

    if not raw_text or not raw_text.strip():
        return "No readable text found in document."

    prompt = (
        "You are an expert academic summarizer. Provide a concise, structured summary "
        "of this document with bullet points for key takeaways. Format with Markdown."
    )
    try:
        data = load_data()
        primary, _ = get_providers(data.get("settings"))
        if primary.name != "none":
            return primary.chat(prompt, raw_text[:8000])
    except Exception:
        pass

    lines = [ln.strip() for ln in raw_text.splitlines() if len(ln.strip()) > 20]
    bullets = "\n".join(f"• {ln[:160]}" for ln in lines[:8])
    return f"### 📄 Document Summary (Offline Preview)\n\n{bullets or raw_text[:500]}"


def suggest_subtasks_ai(task_title: str) -> list:
    """Decompose a task into 3-5 actionable subtasks using V2 LLM or deterministic fallback."""
    clean = (task_title or "task").strip()
    try:
        data = load_data()
        primary, _ = get_providers(data.get("settings"))
        if primary.name != "none":
            sys_prompt = "Return JSON with key 'subtasks' containing 3 to 5 short actionable step strings."
            user_prompt = f"Break down this student task into 3-5 actionable steps: '{clean}'"
            res = primary.chat_json(sys_prompt, user_prompt)
            if isinstance(res, dict) and isinstance(res.get("subtasks"), list) and res["subtasks"]:
                return [str(s) for s in res["subtasks"][:5]]
    except Exception:
        pass

    return [
        f"Review requirements & gather study materials for {clean}",
        f"Complete core work and problem solving for {clean}",
        f"Review, verify, and finalize {clean}",
    ]

