"""views_planner - split from ui.py (Focus Agent V2, Phase 6)."""

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
from .theme import COLORS, FONTS


class PlannerView(ctk.CTkFrame):
    """Deterministic daily planner UI: generate, review, explain, apply."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color=COLORS["bg"])
        self.app = app
        self.current_plan = None
        self.render()

    def render(self):
        for w in self.winfo_children(): w.destroy()

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(10, 5))
        ctk.CTkLabel(header, text="🗓️ Daily Planner", font=FONTS["title"]).pack(side="left")

        if not AGENT_AVAILABLE:
            ctk.CTkLabel(self, text="Planner unavailable (agent layer failed to load).",
                         text_color=COLORS["error"]).pack(pady=30)
            return

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.pack(fill="x", padx=20, pady=5)

        settings = self.app.data.get("settings") or {}
        iso_today = fdates.today_str(settings)
        ctk.CTkLabel(controls, text="Date (YYYY-MM-DD):", font=FONTS["body"]).pack(side="left")
        self.date_entry = ctk.CTkEntry(controls, width=120)
        self.date_entry.insert(0, iso_today)
        self.date_entry.pack(side="left", padx=8)

        ctk.CTkButton(controls, text="Today", width=70, fg_color=COLORS["card"],
                      hover_color=COLORS["card_hover"], text_color=COLORS["text"],
                      command=lambda: self._set_date(iso_today)).pack(side="left", padx=3)
        ctk.CTkButton(controls, text="Tomorrow", width=90, fg_color=COLORS["card"],
                      hover_color=COLORS["card_hover"], text_color=COLORS["text"],
                      command=lambda: self._set_date(
                          (fdates.now_here(settings).date() + timedelta(days=1)).isoformat())
                      ).pack(side="left", padx=3)

        self.generate_btn = ctk.CTkButton(controls, text="⚙ Generate Plan", width=130,
                                          fg_color=COLORS["accent"],
                                          command=self.generate_plan)
        self.generate_btn.pack(side="left", padx=12)

        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=10, pady=8)

        empty = ctk.CTkFrame(self.body, fg_color=COLORS["card"], corner_radius=15)
        empty.pack(fill="x", padx=10, pady=30)
        ctk.CTkLabel(empty, text="Generate a plan to see time slots, reasons and overload warnings.\nPlans respect your classes, study window and learned pace.",
                     text_color=COLORS["text_dim"], font=FONTS["body"], justify="center").pack(pady=30)

    def _set_date(self, iso):
        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, iso)

    def generate_plan(self):
        if self._busy_plan():
            return
        date_str = self.date_entry.get().strip()
        from focus_agent.schemas import valid_date
        if not valid_date(date_str):
            messagebox.showerror("Planner", "Date must be YYYY-MM-DD")
            return
        self.generate_btn.configure(state="disabled", text="Working…")
        self._render_plan_placeholder("⏳ Building a feasible plan…")

        def worker():
            plan = fsched.generate_day_plan(self.app.data, date_str,
                                            settings=self.app.data.get("settings"),
                                            commit=False)
            priorities = fsched.explain_priorities(self.app.data, date_str,
                                                   settings=self.app.data.get("settings"))
            self.after(0, lambda: self._render_plan(plan, priorities))
        threading.Thread(target=worker, daemon=True).start()

    def _busy_plan(self):
        return str(self.generate_btn.cget("state")) == "disabled"

    def _render_plan_placeholder(self, text):
        for w in self.body.winfo_children(): w.destroy()
        ctk.CTkLabel(self.body, text=text, font=FONTS["header"],
                     text_color=COLORS["text_dim"]).pack(pady=40)

    def _render_plan(self, plan, priorities):
        self.generate_btn.configure(state="normal", text="⚙ Generate Plan")
        self.current_plan = plan
        for w in self.body.winfo_children(): w.destroy()

        if not plan.slots and not plan.unscheduled:
            empty = ctk.CTkFrame(self.body, fg_color=COLORS["card"], corner_radius=15)
            empty.pack(fill="x", padx=10, pady=30)
            ctk.CTkLabel(empty, text="☕ Nothing to schedule - no open tasks for this date.",
                         text_color=COLORS["text_dim"], font=FONTS["header"]).pack(pady=30)
            return

        # Schedule card
        card = ctk.CTkFrame(self.body, fg_color=COLORS["card"], corner_radius=15)
        card.pack(fill="x", padx=10, pady=8)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=15, pady=(12, 4))
        ctk.CTkLabel(head, text=f"Schedule for {plan.date}", font=FONTS["header"]).pack(side="left")

        def apply_plan():
            fsched.apply_plan(self.app.data, plan)
            fmemory.log_plan(self.app.data, plan.to_dict())
            messagebox.showinfo("Planner", "Plan applied - task slots saved.")
            if "today" in self.app.views:
                self.app.views["today"].render()
        ctk.CTkButton(head, text="✅ Apply to Tasks", width=140, fg_color=COLORS["success"],
                      hover_color=COLORS["success_dark"], command=apply_plan).pack(side="right")

        self._wrappable = []
        for s in plan.slots:
            row = ctk.CTkFrame(
                card, fg_color=COLORS["bg_secondary"], corner_radius=8,
                border_width=1, border_color=COLORS["border"]
            )
            row.pack(fill="x", padx=12, pady=4)
            mark = "📘" if s.fixed else "🎯"
            ctk.CTkLabel(row, text=f"{mark} {s.start}–{s.end}", font=FONTS["subheader"],
                         width=115, text_color=COLORS["accent"]).pack(side="left", padx=10, pady=8)

            if not s.fixed and hasattr(self.app, "start_focus_for_task"):
                # Calculate slot duration in minutes
                dur_m = getattr(s, "minutes", None) or 25
                ctk.CTkButton(
                    row, text="▶ Start Focus", width=105, height=28,
                    fg_color=COLORS["accent"], hover_color=COLORS["accent_dark"],
                    text_color="white", corner_radius=6, font=FONTS["small"],
                    command=lambda t=s.title, d=dur_m: self.app.start_focus_for_task(t, d)
                ).pack(side="right", padx=10, pady=6)

            title = s.title + (f"  (part {s.chunk}/{s.chunks})" if s.chunks > 1 else "")
            ctk.CTkLabel(row, text=title, font=FONTS["subheader"], text_color=COLORS["text"]).pack(side="left", padx=4)
            rlbl = ctk.CTkLabel(row, text=s.reason, font=FONTS["tiny"],
                                text_color=COLORS["text_dim"], wraplength=280,
                                justify="left")
            rlbl.pack(side="right", padx=10, pady=4)
            self._wrappable.append(rlbl)

        # Unscheduled
        for u in plan.unscheduled:
            row = ctk.CTkFrame(card, fg_color=COLORS["error"], corner_radius=8)
            row.pack(fill="x", padx=12, pady=3)
            ctk.CTkLabel(row, text=f"⚠ {u['title']}", font=FONTS["small"],
                         text_color="#1a1a1a").pack(anchor="w", padx=10, pady=(4, 0))
            ulbl = ctk.CTkLabel(row, text=u["reason"], font=FONTS["tiny"],
                                text_color="#1a1a1a", wraplength=560,
                                justify="left")
            ulbl.pack(anchor="w", padx=10, pady=(0, 4))
            self._wrappable.append(ulbl)

        for note in plan.notes:
            nlbl = ctk.CTkLabel(card, text=note, font=FONTS["small"],
                                text_color=COLORS["text_dim"], wraplength=560,
                                justify="left")
            nlbl.pack(anchor="w", padx=15, pady=2)
            self._wrappable.append(nlbl)

        # Priority explanation card
        if priorities:
            pcard = ctk.CTkFrame(self.body, fg_color=COLORS["card"], corner_radius=15)
            pcard.pack(fill="x", padx=10, pady=8)
            ctk.CTkLabel(pcard, text="Why this order?", font=FONTS["header"]).pack(anchor="w", padx=15, pady=(12, 4))
            for item in priorities[:8]:
                due = f" (due {item['due_date']})" if item.get("due_date") else ""
                plbl = ctk.CTkLabel(pcard, text=f"{item['rank']}. {item['title']}{due} — {item['reason']}",
                                    font=FONTS["small"], text_color=COLORS["text"], wraplength=560,
                                    justify="left")
                plbl.pack(anchor="w", padx=15, pady=2)
                self._wrappable.append(plbl)

    def on_resize(self, width, height):
        w_full = max(260, int(width - 90))
        for lbl in getattr(self, "_wrappable", []):
            try:
                if lbl.winfo_exists():
                    lbl.configure(wraplength=w_full)
            except Exception:
                pass


# ==================== GOALS VIEW ====================
