"""views_settings - split from ui.py (Focus Agent V2, Phase 6)."""

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


class SettingsView(ctk.CTkScrollableFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=COLORS["bg"], scrollbar_button_color=COLORS["card"])
        self.app = app
        self.sliders = {} # Store slider references for save_settings
        self.render()

    def _draw_section(self, title, widgets):
        # Helper (same as before)
        frame = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=10)
        frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(frame, text=title, font=FONTS["header"]).pack(anchor="w", padx=15, pady=10)
        for w in widgets:
            w.pack(anchor="w", padx=15, pady=5)
            
    def render(self):
        for w in self.winfo_children(): w.destroy()
        self.sliders = {} # Clear on re-render

        ctk.CTkLabel(self, text="Settings", font=FONTS["title"],
                     text_color=COLORS["text"]).pack(anchor="w", pady=(10, 20), padx=20)

        # Appearance
        app_frame = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=10)
        app_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(app_frame, text="Appearance", font=FONTS["header"]).pack(anchor="w", padx=15, pady=(10, 5))
        ctk.CTkOptionMenu(app_frame, values=["System", "Dark", "Light"],
                          command=self._change_theme).pack(anchor="w", padx=15, pady=(0, 12))

        # Pomodoro Settings
        pom = get_pomodoro_settings(self.app.data)

        def update_pom(k, v):
            # Update the internal pom dict, but don't save immediately
            # Save will be triggered by the dedicated save button or segmented button
            pom[k] = int(v)

        pom_frame = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=10)
        pom_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(pom_frame, text="Timer Settings (Minutes)", font=FONTS["header"]).pack(anchor="w", padx=15, pady=10)

        def add_slider(label, key, from_, to_):
            sub = ctk.CTkFrame(pom_frame, fg_color="transparent")
            sub.pack(fill="x", padx=15, pady=5)
            ctk.CTkLabel(sub, text=label, width=100, anchor="w").pack(side="left")
            slider = ctk.CTkSlider(sub, from_=from_, to=to_, number_of_steps=(to_-from_),
                                   command=lambda v: update_pom(key, v))
            slider.set(pom[key])
            slider.pack(side="left", fill="x", expand=True, padx=10)
            self.sliders[key] = slider # Store slider reference

        add_slider("Focus Work", "work", 15, 60)
        add_slider("Short Break", "short_break", 1, 15)
        add_slider("Long Break", "long_break", 10, 45)

        # Timer Style
        ctk.CTkLabel(self, text="Timer Style", font=FONTS["header"], text_color=COLORS["text"]).pack(anchor="w", pady=(10, 5))

        self.style_var = ctk.StringVar(value=self.app.data.get("settings", {}).get("timer_style", "stopwatch"))
        style_seg = ctk.CTkSegmentedButton(self, values=["Stopwatch", "Countdown"],
                                           variable=self.style_var, command=self.save_settings)
        style_seg.pack(fill="x", pady=(0, 15))

        # ---- AI AGENT (V2) ----
        if AGENT_AVAILABLE:
            self._draw_agent_section()

        # Data safety
        data_frame = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=10)
        data_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(data_frame, text="Data & Backups", font=FONTS["header"]).pack(anchor="w", padx=15, pady=(10, 4))
        ctk.CTkLabel(data_frame, text="A timestamped backup is created automatically before schema migrations.",
                     font=FONTS["small"], text_color=COLORS["text_dim"]).pack(anchor="w", padx=15)
        btns = ctk.CTkFrame(data_frame, fg_color="transparent")
        btns.pack(fill="x", padx=15, pady=8)
        ctk.CTkButton(btns, text="💾 Backup Now", width=130, command=self._backup_now).pack(side="left", padx=3)
        ctk.CTkButton(btns, text="↩ Restore Backup…", width=150, command=self._restore_backup).pack(side="left", padx=3)
        ctk.CTkButton(btns, text="📤 Export JSON", width=130, command=self._export_data).pack(side="left", padx=3)

        # Save Button
        ctk.CTkButton(self, text="Save Settings", font=FONTS["body"],
                      fg_color=COLORS["success"], hover_color=COLORS["success_dark"],
                      command=self.save_settings).pack(pady=20)

    def _draw_agent_section(self):
        """Provider/endpoint/model config + connection test + study window."""
        cfg = (self.app.data.get("settings", {}).get("agent")
               or storage.DEFAULT_AGENT_SETTINGS)

        frame = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=10)
        frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(frame, text="🤖 AI Agent (local-first)", font=FONTS["header"]).pack(anchor="w", padx=15, pady=(10, 2))
        ctk.CTkLabel(frame, text=("The agent runs on your machine via Ollama. Nothing is sent online unless you "
                                  "explicitly configure an online provider; research answers are always disclosed."),
                     font=FONTS["small"], text_color=COLORS["text_dim"], wraplength=560,
                     justify="left").pack(anchor="w", padx=15, pady=(0, 8))

        # Provider row
        row1 = ctk.CTkFrame(frame, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=4)
        ctk.CTkLabel(row1, text="Provider:", width=90, anchor="w").pack(side="left")
        self.provider_var = ctk.StringVar(value=cfg.get("provider", "ollama"))
        ctk.CTkSegmentedButton(row1, values=["ollama", "online", "none"],
                               variable=self.provider_var).pack(side="left")

        row2 = ctk.CTkFrame(frame, fg_color="transparent")
        row2.pack(fill="x", padx=15, pady=4)
        ctk.CTkLabel(row2, text="Endpoint:", width=90, anchor="w").pack(side="left")
        self.endpoint_entry = ctk.CTkEntry(row2, placeholder_text="http://localhost:11434")
        self.endpoint_entry.insert(0, cfg.get("endpoint", "http://localhost:11434"))
        self.endpoint_entry.pack(side="left", fill="x", expand=True, padx=4)

        row3 = ctk.CTkFrame(frame, fg_color="transparent")
        row3.pack(fill="x", padx=15, pady=4)
        ctk.CTkLabel(row3, text="Model:", width=90, anchor="w").pack(side="left")
        self.model_entry = ctk.CTkEntry(row3, width=180, placeholder_text="e.g. qwen3:4b")
        self.model_entry.insert(0, cfg.get("model", "qwen3:4b"))
        self.model_entry.pack(side="left", padx=4)
        ctk.CTkLabel(row3, text="(any model you pulled in Ollama)", font=FONTS["tiny"],
                     text_color=COLORS["text_dim"]).pack(side="left", padx=6)

        # status + test
        row4 = ctk.CTkFrame(frame, fg_color="transparent")
        row4.pack(fill="x", padx=15, pady=4)
        self.test_btn = ctk.CTkButton(row4, text="Test Connection", width=130,
                                      command=self._test_connection)
        self.test_btn.pack(side="left")
        self.conn_lbl = ctk.CTkLabel(row4, text="", font=FONTS["small"],
                                     text_color=COLORS["text_dim"], wraplength=420, justify="left")
        self.conn_lbl.pack(side="left", padx=10)

        help_text = ("Setup: 1) Install Ollama (ollama.com)  2) pull a model, e.g. `ollama pull qwen3:4b`  "
                     "3) keep it running (`ollama serve`). Optional online research: set env vars "
                     "ONLINE_LLM_API_KEY / ONLINE_LLM_MODEL / ONLINE_LLM_BASE_URL - keys are read from the "
                     "environment only and never stored in data files.")
        self._help_lbl = ctk.CTkLabel(frame, text=help_text, font=FONTS["tiny"], text_color=COLORS["text_muted"],
                                      wraplength=560, justify="left")
        self._help_lbl.pack(anchor="w", padx=15, pady=(4, 10))

        # ---- study window (planner inputs) ----
        settings = self.app.data.get("settings", {})
        study = settings.get("study_hours") or {"start": "09:00", "end": "22:00"}
        srow = ctk.CTkFrame(frame, fg_color="transparent")
        srow.pack(fill="x", padx=15, pady=4)
        ctk.CTkLabel(srow, text="Study window:", width=90, anchor="w").pack(side="left")
        self.study_start_e = ctk.CTkEntry(srow, width=75, placeholder_text="09:00")
        self.study_start_e.insert(0, study.get("start", "09:00"))
        self.study_start_e.pack(side="left", padx=4)
        ctk.CTkLabel(srow, text="to").pack(side="left", padx=4)
        self.study_end_e = ctk.CTkEntry(srow, width=75, placeholder_text="22:00")
        self.study_end_e.insert(0, study.get("end", "22:00"))
        self.study_end_e.pack(side="left", padx=4)
        ctk.CTkLabel(srow, text="Break (min):").pack(side="left", padx=(14, 4))
        self.break_e = ctk.CTkEntry(srow, width=55)
        self.break_e.insert(0, str(settings.get("break_minutes", 10)))
        self.break_e.pack(side="left")

        trow = ctk.CTkFrame(frame, fg_color="transparent")
        trow.pack(fill="x", padx=15, pady=(4, 10))
        ctk.CTkLabel(trow, text="Timezone:", width=90, anchor="w").pack(side="left")
        self.tz_entry = ctk.CTkEntry(trow, width=180, placeholder_text="local / Asia/Dhaka")
        self.tz_entry.insert(0, settings.get("timezone", "local"))
        self.tz_entry.pack(side="left", padx=4)
        ctk.CTkLabel(trow, text="used for 'tomorrow', 'next monday'…", font=FONTS["tiny"],
                     text_color=COLORS["text_dim"]).pack(side="left", padx=6)

    def _test_connection(self):
        self.test_btn.configure(state="disabled", text="Testing…")
        self.conn_lbl.configure(text="connecting…", text_color=COLORS["text_dim"])

        def run():
            provider = fllm.OllamaProvider(endpoint=self.endpoint_entry.get().strip() or None,
                                           model=self.model_entry.get().strip() or None)
            ok, detail = provider.status()
            def apply():
                try:
                    self.conn_lbl.configure(text=("✅ " if ok else "⚠ ") + detail,
                                            text_color=COLORS["success"] if ok else COLORS["warning"])
                    self.test_btn.configure(state="normal", text="Test Connection")
                except Exception:
                    pass
            self.after(0, apply)
        threading.Thread(target=run, daemon=True).start()

    def _apply_agent_settings(self):
        """Persist agent + planner settings from the form. Returns error or None."""
        from focus_agent.schemas import valid_hhmm
        settings = self.app.data.setdefault("settings", {})
        agent = settings.setdefault("agent", {})
        agent["provider"] = self.provider_var.get()
        agent["endpoint"] = (self.endpoint_entry.get().strip()
                             or storage.DEFAULT_AGENT_SETTINGS["endpoint"])
        agent["model"] = self.model_entry.get().strip() or storage.DEFAULT_AGENT_SETTINGS["model"]
        start = valid_hhmm(self.study_start_e.get().strip())
        end = valid_hhmm(self.study_end_e.get().strip())
        if not start or not end or start >= end:
            return "Study window must be valid HH:MM times with start < end"
        settings["study_hours"] = {"start": start, "end": end}
        try:
            settings["break_minutes"] = max(0, min(60, int(self.break_e.get())))
        except ValueError:
            return "Break minutes must be a number"
        settings["timezone"] = self.tz_entry.get().strip() or "local"
        return None

    def _backup_now(self):
        path = storage.make_backup()
        if path:
            messagebox.showinfo("Backup", f"Backup created:\n{os.path.basename(path)}")
        else:
            messagebox.showerror("Backup", "Backup failed (is there a data file yet?)")

    def _restore_backup(self):
        path = filedialog.askopenfilename(initialdir=storage.BACKUP_DIR if os.path.isdir(storage.BACKUP_DIR) else ".",
                                          filetypes=[("JSON", "*.json")])
        if not path:
            return
        if not messagebox.askyesno("Restore",
                                   "Restore this backup? Your CURRENT data will be replaced "
                                   "(a safety backup of it is made first)."):
            return
        safety = storage.make_backup()
        if storage.restore_backup(path):
            messagebox.showinfo("Restore", f"Restored. Current state was backed up to {os.path.basename(safety or '')}.\nRestart the app to reload.")
        else:
            messagebox.showerror("Restore", "Restore failed - file invalid or unreadable.")

    def save_settings(self, *args):
        # Update logic
        style = self.style_var.get().lower()

        # Save sliders + Style
        try:
             agent_err = self._apply_agent_settings() if AGENT_AVAILABLE else None
             if agent_err:
                 messagebox.showerror("Settings", agent_err)
                 return
             # Logic function now accepts style
             update_pomodoro_settings(self.app.data,
                                      self.sliders["work"].get(),
                                      self.sliders["short_break"].get(),
                                      self.sliders["long_break"].get(),
                                      style)

             # Refresh App Timer Label?
             if not self.app.timer_running:
                 # If timer is not running, update its display based on new style
                 if style == "stopwatch":
                     self.app.timer_lbl.configure(text="00:00:00")
                 else: # Countdown
                     pom = get_pomodoro_settings(self.app.data)
                     self.app.timer_lbl.configure(text=format_seconds_to_hms(pom.get("work", 25) * 60))

             messagebox.showinfo("Settings", "Settings saved successfully!")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")
            print(f"Save error: {e}")

    def _draw_goal_section(self):
        frame = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=15)
        frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(frame, text="Focus Goals", font=FONTS["header"], text_color=COLORS["accent"]).pack(anchor="w", padx=20, pady=(15, 10))
        
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=5)
        
        current_goal = self.app.data.get("settings", {}).get("daily_goal_hours", 4)
        
        ctk.CTkLabel(row, text="Daily Focus Target (Hours)", font=FONTS["body"]).pack(side="left")
        lbl = ctk.CTkLabel(row, text=f"{current_goal}h", font=("Inter", 14, "bold"), text_color=COLORS["success"])
        lbl.pack(side="right", padx=10)
        
        def update_lbl(val):
            lbl.configure(text=f"{int(val)}h")
            
        def save_goal(val):
            self.app.data.setdefault("settings", {})["daily_goal_hours"] = int(val)
            save_data(self.app.data)

        slider = ctk.CTkSlider(frame, from_=1, to=12, number_of_steps=11, command=update_lbl)
        slider.set(current_goal)
        slider.bind("<ButtonRelease-1>", lambda event: save_goal(slider.get()))
        
        slider.pack(fill="x", padx=20, pady=(0, 20))

    def _change_theme(self, mode):
        ctk.set_appearance_mode(mode)
        
    def _export_data(self):
        f = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if f:
            import shutil
            try:
                # We save current state first
                save_data(self.app.data)
                # Just copy the data file
                from logic import DATA_FILE
                shutil.copy2(DATA_FILE, f)
                messagebox.showinfo("Success", "Data exported successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {e}")
