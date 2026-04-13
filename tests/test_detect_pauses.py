from pathlib import Path


def test_detect_pauses_returns_expected_shape():
    from tools.detect_pauses import detect_pauses

    audio_path = str(Path(__file__).resolve().parent / "test_audio.wav")
    result = detect_pauses.invoke({"audio_path": audio_path})

    assert set([
        "pauses",
        "pause_count",
        "total_pause_time_sec",
        "longest_pause_sec",
        "audio_duration_sec",
    ]).issubset(result.keys())
    assert isinstance(result["pauses"], list)
    assert isinstance(result["pause_count"], int)
    assert isinstance(result["audio_duration_sec"], (int, float))
