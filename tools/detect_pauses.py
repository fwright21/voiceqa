from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
from langchain_core.tools import tool

from tools.audio_io import load_mono_audio

FILLED_PAUSES = {
    "en": {"um", "uh", "er", "hmm", "erm"},
    "es": {"eh", "este", "mmm", "o sea", "bueno", "pues"},
}


def _classify_pause_by_phrase(
    pause_start: float,
    pause_end: float,
    phrase_spans: List[Dict[str, Any]],
    mid_phrase_threshold: float = 0.5,
) -> Dict[str, Any]:
    """Classify a pause using phrase span context.

    Returns:
        Dict with type (natural/unnatural/trailing), context, phrase_id, severity
    """
    if not phrase_spans:
        return {
            "type": "unknown",
            "context": "no_phrases",
            "phrase_id": None,
            "severity": "ok",
        }

    duration = pause_end - pause_start
    sorted_phrases = sorted(
        [
            (p.get("start_sec"), p.get("end_sec"), p.get("phrase_id"))
            for p in phrase_spans
            if isinstance(p, dict) and p.get("start_sec") is not None
        ],
        key=lambda x: x[0],
    )

    in_phrase = False
    containing_phrase = None
    for ps, pe, pid in sorted_phrases:
        if ps <= pause_start < pe or ps < pause_end <= pe:
            in_phrase = True
            containing_phrase = pid
            break

    if in_phrase:
        if duration > mid_phrase_threshold:
            severity = "fail" if duration >= 0.8 else "warn"
            return {
                "type": "unnatural",
                "context": "mid-phrase",
                "phrase_id": containing_phrase,
                "severity": severity,
            }
        else:
            return {
                "type": "natural",
                "context": "within_phrase_short",
                "phrase_id": containing_phrase,
                "severity": "ok",
            }
    else:
        is_between = False
        for i in range(1, len(sorted_phrases)):
            prev_end = sorted_phrases[i - 1][1]
            cur_start = sorted_phrases[i][0]
            if prev_end <= pause_start and pause_end <= cur_start:
                is_between = True
                break

        if is_between:
            return {
                "type": "natural",
                "context": "between_phrases",
                "phrase_id": None,
                "severity": "ok",
            }
        else:
            return {
                "type": "trailing",
                "context": "trailing_silence",
                "phrase_id": None,
                "severity": "warn" if duration > 3.0 else "ok",
            }


def detect_filled_pauses(
    transcript: str,
    word_spans: List[Dict[str, Any]] | None = None,
    language: str = "en",
    style: str = "formal",
) -> List[Dict[str, Any]]:
    """Detect filled pauses from transcript.

    Args:
        transcript: The transcript text
        word_spans: Optional word-level timestamps
        language: Language code (en/es)
        style: "formal" -> warn, "conversational" -> info

    Returns:
        List of filled pause events with timestamps
    """
    if not transcript:
        return []

    pause_words = FILLED_PAUSES.get(language, FILLED_PAUSES["en"])
    found: List[Dict[str, Any]] = []

    transcript_lower = transcript.lower()
    words = transcript_lower.split()

    def _clean_token(token: str) -> str:
        return str(token).lower().strip(".,!?;:\"'()[]")

    # Best-effort timestamp alignment:
    # - treat `word_spans` as ordered tokens
    # - for each detected filled pause occurrence, match the next corresponding span(s)
    span_tokens: List[str] = []
    span_starts: List[Optional[float]] = []
    span_ends: List[Optional[float]] = []
    if isinstance(word_spans, list):
        for ws in word_spans:
            if not isinstance(ws, dict):
                continue
            span_tokens.append(_clean_token(ws.get("word", "")))
            span_starts.append(ws.get("start_sec"))
            span_ends.append(ws.get("end_sec"))
    span_cursor = 0

    pause_phrases = [p for p in pause_words if " " in p]
    pause_phrase_tokens = sorted(
        [(p, [t for t in p.split() if t]) for p in pause_phrases],
        key=lambda x: len(x[1]),
        reverse=True,
    )

    def _find_next_phrase(tokens: List[str]) -> Optional[tuple[float | None, float | None, int]]:
        nonlocal span_cursor
        if not tokens or not span_tokens:
            return None
        n = len(tokens)
        for j in range(span_cursor, len(span_tokens) - n + 1):
            if span_tokens[j : j + n] == tokens:
                span_cursor = j + n
                start = span_starts[j]
                end = span_ends[j + n - 1]
                return start, end, span_cursor
        return None

    def _find_next_token(token: str) -> Optional[tuple[float | None, float | None, int]]:
        nonlocal span_cursor
        if not token or not span_tokens:
            return None
        for j in range(span_cursor, len(span_tokens)):
            if span_tokens[j] == token:
                span_cursor = j + 1
                return span_starts[j], span_ends[j], span_cursor
        return None

    i = 0
    while i < len(words):
        raw = words[i]
        clean = _clean_token(raw)

        matched_phrase = None
        for phrase, tokens in pause_phrase_tokens:
            if i + len(tokens) <= len(words) and [_clean_token(w) for w in words[i : i + len(tokens)]] == tokens:
                matched_phrase = (phrase, tokens)
                break

        if matched_phrase is not None:
            phrase, tokens = matched_phrase
            start_sec: Optional[float] = None
            end_sec: Optional[float] = None

            match = _find_next_phrase(tokens) if span_tokens else None
            if match is not None:
                start_sec, end_sec, _ = match

            severity = "warn" if style == "formal" else "info"
            found.append(
                {
                    "word": phrase,
                    "start_sec": round(start_sec, 3) if start_sec is not None else None,
                    "end_sec": round(end_sec, 3) if end_sec is not None else None,
                    "language": language,
                    "severity": severity,
                }
            )
            i += len(tokens)
            continue

        if clean in pause_words:
            start_sec = None
            end_sec = None
            match = _find_next_token(clean) if span_tokens else None
            if match is not None:
                start_sec, end_sec, _ = match

            severity = "warn" if style == "formal" else "info"
            found.append(
                {
                    "word": clean,
                    "start_sec": round(start_sec, 3) if start_sec is not None else None,
                    "end_sec": round(end_sec, 3) if end_sec is not None else None,
                    "language": language,
                    "severity": severity,
                }
            )

        i += 1

    return found


@tool("detect_pauses")
def detect_pauses(
    audio_path: str,
    min_pause_sec: float = 0.5,
    word_spans: List[Dict[str, Any]] | None = None,
    phrase_spans: List[Dict[str, Any]] | None = None,
    transcript: str | None = None,
    language: str = "en",
    filled_pause_style: str = "formal",
    mid_phrase_threshold_sec: float = 0.5,
    trailing_threshold_sec: float = 1.5,
) -> dict:
    """
    Detect unnatural silence gaps in an audio file.
    Flags any pause longer than min_pause_sec (default 0.5 seconds).

    Optionally uses phrase span context to classify pauses as natural/unnatural/trailing.
    Also detects filled pauses from transcript if provided.

    Args:
        audio_path:    Path to the audio file.
        min_pause_sec: Minimum duration in seconds to flag as a pause.
        word_spans:    Optional word-level timestamps for phrase-aware classification.
        phrase_spans:   Optional phrase spans for pause classification.
        transcript:  Optional transcript for filled pause detection.
        language:    Language code for filled pause detection (en/es).
        filled_pause_style: "formal" (warn) or "conversational" (info).
        mid_phrase_threshold_sec: Threshold for unnatural mid-phrase pause.
        trailing_threshold_sec: Threshold for trailing silence warning.

    Returns:
        A dict with pause events, total pause time, audio duration, and flagged_regions.
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
            "pauses": [],
            "pause_count": 0,
            "total_pause_time_sec": 0.0,
            "longest_pause_sec": 0.0,
            "audio_duration_sec": round(audio_duration, 3),
            "filled_pauses": [],
            "flagged_regions": [],
        }

    # Compute RMS energy per frame without librosa.
    frame_starts = np.arange(0, len(y) - frame_length + 1, hop_length, dtype=int)
    frames = np.stack([y[s : s + frame_length] for s in frame_starts], axis=0)
    rms = np.sqrt(np.mean(frames * frames, axis=1))

    silence_threshold = 10 ** (-40 / 20.0)
    times = frame_starts.astype(np.float64) / float(sr)

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
                pauses.append(
                    {
                        "start_sec": round(pause_start, 3),
                        "end_sec": round(float(times[i]), 3),
                        "duration_sec": round(duration, 3),
                    }
                )

    if in_pause:
        duration = float(audio_duration) - pause_start
        if duration >= min_pause_sec:
            pauses.append(
                {
                    "start_sec": round(pause_start, 3),
                    "end_sec": round(float(audio_duration), 3),
                    "duration_sec": round(duration, 3),
                }
            )

    # Classify pauses using phrase spans if available.
    flagged_regions: List[Dict[str, Any]] = []
    use_phrase_aware = bool(phrase_spans) and isinstance(phrase_spans, list)

    for p in pauses:
        if use_phrase_aware:
            classification = _classify_pause_by_phrase(
                p["start_sec"],
                p["end_sec"],
                phrase_spans,
                mid_phrase_threshold_sec,
            )
            p["type"] = classification["type"]
            p["context"] = classification["context"]
            p["phrase_id"] = classification["phrase_id"]
            p["severity"] = classification["severity"]
        else:
            p["type"] = "unknown"
            p["context"] = "energy_only"
            p["phrase_id"] = None
            duration = p.get("duration_sec", 0)
            p["severity"] = "warn" if duration > trailing_threshold_sec else "ok"

        if p.get("severity") != "ok":
            label = f"{p.get('type', 'pause').title()} pause ({p['duration_sec']}s)"
            flagged_regions.append(
                {
                    "check": "pause_detection",
                    "label": label,
                    "severity": p["severity"],
                    "start_sec": p["start_sec"],
                    "end_sec": p["end_sec"],
                }
            )

    # Detect filled pauses if transcript provided.
    filled_pauses: List[Dict[str, Any]] = []
    if transcript and isinstance(transcript, str):
        filled_pauses = detect_filled_pauses(
            transcript,
            word_spans,
            language,
            filled_pause_style,
        )
        for fp in filled_pauses:
            if fp.get("severity") != "info":
                label = f"Filled pause ({fp.get('word')})"
                flagged_regions.append(
                    {
                        "check": "filled_pause",
                        "label": label,
                        "severity": fp["severity"],
                        "start_sec": fp.get("start_sec"),
                        "end_sec": fp.get("end_sec"),
                    }
                )

    return {
        "pauses": pauses,
        "pause_count": len(pauses),
        "total_pause_time_sec": round(sum(p["duration_sec"] for p in pauses), 3),
        "longest_pause_sec": round(
            max((p["duration_sec"] for p in pauses), default=0.0), 3
        ),
        "audio_duration_sec": round(audio_duration, 3),
        "filled_pauses": filled_pauses,
        "flagged_regions": flagged_regions,
    }
