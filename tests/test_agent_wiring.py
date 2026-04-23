def test_agent_wires_speaking_rate_into_generate_report(monkeypatch):
    import agent

    captured = {}

    monkeypatch.setattr(
        agent.transcribe_audio,
        "func",
        lambda **_kwargs: {"transcript": "um then um", "transcript_confidence": "ok"},
    )
    monkeypatch.setattr(
        agent,
        "build_alignment",
        lambda _t, expected_script=None: {
            "backend": "test",
            "word_spans": [
                {"word": "um", "start_sec": 0.0, "end_sec": 0.1},
                {"word": "then", "start_sec": 0.1, "end_sec": 0.2},
                {"word": "um", "start_sec": 2.0, "end_sec": 2.1},
            ],
            "phrase_spans": [
                {
                    "phrase_id": 1,
                    "start_sec": 0.0,
                    "end_sec": 3.0,
                    "word_start": 0,
                    "word_end": 2,
                    "text": "um then um",
                    "word_count": 3,
                    "duration_sec": 3.0,
                }
            ],
        },
    )
    monkeypatch.setattr(agent.diff_transcript, "func", lambda **_kwargs: {"wer": 0.0})
    monkeypatch.setattr(
        agent.detect_audio_artifacts, "func", lambda **_kwargs: {"artifact_count": 0}
    )
    monkeypatch.setattr(
        agent.detect_pauses,
        "func",
        lambda **_kwargs: {"pauses": [], "longest_pause_sec": 0.0, "flagged_regions": []},
    )
    monkeypatch.setattr(
        agent.check_pause_naturalness,
        "func",
        lambda **_kwargs: {"flags": [], "max_within_phrase_gap_sec": 0.0, "speaking_rate_wps": 2.0},
    )
    monkeypatch.setattr(
        agent.check_speaking_rate,
        "func",
        lambda **_kwargs: {
            "segments": [{"severity": "warn", "start_sec": 0.0, "end_sec": 1.0}],
            "overall_rate": 230.0,
            "rate_unit": "wpm",
            "flagged_regions": [],
        },
    )
    monkeypatch.setattr(agent.analyse_prosody, "func", lambda **_kwargs: {"flagged_regions": [], "monotone_severity": "ok"})
    monkeypatch.setattr(agent.predict_mos, "func", lambda **_kwargs: {"mos_score": 4.0})
    monkeypatch.setattr(agent.check_entity_fidelity, "func", lambda **_kwargs: {"mismatches": []})
    monkeypatch.setattr(agent.check_name_fidelity, "func", lambda **_kwargs: {"mismatches": []})
    monkeypatch.setattr(agent.check_faithfulness, "func", lambda **_kwargs: {"violations": []})

    def _fake_generate_report(*, analysis_data):
        captured["analysis_data"] = analysis_data
        return {
            "report_text": "ok",
            "score": 100,
            "verdict": "PASS",
            "failures": [],
            "suggestions": [],
        }

    monkeypatch.setattr(agent.generate_qa_report, "func", _fake_generate_report)
    monkeypatch.setattr(agent.save_report, "func", lambda **_kwargs: {"report_id": 1})

    agent.run_analysis(audio_path="dummy.wav", expected_script="hello", language="en")

    assert "speaking_rate" in captured["analysis_data"]
