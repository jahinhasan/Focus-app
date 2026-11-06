"""app - split from ui.py (Focus Agent V2, Phase 6)."""

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
from .theme import COLORS, FONTS, init_responsive_fonts, scale_fonts_for_window
from .widgets import SidebarButton, XPBar
from .views_today import TodayView
from .views_routine import RoutineView
from .views_history import HistoryView, ReportView
from .views_settings import SettingsView
from .views_chat import ChatView
from .views_planner import PlannerView
from .views_goals import GoalsView
from .views_misc import HabitView, VaultView


class FocusApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        init_responsive_fonts()

        self.title("Focus App")
        # Window Setup
        self.title("Focus Dashboard")
        self.center_window()
        self.minsize(720, 480)
        self.configure(fg_color=COLORS["bg"])

        self.data = load_data()

        # Respect saved appearance mode, defaulting to crisp Light academic theme
        saved_theme = (self.data.get("settings") or {}).get("theme", "Light")
        if saved_theme in ("Light", "Dark"):
            ctk.set_appearance_mode(saved_theme)
        else:
            ctk.set_appearance_mode("Light")
        
        # Run Automation
        process_daily_automation(self.data)
        
        self.active_view = None  # Will be set by switch_view

        # Timer State - RESTORED FROM PERSISTENCE
        saved_state = self.data.get("timer_state", {})
        self.timer_seconds = saved_state.get("seconds", 0)
        self.timer_mode = saved_state.get("mode", "focus")
        self.active_class_id = saved_state.get("class_id", None)
        
        self.timer_running = False # Initial state
        self.last_tick = None

        if saved_state.get("is_running"):
            try:
                last_tick_iso = saved_state.get("last_tick")
                if last_tick_iso:
                    last_tick_dt = datetime.fromisoformat(last_tick_iso)
                    elapsed_since_closed = (datetime.now() - last_tick_dt).total_seconds()
                    
                    style = self.data.get("settings", {}).get("timer_style", "stopwatch")
                    if style == "stopwatch":
                        self.timer_seconds += elapsed_since_closed
                    else: # Countdown
                        self.timer_seconds -= elapsed_since_closed
                        if self.timer_seconds < 0: self.timer_seconds = 0
                    
                    # Auto-start if it was running
                    self.after(500, self.start_timer)
            except Exception as e:
                print(f"Error resuming timer: {e}")

        # Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar_width = 230
        self.sidebar_collapsed = False
        self._user_toggled_sidebar = False
        self.sidebar = ctk.CTkFrame(
            self, width=self.sidebar_width, fg_color=COLORS["sidebar"],
            corner_radius=0, border_width=1, border_color=COLORS["border"]
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.setup_sidebar()

        # Main content
        self.main_container = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        self.main_container.grid(row=0, column=1, sticky="nsew")

        self.top_bar = XPBar(self.main_container, self.data, app=self)
        self.top_bar.pack(fill="x")

        self.view_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.view_container.pack(fill="both", expand=True, padx=14, pady=(4, 10))

        self.views = {}
        self.init_views()
        self.switch_view("today")

        # Setup keyboard shortcuts
        self.setup_keyboard_shortcuts()
        
        # Enable mouse scrolling globally
        self.bind_mouse_scroll()

        # Responsive window resize handling (debounced)
        self._resize_job = None
        self._last_size = (0, 0)
        self.bind("<Configure>", self._on_window_resize)
        self.after(120, lambda: self._apply_responsive_layout(self.winfo_width() or 1080, self.winfo_height() or 700))
        
        self.update_clock()

    def _on_window_resize(self, event):
        if event.widget is not self:
            return
        w, h = event.width, event.height
        if abs(w - self._last_size[0]) < 8 and abs(h - self._last_size[1]) < 8:
            return
        self._last_size = (w, h)
        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.after(50, lambda: self._apply_responsive_layout(w, h))

    def _apply_responsive_layout(self, width, height):
        self._resize_job = None
        if getattr(self, "zen_active", False):
            return

        # 1. Dynamically scale all reactive CTkFont objects across the entire app
        scale_fonts_for_window(width, height)

        compact_w = width < 940
        very_short_h = height < 610
        compact_h = height < 700

        # 2. Target sidebar width (ALWAYS wide enough for icon + readable name)
        if width < 840:
            target_sb = 172
        elif width < 1100:
            target_sb = 202
        else:
            target_sb = 232

        if target_sb != self.sidebar_width:
            self.sidebar_width = target_sb
            self.sidebar.configure(width=target_sb)

        # 3. Adapt Brand Header (keep name visible, hide V2 pill only on narrow widths)
        self.brand_frame.pack_configure(padx=10 if compact_w else 12, pady=(8 if compact_h else 12, 4))
        if not compact_w:
            self.v2_pill.pack(side="right", padx=(2, 0))
        else:
            self.v2_pill.pack_forget()
        self.brand_lbl.pack(side="left")

        # 4. Adapt Clock & Date Section
        self.clock_section.pack_configure(padx=8 if compact_w else 10, pady=(2 if compact_h else 4, 6))
        self.clock_lbl.pack_configure(pady=(4 if compact_h else 6, 0))
        if very_short_h:
            self.date_lbl.pack_forget()
        else:
            self.date_lbl.pack(pady=(0, 5))

        # 5. Adapt Timer Card
        self.timer_frame.pack_configure(padx=8 if compact_w else 10, pady=(0, 6 if compact_h else 8))
        if very_short_h:
            self.timer_header.pack_forget()
        else:
            self.timer_header.pack(fill="x", padx=10, pady=(6, 0), before=self.timer_lbl)
        self.timer_lbl.pack_configure(pady=2 if compact_h else 3)
        self.timer_btns.pack_configure(padx=8 if compact_w else 10, pady=(0, 6 if compact_h else 8))
        btn_h_timer = 28 if compact_h else 32
        ctrl_txt = "⏸ Pause" if self.timer_running else ("▶ Resume" if self.timer_seconds > 0 else "▶ Start")
        self.timer_ctrl.configure(text=ctrl_txt, height=btn_h_timer)
        self.stop_btn.configure(height=btn_h_timer, width=30 if compact_w else 32)

        # 6. Adapt Navigation Section & Buttons (always icon + text)
        if very_short_h:
            self.nav_label.pack_forget()
        else:
            self.nav_label.pack(anchor="w", padx=14, pady=(2, 2), before=self.nav_container)

        nav_btn_h = 28 if very_short_h else (32 if compact_h else 36)
        nav_pad_y = 1 if compact_h else 2
        nav_pad_x = 6 if compact_w else 8
        for btn in self.nav_buttons.values():
            btn.set_responsive_mode(
                compact_text=compact_w,
                btn_height=nav_btn_h,
            )
            btn.pack_configure(padx=nav_pad_x, pady=nav_pad_y)

        # 7. Adjust main view container padding & notify top_bar + active view
        pad_x = 8 if width < 860 else 14
        self.view_container.pack_configure(padx=pad_x, pady=(4, 8))
        content_w = max(380, width - target_sb - 2 * pad_x)

        if hasattr(self, "top_bar") and hasattr(self.top_bar, "on_resize"):
            try:
                self.top_bar.on_resize(content_w)
            except Exception:
                pass

        view = self.views.get(self.active_view)
        if view and hasattr(view, "on_resize"):
            try:
                view.on_resize(content_w, height)
            except Exception:
                pass
    
    def setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for navigation and actions."""
        # View navigation (1-6 keys)
        
        # Quick actions
        self.bind("<Control-n>", lambda e: self.quick_add_task())
        self.bind("<Control-N>", lambda e: self.quick_add_task())
        self.bind("<Control-q>", lambda e: self.quit())
        self.bind("<Control-Q>", lambda e: self.quit())
        self.bind("<Escape>", lambda e: self.focus_set())  # Clear focus
        
        # Timer controls (Ctrl+T only — never bind bare <space> as it triggers while typing in inputs)
        self.bind("<Control-t>", lambda e: self.toggle_timer())
        self.bind("<Control-T>", lambda e: self.toggle_timer())
    
    def quick_add_task(self):
        """Quick action to add a new task."""
        if hasattr(self.views.get("today"), "prompt_add_task"):
            self.switch_view("today")
            self.views["today"].prompt_add_task()
    
    def bind_mouse_scroll(self):
        """Enable mouse scroll wheel on Linux."""
        # Linux scroll events
        self.bind_all("<Button-4>", self._on_scroll_up)
        self.bind_all("<Button-5>", self._on_scroll_down)
        # Windows/Mac scroll events  
        self.bind_all("<MouseWheel>", self._on_mousewheel)
    
    def _on_scroll_up(self, event):
        """Handle scroll up (Linux Button-4)."""
        widget = event.widget
        # Find parent scrollable frame
        while widget:
            if hasattr(widget, '_parent_canvas'):
                widget._parent_canvas.yview_scroll(-3, "units")
                return
            widget = widget.master if hasattr(widget, 'master') else None
    
    def _on_scroll_down(self, event):
        """Handle scroll down (Linux Button-5)."""
        widget = event.widget
        while widget:
            if hasattr(widget, '_parent_canvas'):
                widget._parent_canvas.yview_scroll(3, "units")
                return
            widget = widget.master if hasattr(widget, 'master') else None
    
    def _on_mousewheel(self, event):
        """Handle mouse wheel scroll (Windows/Mac)."""
        widget = event.widget
        while widget:
            if hasattr(widget, '_parent_canvas'):
                widget._parent_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                return
            widget = widget.master if hasattr(widget, 'master') else None

    def setup_sidebar(self):
        """Setup responsive sidebar that always keeps icon + readable label visible."""
        # Brand header
        self.brand_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.brand_frame.pack(fill="x", padx=12, pady=(12, 4))

        self.v2_pill = ctk.CTkFrame(self.brand_frame, fg_color=COLORS["card_highlight"], corner_radius=6)
        self.v2_pill.pack(side="right", padx=(2, 0))
        ctk.CTkLabel(self.v2_pill, text="V2 AI", font=FONTS["tiny"], text_color=COLORS["accent"]).pack(padx=6, pady=2)

        self.brand_lbl = ctk.CTkLabel(
            self.brand_frame, text="✦ Focus Agent", font=FONTS["brand"],
            text_color=COLORS["accent"]
        )
        self.brand_lbl.pack(side="left")

        # Clock + Date section with clean border
        self.clock_section = ctk.CTkFrame(
            self.sidebar, fg_color=COLORS["bg_secondary"], corner_radius=12,
            border_width=1, border_color=COLORS["border"]
        )
        self.clock_section.pack(fill="x", padx=10, pady=(4, 6))
        
        self.clock_lbl = ctk.CTkLabel(self.clock_section, text="00:00", font=FONTS["clock"],
                                       text_color=COLORS["text"])
        self.clock_lbl.pack(pady=(6, 0))

        self.date_lbl = ctk.CTkLabel(self.clock_section, text="Date", text_color=COLORS["text_dim"],
                                      font=FONTS["small"])
        self.date_lbl.pack(pady=(0, 6))

        # Timer Frame
        self.timer_frame = ctk.CTkFrame(self.sidebar, fg_color=COLORS["card"], corner_radius=12,
                                        border_width=1, border_color=COLORS["border"])
        self.timer_frame.pack(side="top", fill="x", padx=10, pady=(0, 8))

        self.timer_header = ctk.CTkFrame(self.timer_frame, fg_color="transparent")
        self.timer_header.pack(fill="x", padx=10, pady=(6, 0))
        
        self.timer_mode_lbl = ctk.CTkLabel(self.timer_header, text="🎯 Focus Session",
                                           text_color=COLORS["success"], font=FONTS["small"])
        self.timer_mode_lbl.pack(side="left")

        self.timer_lbl = ctk.CTkLabel(self.timer_frame, text="00:00:00", font=FONTS["timer"],
                                       text_color=COLORS["text"])
        self.timer_lbl.pack(pady=3)

        self.timer_btns = ctk.CTkFrame(self.timer_frame, fg_color="transparent")
        self.timer_btns.pack(fill="x", padx=10, pady=(0, 8))

        self.timer_ctrl = ctk.CTkButton(self.timer_btns, text="▶ Start", height=32,
                                        fg_color=COLORS["accent"], hover_color=COLORS["accent_dark"],
                                        corner_radius=8, font=FONTS["body"],
                                        command=self.toggle_timer)
        self.timer_ctrl.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.stop_btn = ctk.CTkButton(self.timer_btns, text="⏹", width=32, height=32,
                                      fg_color=COLORS["error"], hover_color="#B91C1C",
                                      corner_radius=8, font=FONTS["subheader"],
                                      state="disabled",
                                      command=lambda: self.stop_timer(log=True))
        self.stop_btn.pack(side="right")
        
        # Navigation section
        self.nav_label = ctk.CTkLabel(self.sidebar, text="WORKSPACE", font=FONTS["tiny"],
                                      text_color=COLORS["text_muted"])
        self.nav_label.pack(anchor="w", padx=14, pady=(2, 2))

        # Zen Mode Toggle (If unlocked) - Packed at bottom
        zen_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        zen_frame.pack(side="bottom", fill="x", padx=10, pady=6)
        
        if is_unlocked(self.data, "zen_mode"):
             ctk.CTkButton(zen_frame, text="🧘 Zen Mode", fg_color=COLORS["accent"],
                           hover_color=COLORS["accent_dark"],
                           command=self.toggle_zen_mode).pack(fill="x")

        # Clean non-scrollbar navigation container so no scrollbar steals horizontal space
        self.nav_container = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_container.pack(fill="both", expand=True, padx=0, pady=(0, 4))
        
        self.nav_buttons = {}
        items = [
            ("🏠 Dashboard", "🏠 Dashboard", "today"),
            ("🤖 AI Agent Console", "🤖 AI Agent", "assistant"),
            ("🗓️ Daily Planner", "🗓️ Planner", "planner"),
            ("📅 Class Routine", "📅 Routine", "routine"),
            ("🎯 Goals & Roadmaps", "🎯 Goals", "goals"),
            ("📚 Subject Vault", "📚 Vault", "vault"),
            ("📊 Analytics & Insights", "📊 Analytics", "report"),
            ("⚙️ Settings", "⚙️ Settings", "settings")
        ]
        for full_txt, short_txt, key in items:
            btn = SidebarButton(
                self.nav_container, text=full_txt, short_text=short_txt,
                command=lambda k=key: self.switch_view(k)
            )
            btn.pack(fill="x", padx=8, pady=2)
            self.nav_buttons[key] = btn

    def init_views(self):
        # Lazy loading: store view classes, create instances on first access
        self.view_classes = {
            "today": TodayView,
            "routine": RoutineView,
            "planner": PlannerView,
            "goals": GoalsView,
            "habits": HabitView,
            "vault": VaultView,
            "history": ReportView,
            "report": ReportView,
            "assistant": ChatView,
            "settings": SettingsView,
        }
        self.views = {}  # Instances will be created on demand
        
    def _get_view(self, name):
        """Lazy load view - only create when first accessed."""
        if name not in self.views:
            if name in self.view_classes:
                self.views[name] = self.view_classes[name](self.view_container, self)
                self.views[name].pack_forget()
        return self.views.get(name)

    def switch_view(self, name):
        """Switch to a view and update navigation styling with lazy loading."""
        if name not in self.view_classes: return
        if self.active_view == name: return  # View guard

        # Hide all existing views
        for v in self.views.values(): v.pack_forget()
        
        # Lazy load the requested view
        view = self._get_view(name)
        if view:
            view.pack(fill="both", expand=True)

            # Use the enhanced set_active method
            for k, b in self.nav_buttons.items():
                b.set_active(k == name)

            self.active_view = name
            if hasattr(view, "render"): view.render()
            if hasattr(view, "on_resize"):
                try:
                    w = self.winfo_width() or 1050
                    h = self.winfo_height() or 700
                    view.on_resize(max(400, w - self.sidebar_width - 32), h)
                except Exception:
                    pass

    def refresh_xp(self):
        self.top_bar.render()

    def update_clock(self):
        now = datetime.now()
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%a, %b %d")
        
        # Only update if strings changed
        if self.clock_lbl.cget("text") != time_str:
            self.clock_lbl.configure(text=time_str)
        if self.date_lbl.cget("text") != date_str:
            self.date_lbl.configure(text=date_str)
        
        # Check active class efficiently
        active = get_active_class(self.data)
        if active:
            status_text = f"🔴 Class: {active['title']}"
            if self.timer_mode_lbl.cget("text") != status_text:
                self.timer_mode_lbl.configure(text=status_text, text_color=COLORS["error"])
            
            if self.timer_mode != "class" or self.active_class_id != active["id"]:
                if self.timer_running: self.stop_timer(log=True)
                self.timer_mode = "class"
                self.active_class_id = active["id"]
                self.start_timer()
        else:
            if self.timer_mode_lbl.cget("text") != "🎯 Focus Session":
                self.timer_mode_lbl.configure(text="🎯 Focus Session", text_color=COLORS["success"])
            if self.timer_mode == "class":
                if self.timer_running: self.stop_timer(log=True)
                self.timer_mode = "focus"
                self.active_class_id = None
        
        # Auto-Attendance Check
        sync_res = sync_class_statuses(self.data)
        ended_classes = sync_res[0] if isinstance(sync_res, tuple) else sync_res
        if ended_classes:
            from logic import mark_class_missed
            for task_id in ended_classes:
                task = get_task_by_id(self.data, task_id)
                if task:
                    if messagebox.askyesno("Class Ended", f"Did you attend '{task['title']}'?"):
                        mark_class_done(self.data, task_id)
                        add_xp(self.data, 20) 
                        self.refresh_xp()
                    else:
                        mark_class_missed(self.data, task_id)

        self.after(1000, self.update_clock)

    def update_timer(self):
        if not self.timer_running: return
        
        now = datetime.now()
        elapsed = (now - self.last_tick).total_seconds()
        
        style = self.data.get("settings", {}).get("timer_style", "stopwatch")

        if style == "countdown":
            self.timer_seconds -= elapsed
            
            if self.timer_seconds <= 0:
                # Auto-Flow Logic
                was_work = (self.active_class_id is not None) or (self.timer_mode == "focus")
                
                self.timer_seconds = 0
                self.stop_timer(log=True) # Logs the finished session
                
                # Switch Modes
                pom = get_pomodoro_settings(self.data)
                
                if was_work:
                    # Work -> Break
                    self.timer_seconds = pom.get("short_break", 5) * 60
                    self.timer_mode = "break" # Internal mode tag
                    msg = "Focus Session Complete! Time for a Break? ☕"
                else:
                    # Break -> Work
                    self.timer_seconds = pom.get("work", 25) * 60
                    self.timer_mode = "focus"
                    msg = "Break is over! Ready to Focus? 🚀"
                
                # Update UI for new state
                self.timer_lbl.configure(text=format_seconds_to_hms(int(self.timer_seconds)))
                
                if messagebox.askyesno("Timer Chain", msg):
                    self.start_timer()
                
                return
        else: # stopwatch
            self.timer_seconds += elapsed

        self.last_tick = now
        
        # Only update the label, avoid full refresh
        self.timer_lbl.configure(text=format_seconds_to_hms(int(self.timer_seconds)))
        
        # Zen Mode Update
        if getattr(self, "zen_active", False) and hasattr(self, "zen_lbl"):
             self.zen_lbl.configure(text=format_seconds_to_hms(int(self.timer_seconds)))
        
        # Pomodoro Check (Stopwatch Only)
        if style == "stopwatch" and not getattr(self, "pomodoro_target_reached", False):
            pom = get_pomodoro_settings(self.data)
            target_sec = pom.get("work", 25) * 60
            if self.timer_seconds >= target_sec:
                self.pomodoro_target_reached = True
                # Visual cue only since sound feature removed
                self.timer_lbl.configure(text_color=COLORS["success"])
                if getattr(self, "zen_active", False):
                    self.zen_lbl.configure(text_color=COLORS["success"])
        
        # Periodic autosave/sync could go here, but we'll log on stop to be accurate.
        # Previously mixed incremental logging was buggy.
        
        self.after(1000, self.update_timer)

    def toggle_timer(self):
        if self.timer_running:
            self.pause_timer()
        else:
            self.start_timer()

    def start_focus_for_task(self, title, duration_minutes=25):
        """Start a focus timer session for a specific task or planner slot."""
        if self.timer_running:
            self.stop_timer(log=True)
        style = self.data.get("settings", {}).get("timer_style", "stopwatch")
        mins = max(5, int(duration_minutes or 25))
        if style == "countdown":
            self.timer_seconds = mins * 60
        else:
            self.timer_seconds = 0
        self.timer_mode = "focus"
        self.active_class_id = None
        short_title = (title or "Focus").strip()[:22]
        self.timer_mode_lbl.configure(text=f"🎯 {short_title}", text_color=COLORS["accent"])
        self.start_timer()

    def start_timer(self):
        # Countdown Init Logic
        style = self.data.get("settings", {}).get("timer_style", "stopwatch")
        
        if style == "countdown" and self.timer_seconds <= 0:
            # Load default duration
            pom = get_pomodoro_settings(self.data)
            self.timer_seconds = pom.get("work", 25) * 60
            self.timer_max = self.timer_seconds # For progress bar if we had one
            
        self.timer_running = True
        self.last_tick = datetime.now()
        if not getattr(self, "session_started_hhmm", None):
            self.session_started_hhmm = self.last_tick.strftime("%H:%M")
        self.timer_ctrl.configure(
            text="⏸" if getattr(self, "sidebar_collapsed", False) else "⏸ Pause",
            fg_color=COLORS["warning"],
        )
        self.stop_btn.configure(state="normal") # Enable stop
        
        # Reset target state for Pomodoro check (Stopwatch mode only)
        self.pomodoro_target_reached = False
        
        # Update Label Mode
        lbl = "⏱ Stopwatch" if style == "stopwatch" else "⏳ Timer"
        if self.timer_mode_lbl.cget("text") != lbl and "Class" not in self.timer_mode_lbl.cget("text"):
             self.timer_mode_lbl.configure(text=lbl)
             
        # Save persistence
        update_timer_state(self.data, self.timer_seconds, self.timer_mode, self.active_class_id, is_running=True)
             
        self.update_timer()

    def pause_timer(self):
        self.timer_running = False
        self.last_tick = None
        self.timer_ctrl.configure(
            text="▶" if getattr(self, "sidebar_collapsed", False) else "▶ Resume",
            fg_color=COLORS["success"],
        )
        update_timer_state(self.data, self.timer_seconds, self.timer_mode, self.active_class_id, is_running=False)

    def stop_timer(self, log=False):
        self.timer_running = False
        started_hhmm = getattr(self, "session_started_hhmm", None)
        if log and self.timer_seconds > 5:
            if self.timer_mode == "class" and self.active_class_id:
                log_class_session(self.data, self.timer_seconds, self.active_class_id)
                log_focus_session(self.data, self.timer_seconds, session_type="class",
                                  started_hhmm=started_hhmm)
            else:
                log_focus_session(self.data, self.timer_seconds, session_type="focus",
                                  started_hhmm=started_hhmm)
            self.refresh_xp()
        
        self.timer_seconds = 0
        self.session_started_hhmm = None
        clear_timer_state(self.data) # Logic Clear
        
        self.timer_lbl.configure(text="00:00:00")
        self.timer_ctrl.configure(
            text="▶" if getattr(self, "sidebar_collapsed", False) else "▶ Start",
            fg_color=COLORS["success"],
        )
        self.stop_btn.configure(state="disabled") # Disable instead of hide
        self.last_tick = None

    def toggle_zen_mode(self):
        self.zen_active = not getattr(self, "zen_active", False)
        
        if self.zen_active:
             # Save current geometry before Zen
             self.last_geometry = self.geometry()
             
             # Enter Zen
             self.geometry("300x130")
             self.overrideredirect(True)
             self.attributes("-topmost", True)
             
             # Hide Main UI
             self.sidebar.grid_remove()
             self.main_container.grid_remove()
             
             # Show Zen Frame
             self.zen_frame = ctk.CTkFrame(self, fg_color=COLORS["bg"])
             self.zen_frame.pack(fill="both", expand=True)
             
             # Header (Drag Handle)
             header = ctk.CTkFrame(self.zen_frame, fg_color="transparent", height=30)
             header.pack(fill="x")
             header.bind("<Button-1>", self.start_move)
             header.bind("<B1-Motion>", self.do_move)
             ctk.CTkLabel(header, text="🧘 Zen Focus", font=FONTS["small"]).pack(side="left", padx=10)
             ctk.CTkButton(header, text="✕", width=30, height=20, fg_color="transparent", 
                           text_color=COLORS["error"], command=self.toggle_zen_mode).pack(side="right", padx=5)
             
             # Timer
             self.zen_lbl = ctk.CTkLabel(self.zen_frame, text=format_seconds_to_hms(int(self.timer_seconds)), 
                                         font=("Arial", 36, "bold"), text_color=COLORS["text"])
             self.zen_lbl.pack(pady=(5, 10))
             
             # Controls
             ctrls = ctk.CTkFrame(self.zen_frame, fg_color="transparent")
             ctrls.pack()
             
             icon = "⏸" if self.timer_running else "▶"
             col = COLORS["warning"] if self.timer_running else COLORS["success"]
             
             self.zen_btn = ctk.CTkButton(ctrls, text=icon, width=60, height=30, fg_color=col,
                                          command=self.zen_toggle_timer)
             self.zen_btn.pack(side="left", padx=5)
             
             ctk.CTkButton(ctrls, text="⏹", width=40, height=30, fg_color=COLORS["error"],
                           command=lambda: self.stop_timer(log=True)).pack(side="left", padx=5)
             
        else:
             # Exit Zen
             if hasattr(self, 'zen_frame'): self.zen_frame.destroy()
             self.overrideredirect(False)
             self.attributes("-topmost", False)
             
             # Restore previous geometry or default to center
             if hasattr(self, 'last_geometry'):
                 self.geometry(self.last_geometry)
             else:
                 self.center_window()
                 
             self.sidebar.grid()
             self.main_container.grid()

    def center_window(self, scale=0.85):
        """Dynamic window sizing based on screen resolution (multi-monitor safe)."""
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Cap to single-monitor dimensions when X11 reports combined multi-head width
        single_w = min(screen_width, 1920)
        single_h = min(screen_height, 1080)
        w = max(1050, int(single_w * scale))
        h = max(700, int(single_h * scale))
        x = int((single_w - w) / 2)
        y = int((single_h - h) / 2)
        
        self.geometry(f"{w}x{h}+{x}+{y}")

    def zen_toggle_timer(self):
        self.toggle_timer()
        # Update button icon
        icon = "⏸" if self.timer_running else "▶"
        col = COLORS["warning"] if self.timer_running else COLORS["success"]
        self.zen_btn.configure(text=icon, fg_color=col)

    def start_move(self, event):
        self.x_start = event.x
        self.y_start = event.y

    def do_move(self, event):
        x = self.winfo_x() + event.x - self.x_start
        y = self.winfo_y() + event.y - self.y_start
        self.geometry(f"+{x}+{y}")

def run_app():
    app = FocusApp()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        print("\nGoodbye! 👋")
        try:
            # Try to save state if needed
            if app.timer_seconds > 0:
                # Save persistence instead of stopping
                # Mode might be focus or class
                update_timer_state(app.data, app.timer_seconds, app.timer_mode, app.active_class_id)
                print(f"Saved timer state: {app.timer_seconds}s")
        except:
            pass

if __name__ == "__main__":
    run_app()
