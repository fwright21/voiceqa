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


def test_actionable_suggestions_adds_speaking_rate_when_flagged():
    """
    Unit-tests the deterministic suggestion function directly.
    generate_qa_report.invoke() goes through an LLM when Ollama is running,
    which may rewrite the wording — but _actionable_suggestions is the
    deterministic contract we control.
    """
    from tools.generate_qa_report import _actionable_suggestions

    analysis_data = {
        "audio_name": "test_audio.wav",
        "transcript": "Hello world.",
        "accuracy": {"wer": 0.0},
        "pauses": {"pause_count": 0, "longest_pause_sec": 0.0, "pauses": []},
        "pause_naturalness": {"max_within_phrase_gap_sec": 0.0, "flags": []},
        "speaking_rate": {"segments": [{"severity": "warn"}]},
    }

    suggestions = _actionable_suggestions(analysis_data)

    # Plain-language wording instead of jargon like "speaking rate"
    assert any(
        ("too fast" in str(s).lower() or "too slow" in str(s).lower())
        for s in suggestions
    )
    # All suggestions follow the 3-part plain-language structure
    assert all("how to fix:" in str(s).lower() for s in suggestions)
    assert all("how to check:" in str(s).lower() for s in suggestions)
