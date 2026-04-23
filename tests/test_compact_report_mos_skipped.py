def test_compact_report_exposes_mos_skipped_fields():
    from tools.eval_runner import compact_report

    out = compact_report(
        {
            "case_id": "case-1",
            "verdict": "PASS",
            "score": 99,
            "metrics": {
                "mos": {
                    "skipped": True,
                    "error": "Missing dependency: No module named 'speechmos'",
                    "mos_score": None,
                }
            },
        }
    )

    h = out.get("highlights") or {}
    assert h.get("mos_score") is None
    assert h.get("mos_skipped") is True
    assert "speechmos" in str(h.get("mos_error", "")).lower()
