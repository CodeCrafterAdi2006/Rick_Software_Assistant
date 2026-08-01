import pytest
from unittest.mock import MagicMock
from agent_system.agents.bug_investigation import BugInvestigationAgent
from agent_system.schemas.state import IssuePayload, SessionState, TriageResult, RootCauseReport


@pytest.fixture
def bug_issue():
    return IssuePayload(
        id=42,
        title="Filtering by status string fails",
        body="Calling list_tasks('TODO') raises an error or fails to filter properly.",
        labels=["bug"],
        author="testuser"
    )


def test_bug_investigation_requires_bug_triage(bug_issue):
    agent = BugInvestigationAgent()
    
    # Missing triage_result
    state_no_triage = SessionState(issue=bug_issue)
    with pytest.raises(ValueError, match="requires state.triage_result"):
        agent.analyze(state_no_triage)

    # Feature triage
    state_feature = SessionState(
        issue=bug_issue,
        triage_result=TriageResult(classification="FEATURE", confidence=0.9, routing_note="Feature request")
    )
    with pytest.raises(ValueError, match="requires state.triage_result with classification='BUG'"):
        agent.analyze(state_feature)


def test_bug_investigation_analyze_success(bug_issue, monkeypatch):
    agent = BugInvestigationAgent()
    state = SessionState(
        issue=bug_issue,
        triage_result=TriageResult(classification="BUG", confidence=0.95, routing_note="Defect in status filter")
    )

    # Mock OpenAI client
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"file": "src/task_tracker/core.py", "line_range": [67, 67], "hypothesis": "Comparison uses t.status instead of t.status.value", "grep_evidence": ["core.py:67: if t.status == status"]}'
            )
        )
    ]
    
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    monkeypatch.setattr(agent, "_get_client", lambda: mock_client)

    report = agent.analyze(state)

    assert isinstance(report, RootCauseReport)
    assert report.file == "src/task_tracker/core.py"
    assert report.line_range == (67, 67)
    assert "Comparison uses" in report.hypothesis
    assert state.root_cause_report == report
