import 'package:flutter/material.dart';
import 'dart:async';

class TimerScreen extends StatefulWidget {
  @override
  _TimerScreenState createState() => _TimerScreenState();
}

class _TimerScreenState extends State<TimerScreen> {
  int _secondsRemaining = 25 * 60;
  bool _isActive = false;
  Timer? _timer;
  String _mode = "Focus";

  void _toggleTimer() {
    if (_isActive) {
      _timer?.cancel();
    } else {
      _timer = Timer.periodic(Duration(seconds: 1), (timer) {
        setState(() {
          if (_secondsRemaining > 0) {
            _secondsRemaining--;
          } else {
            _timer?.cancel();
            _isActive = false;
            // Logic for XP gain would go here
          }
        });
      });
    }
    setState(() => _isActive = !_isActive);
  }

  void _resetTimer(int minutes, String mode) {
    _timer?.cancel();
    setState(() {
      _secondsRemaining = minutes * 60;
      _isActive = false;
      _mode = mode;
    });
  }

  String _formatTime(int seconds) {
    int mins = seconds ~/ 60;
    int secs = seconds % 60;
    return "${mins.toString().padLeft(2, '0')}:${secs.toString().padLeft(2, '0')}";
  }

  @override
  Widget build(BuildContext context) {
    double progress = 1 - (_secondsRemaining / (25 * 60)); // Simplified for Focus mode

    return Scaffold(
      backgroundColor: Color(0xFF0F0F1A),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(_mode.toUpperCase(), 
              style: TextStyle(color: Colors.blueAccent, letterSpacing: 3, fontWeight: FontWeight.bold)),
            SizedBox(height: 40),
            
            // --- CIRCULAR GLOW TIMER ---
            Stack(
              alignment: Alignment.center,
              children: [
                SizedBox(
                  width: 250,
                  height: 250,
                  child: CircularProgressIndicator(
                    value: progress,
                    strokeWidth: 8,
                    backgroundColor: Colors.white10,
                    valueColor: AlwaysStoppedAnimation<Color>(Colors.blueAccent),
                  ),
                ),
                Text(_formatTime(_secondsRemaining),
                  style: TextStyle(color: Colors.white, fontSize: 64, fontWeight: FontWeight.w200)),
              ],
            ),
            
            SizedBox(height: 60),
            
            // --- CONTROLS ---
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                IconButton(
                  icon: Icon(Icons.refresh, color: Colors.white38),
                  onPressed: () => _resetTimer(25, "Focus"),
                ),
                SizedBox(width: 30),
                FloatingActionButton.large(
                  backgroundColor: Colors.blueAccent,
                  onPressed: _toggleTimer,
                  child: Icon(_isActive ? Icons.pause : Icons.play_arrow, size: 40, color: Colors.white),
                ),
                SizedBox(width: 30),
                IconButton(
                  icon: Icon(Icons.skip_next, color: Colors.white38),
                  onPressed: () => _resetTimer(5, "Break"),
                ),
              ],
            ),
            
            SizedBox(height: 40),
            
            // --- MODE SELECTOR ---
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                _modeButton("Work", 25),
                _modeButton("Short", 5),
                _modeButton("Long", 15),
              ],
            )
          ],
        ),
      ),
    );
  }

  Widget _modeButton(String label, int mins) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 5),
      child: TextButton(
        onPressed: () => _resetTimer(mins, label),
        child: Text(label, style: TextStyle(color: _mode == label ? Colors.blueAccent : Colors.white24)),
      ),
    );
  }
}
