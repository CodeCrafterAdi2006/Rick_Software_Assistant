import os
from typing import Optional
from openai import OpenAI

from agent_system.config.settings import Settings
from agent_system.config.models import get_model_config

PERSONA_PROMPT = """You are Rick Sanchez (C-137) from Rick and Morty.
The analysis below was performed by a team of professional multi-agent AI tools.
Your job is to re-express the summary narrative in Rick's signature voice: cynical, brilliant, burping/stuttering occasionally, dismissive of bureaucracy and formality, but NEVER inaccurate.
Do NOT alter any technical facts, issue numbers, file names, line numbers, test counts, or decision outcomes. Keep all structured headings intact."""


def apply_persona(text: str) -> str:
    """Wrap agent output narrative in Rick Sanchez's voice if PERSONA_ENABLED=true per engineering.md §11."""
    if not Settings.is_persona_enabled():
        return text

    try:
        config = get_model_config("lightweight")
        api_key_env = config["api_key_env"]
        api_key = Settings.get_api_key(api_key_env)
        if not api_key:
            return text

        client = OpenAI(
            base_url=config["base_url"],
            api_key=api_key,
        )

        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": PERSONA_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.7,
            max_tokens=500,
        )

        decorated = response.choices[0].message.content
        return decorated.strip() if decorated else text
    except Exception as e:
        # Graceful fallback: return original text if LLM call fails
        return text
