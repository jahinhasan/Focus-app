# 📱 Focus Dashboard: Android Edition

This directory contains the **Flutter** source code for the Focus Dashboard mobile app. The mobile version provides high-fidelity parity with the desktop application, including AI parsing, gamification, and persistent background timers.

## 🛠️ Prerequisites

1.  **Flutter SDK**: [Install Flutter](https://docs.flutter.dev/get-started/install).
2.  **Android Studio**: Recommended for building and signing the APK.
3.  **Physical Device/Emulator**: For testing and deployment.

## 🚀 Deployment Instructions

### For Users (Download)
The latest release APK can be built using:
```bash
flutter build apk --release
```
The resulting file will be located at:
`build/app/outputs/flutter-apk/app-release.apk`

### For Developers (Setup)
1. **Fetch Dependencies**:
   ```bash
   flutter pub get
   ```
2. **Run on Device**:
   ```bash
   flutter run --release
   ```

## 📂 Architecture Overview

- **`lib/main.dart`**: App initialization and unified navigation.
- **`lib/logic_port.dart`**: Ported Python business logic (XP, Levels, Persistence).
- **`lib/ai_parser_port.dart`**: Mobile-side Gemini 1.5 Flash integration.
- **`lib/offline_brain.dart`**: Local pattern learning and fuzzy matching for offline use.
- **`lib/timer_screen.dart`**: Persistent background stopwatch and timer logic.

---
*Built with Flutter for high performance and visual excellence.*

