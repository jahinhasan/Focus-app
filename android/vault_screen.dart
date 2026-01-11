import 'package:flutter/material.dart';
import 'logic_port.dart';

class VaultScreen extends StatefulWidget {
  final FocusData appData;
  VaultScreen({required this.appData});

  @override
  _VaultScreenState createState() => _VaultScreenState();
}

class _VaultScreenState extends State<VaultScreen> {
  @override
  Widget build(BuildContext context) {
    // Group tasks by subject/tag if applicable, or show subjects/vault data
    // For now, let's show a clean categorized list of 'Subjects'
    List<String> subjects = ['Math', 'Computer Science', 'Physics', 'History'];

    return Scaffold(
      backgroundColor: Color(0xFF0F0F1A),
      appBar: AppBar(
        title: Text("SUBJECT VAULT", style: TextStyle(letterSpacing: 2, fontSize: 16, fontWeight: FontWeight.bold)),
        backgroundColor: Color(0xFF161625),
        elevation: 0,
        centerTitle: true,
      ),
      body: ListView.builder(
        padding: EdgeInsets.all(15),
        itemCount: subjects.length,
        itemBuilder: (context, index) {
          return SubjectFolderCard(subject: subjects[index]);
        },
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {}, // Logic to add new subject
        backgroundColor: Colors.blueAccent,
        child: Icon(Icons.create_new_folder, color: Colors.white),
      ),
    );
  }
}

class SubjectFolderCard extends StatelessWidget {
  final String subject;
  SubjectFolderCard({required this.subject});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: Color(0xFF1C1C2D),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white.withOpacity(0.03)),
      ),
      child: ListTile(
        contentPadding: EdgeInsets.symmetric(horizontal: 20, vertical: 10),
        leading: Icon(Icons.folder, color: Colors.blueAccent, size: 32),
        title: Text(subject, style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        subtitle: Text("0 files • 0 subtasks", style: TextStyle(color: Colors.white38, fontSize: 12)),
        trailing: Icon(Icons.chevron_right, color: Colors.white24),
        onTap: () {
          // Navigate to subject detail
        },
      ),
    );
  }
}
