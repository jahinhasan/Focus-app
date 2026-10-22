# ==================== CONFTEST.PY (test fixtures) ====================
import json
import os
import sys
import tempfile
from datetime import datetime

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from focus_agent.llm import LLMProvider, ProviderUnavailable, BadResponse  # noqa: E402


@pytest.fixture()
def data_env(tmp_path, monkeypatch):
    """Isolated storage: data.json + backups redirect into a temp dir."""
    import logic
    import storage

    data_file = tmp_path / "data.json"
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(logic, "DATA_FILE", str(data_file))
    monkeypatch.setattr(storage, "DATA_FILE", str(data_file))
    monkeypatch.setattr(storage, "BACKUP_DIR", str(backup_dir))
    if data_file.exists():
        data_file.unlink()
    return {"data_file": str(data_file), "backup_dir": str(backup_dir)}


@pytest.fixture()
def data(data_env):
    """A freshly migrated, empty store."""
    import logic
    return logic.load_data()


@pytest.fixture()
def sample_data(data):
    """Store with subjects, a class routine, and tasks (deterministic base)."""
    import logic
    logic.add_subject(data, "AI")
    logic.add_subject(data, "Database Systems")
    logic.add_class_task(data, title="CSE 3202", subject="AI",
                         days=["fri"], start_time="10:00", end_time="11:30")
    logic.add_task_logic(data, "AI assignment", deadline="2026-10-24", duration=120,
                         subject="AI", importance=3, difficulty=3)
    logic.add_task_logic(data, "Python practice", deadline="2026-10-23", duration=45)
    logic.add_task_logic(data, "Database reading", deadline="2026-10-25", duration=60,
                         subject="Database Systems", difficulty=2)
    return data


NOW = datetime(2026, 10, 23, 14, 0)  # a Friday


class MockProvider(LLMProvider):
    """Scriptable provider for deterministic agent tests."""

    name = "mock"

    def __init__(self, response=None, error=None):
        self.response = response or {}
        self.error = error
        self.calls = []

    def chat(self, system, user, history=None, temperature=0.2, max_tokens=2048):
        self.calls.append({"system": system, "user": user})
        if self.error:
            raise self.error
        return json.dumps(self.response)

    def status(self):
        return True, "mock connected"


class OfflineProvider(LLMProvider):
    """Simulates Ollama being unreachable."""

    name = "offline"

    def chat(self, system, user, history=None, temperature=0.2, max_tokens=2048):
        raise ProviderUnavailable("Could not connect (mock offline)")

    def status(self):
        return False, "offline"


class GarbageProvider(LLMProvider):
    """Returns malformed output - exercises tolerant JSON extraction."""

    name = "garbage"

    def __init__(self, text="```json\n{broken output here"):
        self.text = text

    def chat(self, system, user, history=None, temperature=0.2, max_tokens=2048):
        return self.text

    def status(self):
        return True, "garbage"
