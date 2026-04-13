"""
Name / proper-noun fidelity checker.

Goal: catch high-impact errors (people/org/product/place names) without a heavy NLP stack.
We extract likely name spans from the expected script and look for them in the transcript
using exact and fuzzy matching.

This is deliberately conservative: false positives are worse than a missed name.
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, List, Tuple

from langchain_core.tools import tool


_TITLE_WORDS = {
    "dr",
    "doctor",
    "mr",
    "mrs",
    "ms",
    "prof",
    "professor",
    "nurse",
}

_STOPWORDS = {
    # Common sentence starters / function words that are capitalized by position.
    "i",
    "we",
    "you",
    "your",
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "if",
    "then",
    "this",
    "that",
    "these",
    "those",
    "hello",
    "hi",
    "thanks",
    "thank",
    "please",
    "call",
    "today",
    "tomorrow",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
}


def _normalize_text(text: str) -> str:
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokenize(text: str) -> List[str]:
    norm = _normalize_text(text)
    if not norm:
        return []
    return norm.split()


def _is_likely_name_token(token: str) -> bool:
    # Token from original casing.
    if not token:
        return False
    if token.isupper() and len(token) <= 3:
        # Likely acronym/abbrev, skip (handled elsewhere).
        return False
    if token[0].isupper() and token[1:].islower():
        return True
    return False


def _strip_title_prefix(tokens: List[str]) -> List[str]:
    if not tokens:
        return tokens
    t0 = re.sub(r"[^\w]", "", tokens[0]).lower()
    if t0 in _TITLE_WORDS and len(tokens) > 1:
        return tokens[1:]
    return tokens


def _extract_candidate_spans(expected: str) -> List[str]:
    """
    Extract spans that look like proper nouns from expected text.
    Returns unique spans as they appear (case-preserving).
    """
    if not expected:
        return []

    # 1-4 TitleCase words in a row, allowing hyphens/apostrophes inside words.
    pattern = re.compile(
        r"\b(?:[A-Z][a-z]+(?:[-'][A-Za-z]+)?)"
        r"(?:\s+(?:[A-Z][a-z]+(?:[-'][A-Za-z]+)?)){0,3}\b"
    )

    spans = pattern.findall(expected)
    cleaned: List[str] = []
    for span in spans:
        words = span.split()
        words = _strip_title_prefix(words)
        if not words:
            continue
        # Filter out spans that are just stopwords (common at sentence start).
        if all(w.lower() in _STOPWORDS for w in words):
            continue
        # Avoid single very-short tokens that are likely not names.
        if len(words) == 1 and len(words[0]) < 3:
            continue
        cleaned.append(" ".join(words))

    # Deduplicate while preserving order
    seen = set()
    uniq: List[str] = []
    for s in cleaned:
        key = _normalize_text(s)
        if not key or key in seen:
            continue
        seen.add(key)
        uniq.append(s)
    return uniq


@dataclass(frozen=True)
class _BestMatch:
    phrase: str
    score: float


def _best_fuzzy_match(
    expected_phrase: str,
    transcript_tokens: List[str],
) -> _BestMatch | None:
    exp_tokens = _tokenize(expected_phrase)
    if not exp_tokens or not transcript_tokens:
        return None

    n = len(exp_tokens)
    if n == 0:
        return None

    best: _BestMatch | None = None
    # Sliding n-gram window of same length
    for i in range(0, max(1, len(transcript_tokens) - n + 1)):
        window = transcript_tokens[i : i + n]
        window_phrase = " ".join(window)
        score = SequenceMatcher(None, " ".join(exp_tokens), window_phrase).ratio()
        if best is None or score > best.score:
            best = _BestMatch(phrase=window_phrase, score=score)
    return best


@tool("check_name_fidelity")
def check_name_fidelity(
    expected: str,
    transcript: str,
    expected_names: List[str] | None = None,
    ignore_names: List[str] | None = None,
    min_fuzzy_ratio: float = 0.88,
) -> dict:
    """
    Check that likely proper nouns/names from the expected script appear in the transcript.

    Args:
        expected: Expected script text.
        transcript: ASR transcript text.
        expected_names: Optional explicit list of names/proper nouns to check (overrides extraction).
        ignore_names: Optional list of names to ignore.
        min_fuzzy_ratio: Minimum SequenceMatcher ratio for a fuzzy match (0-1).

    Returns:
        Dict with mismatches list, matched list, and name_fidelity_score (0-100).
    """
    ignore = {_normalize_text(n) for n in (ignore_names or []) if n}

    candidates = expected_names if (expected_names and len(expected_names) > 0) else _extract_candidate_spans(expected)
    candidates = [c for c in candidates if _normalize_text(c) not in ignore]

    transcript_norm = _normalize_text(transcript)
    transcript_tokens = _tokenize(transcript)

    matched = []
    mismatches = []

    for phrase in candidates:
        phrase_norm = _normalize_text(phrase)
        if not phrase_norm:
            continue

        if phrase_norm in transcript_norm:
            matched.append({"value": phrase, "match": phrase, "match_type": "exact", "ratio": 1.0})
            continue

        best = _best_fuzzy_match(phrase, transcript_tokens)
        if best and best.score >= float(min_fuzzy_ratio):
            matched.append(
                {"value": phrase, "match": best.phrase, "match_type": "fuzzy", "ratio": round(float(best.score), 3)}
            )
        else:
            mismatches.append(
                {
                    "value": phrase,
                    "note": "Proper noun/name not found in transcript",
                    "best_match": best.phrase if best else None,
                    "best_ratio": round(float(best.score), 3) if best else None,
                }
            )

    total = len(matched) + len(mismatches)
    name_fidelity_score = round((len(matched) / total) * 100, 1) if total > 0 else 100.0

    return {
        "candidates": candidates,
        "matched": matched,
        "mismatches": mismatches,
        "candidate_count": total,
        "mismatch_count": len(mismatches),
        "name_fidelity_score": name_fidelity_score,
    }

