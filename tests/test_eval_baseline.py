from pathlib import Path

from fastapi.testclient import TestClient

import main


def test_baseline_save_and_compare_roundtrip():
    client = TestClient(main.app)

    run = client.post("/eval/run", json={"suite_id": "_test-missing-audio", "include_reports": True}).json()
    baseline = {
        "summary": run.get("summary"),
        "cases": [
            {
                "case_id": r.get("case_id"),
                "verdict": r.get("verdict"),
                "score": r.get("score"),
                "failures": r.get("failures", [])[:3],
            }
            for r in (run.get("reports") or [])
        ],
    }

    save = client.post("/eval/baseline/save", json={"suite_id": "_test-missing-audio", "baseline": baseline})
    assert save.status_code == 200
    saved = save.json()
    assert saved.get("saved") is True

    compare = client.post("/eval/baseline/compare", json={"suite_id": "_test-missing-audio", "current": baseline})
    assert compare.status_code == 200
    diff = compare.json()
    assert diff["suite_id"] == "_test-missing-audio"
    assert diff["delta"]["pass"] == 0
    assert diff["delta"]["review"] == 0
    assert diff["delta"]["fail"] == 0

    # Clean up the local baseline file to avoid test pollution.
    p = Path(diff["baseline_path"])
    if p.exists():
        p.unlink()

