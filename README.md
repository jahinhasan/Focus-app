# 🎯 Focus Dashboard

**The Ultimate Productivity Command Center** for high-achievers. Built with **Python** & **CustomTkinter** for desktop, with a **Flutter** companion app in development.

Focus Dashboard combines professional task management, automated routine tracking, and gamification into a single, beautiful "Dark Mode" interface. It's designed to keep you in the "Flow" state.

![App Header](https://via.placeholder.com/800x400.png?text=Focus+Dashboard+Preview) *(Replace with actual screenshot)*

## ✨ Key Features

### 🖥️ Dashboard ("Today's Flow")
-   **Aggregated View**: See your personal tasks and class schedule in one timeline.
-   **Smart Persistence**: Tasks from the past (overdue) stick around until you crush them.
-   **Optional Deadlines**: Create "Backlog" tasks without dates for low-stress tracking.
-   **Subtasks**: Break down complex projects with nested checklists.

### 📅 AI-Powered Routine
-   **Gemini 1.5 Flash Integration**: Upload a screenshot of your class schedule, and the AI parses it instantly.
-   **Auto-Recurring**: Classes automatically appear on your dashboard on the correct days.
-   **Attendance Tracking**: Mark classes as Attended/Missed to build your stats.

### 🚀 Gamification (Focus Warrior)
-   **XP System**: Earn XP for every task, subtask, and class.
-   **Level Up**: Climb the ranks from Novice to Focus Master.
-   **Streaks**: Build momentum by completing tasks daily.

### 📂 Subject Vault
-   **Organized Storage**: distinct folders for each class or project.
-   **File Management**: Upload homework, readings, and notes directly to the vault.

### ⏳ Pro Timer
-   **Dual Modes**: Countdown (Pomodoro) and Stopwatch (Deep Work).
-   **Zen Mode**: A distraction-free timer window.

---

## 🛠️ Technology Stack

-   **Core**: Python 3.10+
-   **UI Framework**: [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) (Modern, High DPI)
-   **AI**: Google Gemini 1.5 Flash (via API)
-   **Data**: Local-first JSON storage (Privacy focused)
-   **Mobile**: Dart / Flutter (See `android/` folder)

---

## 🚀 Installation & Setup

### Prerequisites
-   Python 3.10 or higher
-   A Google Cloud API Key (for Gemini features)

### Quick Start
1.  **Clone the repository**:
    ```bash
    git clone https://github.com/jahinhasan/Focus-app.git
    cd Focus-app
    ```

2.  **Set up Virtual Environment**:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # Linux/Mac
    # .venv\Scripts\activate   # Windows
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure API Key**:
    -   Create a `.env` file in the root directory.
    -   Add your key: `GOOGLE_API_KEY=your_key_here`

5.  **Run the App**:
    ```bash
    python main.py
    ```

---

## 📱 Mobile Version (Android/iOS)

This repository includes a **Flutter** port of the logic and UI, located in the `android/` folder.
To build the mobile app:

1.  Navigate to the `android/` directory.
2.  Follow the [**Android Setup Guide**](android/README.md).
3.  Open the project in **Android Studio** to compile.

---

## 🤝 Contributing

We welcome contributions! Please open an issue for feature requests or submit a Pull Request.

**License**: MIT
*Built with ❤️ for focused minds.*
