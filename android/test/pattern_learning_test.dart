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

  test('Offline Pattern Learning and Parsing', () async {
    final brain = OfflineBrain();

    // 1. Train with a "successful" AI response (simulated)
    const onlineResult = [
      {
        "title": "Advanced Physics",
        "schedule": {"start": "10:00", "end": "11:30"}
      }
    ];
    await brain.learnPatterns(onlineResult);

    // 2. Attempt Offline Parsing on RAW TEXT
    // The text contains the known title "Advanced Physics" and a time range.
    const rawInput =
        "I have Advanced Physics class tomorrow from 10:00 to 11:30";

    final result = await brain.attemptOfflineParsing(rawInput);

    expect(result, isNotEmpty);
    expect(result.first['title'], "Advanced Physics");
    expect(result.first['start'], "10:00");
    expect(result.first['end'], "11:30");

    // 3. Verify Unknown Title is NOT picked up
    const unknownInput = "I have Underwater Basket Weaving tomorrow.";
    final unknownResult = await brain.attemptOfflineParsing(unknownInput);
    expect(unknownResult, isEmpty);
  });
}
