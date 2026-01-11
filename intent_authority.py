"""
intent_authority.py

Minimal 4-layer intent authority implementation to satisfy
the IMPLEMENTATION_TODO.md requirements. Provides a safe,
deterministic-first pipeline with advisory AI suggestions,
clarification handling, and action execution hooks.
"""
from typing import List, Dict, Any, Optional
import re
import json
import os

from ai_parser import SmartParser
from logic import load_data, add_task_logic, add_class_task, validate_class_input, save_data

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PENDING_FILE = os.path.join(BASE_DIR, "pending_intents.json")


class IntentDetectionLayer:
    """Deterministic detection using regex/heuristics."""

    QUERY_PATTERNS = [r"^(what|when|how|why|where|whose|which|who)\s",
                      r"^(show|tell|list|get)\s"]

    def detect(self, text: str) -> List[Dict[str, Any]]:
        lower = text.strip().lower()
        candidates = []

        # Query detection (high confidence)
        if any(re.search(p, lower) for p in self.QUERY_PATTERNS):
            candidates.append({"intent": "query", "confidence": 0.95, "source": "deterministic"})

        # Class detection: look for day names + time ranges
        if re.search(r"\b(mon(day)?|tue(sday)?|wed(nesday)?|thu(rsday)?|fri(day)?|sat(urday)?|sun(day)?)\b", lower) and re.search(r"\d{1,2}(:\d{2})?\s*[-–to]+\s*\d{1,2}(:\d{2})?", lower):
            candidates.append({"intent": "class", "confidence": 0.9, "source": "deterministic"})

        # Task detection: keywords
        if any(k in lower for k in ["task", "assignment", "homework", "due"]) or lower.startswith("add "):
            candidates.append({"intent": "task", "confidence": 0.85, "source": "deterministic"})

        return candidates


class AIIntentSuggestionLayer:
    """Advisory AI suggestions using SmartParser. Non-authoritative."""

    def __init__(self):
        self.parser = SmartParser()

    def suggest(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            ai = self.parser.parse(text)
            if ai and isinstance(ai, dict):
                # Assign a modest confidence for AI suggestion
                ai_candidate = ai.copy()
                ai_candidate.setdefault("confidence", 0.7)
                ai_candidate.setdefault("source", "ai")
                return ai_candidate
        except Exception:
            pass
        return None


class IntentAuthorityLayer:
    """Combine deterministic candidates and AI suggestions, enforce rules, and decide.
    Returns a dict with final decision or a clarification request.
    """

    LOW_CONF_THRESHOLD = 0.6

    def __init__(self):
        self.detector = IntentDetectionLayer()
        self.ai = AIIntentSuggestionLayer()

    def resolve(self, text: str) -> Dict[str, Any]:
        det = self.detector.detect(text)
        ai_sugg = self.ai.suggest(text)

        # Prefer deterministic high-confidence query detection
        for c in det:
            if c["intent"] == "query" and c["confidence"] >= 0.9:
                return {"intent": "query", "source": "deterministic", "confidence": c["confidence"]}

        # Merge candidates, use AI if deterministic is absent
        candidates = det.copy()
        if ai_sugg:
            candidates.append(ai_sugg)

        # Sort by confidence
        candidates.sort(key=lambda x: x.get("confidence", 0.0), reverse=True)

        if not candidates:
            # No hint - ask for clarification
            return {"clarify": True, "question": "What would you like me to do? (add task, add class, or ask a question)"}

        top = candidates[0]
        intent = top.get("intent")
        conf = top.get("confidence", 0.0)

        # Hard rules enforcement
        if intent == "query":
            return {"intent": "query", "source": top.get("source", "ai"), "confidence": conf}

        # If low confidence, ask clarification
        if conf < self.LOW_CONF_THRESHOLD:
            return {"clarify": True, "question": "I need a bit more detail to proceed. Could you rephrase or provide specifics?", "candidates": candidates}

        # If class intent but missing schedule details, ask clarification
        if intent == "class":
            # Try to get structured class info from AI suggestion if available
            if ai_sugg and ai_sugg.get("intent") == "class":
                cls = ai_sugg
            else:
                # No structured info: ask for days/time
                return {"clarify": True, "question": "What days and time is this class? (e.g. 'Mon Wed 10-11')"}

            days = cls.get("days") or cls.get("schedule", {}).get("days")
            start = cls.get("start") or cls.get("schedule", {}).get("start")
            end = cls.get("end") or cls.get("schedule", {}).get("end")

            if not (days and start and end):
                return {"clarify": True, "question": "I need the days and start/end times to add the class. Example: 'Mon Wed 10-11'", "candidates": candidates}

            # Validate via logic.validate_class_input
            ok, err = validate_class_input(cls.get("title", "Class"), cls.get("subject", cls.get("title", "Class")), days, start, end)
            if not ok:
                return {"clarify": True, "question": f"Class data seems invalid: {err}. Please correct."}

            return {"intent": "class", "data": {"title": cls.get("title", "Class"), "subject": cls.get("subject"), "days": days, "start": start, "end": end}, "confidence": conf}

        # Task intent: ensure title exists
        if intent == "task":
            if ai_sugg and ai_sugg.get("intent") == "task":
                task = ai_sugg
            else:
                # Best-effort local parse: take text as title
                task = {"title": text}

            title = task.get("title") or task.get("message")
            if not title or len(title.strip()) < 2:
                return {"clarify": True, "question": "What's the task title?"}

            return {"intent": "task", "data": {"title": title.strip(), "date": task.get("date")}, "confidence": conf}

        # Fallback
        return {"clarify": True, "question": "I didn't understand. Could you clarify?", "candidates": candidates}


class ActionExecutionLayer:
    """Execute safe actions (mutations) when authority layer approves."""

    def __init__(self):
        self.data = load_data()

    def execute(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        if decision.get("intent") == "query":
            # Queries do not modify data; return a placeholder response
            return {"status": "ok", "result": {"intent": "query", "message": "Handled as query. Use UI to display results."}}

        if decision.get("intent") == "class":
            d = decision.get("data", {})
            added = add_class_task(self.data, title=d.get("title"), subject=d.get("subject"), days=d.get("days"), start_time=d.get("start"), end_time=d.get("end"))
            if added:
                return {"status": "ok", "result": {"intent": "class", "added": True, "task": added}}
            return {"status": "error", "error": "Failed to add class"}

        if decision.get("intent") == "task":
            d = decision.get("data", {})
            added = add_task_logic(self.data, title=d.get("title"), category="task", deadline=d.get("date"))
            if added:
                return {"status": "ok", "result": {"intent": "task", "added": True, "task": added}}
            return {"status": "error", "error": "Failed to add task"}

        return {"status": "error", "error": "Unknown intent"}


# --- Persistence for pending intents ---
def save_pending(pending: Dict[str, Any]):
    try:
        with open(PENDING_FILE, "w") as f:
            json.dump(pending, f, indent=2)
    except Exception:
        pass


def load_pending() -> Dict[str, Any]:
    if not os.path.exists(PENDING_FILE):
        return {}
    try:
        with open(PENDING_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


# --- Public API ---
def process_text(text: str) -> Dict[str, Any]:
    """Process user input through the 4-layer pipeline.

    Returns a dict. If clarification is needed, contains `clarify: True` and `question`.
    If decision made and execution performed, returns execution result.
    """
    authority = IntentAuthorityLayer()

    # Support both older 'resolve' API and newer 'process' API
    if hasattr(authority, "resolve"):
        # old style
        decision = authority.resolve(text)

        if decision.get("clarify"):
            # Save as pending candidate for later reference
            pending = load_pending()
            pending_entry = {"text": text, "candidates": decision.get("candidates"), "question": decision.get("question")}
            pending[text] = pending_entry
            save_pending(pending)
            return {"clarify": True, "question": decision.get("question"), "pending": pending_entry}

        # Execute approved decision using current ActionExecutionLayer
        exec_layer = ActionExecutionLayer()
        result = exec_layer.execute(decision)
        return {"clarify": False, "decision": decision, "execution": result}

    elif hasattr(authority, "process"):
        # new style
        proc = authority.process(text)

        action = proc.get("action")
        if action == "clarify":
            # Persist pending via session-less key
            pending = load_pending()
            pending_entry = {"text": text, "question": proc.get("question"), "options": proc.get("options", [])}
            pending[text] = pending_entry
            save_pending(pending)
            return {"clarify": True, "question": proc.get("question"), "pending": pending_entry}

        elif action == "respond":
            return {"clarify": False, "decision": {"intent": "query"}, "execution": {"status": "ok", "result": {"intent": "query", "message": proc.get("message")}}}

        elif action == "execute":
            # proc['intent'] is an IntentCandidate dataclass
            exec_layer = ActionExecutionLayer()
            try:
                msg = exec_layer.execute(proc.get("intent"))
                return {"clarify": False, "decision": {"intent": proc.get("intent")}, "execution": {"status": "ok", "result": {"message": msg}}}
            except Exception as e:
                return {"clarify": False, "decision": {"intent": proc.get("intent")}, "execution": {"status": "error", "error": str(e)}}

        else:
            return {"clarify": False, "decision": {}, "execution": {"status": "error", "error": "Unknown action"}}

    else:
        return {"clarify": True, "question": "Internal error: no authority method available."}
# ==================== INTENT_AUTHORITY.PY ====================
# Intent-safe, deterministic AI assistant architecture for Focus Dashboard
# 4-layer system: Detection → Suggestion → Authority → Execution

import re
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from logic import (
    add_task_logic, save_routine_from_parser, 
    add_xp, load_data, save_data
)
from ace_integration import record_query, learn_schedule_patterns


# ==================== ENUMS & DATACLASSES ====================
class IntentType(Enum):
    QUERY = "query"       # Questions about schedule/stats (NEVER mutates)
    TASK = "task"         # Add a task (requires title)
    CLASS = "class"       # Add a class (requires days + start + end)
    CHAT = "chat"         # Casual conversation
    SCHEDULE_FILE = "schedule_file"  # Parsing uploaded files


@dataclass
class IntentCandidate:
    """Represents a potential intent with confidence and metadata."""
    intent_type: IntentType
    confidence: float  # 0.0 - 1.0
    extracted_fields: Dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"  # "regex", "ai", "heuristic"
    reason: str = ""
    needs_clarification: bool = False
    clarification_question: str = ""
    options: List[str] = field(default_factory=list)


@dataclass
class PendingIntent:
    """Stores an intent awaiting user clarification."""
    original_text: str
    candidates: List[IntentCandidate]
    timestamp: datetime
    clarification_asked: str
    options: List[str]


# ==================== STORAGE ====================
PENDING_INTENTS: Dict[str, PendingIntent] = {}  # session_id -> PendingIntent


# ==================== LAYER 1: INTENT DETECTION (CHEAP, FAST, STRICT) ====================
class IntentDetectionLayer:
    """
    Layer 1: Deterministic intent detection using regex and heuristics.
    Never performs actions. Generates intent candidates with structural signals.
    """
    
    # Question patterns - if matched, CANNOT be task or class
    QUERY_PATTERNS = [
        r"^(what|when|how|why|where|whose|which|who)\s",
        r"^(show|tell|list|get)\s",
        r"\?$",  # Ends with question mark
        r"^(is|are|can|could|would)\s",
    ]
    
    # Query keywords mapping to actions
    QUERY_KEYWORDS = {
        "xp": "xp",
        "level": "xp",
        "exp": "xp",
        "progress": "stats",
        "next class": "next_class",
        "next class is": "next_class",
        "class today": "today_tasks",
        "schedule": "today_tasks",
        "what do i have": "today_tasks",
        "what's today": "today_tasks",
        "tasks today": "today_tasks",
        "week": "weekly_classes",
        "weekly": "weekly_classes",
        "this week": "weekly_classes",
        "classes this week": "weekly_classes",
        "stat": "stats",
        "stats": "stats",
        "performance": "stats",
        "productivity": "tips",
        "tip": "tips",
        "advice": "tips",
        "suggestion": "tips",
    }
    
    # Structural signals
    TIME_PATTERN = r"(\d{1,2}(?::\d{2})?)\s*-\s*(\d{1,2}(?::\d{2})?)"
    DAYS_PATTERN = r"\b(mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b"
    
    def detect(self, text: str) -> List[IntentCandidate]:
        """
        Generate intent candidates from text using deterministic rules.
        Returns list of candidates (usually 1-2, never 0).
        """
        candidates = []
        text_lower = text.lower().strip()
        
        # Check for questions FIRST - these are NEVER tasks/classes
        is_question = self._is_question(text_lower)
        
        if is_question:
            candidates.append(IntentCandidate(
                intent_type=IntentType.QUERY,
                confidence=1.0,  # Questions are 100% queries
                extracted_fields={"action": self._map_query_to_action(text_lower)},
                source="regex",
                reason="Text matches question pattern",
                needs_clarification=False
            ))
            return candidates
        
        # Check for class patterns (requires days + time)
        has_days = bool(re.search(self.DAYS_PATTERN, text_lower))
        has_time = bool(re.search(self.TIME_PATTERN, text_lower))
        
        if has_days and has_time:
            # Likely a class - but still need AI for confidence
            candidates.append(IntentCandidate(
                intent_type=IntentType.CLASS,
                confidence=0.7,  # Moderate confidence - needs AI verification
                extracted_fields=self._extract_structural_fields(text),
                source="heuristic",
                reason="Contains both days and time patterns",
                needs_clarification=False
            ))
        elif "class" in text_lower or "lecture" in text_lower:
            # Class keyword but missing details - needs clarification
            candidates.append(IntentCandidate(
                intent_type=IntentType.CLASS,
                confidence=0.5,
                extracted_fields={},
                source="heuristic",
                reason="Contains 'class' keyword but missing schedule details",
                needs_clarification=True,
                clarification_question="What days and time is this class?",
                options=["Mon Wed 10-11", "Tue Thu 14-16", "Daily 9-10"]
            ))
        else:
            # Default: could be task or casual chat
            candidates.append(IntentCandidate(
                intent_type=IntentType.TASK,
                confidence=0.6,
                extracted_fields={"title": self._extract_title(text)},
                source="heuristic",
                reason="No query or class patterns detected",
                needs_clarification=False
            ))
            
            # Also suggest chat as alternative
            candidates.append(IntentCandidate(
                intent_type=IntentType.CHAT,
                confidence=0.4,
                extracted_fields={},
                source="heuristic",
                reason="Could be casual conversation",
                needs_clarification=False
            ))
        
        return candidates
    
    def _is_question(self, text: str) -> bool:
        """Check if text is a question (never a task/class)."""
        return any(re.search(p, text) for p in self.QUERY_PATTERNS)
    
    def _map_query_to_action(self, text: str) -> str:
        """Map question text to query action."""
        for kw, action in self.QUERY_KEYWORDS.items():
            if kw in text:
                return action
        return "general"
    
    def _extract_structural_fields(self, text: str) -> Dict[str, Any]:
        """Extract structural fields like days and times."""
        days_map = {
            "mon": "mon", "monday": "mon", "tue": "tue", "tuesday": "tue",
            "wed": "wed", "wednesday": "wed", "thu": "thu", "thursday": "thu",
            "fri": "fri", "friday": "fri", "sat": "sat", "saturday": "sat",
            "sun": "sun", "sunday": "sun"
        }
        
        found_days = []
        for word in re.findall(r"\b\w+\b", text.lower()):
            if word in days_map:
                found_days.append(days_map[word])
        
        times = re.search(self.TIME_PATTERN, text)
        start, end = None, None
        if times:
            start, end = times.group(1), times.group(2)
            if ":" not in start:
                start = f"{int(start):02}:00"
            if ":" not in end:
                end = f"{int(end):02}:00"
        
        return {
            "days": list(set(found_days)),
            "start": start,
            "end": end
        }
    
    def _extract_title(self, text: str) -> str:
        """Extract task title from text."""
        # Remove common prefixes
        title = re.sub(
            r"^(task|add|create|new|please)\s+",
            "",
            text,
            flags=re.IGNORECASE
        )
        return title.strip()


# ==================== LAYER 2: AI INTENT SUGGESTION (ADVISORY ONLY) ====================
class AIIntentSuggestionLayer:
    """
    Layer 2: AI-powered intent suggestion (ADVISORY ONLY).
    Never mutates state. Returns structured JSON with confidence.
    """
    
    # Try to import Groq
    try:
        from groq import Groq
        api_key = __import__("os").environ.get("GROQ_API_KEY")
        client = Groq(api_key=api_key) if api_key else None
    except Exception:
        client = None
    
    SYSTEM_PROMPT = """You are a helpful assistant for Focus Dashboard (student productivity app).

## OUTPUT FORMAT
You MUST output valid JSON:
{
  "intent": "task|class|query|chat|schedule_file",
  "confidence": 0.0-1.0,
  "extracted_fields": {...},
  "reason": "short explanation"
}

## CRITICAL RULES
1. If text is a QUESTION → intent="query" (confidence=1.0)
   - "What do I have today?" → query
   - "How much XP do I have?" → query

2. If text is a COMMAND to ADD something:
   - "Add math homework" → task
   - "Physics class Mon Wed 10-11" → class

3. If unclear or ambiguous → confidence < 0.75, suggest clarification

4. NEVER claim high confidence (>0.85) if uncertain

## CONFIDENCE GUIDELINES
- 1.0 = Certain (clear question, obvious task)
- 0.85-0.99 = Very confident
- 0.70-0.84 = Moderately confident (needs human check)
- 0.50-0.69 = Uncertain (ask clarification)
- <0.50 = Very uncertain (fallback to chat)

## EXAMPLE OUTPUTS
Input: "What do I have today?"
{"intent": "query", "confidence": 1.0, "extracted_fields": {"action": "today_tasks"}, "reason": "Clear question about schedule"}

Input: "Add math homework"
{"intent": "task", "confidence": 0.9, "extracted_fields": {"title": "Math Homework"}, "reason": "Clear task command"}

Input: "I have a class EEE on January 11 at 17:26"
{"intent": "class", "confidence": 0.75, "extracted_fields": {"title": "EEE", "date": "2025-01-11", "start": "17:26"}, "reason": "Missing end time, possibly ambiguous"}

Input: "Hello"
{"intent": "chat", "confidence": 0.5, "extracted_fields": {}, "reason": "Greeting, not actionable"}
"""
    
    def suggest(self, text: str, context: Optional[Dict] = None) -> Optional[IntentCandidate]:
        """Get AI suggestion for intent."""
        if not self.client:
            return None
        
        try:
            completion = self.client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": text}
                ],
                temperature=0.1,  # Low temperature for consistency
                max_tokens=256,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(completion.choices[0].message.content)
            
            # Map string intent to enum
            intent_map = {
                "task": IntentType.TASK,
                "class": IntentType.CLASS,
                "query": IntentType.QUERY,
                "chat": IntentType.CHAT,
                "schedule_file": IntentType.SCHEDULE_FILE
            }
            
            intent_type = intent_map.get(result.get("intent", "chat"), IntentType.CHAT)
            
            return IntentCandidate(
                intent_type=intent_type,
                confidence=result.get("confidence", 0.5),
                extracted_fields=result.get("extracted_fields", {}),
                source="ai",
                reason=result.get("reason", "")
            )
            
        except Exception as e:
            print(f"AI Intent Suggestion Error: {e}")
            return None


# ==================== LAYER 3: INTENT AUTHORITY (MOST IMPORTANT) ====================
class IntentAuthorityLayer:
    """
    Layer 3: Intent Authority - DECIDES final action.
    Enforces invariants, prevents damage, asks clarification when needed.
    
    GUIDING PRINCIPLE: AI suggests, rules decide, users confirm, code executes.
    """
    
    # Confidence thresholds
    AUTO_EXECUTE_THRESHOLD = 0.85
    CLARIFY_THRESHOLD = 0.60
    
    def __init__(self):
        self.detection_layer = IntentDetectionLayer()
        self.ai_layer = AIIntentSuggestionLayer()
    
    def process(self, text: str, session_id: str = "default") -> Dict[str, Any]:
        """
        Main entry point. Process user text through all layers.
        Returns either:
        - {"action": "execute", "intent": ...} for confirmed actions
        - {"action": "clarify", "question": ..., "options": [...]} for clarifications
        - {"action": "respond", "message": ...} for queries/chat
        """
        global PENDING_INTENTS
        
        # Check for pending intent response
        if session_id in PENDING_INTENTS:
            pending = PENDING_INTENTS[session_id]
            # Check if this is a response to clarification
            if self._is_clarification_response(text, pending.options):
                return self._resolve_pending_intent(pending, text, session_id)
            else:
                # New input - clear old pending and process fresh
                del PENDING_INTENTS[session_id]
        
        # LAYER 1: Get deterministic detection candidates
        detection_candidates = self.detection_layer.detect(text)
        
        # LAYER 2: Get AI suggestion (advisory)
        ai_candidate = self.ai_layer.suggest(text)
        
        # Combine and analyze candidates
        candidates = detection_candidates.copy()
        if ai_candidate:
            candidates.append(ai_candidate)
        
        # Select best candidate
        best_candidate = self._select_best_candidate(candidates)
        
        # Validate candidate against hard rules
        validation = self._validate_candidate(best_candidate, text)
        
        if not validation["valid"]:
            # Rule violation - ask clarification
            return {
                "action": "clarify",
                "question": validation["reason"],
                "options": validation.get("options", [])
            }
        
        # Check confidence thresholds
        if best_candidate.confidence >= self.AUTO_EXECUTE_THRESHOLD:
            # High confidence - execute if safe
            if best_candidate.intent_type == IntentType.QUERY:
                return self._handle_query(best_candidate)
            elif best_candidate.intent_type in (IntentType.TASK, IntentType.CLASS):
                return {
                    "action": "execute",
                    "intent": best_candidate,
                    "needs_confirmation": best_candidate.confidence < 0.95
                }
            else:
                return {
                    "action": "respond",
                    "message": self._generate_chat_response(best_candidate)
                }
        
        elif best_candidate.confidence >= self.CLARIFY_THRESHOLD:
            # Medium confidence - ask clarification
            clarification = self._generate_clarification(best_candidate, text)
            if clarification:
                # Store pending intent
                PENDING_INTENTS[session_id] = PendingIntent(
                    original_text=text,
                    candidates=candidates,
                    timestamp=datetime.now(),
                    clarification_asked=clarification["question"],
                    options=clarification.get("options", [])
                )
                return {
                    "action": "clarify",
                    "question": clarification["question"],
                    "options": clarification.get("options", [])
                }
            else:
                # Fallback to safe response
                return self._handle_low_confidence(best_candidate)
        
        else:
            # Low confidence - fallback to chat/query
            return self._handle_low_confidence(best_candidate)
    
    def _select_best_candidate(self, candidates: List[IntentCandidate]) -> IntentCandidate:
        """Select the best candidate based on confidence and source priority."""
        if not candidates:
            return IntentCandidate(
                intent_type=IntentType.CHAT,
                confidence=0.5,
                extracted_fields={},
                source="default",
                reason="No candidates found"
            )
        
        # Sort by confidence, but prefer regex/heuristic for queries
        def candidate_score(c: IntentCandidate):
            base_score = c.confidence
            
            # Boost query detection (it's deterministic and safe)
            if c.intent_type == IntentType.QUERY and c.source in ("regex", "heuristic"):
                base_score += 0.2
            
            # Slightly prefer AI for complex extractions
            if c.source == "ai" and c.intent_type in (IntentType.TASK, IntentType.CLASS):
                base_score += 0.05
            
            return base_score
        
        return max(candidates, key=candidate_score)
    
    def _validate_candidate(self, candidate: IntentCandidate, text: str) -> Dict[str, Any]:
        """
        Validate candidate against hard rules.
        Returns {"valid": bool, "reason": str, "options": [...]}.
        """
        # HARD RULE: Queries never mutate data
        if candidate.intent_type == IntentType.QUERY:
            return {"valid": True}
        
        # HARD RULE: Tasks require meaningful title
        if candidate.intent_type == IntentType.TASK:
            title = candidate.extracted_fields.get("title", "").strip()
            if len(title) < 2:
                return {
                    "valid": False,
                    "reason": "I need a clearer task title. What exactly do you want to add?",
                    "options": ["Math homework", "Read chapter 5", "Prepare for exam"]
                }
            return {"valid": True}
        
        # HARD RULE: Classes require days + start + end
        if candidate.intent_type == IntentType.CLASS:
            fields = candidate.extracted_fields
            days = fields.get("days", [])
            start = fields.get("start")
            end = fields.get("end")
            
            missing = []
            if not days:
                missing.append("days")
            if not start:
                missing.append("start time")
            if not end:
                missing.append("end time")
            
            if missing:
                return {
                    "valid": False,
                    "reason": f"To add a class, I need: {', '.join(missing)}. Could you provide these details?",
                    "options": ["Mon Wed 10-11", "Tue Thu 14-16", "Daily 9-10"]
                }
            
            # Validate time format
            try:
                if start:
                    datetime.strptime(start, "%H:%M")
                if end:
                    datetime.strptime(end, "%H:%M")
            except ValueError:
                return {
                    "valid": False,
                    "reason": "Time format looks wrong. Please use HH:MM format (e.g., 10:00 or 14:30)",
                    "options": ["10:00-11:00", "14:30-16:00"]
                }
            
            return {"valid": True}
        
        return {"valid": True}
    
    def _generate_clarification(self, candidate: IntentCandidate, text: str) -> Optional[Dict]:
        """Generate clarification question for ambiguous input."""
        if candidate.needs_clarification:
            return {
                "question": candidate.clarification_question,
                "options": candidate.options
            }
        
        # Generate contextual clarification
        if candidate.confidence < 0.75:
            if candidate.intent_type == IntentType.TASK:
                return {
                    "question": "Would you like me to add this as a task, or was that just a note?",
                    "options": ["Add as task", "Just a note", "Help me phrase it"]
                }
            elif candidate.intent_type == IntentType.CLASS:
                return {
                    "question": "It looks like you're mentioning a class. Should I add it to your schedule?",
                    "options": ["Add to schedule", "Just info", "Ask for details"]
                }
        
        return None
    
    def _is_clarification_response(self, text: str, options: List[str]) -> bool:
        """Check if text responds to a clarification."""
        text_lower = text.lower()
        
        # Check for option keywords
        option_keywords = []
        for opt in options:
            opt_lower = opt.lower()
            option_keywords.extend(opt_lower.split()[:2])  # First 2 words
        
        return any(kw in text_lower for kw in option_keywords)
    
    def _resolve_pending_intent(self, pending: PendingIntent, response: str, session_id: str) -> Dict[str, Any]:
        """Resolve a pending intent based on user clarification response."""
        global PENDING_INTENTS
        
        response_lower = response.lower()
        
        # Map response to intended action
        if any(kw in response_lower for kw in ["add", "yes", "sure", "task"]):
            # User wants to add - pick highest confidence task/class candidate
            task_candidates = [c for c in pending.candidates 
                             if c.intent_type in (IntentType.TASK, IntentType.CLASS)]
            if task_candidates:
                best = max(task_candidates, key=lambda c: c.confidence)
                del PENDING_INTENTS[session_id]
                return {
                    "action": "execute",
                    "intent": best,
                    "needs_confirmation": True,
                    "clarification_response": response
                }
        
        if any(kw in response_lower for kw in ["no", "not", "cancel", "just"]):
            # User doesn't want to add - treat as chat/query
            del PENDING_INTENTS[session_id]
            return {
                "action": "respond",
                "message": "Got it! I'll leave your data as is. Is there anything else I can help with?"
            }
        
        # Unclear response - ask again
        return {
            "action": "clarify",
            "question": "I'm not sure what you mean. Could you clarify?",
            "options": ["Yes, add it", "No, cancel", "Just information"]
        }
    
    def _handle_query(self, candidate: IntentCandidate) -> Dict[str, Any]:
        """Handle query intent - never mutates, returns information."""
        action = candidate.extracted_fields.get("action", "general")
        
        if action == "xp":
            from ai_parser import get_user_context
            ctx = get_user_context()
            return {
                "action": "respond",
                "message": f"📊 **Your XP:**\n⭐ Level {ctx['level']}\n✨ {ctx['xp']} / {ctx['xp_needed']} XP ({ctx['progress_percent']}%)"
            }
        elif action == "next_class":
            from ai_parser import format_upcoming_classes
            return {"action": "respond", "message": format_upcoming_classes()}
        elif action == "today_tasks":
            from ai_parser import format_today_schedule
            return {"action": "respond", "message": format_today_schedule()}
        elif action == "weekly_classes":
            from logic import get_weekly_class_tasks
            weekly = get_weekly_class_tasks(load_data())
            lines = ["📚 **Weekly Classes:**"]
            for day, classes in weekly.items():
                if classes:
                    lines.append(f"\n**{day.upper()}:**")
                    for c in classes:
                        schedule = c.get("schedule", {})
                        lines.append(f"  • {c['title']}: {schedule.get('start','')}-{schedule.get('end','')}")
            return {"action": "respond", "message": "\n".join(lines)}
        elif action == "stats":
            from ai_parser import format_user_stats
            return {"action": "respond", "message": format_user_stats()}
        elif action == "tips":
            return {
                "action": "respond",
                "message": "💡 **Productivity Tips:**\n\n1. 🍅 Use Pomodoro Technique (25 min work, 5 min break)\n2. 📝 Break big tasks into smaller subtasks\n3. 🎯 Focus on one task at a time\n4. 📅 Plan your day the night before\n5. 🏃 Take regular breaks to stay fresh"
            }
        else:
            return {
                "action": "respond",
                "message": "I'm not sure what you're asking. Try asking about:\n• Your XP and level\n• Today's schedule\n• Upcoming classes\n• Weekly routine"
            }
    
    def _handle_low_confidence(self, candidate: IntentCandidate) -> Dict[str, Any]:
        """Handle low confidence situations - fall back to safe chat."""
        if candidate.intent_type == IntentType.CHAT:
            return {
                "action": "respond",
                "message": "I'm not sure what you mean. Try:\n• 'What do I have today?'\n• 'Add math homework'\n• 'Physics class Mon Wed 10-11'\n• 'How much XP do I have?'"
            }
        else:
            return {
                "action": "clarify",
                "question": "I'm not quite sure what you want. Could you rephrase?",
                "options": ["Add as task", "Add as class", "Just tell me"]
            }
    
    def _generate_chat_response(self, candidate: IntentCandidate) -> str:
        """Generate chat response for chat intent."""
        return "I'm here to help! You can ask me about your schedule, add tasks or classes, or check your stats."


# ==================== LAYER 4: ACTION EXECUTION ====================
class ActionExecutionLayer:
    """
    Layer 4: Execute actions safely.
    NO AI calls here. NO guessing. Pure business logic.
    """
    
    def execute(self, intent: IntentCandidate) -> str:
        """Execute the approved intent and return result message."""
        if intent.intent_type == IntentType.TASK:
            return self._execute_task(intent)
        elif intent.intent_type == IntentType.CLASS:
            return self._execute_class(intent)
        elif intent.intent_type == IntentType.SCHEDULE_FILE:
            return self._execute_schedule_file(intent)
        else:
            return "Action complete."
    
    def _execute_task(self, candidate: IntentCandidate) -> str:
        """Execute task addition."""
        fields = candidate.extracted_fields
        title = fields.get("title", "New Task").strip()
        date = fields.get("date")
        
        task = add_task_logic(load_data(), title, deadline=date)
        
        # Record to ACE
        record_query("task", {"title": title, "date": date})
        
        return f"✅ Added task: **{title}**"
    
    def _execute_class(self, candidate: IntentCandidate) -> str:
        """Execute class addition."""
        fields = candidate.extracted_fields
        title = fields.get("title", "New Class")
        days = fields.get("days", [])
        start = fields.get("start", "00:00")
        end = fields.get("end", "00:00")
        
        schedule = {
            "days": days,
            "start": start,
            "end": end
        }
        
        add_task_logic(
            load_data(),
            title,
            category="class",
            schedule=schedule,
            days=days
        )
        
        # Record to ACE
        record_query("class", {"title": title, "days": days, "start": start, "end": end})
        learn_schedule_patterns([{"title": title, "days": days, "start": start, "end": end}])
        
        return f"✅ Added class: **{title}** ({', '.join(days)} {start}-{end})"
    
    def _execute_schedule_file(self, candidate: IntentCandidate) -> str:
        """Execute schedule file parsing and addition."""
        fields = candidate.extracted_fields
        classes = fields.get("classes", [])
        
        if not classes:
            return "No classes found in the file."
        
        count = save_routine_from_parser(load_data(), classes)
        
        # Record to ACE
        record_query("schedule_file", {"count": count})
        learn_schedule_patterns(classes)
        
        return f"✅ Successfully added {count} classes from the file to your Weekly Routine!"


# ==================== ORCHESTRATOR ====================
class IntentAuthorityOrchestrator:
    """
    Main orchestrator that coordinates all 4 layers.
    Entry point: process(text) -> result
    """
    
    def __init__(self):
        self.authority_layer = IntentAuthorityLayer()
        self.execution_layer = ActionExecutionLayer()
    
    def process(self, text: str, session_id: str = "default") -> Dict[str, Any]:
        """
        Process user input through the complete pipeline.
        
        Returns:
        - {"action": "respond", "message": ...} for queries/chat
        - {"action": "clarify", "question": ..., "options": [...]} for ambiguity
        - {"action": "execute", "result": ...} for completed actions
        """
        # Process through authority layer
        result = self.authority_layer.process(text, session_id)
        
        # Execute if approved
        if result.get("action") == "execute":
            intent = result.get("intent")
            if intent:
                execution_result = self.execution_layer.execute(intent)
                
                # Build final response
                if result.get("needs_confirmation"):
                    return {
                        "action": "execute_confirmed",
                        "message": execution_result,
                        "intent_type": intent.intent_type.value
                    }
                else:
                    return {
                        "action": "execute",
                        "message": execution_result
                    }
        
        return result


# ==================== CONVENIENCE FUNCTIONS ====================
def process_user_input(text: str, session_id: str = "default") -> Dict[str, Any]:
    """
    Convenience function to process user input.
    Use this instead of parse_with_ai for intent-safe processing.
    """
    orchestrator = IntentAuthorityOrchestrator()
    return orchestrator.process(text, session_id)


def clear_pending_intent(session_id: str = "default") -> None:
    """Clear a pending intent (e.g., on cancel)."""
    global PENDING_INTENTS
    if session_id in PENDING_INTENTS:
        del PENDING_INTENTS[session_id]


def get_pending_intent(session_id: str = "default") -> Optional[PendingIntent]:
    """Get pending intent if exists."""
    return PENDING_INTENTS.get(session_id)

