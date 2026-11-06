# ==================== SUBJECTS.PY ====================
# Subject detection: match a natural-language subject mention against the
# user's configured subjects and class routine, with confidence thresholds.
# Uncertain matches are NEVER silently assigned - the caller asks the user.

import re
from difflib import SequenceMatcher

# Confidence thresholds
AUTO_THRESHOLD = 0.82      # >= : assign automatically
ASK_THRESHOLD = 0.55       # >= : propose to the user as a choice
# < ASK_THRESHOLD: no confident match -> leave unassigned / ask

STOP_PREFIXES = {"class", "lecture", "lab", "exam", "test", "quiz",
                 "assignment", "homework", "project", "study", "revision",
                 "practice", "session", "the", "my", "a", "an", "for", "of"}

SUBJECT_ALIAS_GROUPS = (
    {"math", "maths", "mathematics", "calculus", "gonit", "গণিত"},
    {"ai", "artificial intelligence"},
    {"dbms", "database systems", "database management systems"},
    {"os", "operating systems", "operating system"},
    {"cn", "networking", "data communication", "data comm", "computer networks"},
    {"dsa", "data structures", "data structures and algorithms"},
    {"se", "software engineering"},
    {"ml", "machine learning"},
    {"physics", "phy", "পদার্থবিজ্ঞান", "পদার্থ"},
)


def _are_aliases(a, b):
    """True when normalized names a and b belong to the same academic alias group."""
    if not a or not b:
        return False
    for grp in SUBJECT_ALIAS_GROUPS:
        if a in grp and b in grp:
            return True
    return False


def _normalize(text):
    """Lowercase, strip punctuation/course codes and filler words (preserves Bangla vowel marks)."""
    if not text:
        return ""
    t = str(text).lower()
    t = re.sub(r"[!\"#$%&'()*.,/:;<=>?@\[\\\]^_`{|}~]", " ", t)
    t = re.sub(r"\b[a-z]{2,4}[- ]?\d{3,4}\b", " ", t)  # course codes: CSE2203
    tokens = [w for w in t.split() if w and w not in STOP_PREFIXES and not w.isdigit()]
    return " ".join(tokens) if tokens else str(text).lower().strip()


def _similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def _token_overlap(a, b):
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    return len(inter) / min(len(ta), len(tb))


def get_known_subjects(data):
    """All known subject names: vault subjects + class routine subjects/titles."""
    known = {}
    for name, info in (data.get("subjects") or {}).items():
        known[name] = "vault"
    for task in data.get("tasks", []):
        if task.get("type") == "class":
            subj = task.get("subject") or task.get("title")
            if subj and subj not in known:
                known[subj] = "routine"
    return known


def match_subject(mention, data):
    """Match a subject mention to known subjects.

    Returns dict: {subject, confidence, source, matched_on} or None.
    - mention normalized; exact/prefix/substring/token-overlap/fuzzy scoring.
    """
    if not mention or not str(mention).strip():
        return None
    nm = _normalize(mention)

    # Class titles are strong subject signals (routine knowledge): "CSE 3202"
    # refers to that class's subject even when the vault has no such entry.
    for task in data.get("tasks", []):
        if task.get("type") != "class":
            continue
        title = (task.get("title") or "").strip()
        if title and _normalize(title) == nm:
            subj = task.get("subject") or title
            return {"subject": subj, "confidence": 1.0, "source": "routine",
                    "matched_on": "class title", "auto": True}

    known = get_known_subjects(data)
    if not known:
        return None

    best = (None, 0.0, None, None)
    for name, source in known.items():
        nn = _normalize(name)
        if not nn:
            continue
        score, how = 0.0, None
        if nm == nn:
            score, how = 1.0, "exact"
        elif _are_aliases(nm, nn):
            score, how = 0.95, "alias"
        elif nm and nn and (nm in nn or nn in nm):
            score, how = 0.9, "contains"
        else:
            overlap = _token_overlap(nm, nn)
            fuzzy = _similarity(nm, nn)
            if overlap >= fuzzy:
                score, how = overlap, "token-overlap"
            else:
                score, how = fuzzy, "fuzzy"
        if score > best[1]:
            best = (name, score, source, how)

    name, score, source, how = best
    if score < ASK_THRESHOLD:
        return None
    return {
        "subject": name,
        "confidence": round(score, 3),
        "source": source,
        "matched_on": how,
        "auto": score >= AUTO_THRESHOLD,
    }


def propose_new_subject(mention, data):
    """Should the user be offered a NEW subject for this mention?

    Returns (allowed, reason). Creating a subject is allowed only when no
    existing subject passes ASK_THRESHOLD - and the UI/controller must confirm.
    """
    m = match_subject(mention, data)
    if m is None:
        clean = _normalize(mention) or (mention or "").strip()
        if not clean:
            return False, "empty subject name"
        return True, f"no existing subject resembles {mention!r}"
    return False, (f"existing subject '{m['subject']}' matches "
                   f"(confidence {m['confidence']:.2f}) - confirm instead")


def subjects_for_routine(data):
    """Weekday -> sorted list of {title, subject, start, end} classes."""
    week = {d: [] for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    for task in data.get("tasks", []):
        if task.get("type") != "class":
            continue
        sch = task.get("schedule") or {}
        for day in sch.get("days", []):
            if day in week:
                week[day].append({
                    "id": task.get("id"),
                    "title": task.get("title"),
                    "subject": task.get("subject") or task.get("title"),
                    "start": sch.get("start"),
                    "end": sch.get("end"),
                })
    for day in week:
        week[day].sort(key=lambda c: (c.get("start") or ""))
    return week
