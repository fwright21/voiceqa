from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_ROOT = REPO_ROOT / "eval_set" / "suites"
BASELINE_FILENAME = "baseline.local.json"

DEFAULT_WEIGHTS = {
    "critical_term_missing": 3.0,
    "vitals_fidelity_fail": 3.0,
    "name_fidelity_fail": 2.0,
    "wrong_language": 2.0,
    "code_switching": 2.0,
    "unnatural_pause": 1.0,
    "speaking_rate_out_of_range": 1.0,
    "pitch_monotone": 0.5,
    "filled_pause": 0.5,
    "faithfulness_warn": 0.5,
    "mos": 0.5,
}

DEFAULT_MAX_VERDICTS = {
    "critical_term_missing": "fail",
    "vitals_fidelity_fail": "fail",
    "name_fidelity_fail": "fail",
    "wrong_language": "fail",
    "code_switching": "fail",
    "unnatural_pause": "review",
    "speaking_rate_out_of_range": "review",
    "pitch_monotone": "review",
    "filled_pause": "review",
    "faithfulness_warn": "review",
    "mos": "review",
}

PROSOCIC_CHECKS = {
    "unnatural_pause",
    "speaking_rate_out_of_range",
    "pitch_monotone",
    "filled_pause",
    "mos",
}

VERDICT_ORDER = {"ok": 0, "warn": 1, "fail": 2, "review": 1, "pass": 3}
SCORE_DEFAULTS = {
    "warn_penalty": 5,
    "fail_penalty": 20,
    "pass_threshold": 90,
    "review_threshold": 70,
}


class EvalError(RuntimeError):
    pass


def compute_weighted_score(
    metrics: Dict[str, Any],
    config: Dict[str, Any] | None = None,
    weights: Dict[str, float] | None = None,
    max_verdicts: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    """Compute weighted score from check results.

    Args:
        metrics: Dict of check_name -> result dicts (each must have 'severity' field)
        config: Optional scoring config (warn_penalty, fail_penalty, verdict_thresholds)
        weights: Override default weights
        max_verdicts: Override max verdicts per check

    Returns:
        Dict with score, verdict, score_breakdown
    """
    score_cfg = config.get("scoring") if isinstance(config, dict) else {}
    warn_penalty = int(score_cfg.get("warn_penalty", SCORE_DEFAULTS["warn_penalty"]))
    fail_penalty = int(score_cfg.get("fail_penalty", SCORE_DEFAULTS["fail_penalty"]))
    pass_thresh = int(
        score_cfg.get("verdict_thresholds", {}).get(
            "pass", SCORE_DEFAULTS["pass_threshold"]
        )
    )
    review_thresh = int(
        score_cfg.get("verdict_thresholds", {}).get(
            "review", SCORE_DEFAULTS["review_threshold"]
        )
    )

    w = weights or DEFAULT_WEIGHTS
    max_v = max_verdicts or DEFAULT_MAX_VERDICTS

    score_breakdown: List[Dict[str, Any]] = []
    base_score = 100.0

    for check_name, result in metrics.items():
        if not isinstance(result, dict):
            continue
        severity = result.get("severity") or result.get("verdict", "ok")
        if severity == "ok" or severity == "info":
            continue

        weight = w.get(check_name, 1.0)
        max_verdict = max_v.get(check_name, "fail")

        cap_severity = severity
        was_capped = False
        if check_name in PROSOCIC_CHECKS and VERDICT_ORDER.get(
            severity, 0
        ) > VERDICT_ORDER.get(max_verdict, 2):
            cap_severity = max_verdict
            was_capped = True

        penalty_for_severity = (
            fail_penalty
            if cap_severity == "fail"
            else warn_penalty
            if cap_severity == "warn"
            else 0
        )

        if was_capped:
            penalty_for_severity = warn_penalty

        if penalty_for_severity == 0:
            continue

        penalty_adj = penalty_for_severity * weight
        base_score += penalty_adj * -1
        score_breakdown.append(
            {
                "check": check_name,
                "severity": cap_severity,
                "weight": weight,
                "penalty": -penalty_for_severity,
                "penalty_weighted": -penalty_adj,
                "capped": was_capped,
            }
        )

    final_score = max(0, int(round(base_score)))

    if final_score >= pass_thresh:
        verdict = "PASS"
    elif final_score >= review_thresh:
        verdict = "REVIEW"
    else:
        verdict = "FAIL"
        if any(m in PROSOCIC_CHECKS for m in metrics):
            has_fail = any(
                VERDICT_ORDER.get(r.get("severity", "ok"), 0) >= VERDICT_ORDER["fail"]
                and m not in PROSOCIC_CHECKS
                for m, r in metrics.items()
                if isinstance(r, dict)
            )
            if not has_fail:
                verdict = "REVIEW"

    return {
        "score": final_score,
        "verdict": verdict,
        "score_breakdown": score_breakdown,
    }


def extract_severity_from_result(result: Dict[str, Any]) -> str:
    """Extract severity from a check result dict."""
    if not isinstance(result, dict):
        return "ok"
    for key in ("severity", "verdict", "level"):
        val = result.get(key)
        if val in ("ok", "warn", "fail", "info", "pass", "review"):
            return val
    if result.get("skipped"):
        return "ok"
    return "ok"


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    audio_path: Path
    expected_script: str
    audio_script: str
    voice_settings: dict | None
    postprocess: dict | None
    expected_names: List[str]
    ignore_names: List[str]
    expected_terms: List[Any]
    ignore_terms: List[str]
    tags: List[str]
    notes: str | None


def list_suites() -> List[dict]:
    suites = []
    if not EVAL_ROOT.exists():
        return suites
    for suite_dir in sorted([p for p in EVAL_ROOT.iterdir() if p.is_dir()]):
        manifest = suite_dir / "manifest.jsonl"
        suites.append(
            {
                "suite_id": suite_dir.name,
                "manifest_exists": manifest.exists(),
                "manifest_path": str(manifest),
            }
        )
    return suites


def load_suite(suite_id: str) -> Tuple[Path, List[EvalCase]]:
    suite_dir = EVAL_ROOT / suite_id
    if not suite_dir.exists():
        raise EvalError(f"Unknown suite_id: {suite_id}")

    manifest_path = suite_dir / "manifest.jsonl"
    if not manifest_path.exists():
        raise EvalError(f"Suite is missing manifest.jsonl: {manifest_path}")

    cases: List[EvalCase] = []
    for i, line in enumerate(
        manifest_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        try:
            obj = json.loads(raw)
        except Exception as exc:
            raise EvalError(f"Invalid JSON on line {i} in {manifest_path}: {exc}")

        case_id = str(obj.get("id") or f"case-{i}")
        audio_rel = obj.get("audio_path")
        if not audio_rel:
            raise EvalError(f"Missing audio_path for case {case_id} (line {i})")
        audio_path = (suite_dir / str(audio_rel)).resolve()

        expected_script = str(obj.get("expected_script") or "").strip()
        if not expected_script:
            raise EvalError(f"Missing expected_script for case {case_id} (line {i})")

        # Optional: allow a separate audio_script for synthetic "mismatch" / hallucination demos.
        # If omitted, audio_script defaults to expected_script.
        audio_script = str(
            obj.get("audio_script") or obj.get("actual_script") or expected_script
        ).strip()
        if not audio_script:
            audio_script = expected_script

        voice_settings = obj.get("voice_settings")
        if voice_settings is not None and not isinstance(voice_settings, dict):
            raise EvalError(
                f"voice_settings must be an object for case {case_id} (line {i})"
            )

        postprocess = obj.get("postprocess")
        if postprocess is not None and not isinstance(postprocess, dict):
            raise EvalError(
                f"postprocess must be an object for case {case_id} (line {i})"
            )

        expected_names = obj.get("expected_names") or []
        ignore_names = obj.get("ignore_names") or []
        expected_terms = obj.get("expected_terms") or []
        ignore_terms = obj.get("ignore_terms") or []
        tags = obj.get("tags") or []
        notes = obj.get("notes")

        cases.append(
            EvalCase(
                case_id=case_id,
                audio_path=audio_path,
                expected_script=expected_script,
                audio_script=audio_script,
                voice_settings=voice_settings,
                postprocess=postprocess,
                expected_names=[str(x) for x in expected_names],
                ignore_names=[str(x) for x in ignore_names],
                expected_terms=expected_terms,
                ignore_terms=[str(x) for x in ignore_terms],
                tags=[str(x) for x in tags],
                notes=str(notes) if notes is not None else None,
            )
        )

    return suite_dir, cases


def summarize_reports(reports: List[Dict[str, Any]]) -> dict:
    counts = {"PASS": 0, "REVIEW": 0, "FAIL": 0, "LOW_CONFIDENCE": 0}
    scores: List[float] = []
    failure_reasons: Dict[str, int] = {}

    for r in reports:
        verdict = r.get("verdict", "FAIL")
        counts[verdict] = counts.get(verdict, 0) + 1

        score = r.get("score")
        if isinstance(score, (int, float)):
            scores.append(float(score))

        for reason in r.get("failures") or []:
            failure_reasons[str(reason)] = failure_reasons.get(str(reason), 0) + 1

    avg_score = round(sum(scores) / len(scores), 2) if scores else None
    top_failures = sorted(failure_reasons.items(), key=lambda kv: (-kv[1], kv[0]))[:10]

    return {
        "total": len(reports),
        "pass": counts.get("PASS", 0),
        "review": counts.get("REVIEW", 0),
        "fail": counts.get("FAIL", 0),
        "low_confidence": counts.get("LOW_CONFIDENCE", 0),
        "avg_score": avg_score,
        "top_failures": [{"reason": r, "count": c} for r, c in top_failures],
    }


def _run_single_case(case: EvalCase, suite_dir: Path) -> Dict[str, Any]:
    from agent import run_analysis
    from tools.check_name_fidelity import check_name_fidelity
    from tools.check_term_fidelity import check_term_fidelity
    from tools.check_vitals_fidelity import check_vitals_fidelity

    if not case.audio_path.exists():
        return {
            "case_id": case.case_id,
            "audio_path": str(case.audio_path),
            "verdict": "FAIL",
            "score": 0,
            "failures": [f"Missing audio file: {case.audio_path}"],
            "error": "missing_audio",
        }

    report = run_analysis(
        audio_path=str(case.audio_path),
        expected_script=case.expected_script,
    )

    if case.expected_names or case.ignore_names:
        transcript = report.get("transcript") or ""
        name_result = check_name_fidelity.func(
            expected=case.expected_script,
            transcript=transcript,
            expected_names=case.expected_names or None,
            ignore_names=case.ignore_names or None,
        )
        metrics = report.get("metrics") or {}
        metrics["name_fidelity"] = name_result
        report["metrics"] = metrics

    if case.expected_terms or case.ignore_terms:
        transcript = report.get("transcript") or ""
        term_result = check_term_fidelity.func(
            transcript=transcript,
            expected_terms=case.expected_terms,
            ignore_terms=case.ignore_terms or None,
        )
        metrics = report.get("metrics") or {}
        metrics["term_fidelity"] = term_result
        report["metrics"] = metrics

    vitals_result = check_vitals_fidelity.func(
        expected=case.expected_script,
        transcript=report.get("transcript") or "",
    )
    if (vitals_result.get("vitals_count") or 0) > 0:
        metrics = report.get("metrics") or {}
        metrics["vitals_fidelity"] = vitals_result
        report["metrics"] = metrics

    report["case_id"] = case.case_id
    report["audio_path"] = str(case.audio_path)
    try:
        report["audio_rel_path"] = str(case.audio_path.relative_to(suite_dir))
    except Exception:
        report["audio_rel_path"] = None
    report["tags"] = case.tags
    report["expected_script"] = case.expected_script
    report["expected_names"] = case.expected_names
    report["ignore_names"] = case.ignore_names
    report["expected_terms"] = case.expected_terms
    report["ignore_terms"] = case.ignore_terms

    report = _apply_eval_overrides(report)
    return report


def run_suite(suite_id: str, max_workers: int | None = None) -> dict:
    """
    Run a suite against the local on-disk audio files.

    Args:
        suite_id: The suite to run
        max_workers: Max parallel workers (default: CPU count)

    Returns: { suite_id, duration_sec, summary, reports }
    """
    from concurrent.futures import ProcessPoolExecutor, as_completed

    suite_dir, cases = load_suite(suite_id)

    started = time.time()
    reports: List[Dict[str, Any]] = []

    if max_workers is None:
        max_workers = 4  # Reduced to avoid memory issues

    try:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_run_single_case, case, suite_dir): case
                for case in cases
            }
            for future in as_completed(futures):
                try:
                    report = future.result()
                    reports.append(report)
                except Exception as exc:
                    case = futures[future]
                    reports.append(
                        {
                            "case_id": case.case_id,
                            "audio_path": str(case.audio_path),
                            "verdict": "FAIL",
                            "score": 0,
                            "failures": [f"Execution error: {exc}"],
                            "error": "execution_error",
                        }
                    )
    except (NotImplementedError, PermissionError, OSError):
        for case in cases:
            try:
                reports.append(_run_single_case(case, suite_dir))
            except Exception as exc:
                reports.append(
                    {
                        "case_id": case.case_id,
                        "audio_path": str(case.audio_path),
                        "verdict": "FAIL",
                        "score": 0,
                        "failures": [f"Execution error: {exc}"],
                        "error": "execution_error",
                    }
                )

    reports.sort(key=lambda r: r.get("case_id", ""))
    duration_sec = round(time.time() - started, 3)
    return {
        "suite_id": suite_id,
        "suite_path": str(suite_dir),
        "duration_sec": duration_sec,
        "summary": summarize_reports(reports),
        "reports": reports,
    }


def compact_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reduce a full analysis report to a UI-friendly payload:
    - keeps audio + scripts + verdict/failures
    - keeps transcript (for quick review)
    - extracts a small set of "highlights" for the main checks
    """
    metrics = report.get("metrics") or {}
    entity = metrics.get("entity_fidelity") or {}
    name_fid = metrics.get("name_fidelity") or {}
    term = metrics.get("term_fidelity") or {}
    vitals = metrics.get("vitals_fidelity") or {}
    faith = metrics.get("faithfulness") or {}
    mos = metrics.get("mos") or {}
    pauses = metrics.get("pauses") or {}
    pause_nat = metrics.get("pause_naturalness") or {}
    speaking_rate = metrics.get("speaking_rate") or {}
    artifacts = metrics.get("artifacts") or {}

    def _mismatch_list(obj: Any, key: str = "mismatches", limit: int = 3) -> list:
        if isinstance(obj, dict) and isinstance(obj.get(key), list):
            return obj.get(key)[:limit]
        return []

    highlights = {
        "wer": (metrics.get("accuracy") or {}).get("wer"),
        "entity_mismatch_count": entity.get("mismatch_count"),
        "entity_mismatches": _mismatch_list(entity),
        "name_mismatch_count": name_fid.get("mismatch_count"),
        "name_mismatches": _mismatch_list(name_fid),
        "term_mismatch_count": term.get("mismatch_count"),
        "term_mismatches": _mismatch_list(term),
        "term_critical_mismatches": (
            term.get("critical_mismatch_count") if isinstance(term, dict) else None
        ),
        "vitals_mismatch_count": vitals.get("mismatch_count"),
        "vitals_mismatches": _mismatch_list(vitals),
        "faithfulness_violation_count": (
            len(faith.get("violations") or []) if isinstance(faith, dict) else None
        ),
        "faithfulness_violations": (faith.get("violations") or [])[:2]
        if isinstance(faith, dict)
        else [],
        "mos_score": mos.get("mos_score"),
        "mos_skipped": mos.get("skipped") if isinstance(mos, dict) else None,
        "mos_error": mos.get("error") if isinstance(mos, dict) else None,
        "longest_pause_sec": pauses.get("longest_pause_sec"),
        "max_within_phrase_gap_sec": pause_nat.get("max_within_phrase_gap_sec")
        if isinstance(pause_nat, dict)
        else None,
        "speaking_rate_wps": pause_nat.get("speaking_rate_wps")
        if isinstance(pause_nat, dict)
        else None,
        "pause_flag_count": (
            len(pause_nat.get("flags") or []) if isinstance(pause_nat, dict) else None
        ),
        "pause_flags": (pause_nat.get("flags") or [])[:3]
        if isinstance(pause_nat, dict)
        else [],
        "speaking_rate_overall": speaking_rate.get("overall_rate")
        if isinstance(speaking_rate, dict)
        else None,
        "speaking_rate_unit": speaking_rate.get("rate_unit")
        if isinstance(speaking_rate, dict)
        else None,
        "artifact_count": artifacts.get("artifact_count"),
    }

    return {
        "suite_id": report.get("suite_id"),
        "case_id": report.get("case_id"),
        "audio_name": report.get("audio_name"),
        "audio_rel_path": report.get("audio_rel_path"),
        "audio_path": report.get("audio_path"),
        "tags": report.get("tags") or [],
        "expected_script": report.get("expected_script"),
        "transcript": report.get("transcript"),
        "verdict": report.get("verdict"),
        "score": report.get("score"),
        "score_breakdown": report.get("score_breakdown") or [],
        "failures": report.get("failures") or [],
        "suggestions": report.get("suggestions") or [],
        "flagged_regions": report.get("flagged_regions") or [],
        "highlights": highlights,
    }


def _baseline_path(suite_id: str) -> Path:
    suite_dir = (EVAL_ROOT / suite_id).resolve()
    return suite_dir / BASELINE_FILENAME


def save_baseline(suite_id: str, baseline: Dict[str, Any]) -> dict:
    """
    Save a baseline snapshot for local regression tracking.
    Baselines are intentionally local-only and ignored by git.
    """
    suite_dir = (EVAL_ROOT / suite_id).resolve()
    if not suite_dir.exists():
        raise EvalError(f"Unknown suite_id: {suite_id}")

    payload = {
        "suite_id": suite_id,
        "saved_at": time.time(),
        "baseline": baseline,
    }
    path = _baseline_path(suite_id)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return {"saved": True, "path": str(path)}


def load_baseline(suite_id: str) -> Dict[str, Any]:
    path = _baseline_path(suite_id)
    if not path.exists():
        raise EvalError(f"No baseline found for suite_id={suite_id}. Expected {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def compare_to_baseline(suite_id: str, current: Dict[str, Any]) -> dict:
    """
    Compare a current eval result against saved baseline.local.json.
    Expects 'baseline' and 'current' to be lightweight objects containing:
      - summary
      - cases: [{case_id, verdict, score, failures}]
    """
    saved = load_baseline(suite_id)
    baseline = saved.get("baseline") or {}

    base_summary = baseline.get("summary") or {}
    cur_summary = current.get("summary") or {}

    def _num(d: dict, k: str) -> float:
        v = d.get(k)
        return float(v) if isinstance(v, (int, float)) else 0.0

    delta = {
        "pass": int(_num(cur_summary, "pass") - _num(base_summary, "pass")),
        "review": int(_num(cur_summary, "review") - _num(base_summary, "review")),
        "fail": int(_num(cur_summary, "fail") - _num(base_summary, "fail")),
        "low_confidence": int(
            _num(cur_summary, "low_confidence") - _num(base_summary, "low_confidence")
        ),
        "avg_score": None,
    }
    if isinstance(cur_summary.get("avg_score"), (int, float)) and isinstance(
        base_summary.get("avg_score"), (int, float)
    ):
        delta["avg_score"] = round(
            float(cur_summary["avg_score"]) - float(base_summary["avg_score"]), 2
        )

    base_cases = {
        c.get("case_id"): c for c in (baseline.get("cases") or []) if c.get("case_id")
    }
    cur_cases = {
        c.get("case_id"): c for c in (current.get("cases") or []) if c.get("case_id")
    }

    changed = []
    for case_id in sorted(set(base_cases.keys()) | set(cur_cases.keys())):
        b = base_cases.get(case_id)
        c = cur_cases.get(case_id)
        if not b or not c:
            changed.append(
                {
                    "case_id": case_id,
                    "baseline": b,
                    "current": c,
                    "change": "added" if c else "removed",
                }
            )
            continue
        if (b.get("verdict") != c.get("verdict")) or (b.get("score") != c.get("score")):
            changed.append(
                {"case_id": case_id, "baseline": b, "current": c, "change": "updated"}
            )

    return {
        "suite_id": suite_id,
        "baseline_path": _baseline_path(suite_id).as_posix(),
        "delta": delta,
        "changed_cases": changed[:50],
    }


def _apply_eval_overrides(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply deterministic, eval-only verdict overrides based on attached suite metrics.

    Rationale: some suite-only checks (term/vitals fidelity) are injected after the main
    QA report is generated; we still want the suite run to reflect those results.
    """
    metrics = report.get("metrics") or {}
    failures = list(report.get("failures") or [])
    suggestions = list(report.get("suggestions") or [])
    score_breakdown = list(report.get("score_breakdown") or [])
    verdict = report.get("verdict") or "FAIL"
    score = report.get("score")

    def _add_suggestion(text: str):
        if not text:
            return
        if text in suggestions:
            return
        suggestions.append(text)

    def _bump_verdict(new_verdict: str):
        nonlocal verdict
        order = {"FAIL": 0, "REVIEW": 1, "LOW_CONFIDENCE": 2, "PASS": 3}
        if order.get(new_verdict, 0) < order.get(verdict, 3):
            verdict = new_verdict

    # Vitals mismatches are safety-critical: force FAIL for suite runs.
    vitals = metrics.get("vitals_fidelity") or {}
    if isinstance(vitals, dict) and (vitals.get("mismatch_count") or 0) > 0:
        failures.append(
            "Vitals mismatch detected (temperature/SpO2/BP differs from expected)"
        )
        _add_suggestion(
            "Fix vitals mismatches: speak values clearly (often digit-by-digit), slow down the vitals phrase, and avoid homophones (e.g. hyper vs hypo). Then rerun and confirm mismatch_count is 0."
        )
        score_breakdown.append(
            {
                "check": "vitals_fidelity_fail",
                "severity": "fail",
                "weight": DEFAULT_WEIGHTS["vitals_fidelity_fail"],
                "penalty": -SCORE_DEFAULTS["fail_penalty"],
                "capped": False,
            }
        )
        _bump_verdict("FAIL")

    # Term mismatches: high => FAIL, otherwise REVIEW.
    term = metrics.get("term_fidelity") or {}
    if isinstance(term, dict) and (term.get("mismatch_count") or 0) > 0:
        crit = term.get("critical_mismatch_count") or {}
        high = int((crit.get("high") or 0)) if isinstance(crit, dict) else 0
        if high > 0:
            # If the best fuzzy ratio is close, treat as REVIEW (often just spelling/ASR variance).
            mismatches = term.get("mismatches") or []
            best_ratios = [
                m.get("best_ratio") for m in mismatches if isinstance(m, dict)
            ]
            min_best = None
            for br in best_ratios:
                if isinstance(br, (int, float)):
                    min_best = br if min_best is None else min(min_best, br)

            if min_best is not None and float(min_best) >= 0.83:
                failures.append(
                    "Critical term near-miss detected (symptom/medication spelling variance — review)"
                )
                _add_suggestion(
                    "For near-miss medication/symptom terms: respell phonetically in the script or use SSML `<phoneme>` if supported; keep the term isolated in its own short phrase."
                )
                score_breakdown.append(
                    {
                        "check": "critical_term_missing",
                        "severity": "warn",
                        "weight": DEFAULT_WEIGHTS["critical_term_missing"],
                        "penalty": -SCORE_DEFAULTS["warn_penalty"],
                        "capped": False,
                    }
                )
                _bump_verdict("REVIEW")
            else:
                failures.append(
                    "Critical term mismatch detected (symptom/medication not preserved)"
                )
                _add_suggestion(
                    "For critical term mismatches: re-generate TTS or adjust pronunciation (phonetic respelling / SSML phoneme). For safety-critical terms, prefer a scripted/templated phrase."
                )
                score_breakdown.append(
                    {
                        "check": "critical_term_missing",
                        "severity": "fail",
                        "weight": DEFAULT_WEIGHTS["critical_term_missing"],
                        "penalty": -SCORE_DEFAULTS["fail_penalty"],
                        "capped": False,
                    }
                )
                _bump_verdict("FAIL")
        else:
            failures.append("Term mismatch detected (symptom/medication not preserved)")
            _add_suggestion(
                "Fix term mismatches: shorten the sentence around the term and reduce expressive settings that can cause word drops; rerun and confirm term mismatches disappear."
            )
            score_breakdown.append(
                {
                    "check": "critical_term_missing",
                    "severity": "warn",
                    "weight": DEFAULT_WEIGHTS["critical_term_missing"],
                    "penalty": -SCORE_DEFAULTS["warn_penalty"],
                    "capped": False,
                }
            )
            _bump_verdict("REVIEW")

    # Update report fields if changed.
    report["verdict"] = verdict
    report["failures"] = failures
    report["suggestions"] = suggestions[:3]
    report["score_breakdown"] = score_breakdown
    if isinstance(score, (int, float)):
        # Light penalty for overrides so they show up in ordering, without rewriting the scoring model.
        if verdict == "FAIL":
            report["score"] = int(max(0, float(score) - 20))
        elif verdict == "REVIEW":
            report["score"] = int(max(0, float(score) - 10))

    # Prosody demo: speaking rate outliers should never PASS silently.
    tags = report.get("tags") or []
    pause_nat = metrics.get("pause_naturalness") or {}
    rate = pause_nat.get("speaking_rate_wps") if isinstance(pause_nat, dict) else None
    if isinstance(rate, (int, float)) and any(
        str(t).lower() in {"prosody", "speed", "pause"} for t in tags
    ):
        r = float(rate)
        if r < 2.4 or r > 4.2:
            failures.append("Speaking rate out of expected range (demo threshold)")
            _add_suggestion(
                "Fix speaking rate: reduce provider speed or wrap the fast segment in SSML `<prosody rate=\"slow\">`, and add short breaks between key phrases."
            )
            score_breakdown.append(
                {
                    "check": "speaking_rate_out_of_range",
                    "severity": "warn",
                    "weight": DEFAULT_WEIGHTS["speaking_rate_out_of_range"],
                    "penalty": -SCORE_DEFAULTS["warn_penalty"],
                    "capped": False,
                }
            )
            _bump_verdict("REVIEW")
            report["failures"] = failures
            report["verdict"] = verdict
            report["suggestions"] = suggestions[:3]
            report["score_breakdown"] = score_breakdown
            if isinstance(report.get("score"), (int, float)):
                report["score"] = int(max(0, float(report["score"]) - 5))

    # Demo showcase: filled pauses should be visible in default "Non-PASS" filtering.
    pauses = metrics.get("pauses") or {}
    filled = pauses.get("filled_pauses") or []
    if any(str(t).lower() in {"filled_pause", "filled_pauses", "filled"} for t in tags) and isinstance(
        filled, list
    ) and len(filled) > 0:
        msg = "Filled pauses detected (demo showcase)"
        if msg not in failures:
            failures.append(msg)
        _add_suggestion(
            "Remove 'um/uh' fillers for formal scripts, or switch to a more conversational style if appropriate. Rerun and confirm filled pauses are gone."
        )
        score_breakdown.append(
            {
                "check": "filled_pause",
                "severity": "warn",
                "weight": DEFAULT_WEIGHTS["filled_pause"],
                "penalty": -SCORE_DEFAULTS["warn_penalty"],
                "capped": False,
            }
        )
        _bump_verdict("REVIEW")
        report["failures"] = failures
        report["verdict"] = verdict
        report["suggestions"] = suggestions[:3]
        report["score_breakdown"] = score_breakdown
        if isinstance(report.get("score"), (int, float)):
            report["score"] = int(max(0, float(report["score"]) - 5))

    return report
