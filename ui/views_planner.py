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
        self.current_priorities = None
        self.current_date_str = None
        self._busy_generating = False
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
        self.date_entry.insert(0, self.current_date_str or iso_today)
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

        if self._busy_generating:
            self.generate_btn.configure(state="disabled", text="Working…")
            self._render_plan_placeholder("⏳ Building a feasible plan…")
        elif self.current_plan is not None:
            self._render_plan(self.current_plan, self.current_priorities)
        else:
            # Automatically build today's plan on first open so the user sees their schedule right away
            self.generate_plan()

    def _set_date(self, iso):
        self.current_date_str = iso
        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, iso)
        self.generate_plan()

    def _quick_fix_duration(self, task_id, minutes=60):
        t = get_task_by_id(self.app.data, task_id)
        if t:
            t["duration"] = minutes
            save_data(self.app.data)
            self.generate_plan()

    def generate_plan(self):
        if self._busy_plan():
            return
        date_str = self.date_entry.get().strip()
        from focus_agent.schemas import valid_date
        if not valid_date(date_str):
            messagebox.showerror("Planner", "Date must be YYYY-MM-DD")
            return
        self.current_date_str = date_str
        self._busy_generating = True
        self.generate_btn.configure(state="disabled", text="Working…")
        self._render_plan_placeholder("⏳ Building a feasible plan…")

        def worker():
            try:
                plan = fsched.generate_day_plan(self.app.data, date_str,
                                                settings=self.app.data.get("settings"),
                                                commit=False)
                priorities = fsched.explain_priorities(self.app.data, date_str,
                                                       settings=self.app.data.get("settings"))
                self.after(0, lambda: self._render_plan(plan, priorities))
            except Exception as err:
                def on_err():
                    self._busy_generating = False
                    if hasattr(self, "generate_btn") and self.generate_btn.winfo_exists():
                        self.generate_btn.configure(state="normal", text="⚙ Generate Plan")
                    self._render_plan_placeholder(f"⚠️ Could not build plan: {err}")
                self.after(0, on_err)
        threading.Thread(target=worker, daemon=True).start()

    def _busy_plan(self):
        return bool(self._busy_generating)

    def _render_plan_placeholder(self, text):
        if not hasattr(self, "body") or not self.body.winfo_exists():
            return
        for w in self.body.winfo_children(): w.destroy()
        ctk.CTkLabel(self.body, text=text, font=FONTS["header"],
                     text_color=COLORS["text_dim"]).pack(pady=40)

    def _render_plan(self, plan, priorities):
        self._busy_generating = False
        self.current_plan = plan
        self.current_priorities = priorities
        if hasattr(self, "generate_btn") and self.generate_btn.winfo_exists():
            self.generate_btn.configure(state="normal", text="⚙ Generate Plan")
        if not hasattr(self, "body") or not self.body.winfo_exists():
            return
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

        def export_ics():
            default_name = f"focus_schedule_{plan.date}.ics"
            path = filedialog.asksaveasfilename(
                title="Export Daily Schedule (.ics Calendar)",
                defaultextension=".ics",
                initialfile=default_name,
                filetypes=[("iCalendar File (.ics)", "*.ics"), ("All files", "*.*")]
            )
            if not path:
                return
            from focus_agent.media_import import export_plan_to_ics
            ok, msg = export_plan_to_ics(plan, path)
            if ok:
                messagebox.showinfo("Export Calendar", f"✅ {msg}\nYou can import this .ics file into Google Calendar, Outlook, or your phone.")
            else:
                messagebox.showerror("Export Calendar", msg)

        ctk.CTkButton(head, text="✅ Apply to Tasks", width=136, fg_color=COLORS["success"],
                      hover_color=COLORS["success_dark"], command=apply_plan).pack(side="right", padx=(6, 0))
        ctk.CTkButton(head, text="📅 Export .ics", width=116, fg_color=COLORS["bg_secondary"],
                      hover_color=COLORS["card_hover"], text_color=COLORS["accent"],
                      border_width=1, border_color=COLORS["border"],
                      command=export_ics).pack(side="right")

        self._wrappable = []
        wrap_w = max(280, int(self.winfo_width() - 120)) if self.winfo_width() > 200 else 520
        for s in plan.slots:
            row = ctk.CTkFrame(
                card, fg_color=COLORS["bg_secondary"], corner_radius=10,
                border_width=1, border_color=COLORS["border"]
            )
            row.pack(fill="x", padx=12, pady=5)

            top_line = ctk.CTkFrame(row, fg_color="transparent")
            top_line.pack(fill="x", padx=10, pady=(8, 2))

            mark = "📘" if s.fixed else "🎯"
            ctk.CTkLabel(top_line, text=f"{mark} {s.start}–{s.end}", font=FONTS["subheader"],
                         width=112, anchor="w", text_color=COLORS["accent"]).pack(side="left", padx=(2, 8))

            if not s.fixed and hasattr(self.app, "start_focus_for_task"):
                # Calculate exact slot duration in minutes from start/end
                s_min = fdates.hhmm_to_minutes(s.start) or 0
                e_min = fdates.hhmm_to_minutes(s.end) or (s_min + 25)
                dur_m = max(5, e_min - s_min)
                ctk.CTkButton(
                    top_line, text=f"▶ Start ({dur_m}m)", width=112, height=28,
                    fg_color=COLORS["accent"], hover_color=COLORS["accent_dark"],
                    text_color="white", corner_radius=6, font=FONTS["small"],
                    command=lambda t=s.title, d=dur_m: self.app.start_focus_for_task(t, d)
                ).pack(side="right", padx=(8, 2))

            title = s.title + (f"  (part {s.chunk}/{s.chunks})" if s.chunks > 1 else "")
            tlbl = ctk.CTkLabel(
                top_line, text=title, font=FONTS["subheader"],
                text_color=COLORS["text"], wraplength=max(200, wrap_w - 180),
                justify="left", anchor="w"
            )
            tlbl.pack(side="left", fill="x", expand=True, padx=4)
            self._wrappable.append(tlbl)

            if s.reason:
                rlbl = ctk.CTkLabel(
                    row, text=f"💡 {s.reason}", font=FONTS["tiny"],
                    text_color=COLORS["text_dim"], wraplength=wrap_w,
                    justify="left", anchor="w"
                )
                rlbl.pack(fill="x", padx=14, pady=(0, 7), anchor="w")
                self._wrappable.append(rlbl)

        # Unscheduled
        for u in plan.unscheduled:
            row = ctk.CTkFrame(
                card, fg_color=COLORS["card_highlight"], corner_radius=8,
                border_width=1, border_color=COLORS["warning"]
            )
            row.pack(fill="x", padx=12, pady=4)
            u_top = ctk.CTkFrame(row, fg_color="transparent")
            u_top.pack(fill="x", padx=10, pady=(6, 2))
            ctk.CTkLabel(u_top, text=f"⚠ {u['title']}", font=FONTS["small"],
                         text_color=COLORS["warning"]).pack(side="left")
            if "no duration estimate" in (u.get("reason") or "") and u.get("task_id"):
                ctk.CTkButton(
                    u_top, text="⏱ Set 60m & Schedule", width=145, height=24,
                    fg_color=COLORS["accent"], hover_color=COLORS["accent_dark"],
                    text_color="white", corner_radius=6, font=FONTS["tiny"],
                    command=lambda tid=u["task_id"]: self._quick_fix_duration(tid, 60)
                ).pack(side="right")
            ulbl = ctk.CTkLabel(row, text=u["reason"], font=FONTS["tiny"],
                                text_color=COLORS["text_dim"], wraplength=wrap_w,
                                justify="left")
            ulbl.pack(anchor="w", padx=10, pady=(0, 6))
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
