from pathlib import Path


def test_detect_audio_artifacts_returns_expected_shape():
    from tools.detect_audio_artifacts import detect_audio_artifacts

    audio_path = str(Path(__file__).resolve().parent / "test_audio.wav")
    result = detect_audio_artifacts.invoke({"audio_path": audio_path})

    assert set(["artifacts", "artifact_count", "overall_clean"]).issubset(result.keys())
    assert isinstance(result["artifacts"], list)
    assert isinstance(result["artifact_count"], int)
    assert isinstance(result["overall_clean"], bool)
    assert isinstance(result.get("clipping_pct"), (int, float))
    assert isinstance(result.get("dc_offset"), (int, float))
    assert isinstance(result.get("noise_ratio"), (int, float))
    assert isinstance(result.get("pop_count"), int)
    assert isinstance(result.get("clipping_detected"), bool)
