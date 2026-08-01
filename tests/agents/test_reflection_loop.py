import pytest
from unittest.mock import MagicMock
from agent_system.agents.coding_assistant import CodingAssistantAgent
from agent_system.agents.testing_agent import TestingAgent
from agent_system.agents.code_reviewer import CodeReviewerAgent
from agent_system.agents.reflection_loop import run_reflection_loop
from agent_system.schemas.state import (
    IssuePayload, SessionState, TriageResult, RootCauseReport, RequirementsSpec,
    PatchResult, TestResult, ReviewResult, ToolError
)


@pytest.fixture
def base_state():
    issue = IssuePayload(id=42, title="Fix bug", body="Bug body", labels=["bug"], author="test")
    triage = TriageResult(classification="BUG", confidence=0.95, routing_note="Bug note")
    root_cause = RootCauseReport(
        file="src/task_tracker/core.py",
        line_range=(67, 67),
        hypothesis="Bug hypothesis",
        grep_evidence=["core.py:67"]
    )
    reqs = RequirementsSpec(
        scope="Fix core.py bug",
        acceptance_criteria=["Tests pass"],
        target_files=["src/task_tracker/core.py"]
    )
    return SessionState(issue=issue, triage_result=triage, root_cause_report=root_cause, requirements_spec=reqs)


def test_coding_assistant_requires_requirements_spec(base_state):
    agent = CodingAssistantAgent()
    invalid_state = SessionState(issue=base_state.issue)
    with pytest.raises(ValueError, match="patch requires requirements_spec"):
        agent.generate_patch(invalid_state)


def test_testing_agent_requires_patch(base_state):
    agent = TestingAgent()
    with pytest.raises(ValueError, match="test_result requires patch"):
        agent.run_tests(base_state)


def test_code_reviewer_requires_test_result(base_state):
    agent = CodeReviewerAgent()
    base_state.patch = PatchResult(diff="fake diff", changed_files=["src/task_tracker/core.py"], explanation="Fixed bug")
    with pytest.raises(ValueError, match="review_result requires test_result"):
        agent.review(base_state)


def test_reflection_loop_success_iteration_1(base_state, monkeypatch):
    coding_agent = CodingAssistantAgent()
    testing_agent = TestingAgent()
    reviewer_agent = CodeReviewerAgent()

    # Mock Coding Agent
    monkeypatch.setattr(coding_agent, "generate_patch", lambda st: setattr(st, "patch", PatchResult(
        diff="fake diff", changed_files=["src/task_tracker/core.py"], explanation="Fixed bug"
    )))

    # Mock Testing Agent
    monkeypatch.setattr(testing_agent, "run_tests", lambda st, session_id: setattr(st, "test_result", TestResult(
        status="PASS", passed=6, failed=0, tracebacks=[]
    )) or st.test_result)

    # Mock Reviewer Agent
    monkeypatch.setattr(reviewer_agent, "review", lambda st, session_id: setattr(st, "review_result", ReviewResult(
        decision="APPROVED", linter_output=[], critique="Looks good"
    )) or st.review_result)

    state = run_reflection_loop(
        base_state,
        coding_agent=coding_agent,
        testing_agent=testing_agent,
        reviewer_agent=reviewer_agent
    )

    assert state.iteration_count == 1
    assert state.review_result.decision == "APPROVED"
    assert state.status == "IN_PROGRESS"


def test_reflection_loop_retry_on_test_fail_then_pass(base_state, monkeypatch):
    coding_agent = CodingAssistantAgent()
    testing_agent = TestingAgent()
    reviewer_agent = CodeReviewerAgent()

    attempts = {"count": 0}

    def mock_patch(st):
        st.patch = PatchResult(diff="fake diff", changed_files=["src/task_tracker/core.py"], explanation="Patch attempt")

    def mock_test(st, session_id):
        attempts["count"] += 1
        if attempts["count"] == 1:
            st.test_result = TestResult(status="FAIL", passed=0, failed=1, tracebacks=["AssertionError"])
        else:
            st.test_result = TestResult(status="PASS", passed=6, failed=0, tracebacks=[])
        return st.test_result

    def mock_review(st, session_id):
        st.review_result = ReviewResult(decision="APPROVED", linter_output=[], critique="Good")
        return st.review_result

    monkeypatch.setattr(coding_agent, "generate_patch", mock_patch)
    monkeypatch.setattr(testing_agent, "run_tests", mock_test)
    monkeypatch.setattr(reviewer_agent, "review", mock_review)

    state = run_reflection_loop(
        base_state,
        coding_agent=coding_agent,
        testing_agent=testing_agent,
        reviewer_agent=reviewer_agent
    )

    assert state.iteration_count == 2
    assert state.test_result.status == "PASS"
    assert state.review_result.decision == "APPROVED"


def test_reflection_loop_exhausted_retries_becomes_partial(base_state, monkeypatch):
    coding_agent = CodingAssistantAgent()
    testing_agent = TestingAgent()
    reviewer_agent = CodeReviewerAgent()

    # Testing Agent keeps failing tests
    monkeypatch.setattr(coding_agent, "generate_patch", lambda st: setattr(st, "patch", PatchResult(
        diff="bad diff", changed_files=["src/task_tracker/core.py"], explanation="Bad patch"
    )))

    monkeypatch.setattr(testing_agent, "run_tests", lambda st, session_id: setattr(st, "test_result", TestResult(
        status="FAIL", passed=0, failed=1, tracebacks=["Persistent test failure"]
    )) or st.test_result)

    state = run_reflection_loop(
        base_state,
        coding_agent=coding_agent,
        testing_agent=testing_agent,
        reviewer_agent=reviewer_agent,
        max_iterations=3
    )

    assert state.iteration_count == 3
    assert state.status == "PARTIAL"


def test_testing_agent_handles_tool_error_gracefully(base_state, monkeypatch):
    """Verify TestingAgent converts ToolError into retryable TestResult(status='FAIL') per engineering.md §7.1."""
    agent = TestingAgent()
    base_state.patch = PatchResult(diff="bad diff", changed_files=["src/task_tracker/core.py"], explanation="Bad patch")

    mock_error = ToolError(
        tool="T-3:pytest_runner",
        error_type="PATCH_APPLY_FAILED",
        message="Corrupt diff hunk at line 5",
        details={}
    )

    monkeypatch.setattr("agent_system.agents.testing_agent.run_pytest_in_sandbox", lambda session_id, patch_diff: mock_error)

    result = agent.run_tests(base_state)

    assert isinstance(result, TestResult)
    assert result.status == "FAIL"
    assert result.passed == 0
    assert result.failed == 1
    assert len(result.tracebacks) == 1
    assert "Tool Error (PATCH_APPLY_FAILED): Corrupt diff hunk at line 5" in result.tracebacks[0]
    assert base_state.test_result == result


def test_reflection_loop_retries_on_tool_error(base_state, monkeypatch):
    """Verify reflection loop handles ToolError as retryable failure and increments iteration_count cleanly."""
    coding_agent = CodingAssistantAgent()
    testing_agent = TestingAgent()
    reviewer_agent = CodeReviewerAgent()

    attempts = {"count": 0}

    def mock_patch(st):
        st.patch = PatchResult(diff="patch diff", changed_files=["src/task_tracker/core.py"], explanation="Patch attempt")

    def mock_sandbox_run(session_id, patch_diff):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return ToolError(tool="T-3:pytest_runner", error_type="PATCH_APPLY_FAILED", message="Git apply error")
        return {"status": "PASS", "passed": 6, "failed": 0, "tracebacks": []}

    def mock_review(st, session_id):
        st.review_result = ReviewResult(decision="APPROVED", linter_output=[], critique="LGTM")
        return st.review_result

    monkeypatch.setattr(coding_agent, "generate_patch", mock_patch)
    monkeypatch.setattr("agent_system.agents.testing_agent.run_pytest_in_sandbox", mock_sandbox_run)
    monkeypatch.setattr(reviewer_agent, "review", mock_review)

    # Run loop - iteration 1 encounters ToolError, iteration 2 passes
    state = run_reflection_loop(
        base_state,
        coding_agent=coding_agent,
        testing_agent=testing_agent,
        reviewer_agent=reviewer_agent
    )

    # Specifically assert iteration_count incremented on ToolError-triggered failure
    assert state.iteration_count == 2
    assert state.test_result.status == "PASS"
    assert state.review_result.decision == "APPROVED"

