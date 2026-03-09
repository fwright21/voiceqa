from tools.save_report import save_report

result = save_report.invoke({
    "audio_name":  "test_audio.wav",
    "expected":    "Call 1-800-555-0199 and ask for Dr. Nguyen.",
    "transcript":  "Call 1-800-555-5199, and ask for Dr. Nguyen.",
    "wer":         0.05,
    "score":       95,
    "suggestions": ["Fix phone number pronunciation", "Reduce transients around Dr. Nguyen"],
    "full_report": "Test report text",
})

print(f"Saved! Report ID: {result['report_id']}")