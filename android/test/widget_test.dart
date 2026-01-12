import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:focus_app/main.dart';
import 'package:focus_app/logic_port.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const MethodChannel channel =
      MethodChannel('plugins.flutter.io/path_provider');

  setUpAll(() async {
    SharedPreferences.setMockInitialValues({});
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (MethodCall methodCall) async {
      return ".";
    });
  });

  testWidgets('Focus App Feature Verification', (WidgetTester tester) async {
    // 1. Prepare Data
    final testData = FocusData.defaultState();

    // 2. Launch App with Injected Data
    await tester.pumpWidget(FocusApp(initialData: testData));
    await tester.pumpAndSettle(); // Should resolve immediately

    // --- DASHBOARD CHECK ---
    expect(find.textContaining('Level'), findsOneWidget); // XP Bar
    expect(find.byIcon(Icons.add), findsOneWidget); // FAB exists

    // 2. Add Habit
    await tester.tap(find.byIcon(Icons.add));
    await tester.pumpAndSettle(); // Open Bottom Sheet

    expect(find.text('Habit'), findsOneWidget);
    await tester.tap(find.text('Habit'));
    await tester.pumpAndSettle(); // Open Dialog

    await tester.enterText(find.byType(TextField), 'Drink Water');
    // Use specific finder for Dialog button
    await tester.tap(find.widgetWithText(ElevatedButton, 'Add'));
    await tester.pumpAndSettle();

    // Verify Habit on Dashboard (using direct data check if UI fails, or find text)
    expect(find.text('Drink Water'), findsOneWidget);

    // 3. Add Task
    await tester.tap(find.byIcon(Icons.add));
    await tester.pumpAndSettle();
    expect(find.text('Task'), findsOneWidget);
    await tester.tap(find.text('Task'));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), 'Test Task');
    expect(find.text('Schedule: '), findsOneWidget);
    await tester.tap(find.text('Create'));
    await tester.pumpAndSettle();

    expect(find.text('Test Task'), findsOneWidget);

    // --- ROUTINE CHECK ---
    await tester.tap(find.byIcon(Icons.calendar_view_week_rounded));
    await tester.pumpAndSettle();

    expect(find.text('Weekly Schedule'), findsOneWidget);

    // Add Class
    await tester.tap(find.byIcon(Icons.add));
    await tester.pumpAndSettle();

    expect(find.text('Manual Entry'), findsOneWidget);
    expect(find.text('Import with Gemini AI'), findsOneWidget);

    await tester.tap(find.text('Manual Entry'));
    await tester.pumpAndSettle();
    expect(find.text('New Class'), findsOneWidget);
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    // --- VAULT CHECK ---
    await tester.tap(find.byIcon(Icons.folder_copy_rounded));
    await tester.pumpAndSettle();

    expect(find.text('Vault'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.create_new_folder));
    await tester.pumpAndSettle();
    expect(find.text('New Subject'), findsOneWidget);

    await tester.enterText(find.byType(TextField), 'Physics');
    await tester.tap(find.text('Create'));
    await tester.pumpAndSettle();

    expect(find.text('Physics'), findsOneWidget);
  });
}
