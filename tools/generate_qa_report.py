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


def _actionable_suggestions(analysis_data: dict) -> list[str]:
    """
    Deterministic remediation suggestions in plain language.

    Each suggestion is a single string in three parts, pipe-separated:
        "What happened: ... || How to fix: ... || How to check: ..."

    Design rules:
      - Write for a product manager, not an engineer.
      - No acronyms (WER, MOS, SSML, HNR, ASR) without a plain-English explanation.
      - "How to check" is something a human can hear or see, not a number.
      - One concrete action per "How to fix". Vendor-specific examples allowed.
    """
    suggestions: list[str] = []

    def _suggest(what: str, fix: str, check: str) -> str:
        return (
            f"What happened: {what.strip().rstrip('.')}."
            f" || How to fix: {fix.strip().rstrip('.')}."
            f" || How to check: {check.strip().rstrip('.')}."
        )

    def _add(text: str):
        if text and text not in suggestions:
            suggestions.append(text)

    accuracy = analysis_data.get("accuracy", {}) or {}
    wer = accuracy.get("wer")
    pauses = analysis_data.get("pauses", {}) or {}
    pause_nat = analysis_data.get("pause_naturalness", {}) or {}
    artifacts = analysis_data.get("artifacts", {}) or {}
    prosody = analysis_data.get("prosody", {}) or {}
    mos = analysis_data.get("mos", {}) or {}
    entity = analysis_data.get("entity_fidelity", {}) or {}
    name_fidelity = analysis_data.get("name_fidelity", {}) or {}
    faithfulness = analysis_data.get("faithfulness", {}) or {}

    # Transcript quality
    if isinstance(wer, (int, float)) and float(wer) > 0.15:
        _add(
            _suggest(
                what="The transcript doesn't match the script — many words are wrong, missing, or extra",
                fix="Have the agent slow down and speak more clearly. If it's a recording, move closer to the mic and reduce background noise",
                check="Re-run the clip and read the new transcript — it should read like the expected script",
            )
        )

    # Entity fidelity
    entity_mismatches = entity.get("mismatches") or []
    if isinstance(entity_mismatches, list) and len(entity_mismatches) > 0:
        _add(
            _suggest(
                what="The agent said the wrong number, date, or code — this is dangerous in healthcare or finance",
                fix='Speak important numbers digit by digit ("one eight zero" instead of "one hundred eighty"). For dosages, always include the unit ("fifty milligrams")',
                check="Listen to the flagged moment — the number, date, or code should now match what was expected",
            )
        )

    # Unnatural pauses
    max_within = pause_nat.get("max_within_phrase_gap_sec")
    if isinstance(max_within, (int, float)) and float(max_within) >= 0.9:
        _add(
            _suggest(
                what="The agent paused in the middle of a sentence — sounds broken or like it's buffering",
                fix="Shorten the sentence or split it with a period. If you're using ElevenLabs or Cartesia, try lowering the 'style' or 'stability' setting",
                check="Replay the clip — the pause should be gone, or only appear at a comma or full stop",
            )
        )
    longest_pause = pauses.get("longest_pause_sec")
    if isinstance(longest_pause, (int, float)) and float(longest_pause) > 3.0:
        _add(
            _suggest(
                what="The agent had a long silent gap (over 3 seconds) — sounds like it froze",
                fix="Trim silence from the end of the audio, or remove extra punctuation/padding from the script that the voice is interpreting as a long pause",
                check="Replay the clip — there should be no awkward silences longer than a normal breath",
            )
        )

    # Speaking rate
    speaking_rate = analysis_data.get("speaking_rate", {}) or {}
    segments = speaking_rate.get("segments") or []
    if isinstance(segments, list) and any(
        isinstance(s, dict) and s.get("severity") in {"warn", "fail"} for s in segments
    ):
        _add(
            _suggest(
                what="Parts of the clip are spoken too fast or too slow — listeners can't keep up, or it feels sluggish",
                fix="In your voice provider's settings, adjust the speed/rate. Add short pauses (commas or full stops) before important phrases like medication names",
                check="Replay the clip — every sentence should be easy to follow at a normal listening pace",
            )
        )

    # Audio artifacts
    artifacts_list = artifacts.get("artifacts") or []
    if isinstance(artifacts_list, list) and len(artifacts_list) > 0:
        _add(
            _suggest(
                what="The audio has crackling, clipping, or pops — sounds distorted or unprofessional",
                fix="In your voice provider settings, lower the output volume by about 10–20%. If you're recording, move further from the mic or check your audio cable",
                check="Replay the clip and listen for crackle, distortion, or sudden pops — the audio should sound clean",
            )
        )

    # Naturalness / prosody
    mos_score = mos.get("mos_score")
    if isinstance(mos_score, (int, float)) and float(mos_score) < 3.5:
        _add(
            _suggest(
                what="The voice sounds robotic or unnatural — users may lose trust or hang up",
                fix="Try a different voice or voice model from your provider. If using ElevenLabs, try a different voice or increase expressiveness. If using Cartesia, try a more natural preset",
                check="Replay the clip — it should sound like a real person, not a synthesized voice",
            )
        )
    monotone = prosody.get("monotone") if isinstance(prosody, dict) else None
    if monotone is True:
        _add(
            _suggest(
                what="The voice sounds flat — no rise or fall in tone, like reading a list out loud",
                fix="In your voice provider settings, increase expressiveness or style. If supported, mark key phrases for emphasis in the script",
                check="Replay the clip — important words and questions should sound emphasized, not monotone",
            )
        )

    # Name fidelity
    name_mismatches = name_fidelity.get("mismatches") or []
    if isinstance(name_mismatches, list) and len(name_mismatches) > 0:
        _add(
            _suggest(
                what="A person's name or proper noun was mispronounced or mistranscribed",
                fix="Respell the name how it sounds (for example, write 'Siobhan' as 'Shi-vawn'). Most voice providers also let you upload a pronunciation dictionary",
                check="Replay the clip — the name should sound the way it's meant to be pronounced",
            )
        )

    # Faithfulness
    violations = faithfulness.get("violations") or []
    if isinstance(violations, list) and len(violations) > 0:
        _add(
            _suggest(
                what="The agent said something with a different meaning than the script — could be missing a 'not', adding a claim, or changing the intent",
                fix="Tighten the prompt so the agent must use the exact wording for safety-critical statements. For regulated content, use a template instead of free generation",
                check="Read the new transcript next to the expected script — the meaning should match exactly, not just the gist",
            )
        )

    # Ensure at least 3 items
    _add(
        _suggest(
            what="VoiceQA flagged this clip but you should confirm it manually before changing anything",
            fix="Click the 'Jump' button next to any flagged moment to hear it. Decide if the issue is real or just a quirk of how VoiceQA reads the audio",
            check="A teammate listens and agrees the problem is real",
        )
    )
    _add(
        _suggest(
            what="You won't know if a fix actually worked unless you re-test",
            fix="Save a baseline of the current suite results, then re-run after your changes",
            check="The same case now passes, and no other cases got worse",
        )
    )
    _add(
        _suggest(
            what="Some voice problems are random and don't happen on every run",
            fix="Re-run the same clip 2 or 3 times before deciding the issue is real",
            check="The same problem shows up consistently across runs",
        )
    )

    return suggestions[:3]


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

    suggestions = _actionable_suggestions(analysis_data)

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

    def _fmt_suggestion_markdown(idx: int, raw: str) -> list[str]:
        parts = [p.strip() for p in str(raw).split("||")]
        if len(parts) >= 2:
            out = [f"{idx}. {parts[0]}"]
            for part in parts[1:]:
                out.append(f"   {part}")
            return out
        return [f"{idx}. {raw}"]

    lines.append("")
    lines.append("### Suggestions")
    for i, s in enumerate(suggestions[:3], start=1):
        lines.extend(_fmt_suggestion_markdown(i, s))
    lines.append("")

    return "\n".join(lines)


_REPORT_PROMPT = """\
You are VoiceQA. You write reports about voice agent audio for product managers and
compliance reviewers — NOT engineers. Your readers do not know what WER, MOS, SSML, HNR,
ASR, jitter, or shimmer mean. If you mention any of them, you must explain in plain English
on the same line (e.g., "transcript accuracy (WER) — how closely the words match the script").

You have been given structured analysis results for one audio file. The verdict has already
been computed from deterministic rules — your job is to translate the technical results into
clear, plain-language explanations.

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
2-3 sentences in plain English. What does this clip sound like, and is it safe to ship?

### Transcript Accuracy
In plain English: did the agent say what the script asked for? Name specific words that came
out wrong if any. Avoid raw metric names without explanation.

### Audio Quality
In plain English: does the voice sound natural, robotic, distorted, or flat? Mention the
overall impression a listener would have.

### Pause Analysis
Flag any pauses that would sound broken or awkward to a listener, with timestamps.

### Audio Artifact Analysis
In plain English: any crackling, clipping, pops, or distortion?

### Entity & Faithfulness
In plain English: did the agent get numbers, dates, codes, names, and meaning right?

### Suggestions
Write EXACTLY 3 suggestions in this format — each one a single line with three parts
separated by "||":

1. What happened: [plain-English description of the problem] || How to fix: [one concrete action; vendor-specific examples like ElevenLabs/Cartesia are welcome] || How to check: [what a human can hear or see when it's fixed — NOT a metric threshold]
2. (same format)
3. (same format)

Rules for the three suggestions:
- "What happened" must describe what a listener would experience, not internal metric names.
- "How to fix" must be ONE action, not a list of options separated by "or".
- "How to check" must be something a human can verify by listening or reading — never "WER < 0.15" or any number.
- No acronyms in any of the three parts unless explained.
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
    suggestions: list[str] = []
    suggestions_det = _actionable_suggestions(analysis_data)

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
        if len(suggestions) < 3:
            for s in suggestions_det:
                if s not in suggestions:
                    suggestions.append(s)
                if len(suggestions) >= 3:
                    break
    else:
        score = _compute_score(verdict, analysis_data, failures)
        report_text = _fallback_report_text(verdict, failures, analysis_data, score)
        # suggestions are rendered in report_text already; return as list too
        for line in report_text.splitlines():
            if re.match(r"^\s*\d+\.\s+", line):
                suggestions.append(re.sub(r"^\s*\d+\.\s+", "", line).strip())
        if len(suggestions) < 3:
            suggestions = suggestions_det

    return {
        "report_text": report_text,
        "score": score,
        "verdict": verdict,
        "failures": failures,
        "suggestions": suggestions[:3],
    }
