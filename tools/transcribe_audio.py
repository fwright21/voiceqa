import os
from pathlib import Path
from langchain_core.tools import tool
import whisper

# This loads the model once and reuses it for every call.
# Loading Whisper takes a few seconds so we don't want to 
# reload it on every transcription request.
_model = None

def _get_model():
    global _model
    if _model is None:
        model_name = os.getenv("WHISPER_MODEL", "small")
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
          - transcript: the full transcribed text
          - language:   detected language code e.g. "en"
          - segments:   list of timed chunks with start/end/text
    """
    # Make sure the file actually exists before we do anything
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    model = _get_model()

    # This is the core call — Whisper reads the file and returns
    # a dict with the full transcript plus segment-level detail
    result = model.transcribe(str(path), verbose=False)

    # We clean up the segments to only return what's useful to us
    segments = [
        {
            "id":    seg["id"],
            "start": round(seg["start"], 3),  # seconds
            "end":   round(seg["end"], 3),
            "text":  seg["text"].strip(),
        }
        for seg in result.get("segments", [])
    ]

    return {
        "transcript": result["text"].strip(),
        "language":   result.get("language", "unknown"),
        "segments":   segments,
    }