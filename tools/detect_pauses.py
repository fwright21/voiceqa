from pathlib import Path
import numpy as np
from langchain_core.tools import tool

from tools.audio_io import load_mono_audio

@tool("detect_pauses")
def detect_pauses(audio_path: str, min_pause_sec: float = 0.5) -> dict:
    """
    Detect unnatural silence gaps in an audio file.
    Flags any pause longer than min_pause_sec (default 0.5 seconds).

    Args:
        audio_path:    Path to the audio file.
        min_pause_sec: Minimum duration in seconds to flag as a pause.

    Returns:
        A dict with pause events, total pause time, and audio duration.
    """
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    y, sr = load_mono_audio(str(path))
    audio_duration = float(len(y) / sr)

    frame_length = 2048
    hop_length = 512
    if len(y) < frame_length:
        return {
            "pauses":               [],
            "pause_count":          0,
            "total_pause_time_sec": 0.0,
            "longest_pause_sec":    0.0,
            "audio_duration_sec":   round(audio_duration, 3),
        }

    # Compute RMS energy per frame without librosa to avoid numba/librosa import issues.
    frame_starts = np.arange(0, len(y) - frame_length + 1, hop_length, dtype=int)
    frames = np.stack([y[s : s + frame_length] for s in frame_starts], axis=0)
    rms = np.sqrt(np.mean(frames * frames, axis=1))

    # Convert -40 dBFS to a linear amplitude threshold
    # Anything quieter than this we consider "silence"
    silence_threshold = 10 ** (-40 / 20.0)

    # Frame timestamps (seconds)
    times = frame_starts.astype(np.float64) / float(sr)

    # Walk through the frames and group consecutive silent ones
    pauses = []
    in_pause = False
    pause_start = 0.0

    for i, energy in enumerate(rms):
        if energy < silence_threshold and not in_pause:
            in_pause = True
            pause_start = float(times[i])
        elif energy >= silence_threshold and in_pause:
            in_pause = False
            duration = float(times[i]) - pause_start
            if duration >= min_pause_sec:
                pauses.append({
                    "start_sec":    round(pause_start, 3),
                    "end_sec":      round(float(times[i]), 3),
                    "duration_sec": round(duration, 3),
                })

    # If we end in a pause, close it at the end of the audio.
    if in_pause:
        duration = float(audio_duration) - pause_start
        if duration >= min_pause_sec:
            pauses.append({
                "start_sec":    round(pause_start, 3),
                "end_sec":      round(float(audio_duration), 3),
                "duration_sec": round(duration, 3),
            })

    return {
        "pauses":               pauses,
        "pause_count":          len(pauses),
        "total_pause_time_sec": round(sum(p["duration_sec"] for p in pauses), 3),
        "longest_pause_sec":    round(max((p["duration_sec"] for p in pauses), default=0.0), 3),
        "audio_duration_sec":   round(audio_duration, 3),
    }
