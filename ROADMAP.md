# Roadmap

This is an intentionally pragmatic roadmap for VoiceQA: prioritize **deterministic** safety checks and a tight eval loop.

_Full specs: `plans/replanning-specs.md`_
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

## Long-term

- Pluggable ASR providers (beyond Whisper) for speed/cost tradeoffs
- Stronger faithfulness checks with calibration against human review
- CI recipe (GitHub Actions) with synthetic suites and deterministic gates
- **Rhesis AI integration**: VoiceQA as a metric provider in Rhesis's testing platform

## External resources to revisit

- **VoiceMOS Challenge 2026** — https://sites.google.com/view/voicemos-challenge/voicemos-challenge-2026
  Results + datasets released ~September 2026. Tracks 2 (emotional TTS) and 3 (accented codec synthesis) are directly relevant.
  Once complete: evaluate whether trained models can replace or improve DNSMOS/SpeechMOS in VoiceQA's MOS prediction layer.
