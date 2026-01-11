# ==================== UI.PY (MODERN) ====================
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
from datetime import datetime, timedelta
from PIL import Image
import os
from tkcalendar import Calendar

from logic import (
    load_data, save_data, add_task_logic, add_subtask, toggle_subtask,
    get_level_progress, get_active_class, mark_class_done,
    sync_class_statuses, log_focus_time, cleanup_finished_classes,
    get_today_tasks, get_weekly_class_tasks, today, format_seconds_to_hms,
    log_class_session, get_today_focus_stats, log_focus_session,
    complete_task_logic, add_xp, delete_task_logic, update_task_logic,
    add_subject, delete_subject, add_vault_file, delete_vault_file, rename_subject,
    add_habit, delete_habit, toggle_habit_today, get_habit_streak, get_analytics_data,
    get_heatmap_data, get_store_items, purchase_item, is_unlocked,
    get_pomodoro_settings, update_pomodoro_settings,
    update_timer_state, clear_timer_state
)
import subprocess
from ai_parser import format_today_schedule, format_user_stats

# ==================== CONFIG ====================
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Modern Premium Color Palette
COLORS = {
    "bg": "#0F0F1A",              # Deep rich dark
    "bg": ("#F5F5F7", "#0F0F1A"),
    "bg_secondary": ("#FFFFFF", "#1A1A2E"),
    "sidebar": ("#EBEBEF", "#12121F"),
    "card": ("#FFFFFF", "#1C1C32"),
    "card_hover": ("#F0F0F5", "#252540"),
    "card_highlight": ("#E0E0E5", "#2A2A50"),
    "accent": ("#6C63FF", "#6C63FF"),
    "accent_light": ("#8B83FF", "#8B83FF"),
    "accent_dark": ("#5A52E0", "#5A52E0"),
    "accent_hover": ("#5A52E0", "#5A52E0"),
    "success": ("#00D9A5", "#00D9A5"),
    "success_dark": ("#00B88A", "#00B88A"),
    "warning": ("#FFB84D", "#FFB84D"),
    "error": ("#FF6B6B", "#FF6B6B"),
    "text": ("#1A1A2E", "#E8E8F0"),
    "text_dim": ("#5A5A7A", "#7A7A9A"),
    "text_muted": ("#8A8A9A", "#5A5A7A"),
    "border": ("#D0D0D5", "#2A2A45"),
    "border_light": ("#E0E0E5", "#3A3A55"),
    "glass": ("#FFFFFF", "#1A1A2E"),
    "glow": ("#6C63FF33", "#6C63FF33"),
}

def get_color_str(key):
    """Helper to get hex string from COLORS[key] based on current mode."""
    val = COLORS.get(key)
    if not val: return "#000000"
    if isinstance(val, tuple):
        return val[0] if ctk.get_appearance_mode() == "Light" else val[1]
    return val

FONTS = {
    "title": ("Inter", 26, "bold"),
    "header": ("Inter", 18, "bold"),
    "subheader": ("Inter", 15, "bold"),
    "body": ("Inter", 13),
    "small": ("Inter", 11),
    "tiny": ("Inter", 9),
    "clock": ("Inter", 38, "bold"),
    "timer": ("Inter", 28, "bold"),
}

class TimePicker(ctk.CTkFrame):
    def __init__(self, parent, initial="09:00"):
        super().__init__(parent, fg_color="transparent")
        h, m = initial.split(":")
        self.hour_var = ctk.StringVar(value=h)
        self.min_var = ctk.StringVar(value=m)

        ctk.CTkOptionMenu(self, variable=self.hour_var, width=60,
                          values=[f"{i:02}" for i in range(24)]).pack(side="left", padx=2)
        ctk.CTkLabel(self, text=":").pack(side="left")
        ctk.CTkOptionMenu(self, variable=self.min_var, width=60,
                          values=[f"{i:02}" for i in range(0, 60, 5)]).pack(side="left", padx=2)

    def get(self):
        return f"{self.hour_var.get()}:{self.min_var.get()}"

# ==================== COMPONENTS ====================

class SidebarButton(ctk.CTkButton):
    """Enhanced sidebar navigation button with modern styling."""
    def __init__(self, parent, text, command, icon=None, **kwargs):
        super().__init__(
            parent,
            text=text,
            command=command,
            fg_color="transparent",
            text_color=COLORS["text_dim"],
            hover_color=COLORS["card_hover"],
            anchor="w",
            font=FONTS["body"],
            height=48,
            corner_radius=12,
            **kwargs
        )
        # Bind hover events for visual feedback
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self._is_active = False
    
    def _on_enter(self, event=None):
        if not self._is_active:
            self.configure(text_color=COLORS["text"])
    
    def _on_leave(self, event=None):
        if not self._is_active:
            self.configure(text_color=COLORS["text_dim"])
    
    def set_active(self, active):
        self._is_active = active
        if active:
            self.configure(
                fg_color=COLORS["accent"],
                text_color="white",
                hover_color=COLORS["accent_dark"]
            )
        else:
            self.configure(
                fg_color="transparent",
                text_color=COLORS["text_dim"],
                hover_color=COLORS["card_hover"]
            )

class Tooltip:
    """Hover tooltip that shows details on mouse enter."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show)
        self.widget.bind("<Leave>", self.hide)
    
    def show(self, event=None):
        if self.tooltip: return
        
        x = self.widget.winfo_rootx() + 50
        y = self.widget.winfo_rooty() + 30
        
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        self.tooltip.configure(bg=COLORS["card"])
        
        frame = ctk.CTkFrame(self.tooltip, fg_color=COLORS["card"], corner_radius=8,
                             border_width=1, border_color=COLORS["border"])
        frame.pack(fill="both", expand=True)
        
        ctk.CTkLabel(frame, text=self.text, font=FONTS["small"], 
                     text_color=COLORS["text"], justify="left",
                     wraplength=200).pack(padx=10, pady=8)
    
    def hide(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

class XPBar(ctk.CTkFrame):
    """Enhanced XP progress bar with level badge and gradient styling."""
    def __init__(self, parent, data):
        super().__init__(parent, fg_color="transparent")
        self.data = data
        self.render()

    def render(self):
        for w in self.winfo_children(): w.destroy()

        container = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=15)
        container.pack(fill="x", padx=20, pady=10)
        
        inner = ctk.CTkFrame(container, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=15)

        lvl = self.data.get("level", 1)
        
        # Level Badge with glow effect
        badge_frame = ctk.CTkFrame(inner, fg_color=COLORS["accent"], corner_radius=10, width=70, height=36)
        badge_frame.pack(side="left")
        badge_frame.pack_propagate(False)
        
        ctk.CTkLabel(badge_frame, text=f"⭐ LVL {lvl}", text_color="white",
                     font=FONTS["subheader"]).pack(expand=True)

        curr, req, pct = get_level_progress(self.data)

        # Progress container
        progress_container = ctk.CTkFrame(inner, fg_color="transparent")
        progress_container.pack(side="left", fill="x", expand=True, padx=20)

        # Progress bar with gradient look (using two colors)
        self.progress_bar = ctk.CTkProgressBar(
            progress_container, 
            fg_color=COLORS["border"],
            progress_color=COLORS["success"],  # Teal color
            height=12,
            corner_radius=6
        )
        self.progress_bar.set(pct / 100)
        self.progress_bar.pack(fill="x")

        # XP Text with styling
        xp_text = ctk.CTkLabel(inner, text=f"{curr} / {req} XP", text_color=COLORS["text_dim"],
                     font=FONTS["small"])
        xp_text.pack(side="left")
        
        # Streak indicator (if streak exists)
        streak = self.data.get("streak", 0)
        if streak > 0:
            streak_badge = ctk.CTkFrame(inner, fg_color=COLORS["warning"], corner_radius=8)
            streak_badge.pack(side="right", padx=10)
            ctk.CTkLabel(streak_badge, text=f"🔥 {streak} days", text_color="#1a1a1a",
                        font=FONTS["small"]).pack(padx=8, pady=4)


# ==================== VIEWS ====================

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
                      command=lambda: self.prompt_edit_task(task)).pack(side="right", padx=2)

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
        top.geometry("450x450")
        top.after(100, lambda: top.focus())

        ctk.CTkLabel(top, text="Task Title:", font=FONTS["body"]).pack(pady=(10, 0))
        title_e = ctk.CTkEntry(top, width=350)
        title_e.pack(pady=5)

        ctk.CTkLabel(top, text="Select Date:", font=FONTS["body"]).pack(pady=(10, 0))
        cal = Calendar(top, selectmode='day', date_pattern='yyyy-mm-dd',
                       background=COLORS["card"], foreground="white",
                       headersbackground=COLORS["sidebar"], normalbackground=COLORS["card"],
                       selectbackground=COLORS["accent"])
        cal.pack(pady=10)

        ctk.CTkLabel(top, text="Time Limit (minutes, optional):", font=FONTS["body"]).pack(pady=(5, 0))
        dur_e = ctk.CTkEntry(top, width=350, placeholder_text="e.g. 30")
        dur_e.pack(pady=5)

        def save():
            title = title_e.get().strip()
            if title:
                dur = None
                if dur_e.get().isdigit(): dur = int(dur_e.get())
                date = cal.get_date()
                new_task = add_task_logic(self.app.data, title, duration=dur, deadline=date)
                # Silently add the new task card if it's for today
                if new_task and new_task.get("date") == today():
                    self.draw_task_card(new_task)
            top.destroy()

        ctk.CTkButton(top, text="Add Task", command=save, fg_color=COLORS["accent"]).pack(pady=10)

    def prompt_add_class(self):
        top = ctk.CTkToplevel(self)
        top.title("New Class")
        top.geometry("400x550")
        top.after(100, lambda: top.focus())

        ctk.CTkLabel(top, text="Class Name / Subject:", font=FONTS["body"]).pack(pady=(10, 0))
        title_e = ctk.CTkEntry(top, width=300)
        title_e.pack(pady=5)

        ctk.CTkLabel(top, text="Days (e.g. mon, wed, fri):", font=FONTS["body"]).pack(pady=(5, 0))
        days_e = ctk.CTkEntry(top, width=300)
        days_e.pack(pady=5)

        ctk.CTkLabel(top, text="Start Time:", font=FONTS["body"]).pack(pady=(10, 0))
        start_p = TimePicker(top, "09:00")
        start_p.pack(pady=5)

        ctk.CTkLabel(top, text="End Time:", font=FONTS["body"]).pack(pady=(10, 0))
        end_p = TimePicker(top, "10:30")
        end_p.pack(pady=5)

        def save():
            title = title_e.get().strip()
            days_str = days_e.get().strip()
            if title and days_str:
                days = [d.strip().lower()[:3] for d in days_str.split(",")]
                sch = {"days": days, "start": start_p.get(), "end": end_p.get()}
                new_task = add_task_logic(self.app.data, title, category="class", days=days, schedule=sch, subject=title)
                # Silently add the new class card if it's for today
                from datetime import datetime
                today_day = datetime.now().strftime("%a").lower()
                if new_task and today_day in days:
                    self.draw_task_card(new_task)
            top.destroy()

        ctk.CTkButton(top, text="Add Class", command=save, fg_color=COLORS["accent"]).pack(pady=20)

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

class RoutineView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=COLORS["bg"])
        self.app = app
        self.class_cards = {}  # class_id -> card widget
        self.day_containers = {}  # day_name -> scrollable frame
        self.render()

    def render(self):
        for w in self.winfo_children(): w.destroy()
        self.class_cards = {}
        self.day_containers = {}

        # Header with import button
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(10, 20))
        
        ctk.CTkLabel(header, text="📅 Weekly Routine", font=FONTS["title"],
                     text_color=COLORS["text"]).pack(side="left")
        
        ctk.CTkButton(header, text="📥 Import Schedule", width=140, height=36,
                      fg_color=COLORS["accent"], hover_color=COLORS["accent_dark"],
                      corner_radius=8, command=self.show_import_dialog).pack(side="right", padx=5)
        
        ctk.CTkButton(header, text="+ Add Class", width=100, height=36,
                      fg_color=COLORS["card"], hover_color=COLORS["card_hover"],
                      corner_radius=8, command=self.prompt_add_class).pack(side="right")

        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        for i, d in enumerate(days):
            grid.grid_columnconfigure(i, weight=1, uniform="days")

            day_header = ctk.CTkFrame(grid, fg_color=COLORS["card"], height=35)
            day_header.grid(row=0, column=i, sticky="ew", padx=2, pady=2)
            day_header.grid_propagate(False)
            ctk.CTkLabel(day_header, text=d.upper(), font=FONTS["small"]).pack(expand=True)

            # Fixed height day content to prevent resizing
            day_content = ctk.CTkScrollableFrame(grid, fg_color=COLORS["sidebar"], 
                                                  height=350, scrollbar_button_color=COLORS["card"])
            day_content.grid(row=1, column=i, sticky="nsew", padx=2, pady=2)
            self.day_containers[d] = day_content  # Store for silent add
            grid.grid_rowconfigure(1, weight=1, minsize=350)

            weekly = get_weekly_class_tasks(self.app.data)
            classes = weekly.get(d, [])
            classes.sort(key=lambda x: x.get("schedule", {}).get("start", ""))

            for c in classes:
                self._draw_class_card(day_content, c)

    def _draw_class_card(self, parent, c):
        """Draw a single class card and register it."""
        sch = c.get("schedule", {})
        cls_card = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=5)
        cls_card.pack(fill="x", pady=2, padx=2)
        
        # simple store for callback
        cls_card._class_id = c["id"]
        
        # Register in class_cards list (one class can be on multiple days)
        if c["id"] not in self.class_cards:
            self.class_cards[c["id"]] = []
        self.class_cards[c["id"]].append(cls_card)
        
        # Class info
        time_lbl = ctk.CTkLabel(cls_card, text=f"{sch.get('start','')}", 
                        font=FONTS["tiny"], text_color=COLORS["warning"])
        time_lbl.pack(pady=(4,0))
        
        title_lbl = ctk.CTkLabel(cls_card, text=f"{c['title'][:10]}", 
                        font=FONTS["small"], text_color=COLORS["accent"])
        title_lbl.pack()
        
        # Store label references for silent update
        cls_card._time_lbl = time_lbl
        cls_card._title_lbl = title_lbl
        
        # Tooltip with full details
        days_str = ", ".join(sch.get("days", [])).upper()
        tooltip_text = f"📚 {c['title']}\n⏰ {sch.get('start','')} - {sch.get('end','')}\n📅 {days_str}"
        Tooltip(cls_card, tooltip_text)
        
        # Edit/Delete buttons (fix callback to not pass specific card, but ID)
        btn_frame = ctk.CTkFrame(cls_card, fg_color="transparent")
        btn_frame.pack(pady=(0, 4))
        ctk.CTkButton(btn_frame, text="✎", width=22, height=18, font=FONTS["tiny"],
                        fg_color="transparent", hover_color=COLORS["accent"],
                        text_color=COLORS["text_dim"],
                        command=lambda cid=c["id"]: self.edit_class(cid)).pack(side="left", padx=1)
        ctk.CTkButton(btn_frame, text="✕", width=22, height=18, font=FONTS["tiny"],
                        fg_color="transparent", hover_color=COLORS["error"],
                        text_color=COLORS["text_dim"],
                        command=lambda cid=c["id"]: self.delete_class_silent(cid)).pack(side="left", padx=1)

    def edit_class(self, class_id):
        """Edit a class silently."""
        task = next((t for t in self.app.data["tasks"] if t["id"] == class_id), None)
        if not task: return
        
        top = ctk.CTkToplevel(self)
        top.title(f"Edit: {task['title']}")
        top.geometry("400x350")
        top.after(100, lambda: top.focus())
        
        sch = task.get("schedule", {})
        
        ctk.CTkLabel(top, text="Class Name:", font=FONTS["body"]).pack(pady=(15, 5))
        name_e = ctk.CTkEntry(top, width=300)
        name_e.insert(0, task["title"])
        name_e.pack(pady=5)
        
        ctk.CTkLabel(top, text="Days (e.g., sun, mon, tue):", font=FONTS["body"]).pack(pady=(10, 5))
        days_e = ctk.CTkEntry(top, width=300)
        days_e.insert(0, ", ".join(sch.get("days", [])))
        days_e.pack(pady=5)
        
        ctk.CTkLabel(top, text="Start Time:", font=FONTS["body"]).pack(pady=(10, 5))
        start_e = ctk.CTkEntry(top, width=300)
        start_e.insert(0, sch.get("start", "09:00"))
        start_e.pack(pady=5)
        
        ctk.CTkLabel(top, text="End Time:", font=FONTS["body"]).pack(pady=(10, 5))
        end_e = ctk.CTkEntry(top, width=300)
        end_e.insert(0, sch.get("end", "10:30"))
        end_e.pack(pady=5)
        
        def save():
            new_title = name_e.get().strip()
            days_str = days_e.get().strip()
            new_days = [d.strip().lower()[:3] for d in days_str.split(",")]
            new_start = start_e.get().strip()
            new_end = end_e.get().strip()
            
            # Update data
            task["title"] = new_title
            task["schedule"] = {"days": new_days, "start": new_start, "end": new_end}
            save_data(self.app.data)
            
            # Silent Update
            # If days changed, we must re-draw the cards
            old_days = sch.get("days", [])
            if set(new_days) != set(old_days):
                # Remove all old cards
                self.delete_class_silent_ui_only(class_id)
                # Draw new cards
                for day in new_days:
                    if day in self.day_containers:
                        self._draw_class_card(self.day_containers[day], task)
            else:
                # Just update labels in place
                if class_id in self.class_cards:
                    for card in self.class_cards[class_id]:
                        if hasattr(card, "_title_lbl"): card._title_lbl.configure(text=new_title[:10])
                        if hasattr(card, "_time_lbl"): card._time_lbl.configure(text=new_start)
            
            top.destroy()
        
        ctk.CTkButton(top, text="Save", fg_color=COLORS["success"], command=save).pack(pady=15)
    
    def delete_class_silent(self, class_id):
        """Delete a class silently without full refresh (removes all cards)."""
        if messagebox.askyesno("Delete", "Delete this class?"):
            delete_task_logic(self.app.data, class_id)
            self.delete_class_silent_ui_only(class_id)
            
    def delete_class_silent_ui_only(self, class_id):
        """Helper to remove cards for a class ID without deleting data."""
        if class_id in self.class_cards:
            for card in self.class_cards[class_id]:
                card.destroy()
            del self.class_cards[class_id]

    def show_import_dialog(self):
        """Show dialog to paste and import schedule."""
        top = ctk.CTkToplevel(self)
        top.title("Import Weekly Schedule")
        top.geometry("650x550")
        top.after(100, lambda: top.focus())
        
        ctk.CTkLabel(top, text="📥 Paste your schedule (any format!):", font=FONTS["header"]).pack(pady=(15, 5))
        ctk.CTkLabel(top, text="AI will automatically detect classes, days, and times", 
                     font=FONTS["small"], text_color=COLORS["text_dim"]).pack(pady=(0, 5))
        
        # Option to clear existing
        clear_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(top, text="Clear existing classes before import", 
                        variable=clear_var, font=FONTS["small"]).pack(pady=5)
        
        txt = ctk.CTkTextbox(top, font=FONTS["body"], height=320)
        txt.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Status label
        status_lbl = ctk.CTkLabel(top, text="", font=FONTS["small"], text_color=COLORS["text_dim"])
        status_lbl.pack(pady=5)
        
        def parse_and_import():
            if clear_var.get():
                # Remove all existing classes
                self.app.data["tasks"] = [t for t in self.app.data["tasks"] if t.get("type") != "class"]
                save_data(self.app.data)
                self.render()  # Clear UI immediately
            
            content = txt.get("1.0", "end-1c")
            status_lbl.configure(text="🔄 Parsing with AI...")
            top.update()
            
            count = self.parse_schedule_ai(content)
            top.destroy()
            if count > 0:
                messagebox.showinfo("Success", f"✅ Imported {count} classes!")
                # self.render() removed - updates are now dynamic
            else:
                messagebox.showwarning("No Classes Found", "Could not detect any classes. Try a clearer format.")
        
        ctk.CTkButton(top, text="🤖 Import with AI", fg_color=COLORS["accent"],
                      hover_color=COLORS["accent_dark"], height=40,
                      command=parse_and_import).pack(pady=15)

    def parse_schedule_ai(self, text):
        """Parse schedule using AI - format free!"""
        from ai_parser import SmartParser
        import re
        
        parser = SmartParser()
        count = 0
        
        # Day mapping for normalization
        day_map = {"sunday": "sun", "monday": "mon", "tuesday": "tue", 
                   "wednesday": "wed", "thursday": "thu", "friday": "fri", "saturday": "sat"}
        
        lines = text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or len(line) < 5: continue
            
            # Use SmartParser for robust detection (Regex + AI)
            result = parser.parse(line)
            
            if result and result.get("intent") == "class" and not result.get("needs_clarification"):
                self._add_or_update_class(
                    result.get("title", "Class"),
                    result.get("days", []),
                    result.get("start", "09:00"),
                    result.get("end", "10:30")
                )
                count += 1
            elif result and result.get("intent") == "schedule_file" and "classes" in result:
                for c in result["classes"]:
                    self._add_or_update_class(
                        c.get("title", "Class"),
                        c.get("days", []),
                        c.get("start", "09:00"),
                        c.get("end", "10:30")
                    )
                    count += 1
        
        return count
    
    def _add_or_update_class(self, title, days, start, end):
        """Add new class or update existing by name silently."""
        # Check for duplicates by name
        existing = next((t for t in self.app.data["tasks"] 
                        if t.get("type") == "class" and t.get("title") == title), None)
        
        if existing:
            # Update existing
            existing["schedule"] = {"days": days, "start": start, "end": end}
            save_data(self.app.data)
            
            # Silent Update UI
            self.delete_class_silent_ui_only(existing["id"])
            for day in days:
                if day in self.day_containers:
                    self._draw_class_card(self.day_containers[day], existing)
            
        else:
            # Add new
            new_class = add_task_logic(
                self.app.data,
                title=title,
                category="class",
                schedule={"days": days, "start": start, "end": end},
                subject=title
            )
            # Silent Add UI
            if new_class:
                for day in days:
                    if day in self.day_containers:
                        self._draw_class_card(self.day_containers[day], new_class)

    def prompt_add_class(self):
        """Quick add single class."""
        top = ctk.CTkToplevel(self)
        top.title("Add Class")
        top.geometry("400x400")
        top.after(100, lambda: top.focus())
        
        ctk.CTkLabel(top, text="Class Name:", font=FONTS["body"]).pack(pady=(15, 5))
        name_e = ctk.CTkEntry(top, width=300)
        name_e.pack(pady=5)
        
        ctk.CTkLabel(top, text="Days (e.g., mon, wed, fri):", font=FONTS["body"]).pack(pady=(10, 5))
        days_e = ctk.CTkEntry(top, width=300)
        days_e.pack(pady=5)
        
        ctk.CTkLabel(top, text="Start Time (HH:MM):", font=FONTS["body"]).pack(pady=(10, 5))
        start_e = ctk.CTkEntry(top, width=300, placeholder_text="09:00")
        start_e.pack(pady=5)
        
        ctk.CTkLabel(top, text="End Time (HH:MM):", font=FONTS["body"]).pack(pady=(10, 5))
        end_e = ctk.CTkEntry(top, width=300, placeholder_text="10:30")
        end_e.pack(pady=5)
        
        def save():
            name = name_e.get().strip()
            days_str = days_e.get().strip()
            start = start_e.get().strip() or "09:00"
            end = end_e.get().strip() or "10:30"
            
            if name and days_str:
                days = [d.strip().lower()[:3] for d in days_str.split(",")]
                new_class = add_task_logic(
                    self.app.data,
                    title=name,
                    category="class",
                    schedule={"days": days, "start": start, "end": end},
                    subject=name
                )
                # Silent add
                if new_class:
                    for day in days:
                        if day in self.day_containers:
                            self._draw_class_card(self.day_containers[day], new_class)
            top.destroy()
        
        ctk.CTkButton(top, text="Add Class", fg_color=COLORS["accent"],
                      command=save).pack(pady=20)

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

class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=COLORS["bg"])
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
        self._draw_section("Appearance", [
            ctk.CTkOptionMenu(self, values=["System", "Dark", "Light"],
                              command=self._change_theme)
        ])
        
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

        # Save Button
        ctk.CTkButton(self, text="Save Settings", font=FONTS["body"], 
                      fg_color=COLORS["success"], hover_color=COLORS["success_dark"],
                      command=self.save_settings).pack(pady=20)
        
    def save_settings(self, *args):
        # Update logic
        style = self.style_var.get().lower()
        
        # Save sliders + Style
        try:
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

class StoreView(ctk.CTkScrollableFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=COLORS["bg"])
        self.app = app
        self.render()
        
    def render(self):
        for w in self.winfo_children(): w.destroy()
        
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=20)
        ctk.CTkLabel(header, text="XP Store", font=FONTS["title"], text_color=COLORS["text"]).pack(side="left")
        
        # XP Balance
        xp_bal = ctk.CTkLabel(header, text=f"💎 {self.app.data.get('xp', 0)} XP", 
                              font=FONTS["header"], text_color=COLORS["accent"])
        xp_bal.pack(side="right")
        
        # Items Grid
        items = get_store_items(self.app.data)
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=10)
        
        for i, item in enumerate(items):
            card = ctk.CTkFrame(grid, fg_color=COLORS["card"], corner_radius=15, border_width=1, border_color=COLORS["border"])
            card.grid(row=i//2, column=i%2, padx=10, pady=10, sticky="nsew")
            grid.grid_columnconfigure(i%2, weight=1)
            
            # Content
            ctk.CTkLabel(card, text="🎨" if item["type"]=="theme" else "🎵" if item["type"]=="sound" else "🌟", 
                         font=("Arial", 30)).pack(pady=(15, 0))
            
            ctk.CTkLabel(card, text=item["name"], font=FONTS["header"]).pack(pady=5)
            ctk.CTkLabel(card, text=item["desc"], font=FONTS["small"], text_color=COLORS["text_dim"]).pack(pady=5)
            
            btn_text = "Unlocked" if is_unlocked(self.app.data, item["id"]) else f"Buy ({item['cost']} XP)"
            btn_col = COLORS["success"] if is_unlocked(self.app.data, item["id"]) else COLORS["accent"]
            state = "disabled" if is_unlocked(self.app.data, item["id"]) else "normal"
            
            ctk.CTkButton(card, text=btn_text, fg_color=btn_col, state=state,
                          command=lambda id=item["id"]: self.buy(id)).pack(pady=15)

    def buy(self, item_id):
        success, msg = purchase_item(self.app.data, item_id)
        if success:
            messagebox.showinfo("Store", msg)
            self.app.refresh_xp()
            self.render()
        else:
            messagebox.showerror("Store", msg)
        
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

    def _draw_focus_chart(self, parent, daily_focus):
        frame = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=15)
        frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(frame, text="Daily Focus (Minutes)", font=FONTS["header"],
                     text_color=COLORS["accent"]).pack(anchor="w", padx=20, pady=(15, 5))
        
        canvas = tk.Canvas(frame, bg=get_color_str("card"), height=200, highlightthickness=0)
        canvas.pack(fill="x", padx=20, pady=(0, 20))
        
        if not daily_focus:
            canvas.create_text(200, 100, text="No data yet", fill=COLORS["text_dim"], font=("Inter", 12))
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


# ==================== MAIN APP ====================

class FocusApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Focus App")
        # Window Setup
        self.title("Focus Dashboard")
        self.center_window()
        self.minsize(1000, 600)
        self.configure(fg_color=COLORS["bg"])

        self.data = load_data()
        self.active_view = None  # Will be set by switch_view

        # Timer State - RESTORED FROM PERSISTENCE
        saved_state = self.data.get("timer_state", {})
        self.timer_seconds = saved_state.get("seconds", 0)
        self.timer_mode = saved_state.get("mode", "focus")
        self.active_class_id = saved_state.get("class_id", None)
        
        self.timer_running = False # Always start paused
        self.last_tick = None

        # Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=240, fg_color=COLORS["sidebar"], corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.setup_sidebar()

        # Main content
        self.main_container = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        self.main_container.grid(row=0, column=1, sticky="nsew")

        self.top_bar = XPBar(self.main_container, self.data)
        self.top_bar.pack(fill="x")

        self.view_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.view_container.pack(fill="both", expand=True, padx=20, pady=10)

        self.views = {}
        self.init_views()
        self.switch_view("today")

        # Setup keyboard shortcuts
        self.setup_keyboard_shortcuts()
        
        # Enable mouse scrolling globally
        self.bind_mouse_scroll()
        
        self.update_clock()
    
    def setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for navigation and actions."""
        # View navigation (1-6 keys)
        self.bind("<Key-1>", lambda e: self.switch_view("today"))
        self.bind("<Key-2>", lambda e: self.switch_view("routine"))
        self.bind("<Key-3>", lambda e: self.switch_view("vault"))
        self.bind("<Key-4>", lambda e: self.switch_view("history"))
        self.bind("<Key-5>", lambda e: self.switch_view("report"))
        
        # Quick actions
        self.bind("<Control-n>", lambda e: self.quick_add_task())
        self.bind("<Control-N>", lambda e: self.quick_add_task())
        self.bind("<space>", lambda e: self.toggle_timer())
        self.bind("<Control-q>", lambda e: self.quit())
        self.bind("<Control-Q>", lambda e: self.quit())
        self.bind("<Escape>", lambda e: self.focus_set())  # Clear focus
        
        # Timer controls
        self.bind("<Control-t>", lambda e: self.toggle_timer())
        self.bind("<Control-T>", lambda e: self.toggle_timer())
    
    def quick_add_task(self):
        """Quick action to add a new task."""
        if hasattr(self.views.get("today"), "prompt_add_task"):
            self.switch_view("today")
            self.views["today"].prompt_add_task()
    
    def bind_mouse_scroll(self):
        """Enable mouse scroll wheel on Linux."""
        # Linux scroll events
        self.bind_all("<Button-4>", self._on_scroll_up)
        self.bind_all("<Button-5>", self._on_scroll_down)
        # Windows/Mac scroll events  
        self.bind_all("<MouseWheel>", self._on_mousewheel)
    
    def _on_scroll_up(self, event):
        """Handle scroll up (Linux Button-4)."""
        widget = event.widget
        # Find parent scrollable frame
        while widget:
            if hasattr(widget, '_parent_canvas'):
                widget._parent_canvas.yview_scroll(-3, "units")
                return
            widget = widget.master if hasattr(widget, 'master') else None
    
    def _on_scroll_down(self, event):
        """Handle scroll down (Linux Button-5)."""
        widget = event.widget
        while widget:
            if hasattr(widget, '_parent_canvas'):
                widget._parent_canvas.yview_scroll(3, "units")
                return
            widget = widget.master if hasattr(widget, 'master') else None
    
    def _on_mousewheel(self, event):
        """Handle mouse wheel scroll (Windows/Mac)."""
        widget = event.widget
        while widget:
            if hasattr(widget, '_parent_canvas'):
                widget._parent_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                return
            widget = widget.master if hasattr(widget, 'master') else None

    def setup_sidebar(self):
        """Setup enhanced sidebar with modern styling."""
        # Clock section with gradient background
        clock_section = ctk.CTkFrame(self.sidebar, fg_color=COLORS["card"], corner_radius=15)
        clock_section.pack(fill="x", padx=15, pady=(20, 15))
        
        self.clock_lbl = ctk.CTkLabel(clock_section, text="00:00", font=FONTS["clock"],
                                       text_color=COLORS["text"])
        self.clock_lbl.pack(pady=(15, 5))

        self.date_lbl = ctk.CTkLabel(clock_section, text="Date", text_color=COLORS["text_dim"],
                                      font=FONTS["body"])
        self.date_lbl.pack(pady=(0, 15))

        # Separator
        separator = ctk.CTkFrame(self.sidebar, fg_color=COLORS["border"], height=1)
        separator.pack(fill="x", padx=20, pady=10)

        # Timer Frame (Moved to Top for Visibility)
        self.timer_frame = ctk.CTkFrame(self.sidebar, fg_color=COLORS["card"], corner_radius=15,
                                        border_width=1, border_color=COLORS["border"])
        self.timer_frame.pack(side="top", fill="x", padx=15, pady=(10, 10))

        timer_header = ctk.CTkFrame(self.timer_frame, fg_color="transparent")
        timer_header.pack(fill="x", padx=15, pady=(12, 0))
        
        self.timer_mode_lbl = ctk.CTkLabel(timer_header, text="🎯 Focus Session",
                                           text_color=COLORS["success"], font=FONTS["small"])
        self.timer_mode_lbl.pack(side="left")

        self.timer_lbl = ctk.CTkLabel(self.timer_frame, text="00:00:00", font=FONTS["timer"],
                                       text_color=COLORS["text"])
        self.timer_lbl.pack(pady=10)

        self.timer_btns = ctk.CTkFrame(self.timer_frame, fg_color="transparent")
        self.timer_btns.pack(fill="x", padx=15, pady=(0, 15))

        self.timer_ctrl = ctk.CTkButton(self.timer_btns, text="▶ Start", height=40,
                                        fg_color=COLORS["success"], hover_color=COLORS["success_dark"],
                                        corner_radius=10, font=FONTS["body"],
                                        command=self.toggle_timer)
        self.timer_ctrl.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.stop_btn = ctk.CTkButton(self.timer_btns, text="⏹", width=40, height=40,
                                      fg_color=COLORS["error"], hover_color="#CC0000",
                                      corner_radius=10, font=FONTS["header"],
                                      state="disabled",
                                      command=lambda: self.stop_timer(log=True))
        self.stop_btn.pack(side="right")
        
        # Navigation section
        nav_label = ctk.CTkLabel(self.sidebar, text="NAVIGATION", font=FONTS["tiny"],
                                  text_color=COLORS["text_muted"])
        nav_label.pack(anchor="w", padx=20, pady=(5, 10))
        
        self.nav_buttons = {}
        items = [
            ("📅 Today", "today"),
            ("🗓️ Routine", "routine"),
            ("🥗 Habits", "habits"),
            ("📂 Vault", "vault"),
            ("📜 History", "history"),
            ("📊 Report", "report"),
            ("🛒 Store", "store"),
            ("⚙️ Settings", "settings")
        ]
        for text, key in items:
            btn = SidebarButton(self.sidebar, text=text, command=lambda k=key: self.switch_view(k))
            btn.pack(fill="x", padx=15, pady=3)
            self.nav_buttons[key] = btn

        
        # Zen Mode Toggle (If unlocked) - Moved to bottom of nav
        zen_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        zen_frame.pack(side="bottom", fill="x", padx=15, pady=20)
        
        if is_unlocked(self.data, "zen_mode"):
             ctk.CTkButton(zen_frame, text="🧘 Enter Zen Mode", fg_color=COLORS["accent"],
                           hover_color=COLORS["accent_dark"],
                           command=self.toggle_zen_mode).pack(fill="x")

    def init_views(self):
        # Lazy loading: store view classes, create instances on first access
        self.view_classes = {
            "today": TodayView,
            "routine": RoutineView,
            "habits": HabitView,
            "vault": VaultView,
            "history": HistoryView,
            "report": ReportView,
            "settings": SettingsView,
            "store": StoreView
        }
        self.views = {}  # Instances will be created on demand
        
    def _get_view(self, name):
        """Lazy load view - only create when first accessed."""
        if name not in self.views:
            if name in self.view_classes:
                self.views[name] = self.view_classes[name](self.view_container, self)
                self.views[name].pack_forget()
        return self.views.get(name)

    def switch_view(self, name):
        """Switch to a view and update navigation styling with lazy loading."""
        if name not in self.view_classes: return
        if self.active_view == name: return  # View guard

        # Hide all existing views
        for v in self.views.values(): v.pack_forget()
        
        # Lazy load the requested view
        view = self._get_view(name)
        if view:
            view.pack(fill="both", expand=True)

            # Use the enhanced set_active method
            for k, b in self.nav_buttons.items():
                b.set_active(k == name)

            self.active_view = name
            if hasattr(view, "render"): view.render()

    def refresh_xp(self):
        self.top_bar.render()

    def update_clock(self):
        now = datetime.now()
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%a, %b %d")
        
        # Only update if strings changed
        if self.clock_lbl.cget("text") != time_str:
            self.clock_lbl.configure(text=time_str)
        if self.date_lbl.cget("text") != date_str:
            self.date_lbl.configure(text=date_str)
        
        # Check active class efficiently
        active = get_active_class(self.data)
        if active:
            status_text = f"🔴 Class: {active['title']}"
            if self.timer_mode_lbl.cget("text") != status_text:
                self.timer_mode_lbl.configure(text=status_text, text_color=COLORS["error"])
            
            if self.timer_mode != "class" or self.active_class_id != active["id"]:
                if self.timer_running: self.stop_timer(log=True)
                self.timer_mode = "class"
                self.active_class_id = active["id"]
                self.start_timer()
        else:
            if self.timer_mode_lbl.cget("text") != "🎯 Focus Session":
                self.timer_mode_lbl.configure(text="🎯 Focus Session", text_color=COLORS["success"])
            if self.timer_mode == "class":
                if self.timer_running: self.stop_timer(log=True)
                self.timer_mode = "focus"
                self.active_class_id = None
        
        self.after(1000, self.update_clock)

    def update_timer(self):
        if not self.timer_running: return
        
        now = datetime.now()
        elapsed = (now - self.last_tick).total_seconds()
        
        style = self.data.get("settings", {}).get("timer_style", "stopwatch")

        if style == "countdown":
            self.timer_seconds -= elapsed
            
            if self.timer_seconds <= 0:
                self.timer_seconds = 0
                self.stop_timer(log=True) # Auto stop
                self.sound_mgr.play("success")
                return
        else: # stopwatch
            self.timer_seconds += elapsed

        self.last_tick = now
        
        # Only update the label, avoid full refresh
        self.timer_lbl.configure(text=format_seconds_to_hms(int(self.timer_seconds)))
        
        # Zen Mode Update
        if getattr(self, "zen_active", False) and hasattr(self, "zen_lbl"):
             self.zen_lbl.configure(text=format_seconds_to_hms(int(self.timer_seconds)))
        
        # Pomodoro Check (Stopwatch Only)
        if style == "stopwatch" and not getattr(self, "pomodoro_target_reached", False):
            pom = get_pomodoro_settings(self.data)
            target_sec = pom.get("work", 25) * 60
            if self.timer_seconds >= target_sec:
                self.pomodoro_target_reached = True
                self.sound_mgr.play("success") 
                # Visual cue
                self.timer_lbl.configure(text_color=COLORS["success"])
                if getattr(self, "zen_active", False):
                    self.zen_lbl.configure(text_color=COLORS["success"])
        
        # Periodic autosave/sync could go here, but we'll log on stop to be accurate.
        # Previously mixed incremental logging was buggy.
        
        self.after(1000, self.update_timer)

    def toggle_timer(self):
        if self.timer_running:
            self.pause_timer()
        else:
            self.start_timer()

    def start_timer(self):
        # Countdown Init Logic
        style = self.data.get("settings", {}).get("timer_style", "stopwatch")
        
        if style == "countdown" and self.timer_seconds <= 0:
            # Load default duration
            pom = get_pomodoro_settings(self.data)
            self.timer_seconds = pom.get("work", 25) * 60
            self.timer_max = self.timer_seconds # For progress bar if we had one
            
        self.timer_running = True
        self.last_tick = datetime.now()
        self.timer_ctrl.configure(text="⏸ Pause", fg_color=COLORS["warning"])
        self.stop_btn.configure(state="normal") # Enable stop
        
        # Reset target state for Pomodoro check (Stopwatch mode only)
        self.pomodoro_target_reached = False
        
        # Update Label Mode
        lbl = "⏱ Stopwatch" if style == "stopwatch" else "⏳ Timer"
        if self.timer_mode_lbl.cget("text") != lbl and "Class" not in self.timer_mode_lbl.cget("text"):
             self.timer_mode_lbl.configure(text=lbl)
             
        self.update_timer()

    def pause_timer(self):
        self.timer_running = False
        self.last_tick = None
        self.timer_ctrl.configure(text="▶ Resume", fg_color=COLORS["success"])

    def stop_timer(self, log=False):
        self.timer_running = False
        if log and self.timer_seconds > 5:
            if self.timer_mode == "class" and self.active_class_id:
                log_class_session(self.data, self.timer_seconds, self.active_class_id)
                log_focus_session(self.data, self.timer_seconds, session_type="class")
            else:
                log_focus_session(self.data, self.timer_seconds, session_type="focus")
            self.refresh_xp()
        
        self.timer_seconds = 0
        clear_timer_state(self.data) # Logic Clear
        
        self.timer_lbl.configure(text="00:00:00")
        self.timer_ctrl.configure(text="▶ Start", fg_color=COLORS["success"])
        self.stop_btn.configure(state="disabled") # Disable instead of hide
        self.last_tick = None

    def toggle_zen_mode(self):
        self.zen_active = not getattr(self, "zen_active", False)
        
        if self.zen_active:
             # Save current geometry before Zen
             self.last_geometry = self.geometry()
             
             # Enter Zen
             self.geometry("300x130")
             self.overrideredirect(True)
             self.attributes("-topmost", True)
             
             # Hide Main UI
             self.sidebar.grid_remove()
             self.main_container.grid_remove()
             
             # Show Zen Frame
             self.zen_frame = ctk.CTkFrame(self, fg_color=COLORS["bg"])
             self.zen_frame.pack(fill="both", expand=True)
             
             # Header (Drag Handle)
             header = ctk.CTkFrame(self.zen_frame, fg_color="transparent", height=30)
             header.pack(fill="x")
             header.bind("<Button-1>", self.start_move)
             header.bind("<B1-Motion>", self.do_move)
             ctk.CTkLabel(header, text="🧘 Zen Focus", font=FONTS["small"]).pack(side="left", padx=10)
             ctk.CTkButton(header, text="✕", width=30, height=20, fg_color="transparent", 
                           text_color=COLORS["error"], command=self.toggle_zen_mode).pack(side="right", padx=5)
             
             # Timer
             self.zen_lbl = ctk.CTkLabel(self.zen_frame, text=format_seconds_to_hms(int(self.timer_seconds)), 
                                         font=("Arial", 36, "bold"), text_color=COLORS["text"])
             self.zen_lbl.pack(pady=(5, 10))
             
             # Controls
             ctrls = ctk.CTkFrame(self.zen_frame, fg_color="transparent")
             ctrls.pack()
             
             icon = "⏸" if self.timer_running else "▶"
             col = COLORS["warning"] if self.timer_running else COLORS["success"]
             
             self.zen_btn = ctk.CTkButton(ctrls, text=icon, width=60, height=30, fg_color=col,
                                          command=self.zen_toggle_timer)
             self.zen_btn.pack(side="left", padx=5)
             
             ctk.CTkButton(ctrls, text="⏹", width=40, height=30, fg_color=COLORS["error"],
                           command=lambda: self.stop_timer(log=True)).pack(side="left", padx=5)
             
        else:
             # Exit Zen
             if hasattr(self, 'zen_frame'): self.zen_frame.destroy()
             self.overrideredirect(False)
             self.attributes("-topmost", False)
             
             # Restore previous geometry or default to center
             if hasattr(self, 'last_geometry'):
                 self.geometry(self.last_geometry)
             else:
                 self.center_window()
                 
             self.sidebar.grid()
             self.main_container.grid()

    def center_window(self, scale=0.85):
        """Dynamic window sizing based on screen resolution."""
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        w = int(screen_width * scale)
        h = int(screen_height * scale)
        x = int((screen_width - w) / 2)
        y = int((screen_height - h) / 2)
        
        self.geometry(f"{w}x{h}+{x}+{y}")

    def zen_toggle_timer(self):
        self.toggle_timer()
        # Update button icon
        icon = "⏸" if self.timer_running else "▶"
        col = COLORS["warning"] if self.timer_running else COLORS["success"]
        self.zen_btn.configure(text=icon, fg_color=col)

    def start_move(self, event):
        self.x_start = event.x
        self.y_start = event.y

    def do_move(self, event):
        x = self.winfo_x() + event.x - self.x_start
        y = self.winfo_y() + event.y - self.y_start
        self.geometry(f"+{x}+{y}")

def run_app():
    app = FocusApp()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        print("\nGoodbye! 👋")
        try:
            # Try to save state if needed
            if app.timer_seconds > 0:
                # Save persistence instead of stopping
                # Mode might be focus or class
                update_timer_state(app.data, app.timer_seconds, app.timer_mode, app.active_class_id)
                print(f"Saved timer state: {app.timer_seconds}s")
        except:
            pass

if __name__ == "__main__":
    run_app()
