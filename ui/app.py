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
from ai_parser import format_today_schedule, format_user_stats
# ==================== CONFIG ====================
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Modern Premium Color Palette
from .theme import COLORS, FONTS
from .widgets import SidebarButton, XPBar
from .views_today import TodayView
from .views_routine import RoutineView
from .views_history import HistoryView, ReportView
from .views_settings import SettingsView
from .views_store import StoreView
from .views_chat import ChatView
from .views_planner import PlannerView
from .views_goals import GoalsView
from .views_misc import HabitView, VaultView


class FocusApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Focus App")
        # Window Setup
        self.title("Focus Dashboard")
        self.center_window()
        self.minsize(1000, 600)
        self.configure(fg_color=COLORS["bg"])

        self.data = load_data()
        
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
        self.sidebar = ctk.CTkFrame(self, width=240, fg_color=COLORS["sidebar"], corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.setup_sidebar()

        # Main content
        self.main_container = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        self.main_container.grid(row=0, column=1, sticky="nsew")

        self.top_bar = XPBar(self.main_container, self.data)
        self.top_bar.pack(fill="x")

        self.view_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.view_container.pack(fill="both", expand=True, padx=20, pady=10)

        self.views = {}
        self.init_views()
        self.switch_view("today")

        # Setup keyboard shortcuts
        self.setup_keyboard_shortcuts()
        
        # Enable mouse scrolling globally
        self.bind_mouse_scroll()
        
        self.update_clock()
    
    def setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for navigation and actions."""
        # View navigation (1-6 keys)
        
        # Quick actions
        self.bind("<Control-n>", lambda e: self.quick_add_task())
        self.bind("<Control-N>", lambda e: self.quick_add_task())
        self.bind("<space>", lambda e: self.toggle_timer())
        self.bind("<Control-q>", lambda e: self.quit())
        self.bind("<Control-Q>", lambda e: self.quit())
        self.bind("<Escape>", lambda e: self.focus_set())  # Clear focus
        
        # Timer controls
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
        """Setup enhanced sidebar with modern styling."""
        # Clock section with gradient background
        clock_section = ctk.CTkFrame(self.sidebar, fg_color=COLORS["card"], corner_radius=15)
        clock_section.pack(fill="x", padx=15, pady=(20, 15))
        
        self.clock_lbl = ctk.CTkLabel(clock_section, text="00:00", font=FONTS["clock"],
                                       text_color=COLORS["text"])
        self.clock_lbl.pack(pady=(15, 5))

        self.date_lbl = ctk.CTkLabel(clock_section, text="Date", text_color=COLORS["text_dim"],
                                      font=FONTS["body"])
        self.date_lbl.pack(pady=(0, 15))

        # Separator
        separator = ctk.CTkFrame(self.sidebar, fg_color=COLORS["border"], height=1)
        separator.pack(fill="x", padx=20, pady=10)

        # Timer Frame (Moved to Top for Visibility)
        self.timer_frame = ctk.CTkFrame(self.sidebar, fg_color=COLORS["card"], corner_radius=15,
                                        border_width=1, border_color=COLORS["border"])
        self.timer_frame.pack(side="top", fill="x", padx=15, pady=(10, 10))

        timer_header = ctk.CTkFrame(self.timer_frame, fg_color="transparent")
        timer_header.pack(fill="x", padx=15, pady=(12, 0))
        
        self.timer_mode_lbl = ctk.CTkLabel(timer_header, text="🎯 Focus Session",
                                           text_color=COLORS["success"], font=FONTS["small"])
        self.timer_mode_lbl.pack(side="left")

        self.timer_lbl = ctk.CTkLabel(self.timer_frame, text="00:00:00", font=FONTS["timer"],
                                       text_color=COLORS["text"])
        self.timer_lbl.pack(pady=10)

        self.timer_btns = ctk.CTkFrame(self.timer_frame, fg_color="transparent")
        self.timer_btns.pack(fill="x", padx=15, pady=(0, 15))

        self.timer_ctrl = ctk.CTkButton(self.timer_btns, text="▶ Start", height=40,
                                        fg_color=COLORS["success"], hover_color=COLORS["success_dark"],
                                        corner_radius=10, font=FONTS["body"],
                                        command=self.toggle_timer)
        self.timer_ctrl.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.stop_btn = ctk.CTkButton(self.timer_btns, text="⏹", width=40, height=40,
                                      fg_color=COLORS["error"], hover_color="#CC0000",
                                      corner_radius=10, font=FONTS["header"],
                                      state="disabled",
                                      command=lambda: self.stop_timer(log=True))
        self.stop_btn.pack(side="right")
        
        # Navigation section
        nav_label = ctk.CTkLabel(self.sidebar, text="NAVIGATION", font=FONTS["tiny"],
                                  text_color=COLORS["text_muted"])
        nav_label.pack(anchor="w", padx=20, pady=(5, 10))
        
        self.nav_buttons = {}
        items = [
            ("📅 Today", "today"),
            ("🗓️ Routine", "routine"),
            ("⚙️ Planner", "planner"),
            ("🎯 Goals", "goals"),
            ("🥗 Habits", "habits"),
            ("📂 Vault", "vault"),
            ("📜 History", "history"),
            ("📊 Report", "report"),
            ("🤖 Assistant", "assistant"),
            ("🛒 Store", "store"),
            ("⚙️ Settings", "settings")
        ]
        for text, key in items:
            btn = SidebarButton(self.sidebar, text=text, command=lambda k=key: self.switch_view(k))
            btn.pack(fill="x", padx=15, pady=3)
            self.nav_buttons[key] = btn

        
        # Zen Mode Toggle (If unlocked) - Moved to bottom of nav
        zen_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        zen_frame.pack(side="bottom", fill="x", padx=15, pady=20)
        
        if is_unlocked(self.data, "zen_mode"):
             ctk.CTkButton(zen_frame, text="🧘 Enter Zen Mode", fg_color=COLORS["accent"],
                           hover_color=COLORS["accent_dark"],
                           command=self.toggle_zen_mode).pack(fill="x")

    def init_views(self):
        # Lazy loading: store view classes, create instances on first access
        self.view_classes = {
            "today": TodayView,
            "routine": RoutineView,
            "planner": PlannerView,
            "goals": GoalsView,
            "habits": HabitView,
            "vault": VaultView,
            "history": HistoryView,
            "report": ReportView,
            "assistant": ChatView,
            "settings": SettingsView,
            "store": StoreView
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
        ended_classes = sync_class_statuses(self.data)
        if ended_classes:
            for task_id in ended_classes:
                task = get_task_by_id(self.data, task_id)
                if task:
                    if messagebox.askyesno("Class Ended", f"Did you attend '{task['title']}'?"):
                        mark_class_done(self.data, task_id)
                        add_xp(self.data, 20) 
                        self.refresh_xp()

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
        self.timer_ctrl.configure(text="⏸ Pause", fg_color=COLORS["warning"])
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
        self.timer_ctrl.configure(text="▶ Resume", fg_color=COLORS["success"])
        update_timer_state(self.data, self.timer_seconds, self.timer_mode, self.active_class_id, is_running=False)

    def stop_timer(self, log=False):
        self.timer_running = False
        if log and self.timer_seconds > 5:
            if self.timer_mode == "class" and self.active_class_id:
                log_class_session(self.data, self.timer_seconds, self.active_class_id)
                log_focus_session(self.data, self.timer_seconds, session_type="class")
            else:
                log_focus_session(self.data, self.timer_seconds, session_type="focus")
            self.refresh_xp()
        
        self.timer_seconds = 0
        clear_timer_state(self.data) # Logic Clear
        
        self.timer_lbl.configure(text="00:00:00")
        self.timer_ctrl.configure(text="▶ Start", fg_color=COLORS["success"])
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
        """Dynamic window sizing based on screen resolution."""
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        w = int(screen_width * scale)
        h = int(screen_height * scale)
        x = int((screen_width - w) / 2)
        y = int((screen_height - h) / 2)
        
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
