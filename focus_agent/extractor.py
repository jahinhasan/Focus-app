# ==================== EXTRACTOR.PY ====================
# Natural-language -> structured tasks/goals/intents.
#
# Two engines:
# 1. Deterministic regex parser (always available, no network, testable) -
#    handles the common phrasings and acts as the fallback when the LLM is
#    offline or returns garbage.
# 2. LLM extraction through the provider abstraction with strict validation -
#    invalid fields are dropped with warnings, never executed.
#
# Unknown values stay None. Material ambiguity produces a follow-up question
# instead of a guessed deadline.

import re

from focus_agent import dates as fdates
from focus_agent.schemas import (
    ExtractionResult, ExtractedTask, validate_extracted_task, clean_str,
)

NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "half": 0.5,
}

TASK_NOUNS = ("assignment", "homework", "exam", "test", "quiz", "project",
              "essay", "report", "presentation", "lab", "reading", "revision",
              "practice", "task", "submission", "proposal", "thesis")

# Keywords whose deadline is material - a missing due date triggers a question
DEADLINE_SENSITIVE = ("exam", "submission", "submit", "deadline", "due",
                      "assignment", "homework", "project", "test", "quiz",
                      "application", "apply", "register", "registration",
                      "hand in", "hand-in", "turn in", "scholarship", "enroll")


# ==================== DETERMINISTIC PARSER ====================

def detect_intent(text):
    """Classify the request without any model. Returns (intent, query_action)."""
    low = (text or "").lower().strip()

    if re.search(r"\b(plan|schedule)\b.*\b(day|today|tomorrow|week)\b", low) \
            or re.search(r"\b(daily\s+plan|plan\s+my\s+day|what\s+should\s+i\s+do)\b", low) \
            or re.search(r"\bprepare\s+a\s+revision\s+plan\b", low) \
            or re.search(r"\brevision\s+plan\b", low) \
            or re.search(r"\bplan\b.*\b(pending|tasks|assignments|everything|work)\b", low):
        return "plan_day", None
    if re.search(r"^\s*(move|reschedule|push|shift|postpone|delay)\b", low) or \
            re.search(r"\bmove\b.*\btask\b", low) and re.search(r"\b(move|reschedule)\b", low):
        return "reschedule", None
    if re.search(r"\b(finished|completed|done with|mark.*(done|complete)|i completed)\b", low) \
            or re.match(r"^\s*(complete|finish)\s+\S", low):
        return "complete_task", None
    if re.search(r"^\s*(delete|remove)\b", low):
        return "delete_task", None
    if re.search(r"\b(goal|roadmap|milestone|learning path|master\s+plan)\b", low) or \
            re.search(r"\bi want to learn\b", low) or re.search(r"\bmy goal is\b", low):
        return "goal", None
    if re.match(r"^(analyze|analysis|how productive|productivity)\b", low):
        return "query", "productivity"
    if re.match(r"^(what|when|where|which|who|how much|how many|how long|show|list|tell|do i have)\b", low):
        action = None
        if re.search(r"\bxp\b|\blevel\b|\bprogress\b|productivity", low):
            action = "stats"
        elif re.search(r"\bnext class\b|\bnext lecture\b", low):
            action = "next_class"
        elif re.search(r"\b(week|weekly)\b", low):
            action = "weekly_classes"
        elif re.search(r"\b(today|tonight)\b|\bschedule\b", low):
            action = "today_tasks"
        return "query", action
    if re.match(r"^(hi|hello|hey|thanks|thank you|good (morning|evening|afternoon))\b", low):
        return "chat", None
    return "add_task", None


_DURATION_CLAUSE_RE = re.compile(
    r"^(?:it|this|that|each|they)?\s*(?:will|should|would)?\s*(?:take|need)s?\b.*"
    r"|^(?:about|around|roughly|approximately|approx)\s+\d"
    r"|^(?:\d+\s*(?:hours?|hrs?|minutes?|mins?)\b|half\s+an\s+hour)",
    re.IGNORECASE)


def split_requests(text):
    """Split one message into per-task segments (conservative).

    Duration clarifications after a separator ('; it will take about two
    hours') are merged back into the previous task instead of becoming a
    bogus task of their own.
    """
    parts = re.split(r"\s*(?:;|\n|\.\s+|\band also\b|\balso,\s*|\band then\b|\bafter that\b|\bthen\b)\s*",
                     text.strip())
    segments = []
    for p in parts:
        p = p.strip(" ,.")
        if not p or len(p) <= 2:
            continue
        if segments and _DURATION_CLAUSE_RE.match(p) and not _has_task_noun(p):
            segments[-1] = f"{segments[-1]}; {p}"
            continue
        segments.append(p)
    return segments


def _has_task_noun(text):
    low = (text or "").lower()
    return any(n in low for n in TASK_NOUNS)


# Lead verbs/possessives and trailing date clauses stripped from task_ref
# candidates ("move my networking assignment to friday" -> "networking assignment")
_REF_LEAD_WORDS = ("can you", "could you", "please", "move", "reschedule", "push",
                   "shift", "postpone", "delay", "delete", "remove", "cancel",
                   "complete", "finish", "mark", "done with", "do")
_REF_ARTICLES = ("the ", "my ", "a ", "an ", "that ", "this ")
_REF_TAIL_WORDS = ("to", "for", "by", "until", "till", "on")
_DATEISH_TOKENS = ("today", "tonight", "tomorrow", "next", "mon", "tue", "wed",
                   "thu", "fri", "sat", "sun", "monday", "tuesday", "wednesday",
                   "thursday", "friday", "saturday", "sunday")


def clean_task_ref(text):
    """Normalize a task_ref extracted from a move/complete/delete request."""
    from focus_agent.schemas import clean_str
    t = (text or "").strip().strip("\"'").strip()
    changed = True
    while changed and t:
        changed = False
        low = t.lower()
        for w in sorted(_REF_LEAD_WORDS, key=len, reverse=True):
            if low.startswith(w + " "):
                t = t[len(w) + 1:].strip()
                changed = True
                break
        if not changed:
            for art in _REF_ARTICLES:
                if low.startswith(art):
                    t = t[len(art):].strip()
                    changed = True
                    break
    # trailing "to <date>" clause (only when the tail names a date)
    words = t.split()
    for i in range(1, len(words)):
        if words[i].lower().rstrip(".,") in _REF_TAIL_WORDS:
            tail = " ".join(words[i:])
            tail_low = tail.lower()
            if any(dt in tail_low for dt in _DATEISH_TOKENS) or \
                    re.search(r"\d{4}-\d{2}-\d{2}", tail):
                t = " ".join(words[:i]).strip()
                break
    # trailing bare connector ("... assignment to")
    while t and len(t.split()) > 1 and t.split()[-1].lower().rstrip(".,") in _REF_TAIL_WORDS:
        t = " ".join(t.split()[:-1]).strip()
    return clean_str(t, 200)


def extract_duration(text):
    """Find estimated duration. Returns (minutes_or_None, matched_or_None)."""
    low = (text or "").lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:-\s*)?(hours?|hrs?|h)\b", low)
    if m:
        return int(float(m.group(1)) * 60), m.group(0)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:-\s*)?(minutes?|mins?|m)\b", low)
    if m and "h" not in m.group(0):
        return int(float(m.group(1))), m.group(0)
    m = re.search(r"\bhalf\s+an\s+hour\b", low)
    if m:
        return 30, m.group(0)
    m = re.search(r"\b(?:an\s+hour\s+and\s+a\s+half|one\s+and\s+a\s+half\s+hours)\b", low)
    if m:
        return 90, m.group(0)
    m = re.search(r"\b(two|three|four|five|six|one)\s+hours?\b", low)
    if m:
        return NUMBER_WORDS[m.group(1)] * 60, m.group(0)
    m = re.search(r"\b(\d+)\s*h\b", low)
    if m:
        return int(m.group(1)) * 60, m.group(0)
    return None, None


def _number_word(n):
    return NUMBER_WORDS.get(n, n)


def extract_importance(text):
    """Return (importance_or_None, priority_hint_or_None)."""
    low = (text or "").lower()
    if re.search(r"\b(urgent|critical|asap|highest priority|very important)\b", low):
        return 3, 90
    if re.search(r"\b(important|high priority|priority)\b", low):
        return 3, 70
    if re.search(r"\b(low priority|whenever|no rush|someday|backlog)\b", low):
        return 1, 20
    return None, None


def extract_difficulty(text):
    low = (text or "").lower()
    if re.search(r"\b(very (hard|difficult|tough)|challenging)\b", low):
        return 3
    if re.search(r"\b(hard|difficult|tough)\b", low):
        return 3
    if re.search(r"\b(easy|simple|quick|light)\b", low):
        return 1
    return None


def extract_subject_mention(text):
    """Heuristic: subject-ish word(s) before a task noun ('AI assignment')."""
    low = (text or "").lower()
    nouns = "|".join(TASK_NOUNS)
    m = re.search(rf"\b(?:my|the|a|an)?\s*([a-z][\w+-]*(?:\s+[a-z][\w+-]*)?)\s+(?:{nouns})\b", low)
    if m:
        cand = m.group(1).strip()
        # drop leading verbs/fillers
        cand = re.sub(r"^(add|create|new|do|finish|complete|submit|prepare|make|have|need|want|to|for)\s+",
                      "", cand).strip()
        cand = re.sub(r"\b(tomorrow|today|tonight|next|this|by|due|about|it|will|take|for|the|my)\b", "", cand).strip()
        if cand and cand not in ("i", "me", "we"):
            return cand
    return None


def clean_title(text, due_matched=None, dur_matched=None):
    """Strip request scaffolding into a task title."""
    t = text or ""
    for pattern in (r"^\s*(please\s+)?(can you\s+)?(add|create|make|new|schedule|set up)\b",
                    r"^\s*(i\s+)?(need|want|have|should|must)\s+(to\s+)?",
                    r"^\s*task\s*[:,-]?\s*", r"^\s*to\s+do\s*[:,-]?\s*",
                    r"\bit\s+will\s+take\s+about?\s+\S+(\s+\S+)?",
                    r"\bit'?s?\s+(going to\s+)?take\s+\S+(\s+\S+)?",
                    r"\bwill\s+take\s+about?\s+\S+(\s+\S+)?",
                    r"\babout\s+\d+\s*(hours?|hrs?|minutes?|mins?)",
                    r"\bthis\s+(is\s+)?(urgent|important|critical)\b",
                    r"\b(urgent|asap|high priority|very important|important)\b",
                    r"\bfor\s+(tonight|today|tomorrow)\b",
                    r"\bplease\b"):
        t = re.sub(pattern, " ", t, flags=re.IGNORECASE)
    if due_matched:
        t = re.sub(re.escape(due_matched), " ", t, flags=re.IGNORECASE)
    if dur_matched:
        t = re.sub(re.escape(dur_matched), " ", t, flags=re.IGNORECASE)
    # date/time words already matched are removed by resolve step below
    t = re.sub(r"\b(tomorrow|tmr|tmrw|tonight|today|next week|this week)\b", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(next|this)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)\b", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\b\d{1,2}\s*(am|pm)\b", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\b\d{1,2}:\d{2}\b", " ", t)
    t = re.sub(r"\b(on|by|due|at|for|until|till)\b\s*$", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip(" ,.:;-")
    return t


def parse_task_segment(segment, now=None, settings=None):
    """Deterministic extraction for one task phrase. Returns ExtractedTask."""
    if now is None:
        now = fdates.now_here(settings)
    text = segment
    t = ExtractedTask()

    due, due_matched = fdates.resolve_relative_date(text, now=now, settings=settings)
    if due:
        t.due_date = due
        hhmm, t_matched = fdates.parse_time_of_day(text)
        if hhmm:
            t.due_time = hhmm
    minutes, dur_matched = extract_duration(text)
    if minutes:
        t.estimated_minutes = minutes
    imp, hint = extract_importance(text)
    t.importance, t.priority_hint = imp, hint
    t.difficulty = extract_difficulty(text)
    t.subject = clean_str(extract_subject_mention(text), 120)

    title = clean_title(text, due_matched=None, dur_matched=dur_matched)
    title = clean_title(title, due_matched=due_matched)
    title = re.sub(r"^(?:i\s+)?(?:really\s+)?(?:need|have)\s+to\s+", "", title,
                   flags=re.IGNORECASE)
    title = re.sub(r"^(?:please\s+)?(?:my|the|a|an)\s+", "", title, flags=re.IGNORECASE)
    if not title or len(title) < 2:
        title = clean_str(segment, 200) or "New Task"
    t.title = title[:200]
    t.confidence = 0.6
    t.source = "local"
    if not t.due_date:
        t.missing.append("due date")
    if not t.estimated_minutes:
        t.missing.append("estimated duration")
    return t


def extract_deterministic(text, now=None, settings=None):
    """Full deterministic pass: intent + tasks (+ question when material)."""
    if now is None:
        now = fdates.now_here(settings)
    result = ExtractionResult(source="local")
    intent, q_action = detect_intent(text)
    result.intent = intent
    result.query_action = q_action

    if intent in ("chat", "query", "plan_day"):
        return result

    if intent == "goal":
        m = re.search(r"\b(?:learn|study|master|complete|finish)\s+(?:[^.;]{2,80})",
                      text, re.IGNORECASE)
        goal_title = clean_str(m.group(0), 200) if m else clean_str(text, 200)
        result.goal = {"title": goal_title, "description": clean_str(text, 1000)}
        return result

    if intent in ("add_task", "reschedule", "complete_task", "delete_task"):
        segs = split_requests(text)
        for seg in segs[:5]:  # bounded
            t = parse_task_segment(seg, now=now, settings=settings)
            t.source = "local"
            if intent == "reschedule":
                m = re.search(r"\b(?:move|reschedule|push|shift|postpone|delay)\s+(?:the\s+|my\s+)?(.+?)\s+task\b",
                              seg.lower())
                t.task_ref = (clean_task_ref(m.group(1)) if m
                              else clean_task_ref(t.title))
            elif intent == "complete_task":
                m = re.search(r"\b(?:finished|completed|complete|finish|done with|done)\s+(?:the\s+|my\s+)?(.+)",
                              seg.lower())
                t.task_ref = (clean_task_ref(m.group(1)) if m
                              else clean_task_ref(t.title))
            elif intent == "delete_task":
                m = re.search(r"^(?:delete|remove)\s+(?:the\s+|my\s+)?(.+)",
                              seg.lower())
                t.task_ref = (clean_task_ref(m.group(1)) if m
                              else clean_task_ref(t.title))
            if intent in ("reschedule", "complete_task", "delete_task"):
                # a ref equal to the raw title means the regexes found nothing
                if t.task_ref and t.task_ref.lower() == (t.title or "").lower() \
                        and t.title and _has_task_noun(t.title) is False:
                    t.task_ref = clean_task_ref(t.title)
                t.title = None  # ref intents reference, they do not create
            result.tasks.append(t)

        # Material ambiguity: deadline-sensitive task with no date at all
        first = result.tasks[0] if result.tasks else None
        if first and first.task_ref is None and not first.due_date:
            low = (text or "").lower()
            if any(k in low for k in DEADLINE_SENSITIVE):
                result.question = ("When is this due? (e.g. 'tomorrow', 'next monday', "
                                   "or a date) - I don't want to guess a deadline.")
        return result
    return result


# ==================== LLM EXTRACTION ====================

EXTRACTION_SYSTEM_PROMPT = """You are the task-extraction module of a student productivity app.
Convert the user's request into JSON. Respond with ONLY a JSON object, no prose.

Schema:
{
  "intent": "add_task|update_task|complete_task|delete_task|reschedule|plan_day|query|goal|chat",
  "query_action": "stats|next_class|today_tasks|weekly_classes|null",
  "question": "concise follow-up question or null",
  "reply": "short chat reply when intent=chat, else null",
  "tasks": [
    {
      "title": "short imperative title",
      "description": "extra detail or null",
      "subject": "academic subject mentioned, or null",
      "due_date": "YYYY-MM-DD or null",
      "due_time": "HH:MM 24h or null",
      "estimated_minutes": integer or null,
      "importance": 1|2|3 or null,
      "difficulty": 1|2|3 or null,
      "subtasks": ["..."],
      "recurrence": {"type": "daily|weekly", "days": ["mon",...]} or null,
      "task_ref": "title fragment of an EXISTING task being referenced, or null"
    }
  ],
  "goal": {"title": "...", "description": "...", "target_date": "YYYY-MM-DD or null"} or null
}

Rules:
- Use null for anything unknown. NEVER invent dates, durations, or subjects.
- Resolve relative dates against the CURRENT DATE given below.
- One entry per task; a request may contain several tasks.
- task_ref: for move/complete/delete requests, quote the words identifying the existing task.
- goal: only when the user describes a long-term learning goal or roadmap."""


_CLASS_ATTEND_RE = re.compile(
    r"^(?:attend|go\s+to|goes\s+to|going\s+to|have|has|had|attending)\s+.{0,60}?\bclass\b"
    r"(?:\s+(?:tomorrow|today|tonight|next\s+\w+|on\s+\w+))?$", re.IGNORECASE)


def looks_like_class_attendance(title):
    """True when a title describes attending a class rather than study work.

    Class occurrences get their time from the routine, never a copied study
    estimate (guards against 'attend networking class, ~180min' artifacts).
    """
    return bool(_CLASS_ATTEND_RE.match((title or "").strip()))


def extract_with_llm(text, provider, now=None, settings=None, subject_names=None):
    """LLM-based extraction; validated. Returns ExtractionResult (source='llm').

    Raises LLMError subclasses from the provider layer on failure - the caller
    falls back to the deterministic parser.
    """
    if now is None:
        now = fdates.now_here(settings)
    context = {
        "current_date": now.date().isoformat(),
        "weekday": now.strftime("%A"),
        "time": now.strftime("%H:%M"),
        "known_subjects": list(subject_names or [])[:25],  # minimal context only
    }
    user_payload = (f"CONTEXT: {context}\n"
                    f"CURRENT DATE IS {now.date().isoformat()} ({now.strftime('%A')}).\n"
                    f"REQUEST: {text}")
    raw = provider.chat_json(EXTRACTION_SYSTEM_PROMPT, user_payload,
                             temperature=0.0, max_tokens=1600)
    result = ExtractionResult(source="llm")
    intent = raw.get("intent")
    result.intent = intent if intent in (
        "add_task", "update_task", "complete_task", "delete_task", "reschedule",
        "plan_day", "query", "goal", "chat") else "unknown"
    result.query_action = raw.get("query_action") if raw.get("query_action") in (
        "stats", "next_class", "today_tasks", "weekly_classes") else None
    result.question = clean_str(raw.get("question"), 300)
    result.reply = clean_str(raw.get("reply"), 2000)

    tasks_raw = raw.get("tasks")
    if isinstance(tasks_raw, list):
        for tr in tasks_raw[:5]:
            tr = dict(tr) if isinstance(tr, dict) else {}
            tr["confidence"] = 0.85
            # class attendance copies no study duration - the routine owns it
            if looks_like_class_attendance(str(tr.get("title") or "")):
                tr["estimated_minutes"] = None
            task, warnings = validate_extracted_task(tr)
            # The model must not invent dates that skip validation silently.
            # ref-style intents carry task_ref instead of a title.
            if task.title or task.task_ref:
                result.tasks.append(task)
            result.warnings.extend(warnings)

    goal_raw = raw.get("goal")
    if isinstance(goal_raw, dict) and clean_str(goal_raw.get("title"), 200):
        result.goal = {
            "title": clean_str(goal_raw["title"], 200),
            "description": clean_str(goal_raw.get("description"), 1000),
            "target_date": (goal_raw.get("target_date")
                            if fdates.resolve_relative_date(str(goal_raw.get("target_date")) or "", now=now)[0]
                            else None),
        }
        if isinstance(goal_raw.get("target_date"), str) and re.match(r"^\d{4}-\d{2}-\d{2}$",
                                                                      goal_raw["target_date"]):
            from focus_agent.schemas import valid_date
            result.goal["target_date"] = valid_date(goal_raw["target_date"])
    if result.intent == "unknown" and not result.tasks and not result.reply:
        result.reply = None

    # Same material-ambiguity rule as the deterministic pass: a deadline-
    # sensitive task with no date asks a follow-up instead of a guessed date.
    first = result.tasks[0] if result.tasks else None
    if first and first.task_ref is None and not first.due_date and not result.question:
        low = (text or "").lower()
        if any(k in low for k in DEADLINE_SENSITIVE):
            result.question = ("When is this due? (e.g. 'tomorrow', 'next monday', "
                               "or a date) - I don't want to guess a deadline.")
    return result


def extract(text, provider=None, now=None, settings=None, subject_names=None):
    """Unified entry: LLM first (if provider), deterministic as fallback/merge.

    Returns ExtractionResult. Never raises for provider issues when a
    deterministic parse is possible (falls back and adds a warning).
    """
    if now is None:
        now = fdates.now_here(settings)
    det = extract_deterministic(text, now=now, settings=settings)

    if provider is None:
        return det
    try:
        llm_res = extract_with_llm(text, provider, now=now, settings=settings,
                                   subject_names=subject_names)
    except Exception as e:  # LLMError or unexpected -> graceful fallback
        det.warnings.append(f"LLM extraction unavailable ({e.__class__.__name__}); used local parser")
        return det

    # Prefer the LLM result when it found tasks; keep deterministic titles when better
    if llm_res.tasks or llm_res.intent not in ("unknown", "chat"):
        for dt, lt in zip(det.tasks, llm_res.tasks):
            if not lt.estimated_minutes and dt.estimated_minutes:
                lt.estimated_minutes = dt.estimated_minutes
            if not lt.due_date and dt.due_date:
                lt.due_date = dt.due_date
            elif (lt.due_date and dt.due_date and lt.due_date != dt.due_date):
                # The deterministic date came from an explicit keyword
                # ("tonight", "next wednesday") - keyword evidence beats the
                # model's inference about relative dates.
                llm_res.warnings.append(
                    f"date taken from local resolver ({dt.due_date}) "
                    f"over model's ({lt.due_date})")
                lt.due_date = dt.due_date
        # LLM intent unclear but the deterministic pass recognized the shape
        if llm_res.intent in ("unknown", None) and det.intent not in ("unknown", "chat"):
            llm_res.intent = det.intent
            llm_res.warnings.append(f"intent taken from local parser ({det.intent})")
            for lt2, dt2 in zip(llm_res.tasks, det.tasks):
                if not lt2.task_ref and dt2.task_ref:
                    lt2.task_ref = dt2.task_ref
        if llm_res.tasks:
            return llm_res
        if llm_res.intent in ("chat", "query", "plan_day", "goal"):
            return llm_res
    return det
