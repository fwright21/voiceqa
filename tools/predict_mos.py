"""
MOS (Mean Opinion Score) prediction using SpeechMOS DNSMOS.

UTMOS was tested and rejected — requires PyTorch >= 2.4 and fairseq has a
Python 3.11 dataclasses incompatibility. SpeechMOS is used instead.

SpeechMOS DNSMOS returns:
  - ovrl_mos  : overall naturalness (this is our primary MOS score)
  - sig_mos   : signal quality
  - bak_mos   : background noise quality
  - p808_mos  : perceptual quality (ITU-T P.808)

Requires 16kHz mono audio — we resample via scipy before scoring.
Fails gracefully — returns error dict if speechmos or onnxruntime is unavailable.
"""

from langchain_core.tools import tool

from tools.audio_io import load_mono_audio, resample_mono


@tool("predict_mos")
def predict_mos(audio_path: str) -> dict:
    """
    Predict MOS (Mean Opinion Score) for an audio file using SpeechMOS DNSMOS.

    Args:
        audio_path: Path to the audio file.

    Returns:
        Dict with mos_score (ovrl_mos 1–5), sig_mos, bak_mos, p808_mos — or error dict.
    """
    try:
        from speechmos import dnsmos

        # SpeechMOS requires exactly 16kHz mono
        audio, sr = load_mono_audio(audio_path)
        audio = resample_mono(audio, sr, 16000)

        result = dnsmos.run(audio, 16000)

        mos_score = result.get("ovrl_mos")

        return {
            "mos_score":  round(float(mos_score), 3) if mos_score is not None else None,
            "sig_mos":    round(float(result.get("sig_mos", 0)), 3),
            "bak_mos":    round(float(result.get("bak_mos", 0)), 3),
            "p808_mos":   round(float(result.get("p808_mos", 0)), 3),
            "model":      "speechmos-dnsmos",
            "skipped":    False,
        }

    except ImportError as e:
        return {
            "error": f"Missing dependency: {e}",
            "skipped": True,
            "mos_score": None,
        }
    except Exception as e:
        return {
            "error": str(e),
            "skipped": True,
            "mos_score": None,
        }
