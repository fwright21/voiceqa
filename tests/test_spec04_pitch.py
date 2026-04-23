from __future__ import annotations


def test_spec04_f0_std_dev_computation():
    from tools.analyse_prosody import _f0_std

    assert _f0_std([100.0, 110.0, 120.0]) == 10.0
    assert _f0_std([150.0]) is None


def test_spec04_monotone_severity_thresholds():
    from tools.analyse_prosody import _monotone_severity

    assert _monotone_severity(5.0) == "fail"
    assert _monotone_severity(10.0) == "warn"
    assert _monotone_severity(30.0) == "ok"
    assert _monotone_severity(90.0) == "warn"


def test_spec04_analyse_prosody_graceful_skip_on_error():
    from tools.analyse_prosody import analyse_prosody

    out = analyse_prosody.invoke({"audio_path": "/path/that/does/not/exist.wav", "language": "en"})

    assert out["skipped"] is True
    assert out.get("error")
    assert out["f0_std"] is None
    assert out["monotone_severity"] is None
    assert out["flagged_regions"] == []
