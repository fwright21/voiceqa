from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

import main


def test_spec05_api_returns_flagged_regions(monkeypatch):
    import agent

    fake = {
        "report_id": 123,
        "audio_name": "tmp.wav",
        "verdict": "REVIEW",
        "failures": ["Unnatural pause"],
        "score": 77,
        "transcript": "hello",
        "metrics": {},
        "flagged_regions": [
            {
                "check": "pause_detection",
                "label": "Unnatural pause (0.87s)",
                "severity": "warn",
                "start_sec": 4.21,
                "end_sec": 5.08,
            }
        ],
        "suggestions": [],
        "report_text": "...",
    }

    monkeypatch.setattr(agent, "run_analysis", lambda audio_path, expected_script: fake)

    client = TestClient(main.app)
    resp = client.post(
        "/analyse",
        files={"audio": ("sample.wav", BytesIO(b"RIFF"), "audio/wav")},
        data={"expected_script": "hello"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "flagged_regions" in data
    assert isinstance(data["flagged_regions"], list)
    assert data["flagged_regions"][0]["start_sec"] == 4.21


def test_spec05_ui_handles_missing_timestamps_and_jump_behavior():
    app_js = (Path(__file__).resolve().parents[1] / "ui" / "static" / "app.js").read_text(
        encoding="utf-8"
    )

    assert "(no timestamp)" in app_js
    assert "if (r.start_sec !== null && r.start_sec !== undefined)" in app_js
    assert "function jumpToRegion(startSec" in app_js
    assert "audioEl.currentTime" in app_js
    assert "audioEl.play()" in app_js
    assert "renderFlaggedRegions(jumpList, flaggedRegions, audio);" in app_js


def test_spec05_compact_report_preserves_flagged_regions():
    from tools.eval_runner import compact_report

    out = compact_report(
        {
            "case_id": "case-1",
            "score": 88,
            "score_breakdown": [{"check": "speaking_rate", "penalty": -5}],
            "flagged_regions": [
                {
                    "check": "speaking_rate",
                    "label": "Fast speech",
                    "severity": "warn",
                    "start_sec": 1.2,
                    "end_sec": 2.4,
                }
            ],
        }
    )

    assert out["flagged_regions"][0]["start_sec"] == 1.2
    assert out["score_breakdown"][0]["penalty"] == -5
