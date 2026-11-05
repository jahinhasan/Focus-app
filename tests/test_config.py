"""Config precedence: env > data.settings > default (Phase 1)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from focus_agent.config import (
    get_agent_config, get_loop_budgets, get_study_config,
)


def test_defaults_without_data_or_env():
    cfg = get_agent_config({})
    assert cfg.provider == "ollama" and cfg.model == "qwen3:4b"
    assert cfg.timeout_seconds == 120


def test_settings_beat_defaults(data):
    data["settings"]["agent"]["model"] = "qwen2.5:7b"
    data["settings"]["study_hours"]["end"] = "20:00"
    cfg = get_agent_config(data)
    assert cfg.model == "qwen2.5:7b"
    st = get_study_config(data)
    assert st.study_end == "20:00"


def test_env_beats_settings(monkeypatch, data):
    data["settings"]["agent"]["model"] = "qwen2.5:7b"
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:8b")
    monkeypatch.setenv("FOCUS_AGENT_MAX_STEPS", "3")
    cfg = get_agent_config(data)
    assert cfg.model == "qwen3:8b"
    b = get_loop_budgets()
    assert b.max_steps == 3
    assert b.max_llm_calls == 4  # unset -> default


def test_budget_clamping(monkeypatch):
    monkeypatch.setenv("FOCUS_AGENT_MAX_STEPS", "999")
    assert get_loop_budgets().max_steps == 20  # clamped to hi bound


def test_bad_env_int_falls_back(monkeypatch):
    monkeypatch.setenv("OLLAMA_TIMEOUT", "not-a-number")
    monkeypatch.setenv("FOCUS_AGENT_MAX_LLM_CALLS", "2")
    assert get_loop_budgets().max_llm_calls == 2
    cfg = get_agent_config({})
    assert cfg.timeout_seconds == 120
