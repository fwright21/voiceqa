"""
Faithfulness checker — LLM-as-judge (semantic only).

Checks whether the actual transcript is semantically faithful to the expected script.
Scope: semantic meaning only — hallucinations, fabrications, contradictions.
Entities (numbers, codes, dates) are handled by check_entity_fidelity.py.

IMPORTANT: This tool uses a small local LLM (3-4B parameters).
Output confidence is always "low" — violations can only trigger REVIEW, never FAIL.
"""

import json
import re
from langchain_core.tools import tool
from langchain_ollama import OllamaLLM
from tools.model_config import get_model


def _normalize_for_judge(text: str) -> str:
    """
    Normalization for LLM-as-judge inputs.
    We intentionally remove punctuation/casing so the judge focuses on meaning,
    not formatting or capitalization.
    """
    text = (text or "").lower().strip()
    # Bridge common numeric formatting differences before stripping punctuation.
    text = text.replace("%", " percent ")
    text = _augment_number_words(text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


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


def _augment_number_words(text: str) -> str:
    """
    Best-effort conversion of common number-word sequences into digits so the judge
    doesn't flag differences like '3' vs 'three' or '92%' vs 'ninety two percent'.
    """
    tokens = re.sub(r"[^a-z0-9\s\.]", " ", (text or "").lower())
    tokens = re.sub(r"\s+", " ", tokens).strip().split()
    out = []
    i = 0
    while i < len(tokens):
        t = tokens[i]

        # already numeric
        if re.fullmatch(r"\d+(\.\d+)?", t):
            out.append(t)
            i += 1
            continue

        # tens + ones: ninety two => 92
        if t in _TENS:
            val = _TENS[t]
            if i + 1 < len(tokens) and tokens[i + 1] in _NUM_WORDS_0_19:
                val += _NUM_WORDS_0_19[tokens[i + 1]]
                out.append(str(val))
                i += 2
                continue
            out.append(str(val))
            i += 1
            continue

        # one..nineteen
        if t in _NUM_WORDS_0_19:
            out.append(str(_NUM_WORDS_0_19[t]))
            i += 1
            continue

        # point digit digit...
        if t in {"point", "dot"} and out and re.fullmatch(r"\d+", out[-1]):
            j = i + 1
            digits = []
            while j < len(tokens):
                if tokens[j].isdigit() and len(tokens[j]) == 1:
                    digits.append(tokens[j])
                    j += 1
                    continue
                if tokens[j] in _NUM_WORDS_0_19 and _NUM_WORDS_0_19[tokens[j]] < 10:
                    digits.append(str(_NUM_WORDS_0_19[tokens[j]]))
                    j += 1
                    continue
                break
            if digits:
                out[-1] = out[-1] + "." + "".join(digits)
                i = j
                continue

        out.append(t)
        i += 1

    return " ".join(out)


_FAITHFULNESS_PROMPT = """\
You are evaluating whether a voice agent's spoken output was faithful to its expected script.

Expected script:
{expected}

What was actually said (transcript):
{transcript}

Answer each question with only YES or NO, followed by one sentence of explanation.
Focus on MEANING and CONTENT only — ignore minor wording differences, filler words,
and do not check numbers or specific codes (those are checked separately).

Important:
- Ignore punctuation and capitalization differences.
- Ignore minor misspellings/ASR spelling variants; do NOT treat them as added information.
- Only answer YES if you are confident there is a real meaning-level difference.

Q1: Did the transcript say anything that CONTRADICTS the expected script?
Q2: Did the transcript ADD information that was NOT in the expected script?
Q3: Did the transcript OMIT anything semantically critical from the expected script?

Respond in this exact JSON format:
{{
  "q1_contradiction": {{"answer": "YES or NO", "reason": "one sentence"}},
  "q2_addition":      {{"answer": "YES or NO", "reason": "one sentence"}},
  "q3_omission":      {{"answer": "YES or NO", "reason": "one sentence"}}
}}
"""


@tool("check_faithfulness")
def check_faithfulness(expected: str, transcript: str) -> dict:
    """
    Use a local LLM to check semantic faithfulness of the transcript to the expected script.

    Args:
        expected:   The expected script text.
        transcript: The actual transcript from Whisper.

    Returns:
        Dict with faithful (bool), violations (list), faithfulness_score (0-100),
        confidence ("low"), and raw LLM answers. Returns error dict on failure.
    """
    try:
        llm = OllamaLLM(
            model=get_model("faithfulness"),
            base_url="http://localhost:11434",
            temperature=0.0,  # deterministic for consistency
        )

        prompt = _FAITHFULNESS_PROMPT.format(
            expected=_normalize_for_judge(expected),
            transcript=_normalize_for_judge(transcript),
        )

        raw = llm.invoke(prompt)

        # Extract JSON from response (model may wrap it in markdown)
        json_match = re.search(r"\{[\s\S]+\}", raw)
        if not json_match:
            raise ValueError(f"No JSON found in LLM response: {raw[:200]}")

        answers = json.loads(json_match.group())

        violations = []
        question_map = {
            "q1_contradiction": "Contradiction detected",
            "q2_addition":      "Hallucinated content added",
            "q3_omission":      "Critical content omitted",
        }

        for key, label in question_map.items():
            entry = answers.get(key, {})
            if str(entry.get("answer", "")).upper().startswith("YES"):
                violations.append({
                    "type":   label,
                    "reason": entry.get("reason", ""),
                })

        faithfulness_score = round(100 - (len(violations) / 3) * 100, 1)
        faithful = len(violations) == 0

        return {
            "faithful":          faithful,
            "violations":        violations,
            "faithfulness_score": faithfulness_score,
            "confidence":        "low",
            "raw_answers":       answers,
            "skipped":           False,
        }

    except Exception as e:
        return {
            "error":             str(e),
            "skipped":           True,
            "faithful":          None,
            "violations":        [],
            "faithfulness_score": None,
            "confidence":        "low",
        }
