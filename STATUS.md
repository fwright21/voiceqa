# voice_qa — Status Log

| Date | Status |
|------|--------|
| 2026-03-08 | Initial pipeline built — 6 stages working end-to-end |
| 2026-03-09 | Tests added |
| 2026-03-26 | EVA comparison, handoff created |
| 2026-03-29 | v2 spec locked. Step 0 done (SpeechMOS confirmed). Steps 1-12 in progress. |
| 2026-04-13 | v2 runs end-to-end (10-stage pipeline + batch endpoint). Audio loading no longer depends on librosa; QA report generation degrades gracefully when Ollama is unavailable; `.env.example` and docs updated. |
| 2026-04-16 | Parallel execution (ProcessPoolExecutor + Groq LLM) to speed up eval runs |
