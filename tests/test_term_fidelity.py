from tools.check_term_fidelity import check_term_fidelity


def test_term_fidelity_exact_match_case_insensitive():
    result = check_term_fidelity.invoke({
        "transcript": "Patient reports DYSPNEA for two days.",
        "expected_terms": [{"term": "dyspnea", "criticality": "high"}],
    })
    assert result["mismatch_count"] == 0
    assert result["term_fidelity_score"] == 100.0


def test_term_fidelity_fuzzy_match_catches_minor_typo():
    result = check_term_fidelity.invoke({
        "transcript": "Patient reports hemopthysis yesterday.",
        "expected_terms": [{"term": "hemoptysis", "criticality": "high"}],
        "min_fuzzy_ratio": 0.85,
    })
    assert result["mismatch_count"] == 0
    assert result["term_fidelity_score"] == 100.0


def test_term_fidelity_mismatch():
    result = check_term_fidelity.invoke({
        "transcript": "Patient reports cough.",
        "expected_terms": [{"term": "paresthesia", "criticality": "high"}],
    })
    assert result["mismatch_count"] == 1
    assert result["term_fidelity_score"] == 0.0
    assert result["critical_mismatch_count"]["high"] == 1
