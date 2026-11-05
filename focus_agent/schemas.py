# ==================== SCHEMAS.PY ====================
# Typed structures for extraction results and tool calls.
# Unknown values are represented as None - never invented. Everything the LLM
# proposes passes through validate_*() before any tool executes.

import re
from dataclasses import dataclass, field, asdict

TASK_STATUSES = ("pending", "todo", "active", "done", "missed", "ended", "archived")
IMPORTANCE_RANGE = (1, 3)
DIFFICULTY_RANGE = (1, 3)
INTENTS = (
    "add_task", "update_task", "complete_task", "delete_task", "reschedule",
    "plan_day", "block_time", "query", "goal", "chat", "unknown",
)


@dataclass
class ExtractedTask:
    """One task understood from a natural-language request."""
    title: str | None = None
    description: str | None = None
    subject: str | None = None              # raw subject mention (may not exist yet)
    subject_confidence: float = 0.0         # filled by subject matcher, not the LLM
    due_date: str | None = None             # YYYY-MM-DD
    due_time: str | None = None             # HH:MM or None (dates without times are fine)
    estimated_minutes: int | None = None
    importance: int | None = None           # 1..3
    difficulty: int | None = None           # 1..3
    priority_hint: int | None = None        # 0..100 advisory
    subtasks: list = field(default_factory=list)   # list[str]
    recurrence: dict | None = None          # {"type": "daily"|"weekly", "days": [...]}
    goal_title: str | None = None           # set when the request belongs to a goal
    task_ref: str | None = None             # title fragment referencing an existing task
    missing: list = field(default_factory=list)    # human-readable unknowns
    confidence: float = 0.0

    def to_dict(self):
        return asdict(self)


@dataclass
class ExtractionResult:
    """Full structured understanding of one user request."""
    intent: str = "unknown"
    tasks: list = field(default_factory=list)       # list[ExtractedTask]
    question: str | None = None             # concise follow-up when ambiguous
    query_action: str | None = None         # e.g. "stats", "next_class"
    reply: str | None = None                # chat reply when intent == "chat"
    goal: dict | None = None                # {"title", "description", "target_date"}
    blocks: list = field(default_factory=list)  # [{"title","days","date","start","end"}]
    available_minutes: int | None = None    # "I have three hours free" capacity hint
    source: str = "local"                   # "local" | "llm"
    warnings: list = field(default_factory=list)

    def to_dict(self):
        return {
            "intent": self.intent,
            "tasks": [t.to_dict() for t in self.tasks],
            "question": self.question,
            "query_action": self.query_action,
            "reply": self.reply,
            "goal": self.goal,
            "blocks": list(self.blocks),
            "available_minutes": self.available_minutes,
            "source": self.source,
            "warnings": list(self.warnings),
        }


@dataclass
class ToolCall:
    """A proposed action from the model or the deterministic parser."""
    tool: str
    args: dict = field(default_factory=dict)
    call_id: str | None = None              # idempotency key (set by controller)
    source: str = "llm"                     # "llm" | "local"

    def to_dict(self):
        return {"tool": self.tool, "args": self.args, "call_id": self.call_id,
                "source": self.source}


@dataclass
class ToolResult:
    """Explicit result of a validated tool execution."""
    ok: bool
    tool: str
    message: str = ""
    data: dict | None = None
    error: str | None = None
    confirmed: bool = False                 # did the user approve it?

    def to_dict(self):
        return {"ok": self.ok, "tool": self.tool, "message": self.message,
                "data": self.data, "error": self.error, "confirmed": self.confirmed}


# ==================== VALIDATION ====================

def clean_str(value, max_len=300):
    """Sanitize a model/user string: strip control chars, bound length."""
    if value is None:
        return None
    text = str(value)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = text.strip()
    if not text:
        return None
    return text[:max_len]


def valid_date(value):
    """Validate YYYY-MM-DD; returns normalized value or None."""
    from datetime import date as _date
    if not isinstance(value, str) or not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return None
    try:
        _date.fromisoformat(value)
        return value
    except ValueError:
        return None


def valid_hhmm(value):
    """Validate HH:MM; returns normalized value or None."""
    if not isinstance(value, str):
        return None
    m = re.match(r"^(\d{1,2}):(\d{2})$", value.strip())
    if not m:
        return None
    h, mn = int(m.group(1)), int(m.group(2))
    if 0 <= h < 24 and 0 <= mn < 60:
        return f"{h:02}:{mn:02}"
    return None


def valid_int(value, lo=None, hi=None):
    """Best-effort int coercion with bounds; None when invalid/out of range."""
    if value is None or isinstance(value, bool):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    if lo is not None and n < lo:
        return None
    if hi is not None and n > hi:
        return None
    return n


def validate_extracted_task(raw):
    """Coerce a raw dict (from LLM or parser) into a safe ExtractedTask.

    Invalid fields become None with a warning instead of raising, so one bad
    field never discards an otherwise valid task.
    """
    warnings = []
    t = ExtractedTask()
    if not isinstance(raw, dict):
        return t, ["extraction: expected object, got non-object"]

    t.title = clean_str(raw.get("title"), 200)
    t.task_ref = clean_str(raw.get("task_ref"), 200)
    if not t.title:
        t.title = None
        if not t.task_ref:
            # ref-style intents (complete/delete/move) carry task_ref, not title
            warnings.append("task missing title")
    t.description = clean_str(raw.get("description"), 1000)
    t.subject = clean_str(raw.get("subject"), 120)
    t.due_date = valid_date(raw.get("due_date"))
    if raw.get("due_date") and not t.due_date:
        warnings.append(f"invalid due_date {raw.get('due_date')!r} ignored")
    t.due_time = valid_hhmm(raw.get("due_time"))
    if raw.get("due_time") and not t.due_time:
        warnings.append(f"invalid due_time {raw.get('due_time')!r} ignored")
    t.estimated_minutes = valid_int(raw.get("estimated_minutes"), 5, 16 * 60)
    if raw.get("estimated_minutes") and not t.estimated_minutes:
        warnings.append("invalid estimated_minutes ignored")
    t.importance = valid_int(raw.get("importance"), *IMPORTANCE_RANGE)
    t.difficulty = valid_int(raw.get("difficulty"), *DIFFICULTY_RANGE)
    t.priority_hint = valid_int(raw.get("priority_hint"), 0, 100)
    t.confidence = min(1.0, max(0.0, float(raw.get("confidence") or 0.5)))

    subs = raw.get("subtasks")
    if isinstance(subs, list):
        t.subtasks = [s for s in (clean_str(x, 200) for x in subs) if s][:20]

    rec = raw.get("recurrence")
    if isinstance(rec, dict) and rec.get("type") in ("daily", "weekly"):
        t.recurrence = {"type": rec["type"]}
        days = rec.get("days")
        if rec["type"] == "weekly" and isinstance(days, list):
            valid_days = {d for d in days if d in
                          ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
            t.recurrence["days"] = sorted(valid_days)

    t.goal_title = clean_str(raw.get("goal_title"), 200)

    missing = []
    if not t.due_date:
        missing.append("due date")
    if not t.estimated_minutes:
        missing.append("estimated duration")
    t.missing = missing
    return t, warnings


def validate_tool_args(spec, args):
    """Validate args against a ToolSpec schema.

    Schema field types: "str", "int", "float", "bool", "date", "hhmm",
    "str_list", "any". Returns (clean_args, errors_list).
    """
    errors, clean = [], {}
    args = args if isinstance(args, dict) else {}
    for key, rule in spec.schema.items():
        ftype = rule.get("type", "str")
        required = rule.get("required", False)
        value = args.get(key)
        if value is None:
            default = rule.get("default")
            if required:
                errors.append(f"{key} is required")
            elif default is not None:
                clean[key] = default
            continue
        if ftype == "str":
            v = clean_str(value, rule.get("max", 500))
            if v is None:
                if required:
                    errors.append(f"{key} must be a non-empty string")
            else:
                clean[key] = v
        elif ftype == "int":
            v = valid_int(value, rule.get("min"), rule.get("max"))
            if v is None:
                errors.append(f"{key} must be an integer" +
                              (f" in [{rule.get('min')}, {rule.get('max')}]" if rule.get("min") is not None else ""))
            else:
                clean[key] = v
        elif ftype == "float":
            try:
                fv = float(value)
                clean[key] = fv
            except (TypeError, ValueError):
                errors.append(f"{key} must be a number")
        elif ftype == "bool":
            clean[key] = bool(value)
        elif ftype == "date":
            v = valid_date(value)
            if v is None:
                errors.append(f"{key} must be YYYY-MM-DD")
            else:
                clean[key] = v
        elif ftype == "hhmm":
            v = valid_hhmm(value)
            if v is None:
                errors.append(f"{key} must be HH:MM (24h)")
            else:
                clean[key] = v
        elif ftype == "str_list":
            if isinstance(value, list):
                items = [s for s in (clean_str(v, 200) for v in value) if s]
                clean[key] = items
            else:
                errors.append(f"{key} must be a list of strings")
        elif ftype == "any":
            clean[key] = value
    # reject unexpected keys entirely (defense against schema abuse)
    for key in args:
        if key not in spec.schema:
            errors.append(f"unknown argument {key!r} not allowed")
    return clean, errors
