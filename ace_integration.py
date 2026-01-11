# ==================== ACE_INTEGRATION.PY ====================
# Optional self-learning layer for Focus Dashboard
# Provides a persistent "skillbook" and lightweight learning hooks.
# Designed to work even if external ACE framework is not installed.

import os
import json
import time
from typing import Any, Dict, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLBOOK_FILE = os.path.join(BASE_DIR, "skillbook.json")


def _default_skillbook() -> Dict[str, Any]:
    return {
        "version": 1,
        "stats": {
            "queries": {
                "chat": 0,
                "task": 0,
                "class": 0,
                "schedule_file": 0,
            }
        },
        "patterns": {
            "days": {},          # e.g., {"mon": 12, "wed": 9}
            "time_ranges": {},   # e.g., {"10:00-11:00": 5}
            "titles": {},        # e.g., {"Physics": 3}
        },
        "history": []            # recent interactions (capped)
    }


def load_skillbook() -> Dict[str, Any]:
    if not os.path.exists(SKILLBOOK_FILE):
        return _default_skillbook()
    try:
        with open(SKILLBOOK_FILE, "r") as f:
            data = json.load(f)
            # Basic migration safety
            data.setdefault("version", 1)
            data.setdefault("stats", {}).setdefault("queries", {})
            data.setdefault("patterns", {}).setdefault("days", {})
            data.setdefault("patterns", {}).setdefault("time_ranges", {})
            data.setdefault("patterns", {}).setdefault("titles", {})
            data.setdefault("history", [])
            return data
    except Exception:
        return _default_skillbook()


def save_skillbook(book: Dict[str, Any]) -> None:
    try:
        with open(SKILLBOOK_FILE, "w") as f:
            json.dump(book, f, indent=2)
    except Exception:
        pass


def record_query(intent: str, payload: Dict[str, Any] | None = None) -> None:
    """Record a query/intent occurrence to the skillbook."""
    book = load_skillbook()
    q = book.setdefault("stats", {}).setdefault("queries", {})
    q[intent] = q.get(intent, 0) + 1

    # Append recent history (capped to 500 entries)
    book.setdefault("history", []).append({
        "ts": int(time.time()),
        "intent": intent,
        "payload": payload or {}
    })
    if len(book["history"]) > 500:
        book["history"] = book["history"][-500:]

    save_skillbook(book)


def learn_schedule_patterns(classes: List[Dict[str, Any]] | None) -> None:
    """Update learned patterns from parsed class objects."""
    if not classes:
        return
    book = load_skillbook()
    days_map = book.setdefault("patterns", {}).setdefault("days", {})
    time_map = book.setdefault("patterns", {}).setdefault("time_ranges", {})
    titles_map = book.setdefault("patterns", {}).setdefault("titles", {})

    for c in classes:
        # Days
        for d in (c.get("days") or []):
            if not isinstance(d, str):
                continue
            days_map[d] = days_map.get(d, 0) + 1
        # Time ranges
        start = c.get("start")
        end = c.get("end")
        if isinstance(start, str) and isinstance(end, str) and start and end:
            key = f"{start}-{end}"
            time_map[key] = time_map.get(key, 0) + 1
        # Titles
        title = (c.get("title") or "").strip()
        if title:
            titles_map[title] = titles_map.get(title, 0) + 1

    save_skillbook(book)


def get_top_patterns(limit: int = 3) -> Dict[str, list]:
    """Return top-k learned patterns for UI or agent hints."""
    book = load_skillbook()
    patt = book.get("patterns", {})

    def top_items(d: Dict[str, int]) -> list:
        return sorted(d.items(), key=lambda x: x[1], reverse=True)[:limit]

    return {
        "days": top_items(patt.get("days", {})),
        "time_ranges": top_items(patt.get("time_ranges", {})),
        "titles": top_items(patt.get("titles", {})),
    }

# Placeholder for future ACE agent wiring. Kept noop to avoid hard dependency.
class ACEAgent:
    def __init__(self) -> None:
        self.enabled = False
        # Future: attempt dynamic import and initialization
        try:
            # Example (commented):
            # import ace
            # self.enabled = True
            # self.agent = ace.Agent(...)
            pass
        except Exception:
            self.enabled = False

    def observe(self, event: str, payload: Dict[str, Any] | None = None) -> None:
        # Future: forward events to ACE agent if enabled
        record_query(event, payload or {})

    def learn_from_classes(self, classes: List[Dict[str, Any]] | None) -> None:
        learn_schedule_patterns(classes)

# Singleton-ish helper
ace_agent = ACEAgent()