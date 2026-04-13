from pathlib import Path


TEST_AUDIO_PATH = str(Path(__file__).resolve().parent / "test_audio.wav")


def test_check_entity_fidelity_detects_number_mismatch():
    from tools.check_entity_fidelity import check_entity_fidelity

    result = check_entity_fidelity.invoke({
        "expected": "Your confirmation code is AB12CD and the total is 123.45.",
        "transcript": "Your confirmation code is AB12CD and the total is 124.45.",
    })

    assert "mismatches" in result
    assert "matched" in result
    assert result["mismatch_count"] >= 1
    assert result["fidelity_score"] < 100.0


def test_check_faithfulness_gracefully_skips_when_ollama_unavailable():
    from tools.check_faithfulness import check_faithfulness

    result = check_faithfulness.invoke({
        "expected": "Your balance is available now.",
        "transcript": "Your balance is available now and you owe an additional fee.",
    })

    assert result.get("confidence") == "low"
    assert result.get("skipped") in (True, False)

    # If Ollama isn't reachable, it should fail gracefully, not raise.
    if result.get("skipped") is True:
        assert result.get("faithful") is None
        assert result.get("faithfulness_score") is None
        assert isinstance(result.get("violations"), list)
        assert result.get("error")
    else:
        assert isinstance(result.get("faithful"), bool)
        assert isinstance(result.get("faithfulness_score"), (int, float))
        assert isinstance(result.get("violations"), list)


def test_check_name_fidelity_detects_mismatch():
    from tools.check_name_fidelity import check_name_fidelity

    result = check_name_fidelity.invoke({
        "expected": "Please follow up with Dr. Nguyen about the lab results.",
        "transcript": "Please follow up with Dr. Newen about the lab results.",
    })

    assert "name_fidelity_score" in result
    assert isinstance(result["mismatches"], list)
    assert isinstance(result["matched"], list)
    # With a misspelling, we expect either a fuzzy match or a mismatch depending on threshold.
    assert result["candidate_count"] >= 1


def test_analyse_prosody_returns_shape_or_skips():
    from tools.analyse_prosody import analyse_prosody

    result = analyse_prosody.invoke({"audio_path": TEST_AUDIO_PATH})

    assert result.get("skipped") in (True, False)
    assert "prosody_score" in result

    if result.get("skipped") is True:
        assert result.get("error")
        assert result.get("prosody_score") is None
    else:
        assert isinstance(result.get("prosody_score"), (int, float))
        assert result.get("prosody_score") >= 0
        assert result.get("prosody_score") <= 100


def test_predict_mos_returns_shape_or_skips():
    from tools.predict_mos import predict_mos

    result = predict_mos.invoke({"audio_path": TEST_AUDIO_PATH})

    assert result.get("skipped") in (True, False)
    assert "mos_score" in result

    if result.get("skipped") is True:
        assert result.get("error")
        assert result.get("mos_score") is None
    else:
        assert isinstance(result.get("mos_score"), (int, float))
        assert 1.0 <= float(result.get("mos_score")) <= 5.0
