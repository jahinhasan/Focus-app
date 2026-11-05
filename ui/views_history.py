"""views_history - split from ui.py (Focus Agent V2, Phase 6)."""

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

# V2 agent layer (graceful: app opens even if the agent package fails to load)
AGENT_AVAILABLE = True
try:
    from focus_agent.controller import AgentController
    from focus_agent import scheduler as fsched
    from focus_agent import goals as fgoals
    from focus_agent import estimator as fest
    from focus_agent import llm as fllm
    from focus_agent import dates as fdates
    from focus_agent import memory as fmemory
except Exception as _agent_err:  # pragma: no cover
    AGENT_AVAILABLE = False
    print(f"Agent layer unavailable: {_agent_err}")
# ==================== CONFIG ====================
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Modern Premium Color Palette
from .theme import COLORS, FONTS, get_color_str
from .widgets import Tooltip


class HistoryView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=COLORS["bg"])
        self.app = app
        self.render()

    def render(self):
        try:
            for w in self.winfo_children(): w.destroy()

            ctk.CTkLabel(self, text="History Log", font=FONTS["title"],
                         text_color=COLORS["text"]).pack(anchor="w", pady=(10, 5), padx=20)

            # Streak summary
            if AGENT_AVAILABLE:
                from logic import compute_streak
                current, best = compute_streak(self.app.data)
                n_days = len(self.app.data.get("history", {}))
                streak_txt = f"🔥 {current}-day streak · best {best} · {n_days} active day(s)"
                ctk.CTkLabel(self, text=streak_txt, font=FONTS["small"],
                             text_color=COLORS["warning"]).pack(anchor="w", padx=20, pady=(0, 4))

            # 1. Heatmap Section (Fixed Height)
            heat_data = get_heatmap_data(self.app.data)
            self._draw_heatmap(heat_data)

            # 2. List Section (Fills remaining space)
            hist = self.app.data.get("history", {})
            dates = sorted(hist.keys(), reverse=True)
            
            # Make sure this expands!
            scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
            scroll.pack(fill="both", expand=True, padx=10, pady=10)

            for d in dates[:20]:
                entry = hist[d]
                row = ctk.CTkFrame(scroll, fg_color=COLORS["card"], corner_radius=10)
                row.pack(fill="x", pady=5, padx=10)

                inner = ctk.CTkFrame(row, fg_color="transparent")
                inner.pack(fill="x", padx=20, pady=15)

                ctk.CTkLabel(inner, text=d, font=FONTS["header"]).pack(side="left")

                stat_text = f"Tasks: {entry.get('completed',0)}/{entry.get('total',0)}  |  XP: +{entry.get('xp_gained',0)}"
                ctk.CTkLabel(inner, text=stat_text, text_color=COLORS["text_dim"],
                             font=FONTS["body"]).pack(side="right")

                total = entry.get('total', 0)
                percent = (entry.get('completed', 0) / total) if total > 0 else 0
                
                ctk.CTkLabel(row, text=f"{int(percent*100)}%", width=40, 
                             font=FONTS["small"], text_color=COLORS["text_dim"]).pack(side="right")

                for task_txt in entry.get("tasks_list", []):
                    ctk.CTkLabel(row, text=f"• {task_txt}", font=FONTS["small"],
                                 text_color=COLORS["text_dim"]).pack(anchor="w", padx=20)
        except Exception as e:
            ctk.CTkLabel(self, text=f"Error loading history: {e}", text_color=COLORS["error"]).pack(pady=20)
            print(f"History render error: {e}")

    def _draw_heatmap(self, heat_data):
        """Draws a GitHub-style contribution graph."""
        container = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=10)
        container.pack(fill="x", padx=20, pady=(0, 15))
        
        # Header for Heatmap
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=10)
        ctk.CTkLabel(header, text="365 Days of Focus", font=FONTS["header"], 
                     text_color=COLORS["text"]).pack(side="left")
        
        # Canvas
        # Width: 53 weeks * 12px = ~640px. 
        # Height: 7 days * 12px = ~90px.
        bg_col = get_color_str("card")
        canvas = tk.Canvas(container, height=110, bg=bg_col, highlightthickness=0)
        canvas.pack(fill="x", expand=True, padx=10, pady=(0, 10))
        
        # Logic
        now = datetime.now()
        # Start from 52 weeks ago (Sunday)
        start_date = now - timedelta(days=365)
        # Snap to previous Sunday
        offset = (start_date.weekday() + 1) % 7
        start_date -= timedelta(days=offset)
        
        sz = 10
        gap = 3
        
        # Colors: 0=Empty, 1=Low, 2=Med, 3=High
        # We need hex strings
        col_empty = get_color_str("bg_secondary")
        col_1 = get_color_str("accent_light") # Light Purple
        col_2 = get_color_str("accent")       # Purple
        col_3 = get_color_str("accent_dark")  # Dark Purple
        col_4 = "#FFFFFF" if ctk.get_appearance_mode() == "Dark" else "#000000" # Peak
        
        # Border color for visibility
        col_border = get_color_str("border")
        
        for i in range(371): # 53 * 7
            curr = start_date + timedelta(days=i)
            # Don't draw future
            if curr > now: break
            
            day_idx = (curr.weekday() + 1) % 7 # Sun=0
            week_idx = i // 7
            
            x = week_idx * (sz + gap) + 10
            y = day_idx * (sz + gap) + 10
            
            d_str = curr.strftime("%Y-%m-%d")
            intensity = heat_data.get(d_str, 0)
            
            fill = col_empty
            outline = col_border # Outline empty cells!
            
            if intensity == 1: 
                fill = col_1
                outline = ""
            elif intensity == 2: 
                fill = col_2
                outline = ""
            elif intensity == 3: 
                fill = col_3
                outline = ""
            elif intensity >= 4: 
                fill = col_4
                outline = ""
            
            # Draw rect
            canvas.create_rectangle(x, y, x+sz, y+sz, fill=fill, outline=outline)
            
            # Tooltip logic? (Skip for now, pure visual)

class ReportView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=COLORS["bg"])
        self.app = app
        self.render()

    def render(self):
        for w in self.winfo_children(): w.destroy()

        ctk.CTkLabel(self, text="Productivity Insights", font=FONTS["title"],
                     text_color=COLORS["text"]).pack(anchor="w", pady=(10, 20), padx=20)
        
        # Get Data
        data = get_analytics_data(self.app.data)
        
        # Scrollable container for reports
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10)

        # 1. Daily Focus Graph
        self._draw_focus_chart(scroll, data["daily_focus"])

        # 2. Subject Breakdown
        self._draw_subject_chart(scroll, data["subject_time"])

        # 3. Estimation accuracy + streak (V2)
        if AGENT_AVAILABLE:
            self._draw_estimation_card(scroll)
            self._draw_streak_card(scroll)

    def _draw_estimation_card(self, parent):
        est = fest.estimation_analytics(self.app.data)
        comp = fest.completion_analytics(self.app.data)
        frame = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=15)
        frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(frame, text="Estimation vs Reality", font=FONTS["header"],
                     text_color=COLORS["accent"]).pack(anchor="w", padx=20, pady=(15, 5))

        if not est.get("n"):
            ctk.CTkLabel(frame, text=("No timed completions yet. Complete tasks with a duration "
                                      "estimate and the timer/agent will learn your real pace."),
                         font=FONTS["small"], text_color=COLORS["text_dim"],
                         wraplength=520, justify="left").pack(anchor="w", padx=20, pady=(0, 15))
            return

        ratio = est.get("mean_error_ratio")
        bias = ""
        if ratio:
            if ratio > 1.05:
                bias = f"tasks typically run ~{int(round((ratio - 1) * 100))}% longer than estimated"
            elif ratio < 0.95:
                bias = f"you finish ~{int(round((1 - ratio) * 100))}% faster than estimated"
            else:
                bias = "estimates are well calibrated"
        lines = [
            f"Completed with both estimate & actual: {est['n']}",
            f"Average miss: {est['mae_minutes']} min/task — {bias}",
            f"On/under estimate: {int((est.get('on_time_rate') or 0) * 100)}%",
            f"Completion rate (history): {int((comp.get('done_ratio') or 0) * 100)}%",
        ]
        for subj, s in (est.get("by_subject") or {}).items():
            lines.append(f"  • {subj}: {s['mae_minutes']} min avg miss over {s['n']} task(s)")
        ctk.CTkLabel(frame, text="\n".join(lines), font=FONTS["body"],
                     text_color=COLORS["text"], justify="left").pack(anchor="w", padx=20, pady=(0, 6))
        if est["n"] < 3:
            ctk.CTkLabel(frame, text=f"(only {est['n']} sample(s) - the planner uses defaults until 3+)",
                         font=FONTS["small"], text_color=COLORS["text_dim"]).pack(anchor="w", padx=20, pady=(0, 15))
        else:
            ctk.CTkLabel(frame, text="", font=FONTS["tiny"]).pack(pady=6)

    def _draw_streak_card(self, parent):
        current, best = (0, 0)
        if AGENT_AVAILABLE:
            from logic import compute_streak
            current, best = compute_streak(self.app.data)
        frame = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=15)
        frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(frame, text="🔥 Activity Streak", font=FONTS["header"],
                     text_color=COLORS["warning"]).pack(anchor="w", padx=20, pady=(15, 5))
        emoji = "🔥" * min(current, 5) if current else "🌱"
        ctk.CTkLabel(frame, text=f"{emoji}  {current}-day current streak · best {best}",
                     font=FONTS["body"]).pack(anchor="w", padx=20, pady=(0, 15))

    def _draw_focus_chart(self, parent, daily_focus):
        frame = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=15)
        frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(frame, text="Daily Focus (Minutes)", font=FONTS["header"],
                     text_color=COLORS["accent"]).pack(anchor="w", padx=20, pady=(15, 5))
        
        canvas = tk.Canvas(frame, bg=get_color_str("card"), height=200, highlightthickness=0)
        canvas.pack(fill="x", padx=20, pady=(0, 20))
        
        if not daily_focus:
            canvas.create_text(200, 100, text="No data yet", fill=get_color_str("text_dim"), font=("Inter", 12))
            return

        dates = sorted(daily_focus.keys())
        values = [daily_focus[d] for d in dates]
        max_val = max(values) if values and max(values) > 0 else 60
        
        w = 600 # approximate width, canvas scales? No, frame expands. 
        # We can bind Configure event or just use fixed manageable width.
        # Let's assume fixed usable width or get it.
        pad = 30
        bar_w = 40
        spacing = 60
        start_x = pad
        h = 200
        
        # Draw bars
        for i, d in enumerate(dates):
            val = daily_focus[d]
            x = start_x + (i * spacing)
            bar_h = (val / max_val) * (h - 2*pad)
            y = h - pad - bar_h
            
            # Bar
            canvas.create_rectangle(x, y, x + bar_w, h - pad, fill=get_color_str("accent"), outline="")
            # Value
            if val > 0:
                canvas.create_text(x + bar_w/2, y - 10, text=f"{int(val)}", fill=get_color_str("text"), font=("Inter", 9))
            # Date
            display_date = d[5:] # MM-DD
            canvas.create_text(x + bar_w/2, h - pad + 15, text=display_date, fill=get_color_str("text_dim"), font=("Inter", 9))
            
    def _draw_subject_chart(self, parent, subject_time):
        frame = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=15)
        frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(frame, text="Subject Distribution (Total Hours)", font=FONTS["header"],
                     text_color=COLORS["warning"]).pack(anchor="w", padx=20, pady=(15, 10))
        
        if not subject_time:
            ctk.CTkLabel(frame, text="No study data recorded.", text_color=COLORS["text_dim"]).pack(pady=20)
            return
            
        # Convert seconds to hours
        data = {k: v/3600 for k, v in subject_time.items() if v > 60}
        total_hours = sum(data.values())
        if total_hours == 0: return
        
        # Sort by time
        sorted_subjs = sorted(data.items(), key=lambda x: x[1], reverse=True)
        
        for subj, hours in sorted_subjs:
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=5)
            
            percent = hours / total_hours
            
            # Label
            ctk.CTkLabel(row, text=f"{subj} ({hours:.1f}h)", font=FONTS["body"], 
                         width=150, anchor="w").pack(side="left")
            
            # Progress Bar (Custom)
            # ctk.CTkProgressBar is good
            progress = ctk.CTkProgressBar(row, height=12, progress_color=COLORS["warning"])
            progress.set(percent if percent <= 1.0 else 1.0) # Relative to total? 
            # If we want relative to MAX subject, set relative to max.
            # If we want % of total time, set relative to total.
            # % of total is better for distribution.
            progress.pack(side="left", fill="x", expand=True, padx=10)
            
            ctk.CTkLabel(row, text=f"{int(percent*100)}%", width=40, 
                         font=FONTS["small"], text_color=COLORS["text_dim"]).pack(side="right")
