"""
Term fidelity checker (symptoms, medications, clinical terms).

Unlike name fidelity, this is NOT based on capitalization heuristics.
You provide an explicit list of terms to check (e.g., uncommon symptoms or drug names)
and we verify they appear in the transcript using exact and fuzzy matching.
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, List, Tuple

from langchain_core.tools import tool


def _normalize_text(text: str) -> str:
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokenize(text: str) -> List[str]:
    norm = _normalize_text(text)
    return norm.split() if norm else []


@dataclass(frozen=True)
class _BestMatch:
    phrase: str
    score: float


def _best_fuzzy_ngram(term: str, transcript_tokens: List[str]) -> _BestMatch | None:
    term_tokens = _tokenize(term)
    if not term_tokens or not transcript_tokens:
        return None

    n = len(term_tokens)
    best: _BestMatch | None = None
    target = " ".join(term_tokens)

    for i in range(0, max(1, len(transcript_tokens) - n + 1)):
        window = transcript_tokens[i : i + n]
        candidate = " ".join(window)
        score = SequenceMatcher(None, target, candidate).ratio()
        if best is None or score > best.score:
            best = _BestMatch(phrase=candidate, score=score)
    return best


@tool("check_term_fidelity")
def check_term_fidelity(
    transcript: str,
    expected_terms: List[Any],
    ignore_terms: List[str] | None = None,
    min_fuzzy_ratio: float = 0.9,
) -> dict:
    """
    Check that each expected term appears in the transcript.

    Args:
        transcript: ASR transcript text.
        expected_terms: Explicit list of terms to check (symptoms, meds, etc).
        ignore_terms: Optional list of terms to ignore.
        min_fuzzy_ratio: Minimum SequenceMatcher ratio for fuzzy matching.

    Returns:
        Dict with matched/mismatches, and term_fidelity_score (0-100).
    """
    ignore = {_normalize_text(t) for t in (ignore_terms or []) if t}

    def _coerce_term(item: Any) -> Tuple[str, str]:
        # Supports either "term" or {"term": "...", "criticality": "high|medium|low"}.
        if isinstance(item, str):
            return item, "medium"
        if isinstance(item, dict):
            term = item.get("term") or item.get("value") or ""
            crit = (item.get("criticality") or item.get("crit") or "medium").lower()
            if crit not in {"high", "medium", "low"}:
                crit = "medium"
            return str(term), crit
        return str(item), "medium"

    terms: List[dict] = []
    for raw in (expected_terms or []):
        term, crit = _coerce_term(raw)
        norm = _normalize_text(term)
        if not term or not norm or norm in ignore:
            continue
        terms.append({"term": term, "criticality": crit})

    transcript_norm = _normalize_text(transcript or "")
    transcript_tokens = _tokenize(transcript or "")

    matched = []
    mismatches = []
    critical_mismatches = {"high": 0, "medium": 0, "low": 0}

    for entry in terms:
        term = entry["term"]
        crit = entry["criticality"]
        term_norm = _normalize_text(term)
        if not term_norm:
            continue

        if term_norm in transcript_norm:
            matched.append({"value": term, "criticality": crit, "match": term, "match_type": "exact", "ratio": 1.0})
            continue

        best = _best_fuzzy_ngram(term, transcript_tokens)
        if best and best.score >= float(min_fuzzy_ratio):
            matched.append(
                {
                    "value": term,
                    "criticality": crit,
                    "match": best.phrase,
                    "match_type": "fuzzy",
                    "ratio": round(float(best.score), 3),
                }
            )
        else:
            critical_mismatches[crit] = critical_mismatches.get(crit, 0) + 1
            mismatches.append(
                {
                    "value": term,
                    "criticality": crit,
                    "note": "Term not found in transcript",
                    "best_match": best.phrase if best else None,
                    "best_ratio": round(float(best.score), 3) if best else None,
                }
            )

    total = len(matched) + len(mismatches)

    # Weighted score: high mismatches penalize more.
    weights = {"high": 3.0, "medium": 1.5, "low": 1.0}
    max_penalty = 0.0
    penalty = 0.0
    for entry in terms:
        max_penalty += weights.get(entry["criticality"], 1.5)
    for m in mismatches:
        penalty += weights.get(m.get("criticality", "medium"), 1.5)

    term_fidelity_score = round(max(0.0, (1.0 - (penalty / max_penalty)) * 100.0), 1) if max_penalty > 0 else 100.0

    return {
        "expected_terms": terms,
        "matched": matched,
        "mismatches": mismatches,
        "term_count": total,
        "mismatch_count": len(mismatches),
        "term_fidelity_score": term_fidelity_score,
        "critical_mismatch_count": critical_mismatches,
    }
