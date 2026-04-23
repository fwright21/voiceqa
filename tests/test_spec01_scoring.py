from tools.eval_runner import compute_weighted_score


def test_spec01_all_checks_ok_scores_100_and_passes():
    metrics = {
        "critical_term_missing": {"severity": "ok"},
        "unnatural_pause": {"severity": "ok"},
        "mos": {"severity": "info"},
    }

    result = compute_weighted_score(metrics)

    assert result["score"] == 100
    assert result["verdict"] == "PASS"
    assert result["score_breakdown"] == []


def test_spec01_two_warn_scores_90_and_passes():
    metrics = {
        "unnatural_pause": {"severity": "warn"},
        "speaking_rate_out_of_range": {"severity": "warn"},
    }

    result = compute_weighted_score(metrics)

    assert result["score"] == 90
    assert result["verdict"] == "PASS"
    assert len(result["score_breakdown"]) == 2


def test_spec01_one_fail_scores_at_most_69_and_fails():
    metrics = {
        "name_fidelity_fail": {"severity": "fail"},
    }

    result = compute_weighted_score(metrics)

    assert result["score"] <= 69
    assert result["verdict"] == "FAIL"


def test_spec01_prosodic_failures_are_capped_at_review():
    metrics = {
        "unnatural_pause": {"severity": "fail"},
        "speaking_rate_out_of_range": {"severity": "fail"},
        "pitch_monotone": {"severity": "fail"},
    }

    result = compute_weighted_score(metrics)

    assert result["verdict"] == "REVIEW"


def test_spec01_config_overrides_penalties():
    metrics = {
        "unnatural_pause": {"severity": "warn"},
    }
    config = {
        "scoring": {
            "warn_penalty": 1,
            "fail_penalty": 7,
            "verdict_thresholds": {"pass": 90, "review": 70},
        }
    }

    result = compute_weighted_score(metrics, config=config)

    assert result["score"] == 99
    assert result["verdict"] == "PASS"
    assert result["score_breakdown"][0]["penalty"] == -1
