import 'dart:convert';
import 'dart:io';
import 'package:path_provider/path_provider.dart';
import 'package:flutter/foundation.dart';

/// Manages Offline AI "Knowledge Cache".
/// Stores successful (Question, Answer) pairs and recalls them via fuzzy matching.
class OfflineBrain {
  static const String _fileName = 'offline_brain.json';

  // Singleton
  static final OfflineBrain _instance = OfflineBrain._internal();
  factory OfflineBrain() => _instance;
  OfflineBrain._internal();

  List<Map<String, dynamic>> _knowledgeBase = [];
  bool _isLoaded = false;

  Directory? _mockDir;

  @visibleForTesting
  set mockDirectory(Directory d) => _mockDir = d;

  /// Load brain from disk
  Future<void> load() async {
    if (_isLoaded) return;
    try {
      final dir = _mockDir ?? await getApplicationDocumentsDirectory();
      final file = File('${dir.path}/$_fileName');
      if (await file.exists()) {
        final jsonStr = await file.readAsString();
        final List<dynamic> raw = jsonDecode(jsonStr);
        _knowledgeBase = raw.cast<Map<String, dynamic>>();
      }
      _isLoaded = true;
    } catch (e) {
      debugPrint("OfflineBrain Load Error: $e");
    }
  }

  /// Save brain to disk
  Future<void> _save() async {
    try {
      final dir = _mockDir ?? await getApplicationDocumentsDirectory();
      final file = File('${dir.path}/$_fileName');
      await file.writeAsString(jsonEncode(_knowledgeBase));
    } catch (e) {
      debugPrint("OfflineBrain Save Error: $e");
    }
  }

  /// Learn from a successful interaction
  Future<void> learn(String input, Map<String, dynamic> response) async {
    await load();

    // Normalize input
    final cleanInput = input.trim().toLowerCase();

    // Check if we already know this (exact match) to avoid dupes
    // (Simple check, could be optimized)
    final exists = _knowledgeBase.any((e) => e['input'] == cleanInput);

    if (!exists) {
      _knowledgeBase.add({
        'input': cleanInput,
        'response': response,
        'ts': DateTime.now().millisecondsSinceEpoch
      });

      // Cap size to 500 entries to keep it lightweight
      if (_knowledgeBase.length > 500) {
        _knowledgeBase.removeAt(0); // Remove oldest
      }

      await _save();
      debugPrint("OfflineBrain Learned: $cleanInput");
    }
  }

  /// Recall closest match from database
  Future<Map<String, dynamic>?> recall(String input) async {
    await load();
    if (_knowledgeBase.isEmpty) return null;

    final query = input.trim().toLowerCase();
    Map<String, dynamic>? bestMatch;
    double highestScore = 0.0;

    for (var entry in _knowledgeBase) {
      final storedInput = entry['input'] as String;
      final score = _jaccardSimilarity(query, storedInput);

      if (score > highestScore) {
        highestScore = score;
        bestMatch = entry;
      }
    }

    // Threshold check (e.g. 0.4 for very rough match, adjust as needed)
    if (highestScore > 0.4 && bestMatch != null) {
      debugPrint("OfflineBrain Recall ($highestScore): ${bestMatch['input']}");
      final response = Map<String, dynamic>.from(bestMatch['response']);
      response['message'] =
          (response['message'] ?? "") + "\n\n(Offline Recall)";
      return response;
    }

    return null;
  }

  /// Simple Jaccard Similarity (Word Overlap)
  double _jaccardSimilarity(String s1, String s2) {
    if (s1 == s2) return 1.0;

    final punc = RegExp(r'[^\w\s]');
    final set1 =
        s1.replaceAll(punc, '').split(' ').where((e) => e.isNotEmpty).toSet();
    final set2 =
        s2.replaceAll(punc, '').split(' ').where((e) => e.isNotEmpty).toSet();

    final intersection = set1.intersection(set2).length;
    final union = set1.union(set2).length;

    if (union == 0) return 0.0;
    return intersection / union;
  }

  /// Learn patterns from a list of classes
  Future<void> learnPatterns(List<dynamic> classes) async {
    await load();

    final patterns =
        _knowledgeBase.firstWhere((e) => e['type'] == 'patterns', orElse: () {
      final newP = {
        'type': 'patterns',
        'titles': <String>[],
        'times': <String>[]
      };
      _knowledgeBase.add(newP);
      return newP;
    });

    final titles = List<String>.from(patterns['titles'] ?? []);
    final times = List<String>.from(patterns['times'] ?? []);
    bool changed = false;

    for (var c in classes) {
      if (c['title'] != null && !titles.contains(c['title'])) {
        titles.add(c['title']);
        changed = true;
      }
      final s = c['schedule'];
      if (s != null && s['start'] != null && s['end'] != null) {
        final t = "${s['start']}-${s['end']}";
        if (!times.contains(t)) {
          times.add(t);
          changed = true;
        }
      }
    }

    if (changed) {
      debugPrint("OfflineBrain Learned Patterns: $titles");
      patterns['titles'] = titles;
      patterns['times'] = times;
      await _save();
    }
  }

  /// Attempt to parse text using learned patterns
  Future<List<Map<String, dynamic>>> attemptOfflineParsing(String text) async {
    await load();
    final patterns = _knowledgeBase.firstWhere((e) => e['type'] == 'patterns',
        orElse: () => {'type': 'patterns', 'titles': [], 'times': []});

    final titles = List<String>.from(patterns['titles'] ?? []);
    final lowerText = text.toLowerCase();

    List<Map<String, dynamic>> found = [];

    for (var title in titles) {
      if (lowerText.contains(title.toLowerCase())) {
        // Found a known class!
        // Try to find days
        List<String> days = [];
        for (var d in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']) {
          if (lowerText.contains(d)) days.add(d);
        }

        // Try to find time (very simple regex for now)
        String start = "09:00";
        String end = "10:00";
        final timeMatch =
            RegExp(r"(\d{1,2}:\d{2}).*?(\d{1,2}:\d{2})").firstMatch(lowerText);
        if (timeMatch != null) {
          start = timeMatch.group(1)!;
          end = timeMatch.group(2)!;
        }

        found.add({
          "title": title,
          "days": days.isNotEmpty ? days : ["mon"],
          "start": start,
          "end": end
        });
      }
    }

    return found;
  }
}
