"""views_store - split from ui.py (Focus Agent V2, Phase 6)."""

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
from .theme import COLORS, FONTS


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
        
