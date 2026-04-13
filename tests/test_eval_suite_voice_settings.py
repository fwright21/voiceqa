def test_load_suite_accepts_voice_settings_object():
    from tools.eval_runner import load_suite

    _, cases = load_suite("prosody-demo")
    assert len(cases) >= 1
    assert any((c.voice_settings or {}).get("speed") is not None for c in cases)

