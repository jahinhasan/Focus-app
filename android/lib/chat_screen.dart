import 'package:flutter/material.dart';
import 'logic_port.dart';
import 'ai_parser_port.dart';

class ChatScreen extends StatefulWidget {
  final FocusData appData;

  const ChatScreen({super.key, required this.appData});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  late MobileAIParser _parser;
  final List<Map<String, String>> _messages = [
    {
      'role': 'ai',
      'text':
          'Hello! I am your Focus Assistant powered by Gemini ⚡. Ask me to add tasks!'
    }
  ];

  @override
  void initState() {
    super.initState();
    _parser = MobileAIParser();
  }

  void _sendMessage() async {
    if (_controller.text.isEmpty) return;

    final userText = _controller.text;
    setState(() {
      _messages.add({'role': 'user', 'text': userText});
      _controller.clear();
      _messages.add({'role': 'ai', 'text': 'Thinking...'});
    });
    _scrollToBottom();

    try {
      // Use Gemini Parser
      final result = await _parser.parse(userText);
      final intent = result['intent'];
      String response = result['message'] ?? "Done.";

      if (!mounted) return;
      setState(() {
        _messages.removeLast(); // Remove "Thinking..."

        if (intent == 'add_task') {
          final data = result['data'];
          widget.appData.tasks.add({
            'id': DateTime.now().millisecondsSinceEpoch.toString(),
            'type': 'task',
            'title': data?['name'] ?? 'New Task',
            'status': 'pending',
            'created_at': DateTime.now().toIso8601String().split('T')[0],
          });
          widget.appData.save();
          response = "✅ Added task: ${data?['name'] ?? 'New Task'}";
        } else if (intent == 'add_class') {
          final data = result['data'];
          widget.appData.tasks.add({
            'id': DateTime.now().millisecondsSinceEpoch.toString(),
            'type': 'class',
            'title': data?['name'] ?? "New Class from AI",
            'status': 'todo',
            'created_at': DateTime.now().toIso8601String().split('T')[0],
            'schedule': {
              'days': data?['days'] ?? ['mon'],
              'start': data?['time'] ?? '09:00',
              'end': '10:00'
            }
          });
          widget.appData.save();
          response = "📚 Added class: ${data?['name'] ?? 'New Class'}";
        } else if (intent == 'query_stats') {
          response =
              "You are Level ${widget.appData.level} with ${widget.appData.xp} XP. Keep pushing! 🚀";
        } else if (intent == 'chat' || intent == 'greeting') {
          response =
              result['message'] ?? "I'm here to help! What's on your mind?";
        }

        _messages.add({'role': 'ai', 'text': response});
        _scrollToBottom();
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _messages.removeLast();
        _messages.add({'role': 'ai', 'text': "Error: $e"});
      });
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F0F1A),
      appBar: AppBar(
        title: const Text("Focus AI",
            style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: const Color(0xFF161625),
        elevation: 0,
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.all(16),
              itemCount: _messages.length,
              itemBuilder: (context, index) {
                final msg = _messages[index];
                final isUser = msg['role'] == 'user';
                return Align(
                  alignment:
                      isUser ? Alignment.centerRight : Alignment.centerLeft,
                  child: Container(
                    margin: const EdgeInsets.symmetric(vertical: 4),
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 10),
                    constraints: BoxConstraints(
                        maxWidth: MediaQuery.of(context).size.width * 0.75),
                    decoration: BoxDecoration(
                      color:
                          isUser ? Colors.blueAccent : const Color(0xFF1C1C2D),
                      borderRadius: BorderRadius.only(
                        topLeft: const Radius.circular(12),
                        topRight: const Radius.circular(12),
                        bottomLeft: isUser
                            ? const Radius.circular(12)
                            : const Radius.circular(2),
                        bottomRight: isUser
                            ? const Radius.circular(2)
                            : const Radius.circular(12),
                      ),
                    ),
                    child: Text(msg['text']!,
                        style: const TextStyle(color: Colors.white)),
                  ),
                );
              },
            ),
          ),
          Container(
            padding: const EdgeInsets.all(10),
            color: const Color(0xFF161625),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      hintText: "Type a command...",
                      hintStyle: const TextStyle(color: Colors.white24),
                      filled: true,
                      fillColor: const Color(0xFF1C1C2D),
                      border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(25),
                          borderSide: BorderSide.none),
                      contentPadding: const EdgeInsets.symmetric(
                          horizontal: 20, vertical: 10),
                    ),
                    onSubmitted: (_) => _sendMessage(),
                  ),
                ),
                const SizedBox(width: 8),
                CircleAvatar(
                  backgroundColor: Colors.blueAccent,
                  child: IconButton(
                    icon: const Icon(Icons.send, color: Colors.white, size: 20),
                    onPressed: _sendMessage,
                  ),
                )
              ],
            ),
          )
        ],
      ),
    );
  }
}
