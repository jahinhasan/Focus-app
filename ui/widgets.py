"""widgets - split from ui.py (Focus Agent V2, Phase 6)."""

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
from .theme import COLORS, FONTS, get_color_str


class TimePicker(ctk.CTkFrame):
    """Improved time picker with side-by-side spinbox-like behavior."""
    def __init__(self, parent, initial="09:00"):
        super().__init__(parent, fg_color="transparent")
        try:
            h, m = initial.split(":")
        except:
            h, m = "09", "00"
            
        self.hour_var = ctk.StringVar(value=h)
        self.min_var = ctk.StringVar(value=m)

        # Hours
        ctk.CTkLabel(self, text="H:", font=FONTS["tiny"]).pack(side="left", padx=2)
        self.h_menu = ctk.CTkOptionMenu(self, variable=self.hour_var, width=65, height=28,
                          values=[f"{i:02}" for i in range(24)], dynamic_resizing=False)
        self.h_menu.pack(side="left", padx=2)
        
        # Separator
        ctk.CTkLabel(self, text=":", font=FONTS["subheader"]).pack(side="left")
        
        # Minutes
        ctk.CTkLabel(self, text="M:", font=FONTS["tiny"]).pack(side="left", padx=2)
        self.m_menu = ctk.CTkOptionMenu(self, variable=self.min_var, width=65, height=28,
                          values=[f"{i:02}" for i in range(0, 60, 5)], dynamic_resizing=False)
        self.m_menu.pack(side="left", padx=2)

    def get(self):
        return f"{self.hour_var.get()}:{self.min_var.get()}"

class DaySelector(ctk.CTkFrame):
    """Multi-select toggle buttons for days of the week."""
    def __init__(self, parent, initial_days=None):
        super().__init__(parent, fg_color="transparent")
        self.days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        self.selected_days = {d: ctk.BooleanVar(value=(d in initial_days) if initial_days else False) for d in self.days}
        self.buttons = {}
        
        for d in self.days:
            btn = ctk.CTkButton(
                self, text=d.upper(), width=40, height=32,
                fg_color=COLORS["card"] if not self.selected_days[d].get() else COLORS["accent"],
                text_color=COLORS["text"] if not self.selected_days[d].get() else "white",
                hover_color=COLORS["accent"],
                command=lambda day=d: self.toggle_day(day)
            )
            btn.pack(side="left", padx=2)
            self.buttons[d] = btn

    def toggle_day(self, day):
        val = not self.selected_days[day].get()
        self.selected_days[day].set(val)
        if val:
            self.buttons[day].configure(fg_color=COLORS["accent"], text_color="white")
        else:
            self.buttons[day].configure(fg_color=COLORS["card"], text_color=COLORS["text"])

    def get(self):
        return [d for d, var in self.selected_days.items() if var.get()]

# ==================== COMPONENTS ====================

class SidebarButton(ctk.CTkButton):
    """Responsive sidebar navigation button that ALWAYS keeps icon + readable label visible."""
    def __init__(self, parent, text, command, short_text=None, **kwargs):
        self._is_active = False
        self.full_text = text
        self.short_text = short_text or text
        super().__init__(
            parent,
            text=text,
            command=command,
            fg_color="transparent",
            text_color=COLORS["text_dim"],
            hover_color=COLORS["card_hover"],
            anchor="w",
            font=FONTS["body"],
            height=36,
            corner_radius=10,
            **kwargs
        )

    def set_responsive_mode(self, compact_text=False, btn_height=36):
        """Adapt button label (full vs concise) and height while always keeping icon + name visible."""
        label_to_use = self.short_text if compact_text else self.full_text
        font_to_use = FONTS["small"] if compact_text else FONTS["body"]
        self.configure(
            text=label_to_use,
            anchor="w",
            height=btn_height,
            font=font_to_use,
        )
    
    def _on_enter(self, event=None):
        super()._on_enter(event)
        if not self._is_active:
            self.configure(text_color=COLORS["text"])
    
    def _on_leave(self, event=None):
        super()._on_leave(event)
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
        self.tooltip.configure(bg=get_color_str("card"))
        
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
    """Enhanced top status bar with Level badge, XP bar, Focus stats, Streak, and Theme toggle."""
    def __init__(self, parent, data, app=None):
        super().__init__(parent, fg_color="transparent")
        self.data = data
        self.app = app
        self._compact = False
        self.render()

    def render(self):
        for w in self.winfo_children(): w.destroy()

        self.container = ctk.CTkFrame(
            self, fg_color=COLORS["card"], corner_radius=12,
            border_width=1, border_color=COLORS["border"]
        )
        self.container.pack(fill="x", padx=14, pady=(8, 4))
        
        inner = ctk.CTkFrame(self.container, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=7)

        lvl = self.data.get("level", 1)
        
        # 1. Left: Level Badge
        badge_frame = ctk.CTkFrame(inner, fg_color=COLORS["accent"], corner_radius=8, height=30)
        badge_frame.pack(side="left")
        ctk.CTkLabel(badge_frame, text=f"⭐ LVL {lvl}", text_color="white",
                     font=FONTS["small"]).pack(padx=10, pady=4)

        # 2. Right-side fixed items packed BEFORE expanding progress bar so they are never clipped
        mode = ctk.get_appearance_mode()
        theme_label = "🌙 Dark" if mode == "Light" else "☀️ Light"
        self.theme_btn = ctk.CTkButton(
            inner, text=theme_label, width=72, height=28, corner_radius=8,
            fg_color=COLORS["bg_secondary"], hover_color=COLORS["card_hover"],
            text_color=COLORS["text"], font=FONTS["small"],
            command=self._toggle_theme
        )
        self.theme_btn.pack(side="right", padx=(6, 0))

        focus_stats = get_today_focus_stats(self.data)
        self._focus_mins = int((focus_stats.get("total_seconds", 0) + focus_stats.get("class_seconds", 0)) // 60)
        focus_badge = ctk.CTkFrame(inner, fg_color=COLORS["card_highlight"], corner_radius=8)
        focus_badge.pack(side="right", padx=4)
        focus_txt = f"⏱ {self._focus_mins}m" if self._compact else f"⏱ {self._focus_mins}m today"
        self.focus_lbl = ctk.CTkLabel(focus_badge, text=focus_txt, text_color=COLORS["accent"],
                                      font=FONTS["small"])
        self.focus_lbl.pack(padx=10, pady=4)
        
        streak = self.data.get("streak", 0)
        if streak > 0:
            streak_badge = ctk.CTkFrame(inner, fg_color=COLORS["warning"], corner_radius=8)
            streak_badge.pack(side="right", padx=4)
            ctk.CTkLabel(streak_badge, text=f"🔥 {streak}d", text_color="white",
                        font=FONTS["small"]).pack(padx=8, pady=4)

        curr, req, pct = get_level_progress(self.data)
        self.xp_text = ctk.CTkLabel(inner, text=f"{curr}/{req} XP", text_color=COLORS["text_dim"],
                                    font=FONTS["small"])
        self.xp_text.pack(side="right", padx=(0, 8))

        # 3. Middle: Expanding Progress Bar (fills remaining space cleanly)
        progress_container = ctk.CTkFrame(inner, fg_color="transparent")
        progress_container.pack(side="left", fill="x", expand=True, padx=12)

        self.progress_bar = ctk.CTkProgressBar(
            progress_container, 
            fg_color=COLORS["bg_secondary"],
            progress_color=COLORS["accent"],
            height=10,
            corner_radius=5
        )
        self.progress_bar.set(max(0.02, min(1.0, pct / 100)))
        self.progress_bar.pack(fill="x")

    def on_resize(self, content_width):
        compact = content_width < 620
        if compact != self._compact:
            self._compact = compact
            if hasattr(self, "focus_lbl") and self.focus_lbl.winfo_exists():
                self.focus_lbl.configure(
                    text=f"⏱ {self._focus_mins}m" if compact else f"⏱ {self._focus_mins}m today"
                )

    def _toggle_theme(self):
        new_mode = "Dark" if ctk.get_appearance_mode() == "Light" else "Light"
        ctk.set_appearance_mode(new_mode)
        self.data.setdefault("settings", {})["theme"] = new_mode
        save_data(self.data)
        self.render()
        if self.app and self.app.active_view in self.app.views:
            try:
                self.app.views[self.app.active_view].render()
            except Exception:
                pass


# ==================== VIEWS ====================
