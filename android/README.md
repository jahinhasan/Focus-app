# 📱 Focus Dashboard: Mobile Edition

This folder contains the **Flutter (Dart)** source code for the Focus Dashboard mobile app.
Follow these steps to initialize the project and build it in **Android Studio**.

## 🛠️ Prerequisites

1.  **Flutter SDK**: [Install Flutter](https://docs.flutter.dev/get-started/install).
2.  **Android Studio**: Install with the **Flutter** and **Dart** plugins enabled.
3.  **Android SDK**: Ensure you have the Android SDK Command-line Tools installed (via Android Studio SDK Manager).

## 🚀 Setup Instructions

Since this repository tracks the source files but might not be a fully initialized Flutter project root (to keep the repo clean), follow these steps to generate the build files:

### Step 1: Initialize Flutter Project
Open your terminal in this `android/` folder and run:

```bash
# Initialize a new Flutter project in the current directory
flutter create --project-name=focus_app .
```

*Note: The `.` tells Flutter to use the current directory. If it complains about existing files, you might need to create a new folder, but usually, it works or you can create a `mobile` folder next to it.*

**Alternative (Cleanest Method):**
1.  Go up one level: `cd ..`
2.  Create a new flutter project: `flutter create mobile_app`
3.  Copy the `.dart` files from `android/` into `mobile_app/lib/`.
4.  Copy the dependencies from `android/pubspec.yaml` to `mobile_app/pubspec.yaml`.

### Step 2: Install Dependencies
If you initialized in place, ensure your `pubspec.yaml` has the required packages (see `pubspec.yaml` in this folder). Then run:

```bash
flutter pub get
```

### Step 3: Open in Android Studio
1.  Open **Android Studio**.
2.  Select **Open** and choose the folder containing `pubspec.yaml`.
3.  Wait for Gradle sync to finish.

### Step 4: Run
1.  Connect your physical Android device or start an Emulator.
2.  Click the green **Run** (▶️) button.

---

## 📂 Key Files

-   **`main.dart`**: Entry point. Sets up the theme and navigation.
-   **`dashboard.dart`**: The main "Today" view with task lists and XP progress.
-   **`logic_port.dart`**: The core business logic (XP, Levels, Automation) ported from Python.
-   **`vault_screen.dart`**: File and subject management.
-   **`timer_screen.dart`**: Focus timer implementation.

## ⚠️ Notes for Developers

-   This is a **port** of the Python logic. Changes in `logic.py` (Python) should be manually mirrored to `logic_port.dart` (Dart).
-   The current version uses local shared preferences. Future updates will sync with a cloud backend.
