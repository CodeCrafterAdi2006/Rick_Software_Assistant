import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from agent_system.cli import load_issue_payload, run_pipeline
from agent_system.schemas.state import IssuePayload, TriageResult


def test_load_issue_payload(tmp_path):
    issue_file = tmp_path / "test_issue.json"
    issue_data = {
        "id": 99,
        "title": "Test Issue",
        "body": "Test issue body content",
        "labels": ["bug"],
        "author": "test_user",
    }
    issue_file.write_text(json.dumps(issue_data), encoding="utf-8")

    payload = load_issue_payload(issue_file)
    assert payload.id == 99
    assert payload.title == "Test Issue"
    assert payload.labels == ["bug"]


def test_load_nonexistent_issue_raises():
    with pytest.raises(FileNotFoundError, match="Issue file not found"):
        load_issue_payload("nonexistent_issue.json")


def test_orchestrator_triage_success(monkeypatch):
    """Test successful LLM triage execution."""
    monkeypatch.setenv("GROQ_API_KEY", "mock_groq_key_123")

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps(
                    {
                        "classification": "BUG",
                        "confidence": 0.93,
                        "routing_note": "Issue describes unexpected empty list behavior when using lowercase string.",
                    }
                )
            )
        )
    ]

    from agent_system.schemas.state import RootCauseReport, RequirementsSpec, PatchResult, TestResult, ReviewResult, DocUpdates

    def mock_bug(self, st):
        st.root_cause_report = RootCauseReport(file="core.py", line_range=(1, 1), hypothesis="h", grep_evidence=[])

    def mock_req(self, st):
        st.requirements_spec = RequirementsSpec(scope="s", acceptance_criteria=["c"], target_files=["core.py"])

    def mock_loop(st, session_id):
        st.patch = PatchResult(diff="d", changed_files=["core.py"], explanation="e")
        st.test_result = TestResult(status="PASS", passed=1, failed=0, tracebacks=[])
        st.review_result = ReviewResult(decision="APPROVED", linter_output=[], critique="LGTM")
        return st

    def mock_doc(self, st, session_id="session_default"):
        st.doc_updates = DocUpdates(docstring_diffs=["+ d"], readme_diff=None, changelog_entry="- Fixed")

    monkeypatch.setattr("agent_system.agents.bug_investigation.BugInvestigationAgent.analyze", mock_bug)
    monkeypatch.setattr("agent_system.agents.requirements_analysis.RequirementsAnalysisAgent.analyze", mock_req)
    monkeypatch.setattr("agent_system.cli.run_reflection_loop", mock_loop)
    monkeypatch.setattr("agent_system.agents.documentation_writer.DocumentationWriterAgent.write_documentation", mock_doc)

    with patch("agent_system.agents.orchestrator.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response

        state = run_pipeline("issues/bug_42.json")
        assert state.issue.id == 42
        assert state.status == "READY"
        assert state.triage_result is not None
        assert state.triage_result.classification == "BUG"
        assert state.triage_result.confidence == 0.93


def test_orchestrator_missing_api_key(monkeypatch):
    """Test CONFIG_ERROR when GROQ_API_KEY environment variable is missing."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    state = run_pipeline("issues/bug_42.json")
    assert state.status == "ERROR"
    assert state.triage_result is None


def test_orchestrator_api_non_retryable_failure(monkeypatch):
    """Test non-retryable 401 invalid key failure failing immediately."""
    monkeypatch.setenv("GROQ_API_KEY", "invalid_key_123")

    with patch("agent_system.agents.orchestrator.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = RuntimeError("Error code: 401 - Invalid API Key")

        state = run_pipeline("issues/bug_42.json")
        assert state.status == "ERROR"
        assert state.triage_result is None
        assert mock_client.chat.completions.create.call_count == 1


def test_orchestrator_retry_recovery(monkeypatch):
    """Test retry policy recovering cleanly after 2 transient 429 rate limits."""
    monkeypatch.setenv("GROQ_API_KEY", "mock_groq_key_123")

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps(
                    {
                        "classification": "BUG",
                        "confidence": 0.95,
                        "routing_note": "Recovered on 3rd attempt after transient rate limiting.",
                    }
                )
            )
        )
    ]

    from agent_system.schemas.state import RootCauseReport, RequirementsSpec, PatchResult, TestResult, ReviewResult, DocUpdates

    def mock_bug(self, st):
        st.root_cause_report = RootCauseReport(file="core.py", line_range=(1, 1), hypothesis="h", grep_evidence=[])

    def mock_req(self, st):
        st.requirements_spec = RequirementsSpec(scope="s", acceptance_criteria=["c"], target_files=["core.py"])

    def mock_loop(st, session_id):
        st.patch = PatchResult(diff="d", changed_files=["core.py"], explanation="e")
        st.test_result = TestResult(status="PASS", passed=1, failed=0, tracebacks=[])
        st.review_result = ReviewResult(decision="APPROVED", linter_output=[], critique="LGTM")
        return st

    def mock_doc(self, st, session_id="session_default"):
        st.doc_updates = DocUpdates(docstring_diffs=["+ d"], readme_diff=None, changelog_entry="- Fixed")

    monkeypatch.setattr("agent_system.agents.bug_investigation.BugInvestigationAgent.analyze", mock_bug)
    monkeypatch.setattr("agent_system.agents.requirements_analysis.RequirementsAnalysisAgent.analyze", mock_req)
    monkeypatch.setattr("agent_system.cli.run_reflection_loop", mock_loop)
    monkeypatch.setattr("agent_system.agents.documentation_writer.DocumentationWriterAgent.write_documentation", mock_doc)

    with patch("agent_system.agents.orchestrator.OpenAI") as mock_openai_cls, \
         patch("time.sleep") as mock_sleep:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        # Fail twice with 429 rate limit, succeed on 3rd attempt
        mock_client.chat.completions.create.side_effect = [
            RuntimeError("Groq API 429 Rate Limit Exceeded"),
            RuntimeError("Groq API 429 Rate Limit Exceeded"),
            mock_response,
        ]

        state = run_pipeline("issues/bug_42.json")
        assert state.status == "READY"
        assert state.triage_result is not None
        assert state.triage_result.classification == "BUG"
        assert mock_client.chat.completions.create.call_count == 3
        assert mock_sleep.call_count == 2


def test_orchestrator_retry_exhaustion(monkeypatch):
    """Test retry policy exhausting all 3 retries on persistent 429 rate limits."""
    monkeypatch.setenv("GROQ_API_KEY", "mock_groq_key_123")

    with patch("agent_system.agents.orchestrator.OpenAI") as mock_openai_cls, \
         patch("time.sleep") as mock_sleep:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = RuntimeError("Groq API 429 Rate Limit Exceeded")

        state = run_pipeline("issues/bug_42.json")
        assert state.status == "ERROR"
        assert state.triage_result is None
        # Initial attempt + 3 retries = 4 calls total
        assert mock_client.chat.completions.create.call_count == 4
        assert mock_sleep.call_count == 3
