"""theme - split from ui.py (Focus Agent V2, Phase 6)."""

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


COLORS = {
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
