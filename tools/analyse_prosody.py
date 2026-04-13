"""
Prosody analysis using parselmouth (Python binding for Praat).

Extracts four acoustic features that indicate how natural the voice sounds:
  - F0 mean     : average pitch in Hz (natural speech: 80–300 Hz)
  - Jitter      : cycle-to-cycle pitch variation (natural: < 2%, abnormal: > 5%)
  - Shimmer     : cycle-to-cycle amplitude variation (natural: < 10%, abnormal: > 15%)
  - HNR         : Harmonics-to-Noise Ratio in dB (clean: > 10 dB, noisy: < 5 dB)

Returns a prosody_score 0–100 based on how far each value falls from natural ranges.
Fails gracefully — returns error dict if parselmouth is unavailable or audio is silent.
"""

from langchain_core.tools import tool


def _score_from_metrics(f0_mean, jitter, shimmer, hnr) -> float:
    """
    Convert raw prosody metrics into a 0–100 score.
    100 = perfectly natural, 0 = severely abnormal.
    Each metric contributes 25 points.
    """
    score = 100.0

    # F0: penalise if outside 80–300 Hz or zero (silence / unvoiced)
    if f0_mean is None or f0_mean == 0:
        score -= 25
    elif f0_mean < 80 or f0_mean > 300:
        score -= 15

    # Jitter: 0–2% is fine, 2–5% minor penalty, >5% major penalty
    if jitter is None:
        score -= 10
    elif jitter > 0.05:
        score -= 25
    elif jitter > 0.02:
        score -= 10

    # Shimmer: 0–10% fine, 10–15% minor, >15% major
    if shimmer is None:
        score -= 10
    elif shimmer > 0.15:
        score -= 25
    elif shimmer > 0.10:
        score -= 10

    # HNR: >10 dB fine, 5–10 dB minor, <5 dB major
    if hnr is None:
        score -= 10
    elif hnr < 5.0:
        score -= 25
    elif hnr < 10.0:
        score -= 10

    return max(0.0, round(score, 1))


@tool("analyse_prosody")
def analyse_prosody(audio_path: str) -> dict:
    """
    Analyse prosody of an audio file using parselmouth (Praat).

    Args:
        audio_path: Path to the audio file.

    Returns:
        Dict with f0_mean, jitter, shimmer, hnr, prosody_score — or error dict on failure.
    """
    try:
        import parselmouth
        from parselmouth.praat import call

        snd = parselmouth.Sound(audio_path)

        # ── F0 (pitch) ────────────────────────────────────────────────────────
        pitch = snd.to_pitch()
        f0_values = [
            pitch.get_value_at_time(t)
            for t in pitch.xs()
            if pitch.get_value_at_time(t) is not None
            and not (pitch.get_value_at_time(t) != pitch.get_value_at_time(t))  # NaN check
        ]
        f0_mean = round(sum(f0_values) / len(f0_values), 2) if f0_values else 0.0

        # ── Point process for jitter and shimmer ──────────────────────────────
        point_process = call(snd, "To PointProcess (periodic, cc)", 75, 500)

        # Jitter: local jitter (relative, dimensionless ratio)
        jitter = call(
            [snd, point_process],
            "Get shimmer (local)",  # note: intentional — Praat API quirk
            0, 0, 0.0001, 0.02, 1.3, 1.6,
        )
        # Correct call for jitter
        jitter = call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)

        # Shimmer: local shimmer (relative)
        shimmer = call(
            [snd, point_process],
            "Get shimmer (local)",
            0, 0, 0.0001, 0.02, 1.3, 1.6,
        )

        # ── HNR ───────────────────────────────────────────────────────────────
        harmonicity = call(snd, "To Harmonicity (cc)", 0.01, 75, 0.1, 1.0)
        hnr = call(harmonicity, "Get mean", 0, 0)

        prosody_score = _score_from_metrics(f0_mean, jitter, shimmer, hnr)

        return {
            "f0_mean":       f0_mean,
            "jitter":        round(jitter, 5) if jitter else None,
            "shimmer":       round(shimmer, 5) if shimmer else None,
            "hnr":           round(hnr, 2) if hnr else None,
            "prosody_score": prosody_score,
            "skipped":       False,
        }

    except ImportError:
        return {
            "error": "praat-parselmouth not installed",
            "skipped": True,
            "f0_mean": None, "jitter": None, "shimmer": None,
            "hnr": None, "prosody_score": None,
        }
    except Exception as e:
        return {
            "error": str(e),
            "skipped": True,
            "f0_mean": None, "jitter": None, "shimmer": None,
            "hnr": None, "prosody_score": None,
        }
