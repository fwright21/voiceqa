# VoiceQA — Hallucination detection for voice agents

**The independent audit layer for your STT, TTS, and full-duplex pipeline.**

Voice agents fabricate content at every layer — and most teams only check one:

- **STT (Whisper, Deepgram, AssemblyAI, …):** invents words during silence, substitutes rare/domain words with common phonetic neighbors (`metoprolol` → `metoprolole`, `apuntado` → `atontado`). Worse in non-English and accented audio.
- **TTS (ElevenLabs, Cartesia, Play.ht, OpenAI TTS, …):** mispronounces medication names, drops syllables, garbles numbers. Pipeline logs show correct text was generated; audio rendered something different.
- **Full-duplex models (Claude voice, ChatGPT voice, Gemini Live):** hallucinate conversational content with no separate STT/TTS boundary to instrument.

VoiceQA is the **independent witness**. It doesn't trust any vendor in your pipeline — it re-derives signal from the audio itself. In healthcare, finance, insurance, and legal voice agents, "approximately right" is a compliance violation, and vendor confidence scores are biased toward saying the vendor was right.

## Mental model

VoiceQA is the audit layer between your voice pipeline and production:
1. Provide **audio** (+ optional **expected script**)
2. Run layered, deterministic checks — VoiceQA acts as an independent witness, not a vendor self-report
3. Return a structured verdict: `PASS | REVIEW | FAIL | LOW_CONFIDENCE`
4. Save reports locally and run curated suites to catch regressions over time

## Why this is different

VoiceQA is designed to **fail loudly on the things vendors hide**:
- **Vendor-agnostic**: works with any STT (Whisper, Deepgram, …), any TTS (ElevenLabs, Cartesia, …), any full-duplex model — VoiceQA never trusts the vendor under test
- **Deterministic-first**: entities/vitals/terms/pauses/artifacts don't depend on an LLM judge
- **Audio-side verification**: forced alignment + phoneme checks re-derive what was actually said, independent of whatever transcript the vendor returned
- **Local-first**: practical for sensitive workflows (use synthetic scripts for public repos; keep audio local)
- **Regression-oriented**: curated suites + baselines, not one-off inspection
- **Graceful degradation**: if Ollama or optional tooling isn't available, the system still runs end-to-end

Transcript accuracy is necessary, not sufficient. VoiceQA is built for the rest.

## What it checks

Accepts an audio file plus the expected script, runs a layered pipeline, and returns a structured quality report:

- **Transcription + confidence gate** (Whisper)
- **Transcript accuracy** — WER/MER/WIL + diff (jiwer)
- **Audio artifacts** — clipping, DC offset, noise, pops/clicks (deterministic)
- **Pauses** — silence gaps with timestamps (deterministic)
- **Pause naturalness** — classify pauses as within‑phrase vs between‑phrase (deterministic)
- **Speaking rate (beta)** — per-segment speed checks; current too-fast/too-slow thresholds are intentionally conservative and should be recalibrated per voice/domain
- **Prosody** — F0 mean, jitter, shimmer, HNR (Praat/Parselmouth; graceful skip)
- **MOS prediction** — DNSMOS via SpeechMOS (graceful skip)
- **Entity fidelity** — numbers/codes/dates mismatches (deterministic)
- **Vitals fidelity** — BP / SpO2 / temperature parsing + comparison (deterministic, suite-only)
- **Term fidelity** — “must preserve” symptom/medication words with criticality weights (suite-only)
- **Name fidelity** — proper noun/name mismatches (conservative extraction + fuzzy match)
- **Faithfulness (optional)** — semantic-only LLM-as-judge (Ollama; advisory; low confidence)
- **History** — local SQLite (`voiceqa.db`)

## Design principles

- **Deterministic first.** High-signal checks (entities, vitals, audio artifacts) should not depend on an LLM.
- **LLM-as-judge is advisory.** Faithfulness is low-confidence by default and should not be the only safety gate.
- **Curated eval > random corpora.** Suite manifests are committed; audio is local. You iterate on *your* failure modes.
- **No PHI in public.** Use synthetic scripts and voices for open-source eval sets.

## Who this is for

- Teams building voice agents in **regulated industries** — healthcare, finance, insurance, legal, collections — where a hallucinated medication, dosage, or disclosure is a compliance violation, not a UX bug
- Teams shipping **multilingual voice agents** where STT phonetic substitution gets worse on non-English audio
- Teams using **full-duplex voice models** (Claude voice, ChatGPT voice) and finding existing eval tools have no answer
- Builders who need **repeatable, local/private** evaluation workflows without sending audio to a third-party cloud

## Stack

Python 3.11, FastAPI, LangChain, Whisper, Ollama, scipy, soundfile, jiwer, praat-parselmouth, SpeechMOS, SQLite

## Quick demo (recommended)

Run the UI and try an eval suite:
- `symptom-triage` — “should pass” baseline suite (terms + vitals)
- `hallucination-demo` — intentional additions/omissions/contradictions (uses `audio_script`)
- `prosody-demo` — deterministic weird pauses/pacing (uses `postprocess`)

## Setup

1. Create/activate a Python 3.11 venv (example: `source ~/venvs/voiceqa/bin/activate`)
2. `pip install -r requirements.txt`
3. Optional (recommended): install and run Ollama
   - `brew install ollama`
   - `ollama serve`
   - `ollama pull phi3.5`
   - `ollama pull llama3.2`
4. `cp .env.example .env` (or edit `.env` directly)
5. Run the API: `uvicorn main:app --reload --port 8000`

## Quickstart (UI)

```bash
source ~/venvs/voiceqa/bin/activate
uvicorn main:app --reload --port 8000
```

Open `http://127.0.0.1:8000/ui`.

## Curated eval suites (recommended)

Suites live in `eval_set/suites/<suite_id>/manifest.jsonl`.

Typical workflow:
1. Put scripts (and expected terms) in the manifest (committed)
2. Generate local TTS WAVs (not committed) or record real audio samples
3. Run the suite from the UI or `/eval/run`
4. Inspect flagged clips (audio playback + jump-to flags + JSON) and iterate

For local regression tracking, you can save a suite baseline from the UI and compare future runs.
Baselines are stored as `eval_set/suites/<suite_id>/baseline.local.json` and are gitignored.

### Demo: generate a suite with ElevenLabs

This is the fastest way to get a realistic eval loop without committing audio.

```bash
source ~/venvs/voiceqa/bin/activate
export ELEVENLABS_API_KEY="..."        # do not commit
export ELEVENLABS_VOICE_ID="..."       # see generator output for options
python tools/generate_eval_audio_elevenlabs.py --suite symptom-triage
```

Then run `symptom-triage` from `http://127.0.0.1:8000/ui`.

## Endpoints

- `GET /health`
- `GET /ui` — web UI
- `POST /analyse` — analyse one audio file
- `POST /analyse/batch` — analyse many audio files in one request (paired `audio_files[i]` + `expected_scripts[i]`)
- `GET /eval/suites` — list available eval suites from `eval_set/suites/`
- `POST /eval/run` — run an eval suite (server-side, on local audio files)
- `GET /eval/audio/{suite_id}/{path}` — serve eval audio clips to the UI
- `POST /eval/baseline/save` — save a local baseline snapshot
- `POST /eval/baseline/compare` — compare current run to baseline

## Usage

Single file:

```bash
curl -X POST http://localhost:8000/analyse \
  -F "audio=@your_tts_output.wav" \
  -F "expected_script=Your expected script here"
```

Batch:

```bash
curl -X POST http://localhost:8000/analyse/batch \
  -F "audio_files=@audio1.wav" -F "audio_files=@audio2.wav" \
  -F "expected_scripts=Expected for audio 1" -F "expected_scripts=Expected for audio 2"
```

## Recommended models

- Transcription: Whisper `small` (default) or `large-v3` for better accuracy (slower)
- QA report + faithfulness: `phi3.5` / `llama3.2` via Ollama (see `.env`)

## Notes for healthcare

- Use **synthetic test scripts** in public repos (no PHI).
- Treat `expected_terms` (rare symptoms + medication names) as “must preserve” and curate them into suites (supports `criticality`).
- Vitals are checked deterministically so “one eighty over one ten” still matches `180/110`.

## Screenshots

The UI is intentionally lightweight and local. If you publish this repo, add a screenshot/GIF of:
- an eval suite run showing per-case audio playback + jump-to flags
- a `hallucination-demo` case being flagged
- a `prosody-demo` case being flagged

## Tests

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests -v
```
