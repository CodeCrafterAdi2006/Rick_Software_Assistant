import pytest
from unittest.mock import MagicMock
from agent_system.agents.documentation_writer import DocumentationWriterAgent
from agent_system.schemas.state import (
    IssuePayload, SessionState, TriageResult, RootCauseReport, RequirementsSpec,
    PatchResult, TestResult, ReviewResult, DocUpdates
)


@pytest.fixture
def approved_state():
    issue = IssuePayload(id=42, title="Fix bug", body="Bug body", labels=["bug"], author="test")
    triage = TriageResult(classification="BUG", confidence=0.95, routing_note="Bug note")
    root_cause = RootCauseReport(file="src/task_tracker/core.py", line_range=(67, 67), hypothesis="bug", grep_evidence=[])
    reqs = RequirementsSpec(scope="Fix bug", acceptance_criteria=["Tests pass"], target_files=["src/task_tracker/core.py"])
    patch = PatchResult(diff="fake diff", changed_files=["src/task_tracker/core.py"], explanation="Fixed bug")
    test_res = TestResult(status="PASS", passed=6, failed=0, tracebacks=[])
    review_res = ReviewResult(decision="APPROVED", linter_output=[], critique="Looks good")

    return SessionState(
        issue=issue,
        triage_result=triage,
        root_cause_report=root_cause,
        requirements_spec=reqs,
        patch=patch,
        test_result=test_res,
        review_result=review_res
    )


def test_documentation_writer_guard_5_validation(approved_state):
    agent = DocumentationWriterAgent()

    # Missing review_result
    state_no_review = SessionState(
        issue=approved_state.issue,
        triage_result=approved_state.triage_result,
        root_cause_report=approved_state.root_cause_report,
        requirements_spec=approved_state.requirements_spec,
        patch=approved_state.patch,
        test_result=approved_state.test_result
    )
    with pytest.raises(ValueError, match="doc_updates requires review_result to be set first"):
        agent.write_documentation(state_no_review)

    # Review decision CHANGES_NEEDED
    state_changes_needed = approved_state.model_copy(deep=True)
    state_changes_needed.review_result = ReviewResult(decision="CHANGES_NEEDED", linter_output=[], critique="Fix linting")
    with pytest.raises(ValueError, match="doc_updates requires review_result.decision == 'APPROVED'"):
        agent.write_documentation(state_changes_needed)


def test_documentation_writer_write_success(approved_state, monkeypatch):
    agent = DocumentationWriterAgent()

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"docstring_diffs": ["+ \\"\\"\\"Updated list_tasks status docstring.\\"\\"\\""], "readme_diff": "Updated status filter usage.", "changelog_entry": "- Fixed status filter bug in list_tasks()"}'
            )
        )
    ]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    monkeypatch.setattr(agent, "_get_client", lambda: mock_client)

    doc_updates = agent.write_documentation(approved_state)

    assert isinstance(doc_updates, DocUpdates)
    assert len(doc_updates.docstring_diffs) == 1
    assert "status filter bug" in doc_updates.changelog_entry
    assert approved_state.doc_updates == doc_updates
