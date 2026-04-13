# VoiceQA — Alignment-First Eval Plan (Forced Alignment + Prosody)

## Context

VoiceQA currently evaluates scripted audio using:
- ASR transcript + WER-style diffs
- deterministic checks (entities, vitals, expected terms)
- audio quality/prosody metrics
- optional LLM “faithfulness” judging

For *scripted suites* (where we know the intended text), we want to make the core verdict
more **deterministic** and less sensitive to punctuation/casing/formatting by shifting the
primary “did it say the expected thing?” signal from free-form transcription to
**forced-alignment-style** verification + timing-based prosody checks.

This plan keeps the system general-purpose (medical/law/general) by making lexicons optional
and treating domain lists (meds/symptoms/proper nouns) as per-suite configuration.

---

## Goal

Make **alignment + prosody** the default evaluator for scripted suites:

- **PASS/FAIL** should not hinge on punctuation, casing, or number formatting.
- “ASR spelling variance” should become **REVIEW**, not **FAIL**, unless deterministic
  checks confirm a real content error.
- UI should make it easy to listen to the exact flagged region and understand why it was flagged.

LLM judging becomes optional (helpful for borderline REVIEW cases), not the primary oracle.

---

## Current State (already in repo)

- Prosody features exist (pitch/intensity + jitter/shimmer/etc).
- Deterministic fidelity checks exist (entities, vitals, critical terms).
- Suite runner + UI exists, including baseline save/compare primitives.

---

## Design: Alignment Layer (pluggable backends)

### Backend A (ship first): “ASR + alignment timestamps”

Use a backend that returns word timestamps and confidences (e.g., WhisperX-style).

Pros:
- Simple install path vs lexicon-heavy aligners
- Works across domains without custom dictionaries

Cons:
- Still depends on ASR, but verdict becomes more robust via deterministic gates + disagreement handling

### Backend B (optional, higher fidelity): MFA-style forced alignment

Align **expected text** directly to audio (outputs TextGrid), optionally using:
- custom lexicon additions (meds/names)
- G2P for OOV terms

Pros:
- Best fit for “these should pass exactly” suites
- Great for pause placement scoring (word boundaries are more stable)

Cons:
- Heavier dependencies + lexicon management

---

## What Remains (implementation steps)

### 1) Audit current scoring + decide integration points
- Identify where “faithfulness” currently drives FAIL/REVIEW.
- Decide how alignment-derived signals replace/augment those verdict rules.

### 2) Add an `aligner` interface + first backend
Define a small interface:
- input: `audio_path`, `expected_text` (and optional `language`)
- output: word spans (start/end), token text, confidence, plus backend metadata

Ship Backend A first (timestamps).

### 3) Add deterministic pause/rate checks driven by alignment
New metrics (suite-configurable thresholds):
- **pause_outliers**: long silences between aligned words (e.g., >800ms)
- **mid_phrase_pauses**: pauses that occur where expected punctuation does *not*
  suggest a break
- **speaking_rate**: words/sec or syllables proxy; compare vs per-voice baseline

Output should include **timestamps** so UI can jump directly to the region.

### 4) Add “alignment coverage” and “critical term alignment”
- coverage: what % of expected words align above confidence threshold
- critical terms: for each `expected_terms.critical`, confirm aligned presence (or near-miss)

This is how we separate:
- “ASR spelling variance” (REVIEW)
- “spoken content error” (FAIL)

### 5) UI drilldown for REVIEW/FAIL
Per-case view should show:
- audio playback
- expected text vs normalized transcript (if present)
- flagged metrics with **click-to-jump timestamps**
- a short “why flagged” explanation (pause length, missing critical term, vitals mismatch)

### 6) Tests (fast + deterministic)
Add unit tests for:
- pause detection logic given synthetic word spans
- normalization rules (numbers/vitals)
- critical-term matching rules (including alias lists)

Keep any “real aligner integration test” optional/marked slow so CI can run without heavy deps.

### 7) Documentation
Update:
- `README.md` (explain alignment-first scoring and when LLM judge is used)
- `ROADMAP.md` (alignment milestones + lexicon/G2P work)
- `.env.example` if new optional deps/config are introduced

---

## Files to touch (expected)

- `agent.py` (pipeline wiring + new stage hooks)
- `tools/` (aligner backend + pause/rate scorer)
- `ui/` (per-case drilldown with timestamps + audio)
- `tests/` (unit tests for new deterministic scoring)
- `README.md`, `ROADMAP.md` (docs)

