# prosody-demo

This suite is for generating **intentionally weird prosody** (pauses, pacing) from TTS.

It’s meant for screenshots and regression checks of:
- pause detection (energy-based)
- pause naturalness (alignment-based within-phrase gaps)
- MOS/prosody signals

The manifest uses:
- `audio_script` containing SSML tags like `<break time="1.8s" />` (if supported by your TTS model/provider)
- optional per-case `voice_settings` overrides (e.g., `speed`)
- optional `postprocess` mutations (insert silences / time-stretch) so the suite behaves consistently
  even when SSML/punctuation are ignored by the TTS provider.

Expected outcome:
- This suite is intended to produce **non-PASS** results (typically `REVIEW`) so you can screenshot
  “pause naturalness” and “speaking rate” flags in the UI.
