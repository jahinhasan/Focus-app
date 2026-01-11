import flet as ft
from logic import load_data, get_level_progress

def main(page: ft.Page):
    page.title = "Focus Dashboard Mobile"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20
    page.bgcolor = "#0F0F1A"
    
    # Load App Data (Reusing your logic.py!)
    data = load_data()
    progress = get_level_progress(data)
    
    # --- UI COMPONENTS ---
    
    # XP Header
    xp_header = ft.Column([
        ft.Row([
            ft.Column([
                ft.Text(f"Level {data['level']}", size=28, weight="bold", color="white"),
                ft.Text(f"{data['xp']} Total XP", size=14, color="white70"),
            ], alignment=ft.MainAxisAlignment.START),
            ft.Icon(ft.icons.STARS, color="blue", size=40)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.ProgressBar(value=progress[2], color="blue", bgcolor="white10", height=10, border_radius=5)
    ])

    # Task List
    task_list = ft.ListView(expand=1, spacing=10, padding=10)
    
    for task in data.get("tasks", []):
        task_list.controls.append(
            ft.Container(
                content=ft.Row([
                    ft.Icon(
                        ft.icons.SCHOOL if task['type'] == 'class' else ft.icons.CHECK_CIRCLE_OUTLINE,
                        color="green" if task['status'] == 'done' else "white30"
                    ),
                    ft.Column([
                        ft.Text(task['name'], weight="bold", color="white"),
                        ft.Text(task.get('status', 'pending'), size=12, color="white38")
                    ])
                ]),
                padding=15,
                bgcolor="#1C1C2D",
                border_radius=15,
                border=ft.border.all(1, "white10")
            )
        )

    # --- LAYOUT ---
    page.add(
        xp_header,
        ft.Divider(height=40, color="transparent"),
        ft.Text("Today's Focus", size=20, weight="bold"),
        task_list
    )

    # Bottom Navigation
    page.navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationDestination(icon=ft.icons.TODAY, label="Today"),
            ft.NavigationDestination(icon=ft.icons.CALENDAR_MONTH, label="Routine"),
            ft.NavigationDestination(icon=ft.icons.TIMER, label="Focus"),
        ],
        bgcolor="#161625",
        selected_index=0
    )

if __name__ == "__main__":
    # To run as a mobile app: flet run mobile_app.py
    ft.app(target=main)
