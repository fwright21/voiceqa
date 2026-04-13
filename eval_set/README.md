# eval_set

This folder is a **curated evaluation set** for VoiceQA.

It is intentionally designed for product-grade QA, not leaderboard-style WER:
- scripts represent your real use cases (healthcare-style wording, names, numbers, negations)
- audio clips should reflect production conditions (mic, noise, speed, accents)
- we care about *downstream impact* (entities, meaning, hallucinations, safety), not just WER

## Layout

Each suite lives under `eval_set/suites/<suite_id>/` and contains:

- `manifest.jsonl` — one JSON object per line
- `README.md` (optional) — what this suite is for, how to record/generate audio

`manifest.jsonl` entry schema:

```json
{
  "id": "hc-001-intro",
  "audio_path": "audio/hc-001-intro.wav",
  "expected_script": "Hello, this is Dr. Nguyen calling from St. Mary’s Clinic...",
  "audio_script": "Hello, this is Dr. Nguyen calling from St. Mary’s Clinic...",
  "expected_names": ["Nguyen", "St. Mary’s Clinic"],
  "expected_terms": ["dyspnea", "hemoptysis"],
  "ignore_names": [],
  "ignore_terms": [],
  "notes": "Include a clear proper noun + organization name.",
  "tags": ["healthcare", "names", "intro"]
}
```

Notes:
- `audio_path` is **relative to the suite folder**
- audio files are typically not committed (`.gitignore` ignores `*.wav`); the manifest *is* committed
- `audio_script` is optional and only used by audio generators. It enables synthetic “mismatch” suites
  (e.g., hallucination/contradiction demos) where the audio intentionally differs from `expected_script`.
- `voice_settings` is optional and only used by audio generators. It allows per-case TTS settings
  like speed/stability to create prosody/pacing stress tests.
- `postprocess` is optional and only used by audio generators (or `tools/postprocess_suite_audio.py`).
  It applies deterministic audio mutations (insert silences, time-stretch) so demo suites behave
  consistently even if a TTS provider ignores SSML/punctuation.

## Running a suite

From the repo root:

```bash
source ~/venvs/voiceqa/bin/activate
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uvicorn main:app --reload --port 8000
```

Then use the UI (`http://localhost:8000/ui`) or:

```bash
curl -X POST http://localhost:8000/eval/run \
  -H "Content-Type: application/json" \
  -d '{"suite_id":"healthcare-basic"}'
```

## How to curate (recommended)

Aim for ~50–100 clips per suite:
- 20 “normal” flows that should PASS
- 10 entity-heavy (phone numbers, dates, dosages) that should FAIL if wrong
- 10 name-heavy (patients, clinicians, clinics, medications) that should REVIEW if mismatched
- 10 adversarial (negations, contradictions, hallucinations) to stress faithfulness

## Generating audio via ElevenLabs (recommended)

This repo includes a helper that converts each `expected_script` into a local WAV using
ElevenLabs TTS (PCM 16kHz output wrapped as WAV).

Set env vars:

```bash
export ELEVENLABS_API_KEY="..."
export ELEVENLABS_VOICE_ID="..."   # see docs or run without voice id to list
export ELEVENLABS_MODEL_ID="eleven_multilingual_v2"
```

Generate for a suite:

```bash
source ~/venvs/voiceqa/bin/activate
python tools/generate_eval_audio_elevenlabs.py --suite symptom-triage
```

Notes:
- Audio files are typically not committed (`.gitignore` ignores `*.wav`).
- Use `--dry-run` to preview and `--overwrite` to regenerate.
