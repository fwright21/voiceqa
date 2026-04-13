# hallucination-demo

This suite is designed to produce **intentional mismatches** between:
- `expected_script` (what the agent *should* say)
- `audio_script` (what the audio *actually* says, synthesized)

It’s useful for GitHub screenshots and demos to show VoiceQA catching:
- contradictions (meaning flips)
- additions (“hallucinated” instructions)
- omissions (missing safety instructions)

Notes:
- These cases are expected to come back as `REVIEW` (faithfulness) or `FAIL` (if the mismatch is large).
- To surface semantic “hallucinations” reliably, run Ollama locally so the faithfulness judge can execute.

