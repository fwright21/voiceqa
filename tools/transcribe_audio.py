import os
from pathlib import Path
from langchain_core.tools import tool
import whisper
from tools.model_config import get_model

# This loads the model once and reuses it for every call.
# Loading Whisper takes a few seconds so we don't want to
# reload it on every transcription request.
_model = None

def _get_model():
    global _model
    if _model is None:
        model_name = get_model("whisper")
        print(f"Loading Whisper model: {model_name}...")
        _model = whisper.load_model(model_name)
        print("Model loaded.")
    return _model


@tool
def transcribe_audio(audio_path: str) -> dict:
    """
    Transcribe a local audio file to text using Whisper.

    Args:
        audio_path: Path to the audio file (wav, mp3, m4a, ogg, flac)

    Returns:
        A dict with:
          - transcript:        the full transcribed text
          - language:          detected language code e.g. "en"
          - segments:          list of timed chunks with start/end/text
          - avg_logprob:       mean log-probability across segments (confidence proxy)
          - no_speech_prob:    mean no-speech probability across segments
          - transcript_confidence: "low" if audio is likely silent/unintelligible, else "ok"
    """
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    model = _get_model()

    # Prefer word-level timestamps when available in the installed whisper version.
    # This enables alignment-first scoring (pause placement, speaking rate, etc.)
    # without requiring a separate forced-alignment dependency.
    try:
        result = model.transcribe(str(path), verbose=False, word_timestamps=True)
    except TypeError:
        result = model.transcribe(str(path), verbose=False)

    raw_segments = result.get("segments", [])

    segments = [
        {
            "id":    seg["id"],
            "start": round(seg["start"], 3),
            "end":   round(seg["end"], 3),
            "text":  seg["text"].strip(),
            "words": [
                {
                    "word": (w.get("word") or "").strip(),
                    "start": round(float(w.get("start")), 3) if w.get("start") is not None else None,
                    "end": round(float(w.get("end")), 3) if w.get("end") is not None else None,
                    "probability": round(float(w.get("probability")), 4) if w.get("probability") is not None else None,
                }
                for w in (seg.get("words") or [])
                if isinstance(w, dict)
            ] if isinstance(seg, dict) and isinstance(seg.get("words"), list) else None,
        }
        for seg in raw_segments
    ]

    word_spans = []
    for seg in segments:
        words = seg.get("words")
        if not words:
            continue
        for w in words:
            if not w.get("word"):
                continue
            word_spans.append(w)

    # Compute confidence signals across all segments
    avg_logprob = (
        sum(s.get("avg_logprob", 0.0) for s in raw_segments) / len(raw_segments)
        if raw_segments else 0.0
    )
    no_speech_prob = (
        sum(s.get("no_speech_prob", 0.0) for s in raw_segments) / len(raw_segments)
        if raw_segments else 1.0
    )

    # Gate: flag as low confidence if audio is likely silence or noise
    transcript_confidence = (
        "low" if (no_speech_prob > 0.7 or avg_logprob < -1.0) else "ok"
    )

    return {
        "transcript":             result["text"].strip(),
        "language":               result.get("language", "unknown"),
        "segments":               segments,
        "word_spans":             word_spans or None,
        "avg_logprob":            round(avg_logprob, 4),
        "no_speech_prob":         round(no_speech_prob, 4),
        "transcript_confidence":  transcript_confidence,
    }
