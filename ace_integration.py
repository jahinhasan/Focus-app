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



def record_query(intent: str, payload: Dict[str, Any] | None = None, query_text: str = None, response_data: Any = None) -> None:
    """Record a query/intent occurrence and cache the interaction for offline recall."""
    book = load_skillbook()
    q = book.setdefault("stats", {}).setdefault("queries", {})
    q[intent] = q.get(intent, 0) + 1

    # Append recent history (capped to 500 entries)
    entry = {
        "ts": int(time.time()),
        "intent": intent,
        "payload": payload or {},
        "query_text": query_text,
        "response_data": response_data
    }
    
    # Store full interaction for offline learning if both input/output exist
    if query_text and response_data:
        interactions = book.setdefault("interactions", [])
        interactions.append(entry)
        if len(interactions) > 1000: # Cap knowledge base
            book["interactions"] = interactions[-1000:]

    history = book.setdefault("history", [])
    history.append(entry)
    if len(history) > 500:
        book["history"] = history[-500:]

    save_skillbook(book)


def find_similar_interaction(query_text: str, threshold: float = 0.6) -> Dict[str, Any] | None:
    """Find the most similar past interaction for offline recall."""
    if not query_text: return None
    
    book = load_skillbook()
    interactions = book.get("interactions", [])
    if not interactions: return None

    from difflib import SequenceMatcher
    
    best_score = 0.0
    best_match = None
    
    query_lower = query_text.lower()

    for entry in interactions:
        past_query = entry.get("query_text")
        if not past_query: continue
        
        score = SequenceMatcher(None, query_lower, past_query.lower()).ratio()
        if score > best_score:
            best_score = score
            best_match = entry

    if best_score >= threshold:
        return {
            "intent": best_match.get("intent", "chat"),
            "message": best_match.get("response_data", {}).get("message", "I recall this..."),
            "data": best_match.get("response_data", {}),
            "offline_score": best_score
        }
    
    return None


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