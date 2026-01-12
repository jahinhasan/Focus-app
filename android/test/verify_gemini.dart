import 'package:google_generative_ai/google_generative_ai.dart';
import 'dart:io';

void main() async {
  final apiKey = "AIzaSyDka7mgZjtigZd74bUaiC0K5wsqXyYqPqg";
  final model = GenerativeModel(model: 'gemini-1.5-flash', apiKey: apiKey);

  print("Verifying Gemini API Key...");
  try {
    final prompt = 'Tell me "Connection Successful" if you can hear me.';
    final content = [Content.text(prompt)];
    final response = await model.generateContent(content);

    if (response.text != null &&
        response.text!.contains("Connection Successful")) {
      print("✅ GEMINI VERIFIED: Connection is active and key is valid.");
      exit(0);
    } else {
      print("❌ FAILURE: Unexpected response from Gemini: ${response.text}");
      exit(1);
    }
  } catch (e) {
    print("❌ ERROR calling Gemini: $e");
    exit(1);
  }
}
