"""views_misc - split from ui.py (Focus Agent V2, Phase 6)."""

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
from .theme import COLORS, FONTS


class HabitView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=COLORS["bg"])
        self.app = app
        self.habit_widgets = {} # habit_id -> (streak_lbl, button)
        self.render()

    def render(self):
        for w in self.winfo_children(): w.destroy()
        self.habit_widgets = {}

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(10, 10))
        ctk.CTkLabel(header, text="Daily Habits", font=FONTS["title"]).pack(side="left")
        ctk.CTkButton(header, text="+ New Habit", width=120, height=32, 
                      fg_color=COLORS["accent"], command=self.prompt_new_habit).pack(side="right")

        # Scrollable list
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10)

        habits = self.app.data.get("habits", [])
        if not habits:
            ctk.CTkLabel(scroll, text="No habits yet. Start small! 🌱", 
                         text_color=COLORS["text_dim"]).pack(pady=40)
            return

        for habit in habits:
            self._draw_habit_card(scroll, habit)

    def _draw_habit_card(self, parent, habit):
        card = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=10)
        card.pack(fill="x", padx=10, pady=5)
        
        # Determine status
        done_today = today() in habit.get("history", [])
        streak = get_habit_streak(habit)
        
        # Left: Title + Streak
        left = ctk.CTkFrame(card, fg_color="transparent")
        left.pack(side="left", padx=15, pady=10)
        
        ctk.CTkLabel(left, text=habit["title"], font=FONTS["header"]).pack(anchor="w")
        streak_lbl = ctk.CTkLabel(left, text=f"🔥 {streak} day streak", 
                                  text_color=COLORS["warning"] if streak > 0 else COLORS["text_dim"],
                                  font=FONTS["small"])
        streak_lbl.pack(anchor="w")
        
        # Right: Check Button + Delete
        
        # Check Button
        btn_text = "Done! ✅" if done_today else "Mark Done"
        btn_col = COLORS["success"] if done_today else COLORS["bg_secondary"]
        fg_col = "white" if done_today else COLORS["text_dim"]
        
        check_btn = ctk.CTkButton(card, text=btn_text, width=100,
                                  fg_color=btn_col, text_color=fg_col,
                                  command=lambda h=habit: self.toggle_habit(h["id"]))
        check_btn.pack(side="right", padx=15)
        
        # Delete
        ctk.CTkButton(card, text="✕", width=30, fg_color="transparent", text_color=COLORS["error"],
                      command=lambda h=habit: self.delete_habit_silent(h["id"], card)).pack(side="right", padx=5)
        
        self.habit_widgets[habit["id"]] = (streak_lbl, check_btn)

    def prompt_new_habit(self):
        name = tk.simpledialog.askstring("New Habit", "Habit name (e.g. Drink Water):")
        if name:
            add_habit(self.app.data, name)
            self.render()

    def toggle_habit(self, habit_id):
        toggle_habit_today(self.app.data, habit_id)
        self._update_habit_streak(habit_id)
        
    def _update_habit_streak(self, habit_id):
        if habit_id not in self.habit_widgets: return
        
        habit = next((h for h in self.app.data["habits"] if h["id"] == habit_id), None)
        if not habit: return
        
        streak_lbl, check_btn = self.habit_widgets[habit_id]
        
        # Update logic
        done_today = today() in habit.get("history", [])
        streak = get_habit_streak(habit)
        
        # Streak
        streak_lbl.configure(text=f"🔥 {streak} day streak", 
                             text_color=COLORS["warning"] if streak > 0 else COLORS["text_dim"])
        
        # Button
        if done_today:
            check_btn.configure(text="Done! ✅", fg_color=COLORS["success"], text_color="white")
            self.app.refresh_xp() # Habit gives XP!
        else:
            check_btn.configure(text="Mark Done", fg_color=COLORS["bg_secondary"], text_color=COLORS["text_dim"])

    def delete_habit_silent(self, habit_id, card):
        if messagebox.askyesno("Delete", "Stop tracking this habit?"):
            delete_habit(self.app.data, habit_id)
            card.destroy()
            del self.habit_widgets[habit_id]

class VaultView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=COLORS["bg"])
        self.app = app
        self.subject_frames = {}  # name -> frame
        self.render()

    def render(self):
        for w in self.winfo_children(): w.destroy()
        self.subject_frames = {}
        
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(10, 10))
        ctk.CTkLabel(header, text="Subject Vault", font=FONTS["title"]).pack(side="left")
        
        ctk.CTkButton(header, text="+ New Subject", width=120, height=32, 
                      fg_color=COLORS["accent"], command=self.prompt_new_subject).pack(side="right", padx=10)
        
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=10)
        
        # Get data-driven subjects
        subjects_data = self.app.data.get("subjects", {})
        
        # Also include subjects from tasks if not explicitly created
        for task in self.app.data.get("tasks", []):
            subj = task.get("subject")
            if subj and subj not in subjects_data:
                subjects_data[subj] = {"notes": "", "documents": []}
        
        if not subjects_data:
            ctk.CTkLabel(self.scroll, text="No subjects yet. Create one to start organizing!", 
                         text_color=COLORS["text_dim"]).pack(pady=40)
            return

        for subj, info in subjects_data.items():
            self.draw_subject_section(self.scroll, subj, info)

    def draw_subject_section(self, parent, name, info):
        frame = ctk.CTkFrame(parent, fg_color=COLORS["sidebar"], corner_radius=15)
        frame.pack(fill="x", pady=10, padx=5)
        self.subject_frames[name] = frame
        
        # Use direct packing on frame
        title_bar = ctk.CTkFrame(frame, fg_color="transparent")
        title_bar.pack(fill="x", padx=15, pady=(10, 0))
        
        ctk.CTkLabel(title_bar, text=f"📚 {name}", font=FONTS["header"], text_color=COLORS["accent"]).pack(side="left")
        
        # Actions on the right
        ctk.CTkButton(title_bar, text="✕", width=24, height=24, font=FONTS["small"],
                      text_color=COLORS["error"], fg_color="transparent", hover_color=COLORS["border"],
                      command=lambda n=name: self.confirm_delete_subject(n)).pack(side="right", padx=2)

        ctk.CTkButton(title_bar, text="✎", width=24, height=24, font=FONTS["small"],
                      fg_color="transparent", hover_color=COLORS["border"],
                      command=lambda n=name: self.prompt_rename_subject(n)).pack(side="right", padx=2)

        ctk.CTkButton(title_bar, text="+ Add File", width=80, height=24, font=FONTS["small"],
                      fg_color=COLORS["card"], command=lambda n=name: self.upload_to_vault(n)).pack(side="right", padx=10)
        
        # Files Container
        files_container = ctk.CTkFrame(frame, fg_color="transparent")
        files_container.pack(fill="x", padx=0, pady=5)
        frame._files_container = files_container

        # Files List
        files = info.get("documents", [])
        # Merge task documents too
        for task in self.app.data.get("tasks", []):
            if task.get("subject") == name and task.get("documents"):
                for d in task["documents"]:
                    if d not in files: files.append(d)

        if not files:
            label = ctk.CTkLabel(files_container, text="No documents yet.", font=FONTS["small"], text_color=COLORS["text_dim"])
            label.pack(padx=30, pady=5, anchor="w")
            frame._empty_label = label
        else:
            for f_path in files:
                self._draw_file_row(files_container, name, f_path)

    def _draw_file_row(self, parent, subject, f_path):
        f_item = ctk.CTkFrame(parent, fg_color="transparent")
        f_item.pack(fill="x", padx=30, pady=2)
        
        fname = os.path.basename(f_path)
        ctk.CTkLabel(f_item, text=f"📄 {fname}", font=FONTS["body"]).pack(side="left")
        
        ctk.CTkButton(f_item, text="Rem", width=60, height=20, font=FONTS["small"],
                      text_color=COLORS["error"], fg_color="transparent", 
                      command=lambda n=subject, p=f_path, w=f_item: self.remove_file_silent(n, p, w)).pack(side="right", padx=5)

        ctk.CTkButton(f_item, text="Open", width=60, height=20, font=FONTS["small"],
                      fg_color=COLORS["success_dark"], command=lambda p=f_path: self.open_file(p)).pack(side="right")
        
        ctk.CTkButton(f_item, text="Summ", width=60, height=20, font=FONTS["small"],
                      fg_color=COLORS["accent_dark"], command=lambda p=f_path: self.show_summary(p)).pack(side="right", padx=5)

    def prompt_new_subject(self):
        name = tk.simpledialog.askstring("New Subject", "Enter subject name:")
        if name:
            if add_subject(self.app.data, name):
                # Silent Add
                self.draw_subject_section(self.scroll, name, self.app.data["subjects"][name])
            else:
                messagebox.showerror("Error", "Subject already exists!")

    def prompt_rename_subject(self, old_name):
        new_name = tk.simpledialog.askstring("Rename", f"New name for {old_name}:")
        if new_name:
            rename_subject(self.app.data, old_name, new_name)
            self.render() # Struct change (keys) - render is safest

    def confirm_delete_subject(self, name):
        if messagebox.askyesno("Delete", f"Are you sure you want to delete '{name}' and all its metadata?"):
            delete_subject(self.app.data, name)
            if name in self.subject_frames:
                self.subject_frames[name].destroy()
                del self.subject_frames[name]

    def upload_to_vault(self, subject):
        path = filedialog.askopenfilename()
        if path:
            add_vault_file(self.app.data, subject, path)
            # Silent Add File
            if subject in self.subject_frames:
                frame = self.subject_frames[subject]
                if hasattr(frame, "_empty_label"):
                    frame._empty_label.destroy()
                    del frame._empty_label
                if hasattr(frame, "_files_container"):
                    self._draw_file_row(frame._files_container, subject, path)

    def remove_file_silent(self, subject, path, widget):
        if messagebox.askyesno("Remove", "Remove this file from vault?"):
            delete_vault_file(self.app.data, subject, path)
            widget.destroy()

    def remove_file(self, subject, path):
        # Deprecated
        pass

    def open_file(self, path):
        try:
            if os.name == 'nt': 
                os.startfile(path) # pylint: disable=no-member
            else:
                subprocess.run(['xdg-open', path], check=False)

        except Exception as e:
            messagebox.showerror("Error", f"Could not open file: {e}")

    def show_summary(self, path):
        """Show AI-generated summary in a popup."""
        top = ctk.CTkToplevel(self)
        top.title(f"Summary: {os.path.basename(path)}")
        top.geometry("600x500")
        top.attributes("-topmost", True)
        
        lbl = ctk.CTkLabel(top, text="🔄 Generating summary with Gemini...", font=FONTS["body"])
        lbl.pack(pady=20)
        
        txt = ctk.CTkTextbox(top, font=FONTS["body"], wrap="word")
        txt.pack(fill="both", expand=True, padx=20, pady=10)
        txt.insert("1.0", "Please wait while I read the document...")
        txt.configure(state="disabled")
        
        def run_summ():
            from focus_agent.media_import import summarize_with_ai
            summary = summarize_with_ai(path)
            txt.configure(state="normal")
            txt.delete("1.0", "end")
            txt.insert("1.0", summary)
            txt.configure(state="disabled")
            lbl.configure(text="✨ Summary Generated")

        # Run in a separate thread to avoid freezing UI
        import threading
        threading.Thread(target=run_summ, daemon=True).start()


# ==================== MAIN APP ====================
