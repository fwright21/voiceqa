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


@tool("check_faithfulness")
def check_faithfulness(
    expected: str,
    transcript: str,
) -> dict:
    """
    ...
    """
    try:
        llm = OllamaLLM(
            model=get_model("faithfulness"),
            base_url="http://localhost:11434",
            temperature=0.0,
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
            "q2_addition": "Hallucinated content added",
            "q3_omission": "Critical content omitted",
        }

        for key, label in question_map.items():
            entry = answers.get(key, {})
            if str(entry.get("answer", "")).upper().startswith("YES"):
                violations.append(
                    {
                        "type": label,
                        "reason": entry.get("reason", ""),
                    }
                )

        faithfulness_score = round(100 - (len(violations) / 3) * 100, 1)
        faithful = len(violations) == 0

        return {
            "faithful": faithful,
            "violations": violations,
            "faithfulness_score": faithfulness_score,
            "confidence": "low",
            "raw_answers": answers,
            "skipped": False,
        }

    except Exception as e:
        return {
            "error": str(e),
            "skipped": True,
            "faithful": None,
            "violations": [],
            "faithfulness_score": None,
            "confidence": "low",
        }
