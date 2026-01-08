# schedule.py
from datetime import datetime
SCHEDULE = {
    "monday": [
        {"title": "Math", "start": "09:00", "end": "10:30"},
        {"title": "Physics", "start": "11:00", "end": "12:30"},
    ],
    "tuesday": [
        {"title": "Programming", "start": "10:00", "end": "11:30"},
    ],
}

def to_minutes(t):
    h, m = map(int, t.split(":"))
    return h * 60 + m


def get_current_class(schedule):
    now = datetime.now()
    day = now.strftime("%A").lower()
    now_min = now.hour * 60 + now.minute

    for cls in schedule.get(day, []):
        start = to_minutes(cls["start"])
        end = to_minutes(cls["end"])

        if start <= now_min <= end:
            return cls

    return None