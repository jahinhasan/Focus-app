# 🎯 Focus Dashboard

A modern, high-performance productivity application built with Python and CustomTkinter. Designed for students and professionals to manage tasks, track routines, and maintain focus with a gamified experience.

![App Header](assets/screenshot_placeholder.png) *(Add your screenshot here!)*

## ✨ Key Features

-   **🚀 Gamified Progress**: Earn XP for every task completed and class attended. Level up to unlock new themes and features!
-   **📅 Smart Routine**: Automatically parses your class schedule and populates your daily view. No manual entry needed for recurring classes.
-   **⏳ Pomodoro & Stopwatch**: flexible timer system with auto-flow (Focus -> Break) and Zen Mode for minimal distraction.
-   **📊 Visual Analytics**: GitHub-style activity heatmap to track your consistency over the year.
-   **📂 Subject Vault**: Organize documents, notes, and subtasks by subject in a clean, categorized view.
-   **🤖 Hybrid AI Assistant**: Natural language parsing for adding tasks and classes, powered by a rule-based logic with optional LLM integration.
-   **⚡ Industrial Automation**: 
    -   Daily schedule auto-resets.
    -   Stale task auto-archiving.
    -   Proactive attendance prompts when classes end.

## 🛠️ Technology Stack

-   **Language**: Python 3.10+
-   **UI Framework**: [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) (Modern translucent UI)
-   **Data Storage**: JSON (Local-first, privacy-focused)
-   **AI Engine**: Regex-based Intent Authority + Optional Groq API integration.

## 🚀 Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/jahinhasan/Focus-app.git
   cd Focus-app
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**:
   ```bash
   python main.py
   ```

## 📖 Usage

-   **Sidebar**: Navigate between Today, Routine, History, Vault, and the XP Store.
-   **Timer**: Click the timer display to switch between Countdown and Stopwatch modes.
-   **Zen Mode**: Use the button at the bottom of the sidebar to enter a focused, minimal timer view.


## 📦 Deployment & Releases

This project is configured with **GitHub Actions** to automatically build and package the application for **Windows (.exe)** and **Linux**.

- **Download**: Check the [Releases](https://github.com/jahinhasan/Focus-app/releases) tab for the latest standalone binaries.
- **Manual Build**: If you want to build locally, ensure `pyinstaller` is installed and run: `pyinstaller FocusApp.spec`.

## 📂 Project Structure

- `main.py`: Entry point.
- `ui.py`: All UI components and view logic.
- `logic.py`: Core business logic and data management.
- `ai_parser.py`: Natural language understanding engine.
- `ace_integration.py`: Lightweight stats and pattern learning.
- `file_parser.py`: Document extraction for routine uploads.


---
*Built with ❤️ for focused minds.*
