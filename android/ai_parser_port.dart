import 'package:http/http.dart' as http;
import 'dart:convert';

/// Mobile AI Assistant Engine
/// This handles parsing natural language into tasks/classes via local regex 
/// and optional API calls to Groq.
class MobileAIParser {
  final String? groqApiKey;

  MobileAIParser({this.groqApiKey});

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

    // 2. If no local match and API key is present, use LLM
    if (groqApiKey != null) {
      return await _queryGroq(input);
    }

    return {'intent': 'unknown', 'message': "I'm not sure what you mean."};
  }

  Future<Map<String, dynamic>> _queryGroq(String input) async {
    final url = Uri.parse('https://api.groq.com/openai/v1/chat/completions');
    try {
      final response = await http.post(
        url,
        headers: {
          'Authorization': 'Bearer $groqApiKey',
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'model': 'mixtral-8x7b-32768',
          'messages': [
            {'role': 'system', 'content': 'Parse focus app intent. Return JSON: {intent: add_task/add_class, data: {}}'},
            {'role': 'user', 'content': input}
          ],
        }),
      );

      if (response.statusCode == 200) {
        final body = jsonDecode(response.body);
        return jsonDecode(body['choices'][0]['message']['content']);
      }
    } catch (e) {
      print("AI Error: $e");
    }
    return {'intent': 'error'};
  }
}
