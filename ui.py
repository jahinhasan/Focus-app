import tkinter as tk
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

        self.build_header()
        self.build_task_input()
        self.build_scroll_area()
        self.bind_mouse_wheel()

        self.render_tasks()
        self.click_through = False

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
       

    # ================= HEADER =================
    def build_header(self):
        header = tk.Frame(self.root)
        header.pack(fill="x", padx=10, pady=5)

        tk.Label(
            header, text="🎯 TODAY",
            font=("Arial", 16, "bold")
        ).pack(side="left")

        btns = tk.Frame(header)
        btns.pack(side="right")

        tk.Button(btns, text="🗖", width=3,
                  command=self.toggle_fullscreen).pack(side="left")
        tk.Button(btns, text="—", width=3,
                  command=self.root.iconify).pack(side="left")
        tk.Button(btns, text="❌", width=3, fg="red",
                  command=self.root.destroy).pack(side="left")
        tk.Button(
            btns, text="🪟",
            width=3,
            command=self.toggle_overlay
        ).pack(side="left")


        self.level_label = tk.Label(self.root, font=("Arial", 14, "bold"))
        self.level_label.pack()

        self.xp_bar = ttk.Progressbar(self.root, length=320, maximum=100)
        self.xp_bar.pack(pady=4)

        nav = tk.Frame(self.root)
        nav.pack(pady=4)

        tk.Button(nav, text="📅 Today",
                  command=lambda: self.switch_view("today")).pack(side="left", padx=5)
        tk.Button(nav, text="🕘 History",
                  command=lambda: self.switch_view("history")).pack(side="left", padx=5)

        self.update_stats()

    def update_stats(self):
        level, xp = get_stats(self.data)
        self.level_label.config(text=f"⭐ LEVEL {level}")
        self.xp_bar["value"] = xp

    # ================= ADD TASK =================
    def build_task_input(self):
        frame = tk.Frame(self.root)
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
        container = tk.Frame(self.root)
        container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(container)
        scrollbar = tk.Scrollbar(container, orient="vertical",
                                 command=self.canvas.yview)

        self.task_frame = tk.Frame(self.canvas)

        self.task_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0),
                                  window=self.task_frame,
                                  anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def bind_mouse_wheel(self):
        self.canvas.bind_all("<Button-4>", self._on_mouse_wheel)
        self.canvas.bind_all("<Button-5>", self._on_mouse_wheel)

    def _on_mouse_wheel(self, event):
        self.canvas.yview_scroll(-1 if event.num == 4 else 1, "units")

    # ================= RENDER =================
    def refresh_tasks(self):
        for w in self.task_frame.winfo_children():
            w.destroy()

        if self.view == "today":
            self.render_tasks()
        else:
            self.render_history()

        self.update_stats()

    def render_tasks(self):
        for ti, task in enumerate(self.data["tasks"]):
            self.render_task(ti, task)

    def render_task(self, ti, task):
        frame = tk.Frame(self.task_frame, bd=1, relief="solid")
        frame.pack(fill="x", padx=10, pady=4)

        # ---- TASK TITLE ----
        title_row = tk.Frame(frame)
        title_row.pack(fill="x", padx=5)

        title_lbl = tk.Label(
            title_row,
            text=("✔ " if task["done"] else "⬜ ") + task["title"],
            font=("Arial", 11, "bold")
        )
        title_lbl.pack(side="left")

        def edit_task_inline():
            title_lbl.pack_forget()
            entry = tk.Entry(title_row)
            entry.insert(0, task["title"])
            entry.pack(side="left", fill="x", expand=True)
            entry.bind("<Escape>", lambda e: self.refresh_tasks())

            tk.Button(title_row, text="✔",
                      command=lambda: (
                          edit_task(self.data, ti, entry.get()),
                          self.refresh_tasks()
                      )).pack(side="left")

            tk.Button(title_row, text="✖",
                      command=self.refresh_tasks).pack(side="left")

        tk.Button(title_row, text="✏",
                  command=edit_task_inline).pack(side="right")
        tk.Button(title_row, text="❌",
                  command=lambda: (
                      delete_task(self.data, ti),
                      self.refresh_tasks()
                  )).pack(side="right")

        # ---- SUBTASKS ----
        for si, sub in enumerate(task["subtasks"]):
            row = tk.Frame(frame)
            row.pack(fill="x", padx=20)

            var = tk.BooleanVar(value=sub["done"])
            tk.Checkbutton(
                row, variable=var,
                command=lambda v=var, t=ti, s=si: (
                    toggle_subtask(self.data, t, s, v.get()),
                    self.update_stats()
                )
            ).pack(side="left")

            lbl = tk.Label(row, text=sub["title"])
            lbl.pack(side="left")

            def edit_subtask_inline(r=row, t=ti, s=si, text=sub["title"]):
                for w in r.winfo_children():
                    w.destroy()

                entry = tk.Entry(r)
                entry.insert(0, text)
                entry.pack(side="left", fill="x", expand=True)
                entry.bind("<Escape>", lambda e: self.refresh_tasks())


                tk.Button(r, text="✔",
                          command=lambda: (
                              edit_subtask(self.data, t, s, entry.get()),
                              self.refresh_tasks()
                          )).pack(side="left")
                tk.Button(r, text="✖",
                          command=self.refresh_tasks).pack(side="left")

            tk.Button(row, text="✏",
                      command=edit_subtask_inline).pack(side="right")
            tk.Button(row, text="❌",
                      command=lambda t=ti, s=si: (
                          delete_subtask(self.data, t, s),
                          self.refresh_tasks()
                      )).pack(side="right")

        # ---- ADD SUBTASK ----
        add_row = tk.Frame(frame)
        add_row.pack(fill="x", padx=20, pady=3)

        entry = tk.Entry(add_row)
        entry.pack(side="left", fill="x", expand=True)

        tk.Button(add_row, text="➕",
                  command=lambda: (
                      add_subtask(self.data, ti, entry.get()),
                      self.refresh_tasks()
                  )).pack(side="right")

    # ================= HISTORY =================
    def render_history(self):
        history = self.data.get("history", {})

        if not history:
            tk.Label(self.task_frame, text="No history yet").pack(pady=20)
            return

        for day, info in sorted(history.items(), reverse=True):
            box = tk.Frame(self.task_frame, bd=1, relief="solid")
            box.pack(fill="x", padx=10, pady=5)

            tk.Label(box, text=f"📅 {day}",
                     font=("Arial", 11, "bold")).pack(anchor="w", padx=5)
            tk.Label(box,
                     text=f"✔ {info['completed']} / {info['total']}").pack(anchor="w", padx=15)
            tk.Label(box,
                     text=f"⭐ XP gained: {info['xp_gained']:.1f}").pack(anchor="w", padx=15)

    # ================= UTIL =================
    def toggle_fullscreen(self, event=None):
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)
        if not self.fullscreen:
            self.root.geometry("900x600")

    def switch_view(self, view):
        self.view = view
        self.refresh_tasks()

  
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
        self.overlay = not self.overlay

        if self.overlay:
        # Overlay mode
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)
            self.root.attributes("-alpha", self.overlay_alpha)
            self.root.focus_force()

        # Overlay control bar
            self.overlay_bar = tk.Frame(
                self.root,
                bg="#111"
            )
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
        # Normal window mode
            self.root.overrideredirect(False)
            self.root.attributes("-topmost", False)
            self.root.attributes("-alpha", 1.0)

            if hasattr(self, "overlay_bar"):
                self.overlay_bar.destroy()



def start_ui():
    root = tk.Tk()
    FocusDashboard(root)
    root.mainloop()
