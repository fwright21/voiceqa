from tools.check_entity_fidelity import check_entity_fidelity


def test_entity_fidelity_digits_match_spelled_numbers():
    result = check_entity_fidelity.invoke({
        "expected": "Have the symptoms been present for 3 days, or did they start today?",
        "transcript": "Have the symptoms been present for three days, or did they start today?",
    })
    assert result["mismatch_count"] == 0
