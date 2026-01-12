import 'package:flutter/material.dart';
import 'logic_port.dart';

class StoreScreen extends StatefulWidget {
  final FocusData appData;

  const StoreScreen({super.key, required this.appData});

  @override
  State<StoreScreen> createState() => _StoreScreenState();
}

class _StoreScreenState extends State<StoreScreen> {
  // Store Items Configuration
  final List<Map<String, dynamic>> items = [
    {
      'id': 'theme_dark',
      'name': 'Midnight Theme',
      'cost': 0,
      'icon': Icons.dark_mode
    },
    {
      'id': 'theme_ocean',
      'name': 'Ocean Theme',
      'cost': 500,
      'icon': Icons.water_drop
    },
    {
      'id': 'theme_sunset',
      'name': 'Sunset Theme',
      'cost': 1000,
      'icon': Icons.wb_sunny
    },
    {
      'id': 'sound_rain',
      'name': 'Rain Sounds',
      'cost': 200,
      'icon': Icons.cloud
    },
    {
      'id': 'sound_cafe',
      'name': 'Cafe Ambience',
      'cost': 400,
      'icon': Icons.coffee
    },
    {
      'id': 'sound_forest',
      'name': 'Forest Sounds',
      'cost': 600,
      'icon': Icons.forest
    },
  ];

  void _purchaseItem(Map<String, dynamic> item) {
    // Check if the item is already unlocked (excluding free items which are always "unlocked" by default)
    List<dynamic> unlockedItems = widget.appData.store['unlocked'] ?? [];
    final bool isAlreadyUnlocked = unlockedItems.contains(item['id']);

    if (isAlreadyUnlocked) {
      ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("You already own ${item['name']}!")));
      return;
    }

    final int cost = (item['cost'] as num)
        .toInt(); // Explicit num cast and toInt() for safety
    if (widget.appData.xp >= cost) {
      setState(() {
        widget.appData.xp -= cost;
        widget.appData.store['xp_spent'] =
            (widget.appData.store['xp_spent'] ?? 0) + cost;

        // Ensure 'unlocked' is a list and add the item ID
        if (!unlockedItems.contains(item['id'])) {
          unlockedItems.add(item['id']);
          widget.appData.store['unlocked'] = unlockedItems;
        }
        widget.appData.save();
      });
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text("Unlocked ${item['name']}!")));
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Not enough XP! Need ${item['cost']} XP.")));
    }
  }

  @override
  Widget build(BuildContext context) {
    List<dynamic> unlocked = widget.appData.store['unlocked'] ?? [];

    return Scaffold(
      backgroundColor: const Color(0xFF0F0F1A),
      appBar: AppBar(
        title: const Text("XP Store",
            style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: const Color(0xFF161625),
        elevation: 0,
        actions: [
          Center(
            child: Padding(
              padding: const EdgeInsets.only(right: 20.0),
              child: Text("${widget.appData.xp} XP",
                  style: const TextStyle(
                      color: Colors.blueAccent,
                      fontWeight: FontWeight.bold,
                      fontSize: 16)),
            ),
          )
        ],
      ),
      body: GridView.builder(
        padding: const EdgeInsets.all(16),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 2,
          childAspectRatio: 0.85,
          crossAxisSpacing: 16,
          mainAxisSpacing: 16,
        ),
        itemCount: items.length,
        itemBuilder: (context, index) {
          final item = items[index];
          final isUnlocked = unlocked.contains(item['id']) || item['cost'] == 0;

          return Container(
            decoration: BoxDecoration(
              color: const Color(0xFF1C1C2D),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                  color: isUnlocked
                      ? Colors.blueAccent.withValues(alpha: 0.3)
                      : Colors.white10),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: isUnlocked
                        ? Colors.blueAccent.withValues(alpha: 0.1)
                        : Colors.white.withValues(alpha: 0.05),
                    shape: BoxShape.circle,
                  ),
                  child: Icon(item['icon'],
                      size: 32,
                      color: isUnlocked ? Colors.blueAccent : Colors.white24),
                ),
                const SizedBox(height: 16),
                Text(item['name'],
                    style: const TextStyle(
                        color: Colors.white, fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                if (isUnlocked)
                  const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.check, color: Colors.greenAccent, size: 16),
                      SizedBox(width: 4),
                      Text("Owned",
                          style: TextStyle(
                              color: Colors.greenAccent, fontSize: 12)),
                    ],
                  )
                else
                  ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.blueAccent,
                      shape: const StadiumBorder(),
                      padding: const EdgeInsets.symmetric(
                          horizontal: 20, vertical: 0),
                    ),
                    onPressed: () => _purchaseItem(item),
                    child: Text("${item['cost']} XP",
                        style: const TextStyle(fontSize: 12)),
                  ),
              ],
            ),
          );
        },
      ),
    );
  }
}
