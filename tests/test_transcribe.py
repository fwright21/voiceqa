from tools.transcribe_audio import transcribe_audio

# Point this at the test audio we generated
result = transcribe_audio.invoke({"audio_path": "test_audio.wav"})

print("=== TRANSCRIPT ===")
print(result["transcript"])

print("\n=== LANGUAGE ===")
print(result["language"])

print("\n=== SEGMENTS ===")
for seg in result["segments"]:
    print(f"[{seg['start']}s → {seg['end']}s] {seg['text']}")