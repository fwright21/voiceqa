"""
Resolves Ollama model names from .env with a fallback chain.
Checks which models are actually installed before returning one.
"""

import os
import subprocess
from dotenv import load_dotenv

load_dotenv()

# Fallback chain — ordered by preference
FALLBACK_CHAIN = ["phi3.5", "llama3.2", "mistral", "qwen2.5:1.5b"]


def _installed_models() -> list[str]:
    """Return list of installed Ollama model names."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = result.stdout.strip().splitlines()[1:]  # skip header
        return [line.split()[0] for line in lines if line.strip()]
    except Exception:
        return []


def get_model(role: str) -> str:
    """
    Return the best available Ollama model for a given role.

    Roles:
        "whisper"       → WHISPER_MODEL env var (not an Ollama model, returned as-is)
        "faithfulness"  → FAITHFULNESS_MODEL env var, then fallback chain
        "report"        → REPORT_MODEL env var, then fallback chain

    Falls back through FALLBACK_CHAIN until an installed model is found.
    Returns the last item in FALLBACK_CHAIN as a last resort (qwen2.5:1.5b).
    """
    if role == "whisper":
        return os.getenv("WHISPER_MODEL", "small")

    env_key = {
        "faithfulness": "FAITHFULNESS_MODEL",
        "report": "REPORT_MODEL",
    }.get(role, "REPORT_MODEL")

    preferred = os.getenv(env_key)
    installed = _installed_models()

    # Try preferred model first, then walk fallback chain
    candidates = ([preferred] if preferred else []) + FALLBACK_CHAIN
    for model in candidates:
        if any(inst.startswith(model) for inst in installed):
            return model

    # Last resort — return final fallback even if not confirmed installed
    return FALLBACK_CHAIN[-1]
