import pytest
from agent_system.gate import HumanGate
from agent_system.cli import run_pipeline
from agent_system.schemas.state import (
    IssuePayload, SessionState, TriageResult, RootCauseReport, RequirementsSpec,
    PatchResult, TestResult, ReviewResult, DocUpdates
)


@pytest.fixture
def ready_state():
    issue = IssuePayload(id=42, title="Fix bug", body="Bug body", labels=["bug"], author="test")
    triage = TriageResult(classification="BUG", confidence=0.95, routing_note="Bug note")
    root_cause = RootCauseReport(file="src/task_tracker/core.py", line_range=(67, 67), hypothesis="bug", grep_evidence=["if t.status == status"])
    reqs = RequirementsSpec(scope="Fix status filter comparison", acceptance_criteria=["Tests pass"], target_files=["src/task_tracker/core.py"])
    patch = PatchResult(diff="diff --git a/core.py b/core.py\n+ return [t for t in self._tasks.values() if t.status.value == status]", changed_files=["src/task_tracker/core.py"], explanation="Fixed comparison")
    test_res = TestResult(status="PASS", passed=6, failed=0, tracebacks=[])
    review_res = ReviewResult(decision="APPROVED", linter_output=[], critique="LGTM")
    doc_res = DocUpdates(docstring_diffs=["+ docstring"], readme_diff=None, changelog_entry="- Fixed bug")

    return SessionState(
        issue=issue,
        triage_result=triage,
        root_cause_report=root_cause,
        requirements_spec=reqs,
        patch=patch,
        test_result=test_res,
        review_result=review_res,
        doc_updates=doc_res,
        status="IN_PROGRESS"
    )


def test_human_gate_render_summary(ready_state):
    summary = HumanGate.render_summary(ready_state)
    assert "HUMAN APPROVAL GATE SUMMARY" in summary
    assert "Issue #42 : Fix bug" in summary
    assert "Triage    : BUG" in summary
    assert "Root Cause: File src/task_tracker/core.py:(67, 67)" in summary
    assert "Req Scope : Fix status filter comparison" in summary
    assert "Test Run  : PASS" in summary
    assert "Code Review: APPROVED" in summary


def test_human_gate_approve_choice(ready_state):
    state = HumanGate.prompt_decision(ready_state, interactive=False, default_choice="A")
    assert state.gate_decision == "APPROVE"
    assert state.human_feedback is None


def test_human_gate_request_changes_choice(ready_state):
    state = HumanGate.prompt_decision(ready_state, interactive=False, default_choice="F")
    assert state.gate_decision == "REQUEST_CHANGES"
    assert state.human_feedback is not None
    assert "Please address code review feedback" in state.human_feedback


def test_human_gate_reject_choice(ready_state):
    state = HumanGate.prompt_decision(ready_state, interactive=False, default_choice="R")
    assert state.gate_decision == "REJECT"
    assert state.human_feedback is None


def test_human_gate_forces_intervention_on_partial_status(ready_state):
    ready_state.status = "PARTIAL"
    ready_state.iteration_count = 3
    state = HumanGate.prompt_decision(ready_state, interactive=False, default_choice="A")
    assert state.status == "PARTIAL"
    assert state.gate_decision == "APPROVE"
