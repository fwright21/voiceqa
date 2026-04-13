def test_pause_naturalness_flags_within_phrase_gap():
    from tools.check_pause_naturalness import check_pause_naturalness

    alignment = {
        "backend": "whisper_word_timestamps",
        "notes": {"phrase_gap_sec": 0.45},
        "word_spans": [
            {"word": "i", "start_sec": 0.0, "end_sec": 0.1, "probability": 0.9},
            {"word": "have", "start_sec": 0.12, "end_sec": 0.25, "probability": 0.9},
            # within-phrase long gap
            {"word": "pain", "start_sec": 1.2, "end_sec": 1.35, "probability": 0.9},
        ],
        # Force all words into one phrase so the gap is within-phrase.
        "phrase_spans": [
            {"phrase_id": 1, "start_sec": 0.0, "end_sec": 1.35, "text": "i have pain", "word_start": 0, "word_end": 2}
        ],
    }

    pauses = {
        "pauses": [
            {"start_sec": 0.25, "end_sec": 1.2, "duration_sec": 0.95},
        ]
    }

    out = check_pause_naturalness.invoke(
        {
            "alignment": alignment,
            "pauses": pauses,
            "within_phrase_warn_sec": 0.5,
            "within_phrase_fail_sec": 1.0,
            "between_phrase_warn_sec": 2.0,
        }
    )

    assert out["skipped"] is False
    assert out["max_within_phrase_gap_sec"] >= 0.9
    assert any(f.get("type") == "within_phrase_pause" for f in (out.get("flags") or []))
