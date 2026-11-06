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
    valid_date, valid_hhmm,
)

NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "half": 0.5,
    "ek": 1, "dui": 2, "tin": 3, "char": 4, "pach": 5, "choy": 6,
    " এক ": 1, "এক": 1, "দুই": 2, "তিন": 3, "চার": 4, "পাঁচ": 5, "ছয়": 6,
}

TASK_NOUNS = ("assignment", "assignmant", "asignmant", "assigment", "assinment",
              "homework", "homewrok", "exam", "exm", "test", "quiz", "quize",
              "project", "projct", "essay", "report", "presentation", "presentaion",
              "lab", "reading", "revision", "practice", "task", "submission",
              "proposal", "thesis", "porikkha", "পরীক্ষা", "এসাইনমেন্ট", "অ্যাসাইনমেন্ট", "প্রজেক্ট")

# Keywords whose deadline is material - a missing due date triggers a question
DEADLINE_SENSITIVE = ("exam", "exm", "submission", "submit", "deadline", "due",
                      "assignment", "assignmant", "asignmant", "assigment", "assinment",
                      "homework", "homewrok", "project", "projct", "test", "quiz", "quize",
                      "application", "apply", "register", "registration",
                      "hand in", "hand-in", "turn in", "scholarship", "enroll",
                      "porikkha", "পরীক্ষা", "জমা", "joma")


# ==================== DETERMINISTIC PARSER ====================

def detect_intent(text):
    """Classify the request without any model. Returns (intent, query_action)."""
    low = fdates.normalize_bn_digits(text or "").lower().strip()

    if (re.search(r"\b(don'?t|do not|never)\s+(schedule|plan|book|put)\b", low)
            or re.search(r"\b(block|blocked|busy|unavailable|occupied|byasto|ব্যস্ত)\b", low)) \
            and extract_time_range(low):
        return "block_time", None
    if re.search(r"\b(plan|schedule)\b.*\b(day|today|tomorrow|week|aj|ajke|ajker|kal|kalke)\b", low) \
            or re.search(r"\b(daily\s+plan|plan\s+my\s+day|what\s+should\s+i\s+do)\b", low) \
            or re.search(r"\b(plan\s+koro|routine\s+koro|ajker\s+plan|kalker\s+plan|ki\s+korbo)\b", low) \
            or re.search(r"(প্ল্যান\s*করো|রুটিন\s*করো|আজকের\s*প্ল্যান|কালকের\s*প্ল্যান|কী\s*করব|কি\s*করব)", low) \
            or re.search(r"\bprepare\s+a\s+revision\s+plan\b", low) \
            or re.search(r"\brevision\s+plan\b", low) \
            or re.search(r"\bplan\b.*\b(pending|tasks|assignments|everything|work)\b", low):
        return "plan_day", None
    if re.search(r"^\s*(move|reschedule|push|shift|postpone|delay)\b", low) or \
            re.search(r"\bmove\b.*\btask\b", low) and re.search(r"\b(move|reschedule)\b", low) or \
            re.search(r"\b(reschedule|postpone|delay|pechiye|pichiye)\b", low) or \
            re.search(r"(পিছিয়ে|পিছিয়ে\s*দাও|রিশিডিউল)", low):
        return "reschedule", None
    if re.search(r"\b(finished|completed|done with|mark.*(done|complete)|i completed|shesh\s+korechi|sesh\s+korechi|komplit)\b", low) or \
            re.search(r"(শেষ\s*করেছি|কমপ্লিট\s*করেছি|হয়ে\s*গেছে|হয়ে\s*গেছে)", low):
        return "complete_task", None
    if re.search(r"^\s*(delete|remove|bad\s+dao|muche\s+felo)\b", low) or \
            re.search(r"^(ডিলিট|মুছে\s*ফেলো|বাদ\s*দাও)", low):
        return "delete_task", None
    if re.search(r"\b(goal|roadmap|milestone|learning path|master\s+plan)\b", low) or \
            re.search(r"\bi\s+(want|would like)\s+to\s+(learn|master|study)\b", low) or \
            re.search(r"\b(ami\s+.*\s+shikhte\s+chai|shikhte\s+chai)\b", low) or \
            re.search(r"(শিখতে\s*চাই|রোডম্যাপ)", low) or \
            re.search(r"\bmy goal is\b", low):
        return "goal", None
    if re.match(r"^(analyze|analysis|how productive|productivity)\b", low):
        return "query", "productivity"
    if re.match(r"^(what|when|where|which|who|how much|how many|how long|show|list|tell|do i have|kobe|kokhon|ki\s+ki)\b", low) or \
            re.search(r"(কবে|কখন|কী\s*কী\s*কাজ|নেক্সট\s*ক্লাস)", low):
        action = None
        if re.search(r"\bxp\b|\blevel\b|\bprogress\b|productivity", low):
            action = "stats"
        elif re.search(r"\bnext class\b|\bnext lecture\b|\bporer\s+class\b|নেক্সট\s*ক্লাস|পরের\s*ক্লাস", low):
            action = "next_class"
        elif re.search(r"\b(week|weekly|soptah|সপ্তাহ)\b", low):
            action = "weekly_classes"
        elif re.search(r"\b(today|tonight|aj|ajke|ajker)\b|\bschedule\b|আজ|আজকে|আজকের", low):
            action = "today_tasks"
        return "query", action
    if re.match(r"^(hi|hello|hey|thanks|thank you|good (morning|evening|afternoon)|salam|assalamu|hlw|ki\s+obostha|kemon\s+acho)\b", low) or \
            re.match(r"^(হাই|হ্যালো|সালাম|কেমন\s*আছো|ধন্যবাদ)", low):
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
    """Find estimated duration (English, Banglish, Bangla). Returns (minutes_or_None, matched_or_None)."""
    low = fdates.normalize_bn_digits(text or "").lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:-\s*)?(hours?|hrs?|h|ghonta|ghanta|ঘণ্টা|ঘন্টা)(?:\b|(?=\s|$|[.,;]))", low)
    if m:
        return int(float(m.group(1)) * 60), m.group(0)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:-\s*)?(minutes?|mins?|m|minit|মিনিট)(?:\b|(?=\s|$|[.,;]))", low)
    if m and "h" not in m.group(0):
        return int(float(m.group(1))), m.group(0)
    m = re.search(r"(?:\bhalf\s+an\s+hour\b|\badha\s+ghonta\b|আধা\s*ঘণ্টা|আধা\s*ঘন্টা)", low)
    if m:
        return 30, m.group(0)
    m = re.search(r"(?:\b(?:an\s+hour\s+and\s+a\s+half|one\s+and\s+a\s+half\s+hours|der\s+ghonta)\b|দেড়\s*ঘণ্টা|দেড়\s*ঘণ্টা)", low)
    if m:
        return 90, m.group(0)
    m = re.search(r"\b(two|three|four|five|six|one|ek|dui|tin|char|pach|choy)\s+(?:hours?|ghonta|ghanta)\b", low)
    if m:
        return int(NUMBER_WORDS[m.group(1)] * 60), m.group(0)
    m = re.search(r"(এক|দুই|তিন|চার|পাঁচ|ছয়)\s*(?:ঘণ্টা|ঘন্টা)", low)
    if m:
        return int(NUMBER_WORDS[m.group(1)] * 60), m.group(0)
    m = re.search(r"\b(\d+)\s*h\b", low)
    if m:
        return int(m.group(1)) * 60, m.group(0)
    return None, None


def _number_word(n):
    return NUMBER_WORDS.get(n, n)


def extract_importance(text):
    """Return (importance_or_None, priority_hint_or_None)."""
    low = (text or "").lower()
    if re.search(r"\b(urgent|critical|asap|highest priority|very important|khub\s+joruri|khub\s+dorkar)\b|(?:খুব\s*জরুরি|জরুরি)", low):
        return 3, 90
    if re.search(r"\b(important|high priority|priority|joruri|dorkar|guruttopurno)\b|(?:গুরুত্বপূর্ণ|দরকার)", low):
        return 3, 70
    if re.search(r"\b(low priority|whenever|no rush|someday|backlog|pore\s+korleo\s+hobe)\b", low):
        return 1, 20
    return None, None


def extract_difficulty(text):
    low = (text or "").lower()
    if re.search(r"\b(very (hard|difficult|tough)|challenging|khub\s+kothin|onek\s+kothin)\b|(?:খুব\s*কঠিন|অনেক\s*কঠিন)", low):
        return 3
    if re.search(r"\b(hard|difficult|tough|kothin)\b|কঠিন", low):
        return 3
    if re.search(r"\b(easy|simple|quick|light|sohoj|shohoj)\b|সহজ", low):
        return 1
    return None


def extract_subject_mention(text):
    """Heuristic: subject-ish word(s) before a task noun ('AI assignment')."""
    low = (text or "").lower()
    nouns = "|".join(TASK_NOUNS)
    m = re.search(rf"\b(?:my|the|a|an|amar)?\s*([a-z][\w+-]*(?:\s+[a-z][\w+-]*)?)\s+(?:{nouns})\b", low)
    if m:
        cand = m.group(1).strip()
        # drop leading verbs/fillers
        cand = re.sub(r"^(add|create|new|do|finish|complete|submit|prepare|make|have|need|want|to|for|amar|kal|kalke|aj|ajke|porshu|also|and|tay|tar|ta|am|pm)\s+",
                      "", cand).strip()
        cand = re.sub(r"\b(tomorrow|tommorow|today|tonight|next|this|by|due|about|it|will|take|for|the|my|a|an|also|and|amar|kal|kalke|aj|ajke|porshu|ektu|ekta|tay|tar|ta|am|pm|shokal|shokale|bikal|bikale|rat|raat|raate|dupur|dupure)\b", "", cand).strip()
        cand = re.sub(r"\s+", " ", cand).strip()
        if cand and cand not in ("i", "me", "we", "amar", "a", "an", "the"):
            return cand
    return None


def clean_title(text, due_matched=None, dur_matched=None, time_matched=None):
    """Strip request scaffolding into a task title."""
    t = text or ""
    if time_matched:
        t = re.sub(re.escape(time_matched), " ", t, flags=re.IGNORECASE)
    if due_matched:
        t = re.sub(re.escape(due_matched), " ", t, flags=re.IGNORECASE)
    if dur_matched:
        t = re.sub(re.escape(dur_matched), " ", t, flags=re.IGNORECASE)
    for pattern in (r"^\s*(please\s+)?(can you\s+)?(add|create|make|new|schedule|set up)\b",
                    r"^\s*(i\s+)?(need|want|have|should|must)\s+(to\s+)?",
                    r"^\s*(amar\s+|আমার\s+|amake\s+|আমাকে\s+)",
                    r"^\s*task\s*[:,-]?\s*", r"^\s*to\s+do\s*[:,-]?\s*",
                    r"\bit\s+will\s+take\s+about?\s+\S+(\s+\S+)?",
                    r"\bit'?s?\s+(going to\s+)?take\s+\S+(\s+\S+)?",
                    r"\bwill\s+take\s+about?\s+\S+(\s+\S+)?",
                    r"\babout\s+\d+\s*(hours?|hrs?|minutes?|mins?)",
                    r"\bthis\s+(is\s+)?(urgent|important|critical)\b",
                    r"\b(urgent|asap|high priority|very important|important|joruri|khub\s+kothin|onek\s+kothin|kothin|sohoj|shohoj)\b",
                    r"(?:খুব\s*কঠিন|অনেক\s*কঠিন|কঠিন|সহজ|জরুরি|গুরুত্বপূর্ণ)",
                    r"\b(joma\s+dite\s+hobe|joma\s+diote\s+hobe|joma\s+dao|joma\s+dewa|diote\s+hobe|dite\s+hobe|korte\s+hobe|ache|ase|acche|lagbe|somoy\s+lagbe)\b",
                    r"(?:জমা\s*দিতে\s*হবে|দিতে\s*হবে|করতে\s*হবে|আছে|লাগবে|সময়\s*লাগবে|সময়\s*লাগবে)",
                    r"\b(joma|modhe|moddhe|porjonto|nagad)\b",
                    r"(?:জমা|মধ্যে|পর্যন্ত|নাগাদ)",
                    r"\bfor\s+(tonight|today|tomorrow)\b",
                    r"\bplease\b"):
        t = re.sub(pattern, " ", t, flags=re.IGNORECASE)
    # date/time words already matched are removed by resolve step below
    t = re.sub(r"\b(tomorrow|tommorow|tomorow|tommorrow|tmr|tmrw|tonight|today|todat|next week|this week|agamikal|agami\s+kal|kalker|kalke|kal|ajke|ajker|ajk|aj|porshu|poroshu)\b", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"(?:আগামীকাল|কালকের|কালকে|কাল|আজকে|আজকের|আজ|আগামী\s*পরশু|পরশু)", " ", t)
    t = re.sub(r"\b(next|this|agami)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun|shombar|sombar|mongolbar|budhbar|brihoshpotibar|shukrobar|shonibar|robibar)\b", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(rat|raat|raate|rate|sondha|shondha|sondhay|shondhay|bikal|bikale|dupur|dupure|shokal|sokal|shokale|sokale)\b", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"(?:রাতে|রাত|সন্ধ্যায়|সন্ধ্যায়|সন্ধ্যা|বিকেলে|বিকাল|দুপুরে|দুপুর|সকালে|সকাল)", " ", t)
    t = re.sub(r"\b\d{1,2}\s*(am|pm|tar|tay|ta)\b", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\b\d{1,2}:\d{2}\b", " ", t)
    t = re.sub(r"\b(on|by|due|at|for|until|till|amar|ekta|ektu)\b\s*$", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(amar|ekta|ektu)\b", " ", t, flags=re.IGNORECASE)
    # Fix common student spelling typos in task nouns
    for bad, good in (("assignmant", "assignment"), ("asignmant", "assignment"),
                      ("assigment", "assignment"), ("assinment", "assignment"),
                      ("homewrok", "homework"), ("projct", "project"),
                      ("presentaion", "presentation"), ("quize", "quiz")):
        t = re.sub(rf"\b{bad}\b", good, t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip(" ,.:;-")
    return t


def parse_task_segment(segment, now=None, settings=None):
    """Deterministic extraction for one task phrase. Returns ExtractedTask."""
    if now is None:
        now = fdates.now_here(settings)
    text = segment
    t = ExtractedTask()

    due, due_matched = fdates.resolve_relative_date(text, now=now, settings=settings)
    hhmm, t_matched = fdates.parse_time_of_day(text)
    if due:
        t.due_date = due
    if hhmm:
        t.due_time = hhmm
    minutes, dur_matched = extract_duration(text)
    if minutes:
        t.estimated_minutes = minutes
    imp, hint = extract_importance(text)
    t.importance, t.priority_hint = imp, hint
    t.difficulty = extract_difficulty(text)
    t.subject = clean_str(extract_subject_mention(text), 120)

    title = clean_title(text, due_matched=due_matched, dur_matched=dur_matched,
                        time_matched=t_matched)
    title = re.sub(r"^(?:i\s+)?(?:really\s+)?(?:need|have)\s+to\s+", "", title,
                   flags=re.IGNORECASE)
    title = re.sub(r"^(?:please\s+)?(?:my|the|a|an)\s+", "", title, flags=re.IGNORECASE)
    if not title or len(title) < 2:
        title = clean_str(segment, 200) or "New Task"
    # Capitalize first letter cleanly if lowercase
    if title and title[0].islower():
        title = title[0].upper() + title[1:]
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

    if intent == "block_time":
        block = extract_block(text, now=now, settings=settings)
        if block:
            result.blocks.append(block)
        else:
            result.question = ("What time should I keep free? (e.g. 'from 10 AM "
                               "to 12 PM') - I won't guess the hours.")
        return result

    if intent in ("chat", "query", "plan_day"):
        if intent == "plan_day":
            result.available_minutes = extract_free_capacity(text)
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
  "intent": "add_task|update_task|complete_task|delete_task|reschedule|plan_day|block_time|query|goal|chat",
  "query_action": "stats|next_class|today_tasks|weekly_classes|productivity|null",
  "question": "concise follow-up question or null",
  "reply": "short chat reply when intent=chat, else null",
  "blocks": [{"title": "...", "days": ["mon"], "date": "YYYY-MM-DD or null",
              "start": "HH:MM", "end": "HH:MM"}],
  "available_minutes": integer or null,
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
- The user may write in English, Bangla (বাংলা), or Banglish (Romanized Bengali, e.g. "kal amar AI assignment ache, 2 ghonta lagbe, kothin", "ajker plan koro"). Understand all three seamlessly.
- Use null for anything unknown. NEVER invent dates, durations, or subjects.
- Resolve relative dates against the CURRENT DATE given below (e.g., aj/ajke/আজ = today, kal/kalke/কাল = tomorrow, porshu/পরশু = day after tomorrow).
- One entry per task; a request may contain several tasks.
- blocks: when the user says a time is taken (class, busy, "don't schedule
  X to Y"), list it here with times resolved to 24h HH:MM. Recurring blocks
  use "days", one-off blocks use "date".
- available_minutes: when the user names a free-time budget ("I have three
  hours free"), set it in minutes.
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


def extract_time_range(text):
    """Find 'from 10 AM to 12 PM' / '10-12' / '10:00 to 12:00' style ranges.

    Returns (start_hhmm, end_hhmm) or (None, None). 24h conversion is explicit:
    an am/pm on one side applies to both when the other omits it and the raw
    numbers stay valid."""
    low = (text or "").lower()
    m = re.search(r"from\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:to|until|till|through|-|–)\s*"
                  r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", low)
    if not m:
        m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:-|–|to)\s*"
                      r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", low)
    if not m:
        return None, None

    def to24(h, mn, ap):
        h, mn = int(h), int(mn or 0)
        ap = (ap or "").strip()
        if ap == "pm" and h < 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
        if 0 <= h < 24 and 0 <= mn < 60:
            return f"{h:02d}:{mn:02d}"
        return None

    start = to24(m.group(1), m.group(2), m.group(3))
    end = to24(m.group(4), m.group(5), m.group(6))
    if not start or not end or end <= start:
        return None, None
    return start, end


_WEEKDAY_RE = re.compile(r"\b(mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun|"
                         r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.IGNORECASE)
_WEEKDAY_KEY = {"mon": "mon", "monday": "mon", "tue": "tue", "tues": "tue",
                "tuesday": "tue", "wed": "wed", "wednesday": "wed",
                "thu": "thu", "thur": "thu", "thurs": "thu", "thursday": "thu",
                "fri": "fri", "friday": "fri", "sat": "sat", "saturday": "sat",
                "sun": "sun", "sunday": "sun"}


def extract_weekdays(text):
    """Weekday keys mentioned in text (bounded, deduped)."""
    found = []
    for m in _WEEKDAY_RE.finditer(text or ""):
        k = _WEEKDAY_KEY[m.group(1).lower()]
        if k not in found:
            found.append(k)
    return found


def extract_free_capacity(text):
    """'I have three hours free' / '2 hours free' -> minutes or None."""
    low = (text or "").lower()
    m = re.search(r"\b(?:have|got)\s+(\d+(?:\.\d+)?|"
                  + "|".join(NUMBER_WORDS.keys()) + r")\s*(hours?|hrs?|h|minutes?|mins?)\s+free\b",
                  low)
    if not m:
        return None
    raw = m.group(1)
    n = NUMBER_WORDS.get(raw)
    if n is None:
        try:
            n = float(raw)
        except ValueError:
            return None
    unit = m.group(2)
    minutes = int(n * 60) if unit.startswith(("hour", "hr", "h")) else int(n)
    return minutes if 15 <= minutes <= 16 * 60 else None


def extract_block(text, now=None, settings=None):
    """Parse a 'don't schedule ...' request into a block dict (or None)."""
    start, end = extract_time_range(text)
    if not start:
        return None
    low = (text or "").lower()
    title = "Busy"
    tm = re.search(r"\b(?:have|had|got)\s+(?:a|an|my)?\s*([a-z][a-z \-']{2,40}?)(?=\s+from\b|\s+\d)",
                   low)
    if tm:
        title = tm.group(1).strip()
        if title.endswith(" class"):
            title = title.replace(" class", " class").strip()
    block = {"title": clean_str(title, 120) or "Busy", "start": start, "end": end}
    days = extract_weekdays(text)
    if days:
        block["days"] = days
    if now is not None:
        date_str, _matched = fdates.resolve_relative_date(text, now=now, settings=settings)
        if date_str and not days:
            block["date"] = date_str
    return block


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

    blocks_raw = raw.get("blocks")
    if isinstance(blocks_raw, list):
        for br in blocks_raw[:5]:
            if not isinstance(br, dict):
                continue
            start = valid_hhmm(br.get("start"))
            end = valid_hhmm(br.get("end"))
            if not start or not end or end <= start:
                continue
            block = {"title": clean_str(br.get("title"), 120) or "Busy",
                     "start": start, "end": end}
            days = [d for d in (br.get("days") or [])
                    if isinstance(d, str) and d.lower()[:3] in
                    ("mon", "tue", "wed", "thu", "fri", "sat", "sun")]
            if days:
                block["days"] = sorted({d.lower()[:3] for d in days})
            date_v = valid_date(br.get("date"))
            if date_v:
                block["date"] = date_v
            result.blocks.append(block)

    cap = raw.get("available_minutes")
    if isinstance(cap, (int, float)) and 15 <= cap <= 16 * 60:
        result.available_minutes = int(cap)

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

    # Prefer the LLM result when it found tasks; keep deterministic titles/subjects when LLM hallucinates
    if llm_res.tasks or llm_res.intent not in ("unknown", "chat"):
        text_low = (text or "").lower()
        from focus_agent import subjects as fsubjects
        for dt, lt in zip(det.tasks, llm_res.tasks):
            if not lt.estimated_minutes and dt.estimated_minutes:
                lt.estimated_minutes = dt.estimated_minutes
            if not lt.due_time and dt.due_time:
                lt.due_time = dt.due_time
            if not lt.difficulty and dt.difficulty:
                lt.difficulty = dt.difficulty
            if not lt.importance and dt.importance:
                lt.importance = dt.importance
            if not lt.due_date and dt.due_date:
                lt.due_date = dt.due_date
            elif (lt.due_date and dt.due_date and lt.due_date != dt.due_date):
                # The deterministic date came from an explicit keyword
                # ("tonight", "next wednesday", "kal") - keyword evidence beats the
                # model's inference about relative dates.
                llm_res.warnings.append(
                    f"date taken from local resolver ({dt.due_date}) "
                    f"over model's ({lt.due_date})")
                lt.due_date = dt.due_date

            # Guard against LLM hallucinating a known_subject not mentioned in text
            if lt.subject:
                subj_tokens = [w for w in re.split(r"\W+", lt.subject.lower()) if len(w) >= 2]
                subj_in_text = any(w in text_low for w in subj_tokens)
                if not subj_in_text and dt.subject:
                    subj_in_text = fsubjects._are_aliases(
                        fsubjects._normalize(lt.subject),
                        fsubjects._normalize(dt.subject)
                    )
                if not subj_in_text:
                    llm_res.warnings.append(
                        f"dropped hallucinated LLM subject '{lt.subject}'; "
                        f"used local '{dt.subject}'")
                    lt.subject = dt.subject
            elif dt.subject:
                lt.subject = dt.subject

            # Guard against LLM hallucinating a title from known_subjects not in text
            if lt.title and dt.title and subject_names:
                lt_low = lt.title.lower()
                hallucinated_title = False
                for ks in subject_names:
                    ks_low = str(ks).lower()
                    ks_words = [w for w in re.split(r"\W+", ks_low) if len(w) >= 3]
                    if ks_low and len(ks_low) >= 3 and ks_low in lt_low and not any(w in text_low for w in ks_words):
                        hallucinated_title = True
                        break
                if hallucinated_title:
                    llm_res.warnings.append(
                        f"title taken from local parser ('{dt.title}') "
                        f"over hallucinated model title ('{lt.title}')")
                    lt.title = dt.title

        # If all tasks now have a resolved due_date, clear stale LLM due-date follow-up question
        if llm_res.tasks and all(t.due_date for t in llm_res.tasks) and llm_res.question:
            if re.search(r"\b(due|deadline|date|when)\b", llm_res.question.lower()):
                llm_res.question = None
        # LLM intent unclear but the deterministic pass recognized the shape
        if llm_res.intent in ("unknown", None) and det.intent not in ("unknown", "chat"):
            llm_res.intent = det.intent
            llm_res.warnings.append(f"intent taken from local parser ({det.intent})")
            for lt2, dt2 in zip(llm_res.tasks, det.tasks):
                if not lt2.task_ref and dt2.task_ref:
                    lt2.task_ref = dt2.task_ref
        # Structural intents anchored on explicit keywords ("plan my day",
        # "reschedule", "don't schedule") beat model inference - same rule as
        # dates: keyword evidence wins.
        elif det.intent in ("plan_day", "block_time", "reschedule",
                            "complete_task", "delete_task", "query") \
                and llm_res.intent != det.intent:
            llm_res.intent = det.intent
            llm_res.warnings.append(f"intent taken from local parser ({det.intent}) "
                                    f"over model's ({llm_res.intent})")
            for lt3, dt3 in zip(llm_res.tasks, det.tasks):
                if not lt3.task_ref and dt3.task_ref:
                    lt3.task_ref = dt3.task_ref
        # model found nothing actionable but the local parser did (e.g. model
        # answered "goal" for a concrete task request) -> trust the parser
        if not llm_res.tasks and det.intent == "add_task" and det.tasks \
                and llm_res.intent in ("goal", "unknown"):
            det.warnings.append("intent/tasks taken from local parser "
                                f"(model said {llm_res.intent})")
            return det
        if llm_res.tasks:
            return llm_res
        if llm_res.intent in ("chat", "query", "plan_day", "goal"):
            return llm_res
    return det
