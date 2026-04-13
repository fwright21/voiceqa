def test_load_suite_supports_audio_script_for_mismatch_demos():
    from tools.eval_runner import load_suite

    _, cases = load_suite("hallucination-demo")
    assert len(cases) >= 1

    first = cases[0]
    assert hasattr(first, "audio_script")
    assert isinstance(first.audio_script, str)
    assert first.audio_script.strip()

    # At least one case should intentionally differ.
    assert any(c.audio_script != c.expected_script for c in cases)

