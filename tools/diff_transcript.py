import jiwer
import difflib
import re
from langchain_core.tools import tool

def _normalise(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@tool("diff_transcript")
def diff_transcript(expected_script: str, actual_transcript: str) -> dict:
    """
    Compare the expected script against the Whisper transcript and return
    accuracy metrics and a word-level diff.
    """
    norm_exp = _normalise(expected_script)
    norm_act = _normalise(actual_transcript)

    # Safety check FIRST before doing anything else
    if not norm_exp or not norm_act:
        return {
            "wer": 1.0,
            "mer": 1.0,
            "wil": 1.0,
            "accuracy_pct": 0.0,
            "error_counts": {"substitutions": 0, "deletions": 0, "insertions": 0, "total_errors": 0},
            "diff_ops": [],
        }

    # jiwer metrics
    wer = round(min(1.0, float(jiwer.wer(norm_exp, norm_act))), 4)
    mer = round(min(1.0, float(jiwer.mer(norm_exp, norm_act))), 4)
    wil = round(min(1.0, float(jiwer.wil(norm_exp, norm_act))), 4)

    # difflib word-level diff
    exp_words = norm_exp.split()
    act_words = norm_act.split()
    matcher = difflib.SequenceMatcher(None, exp_words, act_words, autojunk=False)

    diff_ops = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        diff_ops.append({
            "op":       tag,
            "expected": " ".join(exp_words[i1:i2]),
            "actual":   " ".join(act_words[j1:j2]),
        })

    error_counts = {
        "substitutions": sum(1 for o in diff_ops if o["op"] == "replace"),
        "deletions":     sum(1 for o in diff_ops if o["op"] == "delete"),
        "insertions":    sum(1 for o in diff_ops if o["op"] == "insert"),
    }
    error_counts["total_errors"] = sum(error_counts.values())

    return {
        "wer":          wer,
        "mer":          mer,
        "wil":          wil,
        "accuracy_pct": round(max(0.0, (1 - wer) * 100), 2),
        "error_counts": error_counts,
        "diff_ops":     diff_ops,
    }