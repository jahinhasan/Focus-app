import 'package:flutter/material.dart';
import 'logic_port.dart';

class DashboardScreen extends StatelessWidget {
  final FocusData appData;

  DashboardScreen({required this.appData});

  @override
  Widget build(BuildContext context) {
    var progress = appData.getLevelProgress();

    return Scaffold(
      backgroundColor: Color(0xFF0F0F1A),
      body: CustomScrollView(
        slivers: [
          // --- SLEEK APP BAR ---
          SliverAppBar(
            expandedHeight: 180.0,
            floating: false,
            pinned: true,
            backgroundColor: Color(0xFF161625),
            flexibleSpace: FlexibleSpaceBar(
              background: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [Color(0xFF161625), Color(0xFF0F0F1A)],
                  ),
                ),
                child: Padding(
                  padding: const EdgeInsets.only(left: 20, right: 20, top: 60),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text("Level ${appData.level}", 
                                style: TextStyle(color: Colors.white, fontSize: 32, fontWeight: FontWeight.bold)),
                              Text("${appData.xp} TOTAL XP", 
                                style: TextStyle(color: Colors.blueAccent, fontSize: 13, letterSpacing: 1.2, fontWeight: FontWeight.bold)),
                            ],
                          ),
                          Container(
                            padding: EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: Colors.blueAccent.withOpacity(0.1),
                              shape: BoxShape.circle,
                            ),
                            child: Icon(Icons.bolt, color: Colors.blueAccent, size: 30),
                          )
                        ],
                      ),
                      SizedBox(height: 20),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(10),
                        child: LinearProgressIndicator(
                          value: progress.percentage,
                          minHeight: 10,
                          backgroundColor: Colors.white.withOpacity(0.05),
                          valueColor: AlwaysStoppedAnimation<Color>(Colors.blueAccent),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),

          // --- TASK LIST SECTION ---
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.all(20.0),
              child: Text("TODAY'S MISSIONS", 
                style: TextStyle(color: Colors.white70, fontSize: 12, fontWeight: FontWeight.bold, letterSpacing: 1.5)),
            ),
          ),

          SliverList(
            delegate: SliverChildBuilderDelegate(
              (context, index) {
                final task = appData.tasks[index];
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 6),
                  child: Container(
                    decoration: BoxDecoration(
                      color: Color(0xFF1C1C2D),
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(color: Colors.white.withOpacity(0.03)),
                    ),
                    child: ListTile(
                      contentPadding: EdgeInsets.all(15),
                      leading: Container(
                        padding: EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: task['type'] == 'class' ? Colors.purple.withOpacity(0.1) : Colors.green.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Icon(
                          task['type'] == 'class' ? Icons.school : Icons.assignment,
                          color: task['type'] == 'class' ? Colors.purpleAccent : Colors.greenAccent,
                        ),
                      ),
                      title: Text(task['name'], 
                        style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
                      subtitle: Text(task['status']?.toUpperCase() ?? "PENDING", 
                        style: TextStyle(color: Colors.white38, fontSize: 11, letterSpacing: 0.5)),
                      trailing: Icon(Icons.chevron_right, color: Colors.white24),
                    ),
                  ),
                );
              },
              childCount: appData.tasks.length,
            ),
          ),
        ],
      ),
    );
  }
}
