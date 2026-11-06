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
# ==================== CONFIG ====================
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# Refined Academic Alabaster & Slate-Indigo Palette (Light, Dark)
COLORS = {
    "bg": ("#F4F6FB", "#0B0F19"),
    "bg_secondary": ("#EAF0F8", "#111827"),
    "sidebar": ("#FFFFFF", "#111827"),
    "card": ("#FFFFFF", "#1E293B"),
    "card_hover": ("#F1F5F9", "#283548"),
    "card_highlight": ("#EEF2FF", "#1E1B4B"),
    "accent": ("#4F46E5", "#6366F1"),
    "accent_light": ("#6366F1", "#818CF8"),
    "accent_dark": ("#4338CA", "#4F46E5"),
    "accent_hover": ("#4338CA", "#4F46E5"),
    "success": ("#059669", "#10B981"),
    "success_dark": ("#047857", "#059669"),
    "warning": ("#D97706", "#F59E0B"),
    "warning_dark": ("#B45309", "#D97706"),
    "error": ("#DC2626", "#EF4444"),
    "text": ("#0F172A", "#F8FAFC"),
    "text_dim": ("#475569", "#94A3B8"),
    "text_muted": ("#64748B", "#64748B"),
    "border": ("#E2E8F0", "#334155"),
    "border_light": ("#F1F5F9", "#1E293B"),
    "glass": ("#FFFFFF", "#1E293B"),
    "glow": ("#EEF2FF", "#1E1B4B"),
}

def get_color_str(key):
    """Helper to get hex string from COLORS[key] based on current mode."""
    val = COLORS.get(key)
    if not val: return "#0F172A"
    if isinstance(val, tuple):
        return val[0] if ctk.get_appearance_mode() == "Light" else val[1]
    return val

BASE_FONT_SPECS = {
    "title": ("Inter", 22, "bold"),
    "header": ("Inter", 15, "bold"),
    "subheader": ("Inter", 13, "bold"),
    "body": ("Inter", 12, "normal"),
    "small": ("Inter", 11, "normal"),
    "tiny": ("Inter", 10, "normal"),
    "clock": ("Inter", 30, "bold"),
    "timer": ("Inter", 22, "bold"),
    "kpi": ("Inter", 20, "bold"),
    "brand": ("Inter", 17, "bold"),
}

# Initial tuple fallback before Tk root exists; upgraded in-place to reactive CTkFont objects by init_responsive_fonts()
FONTS = {
    k: (fam, sz, wt) if wt != "normal" else (fam, sz)
    for k, (fam, sz, wt) in BASE_FONT_SPECS.items()
}

_FONT_SCALE_CACHE = {"bucket": None}


def init_responsive_fonts():
    """Upgrade FONTS dictionary in-place to live CTkFont instances after root window creation."""
    for key, (family, size, weight) in BASE_FONT_SPECS.items():
        try:
            FONTS[key] = ctk.CTkFont(family=family, size=size, weight=weight)
        except Exception:
            FONTS[key] = (family, size, weight) if weight != "normal" else (family, size)


def scale_fonts_for_window(width: int, height: int):
    """Dynamically scale all CTkFont objects in FONTS based on current window dimensions."""
    if width < 820 or height < 600:
        bucket = "xs"
        scale = 0.84
    elif width < 1020 or height < 680:
        bucket = "sm"
        scale = 0.92
    elif width < 1280:
        bucket = "md"
        scale = 1.0
    else:
        bucket = "lg"
        scale = 1.10

    if _FONT_SCALE_CACHE.get("bucket") == bucket:
        return
    _FONT_SCALE_CACHE["bucket"] = bucket

    min_sizes = {
        "title": 16,
        "header": 13,
        "subheader": 12,
        "body": 11,
        "small": 10,
        "tiny": 9,
        "clock": 20,
        "timer": 16,
        "kpi": 16,
        "brand": 14,
    }
    for key, (_family, base_size, _weight) in BASE_FONT_SPECS.items():
        font_obj = FONTS.get(key)
        if hasattr(font_obj, "configure"):
            new_size = max(min_sizes.get(key, 10), int(round(base_size * scale)))
            try:
                font_obj.configure(size=new_size)
            except Exception:
                pass
