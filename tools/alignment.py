from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def build_alignment(
    transcription: Dict[str, Any],
    expected_script: str | None = None,
    phrase_gap_sec: float = 0.45,
) -> Dict[str, Any]:
    """
    Build a normalized alignment payload from an upstream transcriber output.

    This is intentionally backend-agnostic: the rest of the pipeline should depend on
    standardized "word_spans"/"phrase_spans" rather than Whisper-specific segment shapes.

    Expected output shape:
      {
        "backend": "whisper_word_timestamps" | "segments_only" | "none",
        "word_spans": [{ "word", "start_sec", "end_sec", "probability" }]|None,
        "phrase_spans": [{ "phrase_id", "start_sec", "end_sec", "text", "word_start", "word_end" }]|None,
        "skipped": bool,
        "error": str|None,
        "notes": { ... }
      }

    `phrase_spans` are derived heuristically from word timing gaps so we can:
    - distinguish within-phrase vs between-phrase pauses
    - provide UI jump targets even before adding an MFA backend
    """
    try:
        if not isinstance(transcription, dict):
            return {
                "backend": "none",
                "word_spans": None,
                "phrase_spans": None,
                "skipped": True,
                "error": "transcription must be a dict",
                "notes": {},
            }

        raw_words = transcription.get("word_spans")
        word_spans: Optional[List[Dict[str, Any]]] = None

        if isinstance(raw_words, list) and raw_words:
            normalized = []
            for w in raw_words:
                if not isinstance(w, dict):
                    continue
                word = (w.get("word") or "").strip()
                start = w.get("start")
                end = w.get("end")
                prob = w.get("probability")
                if not word:
                    continue
                if start is None or end is None:
                    continue
                normalized.append(
                    {
                        "word": word,
                        "start_sec": float(start),
                        "end_sec": float(end),
                        "probability": float(prob) if isinstance(prob, (int, float)) else None,
                    }
                )
            word_spans = normalized or None

        backend = "whisper_word_timestamps" if word_spans else "segments_only"

        def _expected_phrase_token_counts(text: str) -> List[int]:
            # Split into phrases on punctuation boundaries; keep it simple and deterministic.
            # We only need approximate phrase segmentation for within-phrase pause scoring.
            raw = (text or "").strip()
            if not raw:
                return []
            parts = [p.strip() for p in re.split(r"[.!?;:]+", raw) if p.strip()]
            if not parts:
                parts = [raw]
            counts = []
            for p in parts:
                tokens = re.findall(r"[A-Za-z0-9']+", p)
                if tokens:
                    counts.append(len(tokens))
            return counts

        def _build_phrase_spans_from_expected(word_spans: List[Dict[str, Any]], expected_script: str) -> Optional[List[Dict[str, Any]]]:
            counts = _expected_phrase_token_counts(expected_script)
            if not counts:
                return None
            total_expected = sum(counts)
            if total_expected <= 0:
                return None
            total_words = len(word_spans)
            if total_words <= 0:
                return None

            ratio = total_words / float(total_expected)
            # If ASR word count is wildly off, expected segmentation will be nonsense.
            if ratio < 0.55 or ratio > 1.75:
                return None

            remaining_words = total_words
            remaining_expected = total_expected
            spans = []
            idx = 0
            for phrase_i, expected_n in enumerate(counts):
                phrases_left = len(counts) - phrase_i
                # Proportional allocation; ensure at least 1 word per phrase and leave enough for remaining phrases.
                want = int(round(expected_n * ratio))
                want = max(1, want)
                max_allowed = remaining_words - (phrases_left - 1)
                want = min(max_allowed, want)
                if want <= 0:
                    break

                start_idx = idx
                end_idx = idx + want - 1
                start_sec = float(word_spans[start_idx]["start_sec"])
                end_sec = float(word_spans[end_idx]["end_sec"])
                text = " ".join(w["word"] for w in word_spans[start_idx : end_idx + 1]).strip()
                spans.append(
                    {
                        "phrase_id": len(spans) + 1,
                        "start_sec": start_sec,
                        "end_sec": end_sec,
                        "text": text,
                        "word_start": start_idx,
                        "word_end": end_idx,
                    }
                )
                idx = end_idx + 1
                remaining_words -= want
                remaining_expected -= expected_n

            # If we didn't consume all words, attach the remainder to the last phrase.
            if spans and idx < total_words:
                spans[-1]["word_end"] = total_words - 1
                spans[-1]["end_sec"] = float(word_spans[total_words - 1]["end_sec"])
                spans[-1]["text"] = " ".join(w["word"] for w in word_spans[spans[-1]["word_start"] : total_words]).strip()

            return spans or None

        def _build_phrase_spans_from_gaps(word_spans: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
            spans = []
            start_idx = 0
            phrase_start = word_spans[0]["start_sec"]
            for i in range(1, len(word_spans)):
                prev = word_spans[i - 1]
                cur = word_spans[i]
                gap = float(cur["start_sec"]) - float(prev["end_sec"])
                if gap >= float(phrase_gap_sec):
                    end_idx = i - 1
                    phrase_end = word_spans[end_idx]["end_sec"]
                    text = " ".join(w["word"] for w in word_spans[start_idx : end_idx + 1]).strip()
                    spans.append(
                        {
                            "phrase_id": len(spans) + 1,
                            "start_sec": float(phrase_start),
                            "end_sec": float(phrase_end),
                            "text": text,
                            "word_start": start_idx,
                            "word_end": end_idx,
                        }
                    )
                    start_idx = i
                    phrase_start = cur["start_sec"]

            end_idx = len(word_spans) - 1
            phrase_end = word_spans[end_idx]["end_sec"]
            text = " ".join(w["word"] for w in word_spans[start_idx : end_idx + 1]).strip()
            spans.append(
                {
                    "phrase_id": len(spans) + 1,
                    "start_sec": float(phrase_start),
                    "end_sec": float(phrase_end),
                    "text": text,
                    "word_start": start_idx,
                    "word_end": end_idx,
                }
            )
            return spans or None

        phrase_spans = None
        phrase_method = None
        if word_spans:
            if expected_script:
                phrase_spans = _build_phrase_spans_from_expected(word_spans, expected_script)
                if phrase_spans:
                    phrase_method = "expected_proportional"
            if not phrase_spans:
                phrase_spans = _build_phrase_spans_from_gaps(word_spans)
                phrase_method = "gap"

        # Enrich phrase spans with derived fields used downstream (e.g. speaking rate).
        if phrase_spans and word_spans:
            for p in phrase_spans:
                if not isinstance(p, dict):
                    continue
                ws = p.get("word_start")
                we = p.get("word_end")
                if isinstance(ws, int) and isinstance(we, int) and 0 <= ws <= we < len(word_spans):
                    p["word_count"] = int(we - ws + 1)
                    try:
                        p["duration_sec"] = round(float(p.get("end_sec")) - float(p.get("start_sec")), 3)
                    except Exception:
                        p["duration_sec"] = None
                else:
                    p["word_count"] = None
                    p["duration_sec"] = None

        return {
            "backend": backend,
            "word_spans": word_spans,
            "phrase_spans": phrase_spans,
            "skipped": False if backend != "none" else True,
            "error": None,
            "notes": {
                "phrase_gap_sec": phrase_gap_sec,
                "expected_script_len": len(expected_script or ""),
                "phrase_method": phrase_method,
            },
        }
    except Exception as exc:
        return {
            "backend": "none",
            "word_spans": None,
            "phrase_spans": None,
            "skipped": True,
            "error": str(exc),
            "notes": {},
        }
