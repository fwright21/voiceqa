import logging
from pathlib import Path

from typing import Any, Dict, List

from tools.transcribe_audio import transcribe_audio
from tools.diff_transcript import diff_transcript
from tools.detect_pauses import detect_pauses
from tools.detect_audio_artifacts import detect_audio_artifacts
from tools.analyse_prosody import analyse_prosody
from tools.predict_mos import predict_mos
from tools.alignment import build_alignment
from tools.check_pause_naturalness import check_pause_naturalness
from tools.check_speaking_rate import check_speaking_rate
from tools.check_entity_fidelity import check_entity_fidelity
from tools.check_name_fidelity import check_name_fidelity
from tools.check_faithfulness import check_faithfulness
from tools.generate_qa_report import generate_qa_report
from tools.save_report import save_report
from tools.eval_runner import compute_weighted_score

logger = logging.getLogger(__name__)


def run_analysis(audio_path: str, expected_script: str, language: str = "en") -> dict:
    """
    Run the full voice_qa v2 pipeline on one audio file.

    Pipeline:
        1.  transcribe_audio       → transcript + confidence signals
        1.1 build_alignment        → word spans (if available)
        4.5 check_pause_naturalness→ classify energy pauses by phrase spans (deterministic)
        1.5 [gate]                 → skip downstream if transcript confidence is low
        2.  diff_transcript        → WER, accuracy
        3.  detect_audio_artifacts → clipping, DC offset, pops
        4.  detect_pauses          → silence gaps
        5.  analyse_prosody        → F0, jitter, shimmer, HNR [graceful fail]
        6.  predict_mos            → MOS 1-5 [graceful fail]
        7.  check_entity_fidelity  → number/code/date mismatches
        8.  check_faithfulness     → semantic faithfulness [graceful fail, low confidence]
        9.  generate_qa_report     → verdict + score + failures + suggestions
        10. save_report            → SQLite persistence

    Returns the full report dict including verdict, failures, and all metric results.
    """
    audio_name = Path(audio_path).name

    # ── Stage 1: Transcription ────────────────────────────────────────────────
    logger.info("Stage 1/10 — Transcribing audio")
    transcription = transcribe_audio.func(audio_path=audio_path)
    transcript_text = transcription["transcript"]
    transcript_confidence = transcription.get("transcript_confidence", "ok")
    alignment = build_alignment(transcription, expected_script=expected_script)

    # ── Stage 1.5: Confidence gate ────────────────────────────────────────────
    if transcript_confidence == "low":
        logger.warning("Transcript confidence LOW — skipping downstream analysis")
        return _low_confidence_result(
            audio_name=audio_name,
            expected_script=expected_script,
            transcription=transcription,
        )

    # ── Stage 2: Transcript diff ──────────────────────────────────────────────
    logger.info("Stage 2/10 — Diffing transcript")
    diff = diff_transcript.func(
        expected_script=expected_script,
        actual_transcript=transcript_text,
    )

    # ── Stage 3: Audio artifacts ──────────────────────────────────────────────
    logger.info("Stage 3/10 — Detecting artifacts")
    artifact_result = detect_audio_artifacts.func(audio_path=audio_path)

    # ── Stage 4: Pauses ───────────────────────────────────────────────────────
    logger.info("Stage 4/10 — Detecting pauses")
    pause_result = detect_pauses.func(
        audio_path=audio_path,
        word_spans=alignment.get("word_spans"),
        phrase_spans=alignment.get("phrase_spans"),
        transcript=transcript_text,
        language=language or "en",
    )
    pause_naturalness = check_pause_naturalness.func(
        alignment=alignment, pauses=pause_result
    )

    # ── Stage 4.5: Speaking rate ──────────────────────────────────────────
    logger.info("Stage 4.5/10 — Checking speaking rate")
    speaking_rate_result = check_speaking_rate.func(
        phrase_spans=alignment.get("phrase_spans") or [],
        language=language or "en",
    )

    # ── Stage 5: Prosody ──────────────────────────────────────────────────────
    logger.info("Stage 5/10 — Analysing prosody")
    prosody_result = analyse_prosody.func(
        audio_path=audio_path, language=language or "en"
    )

    # ── Stage 6: MOS ─────────────────────────────────────────────────────────
    logger.info("Stage 6/10 — Predicting MOS")
    mos_result = predict_mos.func(audio_path=audio_path)

    # ── Stage 7: Entity fidelity ──────────────────────────────────────────────
    logger.info("Stage 7/10 — Checking entity fidelity")
    entity_result = check_entity_fidelity.func(
        expected=expected_script,
        transcript=transcript_text,
    )

    # ── Stage 7.5: Name fidelity ─────────────────────────────────────────────
    logger.info("Stage 7.5/10 — Checking name fidelity")
    name_result = check_name_fidelity.func(
        expected=expected_script,
        transcript=transcript_text,
    )

    # ── Stage 8: Faithfulness ─────────────────────────────────────────────────
    logger.info("Stage 8/10 — Checking faithfulness")
    faithfulness_result = check_faithfulness.func(
        expected=expected_script,
        transcript=transcript_text,
    )

    # ── Stage 9: QA report + verdict ─────────────────────────────────────────
    logger.info("Stage 9/10 — Generating QA report")
    analysis_data = {
        "audio_name": audio_name,
        "transcript": transcript_text,
        "transcript_confidence": transcript_confidence,
        "alignment": alignment,
        "pause_naturalness": pause_naturalness,
        "speaking_rate": speaking_rate_result,
        "accuracy": diff,
        "artifacts": artifact_result,
        "pauses": pause_result,
        "prosody": prosody_result,
        "mos": mos_result,
        "entity_fidelity": entity_result,
        "name_fidelity": name_result,
        "faithfulness": faithfulness_result,
    }
    report = generate_qa_report.func(analysis_data=analysis_data)
    weighted_score = compute_weighted_score(
        _build_scoring_metrics(
            pause_result=pause_result,
            speaking_rate_result=speaking_rate_result,
            prosody_result=prosody_result,
            mos_result=mos_result,
            name_result=name_result,
            faithfulness_result=faithfulness_result,
        )
    )
    report["score_breakdown"] = weighted_score["score_breakdown"]
    report_score = report.get("score")
    report_score = (
        int(report_score)
        if isinstance(report_score, (int, float))
        else weighted_score["score"]
    )
    report["score"] = min(
        report_score,
        weighted_score["score"],
    )
    report["verdict"] = _more_severe_verdict(
        report.get("verdict"), weighted_score["verdict"]
    )

    # ── Stage 10: Persist ─────────────────────────────────────────────────────
    logger.info("Stage 10/10 — Saving to database")
    saved = save_report.func(
        audio_name=audio_name,
        expected=expected_script,
        transcript=transcript_text,
        wer=diff.get("wer", 0.0),
        score=report["score"],
        verdict=report["verdict"],
        failures=report["failures"],
        suggestions=report["suggestions"],
        full_report=report["report_text"],
        transcript_confidence=transcript_confidence,
        prosody_score=prosody_result.get("prosody_score"),
        f0_mean=prosody_result.get("f0_mean"),
        jitter=prosody_result.get("jitter"),
        shimmer=prosody_result.get("shimmer"),
        hnr=prosody_result.get("hnr"),
        mos_score=mos_result.get("mos_score"),
        entity_fidelity_score=entity_result.get("fidelity_score"),
        name_fidelity_score=name_result.get("name_fidelity_score"),
        faithfulness_score=faithfulness_result.get("faithfulness_score"),
        violations=faithfulness_result.get("violations", []),
    )

    return {
        "report_id": saved["report_id"],
        "audio_name": audio_name,
        "verdict": report["verdict"],
        "failures": report["failures"],
        "score": report["score"],
        "score_breakdown": report.get("score_breakdown", []),
        "transcript": transcript_text,
        "metrics": {
            "accuracy": diff,
            "artifacts": artifact_result,
            "pauses": pause_result,
            "prosody": prosody_result,
            "mos": mos_result,
            "alignment": alignment,
            "pause_naturalness": pause_naturalness,
            "speaking_rate": speaking_rate_result,
            "entity_fidelity": entity_result,
            "name_fidelity": name_result,
            "faithfulness": faithfulness_result,
        },
        "flagged_regions": _collect_flagged_regions(
            pause_result, speaking_rate_result, prosody_result
        ),
        "suggestions": report["suggestions"],
        "report_text": report["report_text"],
    }


def _collect_flagged_regions(
    pause_result: dict,
    speaking_rate_result: dict,
    prosody_result: dict,
) -> List[Dict[str, Any]]:
    """Collect flagged_regions from all metric outputs."""
    regions: List[Dict[str, Any]] = []

    for r in pause_result.get("flagged_regions") or []:
        if isinstance(r, dict):
            regions.append(r)

    for r in speaking_rate_result.get("flagged_regions") or []:
        if isinstance(r, dict):
            regions.append(r)

    for r in prosody_result.get("flagged_regions") or []:
        if isinstance(r, dict):
            regions.append(r)

    return regions


def _low_confidence_result(
    audio_name: str,
    expected_script: str,
    transcription: dict,
) -> dict:
    """Return a minimal result when Whisper transcript confidence is too low."""
    saved = save_report.func(
        audio_name=audio_name,
        expected=expected_script,
        transcript=transcription.get("transcript", ""),
        wer=None,
        score=0,
        verdict="LOW_CONFIDENCE",
        failures=[
            "Whisper transcript confidence too low — audio may be silent or corrupted"
        ],
        suggestions=["Check audio file is valid and contains speech"],
        full_report="Transcript confidence too low — analysis aborted.",
        transcript_confidence="low",
    )
    return {
        "report_id": saved["report_id"],
        "audio_name": audio_name,
        "verdict": "LOW_CONFIDENCE",
        "failures": ["Whisper transcript confidence too low"],
        "score": 0,
        "transcript": transcription.get("transcript", ""),
        "metrics": {},
        "flagged_regions": [],
        "score_breakdown": [],
        "suggestions": ["Check audio file is valid and contains speech"],
        "report_text": "Transcript confidence too low — analysis aborted.",
    }


def _more_severe_verdict(left: str | None, right: str | None) -> str:
    order = {"FAIL": 0, "REVIEW": 1, "LOW_CONFIDENCE": 2, "PASS": 3}
    left = left or "FAIL"
    right = right or "FAIL"
    return left if order.get(left, 0) <= order.get(right, 0) else right


def _max_severity(items: list[dict], default: str = "ok") -> str:
    order = {"ok": 0, "info": 0, "warn": 1, "fail": 2}
    max_seen = default
    for item in items:
        if not isinstance(item, dict):
            continue
        severity = item.get("severity") or item.get("level") or default
        if order.get(severity, 0) > order.get(max_seen, 0):
            max_seen = severity
    return max_seen


def _build_scoring_metrics(
    pause_result: dict,
    speaking_rate_result: dict,
    prosody_result: dict,
    mos_result: dict,
    name_result: dict,
    faithfulness_result: dict,
) -> Dict[str, Dict[str, Any]]:
    metrics: Dict[str, Dict[str, Any]] = {}

    pause_regions = [
        r
        for r in (pause_result.get("flagged_regions") or [])
        if isinstance(r, dict) and r.get("check") == "pause_detection"
    ]
    pause_severity = _max_severity(pause_regions)
    if pause_severity != "ok":
        metrics["unnatural_pause"] = {"severity": pause_severity}

    filled_regions = [
        r
        for r in (pause_result.get("flagged_regions") or [])
        if isinstance(r, dict) and r.get("check") == "filled_pause"
    ]
    filled_severity = _max_severity(filled_regions)
    if filled_severity != "ok":
        metrics["filled_pause"] = {"severity": filled_severity}

    rate_severity = _max_severity(speaking_rate_result.get("segments") or [])
    if rate_severity != "ok":
        metrics["speaking_rate_out_of_range"] = {"severity": rate_severity}

    monotone_severity = prosody_result.get("monotone_severity")
    if monotone_severity in {"warn", "fail"}:
        metrics["pitch_monotone"] = {"severity": monotone_severity}

    mos_score = mos_result.get("mos_score") if isinstance(mos_result, dict) else None
    if isinstance(mos_score, (int, float)) and mos_score < 3.0:
        metrics["mos"] = {"severity": "fail" if mos_score < 2.5 else "warn"}

    if len((name_result or {}).get("mismatches") or []) > 0:
        metrics["name_fidelity_fail"] = {"severity": "fail"}

    if len((faithfulness_result or {}).get("violations") or []) > 0:
        metrics["faithfulness_warn"] = {"severity": "warn"}

    return metrics
