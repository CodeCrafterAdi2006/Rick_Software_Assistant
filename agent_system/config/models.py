from __future__ import annotations
from typing import Dict

MODEL_CONFIG: Dict[str, Dict[str, str]] = {
    "heavy": {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
    },
    "lightweight": {
        "provider": "groq",
        "model": "llama-3.1-8b-instant",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
    },
}


def get_model_config(tier: str) -> Dict[str, str]:
    """Retrieve provider and model config dict for a given tier ('heavy' or 'lightweight')."""
    if tier not in MODEL_CONFIG:
        raise ValueError(
            f"Unknown model tier '{tier}'. Supported tiers: {list(MODEL_CONFIG.keys())}"
        )
    return MODEL_CONFIG[tier]
