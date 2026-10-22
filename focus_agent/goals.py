# ==================== GOALS.PY ====================
# Long-term goals + editable milestones + progress tracking.
# Persisted under data["goals"] (schema v3). All CRUD is validated; the LLM
# can propose goal structures but only through the validated tool layer.

import uuid
from datetime import date

from logic import save_data
from focus_agent import dates as fdates
from focus_agent.schemas import clean_str, valid_date

GOAL_STATUSES = ("active", "paused", "done")


def _new_goal(title, description=None, target_date=None, subject=None):
    return {
        "id": str(uuid.uuid4()),
        "title": clean_str(title, 200),
        "description": clean_str(description, 2000),
        "subject": clean_str(subject, 120),
        "status": "active",
        "target_date": valid_date(target_date),
        "created_at": fdates.today_str(),
        "updated_at": fdates.today_str(),
        "milestones": [],
    }


def _new_milestone(title, target_date=None, estimated_minutes=None):
    return {
        "id": str(uuid.uuid4()),
        "title": clean_str(title, 200),
        "done": False,
        "target_date": valid_date(target_date),
        "estimated_minutes": (estimated_minutes if isinstance(estimated_minutes, (int, float))
                              and 0 < estimated_minutes <= 10_000 else None),
        "created_at": fdates.today_str(),
    }


def get_goal(data, goal_id):
    return next((g for g in data.get("goals", []) if g.get("id") == goal_id), None)


def find_goal_by_title(data, title_fragment):
    frag = (title_fragment or "").lower().strip()
    if not frag:
        return None
    for g in data.get("goals", []):
        if frag in (g.get("title") or "").lower():
            return g
    return None


def add_goal(data, title, description=None, target_date=None, subject=None,
             milestones=None):
    """Create a goal. Returns (goal_dict, error_or_None)."""
    title = clean_str(title, 200)
    if not title:
        return None, "Goal needs a title"
    if target_date and not valid_date(target_date):
        return None, "target_date must be YYYY-MM-DD"
    goal = _new_goal(title, description, target_date, subject)
    for ms in (milestones or [])[:30]:
        if isinstance(ms, dict) and clean_str(ms.get("title"), 200):
            goal["milestones"].append(_new_milestone(
                ms["title"], ms.get("target_date"), ms.get("estimated_minutes")))
    data.setdefault("goals", []).append(goal)
    save_data(data)
    return goal, None


def update_goal(data, goal_id, **fields):
    """Edit editable goal fields. Returns (ok, error)."""
    goal = get_goal(data, goal_id)
    if not goal:
        return False, "Goal not found"
    allowed = {"title", "description", "target_date", "subject", "status"}
    for k, v in fields.items():
        if k not in allowed or v is None:
            continue
        if k == "status" and v not in GOAL_STATUSES:
            return False, f"status must be one of {GOAL_STATUSES}"
        if k == "target_date":
            v = valid_date(v)
            if not v:
                return False, "target_date must be YYYY-MM-DD"
        if k in ("title", "description", "subject"):
            v = clean_str(v, 2000)
            if not v:
                continue
        goal[k] = v
    goal["updated_at"] = fdates.today_str()
    save_data(data)
    return True, None


def delete_goal(data, goal_id):
    """Remove a goal. Tasks linked to it are unlinked, NOT deleted."""
    before = len(data.get("goals", []))
    data["goals"] = [g for g in data.get("goals", []) if g.get("id") != goal_id]
    if len(data["goals"]) == before:
        return False
    for t in data.get("tasks", []):
        if t.get("goal_id") == goal_id:
            t["goal_id"] = None
    save_data(data)
    return True


def add_milestone(data, goal_id, title, target_date=None, estimated_minutes=None):
    goal = get_goal(data, goal_id)
    if not goal:
        return None, "Goal not found"
    title = clean_str(title, 200)
    if not title:
        return None, "Milestone needs a title"
    ms = _new_milestone(title, target_date, estimated_minutes)
    goal["milestones"].append(ms)
    goal["updated_at"] = fdates.today_str()
    save_data(data)
    return ms, None


def update_milestone(data, goal_id, milestone_id, done=None, title=None,
                     target_date=None):
    goal = get_goal(data, goal_id)
    if not goal:
        return False, "Goal not found"
    ms = next((m for m in goal["milestones"] if m.get("id") == milestone_id), None)
    if not ms:
        return False, "Milestone not found"
    if done is not None:
        ms["done"] = bool(done)
    if title:
        ms["title"] = clean_str(title, 200) or ms["title"]
    if target_date is not None:
        ms["target_date"] = valid_date(target_date)
    goal["updated_at"] = fdates.today_str()
    save_data(data)
    return True, None


def delete_milestone(data, goal_id, milestone_id):
    goal = get_goal(data, goal_id)
    if not goal:
        return False
    before = len(goal["milestones"])
    goal["milestones"] = [m for m in goal["milestones"] if m.get("id") != milestone_id]
    if len(goal["milestones"]) == before:
        return False
    save_data(data)
    return True


def goal_progress(data, goal):
    """Progress metrics for one goal: milestone completion + task effort done.

    Returns {milestones_done, milestones_total, percent, tasks_done,
             tasks_total, overdue_milestones, next_milestone, blocked_by}.
    """
    today_iso = fdates.today_str()
    mss = goal.get("milestones", [])
    ms_done = sum(1 for m in mss if m.get("done"))
    tasks = [t for t in data.get("tasks", []) if t.get("goal_id") == goal.get("id")]
    tasks_done = sum(1 for t in tasks if t.get("status") == "done")

    overdue = [m for m in mss
               if not m.get("done") and m.get("target_date") and m["target_date"] < today_iso]
    upcoming = [m for m in mss if not m.get("done")]
    upcoming.sort(key=lambda m: m.get("target_date") or "9999-12-31")
    next_ms = upcoming[0] if upcoming else None

    ms_pct = (ms_done / len(mss) * 100) if mss else None
    task_pct = (tasks_done / len(tasks) * 100) if tasks else None
    parts = [p for p in (ms_pct, task_pct) if p is not None]
    percent = round(sum(parts) / len(parts)) if parts else (0 if mss or tasks else None)

    target = goal.get("target_date")
    goal_overdue = bool(target and target < today_iso and (percent is None or percent < 100))

    return {
        "milestones_done": ms_done,
        "milestones_total": len(mss),
        "percent": percent,
        "tasks_done": tasks_done,
        "tasks_total": len(tasks),
        "overdue": goal_overdue,
        "overdue_milestones": [{"id": m["id"], "title": m["title"],
                                "target_date": m["target_date"]} for m in overdue],
        "next_milestone": ({"id": next_ms["id"], "title": next_ms["title"],
                            "target_date": next_ms.get("target_date")}
                           if next_ms else None),
    }


def generate_roadmap_draft(goal_title, weeks=6, hours_per_week=8, start_date=None,
                           assumptions=None):
    """Build an EDITABLE roadmap draft from user inputs - clearly labeled.

    This is a planning aid based on the user's stated time budget; every
    assumption is returned for display, never written as fact.
    """
    try:
        weeks = max(2, min(int(weeks), 26))
        hours_per_week = max(1, min(int(hours_per_week), 40))
    except (TypeError, ValueError):
        return None, "weeks and hours_per_week must be numbers"
    start = start_date or fdates.today_str()
    try:
        d0 = date.fromisoformat(start)
    except ValueError:
        return None, "start_date must be YYYY-MM-DD"

    from datetime import timedelta
    total_hours = weeks * hours_per_week
    phases = [
        ("Foundations & setup", 0.25),
        ("Guided practice & small exercises", 0.30),
        ("Build a small project", 0.25),
        ("Review, gaps & polish", 0.20),
    ]
    milestones = []
    for i, (phase, share) in enumerate(phases):
        end = d0 + timedelta(weeks=int(round((i + 1) * weeks / len(phases))))
        milestones.append({
            "title": f"{phase} (~{int(round(total_hours * share))}h)",
            "target_date": end.isoformat(),
            "estimated_minutes": int(round(total_hours * share * 60)),
        })
    return {
        "goal_title": goal_title,
        "milestones": milestones,
        "assumptions": assumptions or [
            f"{weeks}-week horizon at about {hours_per_week}h/week "
            f"(~{total_hours}h total) starting {start}",
            "Phases are generic until you add specifics - edit any milestone",
        ],
    }, None
