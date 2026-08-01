import pytest
from unittest.mock import MagicMock
from agent_system.agents.requirements_analysis import RequirementsAnalysisAgent
from agent_system.schemas.state import IssuePayload, SessionState, TriageResult, RootCauseReport, RequirementsSpec


@pytest.fixture
def sample_issue():
    return IssuePayload(
        id=42,
        title="Filtering by status string fails",
        body="Calling list_tasks('TODO') fails.",
        labels=["bug"],
        author="testuser"
    )


def test_requirements_analysis_guard_1_validation(sample_issue):
    """Guard #1: requirements_spec cannot be created if triage_result is None."""
    agent = RequirementsAnalysisAgent()
    state = SessionState(issue=sample_issue)

    with pytest.raises(ValueError, match="requirements_spec requires triage_result to be set first"):
        agent.analyze(state)


def test_requirements_analysis_bug_path(sample_issue, monkeypatch):
    agent = RequirementsAnalysisAgent()
    root_cause = RootCauseReport(
        file="src/task_tracker/core.py",
        line_range=(67, 67),
        hypothesis="Defect in status filter comparison",
        grep_evidence=["core.py:67: if t.status == status"]
    )
    state = SessionState(
        issue=sample_issue,
        triage_result=TriageResult(classification="BUG", confidence=0.95, routing_note="Defect in status filter"),
        root_cause_report=root_cause
    )

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"scope": "Fix list_tasks status filter comparison", "acceptance_criteria": ["list_tasks(\'TODO\') returns correct tasks"], "target_files": ["src/task_tracker/core.py"], "out_of_scope": ["Refactoring Task class"]}'
            )
        )
    ]
    
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    monkeypatch.setattr(agent, "_get_client", lambda: mock_client)

    spec = agent.analyze(state)

    assert isinstance(spec, RequirementsSpec)
    assert spec.scope == "Fix list_tasks status filter comparison"
    assert "src/task_tracker/core.py" in spec.target_files
    assert len(spec.acceptance_criteria) == 1
    assert state.requirements_spec == spec


def test_requirements_analysis_feature_path(monkeypatch):
    feature_issue = IssuePayload(
        id=43,
        title="Add priority filter to list_tasks()",
        body="Support filtering by priority integer.",
        labels=["enhancement"],
        author="testuser"
    )
    agent = RequirementsAnalysisAgent()
    state = SessionState(
        issue=feature_issue,
        triage_result=TriageResult(classification="FEATURE", confidence=0.99, routing_note="Feature request for priority filter")
    )

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"scope": "Add priority filtering to list_tasks()", "acceptance_criteria": ["list_tasks(priority=2) returns tasks with priority 2"], "target_files": ["src/task_tracker/core.py"], "out_of_scope": []}'
            )
        )
    ]
    
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    monkeypatch.setattr(agent, "_get_client", lambda: mock_client)

    spec = agent.analyze(state)

    assert isinstance(spec, RequirementsSpec)
    assert spec.scope == "Add priority filtering to list_tasks()"
    assert state.requirements_spec == spec
