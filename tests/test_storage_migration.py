"""Migration safety: additive v3 upgrade, backups, restore, corrupt recovery (spec N.8, K)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logic
import storage


def _v1_store():
    return {
        "xp": 120,
        "level": 2,
        "tasks": [
            {"type": "task", "id": "t-1", "title": "Old essay", "duration": 60,
             "date": "2026-10-25", "status": "pending", "subject": "AI",
             "subtasks": [], "notes": "keep me"},
            {"type": "class", "id": "c-1", "title": "CSE 3202",
             "schedule": {"days": ["fri"], "start": "10:00", "end": "11:30"}},
        ],
        "subjects": {"AI": {"notes": "n", "documents": []}},
        "history": {"2026-10-20": {"sessions": 2, "focus_minutes": 50}},
        "focus_sessions": {},
        "settings": {"theme": "dark"},
    }


def _write_store(data_env, store):
    with open(data_env["data_file"], "w", encoding="utf-8") as f:
        json.dump(store, f)


def test_v1_data_gains_fields_keeps_values(data_env):
    _write_store(data_env, _v1_store())
    data = logic.load_data()

    # all V1 values preserved
    t = data["tasks"][0]
    assert t["title"] == "Old essay" and t["duration"] == 60
    assert t["date"] == "2026-10-25" and t["status"] == "pending"
    assert t["notes"] == "keep me" and t["subtasks"] == []
    assert data["xp"] == 120 and data["level"] == 2
    assert data["settings"]["theme"] == "dark"
    assert data["history"]["2026-10-20"]["focus_minutes"] == 50
    assert data["tasks"][1]["schedule"]["days"] == ["fri"]
    # additive fields now exist
    assert data["schema_version"] == storage.SCHEMA_VERSION
    for field in ("importance", "difficulty", "actual_minutes", "completed_at"):
        assert field in t
    assert "goals" in data and "agent_memory" in data and "streak" in data
    assert "agent" in data["settings"] and "timezone" in data["settings"]


def test_migration_writes_timestamped_backup(data_env):
    _write_store(data_env, _v1_store())
    with open(data_env["data_file"], encoding="utf-8") as f:
        original = json.load(f)
    _, migrated, backup_path = storage.migrate_data(original)
    assert migrated and backup_path and os.path.exists(backup_path)
    with open(backup_path, encoding="utf-8") as f:
        backed_up = json.load(f)
    assert "schema_version" not in backed_up, "backup must hold the pre-migration original"


def test_already_current_schema_not_rebacked(data):
    data = logic.load_data()  # fresh store is already at SCHEMA_VERSION
    _, migrated, backup_path = storage.migrate_data(data)
    assert not migrated and backup_path is None


def test_corrupt_file_recovered_not_destroyed(data_env):
    with open(data_env["data_file"], "w", encoding="utf-8") as f:
        f.write('{"user": {"name": "Half-written"')  # truncated JSON
    data = logic.load_data()
    assert data["tasks"] == []  # fresh valid store served instead
    data_dir = os.path.dirname(data_env["data_file"])
    corrupt = [p for p in os.listdir(data_dir) if ".corrupt-" in p]
    assert corrupt, "corrupt original must be preserved for manual recovery"


def test_backup_and_restore_roundtrip(data_env):
    data = logic.load_data()
    logic.add_task_logic(data, "Pre-backup task", duration=30)
    backup = storage.make_backup()
    assert backup and os.path.exists(backup)

    data["tasks"] = []
    logic.save_data(data)
    assert not logic.load_data()["tasks"]

    assert storage.restore_backup(backup) is True
    restored = logic.load_data()
    assert any(t["title"] == "Pre-backup task" for t in restored["tasks"])
    assert storage.restore_backup("/nonexistent/file.json") is False


def test_stable_task_ids_survive_migration(data_env):
    store = _v1_store()
    store["tasks"][0]["id"] = "legacy-id-42"
    _write_store(data_env, store)
    data = logic.load_data()
    assert data["tasks"][0]["id"] == "legacy-id-42", "IDs must never be regenerated"
