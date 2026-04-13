# Roadmap

This is an intentionally pragmatic roadmap for VoiceQA: prioritize **deterministic** safety checks and a tight eval loop.

## Near-term (high ROI)

- Alignment-first scoring for scripted suites:
  - add a pluggable forced-alignment layer (timestamps first; MFA-style optional later)
  - pause/rate checks driven by alignment timestamps with UI jump-to-flagged-region
- Deterministic **negation/polarity** checks for red-flag questions (e.g., “denies chest pain” meaning flips).
- Deterministic **dosage/frequency** parsing (e.g., “500 mg twice daily for 7 days”) similar to `vitals_fidelity`.
- Suite-level **gating rules** by tag (e.g., `red_flag` and `meds` have stricter FAIL criteria than `baseline`).
- Faster eval runs:
  - configurable Whisper model per suite (tiny/base for quick regressions)
  - optional skipping of expensive metrics in suites (prosody/MOS)

## Mid-term

- Better “entity fidelity” for spoken forms (phone numbers, dates spoken as words).
- Optional de-identification / “no persistence” mode for healthcare-adjacent workflows:
  - disable DB writes
  - redact script/transcript before saving
  - retention + deletion controls
- Baseline diffs in UI:
  - show which case IDs changed and why
  - show score deltas and top regressions

## Long-term

- Pluggable ASR providers (beyond Whisper) for speed/cost tradeoffs.
- Stronger faithfulness checks (still advisory) with calibration against human review.
- Continuous integration recipe (GitHub Actions) with small, synthetic suites and deterministic gates.
