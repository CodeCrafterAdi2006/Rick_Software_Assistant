import pytest
from agent_system.config.models import MODEL_CONFIG, get_model_config
from agent_system.config.settings import Settings


def test_model_config_heavy_and_lightweight():
    heavy = get_model_config("heavy")
    assert heavy["provider"] == "groq"
    assert heavy["model"] == "llama-3.3-70b-versatile"
    assert heavy["api_key_env"] == "GROQ_API_KEY"

    light = get_model_config("lightweight")
    assert light["provider"] == "groq"
    assert light["model"] == "llama-3.1-8b-instant"
    assert light["api_key_env"] == "GROQ_API_KEY"


def test_model_config_unknown_tier():
    with pytest.raises(ValueError, match="Unknown model tier 'nonexistent_tier'"):
        get_model_config("nonexistent_tier")

    with pytest.raises(ValueError, match="Unknown model tier 'nvidia'"):
        get_model_config("nvidia")

    with pytest.raises(ValueError, match="Unknown model tier 'openrouter'"):
        get_model_config("openrouter")


def test_settings_feature_flags(monkeypatch):
    monkeypatch.setenv("PERSONA_ENABLED", "true")
    monkeypatch.setenv("GITHUB_LIVE_MODE", "false")
    
    assert Settings.is_persona_enabled() is True
    assert Settings.is_github_live_mode() is False


def test_settings_retry_policy():
    policy = Settings.get_retry_policy()
    assert policy["max_retries"] == 3
    assert policy["backoff_delays_sec"] == [0.5, 1.0, 2.0]
    assert 429 in policy["retry_on_status_codes"]
