import json
from pathlib import Path


def test_demo_test_suite_includes_metric_showcases():
    suite_dir = Path("eval_set/suites/demo-test-suite")
    manifest = suite_dir / "manifest.jsonl"
    assert manifest.exists()

    wanted_ids = {
        "dt-002-omission-safety__speed_fail",
        "dt-004-prosody-pause__trailing_silence",
        "dt-006-filled-pauses",
    }

    seen = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        obj = json.loads(raw)
        cid = obj.get("id")
        if cid in wanted_ids:
            seen[cid] = obj

    assert wanted_ids.issubset(set(seen.keys()))

    for cid, obj in seen.items():
        rel = obj.get("audio_path")
        assert isinstance(rel, str) and rel.startswith("audio/")
        p = (suite_dir / rel).resolve()
        assert p.exists(), f"Missing audio for {cid}: {p}"
        assert p.stat().st_size > 10_000, f"Audio too small for {cid}: {p.stat().st_size} bytes"
