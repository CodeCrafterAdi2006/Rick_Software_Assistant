import os
import pytest
from unittest.mock import MagicMock, patch

from agent_system.persona.decorator import apply_persona


def test_persona_disabled_by_default(monkeypatch):
    """Test apply_persona returns original text unchanged when PERSONA_ENABLED is false/unset."""
    monkeypatch.delenv("PERSONA_ENABLED", raising=False)

    text = "HUMAN APPROVAL GATE SUMMARY: Issue #42"
    result = apply_persona(text)
    assert result == text


def test_persona_enabled_transforms_narrative(monkeypatch):
    """Test apply_persona invokes LLM and decorates narrative text when PERSONA_ENABLED=true."""
    monkeypatch.setenv("PERSONA_ENABLED", "true")
    monkeypatch.setenv("GROQ_API_KEY", "mock_groq_key")

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content="Listen Morty, *burp* here is your gate summary for Issue #42!"
            )
        )
    ]

    with patch("agent_system.persona.decorator.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response

        text = "HUMAN APPROVAL GATE SUMMARY: Issue #42"
        result = apply_persona(text)

        assert "Listen Morty" in result
        assert mock_client.chat.completions.create.call_count == 1


def test_persona_resiliency_fallback_on_error(monkeypatch):
    """Test apply_persona catches LLM exceptions gracefully and falls back to original text without crashing."""
    monkeypatch.setenv("PERSONA_ENABLED", "true")
    monkeypatch.setenv("GROQ_API_KEY", "mock_groq_key")

    with patch("agent_system.persona.decorator.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = RuntimeError("API Rate Limit Exceeded")

        text = "HUMAN APPROVAL GATE SUMMARY: Issue #42"
        result = apply_persona(text)

        # Fallback to plain text on error
        assert result == text


def test_persona_preserves_technical_facts(monkeypatch):
    """Test apply_persona preserves key technical facts (Issue #, file paths, test counts, decisions) in decorated output."""
    monkeypatch.setenv("PERSONA_ENABLED", "true")
    monkeypatch.setenv("GROQ_API_KEY", "mock_groq_key")

    decorated_output = (
        "Listen Morty *burp*, Issue #42 is fixed in src/task_tracker/core.py line 67. "
        "All 6 tests passed and Code Review is APPROVED!"
    )
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=decorated_output))]

    with patch("agent_system.persona.decorator.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response

        input_text = "Issue #42: src/task_tracker/core.py (67,67). Passed: 6. Decision: APPROVED"
        result = apply_persona(input_text)

        # Assert technical fact preservation in persona-decorated string
        assert "#42" in result
        assert "src/task_tracker/core.py" in result
        assert "6 tests passed" in result
        assert "APPROVED" in result
