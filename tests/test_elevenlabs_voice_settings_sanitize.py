def test_sanitize_voice_settings_clamps_speed():
    from tools.generate_eval_audio_elevenlabs import _sanitize_voice_settings

    assert _sanitize_voice_settings(None) is None
    assert _sanitize_voice_settings({}) is None

    vs = _sanitize_voice_settings({"speed": 1.25, "stability": 0.2})
    assert vs["speed"] == 1.2
    assert vs["stability"] == 0.2

    vs2 = _sanitize_voice_settings({"speed": 0.1})
    assert vs2["speed"] == 0.7

