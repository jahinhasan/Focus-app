import tkinter as tk
import time

from tkinter import ttk
from class_schedule import SCHEDULE, get_current_class

from logic import (
    load_data, toggle_subtask,
    add_task, edit_task, delete_task,
    add_subtask, edit_subtask, delete_subtask,
    get_stats
)
print("### UI.PY VERSION 999 LOADED ###")


class FocusDashboard:
    def update_current_class(self):
        cls = get_current_class(self.schedule)

        if cls:
            self.current_class_label.config(
                text=f"📘 {cls['title']}\n{cls['start']} - {cls['end']}"
            )
        else:
            self.current_class_label.config(text="No class right now")

        self.root.after(60000, self.update_current_class)

    def __init__(self, root):
        self.root = root
        self.data = load_data()
        self.overlay = False
        self.overlay_alpha = 1.0


        from logic import reset_tasks_for_new_day_if_needed
        reset_tasks_for_new_day_if_needed(self.data)


        self.view = "today"
        self.task_widgets = {}


        root.title("Focus Dashboard")
        # --- Floating focus panel startup ---
        root.attributes("-topmost", False)
        root.resizable(False, False)

        PANEL_SIZE = 1300  # perfect square-ish
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()

        x = (sw - PANEL_SIZE) // 2
        y = (sh - PANEL_SIZE) // 2

        root.geometry(f"{PANEL_SIZE}x{PANEL_SIZE}+{x}+{y}")

        # ---------- ROOT GRID LAYOUT ----------
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Top system bar (full width)
        self.top_bar = tk.Frame(self.root)
        self.top_bar.grid(row=0, column=0, sticky="ew")

        # Main content area (fills rest)
        self.main_area = tk.Frame(self.root)
        self.main_area.grid(row=1, column=0, sticky="nsew")
        self.main_area.grid_rowconfigure(0, weight=1)
        self.main_area.grid_columnconfigure(0, weight=1)
        # Right side panel
        # Right side panel
        self.side_panel = tk.Frame(self.main_area, width=450, bg="#0f1115")
        self.side_panel.grid(row=0, column=1, sticky="ns")
        self.side_panel.grid_propagate(False)

        self.main_area.grid_columnconfigure(1, weight=0)

        self.clock = BigClock(self.side_panel)
        self.clock.pack(pady=20)

        self.timer_widget = TimerWidget(self.side_panel)
        self.timer_widget.pack(pady=20)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.schedule = SCHEDULE

        self.current_class_label = tk.Label(
            self.side_panel,
            text="No class right now",
            font=("Arial", 14, "bold"),
            fg="#ff9800",
            bg="#0f1115"
        )
        self.current_class_label.pack(pady=10)

        self.update_current_class()

# ---------- WALLPAPER / CONTENT LAYER ----------
       
       
        # Center wrapper (fixed width, centered)
        self.center_wrapper = tk.Frame(self.main_area)

        self.center_wrapper.place(relx=0.5, rely=0.0, relheight=1.0, anchor="n")
        self.center_wrapper.config(width=720)
        



        self.build_header()

        # INPUT LAYER (isolated, centered)
        self.input_layer = tk.Frame(self.center_wrapper)
        self.input_layer.pack(fill="x")

        self.build_task_input()

        # BOARD LAYER (cards only)
        self.build_scroll_area()

        self.bind_mouse_wheel()

        
        self.click_through = False
        self.root.attributes("-topmost", False)

        
        root.bind("<Control-n>", lambda e: self.task_entry.focus())
        root.bind("<Control-h>", lambda e: self.switch_view(
            "history" if self.view == "today" else "today"
        ))
        self.root.bind_all("<F9>", self.toggle_overlay)

        root.bind("<Escape>", lambda e: self.toggle_overlay() if self.overlay else None)
        #root.bind("<F8>", lambda e: self.toggle_click_through())
        root.bind("<F6>", lambda e: self.change_opacity(-0.05))
       
        self.root.after(100, self.refresh_tasks)
        root.bind("<Control-r>", lambda e: self.reload())


    # ================= HEADER =================
    def build_header(self):
        # 3-column header layout
        self.top_bar.grid_columnconfigure(0, weight=0)
        self.top_bar.grid_columnconfigure(1, weight=1)
        self.top_bar.grid_columnconfigure(2, weight=0)

        # LEFT: TODAY
        left = tk.Frame(self.top_bar)
        left.grid(row=0, column=0, sticky="w", padx=12)

        tk.Label(
            left, text="🎯 TODAY",
            font=("Arial", 14, "bold")
        ).pack()

        # CENTER: LEVEL + XP
        center = tk.Frame(self.top_bar)
        center.grid(row=0, column=1)

        self.level_label = tk.Label(center, font=("Arial", 16, "bold"))
        self.level_label.pack()

        self.xp_bar = ttk.Progressbar(center, length=360, maximum=100)
        self.xp_bar.pack(pady=2)

        # RIGHT: window buttons
        right = tk.Frame(self.top_bar)
        right.grid(row=0, column=2, sticky="e", padx=12)

        
        tk.Button(right, text="—", width=3,
                command=self.root.iconify).pack(side="left")
        tk.Button(right, text="❌", width=3, fg="red",
                command=self.root.destroy).pack(side="left")
        tk.Button(
            right,
            text="🔄",
            width=3,
            command=self.reload
        ).pack(side="left", padx=4)

    def update_stats(self):
        level, xp = get_stats(self.data)
        self.level_label.config(text=f"⭐ LEVEL {level}")
        self.xp_bar["value"] = xp

    # ================= ADD TASK =================
    def build_task_input(self):
        frame = tk.Frame(self.input_layer)

        frame.pack(fill="x", padx=10, pady=5)

        self.task_entry = tk.Entry(frame)
        self.task_entry.pack(side="left", fill="x", expand=True)
        self.task_entry.bind("<Return>", lambda e: self.add_task_ui())

        tk.Button(frame, text="➕ Task",
                  command=self.add_task_ui).pack(side="right")

    def add_task_ui(self):
        add_task(self.data, self.task_entry.get())
        self.task_entry.delete(0, tk.END)
        self.refresh_tasks()

    # ================= SCROLL =================
    def build_scroll_area(self):
        # BOARD LAYER (HTML equivalent of .board)
        board_container = tk.Frame(self.center_wrapper)
        board_container.pack(fill="both", expand=True)

        self.scrollbar = tk.Scrollbar(board_container, orient="vertical")
        self.scrollbar.pack(side="left", fill="y")

        self.canvas = tk.Canvas(board_container)
        self.canvas.pack(side="right", fill="both", expand=True)

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.configure(command=self.canvas.yview)

        # BOARD FRAME (centered grid holder)
        self.board_frame = tk.Frame(self.canvas)
        self.board_window = self.canvas.create_window(
            (0, 0),
            window=self.board_frame,
            anchor="n"
        )

        # Keep board centered
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(
                self.board_window,
                width=min(680, e.width-20)
            )
        )

        self.board_frame.bind("<Configure>", self._update_scroll)
    def refresh_tasks(self):
        if self.view == "today":
            self.render_tasks()
        else:
            self.render_history()

        self.update_stats()
        self._update_scroll()

    def reload(self):
        """
        Reload data from disk and refresh the UI.
        Safe manual refresh.
        """
        self.data = load_data()
        self.refresh_tasks()

    # ================= RENDER =================
    def render_tasks(self):
        tasks = self.data.get("tasks", [])

        task_ids = {task["id"] for task in tasks}

        # Remove widgets for deleted tasks
        for tid in list(self.task_widgets.keys()):
            if tid not in task_ids:
                self.task_widgets[tid].destroy()
                del self.task_widgets[tid]

        cols = max(1, self.canvas.winfo_width() // 360)
        row = col = 0

        for task in tasks:
            tid = task["id"]

            if tid in self.task_widgets:
                self.task_widgets[tid].destroy()

            card = self.create_task_card(task)
            self.task_widgets[tid] = card

            card.grid(row=row, column=col, padx=20, pady=20, sticky="n")

            col += 1
            if col >= cols:
                col = 0
                row += 1


    def create_task_card(self, task):
        ti = self.data["tasks"].index(task)

        # TASK CARD (one self-contained layer)
        frame = tk.Frame(self.board_frame, bd=1, relief="solid", padx=10, pady=8)

        # ---- TASK HEADER ----
        header = tk.Frame(frame)
        header.pack(fill="x")

        title_lbl = tk.Label(
            header,
            text=("✔ " if task.get("done") else "⬜ ") + task.get("title", ""),
            font=("Arial", 11, "bold")
        )
        title_lbl.pack(side="left")

        def edit_task_inline():
            title_lbl.pack_forget()
            entry = tk.Entry(header)
            entry.insert(0, task.get("title", ""))
            entry.pack(side="left", fill="x", expand=True)
            entry.focus()

            tk.Button(
                header, text="✔",
                command=lambda: (
                    edit_task(self.data, ti, entry.get()),
                    self.refresh_tasks()
                )
            ).pack(side="right")

            tk.Button(
                header, text="✖",
                command=self.refresh_tasks
            ).pack(side="right")

        tk.Button(header, text="✏", command=edit_task_inline).pack(side="right")
        tk.Button(
            header, text="❌",
            command=lambda: (
                delete_task(self.data, ti),
                self.refresh_tasks()
            )
        ).pack(side="right")

        # ---- SUBTASK LIST ----
        for si, sub in enumerate(task.get("subtasks", [])):
            row = tk.Frame(frame)
            row.pack(fill="x", padx=10, pady=2)

            var = tk.BooleanVar(value=sub.get("done", False))
            tk.Checkbutton(
                row, variable=var,
                command=lambda v=var, t=ti, s=si: (
                    toggle_subtask(self.data, t, s, v.get()),
                    self.update_stats()
                )
            ).pack(side="left")

            tk.Label(row, text=sub.get("title", "")).pack(side="left")

            def edit_subtask_inline(r=row, t=ti, s=si, text=sub.get("title", "")):
                for w in r.winfo_children():
                    w.destroy()

                entry = tk.Entry(r)
                entry.insert(0, text)
                entry.pack(side="left", fill="x", expand=True)
                entry.focus()

                tk.Button(
                    r, text="✔",
                    command=lambda: (
                        edit_subtask(self.data, t, s, entry.get()),
                        self.refresh_tasks()
                    )
                ).pack(side="right")

                tk.Button(
                    r, text="✖",
                    command=self.refresh_tasks
                ).pack(side="right")

            tk.Button(row, text="✏", command=edit_subtask_inline).pack(side="right")
            tk.Button(
                row, text="❌",
                command=lambda t=ti, s=si: (
                    delete_subtask(self.data, t, s),
                    self.refresh_tasks()
                )
            ).pack(side="right")

        # ---- ADD SUBTASK ----
        add_row = tk.Frame(frame)
        add_row.pack(fill="x", padx=10, pady=5)

        entry = tk.Entry(add_row)
        entry.pack(side="left", fill="x", expand=True)

        tk.Button(
            add_row, text="➕",
            command=lambda: (
                add_subtask(self.data, ti, entry.get()),
                self.refresh_tasks()
            )
        ).pack(side="right")

        return frame


    # ================= HISTORY =================
    def render_history(self):
        
        for w in self.board_frame.winfo_children():
            w.destroy()
        
        
        history = self.data.get("history", {})

        if not history:
            tk.Label(self.board_frame, text="No history yet").grid(pady=20)
            return

        row = 0
        for day, info in sorted(history.items(), reverse=True):
            box = tk.Frame(self.board_frame, bd=1, relief="solid", padx=10, pady=8)
            box.grid(row=row, column=0, padx=20, pady=10, sticky="n")

            tk.Label(box, text=f"📅 {day}",
                    font=("Arial", 11, "bold")).pack(anchor="w")
            tk.Label(box,
                    text=f"✔ {info['completed']} / {info['total']}").pack(anchor="w", padx=10)
            tk.Label(box,
                    text=f"⭐ XP gained: {info['xp_gained']:.1f}").pack(anchor="w", padx=10)

            row += 1

        self.board_frame.grid_anchor("center")

    # ================= UTIL =================
    
    def switch_view(self, view):
        self.view = view

        if self.view == "today":
            self.render_tasks()
        else:
            self.render_history()

        self.update_stats()


  
    def toggle_click_through(self):
        self.click_through = not self.click_through

       
    def change_opacity(self, delta):
        if not self.overlay:
            return
        self.overlay_alpha = min(1.0, max(0.3, self.overlay_alpha + delta))
        self.root.attributes("-alpha", self.overlay_alpha)

    def toggle_overlay(self, event=None):
        self.overlay = not self.overlay

        if self.overlay:
            # Focus mode (compact, subtle)
            self.root.attributes("-alpha", 0.92)
            self.root.resizable(False, False)

            size = 1200
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()

            x = (sw - size) // 2
            y = (sh - size) // 2

            self.root.geometry(f"{size}x{size}+{x}+{y}")

        else:
            # Normal mode
            self.root.attributes("-alpha", 1.0)
            self.root.resizable(False, False)

            size = 720
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()

            x = (sw - size) // 2
            y = (sh - size) // 2

            self.root.geometry(f"{size}x{size}+{x}+{y}")



    def _update_scroll(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        needs_scroll = self.board_frame.winfo_reqheight() > self.canvas.winfo_height()

        if needs_scroll:
            if not self.scrollbar.winfo_ismapped():
                self.scrollbar.pack(side="left", fill="y")
        else:
            if self.scrollbar.winfo_ismapped():
                self.scrollbar.pack_forget()
    def bind_mouse_wheel(self):
        self.canvas.bind("<Enter>", self._bind_scroll)
        self.canvas.bind("<Leave>", self._unbind_scroll)

    def _bind_scroll(self, event):
        self.canvas.bind_all("<Button-4>",
            lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind_all("<Button-5>",
            lambda e: self.canvas.yview_scroll(1, "units"))

    def _unbind_scroll(self, event):
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")


    def on_close(self):
        self.timer_widget.stop()
        self.root.destroy()

    def commit(self):
        save_data(self.data)
        self.refresh_tasks()



class BigClock(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#0f1115")

        self.label = tk.Label(
            self,
            text="00:00:00",
            font=("Courier New", 42, "bold"),  # monospaced
            fg="white",
            bg="#0f1115",
            width=8,          # HH:MM:SS
            anchor="center"
        )
        self.label.pack(pady=10, fill="x")


        self.update_clock()

    def update_clock(self):
        now = time.strftime("%H:%M:%S")
        self.label.config(text=now)
        self.after(1000, self.update_clock)

class StopwatchTimer:
    def __init__(self):
        self.running = False
        self.start_time = None
        self.elapsed = 0.0

    def start(self):
        if not self.running:
            self.start_time = time.time()
            self.running = True

    def pause(self):
        if self.running:
            self.elapsed += time.time() - self.start_time
            self.running = False
            self.start_time = None

    def reset(self):
        self.running = False
        self.start_time = None
        self.elapsed = 0.0

    def get_elapsed(self):
        if self.running:
            return self.elapsed + (time.time() - self.start_time)
        return self.elapsed

    def formatted(self):
        total = int(self.get_elapsed())
        hours = total // 3600
        mins = (total % 3600) // 60
        secs = total % 60
        return f"{hours:02}:{mins:02}:{secs:02}"


class TimerWidget(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#0f1115")

        self.timer = StopwatchTimer()
        self._ui_loop_running = True

        self.time_label = tk.Label(
            self,
            text="00:00:00",
            font=("Courier New", 36, "bold"),  # monospaced
            fg="#4caf50",
            bg="#0f1115",
            width=8,          # EXACT width for HH:MM:SS
            anchor="center"   # prevent left clipping
        )


        self.time_label.pack(pady=10, fill="x")

        btns = tk.Frame(self, bg="#0f1115")
        btns.pack(pady=5)

        self.start_btn = tk.Button(btns, text="▶ Start", command=self.start)
        self.start_btn.pack(side="left", padx=5)

        self.pause_btn = tk.Button(
            btns, text="⏸ Pause", command=self.pause, state="disabled"
        )
        self.pause_btn.pack(side="left", padx=5)

        self.reset_btn = tk.Button(btns, text="⟲ Reset", command=self.reset)
        self.reset_btn.pack(side="left", padx=5)

        self.update_ui()

    def start(self):
        self.timer.start()
        self.start_btn.config(state="disabled")
        self.pause_btn.config(state="normal")

    def pause(self):
        self.timer.pause()
        self.start_btn.config(state="normal")
        self.pause_btn.config(state="disabled")

    def reset(self):
        self.timer.reset()
        self.time_label.config(text="00:00:00")
        self.start_btn.config(state="normal")
        self.pause_btn.config(state="disabled")


    def update_ui(self):
        if not self._ui_loop_running:
            return

        if self.timer.running:
            self.time_label.config(text=self.timer.formatted())

        self.after(100, self.update_ui)

    def stop(self):
        self._ui_loop_running = False

class AppState:
    def __init__(self):
        self.data = load_data()

def start_ui():
    root = tk.Tk()
    FocusDashboard(root)
    root.mainloop()
