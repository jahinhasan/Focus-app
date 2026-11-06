# ==================== DATES.PY ====================
# Timezone-aware date resolution for the agent.
# All relative dates ("tomorrow", "next monday", "tonight") resolve against the
# user's configured timezone and the current local date - never UTC.

import os
from datetime import datetime, timedelta, date
try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - py<3.9
    ZoneInfo = None


DEFAULT_TIMEZONE = "local"


def get_timezone(settings=None):
    """Resolve the user's timezone from settings/env.

    Accepts an IANA name ("Asia/Dhaka"), "local" or None.
    Returns a tzinfo object (or None for naive local time).
    """
    name = None
    if settings:
        name = settings.get("timezone")
    if not name or str(name).lower() in ("", "local", "system", "none"):
        name = os.environ.get("FOCUS_TZ", "local")
    name = str(name).strip()
    if name.lower() in ("local", "system", "none", ""):
        return None  # naive local time (datetime.now())
    if ZoneInfo is None:
        return None
    try:
        return ZoneInfo(name)
    except Exception:
        return None


def now_here(settings=None):
    """Current aware/naive datetime in the user's timezone."""
    tz = get_timezone(settings)
    if tz is not None:
        return datetime.now(tz)
    return datetime.now()


def today_str(settings=None):
    """Today's local date as YYYY-MM-DD (uses configured timezone)."""
    return now_here(settings).date().isoformat()


_BN_DIGIT_MAP = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def normalize_bn_digits(text):
    """Convert Bengali numerals (০-৯) to ASCII digits (0-9)."""
    return (text or "").translate(_BN_DIGIT_MAP)


def resolve_relative_date(text, now=None, settings=None):
    """Resolve a natural-language date fragment to YYYY-MM-DD.

    Supports English, Bangla (বাংলা), and Banglish:
    today/aj/ajke/আজ, tonight/aj rate/আজ রাতে, tomorrow/kal/kalke/কাল/আগামীকাল,
    day-after-tomorrow/porshu/পরশু, this/next <weekday> (incl. shombar..robibar
    and সোমবার..রবিবার), "in N days/weeks", "end of week", "end of month",
    explicit "23 jan"/"jan 23"/"2026-01-23", numeric "23/01" or "23-01".
    Returns (date_str_or_None, matched_phrase_or_None).
    Unknown values resolve to (None, None) - callers must not invent dates.
    """
    import re
    if now is None:
        now = now_here(settings)
    low = normalize_bn_digits(text or "").lower()

    # ISO explicit date
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", low)
    if m:
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return d.isoformat(), m.group(0)
        except ValueError:
            pass

    # today / tonight / tomorrow / day after tomorrow (English + Banglish + Bangla + common typos)
    m = re.search(r"(?:\bday\s+after\s+tomorrow\b|\bporshu\b|\bporoshu\b|আগামী\s*পরশু|পরশু)", low)
    if m:
        return (now.date() + timedelta(days=2)).isoformat(), m.group(0)
    m = re.search(r"(?:\b(?:tomorrow|tommorow|tomorow|tommorrow|tmr|tmrw|agami\s*kal|agamikal|kalker|kalke|kal)\b|আগামীকাল|কালকের|কালকে|কাল)", low)
    if m:
        return (now.date() + timedelta(days=1)).isoformat(), m.group(0)
    m = re.search(r"(?:\b(?:tonight|today|todat|tday|ajke|ajker|ajk|aj)\b|আজকে|আজকের|আজ)", low)
    if m:
        return now.date().isoformat(), m.group(0)

    # "in N days/weeks" or Banglish "N din por"
    m = re.search(r"\bin\s+(\d{1,3})\s*(day|days|week|weeks)\b", low)
    if m:
        n = int(m.group(1))
        delta = timedelta(days=n if m.group(2).startswith("day") else n * 7)
        return (now.date() + delta).isoformat(), m.group(0)
    m = re.search(r"\b(\d{1,3})\s*(?:din|দিন)\s*(?:por|pore|পরে|পর)\b", low)
    if m:
        return (now.date() + timedelta(days=int(m.group(1)))).isoformat(), m.group(0)

    # end of week / month
    m = re.search(r"\bend\s+of\s+(the\s+)?week\b", low)
    if m:
        days_ahead = (4 - now.weekday()) % 7  # Friday as end of week
        return (now.date() + timedelta(days=days_ahead)).isoformat(), m.group(0)
    m = re.search(r"\bend\s+of\s+(the\s+)?month\b", low)
    if m:
        nxt = (now.date().replace(day=28) + timedelta(days=4))
        last = nxt.replace(day=1) - timedelta(days=1)
        return last.isoformat(), m.group(0)

    # this/next <weekday> or bare <weekday> (English + Banglish + Bangla).
    weekdays = {
        "monday": 0, "mon": 0, "shombar": 0, "sombar": 0, "সোমবার": 0,
        "tuesday": 1, "tue": 1, "tues": 1, "mongolbar": 1, "mangalbar": 1, "মঙ্গলবার": 1,
        "wednesday": 2, "wed": 2, "budhbar": 2, "বুধবার": 2,
        "thursday": 3, "thu": 3, "thur": 3, "thurs": 3, "brihoshpotibar": 3, "brihospotibar": 3, "বৃহস্পতিবার": 3,
        "friday": 4, "fri": 4, "shukrobar": 4, "sukrobar": 4, "শুক্রবার": 4,
        "saturday": 5, "sat": 5, "shonibar": 5, "sonibar": 5, "শনিবার": 5,
        "sunday": 6, "sun": 6, "robibar": 6, "rabibar": 6, "রবিবার": 6,
    }
    m = re.search(
        r"(?:\b(?:(next|this|agami)\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
        r"mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun|"
        r"shombar|sombar|mongolbar|mangalbar|budhbar|brihoshpotibar|brihospotibar|"
        r"shukrobar|sukrobar|shonibar|sonibar|robibar|rabibar)\b|"
        r"(?:আগামী\s+)?(সোমবার|মঙ্গলবার|বুধবার|বৃহস্পতিবার|শুক্রবার|শনিবার|রবিবার))",
        low
    )
    if m:
        day_token = m.group(2) or m.group(3)
        if day_token in weekdays:
            target = weekdays[day_token]
            days_ahead = (target - now.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            return (now.date() + timedelta(days=days_ahead)).isoformat(), m.group(0)

    # "23 jan" / "jan 23" style
    months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", low)
    if m:
        d = _month_day(int(m.group(1)), months[m.group(2)], now)
        if d:
            return d.isoformat(), m.group(0)
    m = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})(?:st|nd|rd|th)?\b", low)
    if m:
        d = _month_day(int(m.group(2)), months[m.group(1)], now)
        if d:
            return d.isoformat(), m.group(0)

    # numeric 23/01 or 23-01 (day/month, this year, next if past).
    # Ambiguous forms where both numbers could be a month ("10-11", "3/4")
    # only count as dates after an explicit date word - "meet at 10-11" is a
    # time range, not a date; "due 23/11" is unambiguous (23 can't be a month).
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})\b(?!\s*(?:am|pm|:\d))", low)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        if 1 <= day <= 31 and 1 <= month <= 12:
            unambiguous = day > 12 or month > 12
            if not unambiguous:
                prefix = low[max(0, m.start() - 10):m.start()]
                unambiguous = bool(re.search(r"\b(?:due|by|on|until|till)\s*$", prefix))
            if unambiguous:
                d = _month_day(day, month, now)
                if d:
                    return d.isoformat(), m.group(0)

    return None, None


def _month_day(day, month, now):
    """Build a date in the current year; roll to next year if already past."""
    for year in (now.year, now.year + 1):
        try:
            d = date(year, month, day)
        except ValueError:
            return None
        if d >= now.date():
            return d
    return None


def parse_time_of_day(text):
    """Extract a HH:MM time or daypart hint from text (English, Banglish, Bangla).

    Returns (hh_mm_str_or_None, matched_or_None). "tonight"/"raate" -> 20:00,
    "morning"/"shokale" -> 09:00, "afternoon"/"dupure" -> 14:00, "evening"/"bikale" -> 19:00,
    "at 3pm" / "at 15:30" / "rat 8 tar modhe" / "bikal 5 tay" -> parsed.
    """
    import re
    low = normalize_bn_digits(text or "").lower()
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", low)
    if m:
        h = int(m.group(1)) % 12
        if m.group(3) == "pm":
            h += 12
        return f"{h:02}:{m.group(2) or '00'}", m.group(0)
    m = re.search(r"\b(?:at|by|before)\s+(\d{1,2}):(\d{2})\b", low)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        if 0 <= h < 24 and 0 <= mn < 60:
            return f"{h:02}:{mn:02}", m.group(0)
    # Banglish / Bangla explicit hour ("rat 8 tar modhe", "bikal 5 tay", "shokal 10 ta", "রাত ৮টার মধ্যে")
    m = re.search(
        r"(?:(rat|raat|raate|rate|রাত|রাতে|sondha|shondha|sondhay|shondhay|সন্ধ্যা|সন্ধ্যায়|সন্ধ্যায়|"
        r"bikal|bikale|বিকাল|বিকেলে|dupur|dupure|দুপুর|দুপুরে|"
        r"shokal|sokal|shokale|sokale|সকাল|সকালে|ভোর|bhor)\s+)?"
        r"\b(\d{1,2})(?::(\d{2}))?\s*(?:tar|tay|ta|টার|টায়|টায়|টা)\b"
        r"(?:\s*(?:modhe|moddhe|মধ্যে|নাগাদ|nagad|porjonto|পর্যন্ত))?",
        low
    )
    if m:
        daypart = (m.group(1) or "").strip()
        h = int(m.group(2))
        mn = int(m.group(3) or 0)
        if 1 <= h <= 12 and 0 <= mn < 60:
            pm_parts = ("rat", "raat", "raate", "rate", "রাত", "রাতে",
                        "sondha", "shondha", "sondhay", "shondhay", "সন্ধ্যা", "সন্ধ্যায়", "সন্ধ্যায়",
                        "bikal", "bikale", "বিকাল", "বিকেলে",
                        "dupur", "dupure", "দুপুর", "দুপুরে")
            am_parts = ("shokal", "sokal", "shokale", "sokale", "সকাল", "সকালে", "ভোর", "bhor")
            if daypart in pm_parts:
                if h < 12:
                    h += 12
            elif daypart in am_parts:
                if h == 12:
                    h = 0
            else:
                # No explicit daypart: 1..7 defaults to PM (13:00..19:00)
                if 1 <= h <= 7:
                    h += 12
            return f"{h:02}:{mn:02}", m.group(0)
    for hint, hh in (
        ("tonight", 20), ("this evening", 19), ("evening", 19),
        ("afternoon", 14), ("noon", 12), ("morning", 9),
        ("raate", 20), ("rate", 20), ("raat", 20), ("rat", 20), ("রাতে", 20), ("রাত", 20),
        ("sondhay", 19), ("shondhay", 19), ("সন্ধ্যায়", 19), ("সন্ধ্যায়", 19),
        ("bikale", 16), ("bikal", 16), ("বিকেলে", 16), ("বিকাল", 16),
        ("dupure", 14), ("dupur", 14), ("দুপুরে", 14), ("দুপুর", 14),
        ("shokale", 9), ("sokale", 9), ("shokal", 9), ("sokal", 9), ("সকালে", 9), ("সকাল", 9),
    ):
        if re.search(rf"(?:\b{re.escape(hint)}\b)" if hint.isascii() else re.escape(hint), low):
            return f"{hh:02}:00", hint
    return None, None


def weekday_key(d):
    """3-letter lowercase day key used by the class routine ('mon')."""
    return d.strftime("%a").lower()[:3]


def hhmm_to_minutes(s):
    """'09:30' -> 570. Returns None on malformed input."""
    try:
        parts = str(s).split(":")
        h, m = int(parts[0]), int(parts[1])
        if 0 <= h < 24 and 0 <= m < 60:
            return h * 60 + m
    except (ValueError, IndexError, TypeError):
        pass
    return None


def minutes_to_hhmm(total):
    """570 -> '09:30' (wraps at midnight: 1440 -> '00:00')."""
    total = int(total) % (24 * 60)
    return f"{total // 60:02}:{total % 60:02}"


def date_range_days(start_date_str, days):
    """List of date strings from start (inclusive) for N days."""
    try:
        d = date.fromisoformat(start_date_str)
    except (ValueError, TypeError):
        return []
    return [(d + timedelta(days=i)).isoformat() for i in range(max(0, days))]


def shift_date(date_str, days):
    """YYYY-MM-DD + N days -> YYYY-MM-DD (negative days allowed)."""
    from datetime import date as _d, timedelta as _td
    base = _d.fromisoformat(date_str)
    return (base + _td(days=days)).isoformat()
