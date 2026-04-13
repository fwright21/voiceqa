"""
Vitals fidelity checker (deterministic).

Goal: compare critical numeric vitals even when the transcript normalizes numbers into words.
This is designed for healthcare eval suites where mismatches should be high-signal.

We currently support:
- Temperature (e.g. 102.4 degrees)
- SpO2 / oxygen saturation (e.g. 92 percent)
- Blood pressure (e.g. 180 over 110)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from langchain_core.tools import tool


_NUM_WORDS_0_19 = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}

_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

_FILLERS = {"and", "a", "an", "the", "about", "around"}


def _tokenize(text: str) -> List[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\.\s/%-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    raw = text.split()
    cleaned: List[str] = []
    for tok in raw:
        # Preserve numeric decimals as-is (e.g. 102.4)
        if re.fullmatch(r"\d+(\.\d+)?", tok):
            cleaned.append(tok)
            continue
        cleaned.append(tok.strip(".").strip())
    return [t for t in cleaned if t]


def _parse_int_tokens(tokens: List[str], i: int) -> Tuple[Optional[int], int]:
    """
    Parse an integer from tokens starting at i.

    Supports:
    - "ninety two" => 92
    - "one hundred two" => 102
    - BP shorthand: "one eighty" => 180, "one ten" => 110
    """
    if i >= len(tokens):
        return None, i

    t = tokens[i]
    # Allow tokens like "92%" or "92%," after tokenization.
    if t.endswith("%") and t[:-1].isdigit():
        return int(t[:-1]), i + 1
    if t.isdigit():
        return int(t), i + 1

    if t in _NUM_WORDS_0_19:
        # BP shorthand: one + tens => 100 + tens
        if i + 1 < len(tokens) and tokens[i + 1] in _TENS:
            return 100 + _TENS[tokens[i + 1]], i + 2
        # one + ten/eleven/... => 100 + 10..19 (e.g. "one ten" => 110)
        if i + 1 < len(tokens) and tokens[i + 1] in _NUM_WORDS_0_19:
            n2 = _NUM_WORDS_0_19[tokens[i + 1]]
            if n2 >= 10:
                return 100 + n2, i + 2
        return _NUM_WORDS_0_19[t], i + 1

    if t in _TENS:
        val = _TENS[t]
        if i + 1 < len(tokens) and tokens[i + 1] in _NUM_WORDS_0_19:
            val += _NUM_WORDS_0_19[tokens[i + 1]]
            return val, i + 2
        return val, i + 1

    if t == "hundred" and i + 1 < len(tokens) and tokens[i + 1] in _NUM_WORDS_0_19:
        return 100 + _NUM_WORDS_0_19[tokens[i + 1]], i + 2

    return None, i


def _parse_decimal(tokens: List[str], i: int) -> Tuple[Optional[float], int]:
    """
    Parse a decimal like "one hundred two point four" => 102.4
    or "102.4" => 102.4.
    """
    if i >= len(tokens):
        return None, i

    t = tokens[i]
    # direct numeric
    if re.fullmatch(r"\d+(\.\d+)?", t):
        return float(t), i + 1

    # integer [point] digit(s)
    integer, j = _parse_int_tokens(tokens, i)
    if integer is None:
        return None, i

    if j < len(tokens) and tokens[j] in {"point", "dot"}:
        j += 1
        digits: List[str] = []
        while j < len(tokens):
            if tokens[j].isdigit():
                digits.append(tokens[j])
                j += 1
                continue
            if tokens[j] in _NUM_WORDS_0_19 and _NUM_WORDS_0_19[tokens[j]] < 10:
                digits.append(str(_NUM_WORDS_0_19[tokens[j]]))
                j += 1
                continue
            break
        if digits:
            return float(f"{integer}.{''.join(digits)}"), j
    return float(integer), j


def _extract_expected_vitals(expected: str) -> dict:
    """
    Extract vitals targets from the expected script.
    This is intentionally narrow to avoid false positives.
    """
    exp = expected.lower()
    vitals = {"temperature": None, "spo2": None, "bp": None}

    # temperature: number with optional decimal near "degree"
    m = re.search(r"(\d{2,3}(?:\.\d)?)\s*(?:degrees?|deg)\b", exp)
    if m:
        vitals["temperature"] = float(m.group(1))

    # SpO2: number near "percent" + oxygen saturation keywords
    m = re.search(r"(\d{2,3})\s*(?:percent|%)\b", exp)
    if m and ("oxygen" in exp or "saturation" in exp or "spo2" in exp):
        vitals["spo2"] = int(m.group(1))

    # BP: "X over Y"
    m = re.search(r"\b(\d{2,3})\s*(?:over|/)\s*(\d{2,3})\b", exp)
    if m and ("blood pressure" in exp or "pressure" in exp):
        vitals["bp"] = {"systolic": int(m.group(1)), "diastolic": int(m.group(2))}

    return vitals


def _extract_transcript_vitals(transcript: str) -> dict:
    tokens = [t for t in _tokenize(transcript) if t not in _FILLERS]
    text = " ".join(tokens)
    vitals = {"temperature": None, "spo2": None, "bp": None}

    # Temperature: look for "... point ..." near degrees, else numeric near degrees.
    # We'll scan for "degree(s)" and parse a number within a small window before it.
    for idx, tok in enumerate(tokens):
        if tok.startswith("degree"):
            start = max(0, idx - 6)
            # parse last decimal in window
            best = None
            j = start
            while j < idx:
                val, nxt = _parse_decimal(tokens, j)
                if val is not None:
                    best = val
                    j = nxt
                else:
                    j += 1
            if best is not None:
                vitals["temperature"] = float(best)
                break

    # SpO2: parse integer near "percent" plus oxygen keywords
    if ("percent" in tokens) or ("% " in text) or any("%" in t for t in tokens):
        if any(k in text for k in ["oxygen", "saturation", "spo2", "o2"]):
            for idx, tok in enumerate(tokens):
                if tok in {"percent", "%"} or tok.endswith("%"):
                    start = max(0, idx - 4)
                    best_int = None
                    j = start
                    while j < idx:
                        val, nxt = _parse_int_tokens(tokens, j)
                        if val is not None:
                            best_int = val
                            j = nxt
                        else:
                            j += 1
                    # If the percent token itself carries digits (e.g. 92%), parse it.
                    if best_int is None and tok.endswith("%") and tok[:-1].isdigit():
                        best_int = int(tok[:-1])
                    if best_int is not None:
                        vitals["spo2"] = int(best_int)
                        break

    # BP: look for "over" and parse systolic/diastolic around it
    for idx, tok in enumerate(tokens):
        if tok in {"over", "/"}:
            # parse left number
            left = None
            j = max(0, idx - 4)
            while j < idx:
                val, nxt = _parse_int_tokens(tokens, j)
                if val is not None:
                    left = val
                    j = nxt
                else:
                    j += 1
            # parse right number
            right = None
            k = idx + 1
            # skip fillers
            while k < len(tokens) and tokens[k] in _FILLERS:
                k += 1
            val, _ = _parse_int_tokens(tokens, k)
            if val is not None:
                right = val
            if left is not None and right is not None:
                vitals["bp"] = {"systolic": int(left), "diastolic": int(right)}
                break

    return vitals


def _compare(expected_v: dict, actual_v: dict) -> Tuple[List[dict], List[dict]]:
    matched = []
    mismatches = []

    # temperature: allow +-0.1 tolerance
    exp_t = expected_v.get("temperature")
    if exp_t is not None:
        act_t = actual_v.get("temperature")
        if act_t is None:
            mismatches.append({"type": "temperature", "expected": exp_t, "transcript": None, "note": "Temperature not found"})
        elif abs(float(act_t) - float(exp_t)) <= 0.1:
            matched.append({"type": "temperature", "value": float(exp_t)})
        else:
            mismatches.append({"type": "temperature", "expected": float(exp_t), "transcript": float(act_t), "note": "Temperature differs"})

    # SpO2: exact int match
    exp_s = expected_v.get("spo2")
    if exp_s is not None:
        act_s = actual_v.get("spo2")
        if act_s is None:
            mismatches.append({"type": "spo2", "expected": int(exp_s), "transcript": None, "note": "SpO2 not found"})
        elif int(act_s) == int(exp_s):
            matched.append({"type": "spo2", "value": int(exp_s)})
        else:
            mismatches.append({"type": "spo2", "expected": int(exp_s), "transcript": int(act_s), "note": "SpO2 differs"})

    # BP: exact systolic/diastolic match
    exp_bp = expected_v.get("bp")
    if exp_bp is not None:
        act_bp = actual_v.get("bp")
        if act_bp is None:
            mismatches.append({"type": "bp", "expected": exp_bp, "transcript": None, "note": "Blood pressure not found"})
        elif int(act_bp.get("systolic", -1)) == int(exp_bp.get("systolic")) and int(act_bp.get("diastolic", -1)) == int(exp_bp.get("diastolic")):
            matched.append({"type": "bp", "value": exp_bp})
        else:
            mismatches.append({"type": "bp", "expected": exp_bp, "transcript": act_bp, "note": "Blood pressure differs"})

    return matched, mismatches


@tool("check_vitals_fidelity")
def check_vitals_fidelity(expected: str, transcript: str) -> dict:
    """
    Extract and compare critical numeric vitals between expected script and transcript.
    Returns a high-signal mismatch list when values differ.
    """
    expected_vitals = _extract_expected_vitals(expected or "")
    transcript_vitals = _extract_transcript_vitals(transcript or "")
    matched, mismatches = _compare(expected_vitals, transcript_vitals)

    total = len(matched) + len(mismatches)
    score = round((len(matched) / total) * 100, 1) if total > 0 else 100.0

    return {
        "expected_vitals": expected_vitals,
        "transcript_vitals": transcript_vitals,
        "matched": matched,
        "mismatches": mismatches,
        "vitals_count": total,
        "mismatch_count": len(mismatches),
        "vitals_fidelity_score": score,
    }
