import os
from pathlib import Path
import librosa
import numpy as np
from langchain_core.tools import tool

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

    # Load the audio as a numpy array
    # y = the audio samples, sr = sample rate (e.g. 44100 Hz)
    y, sr = librosa.load(str(path), sr=None, mono=True)
    audio_duration = float(len(y) / sr)

    # Compute RMS energy for each frame
    # RMS = Root Mean Square = a measure of how loud each chunk of audio is
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]

    # Convert -40 dBFS to a linear amplitude threshold
    # Anything quieter than this we consider "silence"
    silence_threshold = 10 ** (-40 / 20.0)

    # Build a list of timestamps for each frame
    times = librosa.frames_to_time(
        np.arange(len(rms)), sr=sr, hop_length=512
    )

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

    return {
        "pauses":               pauses,
        "pause_count":          len(pauses),
        "total_pause_time_sec": round(sum(p["duration_sec"] for p in pauses), 3),
        "longest_pause_sec":    round(max((p["duration_sec"] for p in pauses), default=0.0), 3),
        "audio_duration_sec":   round(audio_duration, 3),
    }