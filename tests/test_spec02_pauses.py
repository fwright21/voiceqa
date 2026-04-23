from __future__ import annotations

import numpy as np


def _synthetic_audio_with_pause(sr: int = 16000) -> tuple[np.ndarray, int]:
    speech_1 = np.full(int(0.5 * sr), 0.15, dtype=np.float32)
    silence = np.zeros(int(0.7 * sr), dtype=np.float32)
    speech_2 = np.full(int(0.5 * sr), 0.15, dtype=np.float32)
    return np.concatenate([speech_1, silence, speech_2]), sr


def test_spec02_phrase_aware_pause_classification(tmp_path, monkeypatch):
    from tools.detect_pauses import detect_pauses
    import tools.detect_pauses as pause_mod

    audio_path = tmp_path / "spec02.wav"
    audio_path.write_bytes(b"placeholder")

    y, sr = _synthetic_audio_with_pause()
    monkeypatch.setattr(pause_mod, "load_mono_audio", lambda _p: (y, sr))

    out = detect_pauses.invoke(
        {
            "audio_path": str(audio_path),
            "min_pause_sec": 0.3,
            "phrase_spans": [
                {
                    "phrase_id": 1,
                    "start_sec": 0.0,
                    "end_sec": 1.7,
                }
            ],
            "mid_phrase_threshold_sec": 0.5,
        }
    )

    assert out["pause_count"] >= 1
    first = out["pauses"][0]
    assert first["type"] == "unnatural"
    assert first["context"] == "mid-phrase"
    assert first["severity"] in {"warn", "fail"}
    assert any(r.get("check") == "pause_detection" for r in out["flagged_regions"])


def test_spec02_pause_fallback_without_phrase_spans(tmp_path, monkeypatch):
    from tools.detect_pauses import detect_pauses
    import tools.detect_pauses as pause_mod

    audio_path = tmp_path / "spec02_fallback.wav"
    audio_path.write_bytes(b"placeholder")

    y, sr = _synthetic_audio_with_pause()
    monkeypatch.setattr(pause_mod, "load_mono_audio", lambda _p: (y, sr))

    out = detect_pauses.invoke(
        {
            "audio_path": str(audio_path),
            "min_pause_sec": 0.3,
            "phrase_spans": None,
        }
    )

    assert out["pause_count"] >= 1
    first = out["pauses"][0]
    assert first["type"] == "unknown"
    assert first["context"] == "energy_only"


def test_spec02_filled_pause_style_config(tmp_path, monkeypatch):
    from tools.detect_pauses import detect_pauses
    import tools.detect_pauses as pause_mod

    audio_path = tmp_path / "spec02_filled.wav"
    audio_path.write_bytes(b"placeholder")

    # Enough frames to avoid the short-audio early return.
    y = np.full(16000, 0.12, dtype=np.float32)
    sr = 16000
    monkeypatch.setattr(pause_mod, "load_mono_audio", lambda _p: (y, sr))

    word_spans = [
        {"word": "um", "start_sec": 0.1, "end_sec": 0.2},
        {"word": "i", "start_sec": 0.2, "end_sec": 0.3},
        {"word": "uh", "start_sec": 0.3, "end_sec": 0.4},
    ]

    formal = detect_pauses.invoke(
        {
            "audio_path": str(audio_path),
            "transcript": "um i uh",
            "word_spans": word_spans,
            "filled_pause_style": "formal",
            "language": "en",
        }
    )
    conversational = detect_pauses.invoke(
        {
            "audio_path": str(audio_path),
            "transcript": "um i uh",
            "word_spans": word_spans,
            "filled_pause_style": "conversational",
            "language": "en",
        }
    )

    assert {fp["severity"] for fp in formal["filled_pauses"]} == {"warn"}
    assert {fp["severity"] for fp in conversational["filled_pauses"]} == {"info"}
    assert any(r.get("check") == "filled_pause" for r in formal["flagged_regions"])
    assert not any(r.get("check") == "filled_pause" for r in conversational["flagged_regions"])


def test_spec02_filled_pause_repeated_occurrences_get_distinct_timestamps(tmp_path, monkeypatch):
    from tools.detect_pauses import detect_pauses
    import tools.detect_pauses as pause_mod

    audio_path = tmp_path / "spec02_filled_repeat.wav"
    audio_path.write_bytes(b"placeholder")

    # Enough frames to avoid the short-audio early return.
    y = np.full(48000, 0.12, dtype=np.float32)
    sr = 16000
    monkeypatch.setattr(pause_mod, "load_mono_audio", lambda _p: (y, sr))

    word_spans = [
        {"word": "um", "start_sec": 0.0, "end_sec": 0.1},
        {"word": "then", "start_sec": 0.1, "end_sec": 0.2},
        {"word": "um", "start_sec": 2.0, "end_sec": 2.1},
    ]

    out = detect_pauses.invoke(
        {
            "audio_path": str(audio_path),
            "transcript": "um then um",
            "word_spans": word_spans,
            "filled_pause_style": "formal",
            "language": "en",
        }
    )

    assert len(out["filled_pauses"]) == 2
    assert out["filled_pauses"][0]["start_sec"] == 0.0
    assert out["filled_pauses"][1]["start_sec"] == 2.0
