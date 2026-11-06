"""views_routine - split from ui.py (Focus Agent V2, Phase 6)."""

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
from .widgets import TimePicker, DaySelector, Tooltip
from .dialogs import ModernFileSelector, RoutineReviewDialog


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
        grid.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        grid.grid_rowconfigure(1, weight=1)

        days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        today_day = datetime.now().strftime("%a").lower()[:3]
        weekly = get_weekly_class_tasks(self.app.data)
        for i, d in enumerate(days):
            grid.grid_columnconfigure(i, weight=1, uniform="days")
            is_today = (d == today_day)
            hdr_bg = COLORS["accent"] if is_today else COLORS["card"]
            hdr_fg = "white" if is_today else COLORS["text"]

            day_header = ctk.CTkFrame(
                grid, fg_color=hdr_bg, height=34, corner_radius=8,
                border_width=0 if is_today else 1, border_color=COLORS["border"]
            )
            day_header.grid(row=0, column=i, sticky="ew", padx=3, pady=2)
            day_header.grid_propagate(False)
            hdr_txt = f"{d.upper()} •" if is_today else d.upper()
            ctk.CTkLabel(day_header, text=hdr_txt, font=FONTS["small"], text_color=hdr_fg).pack(expand=True)

            day_content = ctk.CTkScrollableFrame(
                grid, fg_color=COLORS["bg_secondary"], corner_radius=8,
                border_width=1, border_color=COLORS["accent_light"] if is_today else COLORS["border"],
                scrollbar_button_color=COLORS["border"]
            )
            day_content.grid(row=1, column=i, sticky="nsew", padx=3, pady=2)
            self.day_containers[d] = day_content  # Store for silent add

            classes = weekly.get(d, [])
            classes.sort(key=lambda x: x.get("schedule", {}).get("start", ""))

            for c in classes:
                self._draw_class_card(day_content, c)

    def _draw_class_card(self, parent, c):
        """Draw a single class card and register it."""
        sch = c.get("schedule", {})
        cls_card = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=6)
        cls_card.pack(fill="x", pady=3, padx=2)
        
        # simple store for callback
        cls_card._class_id = c["id"]
        
        # Register in class_cards list (one class can be on multiple days)
        if c["id"] not in self.class_cards:
            self.class_cards[c["id"]] = []
        self.class_cards[c["id"]].append(cls_card)
        
        # Class info
        time_lbl = ctk.CTkLabel(cls_card, text=f"{sch.get('start','')}–{sch.get('end','')}", 
                        font=FONTS["tiny"], text_color=COLORS["warning"])
        time_lbl.pack(pady=(4, 0), padx=2)
        
        title_lbl = ctk.CTkLabel(cls_card, text=c["title"], 
                        font=FONTS["small"], text_color=COLORS["accent"],
                        wraplength=95, justify="center")
        title_lbl.pack(padx=3, pady=1)
        
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
        top.geometry("450x450")
        top.after(100, lambda: top.focus())
        
        sch = task.get("schedule", {})
        
        ctk.CTkLabel(top, text="Class Name:", font=FONTS["body"]).pack(pady=(15, 5))
        name_e = ctk.CTkEntry(top, width=350)
        name_e.insert(0, task["title"])
        name_e.pack(pady=5)
        
        ctk.CTkLabel(top, text="Select Days:", font=FONTS["body"]).pack(pady=(10, 5))
        day_sel = DaySelector(top, initial_days=sch.get("days", []))
        day_sel.pack(pady=5)
        
        ctk.CTkLabel(top, text="Start Time:", font=FONTS["body"]).pack(pady=(10, 5))
        start_p = TimePicker(top, sch.get("start", "09:00"))
        start_p.pack(pady=5)
        
        ctk.CTkLabel(top, text="End Time:", font=FONTS["body"]).pack(pady=(10, 5))
        end_p = TimePicker(top, sch.get("end", "10:30"))
        end_p.pack(pady=5)
        
        def save():
            new_title = name_e.get().strip()
            new_days = day_sel.get()
            new_start = start_p.get()
            new_end = end_p.get()
            
            if not new_title or not new_days:
                messagebox.showwarning("Error", "Name and at least one day required.")
                return
            
            # Update data
            old_days = sch.get("days", [])
            task["title"] = new_title
            task["schedule"] = {"days": new_days, "start": new_start, "end": new_end}
            save_data(self.app.data)
            
            # Silent Update UI
            if set(new_days) != set(old_days):
                self.delete_class_silent_ui_only(class_id)
                for day in new_days:
                    if day in self.day_containers:
                        self._draw_class_card(self.day_containers[day], task)
            else:
                if class_id in self.class_cards:
                    for card in self.class_cards[class_id]:
                        if hasattr(card, "_title_lbl"): card._title_lbl.configure(text=new_title)
                        if hasattr(card, "_time_lbl"): card._time_lbl.configure(text=f"{new_start}–{new_end}")
            
            top.destroy()
        
        ctk.CTkButton(top, text="Save Changes", fg_color=COLORS["success"], command=save, height=40).pack(pady=20)

    def on_resize(self, width, height):
        col_wrap = max(65, int((width - 60) / 7) - 18)
        for cards in self.class_cards.values():
            for card in cards:
                if hasattr(card, "_title_lbl") and card._title_lbl:
                    card._title_lbl.configure(wraplength=col_wrap)
    
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
        top.geometry("650x600")
        top.after(100, lambda: top.focus())
        
        ctk.CTkLabel(top, text="📥 Import your schedule", font=FONTS["header"]).pack(pady=(15, 5))
        ctk.CTkLabel(top, text="AI will automatically detect classes, days, and times", 
                     font=FONTS["small"], text_color=COLORS["text_dim"]).pack(pady=(0, 5))
        
        # Option Frame for Buttons
        btn_frame = ctk.CTkFrame(top, fg_color="transparent")
        btn_frame.pack(pady=10)

        ctk.CTkButton(btn_frame, text="📷 Import from Image", fg_color=COLORS["card"],
                      hover_color=COLORS["card_hover"], height=36,
                      command=lambda: self.import_from_image(top, status_lbl)).pack(side="left", padx=5)

        # Space for paste
        ctk.CTkLabel(top, text="OR Paste Text Below:", font=FONTS["small"], text_color=COLORS["text_dim"]).pack(pady=(10, 0))

        # Option to clear existing
        clear_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(top, text="Clear existing classes before import", 
                        variable=clear_var, font=FONTS["small"]).pack(pady=5)
        
        txt = ctk.CTkTextbox(top, font=FONTS["body"], height=250)
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
            if not content.strip():
                messagebox.showwarning("Error", "Please paste some text first!")
                return

            status_lbl.configure(text="🔄 Parsing with AI...")
            top.update()
            
            count = self.parse_schedule_ai(content)
            top.destroy()
            if count > 0:
                messagebox.showinfo("Success", f"✅ Imported {count} classes!")
            else:
                messagebox.showwarning("No Classes Found", "Could not detect any classes. Try a clearer format.")
        
        ctk.CTkButton(top, text="🤖 Import Text with AI", fg_color=COLORS["accent"],
                      hover_color=COLORS["accent_dark"], height=40,
                      command=parse_and_import).pack(pady=15)

    def import_from_image(self, top_window, status_lbl):
        """Handle image selection via ModernFileSelector and OCR import."""
        
        def on_file_picked(file_path):
            if not file_path: return
            
            # Use top_window for status update
            try:
                import os
                if os.environ.get("GEMINI_API_KEY"):
                    status_lbl.configure(text="✨ AI Visual Analysis (Gemini Flash)...", text_color=COLORS["accent"])
                else:
                    status_lbl.configure(text="📷 Reading image (OCR + Groq)...", text_color=COLORS["text_dim"])
                top_window.update()
            except: pass

            try:
                from focus_agent.media_import import parse_file_with_ai
                result = parse_file_with_ai(file_path)
                
                if result.get("intent") == "schedule_file" and "classes" in result:
                    classes = result["classes"]
                    try: top_window.destroy() 
                    except: pass

                    def handle_final_import(final_classes):
                        count = 0
                        for c in final_classes:
                            if c["title"].strip() and c["days"]:
                                self._add_or_update_class(
                                    c["title"],
                                    c["days"],
                                    c["start"],
                                    c["end"]
                                )
                                count += 1
                        messagebox.showinfo("Success", f"✅ Successfully imported {count} classes to your routine!")

                    # Open the modern Review Dialog
                    RoutineReviewDialog(self.winfo_toplevel(), classes, handle_final_import)
                else:
                    msg = result.get("message", "No clear schedule found in image.")
                    try: status_lbl.configure(text="❌ Import failed.")
                    except: pass
                    messagebox.showwarning("Import Failed", msg)
            except Exception as e:
                try: status_lbl.configure(text="❌ Error processing image.")
                except: pass
                messagebox.showerror("Error", f"Failed to process image: {str(e)}")

        # Open the Modern File Selector
        ModernFileSelector(self.winfo_toplevel(), on_file_picked)

    def parse_schedule_ai(self, text):
        """Parse schedule using V2 routine parser."""
        from focus_agent.media_import import parse_routine_text
        classes = parse_routine_text(text)
        count = 0
        for c in classes:
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
        top.geometry("450x520")
        top.after(100, lambda: top.focus())
        
        ctk.CTkLabel(top, text="Class Name:", font=FONTS["body"]).pack(pady=(15, 5))
        name_e = ctk.CTkEntry(top, width=350)
        name_e.pack(pady=5)
        
        ctk.CTkLabel(top, text="Select Days:", font=FONTS["body"]).pack(pady=(10, 5))
        day_sel = DaySelector(top)
        day_sel.pack(pady=5)
        
        ctk.CTkLabel(top, text="Start Time:", font=FONTS["body"]).pack(pady=(10, 5))
        start_p = TimePicker(top, "09:00")
        start_p.pack(pady=5)
        
        ctk.CTkLabel(top, text="End Time:", font=FONTS["body"]).pack(pady=(10, 5))
        end_p = TimePicker(top, "10:30")
        end_p.pack(pady=5)
        
        def save():
            name = name_e.get().strip()
            days = day_sel.get()
            start = start_p.get()
            end = end_p.get()
            
            if name and days:
                new_class = add_task_logic(
                    self.app.data,
                    title=name,
                    category="class",
                    schedule={"days": days, "start": start, "end": end},
                    subject=name
                )
                if new_class:
                    for day in days:
                        if day in self.day_containers:
                            self._draw_class_card(self.day_containers[day], new_class)
            top.destroy()
        
        ctk.CTkButton(top, text="Add Class", fg_color=COLORS["accent"],
                      command=save, height=40).pack(pady=20)
