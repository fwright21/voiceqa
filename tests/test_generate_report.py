from tools.generate_qa_report import generate_qa_report

# Simulate the combined output from all 4 previous tools
analysis_data = {
    "audio_name": "test_audio.wav",
    "transcription": {
        "transcript": "Call 1-800-555-5199, and ask for Dr. Nguyen. She will walk you through the 14.5% interest rate and the 30-day clause.",
        "language": "en",
        "segments": [
            {"id": 0, "start": 0.0, "end": 6.0, "text": "Call 1-800-555-5199, and ask for Dr. Nguyen."},
            {"id": 1, "start": 6.0, "end": 12.0, "text": "She will walk you through the 14.5% interest rate and the 30-day clause."}
        ]
    },
    "diff": {
        "wer": 0.05,
        "mer": 0.05,
        "wil": 0.09,
        "accuracy_pct": 95.0,
        "error_counts": {"substitutions": 1, "deletions": 0, "insertions": 0, "total_errors": 1},
        "diff_ops": [
            {"op": "equal", "expected": "call", "actual": "call"},
            {"op": "replace", "expected": "18005550199", "actual": "18005555199"},
            {"op": "equal", "expected": "and ask for dr nguyen she will walk you through the 145 interest rate and the 30day clause", "actual": "and ask for dr nguyen she will walk you through the 145 interest rate and the 30day clause"}
        ]
    },
    "pauses": {
        "pause_count": 1,
        "pauses": [{"start_sec": 5.909, "end_sec": 6.421, "duration_sec": 0.512}],
        "longest_pause_sec": 0.512,
        "total_pause_time_sec": 0.512,
        "audio_duration_sec": 12.456
    },
    "artifacts": {
        "artifact_count": 1,
        "artifacts": [{"type": "pops_clicks", "severity": "high", "detail": "194 transients. Times: [4.689, 4.691, 4.692, 4.692, 4.694]"}],
        "overall_clean": False,
        "clipping_pct": 0.0,
        "dc_offset": -0.0000068,
        "noise_ratio": 0.012,
        "pop_count": 194
    }
}

print("Sending to Ollama... this may take 20-30 seconds")
result = generate_qa_report.invoke({"analysis_data": analysis_data})

print("\n=== SCORE ===")
print(f"{result['score']}/100")

print("\n=== SUGGESTIONS ===")
for i, s in enumerate(result['suggestions'], 1):
    print(f"  {i}. {s}")

print("\n=== FULL REPORT ===")
print(result['report_text'])