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


def import_syllabus_pdf(file_path: str, data: dict) -> dict:
    """Read a syllabus/assignment PDF, DOCX, or TXT file and automatically create
    a Goal with Milestones + Day-Wise Dashboard Tasks."""
    import os
    from datetime import datetime, timedelta
    from logic import add_task_logic, save_data
    from focus_agent import goals as fgoals

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    clean_base = re.sub(r"[_\-]+", " ", base_name).strip().title() or "Course Syllabus"

    raw_text = ""
    try:
        from file_parser import FileParser
        raw_text = FileParser().extract_text(file_path) or ""
    except Exception:
        raw_text = ""

    goal_title = f"Master {clean_base}"
    milestones = []

    if raw_text.strip():
        try:
            primary, _ = get_providers(data.get("settings"))
            if primary.name != "none":
                sys_prompt = (
                    "You are an academic syllabus analyzer. Read the syllabus/assignment text "
                    "and output ONLY a JSON object with: "
                    "{\"goal_title\": \"Course/Topic Name\", \"milestones\": [\"1. Topic...\", \"2. Topic...\", ...]} "
                    "containing 5 to 6 sequential study modules."
                )
                res = primary.chat_json(sys_prompt, raw_text[:6000], temperature=0.1, max_tokens=800)
                if isinstance(res, dict):
                    if res.get("goal_title"):
                        goal_title = str(res["goal_title"]).strip()[:160]
                    ms_raw = res.get("milestones")
                    if isinstance(ms_raw, list) and len(ms_raw) >= 3:
                        milestones = [str(m).strip()[:180] for m in ms_raw[:6] if str(m).strip()]
        except Exception:
            pass

        if not milestones:
            # Deterministic heading/bullet extractor from syllabus text
            lines = [
                ln.strip(" •-*#\t")
                for ln in raw_text.splitlines()
                if 12 <= len(ln.strip()) <= 140
            ]
            picked = []
            for ln in lines:
                if re.search(r"\b(week|module|unit|chapter|lecture|part|topic|lab|assignment)\b", ln.lower()) or len(picked) < 6:
                    if ln not in picked:
                        picked.append(ln)
                if len(picked) >= 6:
                    break
            if len(picked) >= 3:
                milestones = [f"{i}. {p}" for i, p in enumerate(picked[:6], start=1)]

    if not milestones:
        draft, _ = fgoals.generate_roadmap_draft(clean_base, weeks=6, hours_per_week=8)
        if draft and draft.get("milestones"):
            milestones = [m["title"] for m in draft["milestones"][:6]]

    now_date = datetime.now().date()
    ms_dicts = []
    for idx, m_title in enumerate(milestones, start=1):
        t_date = (now_date + timedelta(days=idx * 7)).isoformat()
        ms_dicts.append({"title": m_title, "target_date": t_date, "estimated_minutes": 360})

    goal, err = fgoals.add_goal(
        data,
        title=goal_title,
        description=f"Imported from {os.path.basename(file_path)}",
        target_date=ms_dicts[-1]["target_date"] if ms_dicts else None,
        subject=clean_base,
        milestones=ms_dicts,
    )
    if err or not goal:
        return {"ok": False, "message": f"Could not create syllabus roadmap: {err}"}

    existing_titles = {(t.get("title") or "").lower() for t in data.get("tasks", [])}
    day_lines = []
    for idx, m_title in enumerate(milestones, start=1):
        day_date = (now_date + timedelta(days=idx - 1)).isoformat()
        clean_ms = re.sub(r"^\d+[\.\)]\s*", "", m_title).strip()
        task_title = f"Day {idx} ({clean_base}): {clean_ms}"
        if task_title.lower() not in existing_titles:
            add_task_logic(
                data,
                title=task_title,
                deadline=day_date,
                duration=60,
                subject=clean_base,
                importance=2,
                difficulty=2,
                goal_id=goal["id"],
                notes=f"Auto-generated from syllabus file '{os.path.basename(file_path)}'",
            )
            existing_titles.add(task_title.lower())
        day_tag = "Today" if idx == 1 else ("Tomorrow" if idx == 2 else day_date)
        day_lines.append(f"• **Day {idx} ({day_tag}):** {clean_ms}")

    save_data(data)
    msg = (
        f"📄 **Syllabus Roadmap Imported: {goal_title}**\n"
        f"Created **{len(milestones)} milestones** in **Goals & Roadmaps** and scheduled "
        f"**Day-Wise Study Sessions** on your **Dashboard**:\n\n"
        + "\n".join(day_lines)
    )
    return {"ok": True, "goal_id": goal["id"], "message": msg}


def record_and_transcribe_voice(duration_sec: int = 5) -> tuple[str | None, str | None]:
    """Record short microphone audio and transcribe via SpeechRecognition (Bangla + English).
    Returns (text, error_message)."""
    import os
    import shutil
    import subprocess
    import tempfile

    try:
        import speech_recognition as sr
    except ImportError:
        return None, "SpeechRecognition package is not installed."

    recognizer = sr.Recognizer()
    wav_path = os.path.join(tempfile.gettempdir(), "focus_agent_voice.wav")
    recorded = False

    # 1. Try PyAudio Microphone if available
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.4)
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=duration_sec)
            recorded = True
    except Exception:
        audio = None

    # 2. Fallback to Linux `arecord` if PyAudio is not installed
    if not recorded and shutil.which("arecord"):
        try:
            proc = subprocess.run(
                ["arecord", "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", str(duration_sec), wav_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=duration_sec + 3
            )
            if proc.returncode == 0 and os.path.exists(wav_path):
                with sr.AudioFile(wav_path) as source:
                    audio = recognizer.record(source)
                    recorded = True
        except Exception:
            audio = None

    if not recorded or audio is None:
        return None, "No active microphone detected (or PyAudio/arecord unavailable)."

    # Transcribe: try English/Banglish first, then Bengali
    for lang in ("en-IN", "bn-BD", "en-US"):
        try:
            txt = recognizer.recognize_google(audio, language=lang)
            if txt and txt.strip():
                return txt.strip(), None
        except sr.UnknownValueError:
            continue
        except sr.RequestError as e:
            return None, f"Speech recognition service unreachable: {e}"
    return None, "Could not hear clear speech — please try again."


def export_plan_to_ics(plan, file_path: str) -> tuple[bool, str]:
    """Export a PlanResult's time slots into a standard RFC-5545 .ics calendar file."""
    if not plan or not getattr(plan, "slots", None):
        return False, "No scheduled slots to export."
    date_clean = (plan.date or "").replace("-", "")
    if len(date_clean) != 8:
        return False, "Invalid plan date."

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Focus Agent V2//Student Productivity Schedule//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for idx, slot in enumerate(plan.slots, start=1):
        s_clean = (slot.start or "09:00").replace(":", "") + "00"
        e_clean = (slot.end or "10:00").replace(":", "") + "00"
        uid = f"focus-agent-{date_clean}-{idx}@focusagent.local"
        summary = (slot.title or "Study Block").replace("\n", " ")
        desc = (slot.reason or "Scheduled by Focus Agent V2").replace("\n", " ")
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTART:{date_clean}T{s_clean}",
            f"DTEND:{date_clean}T{e_clean}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{desc}",
            "END:VEVENT",
        ])
    lines.append("END:VCALENDAR")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\r\n".join(lines) + "\r\n")
        return True, f"Exported {len(plan.slots)} slot(s) to {file_path}"
    except Exception as exc:
        return False, f"Failed to write calendar file: {exc}"


