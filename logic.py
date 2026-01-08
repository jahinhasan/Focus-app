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
            "history": {}
        }
        save_data(data)
        return data

    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    # 🔥 MIGRATION: ensure every task has an ID
    import uuid
    changed = False

    for task in data.get("tasks", []):
        if "id" not in task:
            task["id"] = str(uuid.uuid4())
            changed = True

    if changed:
        save_data(data)

    return data


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


# ---------------- DAILY RESET ----------------


# ---------------- HISTORY ----------------
def update_history(data, xp_gained):
    if "history" not in data:
        data["history"] = {}

    date_key = today()

    if date_key not in data["history"]:
        data["history"][date_key] = {
            "completed": 0,
            "total": len(data.get("tasks", [])),
            "xp_gained": 0
        }
    

    data["history"][date_key]["completed"] += 1
    data["history"][date_key]["xp_gained"] += xp_gained


# ---------------- TASK LOGIC ----------------
def recalc_task_done(task):
    if task.get("subtasks"):
        task["done"] = all(st["done"] for st in task["subtasks"])
    else:
        task["done"] = False


def toggle_subtask(data, task_i, sub_i, is_done):
    task = data["tasks"][task_i]
    sub = task["subtasks"][sub_i]

    if sub["done"] != is_done:
        sub["done"] = is_done

        xp_gain = xp_per_task(len(data["tasks"])) / max(
            1, len(task["subtasks"])
        )

        if is_done and not sub.get("xp_given", False):
            data["xp"] += xp_gain
            sub["xp_given"] = True
            update_history(data, xp_gain)

    recalc_task_done(task)

    while data["xp"] >= 100:
        data["xp"] -= 100
        data["level"] += 1

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
        save_data(data)



def edit_task(data, index, new_title):
    if new_title.strip():
        data["tasks"][index]["title"] = new_title
        save_data(data)


def delete_task(data, index):
    data["tasks"].pop(index)
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
    today_str = date.today().isoformat()

    if data.get("last_date") == today_str:
        return

    for task in data.get("tasks", []):
        task["done"] = False
        for sub in task.get("subtasks", []):
            sub["done"] = False
            sub["xp_given"] = False

    data["last_date"] = today_str
    save_data(data)
