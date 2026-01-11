# ==================== AI_PARSER.PY ====================
# AI-powered parsing for Focus Dashboard
# Handles natural language understanding for tasks, classes, and file parsing

import os
import json
import re
from datetime import datetime
from file_parser import FileParser
from datetime import datetime, timedelta
from logic import load_data, get_today_tasks, get_weekly_class_tasks, get_level_progress
from ace_integration import record_query, learn_schedule_patterns


# Try to import Groq for AI capabilities
try:
    from groq import Groq
except ImportError:
    Groq = None

# ==================== UTILITIES ====================
class RoutineNormalizer:
    """Handles text normalization for routine parsing."""
    
    DAYS_MAP = {
        "mon": "mon", "monday": "mon", "tue": "tue", "tuesday": "tue",
        "wed": "wed", "wednesday": "wed", "thu": "thu", "thursday": "thu",
        "fri": "fri", "friday": "fri", "sat": "sat", "saturday": "sat",
        "sun": "sun", "sunday": "sun"
    }

    @staticmethod
    def normalize_day(text):
        """Normalize day name to 3-letter lowercase."""
        token = text.lower().strip(".,:()")
        return RoutineNormalizer.DAYS_MAP.get(token)

    @staticmethod
    def extract_time_range(text):
        """
        Robust time extractor.
        Matches: 10-11, 10:00-11:30, 8am-9pm, 08.00 - 09.00
        Returns: (start_time, end_time) in HH:MM format
        """
        pattern = r"(\d{1,2}(?:[:.]\d{2})?(?:\s*[ap]m)?)\s*[-–to]+\s*(\d{1,2}(?:[:.]\d{2})?(?:\s*[ap]m)?)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return RoutineNormalizer._format_time(match.group(1)), RoutineNormalizer._format_time(match.group(2))
        return None, None

    @staticmethod
    def _format_time(t_str):
        """Format time string to HH:MM."""
        t_str = t_str.lower().strip().replace(".", ":")
        is_pm = "pm" in t_str
        is_am = "am" in t_str
        cleaned = re.sub(r"[^\d:]", "", t_str)
        
        if ":" not in cleaned:
            cleaned += ":00"
            
        try:
            h, m = map(int, cleaned.split(":"))
            if is_pm and h < 12: h += 12
            if is_am and h == 12: h = 0
            return f"{h:02}:{m:02}"
        except:
            return cleaned  # Fallback

# ==================== SMART PARSER ====================
class SmartParser:
    """Hybrid parser using local regex + AI (Groq) for complex tasks."""
    
    def __init__(self):
        self.file_parser = FileParser()
        self.normalizer = RoutineNormalizer()
        
        # Initialize Groq client if API key available
        api_key = os.environ.get("GROQ_API_KEY")
        self.client = None
        if Groq and api_key:
            try:
                self.client = Groq(api_key=api_key)
            except Exception as e:
                print(f"Groq Init Error: {e}")

    def _get_enhanced_system_prompt(self) -> str:
        """Get enhanced system prompt with user context."""
        ctx = get_user_context()
        
        # Format today's classes
        today_classes = []
        for c in ctx.get("today_classes", []):
            schedule = c.get("schedule", {})
            today_classes.append(f"- {c['title']}: {schedule.get('start','')}-{schedule.get('end','')}")
        today_classes_str = "\n".join(today_classes) if today_classes else "No classes today"
        
        return f"""You are the Focus Dashboard AI Assistant - a friendly, helpful AI that helps students manage their academic life.

## User Context:
- Level {ctx['level']} with {ctx['xp']} XP ({ctx['progress_percent']}% to next level)
- {ctx['total_weekly_classes']} classes scheduled this week
- Today's classes:
{today_classes_str}

## Your Capabilities:
1. **Add Tasks**: Parse requests like "Add math homework" or "Task: finish essay by Friday"
2. **Add Classes**: Parse "Physics class Mon Wed 10-11" or "Lab Tuesday 2pm-4pm"
3. **Answer Questions**: About schedule, stats, tasks, XP, level, productivity
4. **File Parsing**: Extract schedules from uploaded files/images
5. **Productivity Tips**: Give helpful study advice and motivation

## Response Guidelines:
- Be friendly, encouraging, and use emojis sparingly but effectively
- For **questions** about schedule/stats, give helpful answers using the context above
- For **commands** (add task, add class), confirm what you're doing
- Keep responses concise but complete
- Use markdown formatting for better readability

## Output Format:
Always respond with JSON:
{{"intent": "chat"|"task"|"class"|"schedule_file"|"query", "message": "Your response", ...other_details}}

**IMPORTANT - Intent Classification Rules:**
1. **Questions** → intent = "query" (never "task"!)
   - "How much XP do I have?" → {{"intent": "query", "action": "xp"}}
   - "When is my next class?" → {{"intent": "query", "action": "next_class"}}
   - "What do I have today?" → {{"intent": "query", "action": "today_tasks"}}
   - "What classes this week?" → {{"intent": "query", "action": "weekly_classes"}}
   - "Show my stats" → {{"intent": "query", "action": "stats"}}

2. **Commands to ADD something** → intent = "task" or "class"
   - "Add math homework" → {{"intent": "task", ...}}
   - "Physics class Mon Wed 10-11" → {{"intent": "class", ...}}

3. **Greetings/Casual** → intent = "chat"
   - "Hello", "Hi", "Thanks"

For query intent, use this action mapping:
- "xp" → How much XP/level user has
- "next_class" → When user's next class is
- "today_tasks" → What tasks/classes user has today
- "weekly_classes" → What classes user has this week
- "stats" → User's level, XP, productivity stats
"""

    def _call_groq(self, text: str, system_instruction: str = None) -> dict:
        """Call Groq API for intelligent parsing/chat."""
        if not self.client:
            return None
        
        # Use enhanced system prompt for better context
        system_prompt = system_instruction or self._get_enhanced_system_prompt()
        
        try:
            completion = self.client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.3,  # Slightly higher for more conversational responses
                max_tokens=512,
                response_format={"type": "json_object"}
            )
            return json.loads(completion.choices[0].message.content)
        except Exception as e:
            print(f"AI Error: {e}")
            return None

    def parse_file(self, file_path: str) -> dict:
        """Parse a file and extract schedule/task info."""
        try:
            raw_text = self.file_parser.extract_text(file_path)
        except Exception as e:
            return {"intent": "chat", "message": f"❌ Error reading file: {str(e)}"}

        # Try AI extraction first for files
        if self.client:
            system_prompt = (
                "Extract class schedule from this text. "
                "Output JSON: {'intent': 'schedule_file', 'classes': [{'title': '...', 'days': ['mon'], 'start': 'HH:MM', 'end': 'HH:MM'}], 'message': 'Summary'}. "
                "If no routine found, return {'intent': 'chat', 'message': 'No routine found.'}."
            )
            ai_result = self._call_groq(raw_text, system_prompt)
            if ai_result:
                # Learning hook: schedule patterns from AI result (if any)
                try:
                    if ai_result.get("intent") == "schedule_file":
                        learn_schedule_patterns(ai_result.get("classes", []))
                        record_query("schedule_file", {"count": len(ai_result.get("classes", []))})
                except Exception:
                    pass
                return ai_result

        # Local fallback: Universal Regex Logic
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        found_classes = []
        
        for line in lines:
            match = self._parse_line_universally(line)
            if match:
                found_classes.append(match)

        if found_classes:
            # Learning hook: update patterns from offline file parse
            try:
                learn_schedule_patterns(found_classes)
                record_query("schedule_file", {"count": len(found_classes)})
            except Exception:
                pass
            return {
                "intent": "schedule_file",
                "classes": found_classes,
                "needs_clarification": False,
                "message": f"I analyzed the file and found {len(found_classes)} classes (Offline Mode)."
            }
            
        return {
            "intent": "chat",
            "message": "I couldn't detect a clear schedule. Try taking a clearer picture or ensuring 'Day' and 'Time' are visible."
        }

    def _parse_line_universally(self, line):
        """
        Attempts to extract Day, Time, and Subject from a messy line.
        Returns class dict or None.
        """
        words = line.split()
        
        # 1. Find Time Range
        start, end = self.normalizer.extract_time_range(line)
        if not start:
            return None  # No time found
            
        # 2. Find Days
        found_days = []
        for w in words:
            d = self.normalizer.normalize_day(w)
            if d:
                found_days.append(d)
        
        if not found_days:
            return None  # No days found

        # 3. Extract Subject (clean title)
        clean_text = re.sub(
            r"(\d{1,2}(?:[:.]\d{2})?(?:\s*[ap]m)?)\s*[-–to]+\s*(\d{1,2}(?:[:.]\d{2})?(?:\s*[ap]m)?)",
            "",
            line,
            flags=re.IGNORECASE
        )

        
        subject_words = []
        for w in clean_text.split():
            if not self.normalizer.normalize_day(w) and len(w) > 1:
                subject_words.append(w)
                
        title = " ".join(subject_words).strip(" -:,.()")
        if not title:
            title = "Class"
        
        return {
            "intent": "class",
            "title": title.title(),
            "subject": title.title(),
            "days": list(set(found_days)),
            "start": start,
            "end": end,
            "confidence": 0.9
        }

    def parse(self, text: str) -> dict:
        """Parse natural language text for tasks/classes."""
        text = text.strip()
        lower_text = text.lower()
        
        # 0. FIRST: Check for QUERIES (questions) - this must be before task/class parsing
        # Questions pattern: starts with what, when, how, why, where, whose, which, who, "show", "tell"
        query_patterns = [
            r"^(what|when|how|why|where|whose|which|who)\s",
            r"^(show|tell|list|get)\s",
        ]
        is_question = any(re.search(p, lower_text) for p in query_patterns)
        
        if is_question:
            # Map question keywords to actions
            if any(kw in lower_text for kw in ["xp", "level", "exp", "progress"]):
                return {"intent": "query", "action": "xp", "message": "Let me check your XP and level!"}
            elif any(kw in lower_text for kw in ["next class", "next class is", "class today", "schedule", "class at"]):
                return {"intent": "query", "action": "next_class", "message": "Let me check your upcoming classes!"}
            elif any(kw in lower_text for kw in ["today", "what do i have", "what's today", "tasks today"]):
                return {"intent": "query", "action": "today_tasks", "message": "Let me check your today's schedule!"}
            elif any(kw in lower_text for kw in ["week", "weekly", "this week", "classes this week"]):
                return {"intent": "query", "action": "weekly_classes", "message": "Let me check your weekly classes!"}
            elif any(kw in lower_text for kw in ["stat", "stats", "progress", "performance", "doing"]):
                return {"intent": "query", "action": "stats", "message": "Let me show your stats!"}
            elif any(kw in lower_text for kw in ["productivity", "tip", "advice", "suggestion"]):
                return {"intent": "chat", "message": "💡 **Productivity Tips:**\n\n1. 🍅 Use Pomodoro Technique (25 min work, 5 min break)\n2. 📝 Break big tasks into smaller subtasks\n3. 🎯 Focus on one task at a time\n4. 📅 Plan your day the night before\n5. 🏃 Take regular breaks to stay fresh\n\nWould you like more specific tips?"}
            else:
                return {"intent": "chat", "message": "I'm not sure what you're asking. Try asking:\n• 'How much XP do I have?'\n• 'When is my next class?'\n• 'What do I have today?'\n• 'Show my stats'"}
        
        # 1. Try local regex first
        class_match = self._try_parse_class(text, lower_text)
        if class_match and not class_match.get("needs_clarification"):
            # Learning hook: record intent and class structure
            try:
                learn_schedule_patterns([class_match])
                record_query("class", {k: class_match.get(k) for k in ("days","start","end","title")})
            except Exception:
                pass
            return class_match
            
        task_match = self._parse_task(text, lower_text)
        
        # Simple commands use local parser
        if lower_text.startswith("task") or "assignment" in lower_text:
            # Learning hook: record task intent
            try:
                record_query("task", {"title": task_match.get("title"), "date": task_match.get("date")})
            except Exception:
                pass
            return task_match

        # 2. Use AI for complex/natural input
        if self.client:
            ai_result = self._call_groq(text)
            if ai_result:
                # Learning hook: record generic chat intent
                try:
                    record_query(ai_result.get("intent", "chat"), {"message": ai_result.get("message")})
                except Exception:
                    pass
                return ai_result

        # 3. Local fallback for chat
        if lower_text in ["hi", "hello", "hey"]:
            resp = {
                "intent": "chat",
                "message": "Hello! 👋 I'm ready to help. Try saying 'Physics class Mon Wed 10-11'",
                "needs_clarification": False
            }
            try:
                record_query("chat", {"greeting": True})
            except Exception:
                pass
            return resp
            
        # Default: treat as task
        try:
            record_query("task", {"title": task_match.get("title"), "date": task_match.get("date")})
        except Exception:
            pass
        return task_match

    def _try_parse_class(self, text, lower_text):
        """Parse class from text using regex."""
        # Look for time range: 10:00-11:30 or 10-11
        time_pattern = r"(\d{1,2}(?::\d{2})?)\s*-\s*(\d{1,2}(?::\d{2})?)"
        times = re.search(time_pattern, text)
        
        days_map = {
            "mon": "mon", "tue": "tue", "wed": "wed", "thu": "thu", 
            "fri": "fri", "sat": "sat", "sun": "sun",
            "monday": "mon", "tuesday": "tue", "wednesday": "wed", 
            "thursday": "thu", "friday": "fri", "saturday": "sat", "sunday": "sun"
        }
        
        found_days = []
        for word in lower_text.replace(",", " ").split():
            if word in days_map:
                found_days.append(days_map[word])
        
        # If times + days found, it's a class
        if times and found_days:
            title = text.split(found_days[0])[0] if found_days else text.split()[0]
            title = re.sub(r"\b(class|lecture)\b", "", title, flags=re.IGNORECASE).strip()
            
            start, end = times.group(1), times.group(2)
            
            def norm_time(t):
                if ":" not in t:
                    return f"{int(t):02}:00"
                return t
            
            return {
                "intent": "class",
                "title": title.title() or "New Class",
                "subject": title.title(),
                "days": list(set(found_days)),
                "start": norm_time(start),
                "end": norm_time(end),
                "needs_clarification": False
            }
        
        # Class keyword without details - ask for clarification
        if "class" in lower_text:
            return {
                "intent": "class", 
                "needs_clarification": True, 
                "question": "What days and time is this class? (e.g. 'Mon Wed 10-11')"
            }

        return None

    def _parse_task(self, text, lower_text):
        """Parse task from text with improved natural language handling."""
        title = text
        
        # Step 1: First extract any date information (before cleaning title)
        date_str = self._extract_date(title)
        
        # Step 2: Remove common natural language prefixes that are NOT part of the task
        # These patterns indicate the user is stating they need to do something
        prefixes_to_remove = [
            r"\bi have\b",           # "I have"
            r"\bi need to\b",        # "I need to"
            r"\bi need\b",           # "I need"
            r"\bi should\b",         # "I should"
            r"\bi must\b",           # "I must"
            r"\bi want to\b",        # "I want to"
            r"\badd\b",              # "Add"
            r"\bcreate\b",           # "Create"
            r"\bnew\b",              # "New"
            r"\btask\b",             # "Task"
            r"\bto do\b",            # "To do"
            r"\bto finish\b",        # "To finish"
            r"\bplease\b",           # "Please"
        ]
        
        for prefix in prefixes_to_remove:
            title = re.sub(prefix, "", title, flags=re.IGNORECASE).strip()
        
        # Step 3: Remove date-related words that are not part of the task
        date_words = [
            r"\bon\s+\d{1,2}\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
            r"\bon\s+\d{1,2}[/-]\d{1,2}",
            r"\bby\s+\d{1,2}\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
            r"\bby\s+\d{1,2}[/-]\d{1,2}",
            r"\bdue\s+\d{1,2}\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
            r"\btoday\b",
            r"\btomorrow\b",
            r"\bmonday\b", r"\btuesday\b", r"\bwednesday\b", r"\bthursday\b",
            r"\bfriday\b", r"\bsaturday\b", r"\bsunday\b",
        ]
        
        for dw in date_words:
            title = re.sub(dw, "", title, flags=re.IGNORECASE).strip()
        
        # Step 4: Clean up extra whitespace and special characters
        title = re.sub(r"\s+", " ", title).strip()
        title = re.sub(r"^[,\s.:;-]+|[,\s.:;-]+$", "", title).strip()
        
        # Step 5: Remove assignment keyword if still present (but only if not part of word)
        title = re.sub(r"\bassignment\b", "", title, flags=re.IGNORECASE).strip()
        
        # Step 6: If title is empty or too short, use original text
        if not title or len(title) < 2:
            # Try to extract subject name (like "physics" from "physics assignment")
            words = text.split()
            for i, w in enumerate(words):
                if w.lower() in ["assignment", "task", "homework"]:
                    if i > 0:
                        title = " ".join(words[:i])
                    else:
                        title = " ".join(words[1:])
                    break
            title = title.strip()
        
        # Step 7: Capitalize properly
        title = title.strip()
        if title:
            # Handle hyphenated titles
            title = " ".join(word.capitalize() for word in title.split("-"))
            title = "-".join(word.capitalize() for word in title.split())

        return {
            "intent": "task",
            "title": title if title else "New Task",
            "date": date_str,
            "needs_clarification": False
        }
    
    def _extract_date(self, title):
        """Extract date from task title."""
        from utils import today
        today_date = today()
        
        # Handle "tomorrow"
        if re.search(r"\b(tomorrow|kal)\b", title, re.IGNORECASE):
            tomorrow = datetime.now() + timedelta(days=1)
            return tomorrow.strftime("%Y-%m-%d")
        
        # Handle "today"
        if re.search(r"\b(today|aj)\b", title, re.IGNORECASE):
            return today_date
        
        # Handle explicit date: 23 Jan, 23 January
        date_match = re.search(
            r"(\d{1,2})\s*(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)",
            title, re.IGNORECASE
        )
        
        if date_match:
            day = int(date_match.group(1))
            month_str = date_match.group(2).lower()[:3]
            month_map = {
                "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
                "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
            }
            if month_str in month_map:
                try:
                    new_date = datetime(datetime.now().year, month_map[month_str], day)
                    return new_date.strftime("%Y-%m-%d")
                except ValueError:
                    pass
        
        # Handle numeric date: 23/01
        num_date_match = re.search(r"\b(\d{1,2})[/-](\d{1,2})\b", title)
        if num_date_match:
            try:
                day, month = int(num_date_match.group(1)), int(num_date_match.group(2))
                new_date = datetime(datetime.now().year, month, day)
                return new_date.strftime("%Y-%m-%d")
            except ValueError:
                pass
        
        return None


# ==================== AI HELPER FUNCTIONS ====================
def get_user_context() -> dict:
    """Get current user context for AI to use."""
    data = load_data()
    
    # Get level info
    lvl, xp, progress = get_level_progress(data)
    curr_xp, req_xp, _ = get_level_progress(data)
    
    # Get today's tasks
    today_tasks = get_today_tasks(data)
    classes_today = [t for t in today_tasks if t.get("type") == "class"]
    tasks_today = [t for t in today_tasks if t.get("type") != "class"]
    
    # Get weekly schedule
    weekly = get_weekly_class_tasks(data)
    total_weekly_classes = sum(len(v) for v in weekly.values())
    
    return {
        "level": data.get("level", 1),
        "xp": data.get("xp", 0),
        "xp_needed": req_xp,
        "xp_progress": curr_xp,
        "progress_percent": int((curr_xp / req_xp * 100) if req_xp > 0 else 0),
        "today_classes": classes_today,
        "today_tasks": tasks_today,
        "total_weekly_classes": total_weekly_classes,
        "history": data.get("history", {})
    }

def format_today_schedule() -> str:
    """Format today's schedule for AI responses."""
    data = load_data()
    today_tasks = get_today_tasks(data)
    classes_today = [t for t in today_tasks if t.get("type") == "class"]
    
    if not classes_today:
        return "🎉 No classes scheduled for today!"
    
    lines = ["📅 **Today's Classes:**"]
    for c in classes_today:
        schedule = c.get("schedule", {})
        start = schedule.get("start", "")
        end = schedule.get("end", "")
        lines.append(f"• **{c['title']}** - {start} - {end}")
    
    return "\n".join(lines)

def format_user_stats() -> str:
    """Format user stats for AI responses."""
    ctx = get_user_context()
    
    lines = [
        "📊 **Your Stats:**",
        f"⭐ **Level {ctx['level']}**",
        f"✨ XP: {ctx['xp']} / {ctx['xp_needed']} ({ctx['progress_percent']}%)",
        f"📚 Weekly Classes: {ctx['total_weekly_classes']}",
        f"📝 Today's Tasks: {len(ctx['today_tasks'])}"
    ]
    
    return "\n".join(lines)

def format_upcoming_classes() -> str:
    """Format upcoming classes (next 3) for AI responses."""
    data = load_data()
    today_tasks = get_today_tasks(data)
    classes_today = [t for t in today_tasks if t.get("type") == "class"]
    
    if not classes_today:
        return "🎉 No upcoming classes today!"
    
    # Sort by start time
    classes_today.sort(key=lambda x: x.get("schedule", {}).get("start", ""))
    
    lines = ["📅 **Upcoming Classes:**"]
    for i, c in enumerate(classes_today[:3], 1):
        schedule = c.get("schedule", {})
        start = schedule.get("start", "")
        end = schedule.get("end", "")
        lines.append(f"{i}. **{c['title']}** - {start} to {end}")
    
    return "\n".join(lines)


# ==================== CONVENIENCE FUNCTIONS ====================
def parse_with_ai(text: str) -> dict:
    """Parse natural language text."""
    parser = SmartParser()
    raw = parser.parse(text)

    def _normalize(r: dict) -> dict:
        if not isinstance(r, dict):
            return {"intent": "chat", "message": str(r), "confidence": 0.0, "source": "local"}

        # Ensure intent exists
        intent = r.get("intent", "chat")
        out = r.copy()
        out.setdefault("confidence", 0.0)
        out.setdefault("source", out.get("source", "ai" if out.get("message") else "local"))

        # Normalize common shapes
        if intent == "task":
            # Try to ensure title/date exist
            title = out.get("title") or out.get("message") or out.get("subject")
            out["title"] = title if title else "New Task"
            out.setdefault("date", out.get("date", None))

        if intent == "class" or intent == "schedule_file":
            # Normalize schedule fields
            if "schedule" in out:
                sch = out.get("schedule") or {}
                out.setdefault("days", sch.get("days"))
                out.setdefault("start", sch.get("start"))
                out.setdefault("end", sch.get("end"))

        return out

    return _normalize(raw)

def parse_file_with_ai(file_path: str) -> dict:
    """Parse a file for schedule/task info."""
    parser = SmartParser()
    raw = parser.parse_file(file_path)

    # Basic normalization for file parse
    if isinstance(raw, dict):
        raw.setdefault("confidence", raw.get("confidence", 0.9))
        raw.setdefault("source", raw.get("source", "ai" if Groq else "local"))
    return raw
