# 🎯 Focus Dashboard
[![Flutter](https://img.shields.io/badge/Flutter-%2302569B.svg?style=flat&logo=Flutter&logoColor=white)](https://flutter.dev)
[![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![AI](https://img.shields.io/badge/AI-Gemini_1.5_Flash-orange.svg?style=flat)](https://deepmind.google/technologies/gemini/)

**The Ultimate Productivity Command Center** for high-achievers. A unified ecosystem featuring a professional **Desktop Dashboard** (Python) and a powerful **Mobile Companion** (Flutter).

Focus Dashboard combines advanced task management, AI-automated routine tracking, and a deep gamification system into a stunning, "Dark Mode" glassmorphic interface designed to keep you in the **Flow State**.

---

## ✨ Integrated Feature Suite

### 🖥️ 1. Today's Flow (Unified Dashboard)
*   **Intelligent Timeline**: A combined view of personal tasks and class schedules.
*   **Smart Persistence**: Overdue tasks automatically stick to your timeline until resolved.
*   **Flexible Tasks**: Support for prioritized deadlines and "Backlog" items.
*   **Nested Subtasks**: Break complex goals into manageable steps (with AI-powered generation).

### 📅 2. AI Routine Mastery
*   **Vision-Powered Import**: Take a photo of your physical schedule or upload a screenshot. **Gemini 1.5 Flash** parses it instantly into your digital routine.
*   **Auto-Recurring Scheduler**: Classes appear on your dashboard automatically on the correct days.
*   **Attendance & Stats**: Track attendance to monitor your performance and earn specialized XP.

### 🚀 3. Gamification (The Focus Warrior)
*   **XP & Leveling System**: Earn experience points for every productive action (tasks, habits, classes).
*   **Modern Progression**: Scale from *Novice* to *Focus Master* with a dynamic level formula.
*   **Daily Habits**: Track recurring routines with streak monitoring and rewards.

### 📂 4. The Smart Vault
*   **Subject-Based Organization**: Dedicated storage for every class and project.
*   **File Persistence**: Securely store and open homework, readings, and notes.
*   **Mobile Parity**: Access your vault and manage files directly from your phone.

### ⏳ 5. Pro Timer & Background Flow
*   **Dual Modes**: Switch between **Pomodoro** (Focus blocks) and **Stopwatch** (Deep work tracking).
*   **Persistent Background Execution**: The timer continues accurately even if the app is closed or minimized—calculating elapsed time on relaunch.
*   **Zen Mode (Desktop)**: A minimal, distraction-free floating window.

### 🤖 6. AI Chat Assistant
*   **Intelligent Queries**: Ask about your schedule, tasks, or general productivity tips.
*   **Offline Learning**: The app "silently learns" from your interactions, providing fuzzy-matched offline fallbacks when the API is unavailable.

---

## 🛠️ Architecture & Tech Stack

| Component | Technology |
| :--- | :--- |
| **Desktop Core** | Python 3.10+ |
| **Desktop UI** | CustomTkinter (Glassmorphic Dark Theme) |
| **Mobile App** | Flutter / Dart |
| **AI Brain** | Google Gemini 1.5 Flash & Groq Fallbacks |
| **Logic** | Mirrored Business Logic (Python/Dart Parity) |
| **Data** | Local-First JSON Storage (Privacy Focused) |

---

## 🚀 Getting Started (Desktop)

### Prerequisites
- Python 3.10+
- [Google Generative AI API Key](https://aistudio.google.com/)

### Installation
1. **Clone & Enter**:
   ```bash
   git clone https://github.com/jahinhasan/Focus-app.git
   cd Focus-app
   ```
2. **Setup Environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Configure**:
   Create a `.env` file in the root:
   ```env
   GEMINI_API_KEY=your_key_here
   ```
4. **Launch**:
   ```bash
   python main.py
   ```

---

## 📱 Mobile Companion (Android)

The mobile app provides 100% feature parity with the desktop version.

### For Users
- **Download**: You can find the latest release APK in the [Releases](https://github.com/jahinhasan/Focus-app/releases) section or under `android/build/app/outputs/flutter-apk/app-release.apk`.

### For Developers
1. Navigate to the `android/` directory.
2. Run `flutter pub get`.
3. Connect your device and run `flutter run`.

---

## 📜 License & Acknowledgments

- **License**: MIT
- **Built with ❤️** for students and professionals who value their time.

