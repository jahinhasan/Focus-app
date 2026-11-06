"""dialogs - split from ui.py (Focus Agent V2, Phase 6)."""

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
from .widgets import TimePicker, DaySelector


class ModernFileSelector(ctk.CTkToplevel):
    """A premium, card-based gallery selector for an ultra-modern experience."""
    def __init__(self, parent, on_file_selected):
        super().__init__(parent)
        self.title("Routine Scanner")
        self.geometry("800x650")
        self.on_file_selected = on_file_selected
        self.configure(fg_color=COLORS["bg"])
        
        # Safe lifecycle management
        self.transient(parent)
        try: self.grab_set()
        except: pass
        
        self.images = [] # Keep refs to prevent GC
        self.render()
        self.after(100, lambda: self.focus())

    def find_recent_images(self):
        """Find recent images in common folders."""
        import os
        paths = [
            os.path.expanduser("~/Downloads"),
            os.path.expanduser("~/Pictures"),
            os.path.expanduser("~/Desktop"),
            os.getcwd()
        ]
        found = []
        for p in paths:
            if os.path.exists(p) and os.path.isdir(p):
                try:
                    for f in os.listdir(p):
                        if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                            full_path = os.path.join(p, f)
                            if os.path.isfile(full_path):
                                found.append(full_path)
                except Exception as e:
                    print(f"Error listing {p}: {e}")
        
        # Sort by modification time safely
        def get_mtime_safe(x):
            try: return os.path.getmtime(x)
            except: return 0
            
        found.sort(key=get_mtime_safe, reverse=True)
        return found[:15]

    def render(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=40, pady=(30, 5))
        
        ctk.CTkLabel(header, text="✨ Routine Scanner", font=FONTS["title"], text_color=COLORS["accent"]).pack(side="left")
        ctk.CTkLabel(header, text="Select or Browse", font=FONTS["small"], text_color=COLORS["text_dim"]).pack(side="right", pady=(10, 0))

        # Folder Filters
        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=40, pady=(10, 10))
        
        folders = [("Downloads", "~/Downloads"), ("Pictures", "~/Pictures"), ("Project", "."), ("Desktop", "~/Desktop")]
        for name, path in folders:
            btn = ctk.CTkButton(filter_frame, text=name, width=80, height=26, corner_radius=15,
                                fg_color=COLORS["card"], text_color=COLORS["text"],
                                font=FONTS["tiny"], hover_color=COLORS["accent"],
                                command=lambda p=path: self.refresh_gallery(p))
            btn.pack(side="left", padx=5)

        # Gallery Section
        self.gallery_container = ctk.CTkScrollableFrame(self, orientation="horizontal", height=220, fg_color="transparent")
        self.gallery_container.pack(fill="x", padx=40)
        
        self.refresh_gallery() # Initial load

        # Drop Zone / Browse
        browse_card = ctk.CTkFrame(self, fg_color=COLORS["sidebar"], corner_radius=15, border_width=1, border_color=COLORS["border"])
        browse_card.pack(fill="x", padx=40, pady=20)
        
        ctk.CTkLabel(browse_card, text="Can't find it in the gallery? Use the system browser.", 
                     font=FONTS["small"]).pack(pady=(15, 5))
        
        btn_browse = ctk.CTkButton(browse_card, text="📁 Open File Browser", height=36, width=180,
                                   fg_color=COLORS["card"], border_width=1, border_color=COLORS["accent"],
                                   corner_radius=10, font=FONTS["small"],
                                   command=self.open_system_picker)
        btn_browse.pack(pady=(0, 15))

    def refresh_gallery(self, filter_path=None):
        """Update gallery with images from filters or all recents."""
        for child in self.gallery_container.winfo_children():
            child.destroy()
        
        self.images = [] # Clear old refs
        
        import os
        if filter_path:
            full_path = os.path.expanduser(filter_path) if filter_path.startswith("~") else os.path.abspath(filter_path)
            recents = []
            if os.path.exists(full_path):
                try:
                    for f in os.listdir(full_path):
                        if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                            recents.append(os.path.join(full_path, f))
                except: pass
            recents.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            recents = recents[:15]
        else:
            recents = self.find_recent_images()

        if not recents:
            ctk.CTkLabel(self.gallery_container, text="No images found here.", 
                         font=FONTS["small"], text_color=COLORS["text_dim"]).pack(pady=80, padx=250)
        
        for img_path in recents:
            self.draw_image_card(self.gallery_container, img_path)

    def draw_image_card(self, parent, path):
        """Draw a thumbnail card for an image."""
        import os
        from PIL import Image
        
        fname = os.path.basename(path)
        card = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=12, width=160, height=200)
        card.pack(side="left", padx=10)
        card.pack_propagate(False)
        
        try:
            pil_img = Image.open(path)
            pil_img.thumbnail((140, 120))
            img = ctk.CTkImage(light_image=pil_img, size=pil_img.size)
            self.images.append(img) # Keep alive
            
            img_lbl = ctk.CTkLabel(card, image=img, text="")
            img_lbl.pack(pady=(10, 5))
            # Bind click
            img_lbl.bind("<Button-1>", lambda e: self.select_and_close(path))
            card.bind("<Button-1>", lambda e: self.select_and_close(path))
        except Exception as e:
            ctk.CTkLabel(card, text="🖼️", font=("Inter", 32)).pack(pady=(40, 10))
            print(f"Error loading thumbnail {path}: {e}")

        name_lbl = ctk.CTkLabel(card, text=fname[:15] + "..." if len(fname) > 15 else fname, 
                                font=FONTS["tiny"], text_color=COLORS["text_dim"])
        name_lbl.pack()
        
        btn = ctk.CTkButton(card, text="Select", height=24, fg_color="transparent", 
                            border_width=1, border_color=COLORS["accent"], font=FONTS["tiny"],
                            command=lambda: self.select_and_close(path))
        btn.pack(pady=10)

    def select_and_close(self, path):
        self.on_file_selected(path)
        self.destroy()

    def open_system_picker(self):
        from tkinter import filedialog
        try: self.grab_release()
        except: pass
        file_path = filedialog.askopenfilename(parent=self, title="Locate Routine Image",
                                                filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp")])
        if file_path:
            self.select_and_close(file_path)
        else:
            try: self.grab_set()
            except: pass

class RoutineReviewDialog(ctk.CTkToplevel):
    """Modern dialog to review and edit extracted routine classes."""
    def __init__(self, parent, extracted_classes, on_confirm):
        super().__init__(parent)
        self.title("Verify Routine Classes")
        self.geometry("700x800")
        self.on_confirm = on_confirm
        self.class_data = extracted_classes
        self.cards = []
        
        self.render()
        self.after(100, lambda: self.focus())

    def render(self):
        # Clear existing
        for w in self.winfo_children(): w.destroy()
        
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkLabel(header, text="✨ Review Extracted Classes", font=FONTS["header"]).pack(side="left")
        ctk.CTkLabel(header, text=f"{len(self.class_data)} Found", font=FONTS["small"], 
                     text_color=COLORS["accent"]).pack(side="right")

        # Scrollable area
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["sidebar"])
        self.scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        if not self.class_data:
            ctk.CTkLabel(self.scroll, text="No classes detected in this image.", font=FONTS["body"]).pack(pady=50)

        for i, class_item in enumerate(self.class_data):
            self.draw_review_card(i, class_item)

        # Footer
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkButton(footer, text="Discard", fg_color=COLORS["card"], 
                      text_color=COLORS["error"], command=self.destroy).pack(side="left", padx=10)
        
        ctk.CTkButton(footer, text="Import All Classes", fg_color=COLORS["accent"],
                      height=45, font=FONTS["subheader"],
                      command=self.confirm).pack(side="right", expand=True, fill="x", padx=10)

    def draw_review_card(self, index, data):
        card = ctk.CTkFrame(self.scroll, fg_color=COLORS["card"], corner_radius=10)
        card.pack(fill="x", pady=10, padx=5)
        
        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=15, pady=(10, 5))
        
        name_var = ctk.StringVar(value=data.get("title", "Class"))
        ctk.CTkEntry(top_row, textvariable=name_var, font=FONTS["subheader"], 
                     width=350, border_width=0, fg_color="transparent").pack(side="left")
        
        ctk.CTkButton(top_row, text="✕", width=24, height=24, fg_color="transparent",
                      text_color=COLORS["text_dim"], hover_color=COLORS["error"],
                      command=lambda i=index: self.remove_card(i)).pack(side="right")

        mid_row = ctk.CTkFrame(card, fg_color="transparent")
        mid_row.pack(fill="x", padx=15, pady=5)
        
        day_sel = DaySelector(mid_row, initial_days=data.get("days", []))
        day_sel.pack(side="left")

        bot_row = ctk.CTkFrame(card, fg_color="transparent")
        bot_row.pack(fill="x", padx=15, pady=(5, 10))
        
        ctk.CTkLabel(bot_row, text="⏰", font=FONTS["body"]).pack(side="left", padx=(0, 5))
        start_p = TimePicker(bot_row, data.get("start", "09:00"))
        start_p.pack(side="left", padx=5)
        
        ctk.CTkLabel(bot_row, text="to", font=FONTS["small"]).pack(side="left", padx=5)
        end_p = TimePicker(bot_row, data.get("end", "10:30"))
        end_p.pack(side="left", padx=5)
        
        # Store refs for confirm
        self.cards.append({
            "name_var": name_var,
            "day_sel": day_sel,
            "start_p": start_p,
            "end_p": end_p,
            "card_widget": card,
            "active": True
        })

    def remove_card(self, index):
        self.cards[index]["card_widget"].destroy()
        self.cards[index]["active"] = False

    def confirm(self):
        final_list = []
        for c in self.cards:
            if c.get("active", True):
                final_list.append({
                    "title": c["name_var"].get(),
                    "days": c["day_sel"].get(),
                    "start": c["start_p"].get(),
                    "end": c["end_p"].get()
                })
        self.on_confirm(final_list)
        self.destroy()
