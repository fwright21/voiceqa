"""
Prosody analysis using parselmouth (Python binding for Praat).

Extracts four acoustic features that indicate how natural the voice sounds:
  - F0 mean     : average pitch in Hz (natural speech: 80–300 Hz)
  - F0 std      : standard deviation of pitch (monotone detection)
  - Jitter      : cycle-to-cycle pitch variation (natural: < 2%, abnormal: > 5%)
  - Shimmer     : cycle-to-cycle amplitude variation (natural: < 10%, abnormal: > 15%)
  - HNR         : Harmonics-to-Noise Ratio in dB (clean: > 10 dB, noisy: < 5 dB)

Returns a prosody_score 0–100 based on how far each value falls from natural ranges.
Fails gracefully — returns error dict if parselmouth is unavailable or audio is silent.
"""

import statistics
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

F0_RANGES = {
    "en": {"min": 85, "max": 255},
    "es": {"min": 90, "max": 265},
    "unknown": {"min": 75, "max": 310},
}

MONOTONE_THRESHOLDS = {
    "fail": 8,
    "warn": 15,
    "ok_min": 15,
    "warn_max": 80,
}


def _f0_std(f0_values: List[float]) -> Optional[float]:
    """Compute standard deviation of F0 values."""
    if not f0_values or len(f0_values) < 2:
        return None
    try:
        return round(statistics.stdev(f0_values), 2)
    except statistics.StatisticsError:
        return None


def _monotone_severity(f0_std: Optional[float]) -> str:
    """Determine severity from F0 standard deviation."""
    if f0_std is None:
        return "ok"
    if f0_std < MONOTONE_THRESHOLDS["fail"]:
        return "fail"
    elif f0_std < MONOTONE_THRESHOLDS["warn"]:
        return "warn"
    elif f0_std > MONOTONE_THRESHOLDS["warn_max"]:
        return "warn"
    return "ok"


def _score_from_metrics(
    f0_mean: Optional[float],
    f0_std: Optional[float],
    jitter: Optional[float],
    shimmer: Optional[float],
    hnr: Optional[float],
    language: str = "en",
) -> float:
    """
    Convert raw prosody metrics into a 0–100 score.
    100 = perfectly natural, 0 = severely abnormal.
    Each metric contributes ~20-25 points.
    """
    score = 100.0

    f0_range = F0_RANGES.get(language, F0_RANGES["unknown"])
    f0_min = f0_range["min"]
    f0_max = f0_range["max"]

    # F0: penalise if outside language-specific range or zero (silence / unvoiced)
    if f0_mean is None or f0_mean == 0:
        score -= 20
    elif f0_mean < f0_min or f0_mean > f0_max:
        score -= 10

    # F0 std (monotone detection)
    if f0_std is not None:
        if f0_std < MONOTONE_THRESHOLDS["fail"]:
            score -= 15
        elif f0_std < MONOTONE_THRESHOLDS["warn"]:
            score -= 10

    # Jitter: 0–2% is fine, 2–5% minor penalty, >5% major penalty
    if jitter is None:
        score -= 10
    elif jitter > 0.05:
        score -= 20
    elif jitter > 0.02:
        score -= 10

    # Shimmer: 0–10% fine, 10–15% minor, >15% major
    if shimmer is None:
        score -= 10
    elif shimmer > 0.15:
        score -= 20
    elif shimmer > 0.10:
        score -= 10

    # HNR: >10 dB fine, 5–10 dB minor, <5 dB major
    if hnr is None:
        score -= 10
    elif hnr < 5.0:
        score -= 20
    elif hnr < 10.0:
        score -= 10

    return max(0.0, round(score, 1))


@tool("analyse_prosody")
def analyse_prosody(audio_path: str, language: str = "en") -> dict:
    """
    Analyse prosody of an audio file using parselmouth (Praat).

    Args:
        audio_path: Path to the audio file.
        language: Language code for F0 range (en/es/unknown). Default "en".

    Returns:
        Dict with f0_mean, f0_std, jitter, shimmer, hnr, prosody_score,
        monotone detection fields, and flagged_regions.
    """
    try:
        import parselmouth
        from parselmouth.praat import call

        snd = parselmouth.Sound(audio_path)

        pitch = snd.to_pitch()
        f0_values = [
            pitch.get_value_at_time(t)
            for t in pitch.xs()
            if pitch.get_value_at_time(t) is not None
            and not (pitch.get_value_at_time(t) != pitch.get_value_at_time(t))
        ]
        f0_mean = round(sum(f0_values) / len(f0_values), 2) if f0_values else 0.0
        f0_std = _f0_std(f0_values)

        point_process = call(snd, "To PointProcess (periodic, cc)", 75, 500)

        jitter = call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)

        shimmer = call(
            [snd, point_process],
            "Get shimmer (local)",
            0,
            0,
            0.0001,
            0.02,
            1.3,
            1.6,
        )

        harmonicity = call(snd, "To Harmonicity (cc)", 0.01, 75, 0.1, 1.0)
        hnr = call(harmonicity, "Get mean", 0, 0)

        prosody_score = _score_from_metrics(
            f0_mean, f0_std, jitter, shimmer, hnr, language
        )

        monotone_severity = _monotone_severity(f0_std)
        is_monotone = monotone_severity in ("warn", "fail")

        flagged_regions: List[Dict[str, Any]] = []
        if is_monotone:
            label = "Monotone delivery (flat pitch)"
            flagged_regions.append(
                {
                    "check": "pitch_monotone",
                    "label": label,
                    "severity": monotone_severity,
                    "start_sec": None,
                    "end_sec": None,
                }
            )

        return {
            "f0_mean": f0_mean,
            "f0_std": f0_std,
            "monotone": is_monotone,
            "monotone_severity": monotone_severity,
            "f0_contour": None,
            "intonation_check": None,
            "jitter": round(jitter, 5) if jitter is not None else None,
            "shimmer": round(shimmer, 5) if shimmer is not None else None,
            "hnr": round(hnr, 2) if hnr is not None else None,
            "prosody_score": prosody_score,
            "skipped": False,
            "flagged_regions": flagged_regions,
        }

    except ImportError:
        return {
            "error": "praat-parselmouth not installed",
            "skipped": True,
            "f0_mean": None,
            "f0_std": None,
            "monotone": None,
            "monotone_severity": None,
            "f0_contour": None,
            "intonation_check": None,
            "jitter": None,
            "shimmer": None,
            "hnr": None,
            "prosody_score": None,
            "flagged_regions": [],
        }
    except Exception as e:
        return {
            "error": str(e),
            "skipped": True,
            "f0_mean": None,
            "f0_std": None,
            "monotone": None,
            "monotone_severity": None,
            "f0_contour": None,
            "intonation_check": None,
            "jitter": None,
            "shimmer": None,
            "hnr": None,
            "prosody_score": None,
            "flagged_regions": [],
        }
