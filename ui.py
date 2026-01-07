import tkinter as tk
import subprocess

from tkinter import ttk

from logic import (
    load_data, toggle_subtask,
    add_task, edit_task, delete_task,
    add_subtask, edit_subtask, delete_subtask,
    get_stats
)


class FocusDashboard:
    def __init__(self, root):
        self.root = root
        self.data = load_data()
        self.overlay = False
        self.overlay_alpha = 0.85

        from logic import reset_tasks_for_new_day
        reset_tasks_for_new_day(self.data)

        self.view = "today"
        self.fullscreen = True

        root.title("Focus Dashboard")
        root.attributes("-fullscreen", True)
        root.attributes("-topmost", True)
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

# ---------- WALLPAPER / CONTENT LAYER ----------
        self.wallpaper_layer = tk.Frame(self.main_area)
        self.wallpaper_layer.grid(row=0, column=0, sticky="nsew")

       
        # Center wrapper (fixed width, centered)
        self.center_wrapper = tk.Frame(self.wallpaper_layer)
        self.center_wrapper.place(relx=0.5, rely=0.0, relheight=1.0, anchor="n")
        self.center_wrapper.config(width=720)
        self.center_wrapper.pack_propagate(False)



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

        root.bind("<F11>", self.toggle_fullscreen)
        root.bind("<Control-n>", lambda e: self.task_entry.focus())
        root.bind("<Control-h>", lambda e: self.switch_view(
            "history" if self.view == "today" else "today"
        ))
        self.root.bind_all("<F9>", self.toggle_overlay)

        root.bind("<Escape>", lambda e: self.toggle_overlay() if self.overlay else None)
        #root.bind("<F8>", lambda e: self.toggle_click_through())
        root.bind("<F6>", lambda e: self.change_opacity(-0.05))
        root.bind("<F7>", lambda e: self.change_opacity(0.05))
        root.bind("<Alt-Left>", lambda e: self.dock("left"))
        root.bind("<Alt-Right>", lambda e: self.dock("right"))
        root.bind("<Alt-Up>", lambda e: self.dock("top"))
        self.root.after(100, self.refresh_tasks)
  

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

        tk.Button(right, text="🗖", width=3,
                command=self.toggle_fullscreen).pack(side="left")
        tk.Button(right, text="—", width=3,
                command=self.root.iconify).pack(side="left")
        tk.Button(right, text="❌", width=3, fg="red",
                command=self.root.destroy).pack(side="left")

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
                width=min(1100, e.width)
            )
        )

        self.board_frame.bind("<Configure>", self._update_scroll)

    # ================= RENDER =================
    def render_tasks(self):
        for w in self.board_frame.winfo_children():
            w.destroy()

        if not self.data.get("tasks"):
            tk.Label(
                self.board_frame,
                text="No tasks yet. Add one above 👆",
                font=("Arial", 12),
                fg="gray"
            ).grid(pady=40)
            self.board_frame.grid_anchor("center")
            return

        for i in range(self.board_frame.grid_size()[0]):
            self.board_frame.grid_columnconfigure(i, weight=0)


        cols = max(1, self.canvas.winfo_width() // 360)

        for c in range(cols):
            self.board_frame.grid_columnconfigure(c, weight=1)

        row = col = 0

        for ti, task in enumerate(self.data.get("tasks", [])):
            card = self.render_task(ti, task)
            card.grid(row=row, column=col, padx=20, pady=20, sticky="n")
        

            col += 1
            if col >= cols:
                col = 0
                row += 1
        self.board_frame.grid_anchor("center")


    def render_task(self, ti, task):
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
    def toggle_fullscreen(self, event=None):
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)
        if not self.fullscreen:
            self.root.geometry("900x600")
    def switch_view(self, view):
        self.view = view

        if self.view == "today":
            self.render_tasks()
        else:
            self.render_history()

        self.update_stats()


  
    def toggle_click_through(self):
        self.click_through = not self.click_through

        if self.click_through:
            self.root.attributes("-disabled", True)
        else:
            self.root.attributes("-disabled", False)
    def change_opacity(self, delta):
        self.overlay_alpha = min(1.0, max(0.3, self.overlay_alpha + delta))
        self.root.attributes("-alpha", self.overlay_alpha)
    def dock(self, position):
        w = self.root.winfo_screenwidth()
        h = self.root.winfo_screenheight()

        if position == "left":
            self.root.geometry(f"400x{h}+0+0")
        elif position == "right":
            self.root.geometry(f"400x{h}+{w-400}+0")
        elif position == "top":
            self.root.geometry(f"{w}x200+0+0")
    def toggle_overlay(self, event=None):
        # Toggle overlay state and ensure layout-manager safety
        self.overlay = not self.overlay

        if self.overlay:
            # Overlay ON: disable fullscreen, use overrideredirect,
            # set full-screen geometry and switch center_wrapper to place
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()

            # Ensure root is fullscreen for wallpaper behavior
            try:
                self.root.attributes("-fullscreen", True)
            except Exception:
                pass

            # If center_wrapper is managed by pack, remove it first
            try:
                if self.center_wrapper.winfo_manager() == "pack":
                    self.center_wrapper.pack_forget()
            except Exception:
                pass

            # Calculate constrained width for centered column (600-800px range)
            desired_width = max(600, min(800, sw - 200)) if sw > 800 else max(400, sw - 100)

            # Prevent children from expanding the frame beyond desired width
            try:
                self.center_wrapper.pack_propagate(False)
            except Exception:
                pass

            self.root.overrideredirect(True)
            self.root.attributes("-alpha", self.overlay_alpha)

            # center the UI using place with a fixed width (no simultaneous pack)
            self.center_wrapper.place(relx=0.5, rely=0.5, anchor="center", width=desired_width)

            self.set_desktop_layer()
            self.root.attributes("-topmost", False)

            self.root.focus_force()

            # Overlay control bar (create if not present)
            if not (hasattr(self, "overlay_bar") and getattr(self, "overlay_bar").winfo_exists()):
                self.overlay_bar = tk.Frame(self.root, bg="#111")
                self.overlay_bar.place(x=0, y=0, relwidth=1, height=30)
                tk.Button(
                    self.overlay_bar,
                    text="✖ Exit Overlay",
                    command=self.toggle_overlay,
                    bg="#222",
                    fg="white",
                    bd=0
                ).pack(side="right", padx=10)

        else:
            # Overlay OFF: remove place, disable overrideredirect,
            # restore fullscreen according to self.fullscreen and re-pack


            # If center_wrapper is managed by place, remove it first
            try:
                if self.center_wrapper.winfo_manager() == "place":
                    self.center_wrapper.place_forget()
            except Exception:
                pass

            # Restore propagation so pack can resize the wrapper normally
            try:
                self.center_wrapper.pack_propagate(True)
            except Exception:
                pass

            self.root.overrideredirect(False)
            
            self.root.attributes("-alpha", 1.0)

            # Restore fullscreen to the saved self.fullscreen state
            try:
                self.root.attributes("-fullscreen", self.fullscreen)
            except Exception:
                pass

            # If not restoring to fullscreen, set a reasonable window size
            if not self.fullscreen:
                self.root.geometry("900x600")

            # Re-pack the center wrapper (no simultaneous place)
            try:
                if self.center_wrapper.winfo_manager() != "pack":
                    self.center_wrapper.pack(fill="both", expand=True)
            except Exception:
                # Fallback: ensure it's packed
                self.center_wrapper.pack(fill="both", expand=True)

            if hasattr(self, "overlay_bar"):
                try:
                    self.overlay_bar.destroy()
                except Exception:
                    pass

    def set_desktop_layer(self):
        """
        Attach window to desktop layer (wallpaper-like behavior)
        """
        self.root.update_idletasks()
        wid = self.root.winfo_id()

        subprocess.call([
            "wmctrl", "-i", "-r", str(wid),
            "-b", "add,below,sticky,skip_taskbar"
        ])
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
        self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))
    def refresh_tasks(self):
        for w in self.board_frame.winfo_children():
            w.destroy()

        if self.view == "today":
            self.render_tasks()
        else:
            self.render_history()

        self.update_stats()
        self._update_scroll()
        self.canvas.yview_moveto(0)



def start_ui():
    root = tk.Tk()
    FocusDashboard(root)
    root.mainloop()
