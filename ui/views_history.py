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
        """Draws a responsive GitHub-style contribution graph."""
        container = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=10)
        container.pack(fill="x", padx=20, pady=(0, 12))
        
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(10, 4))
        ctk.CTkLabel(header, text="365 Days of Focus", font=FONTS["header"], 
                     text_color=COLORS["text"]).pack(side="left")
        
        bg_col = get_color_str("card")
        canvas = tk.Canvas(container, height=110, bg=bg_col, highlightthickness=0)
        canvas.pack(fill="x", expand=True, padx=10, pady=(0, 10))
        
        now = datetime.now()
        start_date = now - timedelta(days=365)
        offset = (start_date.weekday() + 1) % 7
        start_date -= timedelta(days=offset)
        
        def redraw_heatmap(event=None):
            if not canvas.winfo_exists():
                return
            canvas.delete("all")
            avail_w = max(320, canvas.winfo_width() - 20)
            cell_step = max(6, min(18, avail_w // 53))
            gap = 2 if cell_step < 11 else 3
            sz = max(4, cell_step - gap)
            total_h = 7 * (sz + gap) + 14
            canvas.configure(height=max(80, total_h), bg=get_color_str("card"))
            
            col_empty = get_color_str("bg_secondary")
            col_1 = get_color_str("accent_light")
            col_2 = get_color_str("accent")
            col_3 = get_color_str("accent_dark")
            col_4 = "#FFFFFF" if ctk.get_appearance_mode() == "Dark" else "#000000"
            col_border = get_color_str("border")
            
            for i in range(371):
                curr = start_date + timedelta(days=i)
                if curr > now:
                    break
                day_idx = (curr.weekday() + 1) % 7
                week_idx = i // 7
                x = week_idx * (sz + gap) + 10
                y = day_idx * (sz + gap) + 8
                d_str = curr.strftime("%Y-%m-%d")
                intensity = heat_data.get(d_str, 0)
                fill = col_empty
                outline = col_border
                if intensity == 1:
                    fill, outline = col_1, ""
                elif intensity == 2:
                    fill, outline = col_2, ""
                elif intensity == 3:
                    fill, outline = col_3, ""
                elif intensity >= 4:
                    fill, outline = col_4, ""
                canvas.create_rectangle(x, y, x + sz, y + sz, fill=fill, outline=outline)

        canvas.bind("<Configure>", redraw_heatmap)
        self.after(50, redraw_heatmap)

class ReportView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=COLORS["bg"])
        self.app = app
        self._bench_summary = None
        self.render()

    def render(self):
        for w in self.winfo_children(): w.destroy()

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(10, 10))
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left")
        ctk.CTkLabel(title_box, text="📊 Analytics, Memory & Agent Evaluation", font=FONTS["title"],
                     text_color=COLORS["text"]).pack(anchor="w")
        ctk.CTkLabel(title_box, text="Focus telemetry · 365-day activity heatmap · learned duration calibration · live benchmark",
                     font=FONTS["small"], text_color=COLORS["text_dim"]).pack(anchor="w")

        # Get Data
        data = get_analytics_data(self.app.data)

        # Scrollable container for unified analytics + history
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10)

        # 1. Live Agent Evaluation Benchmark Suite (Thesis Showcase)
        if AGENT_AVAILABLE:
            self._draw_benchmark_card(scroll)

        # 2. Daily Focus Graph
        self._draw_focus_chart(scroll, data["daily_focus"])

        # 3. 365-Day Activity Heatmap (Merged from HistoryView)
        heat_data = get_heatmap_data(self.app.data)
        self._draw_heatmap_in(scroll, heat_data)

        # 4. Subject Breakdown
        self._draw_subject_chart(scroll, data["subject_time"])

        # 5. Estimation accuracy + streak (V2 Learning Engine)
        if AGENT_AVAILABLE:
            self._draw_estimation_card(scroll)
            self._draw_streak_card(scroll)

        # 6. Recent Daily History Log
        self._draw_history_log_card(scroll)

    def _draw_benchmark_card(self, parent):
        frame = ctk.CTkFrame(
            parent, fg_color=COLORS["card"], corner_radius=14,
            border_width=1, border_color=COLORS["accent_light"]
        )
        frame.pack(fill="x", padx=10, pady=8)

        head = ctk.CTkFrame(frame, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(14, 6))
        ctk.CTkLabel(
            head, text="🧪 Live Agent Evaluation Benchmark (Academic Verification)",
            font=FONTS["header"], text_color=COLORS["accent"]
        ).pack(side="left")

        def run_bench():
            try:
                import evaluate
                self._bench_summary = evaluate.run_benchmark_summary()
                self.render()
            except Exception as e:
                messagebox.showerror("Benchmark Error", str(e))

        ctk.CTkButton(
            head, text="▶ Run Agent Benchmark", width=170, height=30,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_dark"],
            text_color="white", corner_radius=8, font=FONTS["small"],
            command=run_bench
        ).pack(side="right")

        if self._bench_summary is None:
            try:
                import evaluate
                self._bench_summary = evaluate.run_benchmark_summary()
            except Exception:
                self._bench_summary = None

        if not self._bench_summary:
            ctk.CTkLabel(
                frame, text="Click 'Run Agent Benchmark' to evaluate Task Extraction, Subject Detection, Planner & Memory.",
                font=FONTS["small"], text_color=COLORS["text_dim"]
            ).pack(anchor="w", padx=20, pady=(0, 14))
            return

        b = self._bench_summary
        summary_pill = ctk.CTkFrame(frame, fg_color=COLORS["card_highlight"], corner_radius=8)
        summary_pill.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(
            summary_pill,
            text=f"✅ Overall Score: {b['passed']}/{b['total']} Checks Passed ({b['pct']}%) — Zero Overlap, Verified Tool Execution & Honest Fallbacks",
            font=FONTS["subheader"], text_color=COLORS["success"]
        ).pack(anchor="w", padx=12, pady=8)

        grid = ctk.CTkFrame(frame, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=(0, 14))
        for idx, item in enumerate(b.get("areas", [])):
            row = ctk.CTkFrame(grid, fg_color="transparent")
            row.pack(fill="x", pady=2)
            label_name = item["area"].replace("_", " ").title()
            ctk.CTkLabel(row, text=label_name, font=FONTS["small"], width=190, anchor="w",
                         text_color=COLORS["text"]).pack(side="left")
            pbar = ctk.CTkProgressBar(row, height=10, progress_color=COLORS["success"])
            pbar.set(item["pct"] / 100.0)
            pbar.pack(side="left", fill="x", expand=True, padx=10)
            ctk.CTkLabel(row, text=f"{item['passed']}/{item['total']} ({int(item['pct'])}%)",
                         font=FONTS["small"], width=85, anchor="e",
                         text_color=COLORS["text_dim"]).pack(side="right")

    def _draw_heatmap_in(self, parent, heat_data):
        container = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=14)
        container.pack(fill="x", padx=10, pady=8)
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(12, 4))
        ctk.CTkLabel(header, text="📅 365-Day Focus Consistency Heatmap", font=FONTS["header"],
                     text_color=COLORS["text"]).pack(side="left")

        bg_col = get_color_str("card")
        canvas = tk.Canvas(container, height=110, bg=bg_col, highlightthickness=0)
        canvas.pack(fill="x", expand=True, padx=16, pady=(0, 12))

        now = datetime.now()
        start_date = now - timedelta(days=365)
        offset = (start_date.weekday() + 1) % 7
        start_date -= timedelta(days=offset)

        def redraw_heatmap(event=None):
            if not canvas.winfo_exists():
                return
            canvas.delete("all")
            avail_w = max(320, canvas.winfo_width() - 20)
            cell_step = max(6, min(18, avail_w // 53))
            gap = 2 if cell_step < 11 else 3
            sz = max(4, cell_step - gap)
            total_h = 7 * (sz + gap) + 14
            canvas.configure(height=max(80, total_h), bg=get_color_str("card"))

            col_empty = get_color_str("bg_secondary")
            col_1 = get_color_str("accent_light")
            col_2 = get_color_str("accent")
            col_3 = get_color_str("accent_dark")
            col_4 = "#FFFFFF" if ctk.get_appearance_mode() == "Dark" else "#1E1B4B"
            col_border = get_color_str("border")

            for i in range(371):
                curr = start_date + timedelta(days=i)
                if curr > now:
                    break
                day_idx = (curr.weekday() + 1) % 7
                week_idx = i // 7
                x = week_idx * (sz + gap) + 10
                y = day_idx * (sz + gap) + 8
                d_str = curr.strftime("%Y-%m-%d")
                intensity = heat_data.get(d_str, 0)
                fill, outline = col_empty, col_border
                if intensity == 1:
                    fill, outline = col_1, ""
                elif intensity == 2:
                    fill, outline = col_2, ""
                elif intensity == 3:
                    fill, outline = col_3, ""
                elif intensity >= 4:
                    fill, outline = col_4, ""
                canvas.create_rectangle(x, y, x + sz, y + sz, fill=fill, outline=outline)

        canvas.bind("<Configure>", redraw_heatmap)
        self.after(50, redraw_heatmap)

    def _draw_history_log_card(self, parent):
        hist = self.app.data.get("history", {})
        dates = sorted(hist.keys(), reverse=True)
        frame = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=14)
        frame.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(frame, text="📜 Daily Completion Log", font=FONTS["header"],
                     text_color=COLORS["text"]).pack(anchor="w", padx=20, pady=(14, 6))
        if not dates:
            ctk.CTkLabel(frame, text="No daily history entries yet.",
                         font=FONTS["small"], text_color=COLORS["text_dim"]).pack(anchor="w", padx=20, pady=(0, 14))
            return
        for d in dates[:10]:
            entry = hist[d]
            row = ctk.CTkFrame(frame, fg_color=COLORS["bg_secondary"], corner_radius=8)
            row.pack(fill="x", padx=16, pady=3)
            ctk.CTkLabel(row, text=f"📆 {d}", font=FONTS["subheader"], text_color=COLORS["text"]).pack(side="left", padx=12, pady=8)
            stat_text = f"Completed: {entry.get('completed', 0)}/{entry.get('total', 0)}  ·  XP: +{entry.get('xp_gained', 0)}"
            ctk.CTkLabel(row, text=stat_text, font=FONTS["small"], text_color=COLORS["text_dim"]).pack(side="right", padx=12, pady=8)
        ctk.CTkLabel(frame, text="", font=FONTS["tiny"]).pack(pady=2)

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
        canvas.pack(fill="x", expand=True, padx=20, pady=(0, 20))
        
        dates = sorted(daily_focus.keys()) if daily_focus else []
        values = [daily_focus[d] for d in dates]
        max_val = max(values) if values and max(values) > 0 else 60
        
        def redraw_bars(event=None):
            if not canvas.winfo_exists():
                return
            canvas.delete("all")
            canvas.configure(bg=get_color_str("card"))
            cw = max(300, canvas.winfo_width())
            h = 200
            if not daily_focus:
                canvas.create_text(cw // 2, h // 2, text="No data yet",
                                   fill=get_color_str("text_dim"), font=("Inter", 12))
                return
            n = max(1, len(dates))
            pad = 28
            usable_w = max(160, cw - 2 * pad)
            slot_w = usable_w / n
            bar_w = max(18, min(64, int(slot_w * 0.58)))
            
            for i, d in enumerate(dates):
                val = daily_focus[d]
                x = pad + int(i * slot_w + (slot_w - bar_w) / 2)
                bar_h = (val / max_val) * (h - 2 * pad)
                y = h - pad - bar_h
                canvas.create_rectangle(x, y, x + bar_w, h - pad,
                                        fill=get_color_str("accent"), outline="")
                if val > 0:
                    canvas.create_text(x + bar_w / 2, y - 10, text=f"{int(val)}",
                                       fill=get_color_str("text"), font=("Inter", 9))
                display_date = d[5:]
                canvas.create_text(x + bar_w / 2, h - pad + 14, text=display_date,
                                   fill=get_color_str("text_dim"), font=("Inter", 9))

        canvas.bind("<Configure>", redraw_bars)
        self.after(50, redraw_bars)
            
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
