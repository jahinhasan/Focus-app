# ==================== CONFIG.PY ====================
# Centralized configuration resolution: environment variable -> data.settings
# -> default. Replaces the scattered lookups (llm.py factory, scheduler study
# hours, controller budgets) with one precedence chain per ARCHITECTURE.md §6.
#
# Secrets never live here or in data files: ONLINE_LLM_API_KEY stays env-only.

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentConfig:
    provider: str = "ollama"            # ollama | online | none
    endpoint: str = "http://localhost:11434"
    model: str = "qwen3:4b"
    timeout_seconds: int = 120
    temperature: float = 0.2
    online_model: str = ""
    online_research_enabled: bool = False


@dataclass(frozen=True)
class LoopBudgets:
    max_steps: int = 6
    max_llm_calls: int = 4
    max_tool_calls: int = 8


@dataclass(frozen=True)
class StudyConfig:
    study_start: str = "09:00"
    study_end: str = "22:00"
    break_minutes: int = 10
    timezone: str = "local"


def _env(name: str) -> str | None:
    v = os.environ.get(name)
    return v if v not in (None, "") else None


def _int_env(name: str, fallback: int, lo: int = 1, hi: int = 100) -> int:
    try:
        n = int(_env(name) or fallback)
        return max(lo, min(hi, n))
    except (TypeError, ValueError):
        return fallback


def get_agent_config(data: dict | None = None) -> AgentConfig:
    """LLM connection config with documented precedence: env > settings > default."""
    settings = ((data or {}).get("settings") or {})
    agent = settings.get("agent") or {}
    return AgentConfig(
        provider=(_env("FOCUS_LLM_PROVIDER") or agent.get("provider") or "ollama").lower(),
        endpoint=_env("OLLAMA_HOST") or agent.get("endpoint") or "http://localhost:11434",
        model=_env("OLLAMA_MODEL") or agent.get("model") or "qwen3:4b",
        timeout_seconds=_int_env("OLLAMA_TIMEOUT", int(agent.get("timeout_seconds") or 120), 5, 600),
        temperature=float(agent.get("temperature") or 0.2),
        online_model=agent.get("online_model") or "",
        online_research_enabled=bool(agent.get("online_research_enabled")),
    )


def get_loop_budgets() -> LoopBudgets:
    """Agent-loop budgets (env-tunable; test can shrink them)."""
    return LoopBudgets(
        max_steps=_int_env("FOCUS_AGENT_MAX_STEPS", 6, 1, 20),
        max_llm_calls=_int_env("FOCUS_AGENT_MAX_LLM_CALLS", 4, 1, 20),
        max_tool_calls=_int_env("FOCUS_AGENT_MAX_TOOL_CALLS", 8, 1, 40),
    )


def get_study_config(data: dict | None = None) -> StudyConfig:
    settings = ((data or {}).get("settings") or {})
    hours = settings.get("study_hours") or {}
    return StudyConfig(
        study_start=str(hours.get("start") or "09:00"),
        study_end=str(hours.get("end") or "22:00"),
        break_minutes=int(settings.get("break_minutes") or 10),
        timezone=str(settings.get("timezone") or "local"),
    )


__all__ = ["AgentConfig", "LoopBudgets", "StudyConfig",
           "get_agent_config", "get_loop_budgets", "get_study_config"]
