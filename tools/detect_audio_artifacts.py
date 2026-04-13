from pathlib import Path
import numpy as np
from langchain_core.tools import tool

from tools.audio_io import load_mono_audio

@tool("detect_audio_artifacts")
def detect_audio_artifacts(audio_path: str) -> dict:
    """
    Scan an audio file for common quality artifacts: clipping, DC offset,
    high-frequency noise, and pop/click transients.

    Args:
        audio_path: Path to the audio file.

    Returns:
        A dict with detected artifacts, their severity, and overall clean status.
    """
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    y, sr = load_mono_audio(str(path))
    artifacts = []

    # ---- 1. CLIPPING ----
    clipped = int(np.sum(np.abs(y) >= 0.98))
    clipping_pct = round(100.0 * clipped / len(y), 4)
    clipping_detected = clipping_pct > 0.01
    if clipping_pct > 0.01:
        artifacts.append({
            "type":     "clipping",
            "severity": "high" if clipping_pct > 1.0 else "low",
            "detail":   f"{clipping_pct:.3f}% of samples are clipped",
        })

    # ---- 2. DC OFFSET ----
    dc_offset = float(np.mean(y))
    if abs(dc_offset) > 0.01:
        artifacts.append({
            "type":     "dc_offset",
            "severity": "medium" if abs(dc_offset) > 0.05 else "low",
            "detail":   f"Mean amplitude = {dc_offset:.4f} (should be ~0)",
        })

    # ---- 3. HIGH FREQUENCY NOISE ----
    freqs    = np.fft.rfftfreq(len(y), d=1.0 / sr)
    fft_mag  = np.abs(np.fft.rfft(y))
    total_e  = float(np.sum(fft_mag ** 2)) + 1e-10
    hf_e     = float(np.sum(fft_mag[freqs > 8000] ** 2))
    noise_ratio = round(hf_e / total_e, 4)
    if noise_ratio > 0.15:
        artifacts.append({
            "type":     "high_frequency_noise",
            "severity": "high" if noise_ratio > 0.3 else "medium",
            "detail":   f"High-freq energy = {noise_ratio * 100:.1f}% of total",
        })

    # ---- 4. POPS / CLICKS ----
    diff     = np.abs(np.diff(y))
    pop_mask = diff > 0.3
    pop_count = int(np.sum(pop_mask))
    if pop_count > 0:
        pop_times = (np.where(pop_mask)[0].astype(np.float64) / float(sr)).tolist()
        artifacts.append({
            "type":     "pops_clicks",
            "severity": "high" if pop_count > 10 else "low",
            "detail":   f"{pop_count} transients. Times: {[round(t,3) for t in pop_times[:5]]}",
        })

    return {
        "artifacts":      artifacts,
        "artifact_count": len(artifacts),
        "clipping_pct":   clipping_pct,
        "clipping_detected": clipping_detected,
        "dc_offset":      round(dc_offset, 6),
        "noise_ratio":    noise_ratio,
        "pop_count":      pop_count,
        "overall_clean":  len(artifacts) == 0,
    }
