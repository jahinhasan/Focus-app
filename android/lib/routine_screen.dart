import 'package:flutter/material.dart';
import 'logic_port.dart';
import 'ai_parser_port.dart';
import 'package:image_picker/image_picker.dart';

class RoutineScreen extends StatefulWidget {
  final FocusData appData;

  const RoutineScreen({super.key, required this.appData});

  @override
  State<RoutineScreen> createState() => _RoutineScreenState();
}

class _RoutineScreenState extends State<RoutineScreen> {
  late MobileAIParser _parser;

  @override
  void initState() {
    super.initState();
    _parser =
        MobileAIParser(apiKey: widget.appData.settings['gemini_api_key'] ?? "");
  }

  @override
  Widget build(BuildContext context) {
    // Organize classes by day
    final days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
    final dayNames = {
      'mon': 'Monday',
      'tue': 'Tuesday',
      'wed': 'Wednesday',
      'thu': 'Thursday',
      'fri': 'Friday',
      'sat': 'Saturday',
      'sun': 'Sunday'
    };

    final todayIndex = DateTime.now().weekday - 1;

    return Scaffold(
      backgroundColor: const Color(0xFF0F0F1A),
      appBar: AppBar(
        title: const Text("Weekly Schedule",
            style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: const Color(0xFF161625),
        elevation: 0,
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showAddMenu(context),
        backgroundColor: Colors.blueAccent,
        icon: const Icon(Icons.add),
        label: const Text("Add"),
      ),
      body: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: days.length,
        itemBuilder: (context, index) {
          final dayCode = days[index];
          final dayName = dayNames[dayCode]!;
          final isToday = index == todayIndex;

          // Filter classes for this day
          final classes = widget.appData.tasks.where((t) {
            if (t['type'] != 'class') return false;
            final sch = t['schedule'] ?? {};
            final d = sch['days'] ?? [];
            return d.contains(dayCode);
          }).toList();

          // Sort by start time
          classes.sort((a, b) {
            String startA = a['schedule']['start'] ?? '00:00';
            String startB = b['schedule']['start'] ?? '00:00';
            return startA.compareTo(startB);
          });

          if (classes.isEmpty) {
            return const SizedBox.shrink(); // Don't show empty days
          }

          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12.0),
                child: Row(
                  children: [
                    Text(dayName,
                        style: TextStyle(
                            color: isToday ? Colors.blueAccent : Colors.white70,
                            fontSize: 18,
                            fontWeight: FontWeight.bold)),
                    if (isToday)
                      Container(
                        margin: const EdgeInsets.only(left: 10),
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                            color: Colors.blueAccent.withValues(alpha: 0.2),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                                color:
                                    Colors.blueAccent.withValues(alpha: 0.5))),
                        child: const Text("TODAY",
                            style: TextStyle(
                                color: Colors.blueAccent,
                                fontSize: 10,
                                fontWeight: FontWeight.bold)),
                      )
                  ],
                ),
              ),
              ...classes.map((c) => _buildClassCard(c, isToday)),
              const SizedBox(height: 10),
            ],
          );
        },
      ),
    );
  }

  void _showAddMenu(BuildContext context) {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF1C1C2D),
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.edit, color: Colors.blueAccent),
              title: const Text("Manual Entry",
                  style: TextStyle(color: Colors.white)),
              onTap: () {
                Navigator.pop(ctx);
                _showAddClassDialog(context);
              },
            ),
            ListTile(
              leading:
                  const Icon(Icons.auto_awesome, color: Colors.purpleAccent),
              title: const Text("Import with Gemini AI",
                  style: TextStyle(color: Colors.white)),
              subtitle: const Text("Paste text or upload image",
                  style: TextStyle(color: Colors.white38, fontSize: 12)),
              onTap: () {
                Navigator.pop(ctx);
                _showImportDialog(context);
              },
            ),
          ],
        ),
      ),
    );
  }

  void _showImportDialog(BuildContext context) {
    final textController = TextEditingController();
    bool isLoading = false;

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          backgroundColor: const Color(0xFF1C1C2D),
          title: const Text("Import Schedule",
              style: TextStyle(color: Colors.white)),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (isLoading)
                const CircularProgressIndicator()
              else ...[
                TextField(
                  controller: textController,
                  maxLines: 4,
                  style: const TextStyle(color: Colors.white),
                  decoration: const InputDecoration(
                    hintText: "Paste your routine here...",
                    hintStyle: TextStyle(color: Colors.white24),
                    filled: true,
                    fillColor: Color(0xFF252540),
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 15),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: [
                    ElevatedButton.icon(
                      icon: const Icon(Icons.image),
                      label:
                          const Text("Gallery", style: TextStyle(fontSize: 10)),
                      style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.white10),
                      onPressed: () async {
                        _processImage(ImageSource.gallery, setDialogState, ctx);
                      },
                    ),
                    ElevatedButton.icon(
                      icon: const Icon(Icons.camera_alt),
                      label:
                          const Text("Camera", style: TextStyle(fontSize: 10)),
                      style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.white10),
                      onPressed: () async {
                        _processImage(ImageSource.camera, setDialogState, ctx);
                      },
                    ),
                  ],
                ),
              ]
            ],
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text("Cancel")),
            if (!isLoading)
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.purpleAccent),
                onPressed: () async {
                  if (textController.text.isNotEmpty) {
                    setDialogState(() => isLoading = true);
                    try {
                      final classes =
                          await _parser.parseRoutine(textController.text);

                      if (!context.mounted) return;

                      _addClasses(classes);

                      if (ctx.mounted) Navigator.pop(ctx);
                    } catch (e) {
                      debugPrint("Parsing Error: $e");
                      if (ctx.mounted) Navigator.pop(ctx);
                    }
                  }
                },
                child: const Text("Parse Text"),
              )
          ],
        ),
      ),
    );
  }

  Future<void> _processImage(
      ImageSource source, Function setDialogState, BuildContext ctx) async {
    final picker = ImagePicker();
    final pickedFile = await picker.pickImage(source: source);
    if (pickedFile != null) {
      setDialogState(() => true); // Loading
      try {
        final bytes = await pickedFile.readAsBytes();
        if (!mounted) return;

        final classes =
            await _parser.parseRoutine("Extract from image", imageBytes: bytes);

        if (!mounted) return;

        _addClasses(classes);
        // Use the context from the method argument, assuming it matches the dialog
        if (ctx.mounted) {
          Navigator.pop(ctx);
        }
      } catch (e) {
        debugPrint("Image Parsing Error: $e");
        if (ctx.mounted) Navigator.pop(ctx);
      }
    }
  }

  void _addClasses(List<Map<String, dynamic>> newClasses) {
    setState(() {
      widget.appData.tasks.addAll(newClasses);
      widget.appData.save();
    });
    ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Imported ${newClasses.length} classes!")));
  }

  void _showAddClassDialog(BuildContext context) {
    final titleController = TextEditingController();
    final startController = TextEditingController(text: "09:00");
    final endController = TextEditingController(text: "10:30");
    List<String> selectedDays = [];

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          backgroundColor: const Color(0xFF1C1C2D),
          title: const Text("New Class", style: TextStyle(color: Colors.white)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: titleController,
                  style: const TextStyle(color: Colors.white),
                  decoration: const InputDecoration(
                      hintText: "Subject Name",
                      hintStyle: TextStyle(color: Colors.white24)),
                ),
                const SizedBox(height: 15),
                Wrap(
                  spacing: 5,
                  children: ['mon', 'tue', 'wed', 'thu', 'fri'].map((day) {
                    final isSelected = selectedDays.contains(day);
                    return FilterChip(
                      label: Text(day.toUpperCase()),
                      selected: isSelected,
                      onSelected: (val) => setDialogState(() {
                        if (val) {
                          selectedDays.add(day);
                        } else {
                          selectedDays.remove(day);
                        }
                      }),
                      selectedColor: Colors.purpleAccent.withValues(alpha: 0.3),
                      checkmarkColor: Colors.purpleAccent,
                      labelStyle: TextStyle(
                          color: isSelected
                              ? Colors.purpleAccent
                              : Colors.white54),
                      backgroundColor: Colors.transparent,
                      shape: StadiumBorder(
                          side: BorderSide(
                              color: isSelected
                                  ? Colors.purpleAccent
                                  : Colors.white10)),
                    );
                  }).toList(),
                ),
                const SizedBox(height: 15),
                Row(
                  children: [
                    Expanded(
                        child: TextField(
                            controller: startController,
                            style: const TextStyle(color: Colors.white),
                            decoration: const InputDecoration(
                                labelText: "Start",
                                labelStyle: TextStyle(color: Colors.white38)))),
                    const SizedBox(width: 10),
                    Expanded(
                        child: TextField(
                            controller: endController,
                            style: const TextStyle(color: Colors.white),
                            decoration: const InputDecoration(
                                labelText: "End",
                                labelStyle: TextStyle(color: Colors.white38)))),
                  ],
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              child:
                  const Text("Cancel", style: TextStyle(color: Colors.white38)),
              onPressed: () => Navigator.pop(ctx),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.purpleAccent),
              child: const Text("Add Class"),
              onPressed: () {
                if (titleController.text.isNotEmpty &&
                    selectedDays.isNotEmpty) {
                  setState(() {
                    widget.appData.tasks.add({
                      'id': DateTime.now().millisecondsSinceEpoch.toString(),
                      'type': 'class',
                      'title': titleController.text,
                      'schedule': {
                        'days': selectedDays,
                        'start': startController.text,
                        'end': endController.text,
                      },
                      'status': 'todo',
                      'created_at':
                          DateTime.now().toIso8601String().split('T')[0],
                    });
                    widget.appData.save();
                  });
                  Navigator.pop(ctx);
                }
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildClassCard(Map<String, dynamic> task, bool isToday) {
    final sch = task['schedule'] ?? {};
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: isToday
              ? [const Color(0xFF1C1C2D), const Color(0xFF252540)]
              : [const Color(0xFF161625), const Color(0xFF1C1C2D)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
            color: isToday
                ? Colors.blueAccent.withValues(alpha: 0.3)
                : Colors.white.withValues(alpha: 0.05)),
        boxShadow: isToday
            ? [
                BoxShadow(
                    color: Colors.blueAccent.withValues(alpha: 0.1),
                    blurRadius: 10,
                    offset: const Offset(0, 4))
              ]
            : [],
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: Colors.purple.withValues(alpha: 0.15),
              shape: BoxShape.circle,
            ),
            child:
                const Icon(Icons.class_, color: Colors.purpleAccent, size: 20),
          ),
          const SizedBox(width: 15),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                    task['title'] ??
                        task['name'] ??
                        'Class', // Handle 'title' vs 'name' consistency
                    style: const TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.w600)),
                const SizedBox(height: 4),
                Row(
                  children: [
                    const Icon(Icons.access_time,
                        size: 12, color: Colors.white54),
                    const SizedBox(width: 4),
                    Text("${sch['start']} - ${sch['end']}",
                        style: const TextStyle(
                            color: Colors.white54, fontSize: 13)),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
