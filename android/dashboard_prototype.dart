import 'package:flutter/material.dart';
import 'logic_port.dart';

/// 📱 Focus Dashboard: Mobile Home Screen Prototype
/// This uses the FocusData logic we ported earlier.
class DashboardScreen extends StatefulWidget {
  @override
  _DashboardScreenState createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  late FocusData appData;

  @override
  void initState() {
    super.initState();
    // Initialize with default state (Mirroring Python load_data)
    appData = FocusData.defaultState();
    appData.processDailyAutomation();
  }

  @override
  Widget build(BuildContext context) {
    var progress = appData.getLevelProgress();

    return Scaffold(
      backgroundColor: Color(0xFF0F0F1A), // Sleek Dark Background
      body: SafeArea(
        child: Padding(
          padding: EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // --- XP & LEVEL HEADER (Glow UI) ---
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text("Level ${appData.level}", 
                        style: TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold)),
                      Text("${appData.xp} Total XP", 
                        style: TextStyle(color: Colors.white70, fontSize: 14)),
                    ],
                  ),
                  Icon(Icons.stars, color: Colors.blueAccent, size: 40),
                ],
              ),
              SizedBox(height: 10),
              // XP Progress Bar
              ClipRRect(
                borderRadius: BorderRadius.circular(10),
                child: LinearProgressIndicator(
                  value: progress.percentage,
                  backgroundColor: Colors.white10,
                  valueColor: AlwaysStoppedAnimation<Color>(Colors.blueAccent),
                  minHeight: 8,
                ),
              ),
              SizedBox(height: 30),

              // --- TODAY'S TASKS ---
              Text("Today's Focus", 
                style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w600)),
              SizedBox(height: 15),
              Expanded(
                child: ListView.builder(
                  itemCount: appData.tasks.length,
                  itemBuilder: (context, index) {
                    var task = appData.tasks[index];
                    return TaskCard(task: task);
                  },
                ),
              ),
            ],
          ),
        ),
      ),
      // --- MOBILE SIDEBAR (Bottom Nav on Phone) ---
      bottomNavigationBar: BottomNavigationBar(
        backgroundColor: Color(0xFF161625),
        selectedItemColor: Colors.blueAccent,
        unselectedItemColor: Colors.white38,
        items: [
          BottomNavigationBarItem(icon: Icon(Icons.today), label: "Today"),
          BottomNavigationBarItem(icon: Icon(Icons.calendar_month), label: "Routine"),
          BottomNavigationBarItem(icon: Icon(Icons.timer), label: "Focus"),
        ],
      ),
    );
  }
}

class TaskCard extends StatelessWidget {
  final Map<String, dynamic> task;
  TaskCard({required this.task});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: EdgeInsets.only(bottom: 12),
      padding: EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Color(0xFF1C1C2D),
        borderRadius: BorderRadius.circular(15),
        border: Border.all(color: Colors.white.withOpacity(0.05)),
      ),
      child: Row(
        children: [
          Icon(
            task['type'] == 'class' ? Icons.school : Icons.check_circle_outline,
            color: task['status'] == 'done' ? Colors.greenAccent : Colors.white30,
          ),
          SizedBox(width: 15),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(task['name'] ?? "Untitled Task", 
                style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
              if (task['schedule'] != null)
                Text("${task['schedule']['start']} - ${task['schedule']['end']}", 
                  style: TextStyle(color: Colors.white38, fontSize: 12)),
            ],
          ),
        ],
      ),
    );
  }
}
