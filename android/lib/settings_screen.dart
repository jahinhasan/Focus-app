import 'package:flutter/material.dart';
import 'logic_port.dart';

class SettingsScreen extends StatelessWidget {
  final FocusData appData;

  const SettingsScreen({super.key, required this.appData});

  void _resetData(BuildContext context) async {
    // Confirm dialog
    bool confirm = await showDialog(
            context: context,
            builder: (ctx) => AlertDialog(
                  backgroundColor: const Color(0xFF1C1C2D),
                  title: const Text("Reset All Data?",
                      style: TextStyle(color: Colors.white)),
                  content: const Text(
                      "This will delete all tasks, XP, and history. This cannot be undone.",
                      style: TextStyle(color: Colors.white70)),
                  actions: [
                    TextButton(
                        child: const Text("Cancel",
                            style: TextStyle(color: Colors.white38)),
                        onPressed: () => Navigator.pop(ctx, false)),
                    TextButton(
                        child: const Text("RESET",
                            style: TextStyle(color: Colors.redAccent)),
                        onPressed: () => Navigator.pop(ctx, true)),
                  ],
                )) ??
        false;

    if (confirm) {
      final newData = FocusData.defaultState();
      await newData.save();
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text("App data reset. Please restart the app.")));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F0F1A),
      appBar: AppBar(
        title: const Text("Settings",
            style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: const Color(0xFF161625),
        elevation: 0,
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _sectionHeader("General"),
          _settingTile(Icons.dark_mode, "Theme", "System Default (Dark)", null),
          _settingTile(Icons.notifications, "Notifications", "Enabled", null),
          _settingTile(Icons.api_rounded, "Gemini API Key",
              "Update your AI brain key", () => _editApiKey(context)),
          const SizedBox(height: 30),
          _sectionHeader("Data"),
          _settingTile(Icons.delete_forever, "Reset Data",
              "Clear all tasks and XP", () => _resetData(context),
              isDestructive: true),
          const SizedBox(height: 30),
          _sectionHeader("About"),
          _settingTile(
              Icons.info_outline, "Version", "1.0.1 (Flutter Port)", null),
          _settingTile(Icons.code, "Developer", "Jahin Hasan", null),
        ],
      ),
    );
  }

  void _editApiKey(BuildContext context) {
    final controller =
        TextEditingController(text: appData.settings['gemini_api_key'] ?? "");
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1C1C2D),
        title:
            const Text("Edit API Key", style: TextStyle(color: Colors.white)),
        content: TextField(
          controller: controller,
          style: const TextStyle(color: Colors.white),
          decoration: const InputDecoration(
            hintText: "Enter Gemini API Key",
            hintStyle: TextStyle(color: Colors.white24),
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx), child: const Text("Cancel")),
          ElevatedButton(
            onPressed: () {
              appData.settings['gemini_api_key'] = controller.text;
              appData.save();
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                  content: Text("API Key updated for next session.")));
            },
            child: const Text("Save"),
          )
        ],
      ),
    );
  }

  Widget _sectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10, left: 5),
      child: Text(title.toUpperCase(),
          style: const TextStyle(
              color: Colors.blueAccent,
              fontSize: 12,
              fontWeight: FontWeight.bold,
              letterSpacing: 1.2)),
    );
  }

  Widget _settingTile(
      IconData icon, String title, String subtitle, VoidCallback? onTap,
      {bool isDestructive = false}) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: const Color(0xFF1C1C2D),
        borderRadius: BorderRadius.circular(12),
      ),
      child: ListTile(
        leading: Icon(icon,
            color: isDestructive ? Colors.redAccent : Colors.white54),
        title: Text(title,
            style: TextStyle(
                color: isDestructive ? Colors.redAccent : Colors.white)),
        subtitle: Text(subtitle,
            style: const TextStyle(color: Colors.white38, fontSize: 12)),
        trailing: onTap != null
            ? const Icon(Icons.arrow_forward_ios,
                size: 14, color: Colors.white24)
            : null,
        onTap: onTap,
      ),
    );
  }
}
