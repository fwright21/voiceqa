from tools.diff_transcript import diff_transcript

def test_diff_transcript_basic_metrics():
    expected = "Call 1-800-555-0199 and ask for Dr. Nguyen."
    actual = "Call 1-800-555-5199, and ask for Dr. Nguyen."

    result = diff_transcript.invoke({
        "expected_script": expected,
        "actual_transcript": actual,
    })

    assert set(["wer", "mer", "wil", "accuracy_pct", "error_counts", "diff_ops"]).issubset(result.keys())
    assert 0.0 <= float(result["wer"]) <= 1.0
    assert 0.0 <= float(result["accuracy_pct"]) <= 100.0
    assert isinstance(result["error_counts"], dict)
    assert isinstance(result["diff_ops"], list)
