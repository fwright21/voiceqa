from fastapi.testclient import TestClient

import main


def test_ui_serves_html():
    client = TestClient(main.app)
    resp = client.get("/ui")
    assert resp.status_code == 200
    assert "<title>VoiceQA" in resp.text


def test_eval_suites_lists_known_suites():
    client = TestClient(main.app)
    resp = client.get("/eval/suites")
    assert resp.status_code == 200
    data = resp.json()
    suite_ids = {s["suite_id"] for s in data.get("suites", [])}
    assert "healthcare-basic" in suite_ids
    assert "symptom-triage" in suite_ids
    assert "_test-missing-audio" in suite_ids


def test_eval_run_fails_fast_when_audio_missing():
    client = TestClient(main.app)
    resp = client.post("/eval/run", json={"suite_id": "_test-missing-audio", "include_reports": False, "report_mode": "none"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["suite_id"] == "_test-missing-audio"
    assert "summary" in data
    assert data["summary"]["total"] > 0
    # With no audio files present in the repo, we expect all cases to fail fast.
    assert data["summary"]["fail"] == data["summary"]["total"]


def test_eval_run_compact_includes_reports_but_not_full_metrics():
    client = TestClient(main.app)
    resp = client.post("/eval/run", json={"suite_id": "_test-missing-audio", "include_reports": True, "report_mode": "compact"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data.get("reports"), list)
    r0 = data["reports"][0]
    assert "metrics" not in r0
    assert "expected_script" in r0
    assert "transcript" in r0
    assert "highlights" in r0
