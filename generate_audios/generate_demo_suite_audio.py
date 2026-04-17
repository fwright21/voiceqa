"""
Generate audio for demo-test-suite using ElevenLabs.
"""
import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

API_KEY = os.environ["ELEVENLABS_API_KEY"]
VOICE_ID = os.environ["ELEVENLABS_VOICE_ID"]
MODEL = "eleven_multilingual_v2"
OUT_DIR = Path(__file__).parent.parent / "eval_set/suites/demo-test-suite/audio"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CLIPS = [
    {
        "id": "dt-001-number-flip-spo2",
        "text": "Your oxygen saturation is 72 percent.",
    },
    {
        "id": "dt-002-omission-safety",
        "text": "If none of those are happening, we can continue with a few questions.",
    },
    {
        "id": "dt-003-medication-substitution",
        "text": "Are you taking levothyroxine, also known as Keppra?",
    },
    {
        "id": "dt-004-prosody-pause",
        "text": "Do you have chest pain right now?",
    },
    {
        "id": "dt-005-hyper-hypo",
        "text": "Your reading shows hypotension. We recommend monitoring your blood pressure daily and following up with your doctor.",
    },
]


def generate(clip_id: str, text: str) -> Path:
    out_path = OUT_DIR / f"{clip_id}.wav"
    if out_path.exists():
        print(f"  skip (exists): {out_path.name}")
        return out_path

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {"xi-api-key": API_KEY, "Content-Type": "application/json"}
    payload = {
        "text": text,
        "model_id": MODEL,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    r = requests.post(url, json=payload, headers=headers)
    r.raise_for_status()
    out_path.write_bytes(r.content)
    print(f"  saved: {out_path.name}")
    return out_path


if __name__ == "__main__":
    for clip in CLIPS:
        print(f"Generating {clip['id']}...")
        generate(clip["id"], clip["text"])
        time.sleep(0.5)
    print("Done.")
