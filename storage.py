# ==================== STORAGE.PY ====================
# Schema versioning + backward-compatible migration for data.json.
#
# Rules:
# - Migration is ADDITIVE ONLY. Existing keys, tasks, and history are never
#   removed, reset, or rewritten.
# - A timestamped backup of data.json is created BEFORE the first migration
#   save (rollback = restore the backup file).
# - Corrupt/missing data degrades safely instead of raising.

import os
import json
import shutil
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")

SCHEMA_VERSION = 3

DEFAULT_AGENT_SETTINGS = {
    "provider": "ollama",          # "ollama" | "online" | "none"
    "endpoint": "http://localhost:11434",
    "model": "qwen3:4b",           # placeholder; user configures their installed tag
    "timeout_seconds": 120,
    "online_research_enabled": False,
    "online_model": "",            # model name for the optional online adapter
    "temperature": 0.2,
}

DEFAULT_STUDY_HOURS = {"start": "09:00", "end": "22:00"}


def default_agent_section():
    """Fresh defaults for the agent memory section (all additive)."""
    return {
        "estimation_records": [],   # one per completed task with est+actual
        "tool_log": [],             # capped audit of agent tool executions
        "plan_log": [],             # capped history of generated daily plans
        "executed_calls": [],       # recent tool call ids (idempotency)
    }


def make_backup(source_path=None, backup_dir=None):
    """Copy data.json to backups/ with a timestamp; returns backup path or None.

    Paths resolve at call time so tests can redirect storage safely.
    """
    source_path = source_path or DATA_FILE
    backup_dir = backup_dir or BACKUP_DIR
    if not os.path.exists(source_path):
        return None
    try:
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = os.path.join(backup_dir, f"data_pre_v{SCHEMA_VERSION}-{stamp}.json")
        shutil.copy2(source_path, dest)
        return dest
    except OSError:
        return None


def load_raw(path=None):
    """Load raw JSON without migration; returns {} on corrupt/missing files.

    path resolves at call time so test redirection stays safe.
    """
    path = path or DATA_FILE
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}


def migrate_data(data, backup=True):
    """Bring a loaded data dict up to SCHEMA_VERSION. Additive only.

    Returns (data, migrated_bool, backup_path_or_None).
    """
    if not isinstance(data, dict):
        data = {}
    migrated = data.get("schema_version", 1) < SCHEMA_VERSION
    backup_path = None

    if migrated and backup:
        backup_path = make_backup()

    # --- v3 additive fields -------------------------------------------
    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("goals", [])
    data.setdefault("agent_memory", default_agent_section())
    data.setdefault("streak", 0)  # int kept for the existing XPBar display

    settings = data.setdefault("settings", {})
    settings.setdefault("timezone", "local")
    settings.setdefault("study_hours", dict(DEFAULT_STUDY_HOURS))
    settings.setdefault("break_minutes", 10)
    settings.setdefault("agent", dict(DEFAULT_AGENT_SETTINGS))

    for task in data.get("tasks", []):
        if not isinstance(task, dict):
            continue
        task.setdefault("importance", 2)        # 1 low .. 3 high
        task.setdefault("difficulty", 2)        # 1 easy .. 3 hard
        task.setdefault("actual_minutes", None)  # measured focus time (int)
        task.setdefault("completed_at", None)    # ISO timestamp on completion
        task.setdefault("priority_hint", None)   # user/LLM hint 0-100, advisory
        task.setdefault("planned", None)         # {date, start, end, reason}
        task.setdefault("recurrence", None)      # {"type": "daily"|"weekly", ...}
        task.setdefault("goal_id", None)

    # Cap unbounded agent logs defensively on every load
    mem = data.get("agent_memory", {})
    if len(mem.get("tool_log", [])) > 500:
        mem["tool_log"] = mem["tool_log"][-500:]
    if len(mem.get("plan_log", [])) > 200:
        mem["plan_log"] = mem["plan_log"][-200:]
    if len(mem.get("executed_calls", [])) > 300:
        mem["executed_calls"] = mem["executed_calls"][-300:]

    data["schema_version"] = SCHEMA_VERSION
    return data, migrated, backup_path


def restore_backup(backup_path, data_file=None):
    """Restore a backup created by make_backup. Returns True on success.

    data_file resolves at call time so test redirection stays safe.
    """
    data_file = data_file or DATA_FILE
    if not backup_path or not os.path.exists(backup_path):
        return False
    try:
        shutil.copy2(backup_path, data_file)
        return True
    except OSError:
        return False
