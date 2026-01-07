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
        root.bind("<F11>", self.toggle_fullscreen)
        root.bind("<Control-n>", lambda e: self.task_entry.focus())
        root.bind("<Control-h>", lambda e: self.switch_view(
            "history" if self.view == "today" else "today"
        ))

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


def start_ui():
    root = tk.Tk()
    FocusDashboard(root)
    root.mainloop()
