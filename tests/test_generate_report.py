def test_generate_qa_report_returns_expected_shape():
    from tools.generate_qa_report import generate_qa_report

    analysis_data = {
        "audio_name": "test_audio.wav",
        "transcript": "Hello world.",
        "transcript_confidence": "ok",
        "accuracy": {"wer": 0.0},
        "artifacts": {"artifact_count": 0, "overall_clean": True, "clipping_detected": False},
        "pauses": {"pause_count": 0, "longest_pause_sec": 0.0, "pauses": []},
        "prosody": {"skipped": True},
        "mos": {"skipped": True, "mos_score": None},
        "entity_fidelity": {"mismatches": [], "fidelity_score": 100.0},
        "faithfulness": {"violations": [], "skipped": True, "confidence": "low"},
    }

    result = generate_qa_report.invoke({"analysis_data": analysis_data})

    assert set(["report_text", "score", "verdict", "failures", "suggestions"]).issubset(result.keys())
    assert isinstance(result["report_text"], str)
    assert "### Overall Score" in result["report_text"]
    assert isinstance(result["score"], int)
    assert result["verdict"] in ("PASS", "REVIEW", "FAIL", "LOW_CONFIDENCE")
    assert isinstance(result["failures"], list)
    assert isinstance(result["suggestions"], list)


def test_generate_qa_report_adds_speaking_rate_suggestion_when_flagged():
    from tools.generate_qa_report import generate_qa_report

    analysis_data = {
        "audio_name": "test_audio.wav",
        "transcript": "Hello world.",
        "transcript_confidence": "ok",
        "accuracy": {"wer": 0.0},
        "pauses": {"pause_count": 0, "longest_pause_sec": 0.0, "pauses": []},
        "pause_naturalness": {"max_within_phrase_gap_sec": 0.0, "flags": []},
        "speaking_rate": {"segments": [{"severity": "warn"}]},
    }

    result = generate_qa_report.invoke({"analysis_data": analysis_data})

    suggestions = result.get("suggestions") or []
    assert any("speaking rate" in str(s).lower() for s in suggestions)
    assert any("done when:" in str(s).lower() for s in suggestions)
