import numpy as np


def test_insert_silence_increases_length():
    from tools.audio_postprocess import insert_silence

    sr = 16000
    audio = np.zeros((sr,), dtype=np.float32)  # 1s
    out = insert_silence(audio, sr, duration_sec=0.5, at_frac=0.5)
    assert len(out) == len(audio) + int(0.5 * sr)


def test_time_stretch_resample_changes_length():
    from tools.audio_postprocess import time_stretch_resample

    audio = np.zeros((16000,), dtype=np.float32)
    faster = time_stretch_resample(audio, 1.25)
    slower = time_stretch_resample(audio, 0.8)
    assert len(faster) < len(audio)
    assert len(slower) > len(audio)

