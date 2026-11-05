"""views_goals - split from ui.py (Focus Agent V2, Phase 6)."""

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
from .theme import COLORS, FONTS


class GoalsView(ctk.CTkFrame):
    """Long-term goals, milestones and roadmap drafts."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color=COLORS["bg"])
        self.app = app
        self.render()

    def render(self):
        for w in self.winfo_children(): w.destroy()

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(10, 5))
        ctk.CTkLabel(header, text="🎯 Goals & Roadmaps", font=FONTS["title"]).pack(side="left")
        ctk.CTkButton(header, text="+ New Goal", width=110, height=32,
                      fg_color=COLORS["accent"], command=self.prompt_new_goal).pack(side="right")

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=8)

        goals = self.app.data.get("goals", [])
        if not goals:
            empty = ctk.CTkFrame(scroll, fg_color=COLORS["card"], corner_radius=15)
            empty.pack(fill="x", padx=10, pady=40)
            ctk.CTkLabel(empty, text="No goals yet.\nTell the assistant 'I want to learn robotics' or create one here.",
                         text_color=COLORS["text_dim"], font=FONTS["header"],
                         justify="center").pack(pady=30)
            return

        for goal in goals:
            self._draw_goal_card(scroll, goal)

    def _draw_goal_card(self, parent, goal):
        from focus_agent.schemas import clean_str as _cs
        card = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=15)
        card.pack(fill="x", padx=10, pady=8)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=15, pady=(12, 2))
        status = goal.get("status", "active")
        icon = {"active": "🎯", "paused": "⏸", "done": "🏆"}.get(status, "🎯")
        ctk.CTkLabel(top, text=f"{icon} {goal.get('title', '')}", font=FONTS["header"]).pack(side="left")
        if goal.get("target_date"):
            ctk.CTkLabel(top, text=f"by {goal['target_date']}", font=FONTS["small"],
                         text_color=COLORS["text_dim"]).pack(side="left", padx=10)

        prog = fgoals.goal_progress(self.app.data, goal) if AGENT_AVAILABLE else {}

        # progress bar
        bar_row = ctk.CTkFrame(card, fg_color="transparent")
        bar_row.pack(fill="x", padx=15, pady=4)
        pct = (prog.get("percent") or 0) / 100
        bar = ctk.CTkProgressBar(bar_row, height=10, progress_color=COLORS["success"])
        bar.set(pct)
        bar.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(bar_row, text=f"{int((prog.get('percent') or 0))}%", width=40,
                     font=FONTS["small"], text_color=COLORS["text_dim"]).pack(side="left", padx=8)

        ms_txt = f"{prog.get('milestones_done', 0)}/{prog.get('milestones_total', 0)} milestones"
        tasks_txt = f" · {prog.get('tasks_done', 0)}/{prog.get('tasks_total', 0)} linked tasks done"
        ctk.CTkLabel(card, text=ms_txt + tasks_txt, font=FONTS["small"],
                     text_color=COLORS["text_dim"]).pack(anchor="w", padx=15)

        if status == "active" and prog.get("next_milestone"):
            nm = prog["next_milestone"]
            due = f" (by {nm['target_date']})" if nm.get("target_date") else ""
            ctk.CTkLabel(card, text=f"➡ Next: {nm['title']}{due}", font=FONTS["small"],
                         text_color=COLORS["accent"]).pack(anchor="w", padx=15)
        for ov in (prog.get("overdue_milestones") or [])[:3]:
            ctk.CTkLabel(card, text=f"⚠ Overdue: {ov['title']} (was due {ov['target_date']})",
                         font=FONTS["small"], text_color=COLORS["error"]).pack(anchor="w", padx=15)

        # milestones
        for ms in goal.get("milestones", []):
            row = ctk.CTkFrame(card, fg_color=COLORS["bg_secondary"], corner_radius=8)
            row.pack(fill="x", padx=15, pady=2)
            var = ctk.BooleanVar(value=bool(ms.get("done")))

            def toggle(mid=ms["id"], gid=goal["id"], v=var):
                fgoals.update_milestone(self.app.data, gid, mid, done=v.get())
                add_xp(self.app.data, 10) if v.get() else None
                self.app.refresh_xp()
                self.render()
            chk = ctk.CTkCheckBox(row, text=ms.get("title", ""), variable=var, command=toggle,
                                  fg_color=COLORS["success"])
            chk.pack(side="left", padx=10, pady=4)
            if ms.get("target_date"):
                overdue = (not ms.get("done") and ms["target_date"] < today())
                ctk.CTkLabel(row, text=f"by {ms['target_date']}", font=FONTS["tiny"],
                             text_color=COLORS["error"] if overdue else COLORS["text_dim"]).pack(side="left", padx=6)
            ctk.CTkButton(row, text="✕", width=24, height=20, font=FONTS["tiny"],
                          fg_color="transparent", text_color=COLORS["error"],
                          command=lambda mid=ms["id"], gid=goal["id"]: self._delete_milestone(gid, mid)
                          ).pack(side="right", padx=8)
            ctk.CTkButton(row, text="+ Task", width=60, height=20, font=FONTS["tiny"],
                          fg_color=COLORS["card"], text_color=COLORS["text"],
                          command=lambda m=ms, g=goal: self._task_from_milestone(g, m)
                          ).pack(side="right", padx=4)

        # actions
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=15, pady=(6, 12))
        ctk.CTkButton(actions, text="+ Milestone", width=100, height=26, font=FONTS["small"],
                      fg_color=COLORS["card"], hover_color=COLORS["card_hover"],
                      text_color=COLORS["text"],
                      command=lambda g=goal: self.prompt_new_milestone(g)).pack(side="left", padx=3)
        new_status = "paused" if status == "active" else "active"
        ctk.CTkButton(actions, text="⏸ Pause" if status == "active" else "▶ Resume",
                      width=90, height=26, font=FONTS["small"], fg_color=COLORS["card"],
                      hover_color=COLORS["card_hover"], text_color=COLORS["text"],
                      command=lambda g=goal, s=new_status: self._set_status(g, s)).pack(side="left", padx=3)
        if status != "done":
            ctk.CTkButton(actions, text="🏆 Mark Achieved", width=110, height=26, font=FONTS["small"],
                          fg_color=COLORS["success_dark"],
                          command=lambda g=goal: self._set_status(g, "done")).pack(side="left", padx=3)
        ctk.CTkButton(actions, text="🗑 Delete", width=80, height=26, font=FONTS["small"],
                      fg_color="transparent", text_color=COLORS["error"],
                      command=lambda g=goal: self._delete_goal(g)).pack(side="right", padx=3)

    # ------------- actions -------------

    def prompt_new_goal(self):
        title = simpledialog.askstring("New Goal", "Goal title (e.g. Learn AI/ML):", parent=self)
        if not title:
            return
        target = simpledialog.askstring("New Goal", "Target date YYYY-MM-DD (optional):", parent=self)
        from focus_agent.schemas import valid_date
        if target and not valid_date(target):
            messagebox.showerror("Goals", "Date must be YYYY-MM-DD")
            return
        goal, err = fgoals.add_goal(self.app.data, title, target_date=target)
        if err:
            messagebox.showerror("Goals", err)
        else:
            self.render()

    def prompt_new_milestone(self, goal):
        title = simpledialog.askstring("New Milestone", f"Milestone for '{goal['title']}':", parent=self)
        if not title:
            return
        target = simpledialog.askstring("New Milestone", "Target date YYYY-MM-DD (optional):", parent=self)
        from focus_agent.schemas import valid_date
        if target and not valid_date(target):
            messagebox.showerror("Goals", "Date must be YYYY-MM-DD")
            return
        fgoals.add_milestone(self.app.data, goal["id"], title, target_date=target)
        self.render()

    def _task_from_milestone(self, goal, ms):
        """Turn a milestone into a schedulable task linked to the goal."""
        task = add_task_logic(self.app.data, ms.get("title") or "Milestone task",
                              deadline=ms.get("target_date"),
                              duration=ms.get("estimated_minutes"),
                              goal_id=goal["id"],
                              subject=goal.get("subject"))
        messagebox.showinfo("Goals", f"Task created from milestone (est. {task.get('duration') or '?'} min).\nAsk the assistant to 'plan my day' to schedule it.")
        if "today" in self.app.views:
            self.app.views["today"].render()

    def _set_status(self, goal, status):
        ok, err = fgoals.update_goal(self.app.data, goal["id"], status=status)
        if err:
            messagebox.showerror("Goals", err)
        if status == "done":
            add_xp(self.app.data, 50)
            self.app.refresh_xp()
        self.render()

    def _delete_goal(self, goal):
        if messagebox.askyesno("Delete Goal",
                               f"Delete '{goal.get('title')}'?\nLinked tasks are kept but unlinked."):
            fgoals.delete_goal(self.app.data, goal["id"])
            self.render()

    def _delete_milestone(self, goal_id, milestone_id):
        fgoals.delete_milestone(self.app.data, goal_id, milestone_id)
        self.render()
