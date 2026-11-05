# ==================== REPOSITORY.PY ====================
# Typed data services. The ONLY state-mutation surface for the agent layer:
# controller, tools, and planner go through repositories; logic.py becomes an
# implementation detail behind them (and remains the UI's direct API so V1
# behavior is untouched).
#
# Repositories hold a live reference to the loaded store dict (same pattern as
# the rest of the app), validate at the boundary with models.py, and delegate
# persistence to logic.save_data (atomic writes, migration-aware).

from __future__ import annotations

import time
import uuid
from typing import Any

from focus_agent import models as m
from focus_agent.models import (
    Task, Subject, ScheduleBlock, Goal, GoalMilestone, FocusSessionRecord,
    AgentConversation, AgentAction, AgentTurnRecord, AgentPendingQuestion,
)


class ValidationError(ValueError):
    """Raised when a write would violate a domain model's constraints."""


def _pydantic_msg(e) -> str:
    """Human-readable summary of a pydantic ValidationError (or any exception)."""
    errors_fn = getattr(e, "errors", None)
    if callable(errors_fn):
        try:
            return "; ".join(str(x.get("msg", "")) for x in errors_fn()[:3]) or str(e)
        except Exception:
            return str(e)
    return str(e)


def _model_write(model_cls, data: dict, **fields) -> dict:
    """Validate fields through a model and return the validated dict form."""
    try:
        inst = model_cls(**fields)
    except Exception as e:  # pydantic ValidationError and friends
        raise ValidationError(_pydantic_msg(e)) from e
    return inst.to_store()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# ==================== TASKS ====================

class TaskRepository:
    def __init__(self, data: dict):
        self.data = data

    def _tasks(self) -> list[dict]:
        return self.data.setdefault("tasks", [])

    # -- reads ---------------------------------------------------------
    def get(self, task_id: str) -> dict | None:
        return next((t for t in self._tasks() if t.get("id") == task_id), None)

    def find_fuzzy(self, ref: str) -> dict | None:
        """Exact id, then unique substring title match (recent first)."""
        if not ref:
            return None
        t = self.get(ref)
        if t:
            return t
        frag = ref.lower().strip()
        matches = [t for t in self._tasks() if frag in (t.get("title") or "").lower()]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return sorted(matches, key=lambda t: t.get("updated_at") or "",
                          reverse=True)[0]
        return None

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Ranked text search over title/notes/subject with simple scoring."""
        q = (query or "").lower().strip()
        if not q:
            return []
        scored = []
        for t in self._tasks():
            title = (t.get("title") or "").lower()
            notes = (t.get("notes") or "").lower()
            subj = (t.get("subject") or "").lower()
            score = 0.0
            if q == title:
                score = 1.0
            elif q in title:
                score = 0.8
            else:
                tokens = [w for w in q.split() if len(w) > 2]
                hits = sum(1 for w in tokens if w in title)
                if tokens:
                    score = max(score, 0.6 * hits / len(tokens))
                if q in subj:
                    score = max(score, 0.5)
                if q in notes:
                    score = max(score, 0.4)
            if score > 0:
                scored.append((score, t))
        scored.sort(key=lambda st: (-st[0], st[1].get("date") or "9999"))
        return [{"task": t, "score": round(s, 2)} for s, t in scored[:limit]]

    def list(self, *, status: str | None = None, subject: str | None = None,
             due_before: str | None = None, due_after: str | None = None,
             include_classes: bool = False) -> list[dict]:
        out = []
        for t in self._tasks():
            if not include_classes and t.get("type") == "class":
                continue
            if status and t.get("status") != status:
                continue
            if subject and (t.get("subject") or "").lower() != subject.lower():
                continue
            due = t.get("date")
            if due_before and (not due or due > due_before):
                continue
            if due_after and (not due or due < due_after):
                continue
            out.append(t)
        return out

    def model(self, task_id: str) -> Task:
        """Typed view; raises ValidationError when the record is corrupt."""
        t = self.get(task_id)
        if not t:
            raise ValidationError(f"task {task_id!r} not found")
        try:
            return Task(**t)
        except Exception as e:
            raise ValidationError(f"task {task_id!r} fails validation: {e}") from e

    # -- writes --------------------------------------------------------
    def create(self, title: str, *, deadline: str | None = None,
               duration: int | None = None, subject: str | None = None,
               notes: str = "", importance: int | None = None,
               difficulty: int | None = None, priority_hint: int | None = None,
               due_time: str | None = None, recurrence: dict | None = None,
               goal_id: str | None = None, subtasks: list[str] | None = None,
               task_type: str = "task", schedule: dict | None = None,
               days: list[str] | None = None) -> dict:
        if not (title or "").strip():
            raise ValidationError("title must be a non-empty string")
        from logic import add_task_logic, add_subtask, update_task_logic
        task = add_task_logic(
            self.data, title, category=task_type, deadline=deadline,
            duration=duration, subject=subject, notes=notes,
            days=days, schedule=schedule,
        )
        if not task:
            raise ValidationError("task creation failed")
        fields: dict[str, Any] = {}
        if due_time:
            fields["due_time"] = due_time
        if importance is not None:
            fields["importance"] = importance
        if difficulty is not None:
            fields["difficulty"] = difficulty
        if priority_hint is not None:
            fields["priority_hint"] = priority_hint
        if recurrence is not None:
            fields["recurrence"] = recurrence
        if goal_id:
            fields["goal_id"] = goal_id
        if fields:
            self.update(task["id"], **fields)
        for st in (subtasks or [])[:20]:
            add_subtask(self.data, task["id"], st)
        return self.get(task["id"])

    def update(self, task_id: str, **fields) -> dict:
        """Validated field update. Accepts domain names (due_date,
        duration_minutes) and store names (date, duration) alike; None fields
        are ignored."""
        t = self.get(task_id)
        if not t:
            raise ValidationError(f"task {task_id!r} not found")
        field_map = {"due_date": "date", "duration_minutes": "duration"}
        # validate through the model: overlay current + proposed fields
        proposed = {}
        for k, v in fields.items():
            if v is None:
                continue
            proposed[field_map.get(k, k)] = v
        merged = {**t, **proposed}
        try:
            Task(**merged)
        except Exception as e:
            raise ValidationError(f"update rejected: {_pydantic_msg(e)}") from e
        from logic import update_task_logic
        update_task_logic(self.data, task_id, **proposed)
        return self.get(task_id)

    def complete(self, task_id: str, actual_minutes: int | None = None) -> dict:
        from logic import complete_task_logic, record_actual_duration
        if actual_minutes is not None:
            record_actual_duration(self.data, task_id, int(actual_minutes))
        complete_task_logic(self.data, task_id)
        return self.get(task_id)

    def reopen(self, task_id: str) -> dict | None:
        from logic import reopen_task_logic
        if not reopen_task_logic(self.data, task_id):
            raise ValidationError(f"task {task_id!r} cannot be reopened")
        return self.get(task_id)

    def delete(self, task_id: str) -> bool:
        from logic import delete_task_logic
        if not self.get(task_id):
            raise ValidationError(f"task {task_id!r} not found")
        delete_task_logic(self.data, task_id)
        return True

    def add_reschedule_entry(self, task_id: str, entry: dict) -> None:
        """Append to the task's reschedule history (additive v4 field)."""
        t = self.get(task_id)
        if not t:
            raise ValidationError(f"task {task_id!r} not found")
        hist = t.setdefault("reschedule_history", [])
        hist.append({**entry, "ts": entry.get("ts") or int(time.time())})
        if len(hist) > 20:
            t["reschedule_history"] = hist[-20:]
        from logic import save_data
        save_data(self.data)


# ==================== SUBJECTS ====================

class SubjectRepository:
    def __init__(self, data: dict):
        self.data = data

    def _subjects(self) -> dict:
        return self.data.setdefault("subjects", {})

    def list(self) -> list[Subject]:
        out = []
        for name, info in sorted(self._subjects().items()):
            info = info if isinstance(info, dict) else {}
            out.append(Subject(name=name, notes=info.get("notes", ""),
                               documents=list(info.get("documents", [])),
                               keywords=list(info.get("keywords", []))))
        return out

    def names(self) -> list[str]:
        return [s.name for s in self.list()]

    def create(self, name: str, keywords: list[str] | None = None) -> Subject:
        if not (name or "").strip():
            raise ValidationError("subject name must be non-empty")
        subjects = self._subjects()
        if name in subjects:
            raise ValidationError(f"subject {name!r} already exists")
        inst = Subject(name=name, keywords=keywords or [])
        subjects[name] = inst.to_store()
        from logic import save_data
        save_data(self.data)
        return inst

    def rename(self, old: str, new: str) -> None:
        if not (new or "").strip():
            raise ValidationError("new name must be non-empty")
        from logic import rename_subject
        rename_subject(self.data, old, new)

    def set_keywords(self, name: str, keywords: list[str]) -> Subject:
        subjects = self._subjects()
        if name not in subjects:
            raise ValidationError(f"subject {name!r} not found")
        subjects[name]["keywords"] = [str(k)[:40] for k in (keywords or [])][:20]
        from logic import save_data
        save_data(self.data)
        return Subject(name=name, notes=subjects[name].get("notes", ""),
                       documents=list(subjects[name].get("documents", [])),
                       keywords=list(subjects[name]["keywords"]))

    def delete(self, name: str) -> None:
        from logic import delete_subject
        delete_subject(self.data, name)


# ==================== SCHEDULE BLOCKS ====================

class ScheduleRepository:
    """Custom fixed commitments (data['schedule_blocks'], additive v4)."""
    def __init__(self, data: dict):
        self.data = data

    def _blocks(self) -> list[dict]:
        return self.data.setdefault("schedule_blocks", [])

    def list(self, date: str | None = None, weekday: str | None = None) -> list[dict]:
        out = []
        for b in self._blocks():
            if date and b.get("date") not in (None, date):
                continue
            if weekday and weekday not in (b.get("days") or []) and b.get("date") != date:
                continue
            out.append(b)
        return out

    def create(self, title: str, start: str, end: str, *,
               days: list[str] | None = None, date: str | None = None,
               kind: str = "commitment", note: str | None = None) -> dict:
        block = _model_write(ScheduleBlock, self.data,
                             id=_new_id("blk"), title=title, start=start, end=end,
                             days=days or [], date=date, kind=kind, note=note,
                             created_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        self._blocks().append(block)
        from logic import save_data
        save_data(self.data)
        return block

    def update(self, block_id: str, **fields) -> dict:
        b = next((x for x in self._blocks() if x.get("id") == block_id), None)
        if not b:
            raise ValidationError(f"schedule block {block_id!r} not found")
        merged = {**b, **{k: v for k, v in fields.items() if v is not None}}
        try:
            ScheduleBlock(**merged)
        except Exception as e:
            raise ValidationError(f"block update rejected: {_pydantic_msg(e)}") from e
        b.update({k: v for k, v in fields.items() if v is not None})
        from logic import save_data
        save_data(self.data)
        return b

    def delete(self, block_id: str) -> bool:
        blocks = self._blocks()
        kept = [b for b in blocks if b.get("id") != block_id]
        if len(kept) == len(blocks):
            raise ValidationError(f"schedule block {block_id!r} not found")
        self.data["schedule_blocks"] = kept
        from logic import save_data
        save_data(self.data)
        return True


# ==================== GOALS ====================

class GoalRepository:
    def __init__(self, data: dict):
        self.data = data

    def _goals(self) -> list[dict]:
        return self.data.setdefault("goals", [])

    def list(self) -> list[dict]:
        return list(self._goals())

    def get(self, goal_id: str) -> dict | None:
        return next((g for g in self._goals() if g.get("id") == goal_id), None)

    def find_by_title(self, ref: str) -> dict | None:
        ref_l = (ref or "").lower()
        for g in self._goals():
            if ref_l and ref_l in (g.get("title") or "").lower():
                return g
        return None

    def validate(self, goal_dict: dict) -> Goal:
        try:
            return Goal(**goal_dict)
        except Exception as e:
            raise ValidationError(f"goal invalid: {_pydantic_msg(e)}") from e

    def add_milestone(self, goal_id: str, title: str, *,
                      target_date: str | None = None,
                      estimated_minutes: int | None = None) -> dict:
        g = self.get(goal_id)
        if not g:
            raise ValidationError(f"goal {goal_id!r} not found")
        ms = _model_write(GoalMilestone, self.data, id=_new_id("ms"),
                          title=title, target_date=target_date,
                          estimated_minutes=estimated_minutes)
        g.setdefault("milestones", []).append(ms)
        from logic import save_data
        save_data(self.data)
        return ms


# ==================== FOCUS / PRODUCTIVITY ====================

class FocusRepository:
    """Timed sessions: keeps V1 daily aggregates AND adds per-session records
    plus hourly buckets (both additive v4) that the learning engine needs."""
    def __init__(self, data: dict):
        self.data = data

    def log_session(self, date: str, minutes: int, *, kind: str = "focus",
                    task_id: str | None = None,
                    started_hhmm: str | None = None) -> FocusSessionRecord:
        if minutes < 1:
            raise ValidationError("minutes must be >= 1")
        rec = _model_write(FocusSessionRecord, self.data, date=date,
                           minutes=int(minutes), kind=kind, task_id=task_id,
                           started_hhmm=started_hhmm,
                           recorded_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        log = self.data.setdefault("focus_session_log", [])
        log.append(rec)
        if len(log) > 2000:
            self.data["focus_session_log"] = log[-2000:]
        # hourly bucket (from started time, else unattributed hour 99)
        hour = started_hhmm[:2] if started_hhmm else "99"
        buckets = self.data.setdefault("hourly_focus", {})
        day = buckets.setdefault(date, {})
        day[hour] = round(day.get(hour, 0.0) + minutes, 1)
        from logic import save_data
        save_data(self.data)
        return FocusSessionRecord(**rec)

    def hourly_focus(self, date: str | None = None) -> dict:
        buckets = self.data.get("hourly_focus", {})
        return buckets.get(date, {}) if date else buckets

    def session_log(self, days: int = 30) -> list[dict]:
        log = self.data.get("focus_session_log", [])
        return list(log[-days:])


# ==================== AGENT MEMORY ====================

class MemoryRepository:
    """Conversations + actions (persistent, bounded). App logic owns writes -
    the LLM never touches these directly."""
    CONVERSATION_CAP = 50
    TURN_CAP = 200
    ACTION_CAP = 1000

    def __init__(self, data: dict):
        self.data = data

    def _mem(self) -> dict:
        return self.data.setdefault("agent_memory", {})

    # -- conversations --------------------------------------------------
    def open_conversation(self, conv_id: str | None = None) -> AgentConversation:
        now = int(time.time())
        conv = AgentConversation(id=conv_id or _new_id("conv"), started_at=now,
                                 updated_at=now)
        convs = self._mem().setdefault("conversations", [])
        convs.append(conv.to_store())
        self._trim_conversations()
        from logic import save_data
        save_data(self.data)
        return conv

    def _trim_conversations(self) -> None:
        convs = self._mem().get("conversations", [])
        if len(convs) > self.CONVERSATION_CAP:
            self._mem()["conversations"] = convs[-self.CONVERSATION_CAP:]

    def latest_conversation(self) -> dict | None:
        convs = self._mem().get("conversations", [])
        return convs[-1] if convs else None

    def append_turn(self, conversation_id: str, turn: AgentTurnRecord) -> None:
        conv = next((c for c in self._mem().get("conversations", [])
                     if c.get("id") == conversation_id), None)
        if not conv:
            raise ValidationError(f"conversation {conversation_id!r} not found")
        conv["turns"].append(turn.to_store())
        if len(conv["turns"]) > self.TURN_CAP:
            conv["turns"] = conv["turns"][-self.TURN_CAP:]
        conv["updated_at"] = int(time.time())
        from logic import save_data
        save_data(self.data)

    def set_pending_question(self, conversation_id: str,
                             pending: AgentPendingQuestion | None) -> None:
        conv = next((c for c in self._mem().get("conversations", [])
                     if c.get("id") == conversation_id), None)
        if not conv:
            raise ValidationError(f"conversation {conversation_id!r} not found")
        conv["pending"] = pending.to_store() if pending else None
        from logic import save_data
        save_data(self.data)

    # -- actions ---------------------------------------------------------
    def log_action(self, action: AgentAction) -> None:
        actions = self._mem().setdefault("actions", [])
        actions.append(action.to_store())
        if len(actions) > self.ACTION_CAP:
            self._mem()["actions"] = actions[-self.ACTION_CAP:]
        from logic import save_data
        save_data(self.data)

    def recent_actions(self, limit: int = 20) -> list[dict]:
        return list(self._mem().get("actions", [])[-limit:])


__all__ = [
    "TaskRepository", "SubjectRepository", "ScheduleRepository", "GoalRepository",
    "FocusRepository", "MemoryRepository", "ValidationError",
]
