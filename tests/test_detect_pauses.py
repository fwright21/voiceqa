from tools.detect_pauses import detect_pauses

result = detect_pauses.invoke({"audio_path": "test_audio.wav"})

print("=== AUDIO INFO ===")
print(f"Duration: {result['audio_duration_sec']}s")

print("\n=== PAUSES ===")
if result['pause_count'] == 0:
    print("No unnatural pauses detected")
else:
    for p in result['pauses']:
        print(f"  [{p['start_sec']}s → {p['end_sec']}s] duration: {p['duration_sec']}s")

print(f"\nTotal pause time: {result['total_pause_time_sec']}s")
print(f"Longest pause:    {result['longest_pause_sec']}s")
print(f"Pause count:      {result['pause_count']}")