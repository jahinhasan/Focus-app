# ==================== TOOLS PACKAGE ====================
# Importing this package registers every agent tool. The shell API
# (ToolSpec/REGISTRY/tool/execute_tool/list_tools) is re-exported from base so
# `from focus_agent import tools` keeps working for the controller, tests, and
# any code written against the flat tools.py era.

from focus_agent.tools.base import (  # noqa: F401
    ToolSpec, REGISTRY, tool, register_alias, list_tools, execute_tool,
    find_task_fuzzy, subject_names, match_or_none,
)

# handler modules - importing them registers their tools
from focus_agent.tools import tasks as _tasks            # noqa: F401,E402
from focus_agent.tools import subjects as _subjects      # noqa: F401,E402
from focus_agent.tools import schedule as _schedule      # noqa: F401,E402
from focus_agent.tools import goals as _goals            # noqa: F401,E402
from focus_agent.tools import analytics as _analytics    # noqa: F401,E402

# Spec-naming aliases (kept alongside originals for one release; D5 in the plan)
register_alias("get_class_routine", "get_routine",
               "Read the weekly class routine (alias of get_routine).")
register_alias("assign_task_subject", "assign_subject",
               "Attach a task to a subject (alias of assign_subject).")
register_alias("get_goals", "list_goals",
               "List goals with progress (alias of list_goals).")
register_alias("get_available_slots", "get_availability",
               "Read free/busy intervals for a date (alias of get_availability).")
register_alias("get_productivity_statistics", "get_analytics",
               "Productivity analytics (alias of get_analytics).")


def tools_by_category():
    """Registry grouped for docs/UI (categories follow ARCHITECTURE.md §3)."""
    cats = {
        "task": ["create_task", "get_task", "list_tasks", "search_tasks",
                 "update_task", "complete_task", "reopen_task", "delete_task",
                 "add_subtask", "decompose_task"],
        "subject_routine": ["create_subject", "update_subject", "list_subjects",
                            "detect_task_subject", "assign_subject",
                            "assign_task_subject", "get_routine",
                            "get_class_routine", "add_class"],
        "schedule": ["get_availability", "get_available_slots",
                     "generate_daily_plan", "reschedule_day",
                     "explain_priorities"],
        "goal": ["create_goal", "update_goal", "list_goals", "get_goals",
                 "add_milestone", "decompose_goal", "complete_milestone",
                 "track_goal_progress"],
        "analytics": ["get_focus_history", "get_analytics",
                      "get_productivity_statistics", "record_focus_time",
                      "estimate_task_duration", "generate_report"],
    }
    out = {}
    for cat, names in cats.items():
        out[cat] = [n for n in names if n in REGISTRY]
    return out


__all__ = ["ToolSpec", "REGISTRY", "tool", "register_alias", "list_tools",
           "execute_tool", "tools_by_category", "find_task_fuzzy",
           "subject_names", "match_or_none"]
