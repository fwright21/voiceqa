# VoiceQA — Full Explainer

## What it is

A local-first QA harness that catches failures **transcript evals alone miss**.

You give it:
- `expected_script` — what the voice agent *should have said*
- `audio file` — what it *actually said*

It returns a structured verdict: `PASS | REVIEW | FAIL | LOW_CONFIDENCE`

---

## Why it exists

A voice agent can pass transcript-based evals and still fail real-world QA:
- A spoken number is wrong (`92%` → `72%`)
- A negation disappears ("denies chest pain" → "chest pain")
- A long pause makes the agent sound broken even when words are correct
- A rare medical term gets swapped for a similar-sounding wrong one

In healthcare (and other high-stakes settings), "approximately right" is still wrong.

---

## 3-Layer Architecture

```
Layer 1 — Deterministic  (always runs, no LLM, high confidence)
Layer 2 — Statistical    (signal processing — Praat, DNSMOS)
Layer 3 — LLM-as-judge   (advisory only, low confidence, Groq)
```

Deterministic checks run first and are never skipped.
LLM judge is advisory — it cannot be the sole safety gate.

---

## Every Metric

### Layer 1 — Deterministic

| Metric | File | What it measures | Why it matters |
|---|---|---|---|
| **WER / MER / WIL** | `diff_transcript.py` | Word Error Rate, Match Error Rate, Word Information Lost | Overall transcript accuracy gate — high WER = garbled audio |
| **Entity fidelity** | `check_entity_fidelity.py` | Number, date, code mismatches between transcript and expected | `92%` → `72%` is a wrong number — regex catches it, no LLM needed |
| **Vitals fidelity** | `check_vitals_fidelity.py` | BP / SpO2 / temperature; handles spoken forms (`one eighty over one ten` → `180/110`) | Suite-only. Wrong vitals = clinical risk |
| **Term fidelity** | `check_term_fidelity.py` | "Must preserve" medical terms with criticality weights (`high/medium/low`) | Suite-curated. Catches `levetiracetam` → `levothyroxine` |
| **Name fidelity** | `check_name_fidelity.py` | Proper nouns / patient names via fuzzy match | Conservative — doesn't over-flag |
| **Audio artifacts** | `detect_audio_artifacts.py` | Clipping, DC offset, noise floor, pops/clicks | Signal-level TTS failures that break trust |
| **Pauses** | `detect_pauses.py` | Silence gap detection with timestamps | Raw input to pause naturalness |
| **Pause naturalness** | `check_pause_naturalness.py` | Within-phrase (bad) vs between-phrase (fine) | A pause mid-sentence sounds broken; a pause between sentences is fine |

### Layer 2 — Statistical

| Metric | File | What it measures | Why it matters |
|---|---|---|---|
| **Prosody** | `analyse_prosody.py` (Praat/Parselmouth) | F0 mean (pitch), jitter (pitch irregularity), shimmer (amplitude irregularity), HNR (harmonics-to-noise ratio) | Catches robotic/unstable voice even when transcript is correct |
| **MOS prediction** | `predict_mos.py` (DNSMOS/SpeechMOS) | Mean Opinion Score — perceptual quality | Predicts whether a human would find the audio intelligible and pleasant |

Both gracefully skip if the dependency isn't installed.

### Layer 3 — LLM-as-judge

| Metric | File | What it measures | Why it matters |
|---|---|---|---|
| **Faithfulness** | `check_faithfulness.py` (Groq `llama-3.1-8b-instant`) | Semantic equivalence — does the audio *mean* the same as expected? | Catches meaning flips that look fine word-by-word: "do not drive" → "you can drive" |

Marked `LOW_CONFIDENCE` in every report.

---

## Pipeline Flow

```
audio + expected_script
  → Whisper transcription + confidence gate
  → WER / transcript diff
  → audio artifact detection
  → pause detection + naturalness
  → prosody (Praat) — graceful skip
  → MOS (DNSMOS) — graceful skip
  → entity fidelity
  → vitals fidelity (suite-only)
  → term fidelity (suite-only)
  → name fidelity
  → faithfulness LLM (Groq, advisory)
  → structured JSON verdict → SQLite (voiceqa.db)
```

---

## Eval Suites

| Suite | Cases | Purpose |
|---|---|---|
| `symptom-triage` | 20 | Baseline pass suite — healthcare triage questions. All should PASS. |
| `hallucination-demo` | 10 | Intentional additions/omissions/contradictions — tests the system catches failures |
| `prosody-demo` | — | Weird pacing/pauses — deterministic audio failure demos |
| `healthcare-basic` | — | Basic healthcare QA |
| `demo-test-suite` | — | General demo |
| `_test-missing-audio` | — | Edge case: what happens when audio file is absent |

---

## Design Principles

- **Deterministic first.** High-signal checks don't depend on an LLM.
- **LLM-as-judge is advisory.** Faithfulness is low-confidence and never the sole gate.
- **Curated eval > random corpora.** Suite manifests are committed; you iterate on *your* failure modes.
- **No PHI in public.** Use synthetic scripts and voices for open-source eval sets.
- **Graceful degradation.** If Praat/SpeechMOS/Ollama isn't available, the system still runs.

---

## Current State (2026-04-16)

- Parallel eval via `ProcessPoolExecutor` (4 workers)
- LLM backend: Groq (`llama-3.1-8b-instant`) — Ollama still installed but not used
- Whisper runs on CPU (~60-80s/file) — still the main bottleneck
- **Open:** eval with Groq + parallel execution hasn't been verified since the switch

## Stack

Python 3.11, FastAPI, LangChain, Whisper, Groq, scipy, soundfile, jiwer, praat-parselmouth, SpeechMOS, SQLite
