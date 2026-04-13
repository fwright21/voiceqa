def test_build_alignment_derives_phrase_spans_from_gaps():
    from tools.alignment import build_alignment

    transcription = {
        "word_spans": [
            {"word": "hello", "start": 0.0, "end": 0.2, "probability": 0.9},
            {"word": "world", "start": 0.25, "end": 0.5, "probability": 0.9},
            # big gap => phrase break
            {"word": "next", "start": 1.2, "end": 1.4, "probability": 0.9},
        ]
    }

    out = build_alignment(transcription, expected_script="hello world. next", phrase_gap_sec=0.45)
    assert out["backend"] == "whisper_word_timestamps"
    assert isinstance(out["word_spans"], list)
    assert isinstance(out["phrase_spans"], list)
    assert len(out["phrase_spans"]) == 2
    assert out["phrase_spans"][0]["text"] == "hello world"
    assert out["phrase_spans"][1]["text"] == "next"


def test_build_alignment_prefers_expected_phrase_spans_over_gap_splitting():
    from tools.alignment import build_alignment

    # Big gap would normally split, but expected_script is a single phrase.
    transcription = {
        "word_spans": [
            {"word": "please", "start": 0.0, "end": 0.2, "probability": 0.9},
            {"word": "describe", "start": 0.25, "end": 0.5, "probability": 0.9},
            {"word": "symptoms", "start": 0.55, "end": 0.8, "probability": 0.9},
            {"word": "now", "start": 2.5, "end": 2.7, "probability": 0.9},
        ]
    }

    out = build_alignment(transcription, expected_script="Please describe symptoms now.", phrase_gap_sec=0.45)
    assert isinstance(out["phrase_spans"], list)
    assert len(out["phrase_spans"]) == 1
    assert out["phrase_spans"][0]["word_start"] == 0
    assert out["phrase_spans"][0]["word_end"] == 3
