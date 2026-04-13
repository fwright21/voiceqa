from pathlib import Path


def test_save_report_writes_to_sqlite(tmp_path: Path):
    import tools.save_report as save_report_module

    # Keep tests isolated from the repo's real DB.
    save_report_module.DB_PATH = tmp_path / "voiceqa_test.db"

    result = save_report_module.save_report.invoke({
        "audio_name":  "test_audio.wav",
        "expected":    "Call 1-800-555-0199 and ask for Dr. Nguyen.",
        "transcript":  "Call 1-800-555-5199, and ask for Dr. Nguyen.",
        "wer":         0.05,
        "score":       95,
        "verdict":     "REVIEW",
        "failures":    ["Entity mismatch detected (number, code, or date differs from expected)"],
        "suggestions": ["Fix phone number pronunciation", "Reduce transients around Dr. Nguyen"],
        "full_report": "Test report text",
        "transcript_confidence": "ok",
        "prosody_score": 80.0,
        "f0_mean": 160.0,
        "jitter": 0.01,
        "shimmer": 0.05,
        "hnr": 12.0,
        "mos_score": 3.8,
        "entity_fidelity_score": 50.0,
        "name_fidelity_score":  100.0,
        "faithfulness_score": 100.0,
        "violations": [],
    })

    assert result.get("saved") is True
    assert isinstance(result.get("report_id"), int)
    assert save_report_module.DB_PATH.exists()
