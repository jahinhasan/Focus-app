# ==================== UI.PY ====================
# Tkinter-based UI for Focus Dashboard

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from logic import save_routine_from_parser


from logic import (
    load_data, save_data, add_task_logic, add_subtask, toggle_subtask,
    get_level_progress, get_active_class, mark_class_done, 
    sync_class_statuses, log_focus_time, cleanup_finished_classes,
    get_today_tasks, get_weekly_class_tasks, today, format_seconds_to_hms,
    log_class_session, get_today_focus_stats, log_focus_session
)
from file_handler import FileHandler
from ai_parser import parse_with_ai, parse_file_with_ai, format_today_schedule, format_user_stats, get_user_context

# ==================== CONFIG ====================
COLORS = {
    "bg": "#0f1115",
    "sidebar": "#161b22",
    "card": "#1c2128",
    "accent": "#58a6ff",   # Blue
    "success": "#3fb950",  # Green
    "warning": "#d29922",  # Yellow
    "error": "#f85149",    # Red
    "text": "#c9d1d9",
    "text_dim": "#8b949e",
    "border": "#30363d",
    "class_mode": "#f85149",   # Red for class mode
    "focus_mode": "#3fb950",   # Green for focus mode
}

FONT_MAIN = ("Segoe UI", 10)
FONT_HEADER = ("Segoe UI", 14, "bold")
FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_CLOCK = ("Segoe UI", 24, "bold")

# Gradient colors for sidebar
GRADIENT_TOP = "#1a1f2e"
GRADIENT_BOTTOM = "#161b22"

# ==================== COMPONENTS ====================
class XPBar(tk.Frame):
    """XP progress bar with level display."""
    
    def __init__(self, parent, data):
        super().__init__(parent, bg=COLORS["bg"], height=40)
        self.data = data
        self.pack_propagate(False)
        self.render()

    def render(self):
        for w in self.winfo_children(): w.destroy()
        
        container = tk.Frame(self, bg=COLORS["bg"])
        container.pack(fill="x", padx=20, pady=10)
        
        # Level Badge
        lvl = self.data.get("level", 1)
        tk.Label(container, text=f"⭐ LVL {lvl}", fg=COLORS["warning"], bg=COLORS["bg"], 
                 font=("Segoe UI", 12, "bold")).pack(side="left")
        
        # Progress Bar
        curr, req, pct = get_level_progress(self.data)
        
        bar_frame = tk.Frame(container, bg=COLORS["border"], height=8, width=200)
        bar_frame.pack(side="left", padx=15)
        bar_frame.pack_propagate(False)
        
        fill_width = int(200 * (pct / 100))
        tk.Frame(bar_frame, bg=COLORS["accent"], height=8, width=max(1, fill_width)).pack(side="left")
        
        # Text Stats
        tk.Label(container, text=f"{curr} / {req} XP", fg=COLORS["text_dim"], 
                 bg=COLORS["bg"], font=("Segoe UI", 9)).pack(side="left", padx=5)

class Sidebar(tk.Frame):
    """Left sidebar with clock, menu, and focus timer."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=COLORS["sidebar"], width=250)
        self.pack_propagate(False)
        self.app = app

        # ================= CLOCK =================
        self.clock_lbl = tk.Label(
            self, text="00:00", font=FONT_CLOCK,
            bg=COLORS["sidebar"], fg="white"
        )
        self.clock_lbl.pack(pady=(20, 5))

        self.date_lbl = tk.Label(
            self, text="Mon, Jan 01", font=("Segoe UI", 10),
            bg=COLORS["sidebar"], fg=COLORS["text_dim"]
        )
        self.date_lbl.pack(pady=(0, 20))

        # ================= NOTICE BAR =================
        self.notice_frame = tk.Frame(self, bg=COLORS["card"], padx=10, pady=10)
        self.notice_frame.pack(fill="x", padx=15, pady=10)

        self.notice_lbl = tk.Label(
            self.notice_frame,
            text="No active classes",
            bg=COLORS["card"],
            fg=COLORS["text"],
            wraplength=200,
            justify="left"
        )
        self.notice_lbl.pack(anchor="w")

        # ================= MENU =================
        self.menu_frame = tk.Frame(self, bg=COLORS["sidebar"])
        self.menu_frame.pack(fill="x", pady=20)

        self.buttons = {}
        items = [
            ("📅 Today", "today"),
            ("🗓️ Routine", "routine"),
            ("📜 History", "history"),
            ("📊 Report", "report"),
            ("💬 Assistant", "chat")
        ]

        for text, key in items:
            btn = tk.Button(
                self.menu_frame,
                text=text,
                font=("Segoe UI", 11),
                bg=COLORS["sidebar"],
                fg=COLORS["text"],
                activebackground=COLORS["card"],
                activeforeground="white",
                relief="flat",
                anchor="w",
                padx=20,
                pady=10,
                command=lambda k=key: self.app.switch_view(k)
            )
            btn.pack(fill="x")
            self.buttons[key] = btn

        # ================= TIMER STATE (STOPWATCH) =================
        self.timer_elapsed = 0  # seconds
        self.timer_running = False
        self.timer_mode = "focus"  # "focus" or "class"
        self.active_class_id = None
        self.last_tick = None

        # ================= TIMER UI (STOPWATCH) =================
        self.timer_frame = tk.Frame(self, bg=COLORS["card"], pady=10)
        self.timer_frame.pack(side="bottom", fill="x", padx=15, pady=20)

        # Header with mode
        self.mode_lbl = tk.Label(
            self.timer_frame,
            text="🟢 Focus Session",
            font=("Segoe UI", 10, "bold"),
            bg=COLORS["card"],
            fg=COLORS["focus_mode"]
        )
        self.mode_lbl.pack(pady=(0, 4))

        self.timer_lbl = tk.Label(
            self.timer_frame,
            text="00:00",
            font=("Segoe UI", 24, "bold"),
            bg=COLORS["card"],
            fg=COLORS["accent"]
        )
        self.timer_lbl.pack()

        # Secondary line for daily totals
        self.sub_lbl = tk.Label(
            self.timer_frame,
            text="Focus today: 00:00 | Class: 00:00",
            font=("Segoe UI", 9),
            bg=COLORS["card"],
            fg=COLORS["text_dim"]
        )
        self.sub_lbl.pack(pady=(2, 6))

        btn_frame = tk.Frame(self.timer_frame, bg=COLORS["card"])
        btn_frame.pack(pady=5)

        self.start_btn = tk.Button(
            btn_frame, text="▶",
            command=self.toggle_timer,
            bg=COLORS["success"],
            fg="white",
            width=4,
            relief="flat"
        )
        self.start_btn.pack(side="left", padx=5)

        self.reset_btn = tk.Button(
            btn_frame, text="⏹",
            command=self.stop_and_log_session,
            bg=COLORS["border"],
            fg="white",
            width=4,
            relief="flat"
        )
        self.reset_btn.pack(side="left", padx=5)

        # ================= START LOOP (LAST LINE) =================
        self.update_clock()

    def update_clock(self):
        """Update clock display, class status, and stopwatch tick."""
        now = datetime.now()
        self.clock_lbl.config(text=now.strftime("%H:%M"))
        self.date_lbl.config(text=now.strftime("%a, %b %d"))
        
        # Check active class and handle auto start/stop
        active = get_active_class(self.app.data)
        if active:
            self.notice_lbl.config(text=f"🔴 Class Now:\n{active['title']}", fg=COLORS["error"])
            # If class becomes active and stopwatch isn't in class mode, auto-start
            if (self.timer_mode != "class") or (self.active_class_id != active["id"]):
                # If a focus session is running, stop and log it before switching
                if self.timer_running and self.timer_mode == "focus" and self.timer_elapsed > 0:
                    self.stop_and_log_session()
                self.timer_mode = "class"
                self.active_class_id = active["id"]
                self.mode_lbl.config(text=f"🔴 Class: {active['title']}", fg=COLORS["class_mode"])
                self.start_stopwatch(auto=True)
        else:
            self.notice_lbl.config(text="🟢 Focus Session", fg=COLORS["success"])
            # If previously class mode and class ended, stop and log class session
            if self.timer_mode == "class" and self.timer_running:
                self.stop_and_log_session()
            self.timer_mode = "focus"
            self.active_class_id = None
            self.mode_lbl.config(text="🟢 Focus Session", fg=COLORS["focus_mode"])
        
        # Tick stopwatch
        if self.timer_running:
            now_ts = now.timestamp()
            if self.last_tick is None:
                self.last_tick = now_ts
            delta = max(0, int(now_ts - self.last_tick))
            if delta > 0:
                self.timer_elapsed += delta
                self.last_tick = now_ts
                self.timer_lbl.config(text=format_seconds_to_hms(self.timer_elapsed))
        
        # Update sub label with today's totals
        stats = get_today_focus_stats(self.app.data)
        self.sub_lbl.config(text=f"Focus today: {stats['formatted_total']} | Class: {stats['formatted_class']}")
        
        self.after(1000, self.update_clock)
        
    def toggle_timer(self):
        """Toggle stopwatch on/off in current mode."""
        if self.timer_running:
            self.stop_and_log_session()
        else:
            self.start_stopwatch()

    def stop_and_log_session(self):
        """Stop current session and log time + XP based on mode."""
        if not self.timer_running:
            # Reset elapsed and UI if pressed while stopped
            self.timer_elapsed = 0
            self.timer_lbl.config(text="00:00")
            self.start_btn.config(text="▶", bg=COLORS["success"])
            self.last_tick = None
            return

        # Stop running session
        self.timer_running = False
        self.start_btn.config(text="▶", bg=COLORS["success"])
        self.last_tick = None

        if self.timer_elapsed > 0:
            if self.timer_mode == "class" and self.active_class_id:
                # Log class-specific and general class focus
                log_class_session(self.app.data, self.timer_elapsed, self.active_class_id)
                log_focus_session(self.app.data, self.timer_elapsed, session_type="class")
            else:
                # Log general focus
                log_focus_session(self.app.data, self.timer_elapsed, session_type="focus")
            self.app.refresh_xp()
        # Reset elapsed
        self.timer_elapsed = 0
        self.timer_lbl.config(text="00:00")

    def start_stopwatch(self, auto=False):
        """Start the stopwatch; if already running, ignore."""
        if self.timer_running:
            return
        self.timer_running = True
        self.start_btn.config(text="⏸", bg=COLORS["warning"])
        self.last_tick = None

    def set_active(self, view_name):
        """Highlight active menu button."""
        for k, btn in self.buttons.items():
            if k == view_name:
                btn.config(bg=COLORS["card"], fg=COLORS["accent"])
            else:
                btn.config(bg=COLORS["sidebar"], fg=COLORS["text"])


# ==================== VIEWS ====================
class TodayView(tk.Frame):
    """Main view showing today's tasks and classes."""
    
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app
        
        canvas = tk.Canvas(self, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.content = tk.Frame(canvas, bg=COLORS["bg"])
        
        self.content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.content, anchor="nw", width=800)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=20, pady=20)
        scrollbar.pack(side="right", fill="y")
        
        self.render()
        
    def render(self):
        for w in self.content.winfo_children(): w.destroy()
        
        tk.Label(self.content, text="Today's Overview", font=FONT_TITLE, 
                 bg=COLORS["bg"], fg="white").pack(anchor="w", pady=(0, 20))
        
        # Add Task Input
        input_frame = tk.Frame(self.content, bg=COLORS["bg"])
        input_frame.pack(fill="x", pady=(0, 20))
        
        self.task_entry = tk.Entry(input_frame, font=FONT_MAIN, bg=COLORS["card"], 
                                   fg="white", insertbackground="white", relief="flat")
        self.task_entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 10))
        self.task_entry.bind("<Return>", self.add_task)
        
        tk.Button(input_frame, text="+ Add Task", command=self.add_task, 
                  bg=COLORS["accent"], fg="white", relief="flat", font=FONT_MAIN).pack(side="right")
        
        # Get and display today's tasks
        today_tasks = get_today_tasks(self.app.data)
        
        for i, task in enumerate(today_tasks):
            if task.get("status") == "done":
                continue
            self.draw_task_card(i, task)
            
    def draw_task_card(self, index, task):
        """Draw a single task card."""
        card = tk.Frame(self.content, bg=COLORS["card"], pady=10, padx=15)
        card.pack(fill="x", pady=5)
        
        header = tk.Frame(card, bg=COLORS["card"])
        header.pack(fill="x")
        
        # Checkbox
        chk_var = tk.IntVar()
        tk.Checkbutton(header, variable=chk_var, bg=COLORS["card"], 
                       activebackground=COLORS["card"], 
                       command=lambda: self.complete_task(index)).pack(side="left")
        
        title_fg = "white"
        icon = "📝"
        if task.get("type") == "class":
            icon = "📘"
            title_fg = COLORS["accent"]
            schedule = task.get("schedule", {})
            tk.Label(header, text=f"{schedule.get('start','')} - {schedule.get('end','')}", 
                     fg=COLORS["warning"], bg=COLORS["card"]).pack(side="right")

        tk.Label(header, text=f"{icon} {task['title']}", font=("Segoe UI", 11, "bold"), 
                 fg=title_fg, bg=COLORS["card"]).pack(side="left", padx=10)
        
        # Subtasks
        subtasks = task.get("subtasks", [])
        if subtasks:
            sub_frame = tk.Frame(card, bg=COLORS["card"])
            sub_frame.pack(fill="x", padx=30, pady=(5, 0))
            for si, sub in enumerate(subtasks):
                s_frame = tk.Frame(sub_frame, bg=COLORS["card"])
                s_frame.pack(fill="x")
                s_var = tk.IntVar(value=1 if sub.get("done") else 0)
                tk.Checkbutton(s_frame, text=sub["title"], variable=s_var, 
                               bg=COLORS["card"], fg=COLORS["text_dim"], 
                               selectcolor=COLORS["sidebar"], activebackground=COLORS["card"],
                               command=lambda t=task["id"], s=si: self.toggle_sub(t, s)).pack(anchor="w")
                
        # Add Subtask Button
        tk.Button(card, text="+", font=("Arial", 8), bg=COLORS["border"], 
                  fg="white", relief="flat", 
                  command=lambda: self.prompt_subtask(index)).pack(anchor="e", padx=5)

    def add_task(self, event=None):
        """Add a new task."""
        text = self.task_entry.get()
        if text:
            add_task_logic(self.app.data, text)
            self.task_entry.delete(0, "end")
            self.render()

    def complete_task(self, index):
        """Mark a task as complete."""
        # Re-fetch tasks to get correct index
        today_tasks = get_today_tasks(self.app.data)
        if index >= len(today_tasks):
            return
            
        task = today_tasks[index]
        
        if task.get("type") == "class":
            mark_class_done(self.app.data, task["id"])
        else:
            task["status"] = "done"
            from logic import add_xp
            add_xp(self.app.data, 10)
            
        save_data(self.app.data)
        self.app.refresh_xp()
        self.render()
        
    def prompt_subtask(self, index):
        """Prompt for new subtask."""
        today_tasks = get_today_tasks(self.app.data)
        if index >= len(today_tasks):
            return
        
        top = tk.Toplevel(self)
        top.title("Add Subtask")
        top.geometry("300x100")
        top.configure(bg=COLORS["bg"])
        
        e = tk.Entry(top)
        e.pack(pady=10, padx=10, fill="x")
        e.focus()
        
        def save():
            if e.get():
                add_subtask(self.app.data, today_tasks[index]["id"], e.get())
                self.render()
            top.destroy()
        
        tk.Button(top, text="Add", command=save).pack()

    def toggle_sub(self, task_id, sub_index):
        """Toggle a subtask."""
        toggle_subtask(self.app.data, task_id, sub_index)
        self.app.refresh_xp()


class RoutineView(tk.Frame):
    """Weekly routine view."""
    
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app
        tk.Label(self, text="Weekly Routine", font=FONT_TITLE, 
                 bg=COLORS["bg"], fg="white").pack(anchor="nw", padx=20, pady=20)
        
        grid = tk.Frame(self, bg=COLORS["bg"])
        grid.pack(fill="both", expand=True, padx=20, pady=10)
        
        days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        for i, d in enumerate(days):
            tk.Label(grid, text=d.upper(), font=("Segoe UI", 10, "bold"), 
                     bg=COLORS["card"], fg="white", width=10, pady=5).grid(
                         row=0, column=i, sticky="ew", padx=1)
            
            day_frame = tk.Frame(grid, bg=COLORS["sidebar"])
            day_frame.grid(row=1, column=i, sticky="nsew", padx=1, pady=1)
            grid.columnconfigure(i, weight=1)
            grid.rowconfigure(1, weight=1)
            
            # Get classes for this day
            weekly = get_weekly_class_tasks(self.app.data)
            classes = weekly.get(d, [])
            classes.sort(key=lambda x: x.get("schedule", {}).get("start", ""))
            
            for c in classes:
                schedule = c.get("schedule", {})
                tk.Label(day_frame, text=f"{schedule.get('start','')}\n{c['title'][:10]}..", 
                         bg=COLORS["card"], fg=COLORS["accent"], 
                         font=("Arial", 9), pady=5, justify="center").pack(fill="x", pady=2, padx=2)


class HistoryView(tk.Frame):
    """History log view."""
    
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app
        tk.Label(self, text="History Log", font=FONT_TITLE, 
                 bg=COLORS["bg"], fg="white").pack(anchor="nw", padx=20, pady=20)
        
        hist = self.app.data.get("history", {})
        dates = sorted(hist.keys(), reverse=True)
        
        container = tk.Frame(self, bg=COLORS["bg"])
        container.pack(fill="both", padx=20)
        
        for d in dates[:15]:
            entry = hist[d]
            row = tk.Frame(container, bg=COLORS["card"], pady=10, padx=10)
            row.pack(fill="x", pady=2)
            
            tk.Label(row, text=d, font=("Segoe UI", 11, "bold"), 
                     fg="white", bg=COLORS["card"], width=12).pack(side="left")
            tk.Label(row, text=f"Tasks: {entry.get('completed',0)}/{entry.get('total',0)}", 
                     fg=COLORS["text"], bg=COLORS["card"]).pack(side="left", padx=20)
            tk.Label(row, text=f"XP: +{entry.get('xp_gained',0)}", 
                     fg=COLORS["warning"], bg=COLORS["card"]).pack(side="right")


class ReportView(tk.Frame):
    """Productivity report view with graph."""
    
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app
        tk.Label(self, text="Productivity Report", font=FONT_TITLE, 
                 bg=COLORS["bg"], fg="white").pack(anchor="nw", padx=20, pady=20)
        
        self.canvas = tk.Canvas(self, bg=COLORS["card"], height=300, highlightthickness=0)
        self.canvas.pack(fill="x", padx=20, pady=20)
        
        self.draw_graph()
        
    def draw_graph(self):
        """Draw XP bar chart for last 7 days."""
        self.canvas.delete("all")
        w = 800
        h = 250
        pad = 30
        
        # Axes
        self.canvas.create_line(pad, h, w, h, fill=COLORS["border"], width=2)
        self.canvas.create_line(pad, h, pad, 0, fill=COLORS["border"], width=2)
        
        hist = self.app.data.get("history", {})
        dates = sorted(hist.keys())[-7:]
        if not dates:
            return
        
        max_val = 1
        points = []
        for d in dates:
            val = hist[d].get("xp_gained", 0)
            max_val = max(max_val, val)
            points.append(val)
            
        bar_w = (w - 2*pad) / len(dates) / 1.5
        spacing = (w - 2*pad) / len(dates)
        
        for i, val in enumerate(points):
            x = pad + (i * spacing) + 30
            bar_h = (val / max_val) * (h - 20) if max_val > 0 else 0
            y = h - bar_h
            
            self.canvas.create_rectangle(x, y, x + bar_w, h, fill=COLORS["accent"], outline="")
            self.canvas.create_text(x + bar_w/2, h + 15, text=dates[i][5:], 
                                     fill="white", font=("Arial", 8))
            self.canvas.create_text(x + bar_w/2, y - 10, text=str(val), 
                                     fill=COLORS["warning"], font=("Arial", 8))
            
        self.canvas.create_text(w/2, 20, text="XP Gained (Last 7 Days)", 
                                fill="white", font=("Segoe UI", 12))


class ChatView(tk.Frame):
    """AI Assistant chat view."""
    
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app
        self.file_handler = FileHandler(app.root)
        
        # ==================== QUICK ACTIONS ====================
        # Quick action buttons at the top
        self.quick_actions_frame = tk.Frame(self, bg=COLORS["bg"])
        self.quick_actions_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        tk.Label(self.quick_actions_frame, text="⚡ Quick Actions:", 
                 bg=COLORS["bg"], fg=COLORS["text_dim"], font=("Segoe UI", 9)).pack(anchor="w")
        
        action_buttons = [
            ("📝 Add Task", self.quick_add_task),
            ("📘 Add Class", self.quick_add_class),
            ("📅 Show Schedule", self.quick_show_schedule),
            ("📊 Show Stats", self.quick_show_stats),
        ]
        
        for text, cmd in action_buttons:
            tk.Button(self.quick_actions_frame, text=text, command=cmd,
                      bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 9),
                      relief="flat", padx=12, pady=5).pack(side="left", padx=3)
        
        # ==================== QUICK ASKS ====================
        # Template quick-ask chips
        self.quick_asks_frame = tk.Frame(self, bg=COLORS["bg"])
        self.quick_asks_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        tk.Label(self.quick_asks_frame, text="💡 Quick Asks:", 
                 bg=COLORS["bg"], fg=COLORS["text_dim"], font=("Segoe UI", 9)).pack(anchor="w")
        
        quick_asks = [
            "What do I have today?",
            "How much XP do I have?",
            "When is my next class?",
            "What classes this week?",
            "Productivity tips",
        ]
        
        for ask in quick_asks:
            chip = tk.Label(self.quick_asks_frame, text=ask, bg=COLORS["card"], 
                           fg=COLORS["accent"], font=("Segoe UI", 8),
                           padx=10, pady=4, cursor="hand2")
            chip.pack(side="left", padx=3, pady=5)
            chip.bind("<Button-1>", lambda e, t=ask: self.send_quick_ask(t))
            chip.bind("<Enter>", lambda e, c=chip: c.config(bg=COLORS["border"]))
            chip.bind("<Leave>", lambda e, c=chip: c.config(bg=COLORS["card"]))
        
        # Chat history area
        self.history_frame = tk.Frame(self, bg=COLORS["bg"])
        self.history_frame.pack(fill="both", expand=True, padx=20)
        
        self.canvas = tk.Canvas(self.history_frame, bg=COLORS["bg"], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.history_frame, orient="vertical", 
                                        command=self.canvas.yview)
        self.msg_container = tk.Frame(self.canvas, bg=COLORS["bg"])
        
        self.msg_container.bind("<Configure>", 
                                lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.msg_container, anchor="nw", width=800)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Input area
        self.input_frame = tk.Frame(self, bg=COLORS["card"], pady=10, padx=10)
        self.input_frame.pack(fill="x", side="bottom")
        
        self.entry = tk.Entry(self.input_frame, font=("Segoe UI", 11), 
                              bg="#2d333b", fg="white", insertbackground="white", relief="flat")
        self.entry.pack(side="left", fill="x", expand=True, ipady=5, padx=10)
        self.entry.bind("<Return>", self.send)
        self.entry.bind("<Control-v>", self.handle_paste)
        
        tk.Button(self.input_frame, text="➤", command=self.send, 
                  bg=COLORS["success"], fg="white", font=("Arial", 12), 
                  relief="flat").pack(side="right")
        
        tk.Button(self.input_frame, text="📎", command=self.upload_file, 
                  bg=COLORS["card"], fg="white", font=("Arial", 12), 
                  relief="flat").pack(side="right", padx=5)

        # Initial greeting
        self.add_msg("assistant", "👋 Hello! I'm your Focus Assistant!\n\nI can help you with:\n• Adding tasks and classes\n• Answering questions about your schedule\n• Checking your stats and XP\n• Parsing files/images for schedules\n\nTry clicking a quick ask above or type a command! ✨")

    # ==================== QUICK ACTION HANDLERS ====================
    def quick_add_task(self):
        """Quick add task via dialog."""
        top = tk.Toplevel(self)
        top.title("Add Task")
        top.geometry("400x120")
        top.configure(bg=COLORS["bg"])
        
        tk.Label(top, text="Enter task name:", bg=COLORS["bg"], fg="white").pack(pady=5)
        entry = tk.Entry(top, font=("Segoe UI", 11), bg=COLORS["card"], fg="white", relief="flat")
        entry.pack(fill="x", padx=20, pady=5)
        entry.focus()
        
        def save():
            if entry.get().strip():
                add_task_logic(self.app.data, entry.get().strip())
                self.add_msg("assistant", f"✅ Added task: {entry.get().strip()}")
                self.app.refresh_xp()
            top.destroy()
        
        tk.Button(top, text="Add Task", command=save, bg=COLORS["success"], fg="white", relief="flat").pack(pady=10)

    def quick_add_class(self):
        """Quick add class via dialog."""
        top = tk.Toplevel(self)
        top.title("Add Class")
        top.geometry("450x200")
        top.configure(bg=COLORS["bg"])
        
        tk.Label(top, text="Class Details:", bg=COLORS["bg"], fg="white", font=("Segoe UI", 11, "bold")).pack(pady=5)
        
        # Class name
        tk.Label(top, text="Class name:", bg=COLORS["bg"], fg=COLORS["text_dim"]).pack(anchor="w", padx=20)
        name_entry = tk.Entry(top, font=("Segoe UI", 11), bg=COLORS["card"], fg="white", relief="flat")
        name_entry.pack(fill="x", padx=20, pady=2)
        
        # Days and time
        tk.Label(top, text="Days & Time (e.g., Mon Wed 10-11):", bg=COLORS["bg"], fg=COLORS["text_dim"]).pack(anchor="w", padx=20)
        time_entry = tk.Entry(top, font=("Segoe UI", 11), bg=COLORS["card"], fg="white", relief="flat")
        time_entry.pack(fill="x", padx=20, pady=2)
        
        def save():
            name = name_entry.get().strip()
            time_str = time_entry.get().strip()
            if name and time_str:
                self.add_msg("you", f"Add class: {name} {time_str}")
                self.process_ai(f"Add class {name} {time_str}")
            top.destroy()
        
        tk.Button(top, text="Add Class", command=save, bg=COLORS["accent"], fg="white", relief="flat").pack(pady=15)

    def quick_show_schedule(self):
        """Show today's schedule."""
        schedule = format_today_schedule()
        self.add_msg("you", "📅 What's my schedule today?")
        self.add_msg("assistant", schedule)

    def quick_show_stats(self):
        """Show user stats."""
        stats = format_user_stats()
        self.add_msg("you", "📊 How am I doing?")
        self.add_msg("assistant", stats)

    def send_quick_ask(self, text):
        """Send a quick ask template."""
        self.entry.delete(0, "end")
        self.entry.insert(0, text)
        self.send()

    # ==================== MESSAGE HANDLING ====================
    def add_msg(self, sender, text):
        """Add a message to chat with improved styling."""
        # anchor uses compass directions (e/w), side uses full names (right/left)
        anchor = "e" if sender == "you" else "w"
        side = "right" if sender == "you" else "left"
        bg = COLORS["accent"] if sender == "you" else COLORS["card"]
        fg = "white" if sender == "you" else COLORS["text"]
        
        # Create a frame for better styling
        msg_frame = tk.Frame(self.msg_container, bg=COLORS["bg"])
        msg_frame.pack(anchor=anchor, pady=5, fill="x")
        
        # Message bubble
        bubble = tk.Frame(msg_frame, bg=bg, padx=12, pady=8)
        bubble.pack(side=side, padx=10)
        
        tk.Label(bubble, text=text, bg=bg, fg=fg, font=FONT_MAIN, 
                 wraplength=480, justify="left").pack()
        
        self.canvas.update_idletasks()
        self.canvas.yview_moveto(1.0)
        
    def send(self, event=None):
        """Send user message."""
        text = self.entry.get()
        if not text:
            return
        self.entry.delete(0, "end")
        self.add_msg("you", text)
        self.process_ai(text)
        
    def process_ai(self, text, is_file_content=False):
        """Process AI response."""
        # Typing indicator
        lbl = tk.Label(self.msg_container, text="Typing...", bg=COLORS["bg"], 
                       fg="gray", font=("Arial", 8, "italic"))
        lbl.pack(anchor="w", padx=10)
        self.update()
        
        try:
            if is_file_content:
                result = parse_file_with_ai(text)
                lbl.destroy()
                self.handle_result(result)
                return

            # For regular text, use intent authority pipeline
            from intent_authority import process_text as ia_process
            result = ia_process(text)
            lbl.destroy()

            # Clarification requested
            if result.get("clarify"):
                q = result.get("question") or "Could you clarify?"
                self.add_msg("assistant", q)
                return

            # Execution result
            exec_res = result.get("execution", {})
            decision = result.get("decision", {})

            if exec_res.get("status") == "ok":
                det_intent = decision.get("intent")
                if det_intent == "task":
                    task = exec_res.get("result", {}).get("task")
                    title = task.get("title") if task else decision.get("data", {}).get("title")
                    self.add_msg("assistant", f"✅ Added task: {title}")
                    self.app.refresh_xp()
                elif det_intent == "class":
                    self.add_msg("assistant", "✅ Added class to your routine.")
                    self.app.refresh_xp()
                elif det_intent == "query":
                    # Queries should be handled by UI formatting functions
                    # Fallback generic message
                    self.add_msg("assistant", exec_res.get("result", {}).get("message", "Here are the results."))
                else:
                    self.add_msg("assistant", exec_res.get("result", {}).get("message", "Done."))

                # Re-render views that depend on data
                if self.app.active_view == "today":
                    self.app.views["today"].render()
            else:
                # Execution error or unknown
                err = exec_res.get("error") or "Sorry, I couldn't complete that."
                self.add_msg("assistant", f"❌ {err}")

        except Exception as e:
            lbl.destroy()
            self.add_msg("assistant", f"❌ Error: {e}")

    def handle_result(self, result):
        """Handle AI parsing result."""
        intent = result.get("intent")
        
        if intent == "chat":
            self.add_msg("assistant", result.get("message", "Ok."))
            
        elif intent == "query":
            # Handle informational queries
            action = result.get("action")
            if action == "xp":
                ctx = get_user_context()
                self.add_msg("assistant", f"📊 **Your XP:**\n⭐ Level {ctx['level']}\n✨ {ctx['xp']} / {ctx['xp_needed']} XP ({ctx['progress_percent']}%)")
            elif action == "next_class":
                from ai_parser import format_upcoming_classes
                self.add_msg("assistant", format_upcoming_classes())
            elif action == "today_tasks":
                from ai_parser import format_today_schedule
                self.add_msg("assistant", format_today_schedule())
            elif action == "weekly_classes":
                weekly = get_weekly_class_tasks(self.app.data)
                lines = ["📚 **Weekly Classes:**"]
                for day, classes in weekly.items():
                    if classes:
                        lines.append(f"\n**{day.upper()}:**")
                        for c in classes:
                            schedule = c.get("schedule", {})
                            lines.append(f"  • {c['title']}: {schedule.get('start','')}-{schedule.get('end','')}")
                self.add_msg("assistant", "\n".join(lines))
            elif action == "stats":
                self.add_msg("assistant", format_user_stats())
            else:
                self.add_msg("assistant", result.get("message", "What would you like to know?"))
            
        elif intent == "schedule_file":
            classes = result.get("classes", [])
            self.add_msg("assistant", f"📄 Found {len(classes)} classes. Saving to your Routine...")
            
            count = save_routine_from_parser(self.app.data, classes)
            self.add_msg("assistant", f"✅ Successfully added {count} classes to your Weekly Routine!")
            self.app.refresh_xp()
            
        elif intent == "task":
            add_task_logic(self.app.data, result.get("title"))
            self.add_msg("assistant", f"✅ Added task: {result.get('title')}")
            
        elif intent == "class":
            schedule = result.get("schedule", {})
            if not schedule and result.get("days"):
                schedule = {
                    "days": result.get("days"),
                    "start": result.get("start", "00:00"),
                    "end": result.get("end", "00:00")
                }
            add_task_logic(self.app.data, result.get("title"), category="class", 
                          schedule=schedule, days=result.get("days"))
            self.add_msg("assistant", "✅ Added class to your routine.")
            
        else:
            self.add_msg("assistant", result.get("message", "Done."))

    def upload_file(self):
        """Upload a file for parsing."""
        path = filedialog.askopenfilename(filetypes=[
            ("Documents", "*.pdf *.docx *.txt *.png *.jpg")
        ])
        if path:
            self.add_msg("you", f"📎 {path.split('/')[-1]}")
            self.process_ai(path, is_file_content=True)

    def handle_paste(self, event):
        """Handle paste event for files."""
        try:
            type_, content = self.file_handler.check_clipboard()
            if type_ in ["file_path", "image_path"]:
                self.add_msg("you", f"📎 Pasted: {content.split('/')[-1]}")
                self.process_ai(content, is_file_content=True)
                return "break"
        except:
            pass


# ==================== MAIN APP ====================
class FocusDashboard:
    """Main application class."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Focus Dashboard Pro")
        self.root.geometry("1100x700")
        self.root.configure(bg=COLORS["bg"])
        
        self.data = load_data()
        self.active_view = "today"
        
        # Sidebar
        self.sidebar = Sidebar(self.root, self)
        self.sidebar.pack(side="left", fill="y")
        
        # Main area
        self.main_area = tk.Frame(self.root, bg=COLORS["bg"])
        self.main_area.pack(side="right", fill="both", expand=True)
        
        # XP Bar
        self.topbar = XPBar(self.main_area, self.data)
        self.topbar.pack(fill="x")
        
        # Content frame
        self.content_frame = tk.Frame(self.main_area, bg=COLORS["bg"])
        self.content_frame.pack(fill="both", expand=True)
        
        # Initialize views
        self.views = {}
        self.init_views()
        self.switch_view("today")
        
        # Start sync loop
        self.sync_loop()

    def init_views(self):
        """Initialize all views."""
        self.views["today"] = TodayView(self.content_frame, self)
        self.views["routine"] = RoutineView(self.content_frame, self)
        self.views["history"] = HistoryView(self.content_frame, self)
        self.views["report"] = ReportView(self.content_frame, self)
        self.views["chat"] = ChatView(self.content_frame, self)
        
        for v in self.views.values():
            v.place(x=0, y=0, relwidth=1, relheight=1)

    def switch_view(self, name):
        """Switch to a different view."""
        if name in self.views:
            self.views[name].place(relwidth=1, relheight=1)
            self.views[name].tkraise()
            
            # Re-render dynamic views
            if hasattr(self.views[name], "render"):
                self.views[name].render()
            if hasattr(self.views[name], "draw_graph"):
                self.views[name].draw_graph()
                
            self.active_view = name
            self.sidebar.set_active(name)

    def refresh_xp(self):
        """Refresh XP display."""
        self.topbar.render()
        
    def sync_loop(self):
        """Background sync loop for class statuses."""
        ended_ids = sync_class_statuses(self.data)
        if ended_ids:
            messagebox.showinfo("Class Ended", "Did you attend these classes?")
            for tid in ended_ids:
                mark_class_done(self.data, tid)
            self.refresh_xp()
            if self.active_view == "today":
                self.views["today"].render()

        self.root.after(5000, self.sync_loop)


def start_ui():
    """Start the UI."""
    root = tk.Tk()
    app = FocusDashboard(root)
    root.mainloop()


# Entry point
if __name__ == "__main__":
    start_ui()
