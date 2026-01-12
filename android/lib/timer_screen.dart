import 'package:flutter/material.dart';
import 'dart:async';
import 'logic_port.dart';

class TimerScreen extends StatefulWidget {
  final FocusData appData;
  const TimerScreen({super.key, required this.appData});

  @override
  State<TimerScreen> createState() => _TimerScreenState();
}

class _TimerScreenState extends State<TimerScreen> {
  // Mode: "Focus" (Countdown), "Stopwatch" (Countup)
  String _mode = "Focus";
  int _seconds =
      25 * 60; // Current value (remaining for focus, elapsed for stopwatch)
  int _initialSeconds = 25 * 60; // For progress calc in Focus mode
  bool _isActive = false;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _restoreState();
  }

  void _restoreState() {
    final state = widget.appData.timerState;
    _mode = state['mode'] ?? "Focus";
    _seconds = state['seconds'] ?? (_mode == "Focus" ? 25 * 60 : 0);
    _isActive = state['is_running'] ?? false;
    _initialSeconds =
        _mode == "Focus" ? (state['initial_seconds'] ?? _seconds) : 25 * 60;

    if (_isActive) {
      final lastTickStr = state['last_tick'];
      if (lastTickStr != null) {
        final lastTick = DateTime.parse(lastTickStr);
        final elapsed = DateTime.now().difference(lastTick).inSeconds;

        if (_mode == "Stopwatch") {
          _seconds += elapsed;
        } else {
          _seconds -= elapsed;
          if (_seconds < 0) _seconds = 0;
        }
      }
      // Re-start the ticker
      _startTicker();
    }
  }

  void _startTicker() {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      setState(() {
        if (_mode == "Stopwatch") {
          _seconds++;
        } else {
          if (_seconds > 0) {
            _seconds--;
          } else {
            _timer?.cancel();
            _isActive = false;
            _persistState();
          }
        }
      });
    });
  }

  void _persistState() {
    widget.appData.updateTimerState(
      seconds: _seconds,
      mode: _mode,
      isRunning: _isActive,
    );
  }

  void _toggleTimer() {
    if (_isActive) {
      _timer?.cancel();
      _isActive = false;
    } else {
      _isActive = true;
      _startTicker();
    }
    _persistState();
    setState(() {});
  }

  void _resetTimer() {
    _timer?.cancel();
    setState(() {
      _isActive = false;
      if (_mode == "Stopwatch") {
        _seconds = 0;
      } else {
        _seconds = _initialSeconds;
      }
    });
    widget.appData.clearTimerState();
  }

  void _setFocusMode(int minutes, String label) {
    _timer?.cancel();
    setState(() {
      _mode = "Focus";
      _initialSeconds = minutes * 60;
      _seconds = _initialSeconds;
      _isActive = false;
    });
    _persistState();
  }

  void _setStopwatchMode() {
    _timer?.cancel();
    setState(() {
      _mode = "Stopwatch";
      _seconds = 0;
      _isActive = false;
    });
    _persistState();
  }

  String _formatTime(int totalSeconds) {
    int mins = totalSeconds ~/ 60;
    int secs = totalSeconds % 60;
    return "${mins.toString().padLeft(2, '0')}:${secs.toString().padLeft(2, '0')}";
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Progress for circular indicator
    double progress = 0.0;
    if (_mode == "Focus") {
      progress = _initialSeconds > 0 ? 1 - (_seconds / _initialSeconds) : 0.0;
    } else {
      // Stopwatch animation (indeterminate or loop every 60s)
      progress = (_seconds % 60) / 60.0;
    }

    return Scaffold(
      backgroundColor: const Color(0xFF0F0F1A),
      appBar: AppBar(
        title: const Text("Focus Timer",
            style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: [
          // Mode Toggle
          Padding(
            padding: const EdgeInsets.only(right: 16.0),
            child: DropdownButton<String>(
              value: _mode,
              dropdownColor: const Color(0xFF1C1C2D),
              underline: const SizedBox(),
              icon: const Icon(Icons.tune, color: Colors.blueAccent),
              style: const TextStyle(color: Colors.white),
              items: ["Focus", "Stopwatch"].map((String value) {
                return DropdownMenuItem<String>(
                  value: value,
                  child: Text(value),
                );
              }).toList(),
              onChanged: (String? newValue) {
                if (newValue == "Stopwatch") {
                  _setStopwatchMode();
                } else {
                  _setFocusMode(25, "Pomodoro");
                }
              },
            ),
          )
        ],
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(_mode.toUpperCase(),
                style: const TextStyle(
                    color: Colors.blueAccent,
                    letterSpacing: 3,
                    fontWeight: FontWeight.bold)),
            const SizedBox(height: 40),

            // --- CIRCULAR GLOW TIMER ---
            Stack(
              alignment: Alignment.center,
              children: [
                SizedBox(
                  width: 250,
                  height: 250,
                  child: CircularProgressIndicator(
                    value: _mode == "Focus"
                        ? (1 - progress)
                        : progress, // Focus depletes, Stopwatch fills
                    strokeWidth: 8,
                    backgroundColor: Colors.white10,
                    valueColor: AlwaysStoppedAnimation<Color>(
                        _mode == "Stopwatch"
                            ? Colors.purpleAccent
                            : Colors.blueAccent),
                  ),
                ),
                Text(_formatTime(_seconds),
                    style: const TextStyle(
                        color: Colors.white,
                        fontSize: 64,
                        fontWeight: FontWeight.w200)),
              ],
            ),

            const SizedBox(height: 60),

            // --- CONTROLS ---
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                IconButton(
                  icon: const Icon(Icons.refresh,
                      color: Colors.white38, size: 30),
                  onPressed: _resetTimer,
                ),
                const SizedBox(width: 30),
                FloatingActionButton.large(
                  backgroundColor: _mode == "Stopwatch"
                      ? Colors.purpleAccent
                      : Colors.blueAccent,
                  onPressed: _toggleTimer,
                  child: Icon(_isActive ? Icons.pause : Icons.play_arrow,
                      size: 40, color: Colors.white),
                ),
                const SizedBox(width: 30),
                // Only show skip/presets in Focus mode
                _mode == "Focus"
                    ? IconButton(
                        icon: const Icon(Icons.skip_next,
                            color: Colors.white38, size: 30),
                        onPressed: () => _setFocusMode(5, "Break"),
                      )
                    : const SizedBox(width: 30),
              ],
            ),

            const SizedBox(height: 40),

            // --- PRESETS (Focus Only) ---
            if (_mode == "Focus")
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _presetButton("Pomodoro", 25),
                  _presetButton("Short Break", 5),
                  _presetButton("Long Break", 15),
                ],
              )
          ],
        ),
      ),
    );
  }

  Widget _presetButton(String label, int mins) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 5),
      child: TextButton(
        onPressed: () => _setFocusMode(mins, label),
        child: Text(label, style: const TextStyle(color: Colors.white24)),
      ),
    );
  }
}
