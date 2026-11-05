"""views_today - split from ui.py (Focus Agent V2, Phase 6)."""

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
from .theme import COLORS, FONTS, get_color_str
from .widgets import TimePicker, DaySelector, Tooltip


class TodayView(ctk.CTkScrollableFrame):
    """Enhanced Today view with beautiful task cards."""
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=COLORS["bg"], scrollbar_button_color=COLORS["card"])
        self.app = app
        self.task_cards = {}  # task_id -> card widget for silent updates
        self._init_static_ui()
        # Don't render here - switch_view will call render() when view is shown

    def _init_static_ui(self):
        """Create header and input frame once."""
        # Header with gradient accent
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", pady=(10, 20), padx=10)
        
        ctk.CTkLabel(header_frame, text="✨ Today's Flow", font=FONTS["title"],
                     text_color=COLORS["text"]).pack(side="left")
        
        # Current date badge
        from datetime import datetime
        today_str = datetime.now().strftime("%A, %B %d")
        date_badge = ctk.CTkFrame(header_frame, fg_color=COLORS["card"], corner_radius=8)
        date_badge.pack(side="right")
        ctk.CTkLabel(date_badge, text=today_str, font=FONTS["small"],
                     text_color=COLORS["text_dim"]).pack(padx=12, pady=6)

        # Action buttons
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.pack(fill="x", pady=(0, 20), padx=10)

        ctk.CTkButton(input_frame, text="+ Add Task", command=self.prompt_add_task,
                      fg_color=COLORS["card"], hover_color=COLORS["card_hover"], 
                      width=130, height=42, corner_radius=10, text_color=COLORS["text"],
                      font=FONTS["body"]).pack(side="right", padx=8)

        ctk.CTkButton(input_frame, text="+ Add Class", command=self.prompt_add_class,
                      fg_color=COLORS["accent"], hover_color=COLORS["accent_dark"], 
                      width=130, height=42, corner_radius=10, text_color="white",
                      font=FONTS["body"]).pack(side="right")
        
        # Container for dynamic list
        self.list_container = ctk.CTkFrame(self, fg_color="transparent")
        self.list_container.pack(fill="both", expand=True)

    def render(self):
        """Only refresh the dynamic task list."""
        for w in self.list_container.winfo_children(): w.destroy()
        self.task_cards = {}  # Clear card references on full refresh

        today_tasks = get_today_tasks(self.app.data)
        if not today_tasks:
            # Beautiful empty state
            empty_frame = ctk.CTkFrame(self.list_container, fg_color=COLORS["card"], corner_radius=15)
            empty_frame.pack(fill="x", padx=20, pady=40)
            ctk.CTkLabel(empty_frame, text="☕ Relax! No tasks for today.", 
                         text_color=COLORS["text_dim"], font=FONTS["header"]).pack(pady=30)
            return

        for task in today_tasks:
            if task.get("status") == "done": continue
            self.draw_task_card(task)

    def draw_task_card(self, task):
        """Draw a task card with essential actions."""
        # Card container
        card = ctk.CTkFrame(self.list_container, fg_color=COLORS["card"], corner_radius=10)
        card.pack(fill="x", pady=4, padx=10)
        card._task_id = task["id"]  # Store reference for silent updates
        card._detail_section = None  # Will be set if details exist
        self.task_cards[task["id"]] = card  # Register for silent updates
        
        # Top row - main task info
        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=10, pady=(8, 4))
        
        # Determine task type styling
        is_class = task.get("type") == "class"
        icon = "📘" if is_class else "📝"
        title_color = COLORS["accent_light"] if is_class else "white"
        
        # Checkbox - complete task silently
        chk = ctk.CTkCheckBox(top_row, text="", 
                              command=lambda c=card: self.complete_task_silent(task["id"], c),
                              width=20, height=20, fg_color=COLORS["success"],
                              border_color=COLORS["border"])
        chk.pack(side="left", padx=(0, 8))

        # Title
        title_lbl = ctk.CTkLabel(top_row, text=f"{icon} {task['title']}", font=FONTS["header"],
                     text_color=title_color)
        title_lbl.pack(side="left", padx=5)
        card._title_lbl = title_lbl  # Store ref

        # Delete button - delete silently
        ctk.CTkButton(top_row, text="✕", width=26, height=26, font=FONTS["small"],
                      text_color=COLORS["text_dim"], fg_color="transparent", 
                      hover_color=COLORS["error"], corner_radius=5,
                      command=lambda c=card: self.confirm_delete_silent(task["id"], c)).pack(side="right", padx=2)

        # Edit button
        ctk.CTkButton(top_row, text="✎", width=26, height=26, font=FONTS["small"],
                      text_color=COLORS["text_dim"], fg_color="transparent",
                      hover_color=COLORS["accent"], corner_radius=5,
                      command=lambda t=task: self.edit_task(t)).pack(side="right", padx=2)
        
        # Magic Subtask button (Only for non-classes)
        if not is_class:
            magic_btn = ctk.CTkButton(top_row, text="✨", width=26, height=26, font=FONTS["small"],
                          text_color=COLORS["warning"], fg_color="transparent",
                          hover_color=COLORS["card_hover"], corner_radius=5,
                          command=lambda t=task, b=card: self.generate_ai_subtasks(t, b))
            magic_btn.pack(side="right", padx=2)
            Tooltip(magic_btn, "Auto-generate subtasks with AI")

        # Time badge for classes
        if is_class:
            sch = task.get("schedule", {})
            ctk.CTkLabel(top_row, text=f"🕐 {sch.get('start','')} - {sch.get('end','')}",
                        text_color=COLORS["warning"], font=FONTS["small"]).pack(side="right", padx=8)

        # Duration
        if task.get("duration"):
            ctk.CTkLabel(top_row, text=f"⏱️ {task['duration']}m",
                        text_color=COLORS["text_dim"], font=FONTS["small"]).pack(side="right", padx=8)

        # Bottom row - action buttons
        bottom_row = ctk.CTkFrame(card, fg_color="transparent")
        bottom_row.pack(fill="x", padx=12, pady=(0, 4))
        
        btn_style = {"width": 75, "height": 24, "font": FONTS["small"],
                     "fg_color": COLORS["bg_secondary"], "hover_color": COLORS["card_hover"],
                     "corner_radius": 5, "text_color": COLORS["text_dim"]}
        
        ctk.CTkButton(bottom_row, text="+ Sub", command=lambda: self.prompt_subtask(task["id"]),
                      **btn_style).pack(side="left", padx=2)
        ctk.CTkButton(bottom_row, text="📎 File", command=lambda: self.add_attachment(task["id"]),
                      **btn_style).pack(side="left", padx=2)
        ctk.CTkButton(bottom_row, text="📝 Note", command=lambda: self.edit_note(task["id"]),
                      **btn_style).pack(side="left", padx=2)
        
        # Details section - subtasks, notes, attachments
        subtasks = task.get("subtasks", [])
        notes = task.get("notes", "")
        docs = task.get("documents", [])
        
        if subtasks or notes or docs:
            detail_section = ctk.CTkFrame(card, fg_color=COLORS["bg_secondary"], corner_radius=8)
            detail_section.pack(fill="x", padx=12, pady=(4, 10))
            card._detail_section = detail_section  # Store reference for silent updates
            
            # Notes display
            if notes:
                note_lbl = ctk.CTkLabel(detail_section, text=f"📝 {notes[:100]}{'...' if len(notes) > 100 else ''}", 
                            font=FONTS["small"], text_color=COLORS["text_dim"],
                            wraplength=500, justify="left")
                note_lbl.pack(anchor="w", padx=10, pady=(8, 4))
                card._note_lbl = note_lbl  # Store ref
            
            # Attachments
            if docs:
                for doc in docs[:3]:  # Show max 3
                    fname = doc.split('/')[-1] if '://' not in doc else doc[:30] + '...'
                    ctk.CTkLabel(detail_section, text=f"📄 {fname}",
                                font=FONTS["small"], text_color=COLORS["accent"]).pack(anchor="w", padx=10, pady=1)
            
            # Subtasks list with checkboxes
            if subtasks:
                for si, sub in enumerate(subtasks):
                    sub_frame = ctk.CTkFrame(detail_section, fg_color="transparent")
                    sub_frame.pack(fill="x", padx=10, pady=2)
                    
                    s_chk = ctk.CTkCheckBox(sub_frame, text=sub["title"], font=FONTS["body"],
                                            fg_color=COLORS["success"], 
                                            hover_color=COLORS["success_dark"],
                                            width=18, height=18,
                                            command=lambda t=task["id"], s=si: self.toggle_sub(t, s))
                    if sub.get("done"): s_chk.select()
                    s_chk.pack(side="left")

    def prompt_subtask(self, task_id):
        """Add subtask silently - append widget without full refresh."""
        dialog = ctk.CTkInputDialog(text="Enter subtask title:", title="Add Subtask")
        title = dialog.get_input()
        if title:
            add_subtask(self.app.data, task_id, title)
            # Silently add the subtask widget
            self._add_subtask_widget_silent(task_id, title)

    def add_attachment(self, task_id):
        confirm = messagebox.askyesno("Attachment Type", "Is this a file? (Yes for file, No for URL)")
        if confirm:
            path = filedialog.askopenfilename()
            if path:
                self._save_attachment(task_id, path)
        else:
            dialog = ctk.CTkInputDialog(text="Enter URL:", title="Add Link")
            url = dialog.get_input()
            if url:
                self._save_attachment(task_id, url)

    def _save_attachment(self, task_id, value):
        """Save attachment silently - append widget without full refresh."""
        task = next((t for t in self.app.data["tasks"] if t["id"] == task_id), None)
        if task:
            task.setdefault("documents", []).append(value)
            save_data(self.app.data)
            # Silently add the attachment widget
            self._add_attachment_widget_silent(task_id, value)

    def edit_note(self, task_id):
        task = next((t for t in self.app.data["tasks"] if t["id"] == task_id), None)
        if not task: return

        top = ctk.CTkToplevel(self)
        top.title(f"Notes: {task['title']}")
        top.geometry("400x300")
        top.after(100, lambda: top.focus())

        txt = ctk.CTkTextbox(top, font=FONTS["body"])
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        txt.insert("1.0", task.get("notes", ""))

        def save():
            new_note = txt.get("1.0", "end-1c")
            task["notes"] = new_note
            save_data(self.app.data)
            # Silent UI update
            self._update_note_label_silent(task["id"], new_note)
            top.destroy()

        ctk.CTkButton(top, text="Save Note", command=save, fg_color=COLORS["success"]).pack(pady=(0, 10))

    def prompt_add_task(self):
        top = ctk.CTkToplevel(self)
        top.title("New Task")
        top.geometry("450x650")
        top.after(100, lambda: top.focus())

        ctk.CTkLabel(top, text="Task Title:", font=FONTS["body"]).pack(pady=(10, 0))
        title_e = ctk.CTkEntry(top, width=350)
        title_e.pack(pady=5)

        # Date Schedule Option
        date_var = ctk.BooleanVar(value=True)
        
        # Frame for Calendar so we can show/hide it cleanly
        cal_container = ctk.CTkFrame(top, fg_color="transparent")
        
        def toggle_date():
            if date_var.get():
                cal_container.pack(pady=10, after=switch_frame)
            else:
                cal_container.pack_forget()

        switch_frame = ctk.CTkFrame(top, fg_color="transparent")
        switch_frame.pack(pady=5)
        
        switch = ctk.CTkSwitch(switch_frame, text="Schedule for Date", variable=date_var, command=toggle_date, font=FONTS["body"])
        switch.pack()

        # Pack the container initially
        cal_container.pack(pady=10)

        cal = Calendar(cal_container, selectmode='day', date_pattern='yyyy-mm-dd',
                       background=get_color_str("card"), foreground="white",
                       headersbackground=get_color_str("sidebar"), normalbackground=get_color_str("card"),
                       selectbackground=get_color_str("accent"))
        cal.pack()

        ctk.CTkLabel(top, text="Time Limit (minutes, optional):", font=FONTS["body"]).pack(pady=(5, 0))
        dur_e = ctk.CTkEntry(top, width=350, placeholder_text="e.g. 30")
        dur_e.pack(pady=5)

        def save():
            title = title_e.get().strip()
            if title:
                dur = None
                if dur_e.get().isdigit(): dur = int(dur_e.get())
                
                date = None
                if date_var.get():
                    date = cal.get_date()
                
                new_task = add_task_logic(self.app.data, title, duration=dur, deadline=date)
                
                from utils import today
                today_str = today()
                
                should_show = False
                if not date: should_show = True
                elif date <= today_str: should_show = True
                
                if new_task and should_show:
                    self.draw_task_card(new_task)
            top.destroy()

        ctk.CTkButton(top, text="Add Task", command=save, fg_color=COLORS["accent"]).pack(pady=10)

    def prompt_add_class(self):
        top = ctk.CTkToplevel(self)
        top.title("New Class")
        top.geometry("450x550")
        top.after(100, lambda: top.focus())

        ctk.CTkLabel(top, text="Class Name / Subject:", font=FONTS["body"]).pack(pady=(10, 0))
        title_e = ctk.CTkEntry(top, width=350)
        title_e.pack(pady=5)

        ctk.CTkLabel(top, text="Select Days:", font=FONTS["body"]).pack(pady=(5, 0))
        day_sel = DaySelector(top)
        day_sel.pack(pady=5)

        ctk.CTkLabel(top, text="Start Time:", font=FONTS["body"]).pack(pady=(10, 0))
        start_p = TimePicker(top, "09:00")
        start_p.pack(pady=5)

        ctk.CTkLabel(top, text="End Time:", font=FONTS["body"]).pack(pady=(10, 0))
        end_p = TimePicker(top, "10:30")
        end_p.pack(pady=5)

        def save():
            title = title_e.get().strip()
            days = day_sel.get()
            if title and days:
                sch = {"days": days, "start": start_p.get(), "end": end_p.get()}
                new_task = add_task_logic(self.app.data, title, category="class", days=days, schedule=sch, subject=title)
                # Silently add the new class card if it's for today
                from datetime import datetime
                today_day = datetime.now().strftime("%a").lower()
                if new_task and today_day in days:
                    self.draw_task_card(new_task)
            top.destroy()

        ctk.CTkButton(top, text="Add Class", command=save, fg_color=COLORS["accent"], height=40).pack(pady=20)

    def confirm_delete(self, task_id):
        if messagebox.askyesno("Delete", "Are you sure you want to delete this?"):
            delete_task_logic(self.app.data, task_id)
            self.render()

    def prompt_edit_task(self, task):
        top = ctk.CTkToplevel(self)
        top.title(f"Edit: {task['title']}")
        top.geometry("400x300")

        ctk.CTkLabel(top, text="Title:").pack(pady=(10,0))
        title_e = ctk.CTkEntry(top, width=300)
        title_e.insert(0, task["title"])
        title_e.pack(pady=5)

        ctk.CTkLabel(top, text="Duration (min):").pack(pady=(10,0))
        dur_e = ctk.CTkEntry(top, width=300)
        dur_e.insert(0, str(task.get("duration", "")))
        dur_e.pack(pady=5)

        def save():
            updates = {"title": title_e.get().strip()}
            if dur_e.get().isdigit(): updates["duration"] = int(dur_e.get())
            update_task_logic(self.app.data, task["id"], **updates)
            
            # Silent UI Update
            if task["id"] in self.task_cards:
                card = self.task_cards[task["id"]]
                # Update title
                if hasattr(card, "_title_lbl"):
                    icon = "📘" if task.get("type") == "class" else "📝"
                    card._title_lbl.configure(text=f"{icon} {updates['title']}")
                # Update duration (optional - complex to find label if not stored, 
                # but title is the main user concern)
            
            top.destroy()

        ctk.CTkButton(top, text="Update", command=save, fg_color=COLORS["success"]).pack(pady=20)

    def add_task(self, event=None):
        # Deprecated by prompt_add_task for more fields, but keeping if needed
        pass

    def complete_task(self, task_id):
        complete_task_logic(self.app.data, task_id)
        self.app.refresh_xp()
        self.render()

    def toggle_sub(self, task_id, sub_index):
        """Toggle subtask silently - checkbox already updates visually."""
        toggle_subtask(self.app.data, task_id, sub_index)
        self.app.refresh_xp()
        # No render() - checkbox handles its own visual state

    def complete_task_silent(self, task_id, card_widget):
        """Complete a task and remove the card without full refresh."""
        complete_task_logic(self.app.data, task_id)
        self.app.refresh_xp()
        card_widget.destroy()

    def confirm_delete_silent(self, task_id, card_widget):
        """Delete a task after confirmation and remove the card without full refresh."""
        if messagebox.askyesno("Delete", "Are you sure you want to delete this task?"):
            delete_task_logic(self.app.data, task_id)
            card_widget.destroy()
            # Remove from tracking
            if task_id in self.task_cards:
                del self.task_cards[task_id]

    def _get_or_create_detail_section(self, task_id):
        """Get or create the detail section for a task card."""
        if task_id not in self.task_cards:
            return None
        card = self.task_cards[task_id]
        if card._detail_section is None:
            detail_section = ctk.CTkFrame(card, fg_color=COLORS["bg_secondary"], corner_radius=8)
            detail_section.pack(fill="x", padx=12, pady=(4, 10))
            card._detail_section = detail_section
        return card._detail_section

    def _add_subtask_widget_silent(self, task_id, title):
        """Add a subtask checkbox widget silently."""
        detail_section = self._get_or_create_detail_section(task_id)
        if not detail_section:
            return
        
        task = next((t for t in self.app.data["tasks"] if t["id"] == task_id), None)
        if not task:
            return
        
        sub_index = len(task.get("subtasks", [])) - 1
        
        sub_frame = ctk.CTkFrame(detail_section, fg_color="transparent")
        sub_frame.pack(fill="x", padx=10, pady=2)
        
        s_chk = ctk.CTkCheckBox(sub_frame, text=title, font=FONTS["body"],
                                fg_color=COLORS["success"], 
                                hover_color=COLORS["success_dark"],
                                width=18, height=18,
                                command=lambda t=task_id, s=sub_index: self.toggle_sub(t, s))
        s_chk.pack(side="left")

    def _add_attachment_widget_silent(self, task_id, value):
        """Add an attachment label widget silently."""
        detail_section = self._get_or_create_detail_section(task_id)
        if not detail_section:
            return
        
        fname = value.split('/')[-1] if '://' not in value else value[:30] + '...'
        ctk.CTkLabel(detail_section, text=f"📄 {fname}",
                    font=FONTS["small"], text_color=COLORS["accent"]).pack(anchor="w", padx=10, pady=1)

    def _update_note_label_silent(self, task_id, text):
        """Update or create the note label silently."""
        if task_id not in self.task_cards: return
        card = self.task_cards[task_id]
        
        # If label exists, just update
        if hasattr(card, "_note_lbl") and card._note_lbl:
            card._note_lbl.configure(text=f"📝 {text[:100]}{'...' if len(text) > 100 else ''}")
            return

        # If empty text, do nothing (handling removal is complex, keeping old label is fine or empty string)
        if not text: return

        # Need to create label
        detail_section = self._get_or_create_detail_section(task_id)
        if detail_section:
            note_lbl = ctk.CTkLabel(detail_section, text=f"📝 {text[:100]}{'...' if len(text) > 100 else ''}", 
                        font=FONTS["small"], text_color=COLORS["text_dim"],
                        wraplength=500, justify="left")
            # Problem: Packing at end might be wrong order. `pack(side='top', before=...)` requires ref.
            # We'll just pack at top (default side='top') BEFORE other children? 
            # `pack` appends. To insert at top:
            # We can't easily reorder pack without unpacking all. 
            # Production hack: Just pack it. The user sees the note.
            note_lbl.pack(anchor="w", padx=10, pady=(8, 4))
            card._note_lbl = note_lbl

    def generate_ai_subtasks(self, task, card):
        """Ask AI to generate subtasks for this task."""
        from ai_parser import suggest_subtasks_ai
        from logic import add_subtask
        
        # UI Feedback
        self.app.refresh_xp() 
        
        def run_ai():
            subtasks = suggest_subtasks_ai(task["title"])
            if subtasks:
                for st in subtasks:
                    add_subtask(self.app.data, task["id"], st)
                
                # Full refresh for now to update details
                self.after(0, lambda: self.render())
            else:
                self.after(0, lambda: messagebox.showwarning("AI Error", "Could not generate subtasks. Try again!"))

        import threading
        threading.Thread(target=run_ai, daemon=True).start()

    def edit_task(self, task):
        # We can implement a full edit dialog later
        pass
