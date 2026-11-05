# ==================== MODELS.PY ====================
# Typed domain models (spec §9). Pydantic v2 with extra="allow" so a model
# round-trips the stored dict shape without dropping fields it does not know
# about - user data written by older versions (or the UI) survives unchanged.
#
# Rules:
# - Models VALIDATE; they never mutate the store themselves (repositories do).
# - Dates/times stay strings in the stored format (YYYY-MM-DD / HH:MM) so the
#   JSON store shape is untouched; validators check the format.
# - Unknown values are None, never invented (same rule as schemas.py).

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

TaskType = Literal["task", "class"]
TaskStatus = Literal["pending", "todo", "active", "done", "missed", "ended", "archived"]


def _optional_date(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, str) and _DATE_RE.match(value):
        return value
    raise ValueError(f"invalid date {value!r}: expected YYYY-MM-DD")


def _optional_hhmm(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, str) and _HHMM_RE.match(value.strip()):
        return value.strip()
    raise ValueError(f"invalid time {value!r}: expected HH:MM (24h)")


class _StoreModel(BaseModel):
    """Base for all persisted models: tolerate and preserve unknown keys."""

    model_config = ConfigDict(extra="allow", validate_assignment=True, str_strip_whitespace=True)

    def to_store(self) -> dict:
        """Dict for the JSON store - includes unknown passthrough fields."""
        out = self.model_dump(mode="python")
        # drop None for keys that were never set so stores stay tidy, but keep
        # explicitly-known fields (consistent with migrate_data setdefaults)
        return out


class Subtask(_StoreModel):
    title: str = Field(min_length=1, max_length=200)
    done: bool = False


class PlannedSlot(_StoreModel):
    """A committed scheduling slot for a task (from scheduler.apply_plan)."""
    date: str
    start: str
    end: str
    reason: str = ""

    @field_validator("date")
    @classmethod
    def _v_date(cls, v):
        return _optional_date(v)

    @field_validator("start", "end")
    @classmethod
    def _v_time(cls, v):
        return _optional_hhmm(v)


class Task(_StoreModel):
    """A task or recurring class (type discriminates; mirrors the store shape)."""
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    type: TaskType = "task"
    status: TaskStatus = "pending"
    subject: str | None = None
    date: str | None = None                    # due date YYYY-MM-DD
    due_time: str | None = None                # HH:MM
    duration: int | None = Field(default=None, ge=5, le=16 * 60)   # estimate, minutes
    actual_minutes: int | None = Field(default=None, ge=1, le=24 * 60)
    completed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    notes: str = ""
    importance: int | None = Field(default=None, ge=1, le=3)
    difficulty: int | None = Field(default=None, ge=1, le=3)
    priority_hint: int | None = Field(default=None, ge=0, le=100)
    subtasks: list[Subtask] = Field(default_factory=list)
    planned: PlannedSlot | None = None
    recurrence: dict | None = None             # {"type": "daily"|"weekly", "days": [...]}
    goal_id: str | None = None
    schedule: dict | None = None               # classes: {"days": [...], "start", "end"}
    category: str | None = None
    reschedule_history: list[dict] = Field(default_factory=list)  # additive v4

    @field_validator("date")
    @classmethod
    def _v_date(cls, v):
        return _optional_date(v)

    @field_validator("due_time")
    @classmethod
    def _v_time(cls, v):
        return _optional_hhmm(v)

    @field_validator("recurrence")
    @classmethod
    def _v_recurrence(cls, v):
        if v is None:
            return None
        if not isinstance(v, dict) or v.get("type") not in ("daily", "weekly"):
            raise ValueError("recurrence must be {'type': 'daily'|'weekly', ...}")
        return v

    @property
    def is_class(self) -> bool:
        return self.type == "class"


class Subject(_StoreModel):
    """A vault subject (routine-derived subjects live on class tasks)."""
    name: str = Field(min_length=1, max_length=120)
    notes: str = ""
    documents: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)   # additive v4 (update_subject)


class ClassMeeting(_StoreModel):
    """One weekly class occurrence derived from a class task's schedule."""
    task_id: str
    title: str
    subject: str | None = None
    day: Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    start: str
    end: str

    @field_validator("start", "end")
    @classmethod
    def _v_time(cls, v):
        return _optional_hhmm(v)


class ScheduleBlock(_StoreModel):
    """A user-claimed fixed commitment (spec: 'I have a class 10-12, don't
    schedule anything'). Stored in data['schedule_blocks'] (v4)."""
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    days: list[str] = Field(default_factory=list)       # weekly recurrence
    date: str | None = None                             # one-off block
    start: str
    end: str
    kind: Literal["class", "commitment", "busy"] = "commitment"
    note: str | None = None
    created_at: str | None = None

    @field_validator("date")
    @classmethod
    def _v_date(cls, v):
        return _optional_date(v)

    @field_validator("start", "end")
    @classmethod
    def _v_time(cls, v):
        return _optional_hhmm(v)

    @field_validator("days")
    @classmethod
    def _v_days(cls, v):
        days = [str(d).lower()[:3] for d in (v or [])]
        bad = [d for d in days if d not in _WEEKDAYS]
        if bad:
            raise ValueError(f"invalid days {bad}: use mon..sun")
        return sorted(set(days))

    @field_validator("end")
    @classmethod
    def _v_order(cls, v, info):
        start = info.data.get("start")
        if start and v and v <= start:
            raise ValueError("end must be after start")
        return v


class GoalMilestone(_StoreModel):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    done: bool = False
    target_date: str | None = None
    estimated_minutes: int | None = Field(default=None, ge=5, le=10000)
    completed_at: str | None = None

    @field_validator("target_date")
    @classmethod
    def _v_date(cls, v):
        return _optional_date(v)


class Goal(_StoreModel):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    status: Literal["active", "paused", "done", "archived"] = "active"
    target_date: str | None = None
    subject: str | None = None
    milestones: list[GoalMilestone] = Field(default_factory=list)
    created_at: str | None = None

    @field_validator("target_date")
    @classmethod
    def _v_date(cls, v):
        return _optional_date(v)


class FocusSessionRecord(_StoreModel):
    """One timed session (additive v4; day aggregates in focus_sessions stay)."""
    date: str
    minutes: int = Field(ge=1, le=24 * 60)
    kind: Literal["focus", "class"] = "focus"
    task_id: str | None = None
    started_hhmm: str | None = None
    recorded_at: str | None = None

    @field_validator("date")
    @classmethod
    def _v_date(cls, v):
        return _optional_date(v)

    @field_validator("started_hhmm")
    @classmethod
    def _v_time(cls, v):
        return _optional_hhmm(v)


class UserProfile(_StoreModel):
    """Profile-level scalar state (top-level store keys)."""
    xp: int = Field(default=0, ge=0)
    level: int = Field(default=1, ge=1)
    streak: int = Field(default=0, ge=0)
    timezone: str = "local"


class AgentTurnRecord(_StoreModel):
    """One user->assistant exchange inside a conversation."""
    role: Literal["user", "assistant"]
    content: str
    ts: int | None = None
    tool_calls: list[str] = Field(default_factory=list)   # call_ids, links actions


class AgentPendingQuestion(_StoreModel):
    """A parked clarification awaiting the user's next message."""
    question: str
    intent: str | None = None
    draft: dict = Field(default_factory=dict)     # partial extraction / tool args
    asked_at: int | None = None


class AgentConversation(_StoreModel):
    """Persistent conversation (additive v4, capped by memory store)."""
    id: str = Field(min_length=1, max_length=64)
    started_at: int
    updated_at: int | None = None
    turns: list[AgentTurnRecord] = Field(default_factory=list)
    pending: AgentPendingQuestion | None = None
    status: Literal["open", "closed"] = "open"


class AgentAction(_StoreModel):
    """One validated tool execution (promoted, richer tool_log entry)."""
    call_id: str = Field(min_length=1, max_length=64)
    tool: str = Field(min_length=1, max_length=64)
    args: dict = Field(default_factory=dict)
    ok: bool
    summary: str = ""
    ts: int
    conversation_id: str | None = None
    verified: bool | None = None          # did the loop verify the effect?


class DailyPlanRecord(_StoreModel):
    """A generated plan kept for adherence analytics."""
    date: str
    ts: int
    committed: bool = False
    slots: list[dict] = Field(default_factory=list)
    unscheduled: list[dict] = Field(default_factory=list)
    done_slots: int = 0                   # filled on adherence update

    @field_validator("date")
    @classmethod
    def _v_date(cls, v):
        return _optional_date(v)


class AgentMemory(_StoreModel):
    """The whole agent_memory section (bounds enforced by the memory store)."""
    tool_log: list[dict] = Field(default_factory=list)
    plan_log: list[dict] = Field(default_factory=list)
    executed_calls: list[str] = Field(default_factory=list)
    estimation_records: list[dict] = Field(default_factory=list)
    conversations: list[AgentConversation] = Field(default_factory=list)   # v4
    actions: list[AgentAction] = Field(default_factory=list)               # v4
    hourly_focus: dict[str, dict[str, float]] = Field(default_factory=dict)  # v4
    adherence: dict = Field(default_factory=dict)                          # v4 cache


__all__ = [
    "Subtask", "PlannedSlot", "Task", "Subject", "ClassMeeting", "ScheduleBlock",
    "GoalMilestone", "Goal", "FocusSessionRecord", "UserProfile",
    "AgentTurnRecord", "AgentPendingQuestion", "AgentConversation",
    "AgentAction", "DailyPlanRecord", "AgentMemory",
]
