import json
import os
import uuid
from utils import today, xp_per_task
from datetime import date

# ---------------- PATH SAFE ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")


# ---------------- LOAD / SAVE ----------------
def load_data():
    # If file does not exist, create a safe default
    if not os.path.exists(DATA_FILE):
        data = {
            "level": 1,
            "xp": 0,
            "streak": 0,
            "last_date": "",
            "tasks": [],
            "history": {},
            "focus_sessions": {}
        }
        save_data(data)
        return data

    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    # ---- migrations / guards ----
    data["xp"] = int(data.get("xp", 0))
    data.setdefault("focus_sessions", {})
    data.setdefault("history", {})
    data.setdefault("tasks", [])

    # ensure every task has an ID
    changed = False
    for task in data["tasks"]:
        if "id" not in task:
            task["id"] = str(uuid.uuid4())
            changed = True

    if changed:
        save_data(data)
    data["level"] = max(1, int(data.get("level", 1)))


    return data



def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


# ---------------- DAILY RESET ----------------


# ---------------- HISTORY ----------------
def update_history(data, xp_gained):
    data.setdefault("history", {})
    date_key = today()

    if date_key not in data["history"]:
        data["history"][date_key] = {
            "completed": 0,
            "total": 0,
            "xp_gained": 0
        }

    data["history"][date_key]["completed"] = sum(
        1 for t in data["tasks"] if t.get("done")
    )
    data["history"][date_key]["total"] = len(data["tasks"])

    data["history"][date_key]["xp_gained"] = int(
        data["history"][date_key].get("xp_gained", 0)
    ) + int(xp_gained)


# ---------------- TASK LOGIC ----------------
def recalc_task_done(task):
    if task.get("subtasks"):
        task["done"] = all(st["done"] for st in task["subtasks"])
    else:
        task["done"] = False

def toggle_subtask(data, task_i, sub_i, is_done):
    if task_i >= len(data["tasks"]):
        return

    task = data["tasks"][task_i]
    if sub_i >= len(task.get("subtasks", [])):
        return

    sub = task["subtasks"][sub_i]

    if sub["done"] == is_done:
        return

    sub["done"] = is_done

    # XP only first time completion
    if is_done and not sub.get("xp_given", False):
        xp_gain = xp_per_task(len(data["tasks"])) / max(1, len(task["subtasks"]))
        data["xp"] += int(xp_gain)
        sub["xp_given"] = True

    recalc_task_done(task)

    while data["xp"] >= 100:
        data["xp"] -= 100
        data["level"] += 1

    data["xp"] = int(data["xp"])
    update_history(data, 0)
    save_data(data)



# ---------------- TASK CRUD ----------------


def add_task(data, title):
    if title.strip():
        data.setdefault("tasks", []).append({
            "id": str(uuid.uuid4()),
            "title": title,
            "done": False,
            "subtasks": []
        })
        date_key = today()
        if date_key in data.get("history", {}):
            data["history"][date_key]["total"] = len(data["tasks"])

        save_data(data)



def edit_task(data, index, new_title):
    if new_title.strip():
        data["tasks"][index]["title"] = new_title
        save_data(data)


def delete_task(data, index):
    data["tasks"].pop(index)

    date_key = today()
    if date_key in data.get("history", {}):
        data["history"][date_key]["total"] = len(data["tasks"])

    save_data(data)



# ---------------- SUBTASK CRUD ----------------
def add_subtask(data, task_i, title):
    if title.strip():
        data["tasks"][task_i]["subtasks"].append({
            "title": title,
            "done": False,
            "xp_given": False
        })
        save_data(data)


def edit_subtask(data, task_i, sub_i, new_title):
    if new_title.strip():
        data["tasks"][task_i]["subtasks"][sub_i]["title"] = new_title
        save_data(data)


def delete_subtask(data, task_i, sub_i):
    data["tasks"][task_i]["subtasks"].pop(sub_i)
    save_data(data)


# ---------------- STATS / HISTORY ACCESS ----------------
def get_stats(data):
    return data.get("level", 1), data.get("xp", 0)


def get_history(data):
    return data.get("history", {})

def reset_tasks_for_new_day_if_needed(data):
    data.setdefault("history", {})
    data["history"].setdefault(today(), {
        "completed": 0,
        "total": len(data["tasks"]),
        "xp_gained": 0
    })

    today_str = date.today().isoformat()

    if data.get("last_date") == today_str:
        return

    for task in data.get("tasks", []):
        task.pop("_counted_today", None)
        task["done"] = False
        for sub in task.get("subtasks", []):
            sub["done"] = False
            sub["xp_given"] = False

    data["last_date"] = today_str
    save_data(data)


def log_focus_session(data, seconds_spent):
    if seconds_spent < 60:
        return  # ignore very short sessions

    date_key = today()

    data.setdefault("focus_sessions", {})
    data["focus_sessions"].setdefault(date_key, {
        "total_seconds": 0,
        "sessions": 0
    })

    data["focus_sessions"][date_key]["total_seconds"] += int(seconds_spent)
    data["focus_sessions"][date_key]["sessions"] += 1

    # XP: 1 XP per 5 minutes
    xp_gained = int(seconds_spent // 300)
    data["xp"] += xp_gained

    # ✅ ADD THIS (CRITICAL)
    update_history(data, xp_gained)

    # Level up
    while data["xp"] >= 100:
        data["xp"] -= 100
        data["level"] += 1

    data["xp"] = int(data["xp"])
    save_data(data)
