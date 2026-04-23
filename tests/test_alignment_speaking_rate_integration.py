def test_alignment_phrase_spans_support_speaking_rate():
    from tools.alignment import build_alignment
    from tools.check_speaking_rate import check_speaking_rate

    transcription = {
        "word_spans": [
            {"word": "take", "start": 0.0, "end": 0.3, "probability": 0.9},
            {"word": "two", "start": 0.3, "end": 0.6, "probability": 0.9},
            {"word": "tablets", "start": 0.6, "end": 1.0, "probability": 0.9},
            {"word": "daily", "start": 1.0, "end": 1.4, "probability": 0.9},
        ]
    }

    alignment = build_alignment(transcription, expected_script="Take two tablets daily.")
    phrase_spans = alignment.get("phrase_spans") or []

    assert phrase_spans
    assert phrase_spans[0].get("word_count") == 4
    assert phrase_spans[0].get("duration_sec") == 1.4

    out = check_speaking_rate.invoke({"phrase_spans": phrase_spans, "language": "en"})
    assert out["segments"]
    assert out["segments"][0]["wpm"] is not None
