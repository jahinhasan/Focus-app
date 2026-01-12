import 'dart:math';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

/// Core Data Model for the Focus Android App
/// Mirroring the structure from logic.py
class FocusData {
  int level;
  int xp;
  List<Map<String, dynamic>> tasks;
  Map<String, dynamic> history;
  Map<String, dynamic> settings;
  Map<String, dynamic> store;
  List<Map<String, dynamic>> habits;
  Map<String, dynamic> subjects;
  Map<String, dynamic> timerState;

  FocusData({
    required this.level,
    required this.xp,
    required this.tasks,
    required this.history,
    required this.settings,
    required this.store,
    required this.habits,
    required this.subjects,
    required this.timerState,
  });

  /// Factory to create a default/clean state (Mirroring load_data's defaults)
  factory FocusData.defaultState() {
    return FocusData(
      level: 1,
      xp: 0,
      tasks: [],
      history: {},
      settings: {
        'theme': 'System',
        'daily_goal_hours': 4,
        'timer_style': 'stopwatch',
        'pomodoro': {'work': 25, 'short_break': 5, 'long_break': 15},
        'gemini_api_key': '',
      },
      store: {
        'unlocked': ['theme_default', 'sound_rain'],
        'xp_spent': 0,
      },
      habits: [],
      subjects: {},
      timerState: {
        'seconds': 0,
        'mode': 'Focus',
        'is_running': false,
        'last_tick': null
      },
    );
  }

  // ==================== PERSISTENCE ====================

  /// Convert to JSON map
  Map<String, dynamic> toJson() {
    return {
      'level': level,
      'xp': xp,
      'tasks': tasks,
      'history': history,
      'settings': settings,
      'store': store,
      'habits': habits,
      'subjects': subjects,
      'timer_state': timerState,
    };
  }

  /// Create from JSON map
  factory FocusData.fromJson(Map<String, dynamic> json) {
    return FocusData(
      level: json['level'] ?? 1,
      xp: json['xp'] ?? 0,
      tasks: List<Map<String, dynamic>>.from(json['tasks'] ?? []),
      history: json['history'] ?? {},
      settings: json['settings'] != null
          ? {
              ...FocusData.defaultState().settings,
              ...Map<String, dynamic>.from(json['settings'])
            }
          : FocusData.defaultState().settings,
      store: json['store'] ?? {'unlocked': [], 'xp_spent': 0},
      habits: List<Map<String, dynamic>>.from(json['habits'] ?? []),
      subjects: json['subjects'] ?? {},
      timerState: json['timer_state'] ??
          {
            'seconds': 0,
            'mode': 'Focus',
            'is_running': false,
            'last_tick': null
          },
    );
  }

  /// Save data to local file
  Future<void> save() async {
    try {
      final directory = await getApplicationDocumentsDirectory();
      final file = File('${directory.path}/data.json');
      await file.writeAsString(jsonEncode(toJson()));
      debugPrint("Data saved to ${file.path}");
    } catch (e) {
      debugPrint("Error saving data: $e");
    }
  }

  /// Load data from local file
  static Future<FocusData> load() async {
    try {
      final directory = await getApplicationDocumentsDirectory();
      final file = File('${directory.path}/data.json');
      if (await file.exists()) {
        final content = await file.readAsString();
        final json = jsonDecode(content);
        return FocusData.fromJson(json);
      }
    } catch (e) {
      debugPrint("Error loading data: $e");
    }
    return FocusData.defaultState();
  }

  // ==================== XP SYSTEM ====================

  /// Adds XP and returns a record of the change (Mirroring add_xp)
  XPResult addXP(int amount) {
    xp += amount;
    int oldLevel = level;

    // Level Formula: Level = floor(sqrt(XP / 100)) + 1
    level = (sqrt(xp / 100)).floor() + 1;

    bool leveledUp = level > oldLevel;

    save(); // Auto-save on XP change

    return XPResult(
      newLevel: level,
      gainedXP: amount,
      leveledUp: leveledUp,
    );
  }

  /// Calculates progress toward next level (Mirroring get_level_progress)
  ProgressResult getLevelProgress() {
    // Current level's base XP = (level - 1)^2 * 100
    int currentLevelBase = pow(level - 1, 2).toInt() * 100;
    // Next level's base XP = level^2 * 100
    int nextLevelBase = pow(level, 2).toInt() * 100;

    int xpInLevel = xp - currentLevelBase;
    int xpRequiredForLevel = nextLevelBase - currentLevelBase;
    double percentage = xpInLevel / xpRequiredForLevel;

    return ProgressResult(
      currentXP: xpInLevel,
      requiredXP: xpRequiredForLevel,
      percentage: percentage.clamp(0.0, 1.0),
    );
  }

  // ==================== AUTOMATION ====================

  /// Runs daily maintenance (Reset classes, auto-archive tasks)
  /// Mirroring process_daily_automation
  void processDailyAutomation() {
    final now = DateTime.now();
    final todayStr = now.toIso8601String().split('T')[0];
    // List of day names: mon, tue, wed, thu, fri, sat, sun
    final todayDay = _getDayAbbreviation(now.weekday);

    List<Map<String, dynamic>> activeTasks = [];

    for (var task in tasks) {
      // 1. Recurring Class Logic
      if (task['type'] == 'class') {
        final Map<String, dynamic> sch = task['schedule'] ?? {};
        final List<dynamic> days = sch['days'] ?? [];

        if (days.contains(todayDay)) {
          final String lastUpdate = task['updated_at'] ?? '';
          if (lastUpdate != todayStr) {
            task['status'] = 'todo';
            task['updated_at'] = todayStr;
          }
        }
        activeTasks.add(task);
      }
      // 2. Regular Task Logic (Auto-Archive)
      else {
        final String status = task['status'] ?? 'todo';
        final String updated = task['updated_at'] ?? '';

        // If done and NOT updated today -> Archive
        bool shouldArchive = false;
        if (status == 'done' && updated != todayStr) {
          shouldArchive = true;
        }

        if (shouldArchive) {
          // Archive (Don't add to active tasks)
          continue;
        }
        activeTasks.add(task);
      }
    }
    tasks = activeTasks;
    save(); // Save after automation
  }

  /// Checks which classes started or ended (Mirroring sync_class_statuses)
  SyncResult syncClassStatuses() {
    final nowStr = DateTime.now()
        .toIso8601String()
        .split('T')[1]
        .substring(0, 5); // "HH:MM"
    final nowDay = _getDayAbbreviation(DateTime.now().weekday);

    List<String> needsAttendancePrompt = [];
    List<String> justStarted = [];
    bool changed = false;

    for (var task in tasks) {
      if (task['type'] != 'class') continue;

      final Map<String, dynamic> sch = task['schedule'] ?? {};
      final List<dynamic> days = sch['days'] ?? [];

      if (!days.contains(nowDay)) continue;

      final String start = sch['start'] ?? '00:00';
      final String end = sch['end'] ?? '00:00';

      // Active
      if (nowStr.compareTo(start) >= 0 && nowStr.compareTo(end) <= 0) {
        if (task['status'] != 'active') {
          task['status'] = 'active';
          justStarted.add(task['id']);
          changed = true;
        }
      }
      // Ended
      else if (nowStr.compareTo(end) > 0) {
        final String status = task['status'] ?? 'todo';
        if (!['done', 'missed', 'ended'].contains(status)) {
          task['status'] = 'ended';
          needsAttendancePrompt.add(task['id']);
          changed = true;
        }
      }
    }

    if (changed) save();

    return SyncResult(
        needsAttendance: needsAttendancePrompt, justStarted: justStarted);
  }

  // ==================== SUBTASKS ====================

  /// Add a subtask to a task
  void addSubtask(String taskId, String title) {
    for (var task in tasks) {
      if (task['id'] == taskId) {
        if (task['subtasks'] == null) {
          task['subtasks'] = [];
        }
        (task['subtasks'] as List).add({
          'title': title,
          'done': false,
        });
        save();
        break;
      }
    }
  }

  /// Toggle a subtask's completion status
  void toggleSubtask(String taskId, int index) {
    for (var task in tasks) {
      if (task['id'] == taskId) {
        if (task['subtasks'] != null &&
            index < (task['subtasks'] as List).length) {
          var sub = task['subtasks'][index];
          sub['done'] = !(sub['done'] ?? false);
          save();
        }
        break;
      }
    }
  }

  /// Delete a subtask
  void deleteSubtask(String taskId, int index) {
    for (var task in tasks) {
      if (task['id'] == taskId) {
        if (task['subtasks'] != null &&
            index < (task['subtasks'] as List).length) {
          (task['subtasks'] as List).removeAt(index);
          save();
        }
        break;
      }
    }
  }

  String _getDayAbbreviation(int weekday) {
    // DateTime.weekday: 1 = Mon, 7 = Sun
    return ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'][weekday - 1];
  }

  String _generateId() {
    // Simple unique ID generation without external dependencies
    return "${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(10000)}";
  }

  // ==================== HABITS ====================

  void addHabit(String title) {
    if (title.isEmpty) return;
    habits.add({
      'id': _generateId(),
      'title': title,
      'history': [], // List of "YYYY-MM-DD" strings
      'created_at': DateTime.now().toIso8601String().split('T')[0],
    });
    save();
  }

  void toggleHabit(String habitId) {
    final today = DateTime.now().toIso8601String().split('T')[0];
    for (var habit in habits) {
      if (habit['id'] == habitId) {
        List<dynamic> history = habit['history'] ?? [];
        if (history.contains(today)) {
          history.remove(today); // Untoggle
        } else {
          history.add(today); // Toggle
          addXP(10); // Habit XP
        }
        habit['history'] = history;
        save();
        break;
      }
    }
  }

  void deleteHabit(String habitId) {
    habits.removeWhere((h) => h['id'] == habitId);
    save();
  }

  // ==================== VAULT ====================

  bool addSubject(String name) {
    if (subjects.containsKey(name)) return false;
    subjects[name] = {'notes': '', 'documents': []};
    save();
    return true;
  }

  void deleteSubject(String name) {
    subjects.remove(name);
    save();
  }

  void addVaultFile(String subject, String filePath) {
    if (!subjects.containsKey(subject)) {
      addSubject(subject);
    }
    List<dynamic> docs = subjects[subject]['documents'] ?? [];
    if (!docs.contains(filePath)) {
      docs.add(filePath);
      subjects[subject]['documents'] = docs;
      save();
    }
  }

  // ==================== TIMER PERSISTENCE ====================

  void updateTimerState({
    required int seconds,
    required String mode,
    required bool isRunning,
  }) {
    timerState = {
      'seconds': seconds,
      'mode': mode,
      'is_running': isRunning,
      'last_tick': isRunning ? DateTime.now().toIso8601String() : null,
      'updated_at': DateTime.now().toIso8601String(),
    };
    save();
  }

  void clearTimerState() {
    timerState = {
      'seconds': 0,
      'mode': 'Focus',
      'is_running': false,
      'last_tick': null,
    };
    save();
  }
}

class SyncResult {
  final List<String> needsAttendance;
  final List<String> justStarted;
  SyncResult({required this.needsAttendance, required this.justStarted});
}

class XPResult {
  final int newLevel;
  final int gainedXP;
  final bool leveledUp;
  XPResult(
      {required this.newLevel,
      required this.gainedXP,
      required this.leveledUp});
}

class ProgressResult {
  final int currentXP;
  final int requiredXP;
  final double percentage;
  ProgressResult(
      {required this.currentXP,
      required this.requiredXP,
      required this.percentage});
}
