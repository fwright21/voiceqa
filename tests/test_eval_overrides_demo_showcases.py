def test_eval_override_bumps_filled_pause_demo_to_review():
    from tools.eval_runner import _apply_eval_overrides

    report = {
        "verdict": "PASS",
        "score": 98,
        "failures": [],
        "suggestions": [],
        "score_breakdown": [],
        "tags": ["demo", "filled_pause"],
        "metrics": {
            "pauses": {
                "filled_pauses": [
                    {"word": "um", "start_sec": 0.0, "end_sec": 0.1, "severity": "warn"}
                ]
            }
        },
    }

    out = _apply_eval_overrides(report)
    assert out["verdict"] == "REVIEW"
    assert any("Filled pauses detected" in f for f in (out.get("failures") or []))
    assert any(b.get("check") == "filled_pause" for b in (out.get("score_breakdown") or []))
