import 'package:flutter/material.dart';
import 'logic_port.dart';
import 'dashboard.dart';
import 'timer_screen.dart';
import 'vault_screen.dart';
import 'routine_screen.dart';
import 'chat_screen.dart';

void main() {
  runApp(const FocusApp());
}

class FocusApp extends StatelessWidget {
  final FocusData? initialData;

  const FocusApp({super.key, this.initialData});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Focus Dashboard',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        primaryColor: const Color(0xFF0F0F1A),
        scaffoldBackgroundColor: const Color(0xFF0F0F1A),
        fontFamily: 'Inter',
        colorScheme: const ColorScheme.dark(
          primary: Colors.blueAccent,
          secondary: Colors.purpleAccent,
          surface: Color(0xFF161625),
        ),
      ),
      home: MainNavigation(initialData: initialData),
    );
  }
}

class MainNavigation extends StatefulWidget {
  final FocusData? initialData;
  const MainNavigation({super.key, this.initialData});

  @override
  State<MainNavigation> createState() => _MainNavigationState();
}

class _MainNavigationState extends State<MainNavigation> {
  int _selectedIndex = 0;
  FocusData? appData; // Nullable until loaded
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    if (widget.initialData != null) {
      appData = widget.initialData;
      isLoading = false;
    } else {
      _loadData();
    }
  }

  Future<void> _loadData() async {
    final data = await FocusData.load();
    // Run automation on startup
    data.processDailyAutomation();
    if (mounted) {
      setState(() {
        appData = data;
        isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (isLoading || appData == null) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    // List of integrated screens
    final List<Widget> screens = [
      DashboardScreen(appData: appData!),
      RoutineScreen(appData: appData!),
      ChatScreen(appData: appData!),
      VaultScreen(appData: appData!),
      TimerScreen(appData: appData!),
    ];

    return Scaffold(
      body: screens[_selectedIndex],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        onTap: (index) => setState(() => _selectedIndex = index),
        backgroundColor: const Color(0xFF161625),
        selectedItemColor: Colors.blueAccent,
        unselectedItemColor: Colors.white30,
        type: BottomNavigationBarType.fixed,
        items: const [
          BottomNavigationBarItem(
              icon: Icon(Icons.dashboard_rounded), label: 'Today'),
          BottomNavigationBarItem(
              icon: Icon(Icons.calendar_view_week_rounded), label: 'Routine'),
          BottomNavigationBarItem(
              icon: Icon(Icons.chat_bubble_outline), label: 'AI'),
          BottomNavigationBarItem(
              icon: Icon(Icons.folder_copy_rounded), label: 'Vault'),
          BottomNavigationBarItem(
              icon: Icon(Icons.timer_rounded), label: 'Focus'),
        ],
      ),
    );
  }
}
