# ==================== TOOLS/BASE.PY ====================
# Validated agent tool registry shell - the ONLY way model-proposed actions
# touch data. Handlers live in the sibling modules (tasks, subjects, schedule,
# goals, analytics); this module owns registration, validation, permissions,
# confirmation, idempotency and audit logging.

from dataclasses import dataclass, replace

from logic import (
    add_task_logic, delete_task_logic, update_task_logic, complete_task_logic,
    reopen_task_logic, record_actual_duration, get_task_by_id, add_subtask,
    add_subject, add_xp, get_today_focus_stats, get_analytics_data,
)
from focus_agent import dates as fdates
from focus_agent import subjects as fsubjects
from focus_agent import memory as fmemory
from focus_agent.schemas import ToolResult, validate_tool_args, clean_str


@dataclass
class ToolSpec:
    name: str
    description: str
    schema: dict                       # field -> {type, required, ...}
    permission: str = "read"           # read | write | destructive
    requires_confirmation: bool = False
    confirm_fn: object = None          # callable(data, args) -> (bool, reason)
    handler: object = None


REGISTRY = {}


def tool(name, description, schema, permission="read", requires_confirmation=False,
         confirm_fn=None):
    def deco(fn):
        REGISTRY[name] = ToolSpec(
            name=name, description=description, schema=schema,
            permission=permission, requires_confirmation=requires_confirmation,
            confirm_fn=confirm_fn, handler=fn)
        return fn
    return deco


def register_alias(alias, target, description=None):
    """Expose an existing tool under a second name (spec-naming migration)."""
    spec = REGISTRY.get(target)
    if spec is None:
        raise ValueError(f"cannot alias unknown tool {target!r}")
    REGISTRY[alias] = replace(spec, name=alias,
                              description=description or spec.description)


def list_tools():
    """Tool catalog for prompts and docs (sorted, bounded)."""
    return [{"name": s.name, "description": s.description, "schema": s.schema,
             "permission": s.permission,
             "requires_confirmation": s.requires_confirmation}
            for s in (REGISTRY[k] for k in sorted(REGISTRY))]


def execute_tool(data, call, ctx=None, confirm_callback=None):
    """Validate + execute one ToolCall. Never raises; returns ToolResult.

    - ctx: dict with at least {'settings', 'now'} (timezone-aware now).
    - confirm_callback(question) -> bool: invoked for confirmation-required tools.
    - Idempotency: repeated call_id within the session returns the cached
      outcome instead of executing twice.
    """
    ctx = ctx or {}
    settings = ctx.get("settings") or (data.get("settings") or {})
    spec = REGISTRY.get(call.tool)
    if spec is None:
        return ToolResult(False, call.tool, error=f"Unknown tool '{call.tool}'")

    # Idempotency guard (retry protection)
    if call.call_id and not fmemory.remember_call(data, call.call_id):
        return ToolResult(True, call.tool,
                          message="Already executed (duplicate request ignored).",
                          data={"duplicate": True})

    args, errors = validate_tool_args(spec, call.args)
    if errors:
        fmemory.forget_call(data, call.call_id) if call.call_id else None
        return ToolResult(False, call.tool,
                          error="Invalid arguments: " + "; ".join(errors[:5]))

    confirmed = False
    if spec.requires_confirmation:
        reason = ""
        if spec.confirm_fn is not None:
            allowed, reason = spec.confirm_fn(data, args)
            if not allowed:
                if call.call_id:
                    fmemory.forget_call(data, call.call_id)
                return ToolResult(False, call.tool,
                                  error=f"Not allowed: {reason}")
        question = reason or f"Allow '{spec.name}' with {args}?"
        if confirm_callback is None:
            if call.call_id:
                fmemory.forget_call(data, call.call_id)
            return ToolResult(False, call.tool,
                              error="Confirmation required but no UI available - ask the user first.",
                              data={"needs_confirmation": True, "question": question})
        confirmed = bool(confirm_callback(question))
        if not confirmed:
            if call.call_id:
                fmemory.forget_call(data, call.call_id)
            return ToolResult(False, call.tool, message="User declined this action.",
                              data={"declined": True}, confirmed=False)

    try:
        result = spec.handler(data, args, {"settings": settings, "now": ctx.get("now")})
    except Exception as e:  # bounded: any handler crash becomes a ToolResult
        if call.call_id:
            fmemory.forget_call(data, call.call_id)
        return ToolResult(False, call.tool,
                          error=f"Tool failed: {e.__class__.__name__}")
    result.confirmed = confirmed
    if call.call_id:
        fmemory.log_tool_execution(data, call.call_id, call.tool, args,
                                   result.ok, result.message or result.error or "")
    return result


# ==================== SHARED HELPERS ====================

def find_task_fuzzy(data, ref):
    """Find a task by exact id, then substring title match (best effort)."""
    from focus_agent.repository import TaskRepository
    if not ref:
        return None
    return TaskRepository(data).find_fuzzy(ref)


def subject_names(data):
    return list(fsubjects.get_known_subjects(data).keys())


def match_or_none(data, mention):
    if not mention:
        return None, None
    m = fsubjects.match_subject(mention, data)
    if m and m["auto"]:
        return m["subject"], m
    return None, m
