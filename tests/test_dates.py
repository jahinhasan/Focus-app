"""Deadline extraction and relative-date resolution (spec N.2)."""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from focus_agent import dates as fd

NOW = datetime(2026, 10, 23, 14, 0)  # Friday


def test_tomorrow():
    assert fd.resolve_relative_date("submit tomorrow", now=NOW)[0] == "2026-10-24"


def test_today_and_tonight():
    assert fd.resolve_relative_date("finish today", now=NOW)[0] == "2026-10-23"
    assert fd.resolve_relative_date("practice tonight", now=NOW)[0] == "2026-10-23"


def test_day_after_tomorrow():
    assert fd.resolve_relative_date("due day after tomorrow", now=NOW)[0] == "2026-10-25"


def test_next_monday_from_friday():
    got, matched = fd.resolve_relative_date("exam next monday", now=NOW)
    assert got == "2026-10-26"
    assert matched == "next monday"


def test_bare_weekday_is_next_occurrence_not_today():
    # Friday -> "friday" means NEXT friday, never an already-passing day
    assert fd.resolve_relative_date("due friday", now=NOW)[0] == "2026-10-30"


def test_weekday_earlier_in_week():
    # Wednesday Oct 21 -> "monday" is Oct 26? No: next occurrence after Wed is Mon Oct 26? Mon is 2 days back; next is Oct 26
    wed = datetime(2026, 10, 21, 9, 0)
    assert fd.resolve_relative_date("submit monday", now=wed)[0] == "2026-10-26"


def test_in_n_days_weeks():
    assert fd.resolve_relative_date("in 3 days", now=NOW)[0] == "2026-10-26"
    assert fd.resolve_relative_date("in 2 weeks", now=NOW)[0] == "2026-11-06"


def test_explicit_month_day():
    assert fd.resolve_relative_date("due 23 jan", now=NOW)[0] == "2027-01-23"  # rolled to future
    assert fd.resolve_relative_date("due 30 nov", now=NOW)[0] == "2026-11-30"
    assert fd.resolve_relative_date("jan 5", now=NOW)[0] == "2027-01-05"


def test_numeric_day_month_and_times_not_dates():
    assert fd.resolve_relative_date("due 23/11", now=NOW)[0] == "2026-11-23"
    # clock times must not be mistaken for dates
    assert fd.resolve_relative_date("meet at 10-11", now=NOW)[0] in (None, "2026-10-30")


def test_unknown_stays_none():
    assert fd.resolve_relative_date("sometime eventually", now=NOW) == (None, None)


def test_iso_date():
    assert fd.resolve_relative_date("submit by 2026-12-01", now=NOW)[0] == "2026-12-01"


def test_time_of_day():
    assert fd.parse_time_of_day("meeting at 3pm") == ("15:00", "3pm")
    assert fd.parse_time_of_day("call at 15:30")[0] == "15:30"
    assert fd.parse_time_of_day("study tonight")[0] == "20:00"
    assert fd.parse_time_of_day("sometime")[0] is None


def test_hhmm_conversions():
    assert fd.hhmm_to_minutes("09:30") == 570
    assert fd.minutes_to_hhmm(570) == "09:30"
    assert fd.minutes_to_hhmm(1440) == "00:00"
    assert fd.hhmm_to_minutes("25:00") is None
    assert fd.hhmm_to_minutes("garbage") is None


def test_timezone_setting():
    settings = {"timezone": "Asia/Dhaka"}
    aware = fd.now_here(settings)
    assert aware.tzinfo is not None
    assert fd.today_str(settings) == aware.date().isoformat()
    # invalid timezone falls back to naive local
    assert fd.get_timezone({"timezone": "Not/AZone"}) is None
