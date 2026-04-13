"""
Manual transcription smoke-test.

This is intentionally *not* part of the automated pytest suite because Whisper
model loading/transcription is slow and depends on local model availability.
"""


if __name__ == "__main__":
    from tools.transcribe_audio import transcribe_audio

    result = transcribe_audio.invoke({"audio_path": "test_audio.wav"})

    print("=== TRANSCRIPT ===")
    print(result["transcript"])

    print("\n=== LANGUAGE ===")
    print(result["language"])

    print("\n=== SEGMENTS ===")
    for seg in result["segments"]:
        print(f"[{seg['start']}s → {seg['end']}s] {seg['text']}")

