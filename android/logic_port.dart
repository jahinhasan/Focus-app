import 'dart:math';

/// Core Data Model for the Focus Android App
/// Mirroring the structure from logic.py
class FocusData {
  int level;
  int xp;
  List<Map<String, dynamic>> tasks;
  Map<String, dynamic> history;
  Map<String, dynamic> settings;
  Map<String, dynamic> store;

  FocusData({
    required this.level,
    required this.xp,
    required this.tasks,
    required this.history,
    required this.settings,
    required this.store,
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
        'pomodoro': {'work': 25, 'short_break': 5, 'long_break': 15}
      },
      store: {
        'unlocked': ['theme_default', 'sound_rain'],
        'xp_spent': 0,
      },
    );
  }

  // ==================== XP SYSTEM ====================

  /// Adds XP and returns a record of the change (Mirroring add_xp)
  XPResult addXP(int amount) {
    xp += amount;
    int oldLevel = level;
    
    // Level Formula: Level = floor(sqrt(XP / 100)) + 1
    level = (sqrt(xp / 100)).floor() + 1;
    
    bool leveledUp = level > oldLevel;
    
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

        if (status == 'done' && updated != todayStr) {
          // Archive (Don't add to active tasks)
          continue;
        }
        activeTasks.add(task);
      }
    }
    tasks = activeTasks;
  }

  /// Checks which classes started or ended (Mirroring sync_class_statuses)
  SyncResult syncClassStatuses() {
    final nowStr = DateTime.now().toIso8601String().split('T')[1].substring(0, 5); // "HH:MM"
    final nowDay = _getDayAbbreviation(DateTime.now().weekday);
    
    List<String> needsAttendancePrompt = [];
    List<String> justStarted = [];

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
        }
      }
      // Ended
      else if (nowStr.compareTo(end) > 0) {
        final String status = task['status'] ?? 'todo';
        if (!['done', 'missed', 'ended'].contains(status)) {
          task['status'] = 'ended';
          needsAttendancePrompt.add(task['id']);
        }
      }
    }
    return SyncResult(needsAttendance: needsAttendancePrompt, justStarted: justStarted);
  }

  String _getDayAbbreviation(int weekday) {
    // DateTime.weekday: 1 = Mon, 7 = Sun
    return ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'][weekday - 1];
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
  XPResult({required this.newLevel, required this.gainedXP, required this.leveledUp});
}

class ProgressResult {
  final int currentXP;
  final int requiredXP;
  final double percentage;
  ProgressResult({required this.currentXP, required this.requiredXP, required this.percentage});
}
