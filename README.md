# VoiceQA

Voice Agent Quality Assurance — evaluate the spoken output quality of TTS/voice agents.

## What it does

Accepts an audio file and expected script, runs a 6-stage analysis pipeline, and returns a structured quality report covering:

- **Transcript accuracy** — WER, MER, word-level diff (Whisper + jiwer)
- **Pause detection** — unnatural silences with timestamps (librosa)
- **Audio artifacts** — clipping, DC offset, noise, pops/clicks (librosa/scipy)
- **QA report** — score 0-100 + suggestions (Ollama, local LLM)
- **History** — all reports saved to SQLite

## Stack

Python 3.11, FastAPI, LangChain, Whisper, Ollama, librosa, scipy, jiwer, SQLite

## Setup

1. Create venv with Python 3.11
2. pip install -r requirements.txt
3. Install Ollama: brew install ollama && ollama serve && ollama pull phi3.5
4. cp .env.example .env
5. uvicorn main:app --reload --port 8000

## Usage

curl -X POST http://localhost:8000/analyse \
  -F "audio=@your_tts_output.wav" \
  -F "expected_script=Your expected script here"

## Recommended models

- Transcription: Whisper small (default) or large-v3 for better accuracy
- LLM report: phi3.5 via Ollama (best local quality/size tradeoff)
