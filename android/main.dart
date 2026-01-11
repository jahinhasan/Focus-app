import 'package:flutter/material.dart';
import 'logic_port.dart';
import 'dashboard.dart';
import 'timer_screen.dart';
import 'vault_screen.dart';

void main() {
  runApp(FocusApp());
}

class FocusApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Focus Dashboard',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        primaryColor: Color(0xFF0F0F1A),
        scaffoldBackgroundColor: Color(0xFF0F0F1A),
        fontFamily: 'Inter', // Suggesting a modern font
      ),
      home: MainNavigation(),
    );
  }
}

class MainNavigation extends StatefulWidget {
  @override
  _MainNavigationState createState() => _MainNavigationState();
}

class _MainNavigationState extends State<MainNavigation> {
  int _selectedIndex = 0;
  late FocusData appData;

  @override
  void initState() {
    super.initState();
    appData = FocusData.defaultState();
    appData.processDailyAutomation();
  }

  @override
  Widget build(BuildContext context) {
    // List of integrated screens
    final List<Widget> _screens = [
      DashboardScreen(appData: appData),
      VaultScreen(appData: appData),
      TimerScreen(),
    ];

    return Scaffold(
      body: _screens[_selectedIndex],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        onTap: (index) => setState(() => _selectedIndex = index),
        backgroundColor: Color(0xFF161625),
        selectedItemColor: Colors.blueAccent,
        unselectedItemColor: Colors.white30,
        type: BottomNavigationBarType.fixed,
        items: [
          BottomNavigationBarItem(icon: Icon(Icons.dashboard_rounded), label: 'Today'),
          BottomNavigationBarItem(icon: Icon(Icons.folder_copy_rounded), label: 'Vault'),
          BottomNavigationBarItem(icon: Icon(Icons.timer_rounded), label: 'Focus'),
        ],
      ),
    );
  }
}
