from __future__ import annotations
import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file at startup
load_dotenv()


class Settings:
    """Central configuration and environment settings loader with multi-key pool support."""

    _key_indices: Dict[str, int] = {}

    @classmethod
    def get_api_key(cls, env_var_name: str) -> Optional[str]:
        """Retrieve API key string from environment.
        Supports comma-separated key pools (e.g. 'gsk_key1, gsk_key2, gsk_key3') with round-robin rotation.
        """
        raw = os.getenv(env_var_name)
        if not raw:
            return None

        keys = [k.strip() for k in raw.split(",") if k.strip()]
        if not keys:
            return None
        if len(keys) == 1:
            return keys[0]

        idx = cls._key_indices.get(env_var_name, 0) % len(keys)
        cls._key_indices[env_var_name] = idx + 1
        return keys[idx]

    @classmethod
    def get_all_api_keys(cls, env_var_name: str) -> List[str]:
        """Return list of all configured API keys for a given env var."""
        raw = os.getenv(env_var_name)
        if not raw:
            return []
        return [k.strip() for k in raw.split(",") if k.strip()]

    @staticmethod
    def is_persona_enabled() -> bool:
        """Check if Rick Sanchez persona decorator flag is active."""
        return os.getenv("PERSONA_ENABLED", "false").lower() in ("true", "1", "yes")

    @staticmethod
    def is_github_live_mode() -> bool:
        """Check if live GitHub API mode (T-1/T-5) is active."""
        return os.getenv("GITHUB_LIVE_MODE", "false").lower() in ("true", "1", "yes")

    @staticmethod
    def get_retry_policy() -> Dict[str, Any]:
        """Return standard LLM API retry policy (3 retries, backoff delays)."""
        return {
            "max_retries": 3,
            "backoff_delays_sec": [0.5, 1.0, 2.0],
            "retry_on_status_codes": [429, 500, 502, 503, 504],
        }
