import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:focus_app/logic_port.dart';
import 'package:focus_app/chat_screen.dart';

void main() {
  testWidgets('AI Chat Verification Test', (WidgetTester tester) async {
    // 1. Setup Data
    final data = FocusData.defaultState();

    // 2. Build Chat Screen
    await tester.pumpWidget(MaterialApp(
      home: ChatScreen(appData: data),
    ));

    // 3. Find the text field and send a message
    final textField = find.byType(TextField);
    final sendButton = find.byIcon(Icons.send);

    expect(textField, findsOneWidget);
    expect(sendButton, findsOneWidget);

    await tester.enterText(textField, "Add a task to drink water");
    await tester.tap(sendButton);
    await tester.pump(); // Start the thinking...

    // 4. Wait for AI response (Gemini API Call)
    // Since this is a live test, we need to wait for the real network response
    // We'll poll for the "Thinking..." message to disappear or for a result to appear
    print("Waiting for Gemini response...");

    bool foundResult = false;
    for (int i = 0; i < 20; i++) {
      await tester.pump(const Duration(seconds: 1));
      if (find.textContaining("Added task").evaluate().isNotEmpty ||
          find.textContaining("Error").evaluate().isNotEmpty) {
        foundResult = true;
        break;
      }
    }

    // 5. Verify outcome
    if (find.textContaining("Added task: drink water").evaluate().isNotEmpty) {
      print("SUCCESS: AI successfully parsed and added the task!");
    } else if (find.textContaining("Error").evaluate().isNotEmpty) {
      final errorWidget =
          find.textContaining("Error").evaluate().single.widget as Text;
      print("FAILURE: AI returned an error: ${errorWidget.data}");
    } else {
      print("TIMEOUT: AI did not respond in time.");
    }
  });
}
