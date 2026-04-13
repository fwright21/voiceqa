from tools.eval_runner import summarize_reports


def test_summarize_reports_counts_and_top_failures():
    reports = [
        {"verdict": "PASS", "score": 90, "failures": []},
        {"verdict": "REVIEW", "score": 70, "failures": ["Name mismatch"]},
        {"verdict": "FAIL", "score": 0, "failures": ["Missing audio file: x.wav"]},
        {"verdict": "FAIL", "score": 10, "failures": ["Missing audio file: x.wav"]},
    ]

    summary = summarize_reports(reports)
    assert summary["total"] == 4
    assert summary["pass"] == 1
    assert summary["review"] == 1
    assert summary["fail"] == 2
    assert summary["low_confidence"] == 0
    assert summary["avg_score"] is not None
    assert summary["top_failures"][0]["reason"] == "Missing audio file: x.wav"
    assert summary["top_failures"][0]["count"] == 2

