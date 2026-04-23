from __future__ import annotations


def test_spec03_wpm_calculation_and_warning_flag():
    from tools.check_speaking_rate import check_speaking_rate

    out = check_speaking_rate.invoke(
        {
            "phrase_spans": [
                {
                    "phrase_id": 1,
                    "start_sec": 0.0,
                    "end_sec": 3.2,
                    "word_count": 12,
                    "duration_sec": 3.2,
                    "text": "take two tablets every morning",
                }
            ],
            "language": "en",
        }
    )

    assert out["rate_unit"] == "wpm"
    assert out["overall_rate"] == 225.0
    assert len(out["segments"]) == 1
    seg = out["segments"][0]
    assert seg["wpm"] == 225.0
    assert seg["severity"] == "warn"
    assert any(r.get("check") == "speaking_rate" for r in out["flagged_regions"])


def test_spec03_critical_tag_threshold_adjustment():
    from tools.check_speaking_rate import check_speaking_rate

    out = check_speaking_rate.func(
        phrase_spans=[
            {
                "phrase_id": "critical",
                "start_sec": 0.0,
                "end_sec": 4.0,
                "word_count": 14,
                "duration_sec": 4.0,
                "tags": ["red_flag"],
                "text": "critical segment",
            },
            {
                "phrase_id": "normal",
                "start_sec": 4.0,
                "end_sec": 8.0,
                "word_count": 14,
                "duration_sec": 4.0,
                "tags": [],
                "text": "normal segment",
            },
        ],
        language="en",
        config={"critical_tags": ["red_flag", "meds"]},
    )

    by_id = {s["phrase_id"]: s for s in out["segments"]}
    assert by_id["critical"]["rate_value"] == 210.0
    assert by_id["normal"]["rate_value"] == 210.0
    assert by_id["critical"]["severity"] == "warn"
    assert by_id["normal"]["severity"] == "ok"


def test_spec03_empty_and_single_word_spans():
    from tools.check_speaking_rate import check_speaking_rate

    empty = check_speaking_rate.invoke({"phrase_spans": [], "language": "en"})
    assert empty["skipped"] is True
    assert empty["segments"] == []
    assert empty["flagged_regions"] == []

    single = check_speaking_rate.invoke(
        {
            "phrase_spans": [
                {
                    "phrase_id": 7,
                    "words": [{"word": "hello", "start_sec": 1.0, "end_sec": 1.5}],
                }
            ],
            "language": "en",
        }
    )

    assert len(single["segments"]) == 1
    seg = single["segments"][0]
    assert seg["word_count"] == 1
    assert seg["wpm"] == 120.0
