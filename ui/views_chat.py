"""views_chat - split from ui.py (Focus Agent V2, Phase 6)."""

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


class ChatView(ctk.CTkFrame):
    """AI assistant backed by the validated agent controller.

    Runs agent turns on a worker thread (UI never freezes); destructive tool
    actions pop a confirmation dialog bridged back to the worker via a queue.
    Every executed action appears as a tool chip under the reply.
    """

    def __init__(self, parent, app):
        super().__init__(parent, fg_color=COLORS["bg"])
        self.app = app
        self.history = []  # [{'role': 'user'|'assistant', 'content': '...'}]
        self.controller = AgentController(app.data) if AGENT_AVAILABLE else None
        self._busy = False
        self._confirm_answers = queue.Queue()
        self._status_checked = False
        self.render()

    def render(self):
        for w in self.winfo_children(): w.destroy()

        # Header with provider status
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(10, 10))
        ctk.CTkLabel(header, text="🤖 AI Assistant", font=FONTS["title"]).pack(side="left")

        self.status_lbl = ctk.CTkLabel(header, text="● checking…",
                                       font=FONTS["small"], text_color=COLORS["text_dim"])
        self.status_lbl.pack(side="right")
        if not AGENT_AVAILABLE:
            self.status_lbl.configure(text="● agent layer unavailable", text_color=COLORS["error"])

        self.status_dot = None
        if not self._status_checked and AGENT_AVAILABLE:
            self._check_provider_status_async()

        # Chat area
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["sidebar"], corner_radius=15)
        self.scroll.pack(fill="both", expand=True, padx=20, pady=10)

        # Input area
        input_frame = ctk.CTkFrame(self, fg_color=COLORS["card"], height=60, corner_radius=20)
        input_frame.pack(fill="x", padx=20, pady=(10, 20))

        self.entry = ctk.CTkEntry(input_frame, placeholder_text="Try: 'Tomorrow submit my AI assignment; it will take about two hours'",
                                  font=FONTS["body"], fg_color="transparent", border_width=0)
        self.entry.pack(side="left", fill="both", expand=True, padx=(20, 10), pady=10)
        self.entry.bind("<Return>", lambda e: self.send_message())

        ctk.CTkButton(input_frame, text="📎", width=40, height=36, corner_radius=15,
                      fg_color="transparent", text_color=COLORS["accent"],
                      hover_color=COLORS["card_hover"], command=self.upload_image).pack(side="left", padx=5)

        self.send_btn = ctk.CTkButton(input_frame, text="Send 🚀", width=90, height=36, corner_radius=15,
                                      fg_color=COLORS["accent"], command=self.send_message)
        self.send_btn.pack(side="right", padx=10)

        if not self.history:
            self.add_message("assistant",
                "Hello! I'm your To Do Agent. I don't just chat - I take real actions:\n"
                "• \"Tomorrow submit my AI assignment; it will take about two hours\"\n"
                "• \"Plan my day\" — get a conflict-free schedule\n"
                "• \"Move the unfinished database task to my next available slot\"\n"
                "• \"I want to learn robotics\" — build a goal roadmap\n"
                "• \"What should I prioritize?\" — transparent reasoning",
                render_only=True)

    # ---------------- provider status ----------------

    def _check_provider_status_async(self):
        self._status_checked = True

        def run():
            ok, detail = False, "agent unavailable"
            if AGENT_AVAILABLE:
                settings = self.app.data.get("settings") or {}
                primary, online = fllm.get_providers(settings)
                ok, detail = primary.status()
            def apply():
                try:
                    self.status_lbl.configure(
                        text=("● " + detail[:60]),
                        text_color=COLORS["success"] if ok else COLORS["warning"])
                except Exception:
                    pass
            self.after(0, apply)
        threading.Thread(target=run, daemon=True).start()

    # ---------------- sending ----------------

    def send_message(self):
        msg = self.entry.get().strip()
        if not msg or self._busy:
            return
        self.entry.delete(0, "end")
        self.add_message("user", msg)
        self._set_busy(True)
        thinking = self.add_message("assistant", "Thinking… 🧠", is_temporary=True)

        def worker():
            try:
                reply = self.controller.handle(msg, history=self.history,
                                               confirm_callback=self._confirm_from_ui)
            except Exception as e:
                reply = None
                err = f"Agent error: {e.__class__.__name__}: {e}"
            self.after(0, lambda: self._deliver(reply if reply else None,
                                                err if not reply else None,
                                                thinking))
        threading.Thread(target=worker, daemon=True).start()

    def _confirm_from_ui(self, question):
        """Runs on the worker thread; asks the UI thread and waits for the answer."""
        box = queue.Queue()
        self.after(0, lambda: self._show_confirm(question, box))
        try:
            return bool(box.get(timeout=180))
        except queue.Empty:
            return False

    def _show_confirm(self, question, box):
        try:
            answer = messagebox.askyesno("Confirm agent action", question, parent=self)
        except Exception:
            answer = False
        box.put(answer)

    def _deliver(self, reply, err, thinking_lbl):
        try:
            thinking_lbl.destroy()
        except Exception:
            pass
        if err:
            self.add_message("assistant", f"⚠️ {err}")
        else:
            # honest execution trail first: only steps the loop really took
            for ev in (getattr(reply, "events", None) or []):
                self._add_event_line(ev)
            self.add_message("assistant", reply.message)
            for tr in reply.tool_results:
                self._add_tool_chip(tr)
            if reply.plan:
                self._add_plan_chip(reply.plan)
            self._refresh_after_action(reply)
        self._set_busy(False)

    def _add_event_line(self, ev):
        """One loop step, rendered as a subtle status line. Only real events
        are ever shown (spec: no fabricated execution statuses)."""
        etype = ev.get("type")
        if etype == "tool_result":
            return  # already rendered as a tool chip
        style = {
            "status": ("…", COLORS["text_dim"]),
            "verification": ("✓", COLORS["success_dark"]),
            "repeat": ("↺", COLORS["text_dim"]),
            "budget": ("⏸", COLORS["warning_dark"] if "warning_dark" in COLORS
                       else COLORS["text_dim"]),
            "question": ("❓", COLORS["accent"]),
            "error": ("⚠", COLORS["error"]),
        }.get(etype, ("•", COLORS["text_dim"]))
        icon, color = style
        text = (ev.get("text") or "")[:240]
        chip = ctk.CTkFrame(self.scroll, fg_color="transparent")
        chip.pack(fill="x", padx=10, pady=0, anchor="w")
        ctk.CTkLabel(chip, text=f"{icon} {text}", font=FONTS["small"],
                     text_color=color, wraplength=480,
                     justify="left").pack(padx=12, pady=1, anchor="w")
        try:
            self.scroll._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _set_busy(self, busy):
        self._busy = busy
        self.send_btn.configure(state="disabled" if busy else "normal",
                                text="Thinking…" if busy else "Send 🚀")

    # ---------------- message rendering ----------------

    def add_message(self, role, content, is_temporary=False, render_only=False):
        bubble_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        bubble_frame.pack(fill="x", pady=5)

        align = "right" if role == "user" else "left"
        bg_col = COLORS["accent"] if role == "user" else COLORS["card"]
        text_col = "white" if role == "user" else COLORS["text"]

        bubble = ctk.CTkFrame(bubble_frame, fg_color=bg_col, corner_radius=15)
        bubble.pack(side=align, padx=10, pady=2, anchor="e" if role == "user" else "w")

        msg_lbl = ctk.CTkLabel(bubble, text=content, font=FONTS["body"], text_color=text_col,
                               wraplength=520, justify="left")
        msg_lbl.pack(padx=15, pady=8)

        if not is_temporary and not render_only:
            self.history.append({"role": role, "content": content})

        try:
            self.scroll._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass
        return bubble_frame

    def _add_tool_chip(self, tr):
        """Show an executed (or rejected) tool action as a compact chip."""
        ok = getattr(tr, "ok", False)
        icon = "🔧" if ok else "🚫"
        text = (tr.message or tr.error or "")[:220]
        chip = ctk.CTkFrame(self.scroll, fg_color=COLORS["card_hover"], corner_radius=10)
        chip.pack(fill="x", padx=10, pady=1, anchor="w")
        ctk.CTkLabel(chip, text=f"{icon} {tr.tool}: {text}", font=FONTS["small"],
                     text_color=COLORS["success_dark"] if ok else COLORS["error"],
                     wraplength=480, justify="left").pack(padx=12, pady=4, anchor="w")
        try:
            self.scroll._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _add_plan_chip(self, plan):
        """Compact schedule preview chip with a button to open the Planner.
        Handles both single-day plans ({slots}) and range plans ({days})."""
        slots = plan.get("slots")
        day_list = plan.get("days")
        if slots is None and day_list:
            slots = [s for d in day_list for s in d.get("slots", [])]
        unsched = plan.get("unscheduled", [])
        if not unsched and day_list:
            unsched = []
        chip = ctk.CTkFrame(self.scroll, fg_color=COLORS["card_highlight"], corner_radius=10)
        chip.pack(fill="x", padx=10, pady=3, anchor="w")
        head = f"🗓 Proposed plan: {len(slots or [])} slot(s)"
        if plan.get("start_date") and plan.get("end_date") and \
                plan["start_date"] != plan["end_date"]:
            head += f" ({plan['start_date']} → {plan['end_date']})"
        if unsched:
            head += f", {len(unsched)} didn't fit"
        ctk.CTkLabel(chip, text=head, font=FONTS["small"],
                     text_color=COLORS["text"]).pack(padx=12, pady=(6, 2), anchor="w")
        for s in (slots or [])[:8]:
            mark = "✅" if s.get("fixed") else "•"
            ctk.CTkLabel(chip, text=f"   {mark} {s['start']}–{s['end']}  {s['title']}",
                         font=FONTS["small"], text_color=COLORS["text_dim"]).pack(anchor="w", padx=12)
        ctk.CTkButton(chip, text="Open Planner to apply →", height=24, width=170,
                      fg_color=COLORS["accent"],
                      command=lambda: self.app.switch_view("planner")).pack(padx=12, pady=(2, 8), anchor="w")
        try:
            self.scroll._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _refresh_after_action(self, reply):
        """Push agent-made changes into the open views."""
        touched = {(tr.tool) for tr in reply.tool_results if getattr(tr, "ok", False)}
        if not touched:
            return
        if any(t in ("create_task", "update_task", "complete_task", "reopen_task",
                     "delete_task", "add_subtask", "assign_subject") for t in touched):
            if "today" in self.app.views:
                self.app.views["today"].render()
            self.app.refresh_xp()
        if any(t in ("add_class", "get_routine") for t in touched):
            if "routine" in self.app.views:
                self.app.views["routine"].render()
        if any(t in ("create_goal", "update_goal", "add_milestone", "complete_milestone")
               for t in touched) and "goals" in self.app.views:
            self.app.views["goals"].render()

    # ---------------- legacy image import (routine scan) ----------------

    def upload_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")])
        if file_path:
            self.add_message("user", f"Uploaded image: {os.path.basename(file_path)}")

            from ai_parser import parse_file_with_ai

            thinking_lbl = self.add_message("assistant", "Analyzing image… 🖼️", is_temporary=True)
            self.update()

            result = parse_file_with_ai(file_path)
            thinking_lbl.destroy()

            if result:
                msg = result.get("message", "I've analyzed the image.")
                if result.get("intent") == "schedule_file":
                    msg = f"✅ I found {len(result.get('classes', []))} classes in that image! Review them in the Routine tab."
                    self.app.views["routine"].render()

                self.add_message("assistant", msg)
            else:
                self.add_message("assistant", "I couldn't read information from that image. Make sure it's clear!")


# ==================== PLANNER VIEW ====================
