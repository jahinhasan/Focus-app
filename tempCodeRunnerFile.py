# ==================== LOGIC.PY ====================
# Core business logic for Focus Dashboard
# Handles tasks, classes, XP, history, and routine management

import json
import os
import uuid
import math
from datetime import date, datetime, timedelta
from utils import today

# ==================== PATH SAFE ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")

# ==================== LOAD / SAVE ====================
def load_data():
    """Load data from JSON file or create default structure."""
    if not os.path.exists(DATA_FILE):
        data = {
            "level": 1,
            "xp": 0,
            "tasks": [],
            "history": {},
            "focus_sessions": {}
        }
        save_data(data)
        return data

    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    # Migrations & Validation
    data.setdefault("level", 1)
    data.setdefault("xp", 0)
    data.setdefault("tasks", [])
    data.setdefault("history", {})
    data.setdefault("focus_sessions", {})
    
    for task in data["tasks"]:
        if task.get("type") == "personal":
           task["type"] = "task"
        if "id" not in task:
            task["id"] = str(uuid.uuid4())
        task.setdefault("subtasks", [])
        task.setdefault("status", "pending")
        task.setdefault("type", "task")  # Default to task type

    return data

def save_data(data):
    """Save data to JSON file."""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ==================== XP SYSTEM ====================
def add_xp(data, amount):
    """Adds XP, updates level, and returns (new_level, gained_xp, leveled_up)."""
    data["xp"] += amount
    current_level = data["level"]
    
    # Level Formula: Level = floor(sqrt(XP / 100)) + 1
    # XP 0 -> Lvl 1
    # XP 100 -> Lvl 2
    # XP 400 -> Lvl 3
    new_level = math.floor(math.sqrt(data["xp"] / 100)) + 1
    
    leveled_up = False
    if new_level > current_level:
        data["level"] = new_level
        leveled_up = True
        
    update_history(data, amount)
    save_data(data)
    return new_level, amount, leveled_up

def get_level_progress(data):
    """Returns (current_xp, xp_for_next_level, percentage)."""
    xp = data["xp"]
    lvl = data["level"]
    
    # XP required for current level start
    current_level_xp = 100 * ((lvl - 1) ** 2)
    # XP required for next level
    next_level_xp = 100 * (lvl ** 2)
    
    progress = xp - current_level_xp
    required = next_level_xp - current_level_xp
    
    if required <= 0:
        return 0, 100, 100  # Maxed/Bug guard
    
    percent = (progress / required) * 100
    return int(progress), int(required), percent

# ==================== HISTORY ====================
def update_history(data, xp_gained=0):
    """Update daily history stats."""
    date_key = today()
    hist = data["history"]
    
    if date_key not in hist:
        hist[date_key] = {
            "completed": 0, 
            "total": 0, 
            "xp_gained": 0, 
            "focus_minutes": 0
        }
        
    # Recalculate daily stats
    completed = sum(1 for t in data["tasks"] if t.get("status") == "done")
    hist[date_key]["completed"] = completed
    hist[date_key]["total"] = len(data["tasks"])
    hist[date_key]["xp_gained"] += xp_gained

def log_focus_time(data, minutes):
    """Log focus session time."""
    date_key = today()
    update_history(data, 0)  # Ensure entry exists
    data["history"][date_key]["focus_minutes"] = data["history"][date_key].get("focus_minutes", 0) + minutes
    save_data(data)

# ==================== TASK FACTORY ====================
def create_task(*, title, task_type="task", subject=None, schedule=None, date=None, days=None):
    """
    Create a new task.
    
    Args:
        title: Task title
        task_type: "task" (personal) or "class"
        subject: Optional subject name
        schedule: Dict with 'days', 'start', 'end' for classes
        date: Due date (YYYY-MM-DD) for tasks
        days: List of days ['mon', 'wed'] for classes (alternative to schedule)
    
    Returns:
        Task dict
    """
    return {
        "id": str(uuid.uuid4()),
        "type": task_type,
        "title": title,
        "subject": subject,
        "schedule": schedule,
        "date": date,
        "days": days,  # For classes: list of days
        "status": "pending",
        "subtasks": [],
        "documents": [],
        "created_at": today(),
        "updated_at": today()
    }

# ==================== TASK CRUD ====================
def add_task_logic(data, title, category="task", deadline=None, days=None, schedule=None):
    """
    Add a new task.
    
    Args:
        data: The data dict
        title: Task title
        category: "task" or "class"
        deadline: Due date for tasks
        days: List of days for classes
        schedule: Schedule dict for classes
    """
    if not title or not title.strip():
        return None

    new_task = create_task(
        title=title.strip(),
        task_type=category,
        schedule=schedule,
        date=deadline,
        days=days
    )
    
    data.setdefault("tasks", []).append(new_task)
    save_data(data)
    return new_task

def add_subtask(data, task_id, title):
    """Add a subtask to a task."""
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if task:
        task.setdefault("subtasks", []).append({
            "title": title, 
            "done": False
        })
        save_data(data)

def toggle_subtask(data, task_id, sub_index):
    """Toggle a subtask's done status."""
    task = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if task and 0 <= sub_index < len(task["subtasks"]):
        task["subtasks"][sub_index]["done"] = not task["subtasks"][sub_index]["done"]
        save_data(data)

def get_task_by_id(data, task_id):
    """Get a task by ID."""
    for task in data.get("tasks", []):
        if task["id"] == task_id:
            return task
    return None

# ==================== CLASS MANAGEMENT ====================
def add_class_task(data, *, title, subject=None, days=None, start_time=None, end_time=None):
    """Add a class with schedule."""
    schedule = None
    if days and start_time and end_time:
        schedule = {
            "days": days,
            "start": start_time,
            "end": end_time
        }
    
    return add_task_logic(
        data=data,
        title=title,
        category="class",
        schedule=schedule,
        days=days
    )

def get_class_detail(data, task_id):
    """Get detailed class info."""
    for task in data.get("tasks", []):
        if task["id"] == task_id and task["type"] == "class":
            return {
                "title": task["title"],
                "subject": task.get("subject"),
                "schedule": task.get("schedule"),
                "subtasks": task.get("subtasks", []),
                "documents": task.get("documents", []),
                "status": task.get("status")
            }
    return None

def today_weekday():
    """Get current day as 3-letter lowercase (e.g., 'mon')."""
    return datetime.today().strftime("%a").lower()[:3]

def current_time_str():
    """Get current time as HH:MM."""
    return datetime.now().strftime("%H:%M")

def get_active_class(data):
    """Get the currently active class based on time."""
    today_day = today_weekday()
    now = current_time_str()

    for task in data.get("tasks", []):
        if task["type"] != "class":
            continue

        schedule = task.get("schedule")
        if not schedule:
            continue

        if today_day in schedule.get("days", []):
            if schedule["start"] <= now <= schedule["end"]:
                return task

    return None

def sync_class_statuses(data):
    """
    Sync class statuses based on current time.
    Returns list of task IDs that need attendance confirmation.
    """
    today_day = today_weekday()
    now = current_time_str()
    changed = False
    needs_attendance_prompt = []

    for task in data.get("tasks", []):
        if task["type"] != "class":
            continue

        sch = task.get("schedule")
        if not sch:
            continue

        if today_day not in sch.get("days", []):
            continue

        start = sch["start"]
        end = sch["end"]

        # Active - class is in progress
        if start <= now <= end:
            if task.get("status") != "active":
                task["status"] = "active"
                changed = True

        # Ended - class time has passed
        elif now > end:
            if task.get("status") not in ("done", "missed", "ended"):
                task["status"] = "ended"
                needs_attendance_prompt.append(task["id"])
                changed = True

    if changed:
        save_data(data)

    return needs_attendance_prompt

def mark_class_done(data, task_id):
    """Mark a class as attended."""
    for task in data.get("tasks", []):
        if task["id"] == task_id and task["type"] == "class":
            task["status"] = "done"
            task["updated_at"] = today()
            update_history(data, 1)
            save_data(data)
            return True
    return False

def mark_class_missed(data, task_id):
    """Mark a class as missed."""
    for task in data.get("tasks", []):
        if task["id"] == task_id and task["type"] == "class":
            task["status"] = "missed"
            task["updated_at"] = today()
            save_data(data)
            return True
    return False

# ==================== DAILY CLEANUP ====================
def cleanup_finished_classes(data):
    """Remove completed classes from active list."""
    data["tasks"] = [
        t for t in data.get("tasks", [])
        if not (t["type"] == "class" and t.get("status") == "done")
    ]
    save_data(data)

# ==================== ROUTINE MANAGEMENT ====================
def save_routine_from_parser(data, classes):
    """
    Save parsed classes from AI to routine.
    
    Args:
        data: The data dict
        classes: List of dicts with 'title', 'days', 'start', 'end'
    
    Returns:
        Number of classes added
    """
    count = 0
    for cls in classes:
        add_task_logic(
            data=data,
            title=cls.get('title', 'Class'),
            category="class",
            schedule={
                "days": cls.get('days', []),
                "start": cls.get('start', '00:00'),
                "end": cls.get('end', '00:00')
            }
        )
        count += 1
    
    save_data(data)
    return count

def get_today_tasks(data):
    """Get tasks for today view."""
    today_date = today()
    today_day = today_weekday()
    now_time = current_time_str()

    today_tasks = []

    for task in data.get("tasks", []):
        if task["type"] == "task" or task.get("type") == "personal":
            # Personal tasks show if no date or today
            task_date = task.get("date")
            if task_date is None or task_date == today_date:
                today_tasks.append(task)

        elif task["type"] == "class":
            schedule = task.get("schedule")
            if not schedule:
                continue

            if today_day not in schedule.get("days", []):
                continue

            # Skip done/missed classes
            if task.get("status") in ("done", "missed"):
                continue

            # Update active status based on time
            current_status = task.get("status", "pending")
            if current_status not in ("ended",):
                if schedule["start"] <= now_time <= schedule["end"]:
                    task["status"] = "active"

            today_tasks.append(task)

    return today_tasks

def get_weekly_class_tasks(data):
    """Get classes organized by day of week."""
    week = {
        "mon": [], "tue": [], "wed": [], "thu": [],
        "fri": [], "sat": [], "sun": []
    }

    for task in data.get("tasks", []):
        if task["type"] != "class":
            continue

        schedule = task.get("schedule")
        if not schedule:
            continue

        for day in schedule.get("days", []):
            if day in week:
                week[day].append(task)

    return week

# ==================== FOCUS SESSION ====================
def log_focus_session(data, seconds_spent, session_type="focus"):
    """
    Log a focus session and award XP.
    
    Args:
        data: The data dict
        seconds_spent: Time spent (seconds)
        session_type: "focus" or "class"
    """
    if seconds_spent < 60:
        return  # Ignore very short sessions

    date_key = today()

    data.setdefault("focus_sessions", {})
    data["focus_sessions"].setdefault(date_key, {
        "total_seconds": 0,
        "sessions": 0,
        "class_seconds": 0  # Track class time separately
    })

    if session_type == "class":
        data["focus_sessions"][date_key]["class_seconds"] += int(seconds_spent)
    else:
        data["focus_sessions"][date_key]["total_seconds"] += int(seconds_spent)
    
    data["focus_sessions"][date_key]["sessions"] += 1

    # XP: 1 XP per 5 minutes for focus, 1 XP per 2 minutes for class
    if session_type == "class":
        xp_gained = int(seconds_spent // 120)
    else:
        xp_gained = int(seconds_spent // 300)
    
    if xp_gained > 0:
        add_xp(data, xp_gained)
        update_history(data, xp_gained)

    save_data(data)

def get_today_focus_stats(data):
    """Get today's focus statistics.
    
    Returns:
        dict with total_seconds, class_seconds, sessions, and formatted strings
    """
    date_key = today()
    sessions = data.get("focus_sessions", {})
    today_data = sessions.get(date_key, {
        "total_seconds": 0,
        "sessions": 0,
        "class_seconds": 0
    })
    
    total = today_data.get("total_seconds", 0)
    class_time = today_data.get("class_seconds", 0)
