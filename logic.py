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

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Migrations & Validation
    data.setdefault("level", 1)
    data.setdefault("xp", 0)
    data.setdefault("tasks", [])
    data.setdefault("history", {})
    data.setdefault("focus_sessions", {})
    data.setdefault("class_sessions", {})

    data.setdefault("habits", [])
    data.setdefault("timer_state", {"seconds": 0, "mode": "focus", "class_id": None})
    
    # New settings and store defaults
    if "store" not in data:
        data["store"] = {"unlocked": ["theme_default", "sound_rain"], "xp_spent": 0}
    
    if "settings" not in data:
        data["settings"] = {
            "theme": "System",
            "daily_goal_hours": 4,
            "timer_style": "stopwatch", # stopwatch (count up) or countdown
            "pomodoro": {"work": 25, "short_break": 5, "long_break": 15}
        }
    # The original setdefault for settings is now replaced by the more detailed 'if not in data' block above.
    # data.setdefault("settings", {"theme": "System", "daily_goal_hours": 4}) 
    
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
    """Save data to JSON file atomically."""
    temp_file = DATA_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    os.replace(temp_file, DATA_FILE)

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
    save_data(data)

def update_timer_state(data, seconds, mode="focus", class_id=None):
    """Save the current timer state for persistence."""
    data["timer_state"] = {
        "seconds": seconds,
        "mode": mode,
        "class_id": class_id,
        "updated_at": str(datetime.now())
    }
    save_data(data)

def clear_timer_state(data):
    """Reset timer persistence."""
    data["timer_state"] = {"seconds": 0, "mode": "focus", "class_id": None}
    save_data(data)
# ==================== TASK FACTORY ====================
def create_task(*, title, task_type="task", subject=None, schedule=None, date=None, days=None, notes="", duration=None):
    """
    Create a new task.
    
    Args:
        title: Task title
        task_type: "task" (personal) or "class"
        subject: Optional subject name
        schedule: Dict with 'days', 'start', 'end' for classes
        date: Due date (YYYY-MM-DD) for tasks
        days: List of days ['mon', 'wed'] for classes (alternative to schedule)
        notes: User notes/link storage
        duration: Optional time limit in minutes
    
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
        "notes": notes,
        "duration": duration,
        "status": "pending",
        "subtasks": [],
        "documents": [],
        "review_needed": False,
        "created_at": today(),
        "updated_at": today()
    }

# ==================== TASK CRUD ====================
def add_task_logic(data, title, category="task", deadline=None, days=None, schedule=None, notes="", duration=None, subject=None):
    """
    Add a new task.
    
    Args:
        data: The data dict
        title: Task title
        category: "task" or "class"
        deadline: Due date for tasks
        days: List of days for classes
        schedule: Schedule dict for classes
        notes: User notes
        duration: Time limit in minutes
        subject: Optional subject name
    """
    if not title or not title.strip():
        return None

    new_task = create_task(
        title=title.strip(),
        task_type=category,
        schedule=schedule,
        date=deadline,
        days=days,
        notes=notes,
        duration=duration,
        subject=subject
    )
    
    data.setdefault("tasks", []).append(new_task)
    save_data(data)
    return new_task

def delete_task_logic(data, task_id):
    """Delete a task by ID."""
    data["tasks"] = [t for t in data["tasks"] if t["id"] != task_id]
    save_data(data)

def update_task_logic(data, task_id, **fields):
    """Update specific fields of a task."""
    for task in data.get("tasks", []):
        if task["id"] == task_id:
            for k, v in fields.items():
                task[k] = v
            task["updated_at"] = today()
            break
    save_data(data)
    
def complete_task_logic(data, task_id):
    """Mark a task as done and award XP."""
    task = next((t for t in data.get("tasks", []) if t["id"] == task_id), None)
    if not task: return
    
    if task.get("type") == "class":
        mark_class_done(data, task_id)
    else:
        task["status"] = "done"
        add_xp(data, 10)
    
    save_data(data)

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
        days=days,
        subject=subject
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
    just_started = []

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
                just_started.append(task["id"]) # Capture start event

        # Ended - class time has passed
        elif now > end:
            if task.get("status") not in ("done", "missed", "ended"):
                task["status"] = "ended"
                needs_attendance_prompt.append(task["id"])
                changed = True

    if changed:
        save_data(data)

    return needs_attendance_prompt, just_started

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

def process_daily_automation(data):
    """
    Run daily automated maintenance:
    1. Reset recurring classes for today (if they were done previous weeks).
    2. Archive completed tasks from > 1 day ago.
    """
    import datetime
    today_str = str(datetime.date.today())
    today_day = datetime.date.today().strftime("%a").lower()[:3]
    
    tasks = data.get("tasks", [])
    active_tasks = []
    
    for task in tasks:
        # 1. Recurring Class Logic
        if task.get("type") == "class":
            schedule = task.get("schedule", {})
            if today_day in schedule.get("days", []):
                # Check if it was updated TODAY. If not, reset it to 'todo'
                last_update = task.get("updated_at", "")
                if last_update != today_str:
                    task["status"] = "todo"
                    task["updated_at"] = today_str # Mark as fresh for today
            
            # Classes always stay in the active list (recurring)
            active_tasks.append(task)
            
        # 2. Regular Task Logic (Auto-Archive)
        else:
            status = task.get("status", "todo")
            updated = task.get("updated_at", "")
            
            # If done and from yesterday (or older), archive it is handled by cleanup_finished_classes normally.
            # But let's enforce a strict "Keep Today's View Clean" policy.
            # If done and NOT today -> Move to History (implicit via not adding to active_tasks?)
            # Wait, `active_tasks` replaces `data["tasks"]`.
            
            should_archive = False
            if status == "done" and updated != today_str:
                should_archive = True
            
            if should_archive:
                # Add to history if not exists? 
                # Actually `complete_task_logic` adds XP. The `history` dict logs completed counts daily.
                # We just remove it from active view.
                pass 
            else:
                active_tasks.append(task)
                
    data["tasks"] = active_tasks
    save_data(data)

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
    
    return {
        "total_seconds": total,
        "class_seconds": class_time,
        "sessions": today_data.get("sessions", 0),
        "formatted_total": format_seconds_to_hms(total),
        "formatted_class": format_seconds_to_hms(class_time)
    }

# ==================== CLASS FOCUS TIME ====================
def log_class_session(data, seconds_spent, class_id):
    """
    Log a class focus session and award XP.
    
    Args:
        data: The data dict
        seconds_spent: Time spent in class (seconds)
        class_id: The class task ID
    """
    if seconds_spent < 60:
        return  # Ignore very short sessions

    date_key = today()
    
    data.setdefault("class_sessions", {})
    data["class_sessions"].setdefault(date_key, {})
    data["class_sessions"][date_key].setdefault(class_id, {
        "total_seconds": 0,
        "sessions": 0
    })
    
    data["class_sessions"][date_key][class_id]["total_seconds"] += int(seconds_spent)
    data["class_sessions"][date_key][class_id]["sessions"] += 1

    # XP: 1 XP per 2 minutes for class time (more generous than regular focus)
    xp_gained = int(seconds_spent // 120)
    if xp_gained > 0:
        add_xp(data, xp_gained)
        update_history(data, xp_gained)

    save_data(data)

def get_class_session_stats(data, class_id):
    """Get total time spent on a specific class."""
    date_key = today()
    sessions = data.get("class_sessions", {})
    day_sessions = sessions.get(date_key, {})
    class_data = day_sessions.get(class_id, {})
    return class_data.get("total_seconds", 0)

def format_seconds_to_hms(seconds):
    """Format seconds to HH:MM:SS or MM:SS format."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours:02}:{minutes:02}:{secs:02}"
    else:
        return f"{minutes:02}:{secs:02}"

# ==================== STATS ====================
def get_stats(data):
    """Get user stats."""
    return data.get("level", 1), data.get("xp", 0)

def get_history(data):
    """Get history data."""
    return data.get("history", {})

# ==================== VALIDATION ====================
def validate_class_input(title, subject, days, start, end):
    """Validate class input before adding."""
    if not title or not title.strip():
        return False, "Title required"

    if not subject or not subject.strip():
        return False, "Subject required"

    if not days:
        return False, "At least one day required"

    try:
        datetime.strptime(start, "%H:%M")
        datetime.strptime(end, "%H:%M")
    except ValueError:
        return False, "Time must be HH:MM"

    if start >= end:
        return False, "Start time must be before end time"

    return True, None

# The following lines were part of the instruction but appear to be misplaced or incomplete.
# They are commented out to maintain syntactical correctness.
#    return False, "End time required"
#    return True, ""

# ==================== VAULT & SUBJECTS ====================
def add_subject(data, name):
    """Add a new subject to the vault."""
    subjects = data.setdefault("subjects", {})
    if name not in subjects:
        subjects[name] = {"notes": "", "documents": []}
        save_data(data)
        return True
    return False

def delete_subject(data, name):
    """Delete a subject and its associated metadata."""
    if name in data.get("subjects", {}):
        del data["subjects"][name]
        save_data(data)

def add_vault_file(data, subject, file_path):
    """Add a file to a subject in the vault."""
    subjects = data.setdefault("subjects", {})
    if subject not in subjects:
        add_subject(data, subject)
    
    if file_path not in subjects[subject]["documents"]:
        subjects[subject]["documents"].append(file_path)
        save_data(data)

def delete_vault_file(data, subject, file_path):
    """Remove a file reference from a subject."""
    if subject in data.get("subjects", {}) :
        if file_path in data["subjects"][subject]["documents"]:
            data["subjects"][subject]["documents"].remove(file_path)
            save_data(data)

def rename_subject(data, old_name, new_name):
    """Rename a subject."""
    if old_name in data.get("subjects", {}) and new_name not in data["subjects"]:
        data["subjects"][new_name] = data["subjects"].pop(old_name)
        # Update tasks that use this subject
        for task in data.get("tasks", []):
            if task.get("subject") == old_name:
                task["subject"] = new_name
        save_data(data)

# ==================== HABITS ====================
def add_habit(data, title):
    """Add a new habit."""
    if not title: return
    new_habit = {
        "id": str(uuid.uuid4()),
        "title": title,
        "history": [], # List of YYYY-MM-DD strings
        "created_at": today()
    }
    data.setdefault("habits", []).append(new_habit)
    save_data(data)
    return new_habit

def delete_habit(data, habit_id):
    """Delete a habit."""
    data["habits"] = [h for h in data.get("habits", []) if h["id"] != habit_id]
    save_data(data)

def toggle_habit_today(data, habit_id):
    """Toggle habit completion for today."""
    t = today()
    habit = next((h for h in data.get("habits", []) if h["id"] == habit_id), None)
    if not habit: return

    if t in habit["history"]:
        habit["history"].remove(t)
        # Remove XP if untoggled? Simplify: No XP penalty/refund for now to avoid abuse/complexity
    else:
        habit["history"].append(t)
        add_xp(data, 5) # Small XP reward for habit

    save_data(data)

def get_habit_streak(habit):
    """Calculate current streak."""
    history = set(habit.get("history", []))
    if not history: return 0
    
    current_date = date.today()
    streak = 0
    
    # Check if done today
    if current_date.isoformat() in history:
        streak += 1
        current_date -= timedelta(days=1)
    
    # Check backwards
    while True:
        # If we didn't do it today, initially we check yesterday.
        # If we DID do it today, current_date is already yesterday.
        if current_date.isoformat() in history:
            streak += 1
            current_date -= timedelta(days=1)
        else:
            # If today is NOT done, check if yesterday was done to start the count.
            # This logic ensures that if today is not done, but yesterday was, the streak from yesterday is counted.
            # If the streak is 0 (meaning today wasn't done and we haven't found any previous days yet)
            # and the current_date (which would be yesterday if today was done, or today if not) is not in history,
            # we check the day before that.
            if streak == 0 and current_date.isoformat() not in history:
                 yesterday = current_date - timedelta(days=1)
                 if yesterday.isoformat() in history:
                     current_date = yesterday
                     continue # Continue checking backwards from yesterday
                 else:
                     break # No streak found ending today or yesterday
            else:
                break # Streak ended or we've gone past the start of the streak
                
    return streak

# ==================== ANALYTICS ====================
def get_analytics_data(data):
    """Get aggregated data for reports."""
    stats = {
        "subject_time": {},
        "daily_focus": {},
    }
    
    # Subject Breakdown
    # Access class_sessions: {date: {class_id: {total_seconds: ...}}}
    # Need to map class_id to Subject Name
    
    # Build class_id -> subject map
    class_map = {}
    for task in data.get("tasks", []):
        if task["type"] == "class":
            class_map[task["id"]] = task.get("subject", "Unknown")
            
    class_sessions = data.get("class_sessions", {})
    for day, classes in class_sessions.items():
        for cid, info in classes.items():
            subj = class_map.get(cid, "Unknown")
            stats["subject_time"][subj] = stats["subject_time"].get(subj, 0) + info.get("total_seconds", 0)
            
    # Daily Focus (Total + Class)
    # focus_sessions: {date: {total_seconds: ..., class_seconds: ...}}
    focus_sessions = data.get("focus_sessions", {})
    # Sort last 7 days
    dates = sorted(list(set(list(focus_sessions.keys()) + list(class_sessions.keys()))))[-7:]
    
    for d in dates:
        # Total focus log
        f_info = focus_sessions.get(d, {})
        f_seconds = f_info.get("total_seconds", 0)
        
        # Add class seconds if not included (logic.py log_focus_session with type='class' DOES add to focus_sessions class_seconds)
        # But log_class_session also logs to class_sessions.
        # Let's rely on focus_sessions for daily totals as it aggregates both types in 'focus_sessions' dict?
        # Check log_focus_session: 
        #   if session_type == "class": data["focus_sessions"][date]["class_seconds"] += ...
        #   else: total_seconds += ...
        
        total = f_seconds + f_info.get("class_seconds", 0)
        stats["daily_focus"][d] = total / 60 # Minutes
        
    return stats

# ==================== ANALYTICS & HEATMAP ====================
def get_heatmap_data(data):
    """
    Get daily activity intensity for the last 365 days.
    Returns: { "YYYY-MM-DD": count (0-4 intensity) }
    """
    history = data.get("history", {})
    heatmap = {}
    
    # Calculate max activity to normalize intensity
    # Metric: tasks_completed * 10 + xp_gained / 10 + focus_minutes / 5
    # Just simpler: tasks + focus_hours?
    
    for date_str, entry in history.items():
        tasks = entry.get("completed", 0)
        # Handle different focus tracking keys
        focus_sec = entry.get("focus_minutes", 0) * 60 # Convert minutes to seconds
        
        # Approximate "intensity score"
        score = tasks * 2 + (focus_sec / 900) # 1 task = 2 pts, 15 min focus = 1 pt
        
        # Map score to 0-4
        if score == 0: intensity = 0
        elif score < 5: intensity = 1
        elif score < 10: intensity = 2
        elif score < 20: intensity = 3
        else: intensity = 4
        
        heatmap[date_str] = intensity
        
    return heatmap

# ==================== POMODORO SETTINGS ====================
def get_pomodoro_settings(data):
    return data.get("settings", {}).get("pomodoro", {"work": 25, "short_break": 5, "long_break": 15})

def update_pomodoro_settings(data, work, short, long, style="stopwatch"):
    """Update Pomodoro durations and style."""
    settings = data.setdefault("settings", {})
    settings["pomodoro"] = {
        "work": int(work),
        "short_break": int(short),
        "long_break": int(long)
    }
    settings["timer_style"] = style
    save_data(data)

# ==================== XP STORE LOGIC ====================
STORE_ITEMS = [
    {"id": "theme_cyber", "name": "Cyberpunk Theme", "type": "theme", "cost": 500, "desc": "Neon vibes for night coding."},
    {"id": "theme_forest", "name": "Forest Theme", "type": "theme", "cost": 300, "desc": "Calm green aesthetics."},
    {"id": "zen_mode", "name": "Zen Mode", "type": "feature", "cost": 1000, "desc": "Minimalist Always-on-Top Timer."},
]

def get_store_items(data):
    """Get all items with unlock status."""
    unlocked = data.get("store", {}).get("unlocked", [])
    items = []
    for item in STORE_ITEMS:
        item_copy = item.copy()
        item_copy["unlocked"] = item["id"] in unlocked
        items.append(item_copy)
    return items

def purchase_item(data, item_id):
    """Attempt to purchase item. Returns (success, message)."""
    item = next((i for i in STORE_ITEMS if i["id"] == item_id), None)
    if not item: return False, "Item not found."
    
    store = data.setdefault("store", {"unlocked": [], "xp_spent": 0})
    if item_id in store["unlocked"]:
        return False, "Already owned."
    
    if data["xp"] >= item["cost"]:
        data["xp"] -= item["cost"]
        store["unlocked"].append(item_id)
        store["xp_spent"] += item["cost"]
        save_data(data)
        return True, f"Successfully purchased {item['name']}!"
    else:
        return False, f"Not enough XP! Need {item['cost'] - data['xp']} more."

def is_unlocked(data, item_id):
    return item_id in data.get("store", {}).get("unlocked", [])

