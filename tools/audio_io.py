from __future__ import annotations

from pathlib import Path
from typing import Tuple

import numpy as np


def load_mono_audio(audio_path: str) -> Tuple[np.ndarray, int]:
    """
    Load an audio file as mono float32 samples and return (samples, sample_rate).

    Notes:
    - This intentionally avoids librosa because importing librosa's audio backend
      can trigger numba caching issues in some environments.
    - Primary loader is soundfile, which supports WAV/FLAC/OGG and other formats
      depending on the local libsndfile build.
    """
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    try:
        import soundfile as sf
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"soundfile is required to load audio ({exc})")

    try:
        audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
    except Exception as exc:
        raise RuntimeError(f"Failed to read audio via soundfile: {exc}")

    if audio.size == 0 or sr <= 0:
        raise ValueError("Audio file appears empty or has invalid sample rate.")

    # audio shape: (n_samples, n_channels)
    mono = np.mean(audio, axis=1)
    return mono, int(sr)


def resample_mono(audio: np.ndarray, sr: int, target_sr: int) -> np.ndarray:
    """Resample mono float audio to target_sr using polyphase filtering."""
    if sr == target_sr:
        return audio

    if sr <= 0 or target_sr <= 0:
        raise ValueError("Sample rates must be positive.")

    from math import gcd
    from scipy.signal import resample_poly

    g = gcd(sr, target_sr)
    up = target_sr // g
    down = sr // g
    return resample_poly(audio, up, down).astype(np.float32, copy=False)

