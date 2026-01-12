import 'package:flutter/material.dart';
import 'logic_port.dart';

class VaultScreen extends StatefulWidget {
  final FocusData appData;
  const VaultScreen({super.key, required this.appData});

  @override
  State<VaultScreen> createState() => _VaultScreenState();
}

class _VaultScreenState extends State<VaultScreen> {
  @override
  Widget build(BuildContext context) {
    final subjects = widget.appData.subjects.keys.toList();

    return Scaffold(
      backgroundColor: const Color(0xFF0F0F1A),
      appBar: AppBar(
        title: const Text("SUBJECT VAULT",
            style: TextStyle(
                letterSpacing: 2, fontSize: 16, fontWeight: FontWeight.bold)),
        backgroundColor: const Color(0xFF161625),
        elevation: 0,
        centerTitle: true,
      ),
      body: subjects.isEmpty
          ? const Center(
              child: Text(
                  "No subjects yet.\nCreate one to store notes & files.",
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.white30)))
          : ListView.builder(
              padding: const EdgeInsets.all(15),
              itemCount: subjects.length,
              itemBuilder: (context, index) {
                final subject = subjects[index];
                final data = widget.appData.subjects[subject];
                final docCount = (data['documents'] as List? ?? []).length;

                return SubjectFolderCard(
                  subject: subject,
                  docCount: docCount,
                  onTap: () {
                    Navigator.push(
                        context,
                        MaterialPageRoute(
                            builder: (context) => SubjectDetailScreen(
                                  appData: widget.appData,
                                  subjectName: subject,
                                )));
                  },
                );
              },
            ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _showAddSubjectDialog(context),
        backgroundColor: Colors.blueAccent,
        child: const Icon(Icons.create_new_folder, color: Colors.white),
      ),
    );
  }

  void _showAddSubjectDialog(BuildContext context) {
    final controller = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1C1C2D),
        title: const Text("New Subject", style: TextStyle(color: Colors.white)),
        content: TextField(
          controller: controller,
          style: const TextStyle(color: Colors.white),
          decoration: const InputDecoration(hintText: "Enter subject name..."),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx), child: const Text("Cancel")),
          ElevatedButton(
            onPressed: () {
              if (controller.text.isNotEmpty) {
                setState(() {
                  widget.appData.addSubject(controller.text);
                });
                Navigator.pop(ctx);
              }
            },
            child: const Text("Create"),
          )
        ],
      ),
    );
  }
}

class SubjectFolderCard extends StatelessWidget {
  final String subject;
  final int docCount;
  final VoidCallback onTap;

  const SubjectFolderCard(
      {super.key,
      required this.subject,
      required this.docCount,
      required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: const Color(0xFF1C1C2D),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withValues(alpha: 0.03)),
      ),
      child: ListTile(
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
        leading: const Icon(Icons.folder, color: Colors.blueAccent, size: 32),
        title: Text(subject,
            style: const TextStyle(
                color: Colors.white, fontWeight: FontWeight.bold)),
        subtitle: Text("$docCount files",
            style: const TextStyle(color: Colors.white38, fontSize: 12)),
        trailing: const Icon(Icons.chevron_right, color: Colors.white24),
        onTap: onTap,
      ),
    );
  }
}

class SubjectDetailScreen extends StatefulWidget {
  final FocusData appData;
  final String subjectName;
  const SubjectDetailScreen(
      {super.key, required this.appData, required this.subjectName});

  @override
  State<SubjectDetailScreen> createState() => _SubjectDetailScreenState();
}

class _SubjectDetailScreenState extends State<SubjectDetailScreen> {
  @override
  Widget build(BuildContext context) {
    final data = widget.appData.subjects[widget.subjectName];
    if (data == null) return const Scaffold(); // Should not happen

    final documents = (data['documents'] as List? ?? []);

    return Scaffold(
      backgroundColor: const Color(0xFF0F0F1A),
      appBar: AppBar(
        title: Text(widget.subjectName),
        backgroundColor: const Color(0xFF161625),
        actions: [
          IconButton(
            icon: const Icon(Icons.delete_outline),
            onPressed: () {
              // Delete Subject
              widget.appData.deleteSubject(widget.subjectName);
              Navigator.pop(context);
            },
          )
        ],
      ),
      body: documents.isEmpty
          ? const Center(
              child: Text("No documents yet.\nUse 'Add' to upload.",
                  style: TextStyle(color: Colors.white24)))
          : ListView.builder(
              itemCount: documents.length,
              itemBuilder: (context, index) {
                final doc = documents[index].toString();
                return ListTile(
                  leading: const Icon(Icons.insert_drive_file,
                      color: Colors.white54),
                  title: Text(doc.split('/').last,
                      style: const TextStyle(color: Colors.white)),
                  subtitle: Text(doc,
                      style:
                          const TextStyle(color: Colors.white38, fontSize: 10)),
                );
              },
            ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: Colors.purpleAccent,
        child: const Icon(Icons.add),
        onPressed: () {
          // Placeholder for adding file
          _showAddFileDialog(context);
        },
      ),
    );
  }

  void _showAddFileDialog(BuildContext context) {
    final controller = TextEditingController();
    showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
              backgroundColor: const Color(0xFF1C1C2D),
              title: const Text("Add Document",
                  style: TextStyle(color: Colors.white)),
              content: TextField(
                controller: controller,
                style: const TextStyle(color: Colors.white),
                decoration: const InputDecoration(
                    hintText: "File path or Note title..."),
              ),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(ctx),
                    child: const Text("Cancel")),
                ElevatedButton(
                  onPressed: () {
                    if (controller.text.isNotEmpty) {
                      setState(() {
                        widget.appData
                            .addVaultFile(widget.subjectName, controller.text);
                      });
                      Navigator.pop(ctx);
                    }
                  },
                  child: const Text("Add"),
                )
              ],
            ));
  }
}
