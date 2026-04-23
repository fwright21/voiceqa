from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain_core.tools import tool


@tool("check_pause_naturalness")
def check_pause_naturalness(
    alignment: Dict[str, Any],
    pauses: Dict[str, Any] | None = None,
    within_phrase_warn_sec: float = 0.9,
    within_phrase_fail_sec: float = 1.6,
    between_phrase_warn_sec: float = 2.2,
) -> dict:
    """
    Score pause naturalness using energy-derived pauses (and phrase spans).

    Motivation: energy-based pause detection is useful, but for scripted evaluation we want
    to identify *where* a pause happened (within-phrase vs between-phrases) and provide
    stable jump targets for UI review.

    Primary signal:
    - use `pauses.pauses` from `detect_pauses` (energy/VAD-like) for real silences
    - classify each pause as within-phrase vs between-phrase using `alignment.phrase_spans`

    Secondary signal (best-effort):
    - if word spans expose real gaps, we can also compute timing gaps, but many timestamp backends
      produce contiguous word boundaries and do not reflect silence as gaps.
    """
    if not isinstance(alignment, dict):
        return {"skipped": True, "error": "alignment must be a dict"}

    words = alignment.get("word_spans")
    phrases = alignment.get("phrase_spans")
    phrase_gap_sec = None
    if isinstance(alignment.get("notes"), dict):
        phrase_gap_sec = alignment["notes"].get("phrase_gap_sec")

    if not isinstance(words, list) or len(words) < 2:
        return {
            "skipped": True,
            "error": "alignment.word_spans missing (word-level timestamps unavailable)",
            "gaps": [],
            "flags": [],
        }

    # Build a quick lookup to label which phrase a word index belongs to.
    phrase_by_word_idx: Dict[int, Optional[int]] = {}
    if isinstance(phrases, list):
        for p in phrases:
            if not isinstance(p, dict):
                continue
            pid = p.get("phrase_id")
            ws = p.get("word_start")
            we = p.get("word_end")
            if isinstance(pid, int) and isinstance(ws, int) and isinstance(we, int):
                for idx in range(ws, we + 1):
                    phrase_by_word_idx[idx] = pid

    def _w(idx: int) -> dict:
        w = words[idx]
        return w if isinstance(w, dict) else {}

    gaps: List[dict] = []
    flags: List[dict] = []
    max_within = 0.0
    max_between = 0.0

    # Classify energy-derived pauses against phrase spans.
    pause_events = []
    if isinstance(pauses, dict) and isinstance(pauses.get("pauses"), list):
        pause_events = pauses.get("pauses") or []

    # If phrase spans are unavailable, treat everything as "unknown phrase".
    phrase_spans = phrases if isinstance(phrases, list) else []
    phrase_bounds = []
    for p in phrase_spans:
        if not isinstance(p, dict):
            continue
        try:
            phrase_bounds.append((float(p.get("start_sec")), float(p.get("end_sec"))))
        except Exception:
            continue
    phrase_bounds.sort(key=lambda x: x[0])
    first_phrase_start = phrase_bounds[0][0] if phrase_bounds else None
    last_phrase_end = phrase_bounds[-1][1] if phrase_bounds else None

    def _phrase_for_time(t: float) -> Optional[int]:
        for p in phrase_spans:
            if not isinstance(p, dict):
                continue
            try:
                ps = float(p.get("start_sec"))
                pe = float(p.get("end_sec"))
            except Exception:
                continue
            if ps <= t <= pe:
                pid = p.get("phrase_id")
                return int(pid) if isinstance(pid, int) else None
        return None

    def _is_between_phrases(pause_start: float, pause_end: float) -> bool:
        # Between phrases if the pause sits in the gap between two adjacent phrase spans.
        spans = []
        for p in phrase_spans:
            if not isinstance(p, dict):
                continue
            try:
                spans.append((float(p.get("start_sec")), float(p.get("end_sec")), p.get("phrase_id")))
            except Exception:
                continue
        spans.sort(key=lambda x: x[0])
        for i in range(1, len(spans)):
            prev_end = spans[i - 1][1]
            cur_start = spans[i][0]
            if pause_start >= prev_end and pause_end <= cur_start:
                return True
        return False

    for p in pause_events:
        if not isinstance(p, dict):
            continue
        try:
            start = float(p.get("start_sec"))
            end = float(p.get("end_sec"))
            dur = float(p.get("duration_sec"))
        except Exception:
            continue
        if dur <= 0:
            continue

        between = _is_between_phrases(start, end) if phrase_spans else False
        phrase_id = _phrase_for_time((start + end) / 2.0) if phrase_spans else None
        within = (not between) and (phrase_id is not None)
        outside_phrases = (not between) and (phrase_id is None)

        # Best-effort labeling for pauses outside all phrase spans (e.g. leading/trailing silence).
        context = None
        if outside_phrases and first_phrase_start is not None and last_phrase_end is not None:
            if end <= first_phrase_start:
                context = "leading_silence"
            elif start >= last_phrase_end:
                context = "trailing_silence"
            else:
                context = "outside_phrases"

        ev = {
            "start_sec": round(start, 3),
            "end_sec": round(end, 3),
            "duration_sec": round(dur, 3),
            "within_phrase": bool(within),
            "between_phrases": bool(between),
            "phrase_id": phrase_id,
        }
        if outside_phrases:
            ev["outside_phrases"] = True
            if context:
                ev["context"] = context
        gaps.append(ev)

        if within:
            max_within = max(max_within, dur)
            if dur >= within_phrase_fail_sec:
                flags.append({"level": "fail", "type": "within_phrase_pause", **ev})
            elif dur >= within_phrase_warn_sec:
                flags.append({"level": "warn", "type": "within_phrase_pause", **ev})
        elif between:
            max_between = max(max_between, dur)
            if dur >= between_phrase_warn_sec:
                flags.append({"level": "warn", "type": "between_phrase_pause", **ev})

    # Secondary: word gap detection (only if there are real positive gaps).
    # Kept for future backends that produce non-contiguous word boundaries.
    for i in range(1, len(words)):
        prev = _w(i - 1)
        cur = _w(i)
        try:
            gap = float(cur.get("start_sec")) - float(prev.get("end_sec"))
        except Exception:
            continue
        if gap <= 0:
            continue
        prev_phrase = phrase_by_word_idx.get(i - 1)
        cur_phrase = phrase_by_word_idx.get(i)
        within_phrase = (prev_phrase is not None) and (prev_phrase == cur_phrase)
        if within_phrase and gap >= within_phrase_warn_sec:
            flags.append(
                {
                    "level": "warn",
                    "type": "within_phrase_gap",
                    "gap_sec": round(gap, 3),
                    "start_sec": round(float(prev.get("end_sec")), 3) if prev.get("end_sec") is not None else None,
                    "end_sec": round(float(cur.get("start_sec")), 3) if cur.get("start_sec") is not None else None,
                    "phrase_id": prev_phrase,
                    "within_phrase": True,
                    "between_phrases": False,
                }
            )

    # Speaking rate (words per second) using aligned span, excluding leading/trailing silence.
    try:
        start = float(_w(0).get("start_sec"))
        end = float(_w(len(words) - 1).get("end_sec"))
        duration = max(0.001, end - start)
        speaking_rate_wps = round(len(words) / duration, 3)
    except Exception:
        speaking_rate_wps = None

    return {
        "skipped": False,
        "backend": alignment.get("backend"),
        "phrase_gap_sec": phrase_gap_sec,
        "within_phrase_warn_sec": within_phrase_warn_sec,
        "within_phrase_fail_sec": within_phrase_fail_sec,
        "between_phrase_warn_sec": between_phrase_warn_sec,
        "max_within_phrase_gap_sec": round(max_within, 3),
        "max_between_phrase_gap_sec": round(max_between, 3),
        "speaking_rate_wps": speaking_rate_wps,
        "gap_count": len(gaps),
        "gaps": gaps[:250],  # cap for payload sanity
        "flags": flags[:50],
    }
