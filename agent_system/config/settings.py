from __future__ import annotations
import os
from typing import Any, Dict, Optional
from dotenv import load_dotenv

# Load environment variables from .env file at startup
load_dotenv()


class Settings:
    """Central configuration and environment settings loader."""

    @staticmethod
    def get_api_key(env_var_name: str) -> Optional[str]:
        """Retrieve API key string from environment."""
        return os.getenv(env_var_name)

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
