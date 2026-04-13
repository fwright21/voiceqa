"""
Entity fidelity checker — regex only.

Extracts structured entities from the expected script and checks whether each
appears correctly in the actual transcript. Scope is limited to:
  - Numbers       : integers, decimals, percentages, phone numbers
  - Alphanumeric codes : booking refs, confirmation codes (4-8 chars)
  - Dates         : common formats (DD/MM/YYYY, Month DD, etc.)

Names are intentionally excluded — too many format variants cause false positives.

A HIGH-confidence FAIL is triggered by any mismatch (entity_mismatch_count > 0).
This is checked in generate_qa_report.py, not here.
"""

import re
from langchain_core.tools import tool


# ── Patterns ──────────────────────────────────────────────────────────────────

# Standalone numbers: integers, decimals, percentages
# Matches: 14.5%, 1-800-555-0199, 250, 0.75, 30
_NUMBER_PATTERN = re.compile(
    r"""
    (?<!\w)
    (?:
        \d{1,3}(?:[,\s]\d{3})+  # thousands: 1,000 or 1 000
        | \d+(?:\.\d+)?%?        # plain integer or decimal, optional %
        | \d[\d\s\-\(\)\.]{6,}   # phone-like: 1-800-555-0199
    )
    (?!\w)
    """,
    re.VERBOSE,
)

# Alphanumeric codes: 4–8 uppercase chars+digits, surrounded by whitespace/punctuation
_CODE_PATTERN = re.compile(r"(?<!\w)[A-Z0-9]{4,8}(?!\w)")

# Dates: DD/MM/YYYY, MM-DD-YYYY, Month DD YYYY, DD Month YYYY
_DATE_PATTERN = re.compile(
    r"""
    (?:
        \d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}   # 01/03/2024
        | (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2}(?:,?\s*\d{4})?
        | \d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*(?:\s+\d{4})?
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _normalise(text: str) -> str:
    """Strip punctuation and lowercase for fuzzy comparison."""
    return re.sub(r"[\s\-\.\(\),]", "", text).lower()


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

_NUM_FILLERS = {"and", "a", "an", "the", "about", "around"}


def _tokenize_for_numbers(text: str) -> list[str]:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\.\s/%-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return [t for t in text.split() if t and t not in _NUM_FILLERS]


def _parse_int_tokens(tokens: list[str], i: int) -> tuple[int | None, int]:
    if i >= len(tokens):
        return None, i
    t = tokens[i]
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


def _parse_decimal(tokens: list[str], i: int) -> tuple[str | None, int]:
    if i >= len(tokens):
        return None, i

    t = tokens[i]
    if re.fullmatch(r"\d+(\.\d+)?", t):
        return t, i + 1

    integer, j = _parse_int_tokens(tokens, i)
    if integer is None:
        return None, i

    if j < len(tokens) and tokens[j] in {"point", "dot"}:
        j += 1
        digits: list[str] = []
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
            return f"{integer}.{''.join(digits)}", j
    return str(integer), j


def _transcript_numeric_augmentation(transcript: str) -> str:
    """
    Augment transcript text by inserting digit forms of number-word sequences.
    This is a best-effort helper to avoid false entity mismatches like "3" vs "three".
    """
    tokens = _tokenize_for_numbers(transcript)
    out: list[str] = []
    i = 0
    while i < len(tokens):
        num, j = _parse_decimal(tokens, i)
        if num is not None and j > i:
            out.append(num)
            i = j
            continue
        out.append(tokens[i])
        i += 1
    return " ".join(out)


def _extract_entities(text: str) -> dict:
    """Extract all entity types from a text string."""
    return {
        "numbers": _NUMBER_PATTERN.findall(text),
        "codes":   _CODE_PATTERN.findall(text),
        "dates":   _DATE_PATTERN.findall(text),
    }


@tool("check_entity_fidelity")
def check_entity_fidelity(expected: str, transcript: str) -> dict:
    """
    Check whether structured entities in the expected script appear correctly
    in the actual transcript.

    Args:
        expected:   The expected script text.
        transcript: The actual transcript from Whisper.

    Returns:
        Dict with mismatches list, matched list, fidelity_score (0-100).
    """
    expected_entities = _extract_entities(expected)
    transcript_norm = _normalise(transcript)
    transcript_numeric_norm = _normalise(_transcript_numeric_augmentation(transcript))

    mismatches = []
    matched = []

    for entity_type, entities in expected_entities.items():
        for entity in entities:
            entity_norm = _normalise(entity)
            if entity_norm and (entity_norm in transcript_norm or entity_norm in transcript_numeric_norm):
                matched.append({"type": entity_type, "value": entity})
            else:
                mismatches.append({
                    "type":  entity_type,
                    "value": entity,
                    "note":  f"'{entity}' not found in transcript",
                })

    total = len(matched) + len(mismatches)
    fidelity_score = round((len(matched) / total) * 100, 1) if total > 0 else 100.0

    return {
        "mismatches":      mismatches,
        "matched":         matched,
        "fidelity_score":  fidelity_score,
        "entity_count":    total,
        "mismatch_count":  len(mismatches),
    }
