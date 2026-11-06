"""views_today - split from ui.py (Focus Agent V2, Phase 6)."""

# ==================== UI.PY (MODERN) ====================
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog
from datetime import datetime, timedelta
from PIL import Image
import os
import queue
import threading
from tkcalendar import Calendar

from logic import (
    load_data, save_data, add_task_logic, add_subtask, toggle_subtask,
    get_level_progress, get_active_class, mark_class_done,
    sync_class_statuses, log_focus_time, cleanup_finished_classes,
    get_today_tasks, get_weekly_class_tasks, today, format_seconds_to_hms,
    get_task_by_id, # Added missing import
    log_class_session, get_today_focus_stats, log_focus_session,
    complete_task_logic, add_xp, delete_task_logic, update_task_logic,
    add_subject, delete_subject, add_vault_file, delete_vault_file, rename_subject,
    add_habit, delete_habit, toggle_habit_today, get_habit_streak, get_analytics_data,
    get_heatmap_data, get_store_items, purchase_item, is_unlocked,
    get_pomodoro_settings, update_pomodoro_settings,
    update_timer_state, clear_timer_state, process_daily_automation, # Added automation
)
import subprocess
import storage
# Modern Premium Color Palette
from .theme import COLORS, FONTS, get_color_str
from .widgets import TimePicker, DaySelector, Tooltip


class TodayView(ctk.CTkScrollableFrame):
    """Enhanced Today view with beautiful task cards."""
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=COLORS["bg"], scrollbar_button_color=COLORS["card"])
        self.app = app
        self.task_cards = {}  # task_id -> card widget for silent updates
        self._init_static_ui()
        # Don't render here - switch_view will call render() when view is shown

    def _init_static_ui(self):
        """Create header, Quick Agent Command Bar, KPI strip, and action bar."""
        self._last_width = 760
        self._kpi_cards = []
        self._kpi_sub_lbls = []
        self._briefing_detail_lbl = None

        # Header with gradient accent (pack date_badge on right FIRST so title never overlaps it)
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", pady=(6, 10), padx=10)

        from datetime import datetime
        now_dt = datetime.now()
        self._full_date_str = now_dt.strftime("%A, %B %d")
        self._short_date_str = now_dt.strftime("%b %d")
        self.date_badge = ctk.CTkFrame(
            header_frame, fg_color=COLORS["card"], corner_radius=8,
            border_width=1, border_color=COLORS["border"]
        )
        self.date_badge.pack(side="right", pady=4, padx=(8, 0))
        self.date_badge_lbl = ctk.CTkLabel(
            self.date_badge, text=f"📅 {self._full_date_str}", font=FONTS["small"],
            text_color=COLORS["text_dim"]
        )
        self.date_badge_lbl.pack(padx=10, pady=5)

        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.pack(side="left", fill="x", expand=True)
        self.dash_title_lbl = ctk.CTkLabel(
            title_box, text="📊 Student Productivity Dashboard", font=FONTS["title"],
            text_color=COLORS["text"], anchor="w", justify="left"
        )
        self.dash_title_lbl.pack(anchor="w")
        self.dash_sub_lbl = ctk.CTkLabel(
            title_box, text="Agent-driven tasks, classes, and daily focus flow",
            font=FONTS["small"], text_color=COLORS["text_dim"], anchor="w", justify="left"
        )
        self.dash_sub_lbl.pack(anchor="w")

        # ---- Quick AI Agent Command Bar (First-Class V2 Agent Entry) ----
        agent_card = ctk.CTkFrame(
            self, fg_color=COLORS["card_highlight"], corner_radius=12,
            border_width=1, border_color=COLORS["accent_light"]
        )
        agent_card.pack(fill="x", padx=10, pady=(0, 12))

        agent_top = ctk.CTkFrame(agent_card, fg_color="transparent")
        agent_top.pack(fill="x", padx=14, pady=(10, 4))
        self.console_link_btn = ctk.CTkButton(
            agent_top, text="Open Agent Console →", width=145, height=26,
            fg_color="transparent", hover_color=COLORS["card"],
            text_color=COLORS["accent"], font=FONTS["small"],
            command=lambda: self.app.switch_view("assistant")
        )
        self.console_link_btn.pack(side="right")
        ctk.CTkLabel(
            agent_top, text="🤖 Quick Agent Command", font=FONTS["subheader"],
            text_color=COLORS["accent"]
        ).pack(side="left")

        agent_input_row = ctk.CTkFrame(agent_card, fg_color="transparent")
        agent_input_row.pack(fill="x", padx=14, pady=(2, 10))
        self.quick_agent_btn = ctk.CTkButton(
            agent_input_row, text="Ask Agent ✦", width=114, height=36,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_dark"],
            text_color="white", corner_radius=8, font=FONTS["body"],
            command=self.run_quick_agent
        )
        self.quick_agent_btn.pack(side="right")

        self.quick_agent_entry = ctk.CTkEntry(
            agent_input_row,
            placeholder_text="Ask AI Agent: e.g. 'Kal math assignment rat 8 tay' or 'Plan my day'",
            font=FONTS["body"], height=36, fg_color=COLORS["card"],
            border_color=COLORS["border"]
        )
        self.quick_agent_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.quick_agent_entry.bind("<Return>", lambda e: self.run_quick_agent())

        self.quick_agent_status = ctk.CTkLabel(
            agent_card, text="", font=FONTS["small"],
            text_color=COLORS["text_dim"], wraplength=600, justify="left"
        )
        self.quick_agent_trace = ctk.CTkLabel(
            agent_card, text="", font=FONTS["tiny"],
            text_color=COLORS["accent"], wraplength=600, justify="left"
        )

        # ---- Proactive Morning Briefing & Conflict Alert Banner ----
        self.briefing_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.briefing_frame.pack(fill="x", padx=10, pady=(0, 10))

        # ---- KPI Summary Strip ----
        self.kpi_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.kpi_frame.pack(fill="x", padx=10, pady=(0, 12))

        # Section header + Action buttons (pack buttons on right FIRST so they never overlap title)
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.pack(fill="x", pady=(0, 10), padx=10)

        self.add_task_btn = ctk.CTkButton(
            input_frame, text="+ Add Task", command=self.prompt_add_task,
            fg_color=COLORS["card"], hover_color=COLORS["card_hover"],
            border_width=1, border_color=COLORS["border"],
            width=105, height=32, corner_radius=8, text_color=COLORS["text"],
            font=FONTS["body"]
        )
        self.add_task_btn.pack(side="right", padx=(6, 0))

        self.add_class_btn = ctk.CTkButton(
            input_frame, text="+ Add Class", command=self.prompt_add_class,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_dark"], 
            width=105, height=32, corner_radius=8, text_color="white",
            font=FONTS["body"]
        )
        self.add_class_btn.pack(side="right")

        self.plan_day_btn = ctk.CTkButton(
            input_frame, text="🗓 Plan My Day",
            command=lambda: self.app.switch_view("planner"),
            fg_color=COLORS["bg_secondary"], hover_color=COLORS["card_hover"],
            width=118, height=32, corner_radius=8, text_color=COLORS["accent"],
            font=FONTS["body"]
        )
        self.plan_day_btn.pack(side="right", padx=(0, 6))

        self.schedule_hdr_lbl = ctk.CTkLabel(
            input_frame, text="Today's Schedule & Deadlines", font=FONTS["header"],
            text_color=COLORS["text"], anchor="w"
        )
        self.schedule_hdr_lbl.pack(side="left", fill="x", expand=True)
        
        # Container for dynamic list
        self.list_container = ctk.CTkFrame(self, fg_color="transparent")
        self.list_container.pack(fill="both", expand=True)

    def run_quick_agent(self):
        msg = self.quick_agent_entry.get().strip()
        if not msg:
            return
        self.quick_agent_entry.delete(0, "end")
        self.quick_agent_btn.configure(state="disabled", text="Working…")
        self.quick_agent_status.configure(text=f"⏳ Agent processing: \"{msg}\"…", text_color=COLORS["accent"])
        self.quick_agent_status.pack(anchor="w", padx=14, pady=(0, 2))
        self.quick_agent_trace.configure(text="")

        def worker():
            trace_line = ""
            try:
                from focus_agent.controller import AgentController
                ctrl = AgentController(self.app.data)
                reply = ctrl.handle(msg)
                summary = (reply.message or "Done.").split("\n")[0][:200]
                ok = reply.status in ("ok", "provider_offline", "asked_user")
                ext = getattr(reply, "extraction", None)
                tools = getattr(reply, "tool_results", None) or []
                t_parts = []
                if ext:
                    t_parts.append(f"Intent={ext.intent}")
                    if ext.tasks:
                        t0 = ext.tasks[0]
                        if t0.title:
                            t_parts.append(f"Title='{t0.title}'")
                        if t0.subject:
                            t_parts.append(f"Subject='{t0.subject}'")
                        if t0.due_date:
                            t_parts.append(f"Due={t0.due_date}")
                        if t0.due_time:
                            t_parts.append(f"Time={t0.due_time}")
                        if t0.estimated_minutes:
                            t_parts.append(f"Est={t0.estimated_minutes}m")
                if tools:
                    t_parts.append("Tools=" + ",".join(f"{tr.tool}({'✓' if tr.ok else '✗'})" for tr in tools))
                if t_parts:
                    trace_line = "🔍 Agent Trace: " + " · ".join(t_parts)
            except Exception as e:
                summary = f"Error: {e}"
                ok = False

            def finish():
                self.quick_agent_btn.configure(state="normal", text="Ask Agent ✦")
                icon = "✅" if ok else "⚠️"
                self.quick_agent_status.configure(
                    text=f"{icon} {summary}",
                    text_color=COLORS["success"] if ok else COLORS["error"]
                )
                if trace_line:
                    self.quick_agent_trace.configure(text=trace_line)
                    self.quick_agent_trace.pack(anchor="w", padx=14, pady=(0, 8))
                self.app.refresh_xp()
                self.render()
            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _render_proactive_briefing(self):
        """Autonomous Morning Briefing & Deadline Conflict Detector."""
        for w in self.briefing_frame.winfo_children():
            w.destroy()
        today_str = today()
        tmr_str = (datetime.now().date() + timedelta(days=1)).isoformat()
        all_open = [
            t for t in self.app.data.get("tasks", [])
            if t.get("type") != "class" and t.get("status") not in ("done", "archived")
        ]
        if not all_open:
            return

        overdue = [t for t in all_open if t.get("date") and t["date"] < today_str]
        due_today = [t for t in all_open if t.get("date") == today_str]
        due_tmr = [t for t in all_open if t.get("date") == tmr_str]
        tmr_mins = sum(int(t.get("duration") or 60) for t in due_tmr)
        today_mins = sum(int(t.get("duration") or 60) for t in due_today)

        if overdue:
            headline = f"⚠️ Proactive Alert: {len(overdue)} overdue task(s) need rescheduling"
            detail = (f"'{overdue[0]['title']}' was due {overdue[0]['date']}. "
                      f"Click Auto-Plan to reschedule overdue & today's tasks into free study slots.")
            border_c = COLORS["warning"]
        elif due_tmr and tmr_mins >= 120:
            headline = f"⚡ Deadline Radar: {len(due_tmr)} task(s) due tomorrow ({tmr_mins} min estimated)"
            detail = (f"Next up: '{due_tmr[0]['title']}'"
                      + (f" at {due_tmr[0]['due_time']}" if due_tmr[0].get("due_time") else "")
                      + ". Start a study block today to avoid a last-minute crunch.")
            border_c = COLORS["accent"]
        elif due_today:
            headline = f"🎯 Today's Briefing: {len(due_today)} task(s) due today (~{today_mins} min total)"
            detail = f"Top priority: '{due_today[0]['title']}'. Generate a conflict-free schedule around your classes."
            border_c = COLORS["accent_light"]
        else:
            headline = f"💡 Agent Briefing: {len(all_open)} active task(s) in queue"
            detail = f"Next task: '{all_open[0]['title']}'. Let the planner assign optimal study blocks."
            border_c = COLORS["border"]

        banner = ctk.CTkFrame(
            self.briefing_frame, fg_color=COLORS["card"], corner_radius=10,
            border_width=1, border_color=border_c
        )
        banner.pack(fill="x")

        def auto_plan_now():
            try:
                from focus_agent import scheduler as fsched, memory as fmemory
                plan = fsched.generate_day_plan(
                    self.app.data, today_str,
                    settings=self.app.data.get("settings"), commit=True
                )
                fmemory.log_plan(self.app.data, plan.to_dict())
                self.app.switch_view("planner")
                if "planner" in self.app.views:
                    self.app.views["planner"].generate_plan()
            except Exception as e:
                messagebox.showerror("Auto-Plan", str(e))

        ctk.CTkButton(
            banner, text="⚡ Auto-Plan Today", width=136, height=30,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_dark"],
            text_color="white", corner_radius=8, font=FONTS["small"],
            command=auto_plan_now
        ).pack(side="right", padx=12, pady=10)

        txt_col = ctk.CTkFrame(banner, fg_color="transparent")
        txt_col.pack(side="left", fill="x", expand=True, padx=14, pady=8)
        wrap_b = max(240, int(getattr(self, "_last_width", 760) - 210))
        self._briefing_head_lbl = ctk.CTkLabel(
            txt_col, text=headline, font=FONTS["subheader"],
            text_color=COLORS["text"], wraplength=wrap_b, justify="left"
        )
        self._briefing_head_lbl.pack(anchor="w")
        self._briefing_detail_lbl = ctk.CTkLabel(
            txt_col, text=detail, font=FONTS["small"],
            text_color=COLORS["text_dim"], wraplength=wrap_b, justify="left"
        )
        self._briefing_detail_lbl.pack(anchor="w")

    def _render_kpis(self, today_tasks):
        for w in self.kpi_frame.winfo_children():
            w.destroy()
        self._kpi_cards = []
        self._kpi_sub_lbls = []
        all_open = [
            t for t in self.app.data.get("tasks", [])
            if t.get("type") != "class" and t.get("status") not in ("done", "archived")
        ]
        classes_today = [t for t in today_tasks if t.get("type") == "class"]
        focus_stats = get_today_focus_stats(self.app.data)
        focus_min = int((focus_stats.get("total_seconds", 0) + focus_stats.get("class_seconds", 0)) // 60)
        active_goals = sum(1 for g in self.app.data.get("goals", []) if g.get("status", "active") == "active")

        cards = [
            ("📝 Open Tasks", str(len(all_open)), "Active assignments", COLORS["accent"]),
            ("📘 Classes Today", str(len(classes_today)), "In weekly routine", COLORS["warning"]),
            ("⏱ Focus Time", f"{focus_min} min", f"{focus_stats.get('sessions', 0)} session(s) today", COLORS["success"]),
            ("🎯 Active Goals", str(active_goals), "Long-term roadmaps", COLORS["accent_light"]),
        ]
        for _idx, (label, val, sub, col) in enumerate(cards):
            c = ctk.CTkFrame(
                self.kpi_frame, fg_color=COLORS["card"], corner_radius=10,
                border_width=1, border_color=COLORS["border"]
            )
            ctk.CTkLabel(c, text=label, font=FONTS["small"], text_color=COLORS["text_dim"]).pack(
                anchor="w", padx=12, pady=(8, 0)
            )
            ctk.CTkLabel(c, text=val, font=FONTS["kpi"], text_color=col).pack(
                anchor="w", padx=12, pady=1
            )
            sub_lbl = ctk.CTkLabel(
                c, text=sub, font=FONTS["tiny"], text_color=COLORS["text_muted"],
                anchor="w", justify="left"
            )
            sub_lbl.pack(anchor="w", padx=12, pady=(0, 8))
            self._kpi_cards.append(c)
            self._kpi_sub_lbls.append(sub_lbl)

        self._layout_kpi_grid(getattr(self, "_last_width", 760))

    def _layout_kpi_grid(self, width):
        """Arrange KPI cards in a 2x2 grid on narrow screens (<660px) and 1x4 row on wider screens."""
        if not getattr(self, "_kpi_cards", None):
            return
        two_by_two = width < 660
        for col_i in range(4):
            self.kpi_frame.grid_columnconfigure(col_i, weight=0, uniform="")
        if two_by_two:
            self.kpi_frame.grid_columnconfigure(0, weight=1, uniform="kpi2")
            self.kpi_frame.grid_columnconfigure(1, weight=1, uniform="kpi2")
            sub_wrap = max(120, int(width // 2 - 44))
            for idx, card in enumerate(self._kpi_cards):
                card.grid(row=idx // 2, column=idx % 2, sticky="nsew", padx=4, pady=3)
        else:
            for col_i in range(4):
                self.kpi_frame.grid_columnconfigure(col_i, weight=1, uniform="kpi4")
            sub_wrap = max(105, int(width // 4 - 36))
            for idx, card in enumerate(self._kpi_cards):
                card.grid(row=0, column=idx, sticky="nsew", padx=4, pady=2)
        for lbl in getattr(self, "_kpi_sub_lbls", []):
            try:
                lbl.configure(wraplength=sub_wrap)
            except Exception:
                pass

    def render(self):
        """Refresh proactive briefing, KPI strip, today's tasks, upcoming deadlines, and habits."""
        for w in self.list_container.winfo_children(): w.destroy()
        self.task_cards = {}  # Clear card references on full refresh

        today_str = today()
        today_tasks = get_today_tasks(self.app.data)
        self._render_proactive_briefing()
        self._render_kpis(today_tasks)

        pending_today = [t for t in today_tasks if t.get("status") != "done"]
        upcoming_tasks = [
            t for t in self.app.data.get("tasks", [])
            if t.get("type") != "class"
            and t.get("status") not in ("done", "archived")
            and t.get("date") and t["date"] > today_str
        ]
        upcoming_tasks.sort(key=lambda t: (t.get("date") or "9999", t.get("due_time") or "23:59"))

        if not pending_today and not upcoming_tasks:
            empty_frame = ctk.CTkFrame(
                self.list_container, fg_color=COLORS["card"], corner_radius=14,
                border_width=1, border_color=COLORS["border"]
            )
            empty_frame.pack(fill="x", padx=10, pady=20)
            ctk.CTkLabel(empty_frame, text="✨ All caught up!", 
                         text_color=COLORS["text"], font=FONTS["header"]).pack(pady=(24, 4))
            ctk.CTkLabel(empty_frame, text="Use the Quick Agent Command bar above or click '+ Add Task' to plan ahead.", 
                         text_color=COLORS["text_dim"], font=FONTS["body"]).pack(pady=(0, 24))
        else:
            if pending_today:
                for task in pending_today:
                    self.draw_task_card(task)
            if upcoming_tasks:
                up_hdr = ctk.CTkFrame(self.list_container, fg_color="transparent")
                up_hdr.pack(fill="x", padx=12, pady=(14, 4))
                ctk.CTkLabel(
                    up_hdr, text=f"🗓️ Day-Wise Upcoming Schedule & Deadlines ({len(upcoming_tasks)})",
                    font=FONTS["subheader"], text_color=COLORS["accent"]
                ).pack(side="left")
                tmr_str = (datetime.now().date() + timedelta(days=1)).isoformat()
                last_date = None
                for task in upcoming_tasks:
                    t_date = task.get("date")
                    if t_date and t_date != last_date:
                        last_date = t_date
                        day_label = f"Tomorrow ({t_date})" if t_date == tmr_str else t_date
                        day_banner = ctk.CTkFrame(self.list_container, fg_color="transparent")
                        day_banner.pack(fill="x", padx=16, pady=(6, 2))
                        ctk.CTkLabel(
                            day_banner, text=f"📌 {day_label}",
                            font=FONTS["small"], text_color=COLORS["text_dim"]
                        ).pack(side="left")
                    self.draw_task_card(task)

        # Compact Daily Habits section at bottom of Dashboard
        self._render_habits_strip()

    def _render_habits_strip(self):
        habits = self.app.data.get("habits", [])
        hab_card = ctk.CTkFrame(
            self.list_container, fg_color=COLORS["card"], corner_radius=12,
            border_width=1, border_color=COLORS["border"]
        )
        hab_card.pack(fill="x", padx=10, pady=(16, 10))
        hdr = ctk.CTkFrame(hab_card, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(10, 6))
        ctk.CTkLabel(hdr, text="🥗 Daily Habits", font=FONTS["subheader"],
                     text_color=COLORS["text"]).pack(side="left")

        def add_new_habit():
            dlg = ctk.CTkInputDialog(text="New daily habit title:", title="Add Habit")
            h_title = dlg.get_input()
            if h_title and h_title.strip():
                add_habit(self.app.data, h_title.strip())
                self.render()

        ctk.CTkButton(
            hdr, text="+ Habit", width=70, height=24, corner_radius=6,
            fg_color=COLORS["bg_secondary"], hover_color=COLORS["card_hover"],
            text_color=COLORS["accent"], font=FONTS["small"], command=add_new_habit
        ).pack(side="right")

        if not habits:
            ctk.CTkLabel(hab_card, text="No daily habits yet — click '+ Habit' to track daily consistency.",
                         font=FONTS["small"], text_color=COLORS["text_dim"]).pack(anchor="w", padx=14, pady=(0, 10))
            return

        today_str = today()
        chips = ctk.CTkFrame(hab_card, fg_color="transparent")
        chips.pack(fill="x", padx=12, pady=(0, 10))
        for h in habits:
            is_done = today_str in h.get("history", {})
            streak = get_habit_streak(h)
            pill = ctk.CTkFrame(chips, fg_color=COLORS["bg_secondary"], corner_radius=8)
            pill.pack(side="left", padx=4, pady=3)
            chk = ctk.CTkCheckBox(
                pill, text=f"{h['title']} (🔥{streak}d)", font=FONTS["small"],
                fg_color=COLORS["success"], width=18, height=18,
                command=lambda hid=h["id"]: (toggle_habit_today(self.app.data, hid), self.app.refresh_xp(), self.render())
            )
            if is_done:
                chk.select()
            chk.pack(side="left", padx=(8, 6), pady=5)

    def draw_task_card(self, task):
        """Draw a responsive task card: Row 1 has Checkbox + full-width Title + Edit/Delete; Row 2 has Action buttons + Metadata pills."""
        is_class = task.get("type") == "class"
        border_col = COLORS["accent_light"] if is_class else COLORS["border"]
        card = ctk.CTkFrame(
            self.list_container, fg_color=COLORS["card"], corner_radius=12,
            border_width=1, border_color=border_col
        )
        card.pack(fill="x", pady=5, padx=10)
        card._task_id = task["id"]  # Store reference for silent updates
        card._detail_section = None  # Will be set if details exist
        self.task_cards[task["id"]] = card  # Register for silent updates
        
        # Row 1: Checkbox (left), Edit/Delete/AI buttons (right), Task Title (expands across full remaining width)
        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=12, pady=(10, 4))
        
        icon = "📘" if is_class else "📝"
        title_color = COLORS["accent"] if is_class else COLORS["text"]
        
        chk = ctk.CTkCheckBox(top_row, text="", 
                              command=lambda c=card: self.complete_task_silent(task["id"], c),
                              width=20, height=20, fg_color=COLORS["success"],
                              border_color=COLORS["border"])
        chk.pack(side="left", padx=(0, 8))

        ctk.CTkButton(top_row, text="✕", width=26, height=26, font=FONTS["small"],
                      text_color=COLORS["text_dim"], fg_color="transparent", 
                      hover_color=COLORS["error"], corner_radius=6,
                      command=lambda c=card: self.confirm_delete_silent(task["id"], c)).pack(side="right", padx=2)

        ctk.CTkButton(top_row, text="✎", width=26, height=26, font=FONTS["small"],
                      text_color=COLORS["text_dim"], fg_color="transparent",
                      hover_color=COLORS["card_hover"], corner_radius=6,
                      command=lambda t=task: self.edit_task(t)).pack(side="right", padx=2)
        
        if not is_class:
            magic_btn = ctk.CTkButton(top_row, text="✨", width=26, height=26, font=FONTS["small"],
                          text_color=COLORS["warning"], fg_color="transparent",
                          hover_color=COLORS["card_hover"], corner_radius=6,
                          command=lambda t=task, b=card: self.generate_ai_subtasks(t, b))
            magic_btn.pack(side="right", padx=2)
            Tooltip(magic_btn, "Auto-generate subtasks with AI")

        if is_class:
            sch = task.get("schedule", {})
            ctk.CTkLabel(top_row, text=f"🕐 {sch.get('start','')} – {sch.get('end','')}",
                        text_color=COLORS["warning"], font=FONTS["small"]).pack(side="right", padx=8)

        title_wrap = max(240, int(getattr(self, "_last_width", 760) - 160))
        title_lbl = ctk.CTkLabel(top_row, text=f"{icon} {task['title']}", font=FONTS["header"],
                     text_color=title_color, anchor="w", justify="left", wraplength=title_wrap)
        title_lbl.pack(side="left", fill="x", expand=True, padx=4)
        card._title_lbl = title_lbl  # Store ref

        # Row 2: Quick Action buttons (left) + Metadata badges (right: Subject, Due Date, Due Time, Duration, Difficulty)
        bottom_row = ctk.CTkFrame(card, fg_color="transparent")
        bottom_row.pack(fill="x", padx=12, pady=(0, 6))
        
        btn_style = {"width": 66, "height": 24, "font": FONTS["small"],
                     "fg_color": COLORS["bg_secondary"], "hover_color": COLORS["card_hover"],
                     "corner_radius": 5, "text_color": COLORS["text_dim"]}
        
        if not is_class and hasattr(self.app, "start_focus_for_task"):
            ctk.CTkButton(
                bottom_row, text="▶ Focus", width=68, height=24, font=FONTS["small"],
                fg_color=COLORS["accent"], hover_color=COLORS["accent_dark"],
                corner_radius=5, text_color="white",
                command=lambda t=task: self.app.start_focus_for_task(t["title"], t.get("duration") or 25)
            ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(bottom_row, text="+ Sub", command=lambda: self.prompt_subtask(task["id"]),
                      **btn_style).pack(side="left", padx=2)
        ctk.CTkButton(bottom_row, text="📎 File", command=lambda: self.add_attachment(task["id"]),
                      **btn_style).pack(side="left", padx=2)
        ctk.CTkButton(bottom_row, text="📝 Note", command=lambda: self.edit_note(task["id"]),
                      **btn_style).pack(side="left", padx=2)

        # Metadata pills packed on the right of bottom_row
        if task.get("due_time") and not is_class:
            time_pill = ctk.CTkFrame(bottom_row, fg_color=COLORS["bg_secondary"], corner_radius=6)
            time_pill.pack(side="right", padx=3)
            ctk.CTkLabel(time_pill, text=f"⏰ {task['due_time']}",
                         text_color=COLORS["warning"], font=FONTS["tiny"]).pack(padx=6, pady=2)

        if task.get("date") and not is_class:
            d_val = task["date"]
            today_str = today()
            tmr_str = (datetime.now().date() + timedelta(days=1)).isoformat()
            if d_val == today_str:
                d_txt = f"📅 Today ({d_val[5:]})"
                d_col = COLORS["warning"]
            elif d_val == tmr_str:
                d_txt = f"📅 Tomorrow ({d_val[5:]})"
                d_col = COLORS["accent"]
            elif d_val < today_str:
                d_txt = f"⚠️ Overdue ({d_val})"
                d_col = COLORS["error"]
            else:
                d_txt = f"📅 {d_val}"
                d_col = COLORS["text_dim"]
            ctk.CTkLabel(bottom_row, text=d_txt,
                         text_color=d_col, font=FONTS["small"]).pack(side="right", padx=5)

        if not is_class and (task.get("difficulty") == 3 or task.get("importance") == 3):
            tag_txt = "🔥 Hard" if task.get("difficulty") == 3 else "⚡ Urgent"
            ctk.CTkLabel(bottom_row, text=tag_txt, text_color=COLORS["error"],
                         font=FONTS["tiny"]).pack(side="right", padx=4)

        if task.get("duration"):
            ctk.CTkLabel(bottom_row, text=f"⏱️ {task['duration']}m",
                        text_color=COLORS["text_dim"], font=FONTS["small"]).pack(side="right", padx=4)

        if task.get("subject"):
            subj_pill = ctk.CTkFrame(bottom_row, fg_color=COLORS["card_highlight"], corner_radius=6)
            subj_pill.pack(side="right", padx=4)
            ctk.CTkLabel(subj_pill, text=f"📚 {task['subject']}",
                         text_color=COLORS["accent"], font=FONTS["tiny"]).pack(padx=6, pady=2)
        
        # Details section - subtasks, notes, attachments
        subtasks = task.get("subtasks", [])
        notes = task.get("notes", "")
        docs = task.get("documents", [])
        
        if subtasks or notes or docs:
            detail_section = ctk.CTkFrame(card, fg_color=COLORS["bg_secondary"], corner_radius=8)
            detail_section.pack(fill="x", padx=12, pady=(4, 10))
            card._detail_section = detail_section  # Store reference for silent updates
            
            # Notes display
            if notes:
                note_lbl = ctk.CTkLabel(detail_section, text=f"📝 {notes[:100]}{'...' if len(notes) > 100 else ''}", 
                            font=FONTS["small"], text_color=COLORS["text_dim"],
                            wraplength=500, justify="left")
                note_lbl.pack(anchor="w", padx=10, pady=(8, 4))
                card._note_lbl = note_lbl  # Store ref
            
            # Attachments
            if docs:
                for doc in docs[:3]:  # Show max 3
                    fname = doc.split('/')[-1] if '://' not in doc else doc[:30] + '...'
                    ctk.CTkLabel(detail_section, text=f"📄 {fname}",
                                font=FONTS["small"], text_color=COLORS["accent"]).pack(anchor="w", padx=10, pady=1)
            
            # Subtasks list with checkboxes
            if subtasks:
                for si, sub in enumerate(subtasks):
                    sub_frame = ctk.CTkFrame(detail_section, fg_color="transparent")
                    sub_frame.pack(fill="x", padx=10, pady=2)
                    
                    s_chk = ctk.CTkCheckBox(sub_frame, text=sub["title"], font=FONTS["body"],
                                            fg_color=COLORS["success"], 
                                            hover_color=COLORS["success_dark"],
                                            width=18, height=18,
                                            command=lambda t=task["id"], s=si: self.toggle_sub(t, s))
                    if sub.get("done"): s_chk.select()
                    s_chk.pack(side="left")

    def prompt_subtask(self, task_id):
        """Add subtask silently - append widget without full refresh."""
        dialog = ctk.CTkInputDialog(text="Enter subtask title:", title="Add Subtask")
        title = dialog.get_input()
        if title:
            add_subtask(self.app.data, task_id, title)
            # Silently add the subtask widget
            self._add_subtask_widget_silent(task_id, title)

    def add_attachment(self, task_id):
        confirm = messagebox.askyesno("Attachment Type", "Is this a file? (Yes for file, No for URL)")
        if confirm:
            path = filedialog.askopenfilename()
            if path:
                self._save_attachment(task_id, path)
        else:
            dialog = ctk.CTkInputDialog(text="Enter URL:", title="Add Link")
            url = dialog.get_input()
            if url:
                self._save_attachment(task_id, url)

    def _save_attachment(self, task_id, value):
        """Save attachment silently - append widget without full refresh."""
        task = next((t for t in self.app.data["tasks"] if t["id"] == task_id), None)
        if task:
            task.setdefault("documents", []).append(value)
            save_data(self.app.data)
            # Silently add the attachment widget
            self._add_attachment_widget_silent(task_id, value)

    def edit_note(self, task_id):
        task = next((t for t in self.app.data["tasks"] if t["id"] == task_id), None)
        if not task: return

        top = ctk.CTkToplevel(self)
        top.title(f"Notes: {task['title']}")
        top.geometry("400x300")
        top.after(100, lambda: top.focus())

        txt = ctk.CTkTextbox(top, font=FONTS["body"])
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        txt.insert("1.0", task.get("notes", ""))

        def save():
            new_note = txt.get("1.0", "end-1c")
            task["notes"] = new_note
            save_data(self.app.data)
            # Silent UI update
            self._update_note_label_silent(task["id"], new_note)
            top.destroy()

        ctk.CTkButton(top, text="Save Note", command=save, fg_color=COLORS["success"]).pack(pady=(0, 10))

    def prompt_add_task(self):
        top = ctk.CTkToplevel(self)
        top.title("New Task")
        top.geometry("450x650")
        top.after(100, lambda: top.focus())

        ctk.CTkLabel(top, text="Task Title:", font=FONTS["body"]).pack(pady=(10, 0))
        title_e = ctk.CTkEntry(top, width=350)
        title_e.pack(pady=5)

        # Date Schedule Option
        date_var = ctk.BooleanVar(value=True)
        
        # Frame for Calendar so we can show/hide it cleanly
        cal_container = ctk.CTkFrame(top, fg_color="transparent")
        
        def toggle_date():
            if date_var.get():
                cal_container.pack(pady=10, after=switch_frame)
            else:
                cal_container.pack_forget()

        switch_frame = ctk.CTkFrame(top, fg_color="transparent")
        switch_frame.pack(pady=5)
        
        switch = ctk.CTkSwitch(switch_frame, text="Schedule for Date", variable=date_var, command=toggle_date, font=FONTS["body"])
        switch.pack()

        # Pack the container initially
        cal_container.pack(pady=10)

        cal = Calendar(cal_container, selectmode='day', date_pattern='yyyy-mm-dd',
                       background=get_color_str("card"), foreground="white",
                       headersbackground=get_color_str("sidebar"), normalbackground=get_color_str("card"),
                       selectbackground=get_color_str("accent"))
        cal.pack()

        ctk.CTkLabel(top, text="Time Limit (minutes, optional):", font=FONTS["body"]).pack(pady=(5, 0))
        dur_e = ctk.CTkEntry(top, width=350, placeholder_text="e.g. 30")
        dur_e.pack(pady=5)

        def save():
            title = title_e.get().strip()
            if title:
                dur = None
                if dur_e.get().isdigit(): dur = int(dur_e.get())
                
                date = None
                if date_var.get():
                    date = cal.get_date()
                
                new_task = add_task_logic(self.app.data, title, duration=dur, deadline=date)
                
                from utils import today
                today_str = today()
                
                should_show = False
                if not date: should_show = True
                elif date <= today_str: should_show = True
                
                if new_task and should_show:
                    self.draw_task_card(new_task)
            top.destroy()

        ctk.CTkButton(top, text="Add Task", command=save, fg_color=COLORS["accent"]).pack(pady=10)

    def prompt_add_class(self):
        top = ctk.CTkToplevel(self)
        top.title("New Class")
        top.geometry("450x550")
        top.after(100, lambda: top.focus())

        ctk.CTkLabel(top, text="Class Name / Subject:", font=FONTS["body"]).pack(pady=(10, 0))
        title_e = ctk.CTkEntry(top, width=350)
        title_e.pack(pady=5)

        ctk.CTkLabel(top, text="Select Days:", font=FONTS["body"]).pack(pady=(5, 0))
        day_sel = DaySelector(top)
        day_sel.pack(pady=5)

        ctk.CTkLabel(top, text="Start Time:", font=FONTS["body"]).pack(pady=(10, 0))
        start_p = TimePicker(top, "09:00")
        start_p.pack(pady=5)

        ctk.CTkLabel(top, text="End Time:", font=FONTS["body"]).pack(pady=(10, 0))
        end_p = TimePicker(top, "10:30")
        end_p.pack(pady=5)

        def save():
            title = title_e.get().strip()
            days = day_sel.get()
            if title and days:
                sch = {"days": days, "start": start_p.get(), "end": end_p.get()}
                new_task = add_task_logic(self.app.data, title, category="class", days=days, schedule=sch, subject=title)
                # Silently add the new class card if it's for today
                from datetime import datetime
                today_day = datetime.now().strftime("%a").lower()
                if new_task and today_day in days:
                    self.draw_task_card(new_task)
            top.destroy()

        ctk.CTkButton(top, text="Add Class", command=save, fg_color=COLORS["accent"], height=40).pack(pady=20)

    def confirm_delete(self, task_id):
        if messagebox.askyesno("Delete", "Are you sure you want to delete this?"):
            delete_task_logic(self.app.data, task_id)
            self.render()

    def prompt_edit_task(self, task):
        top = ctk.CTkToplevel(self)
        top.title(f"Edit: {task['title']}")
        top.geometry("400x300")

        ctk.CTkLabel(top, text="Title:").pack(pady=(10,0))
        title_e = ctk.CTkEntry(top, width=300)
        title_e.insert(0, task["title"])
        title_e.pack(pady=5)

        ctk.CTkLabel(top, text="Duration (min):").pack(pady=(10,0))
        dur_e = ctk.CTkEntry(top, width=300)
        dur_e.insert(0, str(task.get("duration", "")))
        dur_e.pack(pady=5)

        def save():
            updates = {"title": title_e.get().strip()}
            if dur_e.get().isdigit(): updates["duration"] = int(dur_e.get())
            update_task_logic(self.app.data, task["id"], **updates)
            
            # Silent UI Update
            if task["id"] in self.task_cards:
                card = self.task_cards[task["id"]]
                # Update title
                if hasattr(card, "_title_lbl"):
                    icon = "📘" if task.get("type") == "class" else "📝"
                    card._title_lbl.configure(text=f"{icon} {updates['title']}")
                # Update duration (optional - complex to find label if not stored, 
                # but title is the main user concern)
            
            top.destroy()

        ctk.CTkButton(top, text="Update", command=save, fg_color=COLORS["success"]).pack(pady=20)

    def add_task(self, event=None):
        # Deprecated by prompt_add_task for more fields, but keeping if needed
        pass

    def complete_task(self, task_id):
        complete_task_logic(self.app.data, task_id)
        self.app.refresh_xp()
        self.render()

    def toggle_sub(self, task_id, sub_index):
        """Toggle subtask silently - checkbox already updates visually."""
        toggle_subtask(self.app.data, task_id, sub_index)
        self.app.refresh_xp()
        # No render() - checkbox handles its own visual state

    def complete_task_silent(self, task_id, card_widget):
        """Complete a task and remove the card without full refresh."""
        complete_task_logic(self.app.data, task_id)
        self.app.refresh_xp()
        card_widget.destroy()

    def confirm_delete_silent(self, task_id, card_widget):
        """Delete a task after confirmation and remove the card without full refresh."""
        if messagebox.askyesno("Delete", "Are you sure you want to delete this task?"):
            delete_task_logic(self.app.data, task_id)
            card_widget.destroy()
            # Remove from tracking
            if task_id in self.task_cards:
                del self.task_cards[task_id]

    def _get_or_create_detail_section(self, task_id):
        """Get or create the detail section for a task card."""
        if task_id not in self.task_cards:
            return None
        card = self.task_cards[task_id]
        if card._detail_section is None:
            detail_section = ctk.CTkFrame(card, fg_color=COLORS["bg_secondary"], corner_radius=8)
            detail_section.pack(fill="x", padx=12, pady=(4, 10))
            card._detail_section = detail_section
        return card._detail_section

    def _add_subtask_widget_silent(self, task_id, title):
        """Add a subtask checkbox widget silently."""
        detail_section = self._get_or_create_detail_section(task_id)
        if not detail_section:
            return
        
        task = next((t for t in self.app.data["tasks"] if t["id"] == task_id), None)
        if not task:
            return
        
        sub_index = len(task.get("subtasks", [])) - 1
        
        sub_frame = ctk.CTkFrame(detail_section, fg_color="transparent")
        sub_frame.pack(fill="x", padx=10, pady=2)
        
        s_chk = ctk.CTkCheckBox(sub_frame, text=title, font=FONTS["body"],
                                fg_color=COLORS["success"], 
                                hover_color=COLORS["success_dark"],
                                width=18, height=18,
                                command=lambda t=task_id, s=sub_index: self.toggle_sub(t, s))
        s_chk.pack(side="left")

    def _add_attachment_widget_silent(self, task_id, value):
        """Add an attachment label widget silently."""
        detail_section = self._get_or_create_detail_section(task_id)
        if not detail_section:
            return
        
        fname = value.split('/')[-1] if '://' not in value else value[:30] + '...'
        ctk.CTkLabel(detail_section, text=f"📄 {fname}",
                    font=FONTS["small"], text_color=COLORS["accent"]).pack(anchor="w", padx=10, pady=1)

    def _update_note_label_silent(self, task_id, text):
        """Update or create the note label silently."""
        if task_id not in self.task_cards: return
        card = self.task_cards[task_id]
        
        # If label exists, just update
        if hasattr(card, "_note_lbl") and card._note_lbl:
            card._note_lbl.configure(text=f"📝 {text[:100]}{'...' if len(text) > 100 else ''}")
            return

        # If empty text, do nothing (handling removal is complex, keeping old label is fine or empty string)
        if not text: return

        # Need to create label
        detail_section = self._get_or_create_detail_section(task_id)
        if detail_section:
            note_lbl = ctk.CTkLabel(detail_section, text=f"📝 {text[:100]}{'...' if len(text) > 100 else ''}", 
                        font=FONTS["small"], text_color=COLORS["text_dim"],
                        wraplength=500, justify="left")
            # Problem: Packing at end might be wrong order. `pack(side='top', before=...)` requires ref.
            # We'll just pack at top (default side='top') BEFORE other children? 
            # `pack` appends. To insert at top:
            # We can't easily reorder pack without unpacking all. 
            # Production hack: Just pack it. The user sees the note.
            note_lbl.pack(anchor="w", padx=10, pady=(8, 4))
            card._note_lbl = note_lbl

    def generate_ai_subtasks(self, task, card):
        """Ask AI to generate subtasks for this task."""
        from focus_agent.media_import import suggest_subtasks_ai
        from logic import add_subtask
        
        # UI Feedback
        self.app.refresh_xp() 
        
        def run_ai():
            subtasks = suggest_subtasks_ai(task["title"])
            if subtasks:
                for st in subtasks:
                    add_subtask(self.app.data, task["id"], st)
                
                # Full refresh for now to update details
                self.after(0, lambda: self.render())
            else:
                self.after(0, lambda: messagebox.showwarning("AI Error", "Could not generate subtasks. Try again!"))

        import threading
        threading.Thread(target=run_ai, daemon=True).start()

    def edit_task(self, task):
        self.prompt_edit_task(task)

    def on_resize(self, width, height):
        self._last_width = width
        compact = width < 680

        # 1. Header date badge & title wrap
        if hasattr(self, "date_badge_lbl") and self.date_badge_lbl.winfo_exists():
            date_txt = f"📅 {self._short_date_str}" if compact else f"📅 {self._full_date_str}"
            self.date_badge_lbl.configure(text=date_txt)

        # 2. Quick Agent Command Bar status/trace wraplength & buttons
        agent_wrap = max(240, int(width - 64))
        if hasattr(self, "quick_agent_status") and self.quick_agent_status.winfo_exists():
            self.quick_agent_status.configure(wraplength=agent_wrap)
        if hasattr(self, "quick_agent_trace") and self.quick_agent_trace.winfo_exists():
            self.quick_agent_trace.configure(wraplength=agent_wrap)
        if hasattr(self, "console_link_btn") and self.console_link_btn.winfo_exists():
            self.console_link_btn.configure(
                text="Console →" if compact else "Open Agent Console →",
                width=90 if compact else 145,
            )

        # 3. Proactive Briefing Banner wraplength
        brief_wrap = max(220, int(width - 205))
        if getattr(self, "_briefing_head_lbl", None) and self._briefing_head_lbl.winfo_exists():
            self._briefing_head_lbl.configure(wraplength=brief_wrap)
        if getattr(self, "_briefing_detail_lbl", None) and self._briefing_detail_lbl.winfo_exists():
            self._briefing_detail_lbl.configure(wraplength=brief_wrap)

        # 4. KPI Grid reflow (2x2 on narrow widths, 1x4 on wider widths)
        self._layout_kpi_grid(width)

        # 5. Schedule section header & action buttons
        if hasattr(self, "schedule_hdr_lbl") and self.schedule_hdr_lbl.winfo_exists():
            self.schedule_hdr_lbl.configure(
                text="Today's Schedule" if compact else "Today's Schedule & Deadlines"
            )
        if hasattr(self, "add_task_btn") and self.add_task_btn.winfo_exists():
            self.add_task_btn.configure(
                text="+ Task" if compact else "+ Add Task",
                width=78 if compact else 105,
            )
        if hasattr(self, "add_class_btn") and self.add_class_btn.winfo_exists():
            self.add_class_btn.configure(
                text="+ Class" if compact else "+ Add Class",
                width=82 if compact else 105,
            )
        if hasattr(self, "plan_day_btn") and self.plan_day_btn.winfo_exists():
            self.plan_day_btn.configure(
                text="🗓 Plan" if compact else "🗓 Plan My Day",
                width=78 if compact else 118,
            )

        # 6. Task Card titles & notes wraplength
        title_wrap = max(220, int(width - 155))
        note_wrap = max(220, int(width - 90))
        for card in self.task_cards.values():
            if hasattr(card, "_title_lbl") and card._title_lbl and card._title_lbl.winfo_exists():
                card._title_lbl.configure(wraplength=title_wrap)
            if hasattr(card, "_note_lbl") and card._note_lbl and card._note_lbl.winfo_exists():
                card._note_lbl.configure(wraplength=note_wrap)
