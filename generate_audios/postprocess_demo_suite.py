"""
Postprocess demo-test-suite audio: insert awkward pauses into dt-004-prosody-pause.
"""
import numpy as np
import soundfile as sf
from pathlib import Path

AUDIO_DIR = Path(__file__).parent.parent / "eval_set/suites/demo-test-suite/audio"


def insert_silences(path: Path, durations_at: list[tuple[float, float]]) -> None:
    data, sr = sf.read(path)
    total = len(data)
    result = []
    prev = 0
    for dur_sec, at_frac in sorted(durations_at, key=lambda x: x[1]):
        cut = int(at_frac * total)
        result.append(data[prev:cut])
        silence = np.zeros((int(dur_sec * sr),) if data.ndim == 1 else (int(dur_sec * sr), data.shape[1]))
        result.append(silence)
        prev = cut
    result.append(data[prev:])
    sf.write(path, np.concatenate(result), sr)
    print(f"  postprocessed: {path.name}")


if __name__ == "__main__":
    p = AUDIO_DIR / "dt-004-prosody-pause.wav"
    insert_silences(p, [(1.2, 0.35), (1.2, 0.7)])
    print("Done.")
