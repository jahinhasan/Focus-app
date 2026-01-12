import 'package:flutter_test/flutter_test.dart';
import 'package:focus_app/offline_brain.dart';
import 'dart:io';

void main() {
  late Directory tempDir;

  setUp(() async {
    tempDir = await Directory.systemTemp.createTemp();
    OfflineBrain().mockDirectory = tempDir;
  });

  tearDown(() async {
    await tempDir.delete(recursive: true);
  });

  test('Offline Brain Learning and Recall', () async {
    final brain = OfflineBrain();

    // 1. Learn
    const input = "How much XP do I have?";
    final response = {"intent": "query_stats", "message": "You have 500 XP."};

    await brain.learn(input, response);

    // 2. Recall (Exact Match)
    final exact = await brain.recall("How much XP do I have?");
    expect(exact, isNotNull);
    expect(exact!['intent'], "query_stats");

    // 3. Recall (Fuzzy Match - "have I" vs "do I have")
    final fuzzy = await brain.recall("How much XP have I?");
    expect(fuzzy, isNotNull);
    expect(fuzzy!['message'], contains("(Offline Recall)"));

    // 4. No Match
    final unknown = await brain.recall("What is the meaning of life?");
    expect(unknown, isNull);
  });
}
