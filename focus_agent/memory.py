# ==================== MEMORY.PY ====================
# Persistent agent memory: tool audit log, plan history, idempotency cache.
# Stored inside data["agent_memory"] (schema v3) - one JSON store, atomic saves.
# The LLM never writes here directly; only validated tool execution does.

import time

from logic import save_data

TOOL_LOG_CAP = 500
PLAN_LOG_CAP = 200
CALL_CACHE_CAP = 300


def _mem(data):
    return data.setdefault("agent_memory", {})


def log_tool_execution(data, call_id, tool, args, result_ok, summary):
    """Append one audit entry (bounded). Contains no secrets by construction."""
    mem = _mem(data)
    log = mem.setdefault("tool_log", [])
    log.append({
        "ts": int(time.time()),
        "call_id": call_id,
        "tool": tool,
        "args": args if isinstance(args, dict) else {},
        "ok": bool(result_ok),
        "summary": str(summary)[:300],
    })
    if len(log) > TOOL_LOG_CAP:
        mem["tool_log"] = log[-TOOL_LOG_CAP:]
    save_data(data)


def log_plan(data, plan_dict):
    """Store a generated plan (bounded) for history/adherence analytics."""
    mem = _mem(data)
    log = mem.setdefault("plan_log", [])
    log.append({"ts": int(time.time()), "plan": plan_dict})
    if len(log) > PLAN_LOG_CAP:
        mem["plan_log"] = log[-PLAN_LOG_CAP:]
    save_data(data)


def remember_call(data, call_id):
    """Mark a call id as executed. Returns False if already known (dupe retry)."""
    mem = _mem(data)
    cache = mem.setdefault("executed_calls", [])
    if call_id in cache:
        return False
    cache.append(call_id)
    if len(cache) > CALL_CACHE_CAP:
        mem["executed_calls"] = cache[-CALL_CACHE_CAP:]
    return True


def forget_call(data, call_id):
    """Remove a call id after a failed/rolled-back execution."""
    mem = _mem(data)
    cache = mem.get("executed_calls", [])
    if call_id in cache:
        cache.remove(call_id)
        save_data(data)


def get_recent_activity(data, limit=20):
    entries = _mem(data).get("tool_log", [])[-limit:]
    return list(reversed(entries))
