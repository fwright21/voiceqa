from __future__ import annotations

import argparse
import json
import os
import sys
import time
import wave
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.eval_runner import load_suite
from tools.audio_postprocess import apply_postprocess_file


ELEVEN_API_BASE = "https://api.elevenlabs.io"


class ElevenLabsError(RuntimeError):
    pass


def _sanitize_voice_settings(voice_settings: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    ElevenLabs validates voice settings server-side. We sanitize a few common fields
    to reduce "400 invalid_voice_settings" errors in demos.

    Notes:
    - `speed` is constrained (per ElevenLabs error messages) to [0.7, 1.2].
    - We only sanitize fields we *know* can break runs; unknown fields are passed through.
    """
    if not isinstance(voice_settings, dict) or not voice_settings:
        return None

    out = dict(voice_settings)
    speed = out.get("speed")
    if isinstance(speed, (int, float)):
        if speed < 0.7:
            out["speed"] = 0.7
        elif speed > 1.2:
            out["speed"] = 1.2

    return out


def _http_json(method: str, url: str, api_key: str, payload: dict | None = None) -> dict:
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = Request(url, method=method.upper(), headers=headers, data=data)
    try:
        with urlopen(req, timeout=60) as resp:
            raw = resp.read()
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise ElevenLabsError(f"HTTP {e.code} {e.reason}: {body[:500]}")
    except URLError as e:
        raise ElevenLabsError(f"Network error: {e}")


def _http_bytes(method: str, url: str, api_key: str, payload: dict) -> bytes:
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, method=method.upper(), headers=headers, data=data)
    try:
        with urlopen(req, timeout=120) as resp:
            return resp.read()
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise ElevenLabsError(f"HTTP {e.code} {e.reason}: {body[:500]}")
    except URLError as e:
        raise ElevenLabsError(f"Network error: {e}")


def write_wav_from_pcm_s16le(pcm: bytes, wav_path: Path, sample_rate: int) -> None:
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(int(sample_rate))
        wf.writeframes(pcm)


def list_voices(api_key: str) -> list[dict]:
    url = f"{ELEVEN_API_BASE}/v1/voices"
    data = _http_json("GET", url, api_key)
    return data.get("voices", []) if isinstance(data, dict) else []


def synthesize_pcm_16000(
    *,
    api_key: str,
    voice_id: str,
    text: str,
    model_id: str,
    seed: Optional[int] = None,
    voice_settings: Optional[Dict[str, Any]] = None,
    pronunciation_dictionary_locators: Optional[list[dict]] = None,
) -> bytes:
    # Uses PCM 16kHz output to produce deterministic WAVs locally.
    url = f"{ELEVEN_API_BASE}/v1/text-to-speech/{voice_id}?output_format=pcm_16000"
    payload: Dict[str, Any] = {
        "text": text,
        "model_id": model_id,
    }
    if seed is not None:
        payload["seed"] = int(seed)
    voice_settings = _sanitize_voice_settings(voice_settings)
    if isinstance(voice_settings, dict) and voice_settings:
        payload["voice_settings"] = voice_settings
    if isinstance(pronunciation_dictionary_locators, list) and pronunciation_dictionary_locators:
        payload["pronunciation_dictionary_locators"] = pronunciation_dictionary_locators
    return _http_bytes("POST", url, api_key, payload)


def _resolve_api_key(cli_value: str | None) -> str:
    if cli_value:
        return cli_value.strip()
    env = os.getenv("ELEVENLABS_API_KEY") or os.getenv("XI_API_KEY")
    if env and env.strip():
        return env.strip()
    raise ElevenLabsError("Missing API key. Set ELEVENLABS_API_KEY (or XI_API_KEY) or pass --api-key.")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Generate eval_set audio WAVs via ElevenLabs from suite manifests.",
    )
    parser.add_argument("--suite", required=True, help="Suite id under eval_set/suites/ (e.g. symptom-triage)")
    parser.add_argument("--api-key", default=None, help="ElevenLabs API key (or set ELEVENLABS_API_KEY)")
    parser.add_argument("--voice-id", default=os.getenv("ELEVENLABS_VOICE_ID"), help="ElevenLabs voice_id to use")
    parser.add_argument("--model-id", default=os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"))
    parser.add_argument("--seed", type=int, default=None, help="Optional deterministic seed")
    parser.add_argument(
        "--voice-settings-json",
        default=os.getenv("ELEVENLABS_VOICE_SETTINGS_JSON"),
        help="Optional JSON object for voice settings (e.g. '{\"stability\":0.3,\"similarity_boost\":0.8,\"style\":0.2,\"speed\":1.05}').",
    )
    parser.add_argument(
        "--pron-dict",
        action="append",
        default=None,
        help="Optional pronunciation dictionary locator JSON (repeatable). Example: '{\"pronunciation_dictionary_id\":\"...\",\"version_id\":\"...\"}'.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing audio files")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without calling the API")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of cases")
    parser.add_argument("--case-id", default=None, help="Only generate a single case id")
    parser.add_argument("--sleep-sec", type=float, default=0.0, help="Sleep between requests (rate limit helper)")
    args = parser.parse_args(argv)

    api_key = _resolve_api_key(args.api_key)

    voice_settings_default: Optional[Dict[str, Any]] = None
    if args.voice_settings_json:
        try:
            voice_settings_default = json.loads(args.voice_settings_json)
            if not isinstance(voice_settings_default, dict):
                raise ValueError("voice settings must be a JSON object")
        except Exception as exc:
            raise ElevenLabsError(f"Invalid --voice-settings-json: {exc}")

    pron_dict_locators: Optional[list[dict]] = None
    if args.pron_dict:
        pron_dict_locators = []
        for raw in args.pron_dict:
            try:
                obj = json.loads(raw)
            except Exception as exc:
                raise ElevenLabsError(f"Invalid --pron-dict JSON: {exc}")
            if not isinstance(obj, dict):
                raise ElevenLabsError("--pron-dict must be a JSON object")
            if not obj.get("pronunciation_dictionary_id"):
                raise ElevenLabsError("--pron-dict missing pronunciation_dictionary_id")
            # version_id is optional; ElevenLabs can use latest in some contexts.
            pron_dict_locators.append(obj)

    if not args.voice_id:
        voices = list_voices(api_key)
        preview = "\n".join([f"- {v.get('name')} ({v.get('voice_id')})" for v in voices[:20]])
        raise ElevenLabsError(
            "Missing --voice-id (or ELEVENLABS_VOICE_ID).\n"
            "Available voices (first 20):\n"
            f"{preview}\n"
        )

    suite_dir, cases = load_suite(args.suite)
    selected = cases
    if args.case_id:
        selected = [c for c in cases if c.case_id == args.case_id]
        if not selected:
            raise ElevenLabsError(f"Unknown case id {args.case_id!r} in suite {args.suite!r}")
    if args.limit is not None:
        selected = selected[: max(0, int(args.limit))]

    generated = 0
    skipped = 0

    for case in selected:
        # audio_path is already resolved absolute by load_suite().
        out_path = case.audio_path

        if out_path.exists() and not args.overwrite:
            skipped += 1
            continue

        if args.dry_run:
            print(f"[dry-run] would generate {case.case_id} -> {out_path}")
            generated += 1
            continue

        # Optional per-case overrides:
        # - audio_script: what to synthesize (defaults to expected_script)
        # - voice_settings: tweak stability/similarity/style/speed to force weird prosody
        per_case_vs = None
        try:
            # EvalCase stores expected_terms as Any; it can also carry custom fields if present.
            # We don't want this to hard-fail if absent.
            per_case_vs = getattr(case, "voice_settings", None)
        except Exception:
            per_case_vs = None

        voice_settings = voice_settings_default
        if isinstance(voice_settings_default, dict) and isinstance(per_case_vs, dict):
            merged = dict(voice_settings_default)
            merged.update(per_case_vs)
            voice_settings = merged
        elif isinstance(per_case_vs, dict):
            voice_settings = per_case_vs

        pcm = synthesize_pcm_16000(
            api_key=api_key,
            voice_id=args.voice_id,
            text=getattr(case, "audio_script", None) or case.expected_script,
            model_id=args.model_id,
            seed=args.seed,
            voice_settings=voice_settings,
            pronunciation_dictionary_locators=pron_dict_locators,
        )
        write_wav_from_pcm_s16le(pcm, out_path, sample_rate=16000)

        # Optional deterministic postprocessing (provider-agnostic):
        # Useful for forcing weird prosody (insert silences, time-stretch) for demos.
        try:
            pp = getattr(case, "postprocess", None)
        except Exception:
            pp = None
        if isinstance(pp, dict) and pp:
            apply_postprocess_file(out_path, pp, overwrite=True)

        generated += 1

        if args.sleep_sec and args.sleep_sec > 0:
            time.sleep(float(args.sleep_sec))

    print(
        json.dumps(
            {
                "suite_id": args.suite,
                "suite_path": str(suite_dir),
                "voice_id": args.voice_id,
                "model_id": args.model_id,
                "generated": generated,
                "skipped": skipped,
            },
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except ElevenLabsError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
