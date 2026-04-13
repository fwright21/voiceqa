from tools.check_vitals_fidelity import check_vitals_fidelity


def test_vitals_fidelity_spo2_words_match_digits():
    result = check_vitals_fidelity.invoke({
        "expected": "If you have a pulse oximeter, what is your oxygen saturation? For example, 92 percent.",
        "transcript": "My oxygen saturation is ninety two percent.",
    })
    assert result["mismatch_count"] == 0


def test_vitals_fidelity_bp_words_match_digits():
    result = check_vitals_fidelity.invoke({
        "expected": "If you have a blood pressure reading, please say it like 180 over 110.",
        "transcript": "My blood pressure is one eighty over one ten.",
    })
    assert result["mismatch_count"] == 0


def test_vitals_fidelity_temp_decimal_words_match_digits():
    result = check_vitals_fidelity.invoke({
        "expected": "My temperature is 102.4 degrees.",
        "transcript": "My temperature is one hundred two point four degrees.",
    })
    assert result["mismatch_count"] == 0

