from __future__ import annotations

from dataclasses import dataclass
from math import gcd
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from tools.audio_io import load_mono_audio


def _write_mono_wav(path: Path, audio: np.ndarray, sr: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import soundfile as sf
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"soundfile is required to write audio ({exc})")
    sf.write(str(path), audio.astype("float32", copy=False), int(sr))


def insert_silence(
    audio: np.ndarray,
    sr: int,
    *,
    duration_sec: float,
    at_sec: Optional[float] = None,
    at_frac: Optional[float] = None,
) -> np.ndarray:
    if duration_sec <= 0:
        return audio
    if sr <= 0:
        raise ValueError("Invalid sample rate.")

    n = len(audio)
    if n == 0:
        return audio

    if at_sec is None and at_frac is None:
        at_frac = 0.5

    if at_sec is None:
        at_sec = float(max(0.0, min(float(n) / float(sr), float(at_frac) * (float(n) / float(sr)))))

    at_sample = int(round(float(at_sec) * float(sr)))
    at_sample = max(0, min(n, at_sample))

    silence_samples = int(round(float(duration_sec) * float(sr)))
    if silence_samples <= 0:
        return audio

    silence = np.zeros((silence_samples,), dtype=np.float32)
    return np.concatenate([audio[:at_sample], silence, audio[at_sample:]]).astype(np.float32, copy=False)


def time_stretch_resample(audio: np.ndarray, rate: float) -> np.ndarray:
    """
    Simple time-stretch via resampling.
    rate > 1.0 => faster (shorter audio)
    rate < 1.0 => slower (longer audio)

    Note: this changes pitch (demo-only). For pitch-preserving stretch, we'd need a phase vocoder.
    """
    if rate is None:
        return audio
    rate = float(rate)
    if rate <= 0:
        raise ValueError("rate must be > 0")
    if abs(rate - 1.0) < 1e-6:
        return audio

    from scipy.signal import resample_poly

    # Resample by 1/rate using polyphase filtering.
    # Use integer ratio with a fixed base for stability.
    base = 1000
    up = base
    down = int(round(base * rate))
    g = gcd(up, down)
    up //= g
    down //= g
    return resample_poly(audio, up, down).astype(np.float32, copy=False)


def apply_postprocess_file(audio_path: Path, postprocess: Dict[str, Any], overwrite: bool = True) -> dict:
    if not audio_path.exists():
        return {"applied": False, "skipped": True, "error": f"Audio not found: {audio_path}"}
    if not isinstance(postprocess, dict) or not postprocess:
        return {"applied": False, "skipped": True, "error": "No postprocess config"}

    audio, sr = load_mono_audio(str(audio_path))
    original_len = len(audio)

    # Supported transforms:
    # - insert_silence: {"duration_sec": 1.8, "at_frac": 0.55} or {"at_sec": 1.2, ...}
    # - insert_silences: [ {..}, {..} ]
    # - time_stretch: {"rate": 1.15}
    try:
        if isinstance(postprocess.get("time_stretch"), dict):
            rate = postprocess["time_stretch"].get("rate")
            if rate is not None:
                audio = time_stretch_resample(audio, float(rate))

        if isinstance(postprocess.get("insert_silence"), dict):
            cfg = postprocess["insert_silence"]
            audio = insert_silence(
                audio,
                sr,
                duration_sec=float(cfg.get("duration_sec", 0)),
                at_sec=cfg.get("at_sec"),
                at_frac=cfg.get("at_frac"),
            )

        if isinstance(postprocess.get("insert_silences"), list):
            for cfg in postprocess["insert_silences"]:
                if not isinstance(cfg, dict):
                    continue
                audio = insert_silence(
                    audio,
                    sr,
                    duration_sec=float(cfg.get("duration_sec", 0)),
                    at_sec=cfg.get("at_sec"),
                    at_frac=cfg.get("at_frac"),
                )

    except Exception as exc:
        return {"applied": False, "skipped": False, "error": str(exc)}

    out_path = audio_path if overwrite else audio_path.with_suffix(f".post{audio_path.suffix}")
    _write_mono_wav(out_path, audio, sr)

    return {
        "applied": True,
        "skipped": False,
        "path": str(out_path),
        "sr": sr,
        "samples_before": int(original_len),
        "samples_after": int(len(audio)),
    }

