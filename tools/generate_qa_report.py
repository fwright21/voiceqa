import json
import os
import re
from langchain_core.tools import tool
from langchain_ollama import OllamaLLM
from tools.model_config import get_model

# ── Verdict thresholds (locked — do not tune at runtime) ──────────────────────

# Any one of these → FAIL (high-confidence, deterministic signals)
_FAIL_RULES = [
    lambda d: (
        d.get("accuracy", {}).get("wer", 0) > 0.30
        and len(d.get("transcript", "").split()) > 10
    ),
    lambda d: len(d.get("entity_fidelity", {}).get("mismatches", [])) > 0,
    lambda d: d.get("artifacts", {}).get("clipping_detected", False),
]

_FAIL_LABELS = [
    "WER > 30% on utterance with more than 10 words",
    "Entity mismatch detected (number, code, or date differs from expected)",
    "Audio clipping detected",
]

# Any one of these → REVIEW (medium/low confidence signals)
_REVIEW_RULES = [
    lambda d: (
        (d.get("pause_naturalness", {}) or {}).get("max_within_phrase_gap_sec")
        is not None
        and d["pause_naturalness"]["max_within_phrase_gap_sec"] >= 1.6
    ),
    lambda d: (
        (d.get("pause_naturalness", {}) or {}).get("max_within_phrase_gap_sec")
        is not None
        and d["pause_naturalness"]["max_within_phrase_gap_sec"] >= 0.9
    ),
    lambda d: (
        (d.get("mos", {}) or {}).get("mos_score") is not None
        and d["mos"]["mos_score"] < 3.0
    ),
    lambda d: (d.get("pauses", {}) or {}).get("longest_pause_sec", 0) > 3.0,
    lambda d: (
        (d.get("prosody", {}) or {}).get("jitter") is not None
        and d["prosody"]["jitter"] > 0.05
    ),
    lambda d: (
        (d.get("prosody", {}) or {}).get("shimmer") is not None
        and d["prosody"]["shimmer"] > 0.15
    ),
    lambda d: (
        (d.get("prosody", {}) or {}).get("hnr") is not None
        and d["prosody"]["hnr"] < 5.0
    ),
    lambda d: len((d.get("faithfulness", {}) or {}).get("violations", [])) > 0,
    lambda d: len((d.get("name_fidelity", {}) or {}).get("mismatches", [])) > 0,
]

_REVIEW_LABELS = [
    "Long within-phrase pause detected (unnatural pause inside a phrase)",
    "Mid-phrase pause detected (unnatural pause inside a phrase)",
    "MOS score below 3.0 — voice may sound unnatural",
    "Pause longer than 3 seconds detected",
    "Jitter above 5% — pitch instability detected",
    "Shimmer above 15% — amplitude instability detected",
    "HNR below 5 dB — high noise-to-signal ratio",
    "Faithfulness violations flagged (low confidence — manual review recommended)",
    "Proper noun/name mismatch detected (high impact — manual review recommended)",
]


def _compute_verdict(analysis_data: dict) -> tuple[str, list[str]]:
    """
    Apply locked thresholds to compute verdict and list of failure reasons.
    Returns: (verdict, failures)
    """
    failures = []

    for rule, label in zip(_FAIL_RULES, _FAIL_LABELS):
        try:
            if rule(analysis_data):
                failures.append(label)
        except Exception:
            pass

    if failures:
        return "FAIL", failures

    reviews = []
    for rule, label in zip(_REVIEW_RULES, _REVIEW_LABELS):
        try:
            if rule(analysis_data):
                reviews.append(label)
        except Exception:
            pass

    if reviews:
        return "REVIEW", reviews

    return "PASS", []


def _compute_score(verdict: str, analysis_data: dict, failures: list[str]) -> int:
    """
    Compute a stable 0–100 score without an LLM.

    This is intentionally simple and deterministic: the LLM (when available)
    can refine wording, but scoring must work offline.
    """
    base = {
        "PASS": 90,
        "REVIEW": 70,
        "FAIL": 25,
        "LOW_CONFIDENCE": 0,
    }.get(verdict, 50)

    accuracy = analysis_data.get("accuracy", {}) or {}
    wer = accuracy.get("wer")
    if isinstance(wer, (int, float)):
        base -= int(min(50, max(0.0, float(wer)) * 100))

    artifacts = analysis_data.get("artifacts", {}) or {}
    artifact_count = int(artifacts.get("artifact_count") or 0)
    base -= min(20, artifact_count * 5)

    pauses = analysis_data.get("pauses", {}) or {}
    longest_pause = pauses.get("longest_pause_sec")
    if isinstance(longest_pause, (int, float)) and float(longest_pause) > 3.0:
        base -= 10

    mos = analysis_data.get("mos", {}) or {}
    mos_score = mos.get("mos_score")
    if isinstance(mos_score, (int, float)):
        if float(mos_score) < 3.0:
            base -= 15
        elif float(mos_score) < 3.5:
            base -= 7

    entity = analysis_data.get("entity_fidelity", {}) or {}
    mismatches = entity.get("mismatches") or []
    if isinstance(mismatches, list) and len(mismatches) > 0:
        base -= 25

    faithfulness = analysis_data.get("faithfulness", {}) or {}
    violations = faithfulness.get("violations") or []
    if isinstance(violations, list) and len(violations) > 0:
        base -= 10

    # Penalize long failure lists slightly, but avoid double-counting.
    base -= min(10, max(0, len(failures) - 1) * 2)

    return int(min(100, max(0, base)))


def _fallback_report_text(
    verdict: str, failures: list[str], analysis_data: dict, score: int
) -> str:
    """Generate a human-readable report without calling an LLM."""
    accuracy = analysis_data.get("accuracy", {}) or {}
    wer = accuracy.get("wer")
    transcript = (analysis_data.get("transcript") or "").strip()
    pauses = analysis_data.get("pauses", {}) or {}
    artifacts = analysis_data.get("artifacts", {}) or {}
    prosody = analysis_data.get("prosody", {}) or {}
    mos = analysis_data.get("mos", {}) or {}
    entity = analysis_data.get("entity_fidelity", {}) or {}
    name_fidelity = analysis_data.get("name_fidelity", {}) or {}
    faithfulness = analysis_data.get("faithfulness", {}) or {}

    reasons = failures or ["None"]
    pauses_list = pauses.get("pauses") or []
    artifacts_list = artifacts.get("artifacts") or []
    entity_mismatches = entity.get("mismatches") or []
    name_mismatches = name_fidelity.get("mismatches") or []
    faithfulness_violations = faithfulness.get("violations") or []

    def _fmt_num(value, default="N/A"):
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return str(round(float(value), 3))
        return str(value)

    suggestions = []
    if isinstance(wer, (int, float)) and float(wer) > 0.15:
        suggestions.append(
            "Regenerate or clean up the audio to improve intelligibility and reduce WER (background noise, mic artifacts, speed)."
        )
    if len(entity_mismatches) > 0:
        suggestions.append(
            "Ensure numbers/codes/dates are spoken exactly as expected (entity fidelity mismatches found)."
        )
    if (
        pauses.get("longest_pause_sec", 0)
        and float(pauses.get("longest_pause_sec", 0)) > 3.0
    ):
        suggestions.append(
            "Reduce long silences by tightening turn-taking and trimming dead air in the audio."
        )
    if len(artifacts_list) > 0:
        suggestions.append(
            "Address audio artifacts (normalize levels, avoid clipping, remove clicks/pops)."
        )
    if mos.get("mos_score") is not None and float(mos.get("mos_score")) < 3.0:
        suggestions.append(
            "Try a different voice/model or adjust synthesis settings (MOS suggests unnaturalness)."
        )
    if len(faithfulness_violations) > 0:
        suggestions.append(
            "Manually review content against the script (faithfulness tool flagged potential semantic issues)."
        )

    while len(suggestions) < 3:
        suggestions.append(
            "Spot-check the transcript vs expected script and rerun VoiceQA after any audio/model changes."
        )

    # Render concise lists (avoid very long lines)
    pause_lines = []
    for p in pauses_list[:5]:
        pause_lines.append(
            f"- {p.get('start_sec')}s → {p.get('end_sec')}s ({p.get('duration_sec')}s)"
        )
    if len(pauses_list) > 5:
        pause_lines.append(f"- ... ({len(pauses_list) - 5} more)")

    artifact_lines = []
    for a in artifacts_list[:5]:
        artifact_lines.append(
            f"- {a.get('severity', '').upper()} {a.get('type')}: {a.get('detail')}"
        )
    if len(artifacts_list) > 5:
        artifact_lines.append(f"- ... ({len(artifacts_list) - 5} more)")

    entity_lines = []
    for m in entity_mismatches[:5]:
        entity_lines.append(
            f"- expected={m.get('expected')} transcript={m.get('transcript')}"
        )
    if len(entity_mismatches) > 5:
        entity_lines.append(f"- ... ({len(entity_mismatches) - 5} more)")

    faith_lines = []
    for v in faithfulness_violations[:5]:
        faith_lines.append(f"- {v.get('type')}: {v.get('reason')}")
    if len(faithfulness_violations) > 5:
        faith_lines.append(f"- ... ({len(faithfulness_violations) - 5} more)")

    lines = [
        "### Overall Score",
        str(int(score)),
        "",
        "### Summary",
        f"Verdict: {verdict}. "
        + ("; ".join(reasons) if reasons else "No issues detected."),
        "This report was generated without an LLM because the local Ollama endpoint was unavailable.",
        "",
        "### Transcript Accuracy",
        f"WER: {_fmt_num(wer)}. Transcript (first 200 chars): {transcript[:200]!r}",
        "",
        "### Audio Quality",
        f"MOS: {_fmt_num(mos.get('mos_score'))} (model: {mos.get('model', 'unknown')}). "
        f"Prosody: f0_mean={_fmt_num(prosody.get('f0_mean'))}, jitter={_fmt_num(prosody.get('jitter'))}, "
        f"shimmer={_fmt_num(prosody.get('shimmer'))}, hnr={_fmt_num(prosody.get('hnr'))}.",
        "",
        "### Pause Analysis",
        f"Pause count: {pauses.get('pause_count', 0)}. Longest: {_fmt_num(pauses.get('longest_pause_sec'))}s.",
    ]
    lines.extend(pause_lines if pause_lines else ["- None"])

    lines.extend(
        [
            "",
            "### Audio Artifact Analysis",
            f"Artifact count: {artifacts.get('artifact_count', 0)}. Overall clean: {artifacts.get('overall_clean')}.",
        ]
    )
    lines.extend(artifact_lines if artifact_lines else ["- None"])

    lines.extend(
        [
            "",
            "### Entity & Faithfulness",
            f"Entity mismatches: {len(entity_mismatches)}. Name mismatches: {len(name_mismatches)}. Faithfulness violations: {len(faithfulness_violations)}.",
        ]
    )
    if len(entity_mismatches):
        lines.append("Entity mismatches:")
        lines.extend(entity_lines)
    else:
        lines.append("Entity mismatches: None")

    if len(name_mismatches):
        lines.append("Name mismatches:")
        lines.extend(name_lines)
    else:
        lines.append("Name mismatches: None")

    if len(faithfulness_violations):
        lines.append("Faithfulness violations:")
        lines.extend(faith_lines)
    else:
        lines.append("Faithfulness violations: None")

    lines.extend(
        [
            "",
            "### Suggestions",
            "1. " + suggestions[0],
            "2. " + suggestions[1],
            "3. " + suggestions[2],
            "",
        ]
    )

    return "\n".join(lines)


_REPORT_PROMPT = """\
You are VoiceQA, an expert QA engineer evaluating Text-to-Speech (TTS) and voice agent outputs.

You have been given structured analysis results for one audio file. The verdict has already been
computed from deterministic rules — your job is to write a clear, human-readable explanation.

## Verdict
{verdict}

## Failure/Review Reasons
{reasons}

## Full Analysis Data
```json
{analysis_json}
```

Write a concise QA report in this EXACT format. Do not add sections or change headers:

### Overall Score
[JUST a single integer between 0 and 100. Nothing else on this line.]

### Summary
2-3 sentences summarising the quality and the verdict.

### Transcript Accuracy
Comment on WER score and any specific word errors.

### Audio Quality
Comment on prosody (pitch, jitter, shimmer, HNR) and MOS score.

### Pause Analysis
Flag any unnatural pauses with timestamps and durations.

### Audio Artifact Analysis
List any detected artifacts.

### Entity & Faithfulness
Comment on entity fidelity and faithfulness results.

### Suggestions
1. First suggestion
2. Second suggestion
3. Third suggestion
"""


@tool("generate_qa_report")
def generate_qa_report(analysis_data: dict) -> dict:
    """
    Compute a PASS/REVIEW/FAIL verdict from locked thresholds, then use a local
    Ollama LLM to generate a human-readable QA report with score and suggestions.

    Args:
        analysis_data: Dict containing results from all pipeline tools.

    Returns:
        A dict with: report_text, score, verdict, failures, suggestions.
    """
    verdict, failures = _compute_verdict(analysis_data)

    # If transcript was flagged low-confidence upstream, override verdict
    if analysis_data.get("transcript_confidence") == "low":
        verdict = "LOW_CONFIDENCE"
        failures = [
            "Whisper transcript confidence too low — audio may be silent or corrupted"
        ]

    llm = OllamaLLM(
        model=get_model("report"),
        base_url="http://localhost:11434",
        temperature=0.2,
    )

    reasons_text = "\n".join(f"- {r}" for r in failures) if failures else "- None"

    prompt = _REPORT_PROMPT.format(
        verdict=verdict,
        reasons=reasons_text,
        analysis_json=json.dumps(analysis_data, indent=2, default=str),
    )

    report_text = None
    suggestions = []

    try:
        report_text = llm.invoke(prompt)
    except Exception:
        report_text = None

    if report_text:
        # Extract score
        score = 50
        score_match = re.search(r"###\s*Overall Score\s*\n+\s*(\d+)", report_text)
        if not score_match:
            score_match = re.search(r"(?:score|Score)[^\d]*(\d{1,3})", report_text)
        if score_match:
            score = min(100, max(0, int(score_match.group(1))))

        # Extract suggestions
        in_suggestions = False
        for line in report_text.splitlines():
            if "### Suggestions" in line:
                in_suggestions = True
                continue
            if in_suggestions:
                if line.startswith("###"):
                    break
                cleaned = re.sub(r"^\s*\d+[\.\)]\s*", "", line).strip()
                if cleaned and not cleaned.startswith("*"):
                    suggestions.append(cleaned)
    else:
        score = _compute_score(verdict, analysis_data, failures)
        report_text = _fallback_report_text(verdict, failures, analysis_data, score)
        # suggestions are rendered in report_text already; return as list too
        for line in report_text.splitlines():
            if re.match(r"^\s*\d+\.\s+", line):
                suggestions.append(re.sub(r"^\s*\d+\.\s+", "", line).strip())

    return {
        "report_text": report_text,
        "score": score,
        "verdict": verdict,
        "failures": failures,
        "suggestions": suggestions,
    }
    name_lines = []
    for m in name_mismatches[:5]:
        name_lines.append(
            f"- expected={m.get('value')} best_match={m.get('best_match')} ratio={m.get('best_ratio')}"
        )
    if len(name_mismatches) > 5:
        name_lines.append(f"- ... ({len(name_mismatches) - 5} more)")
