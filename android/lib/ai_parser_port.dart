import 'package:google_generative_ai/google_generative_ai.dart';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'offline_brain.dart';

/// Mobile AI Assistant Engine
/// Uses Google's Gemini 1.5 Flash for fast, efficient intent parsing.
class MobileAIParser {
  final String? apiKey;
  GenerativeModel? _model;

  MobileAIParser({this.apiKey}) {
    // HARDCORE API KEY - Updated per user request
    const String hardcoreKey = "AIzaSyC4qYFPi-TWbOo_bh8NFYx-jifZPoW7lfo";

    _model = GenerativeModel(
      model: 'gemini-1.5-flash',
      apiKey: hardcoreKey,
      generationConfig: GenerationConfig(responseMimeType: 'application/json'),
    );
  }

  /// Main parsing entry point
  /// Returns a Map containing the detected intent and data
  Future<Map<String, dynamic>> parse(String input) async {
    // 1. Check for basic "Add Task" patterns locally (Fast)
    final taskMatch = RegExp(r"add task (.+)").firstMatch(input.toLowerCase());
    if (taskMatch != null) {
      return {
        'intent': 'add_task',
        'data': {'name': taskMatch.group(1), 'type': 'task'}
      };
    }

    // 2. If no local match and model is ready, use LLM
    if (_model != null) {
      return await _queryGemini(input);
    }

    return {
      'intent': 'unknown',
      'message': "I'm not sure what you mean (API Key missing)."
    };
  }

  /// Breaks down a task into subtasks
  Future<List<String>> generateSubtasks(String taskTitle) async {
    if (_model == null) return [];

    try {
      final prompt =
          'Break down this task into 3-5 actionable subtasks: "$taskTitle". Output JSON: {"subtasks": ["subtask 1", "subtask 2"]}';
      final content = [Content.text(prompt)];
      final response = await _model!.generateContent(content);

      if (response.text != null) {
        String jsonStr = response.text!
            .replaceAll('```json', '')
            .replaceAll('```', '')
            .trim();
        final data = jsonDecode(jsonStr);
        return List<String>.from(data['subtasks'] ?? []);
      }
    } catch (e) {
      debugPrint("Subtask Gen Error: $e");
    }
    return [];
  }

  Future<List<Map<String, dynamic>>> parseRoutine(String input,
      {Uint8List? imageBytes}) async {
    // Offline / No Key Mode
    if (_model == null) {
      final offline = await OfflineBrain().attemptOfflineParsing(input);
      if (offline.isNotEmpty) return _finalizeClasses(offline);
      return [];
    }

    try {
      final promptText = '''
    Analyze this routine/schedule and extract the classes.
    Return ONLY a JSON list of objects with these fields:
    - title (string)
    - days (list of strings, use abbreviations: mon, tue, wed, thu, fri, sat, sun)
    - start (string HH:MM 24hr format)
    - end (string HH:MM 24hr format)

    Context: $input
    ''';

      final List<Part> parts = [TextPart(promptText)];
      if (imageBytes != null) {
        parts.add(DataPart('image/jpeg', imageBytes));
      }

      final content = [Content.multi(parts)];
      final response = await _model!.generateContent(content);
      final text = response.text;

      if (text != null) {
        String jsonStr =
            text.replaceAll('```json', '').replaceAll('```', '').trim();
        final List<dynamic> json = jsonDecode(jsonStr);

        // Learn Patterns Hook
        OfflineBrain().learnPatterns(json);

        return _finalizeClasses(json.cast<Map<String, dynamic>>());
      }
    } catch (e) {
      debugPrint("AI Routine Parse Error: $e");
      // Fallback
      final offline = await OfflineBrain().attemptOfflineParsing(input);
      if (offline.isNotEmpty) return _finalizeClasses(offline);
    }
    return [];
  }

  List<Map<String, dynamic>> _finalizeClasses(List<Map<String, dynamic>> list) {
    return list
        .map((e) => {
              "id": DateTime.now().millisecondsSinceEpoch.toString() +
                  e['title'].hashCode.toString(),
              "type": "class",
              "title": e['title'],
              "schedule": {
                "days": e['days'] is List ? e['days'] : ["mon"],
                "start": e['start'],
                "end": e['end']
              },
              "status": "todo",
              "created_at": DateTime.now().toIso8601String().split('T')[0]
            })
        .toList();
  }

  Future<Map<String, dynamic>> _queryGemini(String input) async {
    try {
      final prompt = '''
      You are a productivity assistant for the "Focus Dashboard" app.
      Analyze the user's request and parse it into a structured JSON object.

      Supported Intents:
      1. "add_task": Create a new task. Data: {"name": "Task Title", "type": "task"}
      2. "add_class": Create a class. Data: {"name": "Subject", "type": "class", "days": ["mon", "wed"], "time": "09:00"}
      3. "query_stats": User asks about XP or Level. Data: {}
      4. "greeting": User says hi. Data: {}

      User Input: "$input"

      Return ONLY the JSON. Example:
      {"intent": "add_task", "data": {"name": "Buy Milk", "type": "task"}}
      ''';

      final content = [Content.text(prompt)];
      final response = await _model!.generateContent(content);

      if (response.text != null) {
        // Cleanup any potential markdown fencing if the model adds it (though mimeType json helps)
        String jsonStr = response.text!
            .replaceAll('```json', '')
            .replaceAll('```', '')
            .trim();
        final result = jsonDecode(jsonStr);

        // Silent Learning (Fire and forget)
        OfflineBrain().learn(input, result);

        return result;
      }
    } catch (e) {
      debugPrint("Gemini AI Error: $e");

      // Offline Recall
      final offlineResult = await OfflineBrain().recall(input);
      if (offlineResult != null) {
        return offlineResult;
      }

      return {'intent': 'unknown', 'message': "Error: $e"};
    }
    return {
      'intent': 'unknown',
      'message': "Sorry, I couldn't process that (Empty Response)."
    };
  }
}
