# Roadmap

This is an intentionally pragmatic roadmap for VoiceQA: prioritize **deterministic** safety checks and a tight eval loop.

_Full specs: `plans/replanning-specs.md` · `plans/hallucination-specs.md`_
_Demo: 2026-05-15 (Barcelona AI / Happy Operators)_
_Collaboration: Rhesis AI integration (post-demo)_

## Demo build (ship by May 15)

- **Weighted scoring rubric** (Spec 01):
  - Replace binary pass/fail with 0–100 score (severity × weight per check)
  - Prosodic metrics can only push to REVIEW — never to FAIL
  - Only deterministic checks (missing term, vitals, wrong language) can produce FAIL

- **Phrase-aware pause detection** (Spec 02):
  - Classify pauses as natural (between phrases) vs unnatural (mid-phrase)
  - **Filled pause detection** (`um`, `uh`, `este`, `mmm`) — configurable as defect or acceptable depending on voice style
  - Expose timestamps for UI playback

- **Speaking rate per segment** (Spec 03):
  - WPM per phrase span (EN only for demo; SPS for ES added later)
  - Tighter limits for `red_flag` and `meds` tagged segments

- **Pitch monotone detection** (Spec 04 — partial):
  - F0 standard deviation — flags flat/robotic delivery
  - Full contour + intonation checks deferred to post-demo

- **Jump-to-flagged-region in UI** (Spec 05):
  - Flagged metrics with timestamps → clickable markers that seek the audio player

## Post-demo: advanced detection

- **Emotion detection** (Spec 06):
  - emotion2vec (free, local) — classify emotional tone per segment
  - Compare against expected emotion tag in suite config

- **Pronunciation / phoneme alignment** (Spec 08):
  - epitran (G2P) + Montreal Forced Aligner → Phoneme Error Rate per word
  - Catches mispronunciation invisible to transcript (Whisper transcribes correctly even when pronunciation is wrong)

- **Naturalness MOS** (Spec 07):
  - Fix UTMOS version pin (trained on TTS naturalness, not telephony like DNSMOS)
  - Or fine-tune wav2vec2 on ~200 annotated samples

- Deterministic **negation/polarity** checks for red-flag questions (e.g., "denies chest pain" meaning flips)
- Deterministic **dosage/frequency** parsing (e.g., "500 mg twice daily for 7 days") similar to `vitals_fidelity`
- Faster eval runs:
  - configurable Whisper model per suite (tiny/base for quick regressions)
  - optional skipping of expensive metrics in suites (prosody/MOS)

## Post-demo: multi-turn

- **Multi-turn conversation analysis** (Spec 09):
  - New `conversation.yaml` suite format for ordered turn sequences
  - Inter-turn latency checks (agent response gap)
  - Topic coherence per turn (LLM-assisted, Groq)
  - Prior-turn reference check (did agent acknowledge the user?)

- **Latency tracking** (Spec 10):
  - Per-turn latency from audio files (Phase 1)
  - Live API measurement: TTFB + total response time (Phase 2)

- **Pragmatic coherence** (Spec 11):
  - Structured 5-question rubric per agent turn (LLM judge via Groq)
  - Does agent acknowledge user? Answer the question? Address emotion? Consistent formality?

## Post-demo: i18n

- **EN/ES language support** (Spec 12):
  - Fix Unicode tokenizer (`alignment.py` drops accented characters)
  - Spanish title/stopword lists, per-language WPM→SPS, language in LLM prompts
  - Code-switching detection (English words in Spanish transcripts, via `lingua`)

- **Cultural/regional appropriateness** (Spec 13):
  - Formality detection (tú vs usted)
  - Regional vocabulary (coche vs carro vs auto)

- Broader language support beyond EN/ES (tokenization already Unicode-safe after Spec 12)

## Hallucination detection — VoiceQA as independent audit layer

Voice fabrication is not Whisper-specific. It happens at every layer (STT, TTS, full-duplex) and across every vendor (Whisper, Deepgram, ElevenLabs, Cartesia, Play.ht, Claude voice, ChatGPT voice). VoiceQA's role is to act as an independent witness that doesn't trust any vendor's self-report.

Full design: `plans/hallucination-specs.md`. Ship order: **13.5 → 14b → 16 → 14a → 14c → 14d → 15 → 17**.

- **Vendor-agnostic transcript interface** (Spec 13.5 — prerequisite refactor):
  - New `tools/transcript.py` with `Transcript`, `WordSpan`, `SegmentConf` dataclasses + `TranscriberBackend` protocol
  - Wrap existing `transcribe_audio.py` as `WhisperBackend`; ship `UserProvidedBackend` so VoiceQA can audit vendor STT output without re-transcribing
  - Distinguishes `transcript_under_test` (the system being audited) from `audit_transcript` (VoiceQA's independent witness)
  - All downstream checks consume the interface — graceful degradation when a backend doesn't expose confidence

- **STT fabrication & substitution detection** (Spec 14, split):
  - **14a — Silence fabrication:** word timestamps cross-referenced with per-frame RMS; words in silent regions → fabricated
  - **14b — Phonetic substitution (highest-value):** force-align the *transcript* (not the expected script) to audio via MMS_FA; low per-word alignment confidence = audio phonemes don't match transcribed word (catches "apuntado" → "atontado", "metoprolol" → "metoprolole" — happens with any STT, any language)
  - **14c — Critical-term phonetic neighbor:** G2P + phoneme Levenshtein from each transcript word to suite's critical terms; near-misses are always FAIL (cheap, deterministic)
  - **14d — Independent phoneme verification:** wav2vec2-phoneme on audio, compare to G2P(transcript); the only audio-side check that works without a reference script — enables Spec 17

- **TTS output fidelity** (Spec 16):
  - Re-transcribe TTS-rendered audio (any vendor) → WER against reference; flag high-severity mismatches on numbers, proper nouns, critical terms
  - Vendor-agnostic by design: audited TTS can be anything, audit transcriber is pluggable
  - UI: mismatched tokens become clickable timestamp markers (extends Spec 05)

- **Per-segment confidence propagation** (Spec 15):
  - Mark `Transcript.segments` with `confidence < 0.6` or `no_speech_prob > 0.6` as low-confidence
  - Entity/vitals/term fidelity checks downgrade `fail` → `warn` when the flagged token overlaps a low-confidence segment — prevents false FAILs from bad STT segments
  - Skips gracefully when a backend exposes no confidence at all (vendor-agnostic)

- **Full-duplex model auditing** (Spec 17):
  - For Claude voice / ChatGPT voice / Gemini Live etc., where there's no separate STT/TTS to instrument
  - Independently transcribe `audio_in` and `audio_out` with an audit backend; apply Specs 14/16 to both sides
  - Optional multi-witness consensus: run two different audit backends, disagreements = high-suspicion
  - New suite mode `full_duplex` with paired input/output audio
  - Composes everything above — ships last

## Long-term

- Pluggable ASR providers (beyond Whisper) for speed/cost tradeoffs
- Stronger faithfulness checks with calibration against human review
- CI recipe (GitHub Actions) with synthetic suites and deterministic gates
- **Rhesis AI integration**: VoiceQA as a metric provider in Rhesis's testing platform

## External resources to revisit

- **VoiceMOS Challenge 2026** — https://sites.google.com/view/voicemos-challenge/voicemos-challenge-2026
  Results + datasets released ~September 2026. Tracks 2 (emotional TTS) and 3 (accented codec synthesis) are directly relevant.
  Once complete: evaluate whether trained models can replace or improve DNSMOS/SpeechMOS in VoiceQA's MOS prediction layer.
