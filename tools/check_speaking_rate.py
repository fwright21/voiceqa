from __future__ import annotations

from typing import Any, Dict, List, Optional
from langchain_core.tools import tool

WPM_RANGES = {
    "en": {
        "min_ok": 120,
        "max_ok": 220,
        "min_warn": 90,
        "max_warn": 260,
        "min_fail": 90,
        "max_fail": 260,
    },
    "es": {
        "min_ok": 4.5,
        "max_ok": 6.5,
        "min_warn": 3.5,
        "max_warn": 7.5,
        "min_fail": 3.5,
        "max_fail": 7.5,
    },
}

SPS_MULTIPLIER = 2.5

DEFAULT_CONFIG = {
    "enabled": True,
    "critical_tags": ["red_flag", "meds"],
    "warn_above": 220,
    "fail_above": 260,
    "warn_below": 120,
    "fail_below": 90,
}

DEFAULT_EN_CONFIG = {
    "enabled": True,
    "critical_tags": ["red_flag", "meds"],
    "warn_above": 220,
    "fail_above": 260,
    "warn_below": 120,
    "fail_below": 90,
}

DEFAULT_ES_CONFIG = {
    "enabled": True,
    "critical_tags": ["red_flag", "meds"],
    "warn_above": 7.5,
    "fail_above": 7.5,
    "warn_below": 3.5,
    "fail_below": 3.5,
}


def _compute_wpm(word_count: int, duration_sec: float) -> Optional[float]:
    if duration_sec <= 0 or word_count <= 0:
        return None
    return round((word_count / duration_sec) * 60, 1)


def _compute_sps(word_count: int, duration_sec: float) -> Optional[float]:
    if duration_sec <= 0 or word_count <= 0:
        return None
    syllables = word_count * SPS_MULTIPLIER
    return round(syllables / duration_sec, 1)


def _severity_from_rate(
    rate: float,
    language: str,
    is_critical: bool = False,
    config: Dict[str, Any] | None = None,
) -> str:
    cfg = config or DEFAULT_CONFIG

    def _thresholds() -> tuple[float, float, float, float]:
        if language == "en":
            warn_above = float(int(cfg.get("warn_above", 220)))
            fail_above = float(int(cfg.get("fail_above", 260)))
            warn_below = float(int(cfg.get("warn_below", 120)))
            fail_below = float(int(cfg.get("fail_below", 90)))
            if is_critical:
                warn_above = min(warn_above, 200.0)
            return warn_above, fail_above, warn_below, fail_below

        warn_above = float(cfg.get("warn_above", 7.5))
        fail_above = float(cfg.get("fail_above", 7.5))
        warn_below = float(cfg.get("warn_below", 3.5))
        fail_below = float(cfg.get("fail_below", 3.5))
        if is_critical:
            warn_above = min(warn_above, 6.0)
            fail_above = min(fail_above, 6.5)
        return warn_above, fail_above, warn_below, fail_below

    if language == "en":
        warn_above, fail_above, warn_below, fail_below = _thresholds()
        if rate >= fail_above or rate <= fail_below:
            return "fail"
        elif rate >= warn_above or rate <= warn_below:
            return "warn"
    else:
        warn_above, fail_above, warn_below, fail_below = _thresholds()
        if rate >= fail_above or rate <= fail_below:
            return "fail"
        elif rate >= warn_above or rate <= warn_below:
            return "warn"

    return "ok"


def _text_for_span(span: Dict[str, Any], max_len: int = 80) -> str:
    text = span.get("word") or span.get("text") or ""
    if isinstance(text, list):
        text = " ".join(str(t) for t in text[:10])
    else:
        text = str(text)[:max_len]
    return text


@tool("check_speaking_rate")
def check_speaking_rate(
    phrase_spans: List[Dict[str, Any]],
    language: str = "en",
    config: Dict[str, Any] | None = None,
) -> dict:
    """
    Compute speaking rate per phrase span.

    Args:
        phrase_spans: List of phrase spans from alignment (must have word_count/duration or words).
        language: Language code (en = WPM, es = SPS). Default "en".
        config: Optional config with critical_tags, threshold overrides.

    Returns:
        Dict with segments (per-phrase rates), overall_rate, flagged_regions.
    """
    if not phrase_spans or not isinstance(phrase_spans, list):
        return {
            "segments": [],
            "overall_rate": None,
            "rate_unit": "wpm" if language == "en" else "sps",
            "skipped": True,
            "error": "no phrase_spans provided",
            "flagged_regions": [],
        }

    cfg = config or (DEFAULT_ES_CONFIG if language == "es" else DEFAULT_EN_CONFIG)
    critical_tags = cfg.get("critical_tags", []) if isinstance(cfg, dict) else []

    rate_unit = "wpm" if language == "en" else "sps"
    segments: List[Dict[str, Any]] = []
    flagged_regions: List[Dict[str, Any]] = []
    total_words = 0
    total_duration = 0.0

    for span in phrase_spans:
        if not isinstance(span, dict):
            continue

        word_count = span.get("word_count")
        duration_sec = span.get("duration_sec")

        if not word_count or not duration_sec:
            words = span.get("words") or span.get("word_spans")
            if isinstance(words, list):
                word_count = len(words)
                try:
                    start = float(
                        min(w.get("start_sec", 0) for w in words if isinstance(w, dict))
                    )
                    end = float(
                        max(w.get("end_sec", 0) for w in words if isinstance(w, dict))
                    )
                    duration_sec = max(0.001, end - start)
                except (ValueError, TypeError):
                    continue
            else:
                continue

        if not word_count or not duration_sec or duration_sec <= 0:
            continue

        total_words += word_count
        total_duration += duration_sec

        if rate_unit == "wpm":
            rate = _compute_wpm(word_count, duration_sec)
            rate_value = rate
        else:
            rate = _compute_sps(word_count, duration_sec)
            rate_value = rate

        tags = span.get("tags", []) or []
        is_critical = any(t in critical_tags for t in tags) if tags else False

        severity = (
            _severity_from_rate(rate_value, language, is_critical, cfg)
            if rate_value
            else "ok"
        )

        phrase_id = span.get("phrase_id")
        start_sec = span.get("start_sec", 0)
        end_sec = span.get("end_sec", 0)

        segment = {
            "phrase_id": phrase_id,
            "start_sec": round(start_sec, 3) if start_sec is not None else None,
            "end_sec": round(end_sec, 3) if end_sec is not None else None,
            "word_count": word_count,
            "wpm": rate if language == "en" else None,
            "sps": rate if language == "es" else None,
            "rate_unit": rate_unit,
            "rate_value": rate_value,
            "severity": severity,
            "text": _text_for_span(span),
        }
        segments.append(segment)

        if severity != "ok":
            # Label slow vs fast so the jump target makes sense to reviewers.
            if language == "en":
                warn_above = float(int(cfg.get("warn_above", 220)))
                fail_above = float(int(cfg.get("fail_above", 260)))
                warn_below = float(int(cfg.get("warn_below", 120)))
                fail_below = float(int(cfg.get("fail_below", 90)))
                if is_critical:
                    warn_above = min(warn_above, 200.0)
            else:
                warn_above = float(cfg.get("warn_above", 7.5))
                fail_above = float(cfg.get("fail_above", 7.5))
                warn_below = float(cfg.get("warn_below", 3.5))
                fail_below = float(cfg.get("fail_below", 3.5))
                if is_critical:
                    warn_above = min(warn_above, 6.0)
                    fail_above = min(fail_above, 6.5)

            if severity == "fail":
                if rate_value >= fail_above:
                    desc = "Extreme fast speech"
                elif rate_value <= fail_below:
                    desc = "Extreme slow speech"
                else:
                    desc = "Extreme speech rate"
            else:
                if rate_value >= warn_above:
                    desc = "Fast speech"
                elif rate_value <= warn_below:
                    desc = "Slow speech"
                else:
                    desc = "Speech rate out of range"

            label = f"{desc} ({rate_value} {rate_unit})"
            flagged_regions.append(
                {
                    "check": "speaking_rate",
                    "label": label,
                    "severity": severity,
                    "start_sec": segment.get("start_sec"),
                    "end_sec": segment.get("end_sec"),
                }
            )

    overall_rate: Optional[float] = None
    if total_duration > 0 and total_words > 0:
        if rate_unit == "wpm":
            overall_rate = _compute_wpm(total_words, total_duration)
        else:
            overall_rate = _compute_sps(total_words, total_duration)

    return {
        "segments": segments,
        "overall_rate": overall_rate,
        "rate_unit": rate_unit,
        "baseline_rate": None,
        "flagged_regions": flagged_regions,
    }
