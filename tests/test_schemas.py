import pytest
from pydantic import ValidationError
from agent_system.schemas.state import (
    IssuePayload,
    TriageResult,
    RootCauseReport,
    RequirementsSpec,
    PatchResult,
    TestResult,
    LinterIssue,
    ReviewResult,
    DocUpdates,
    SessionState,
)


def create_sample_issue() -> IssuePayload:
    return IssuePayload(
        id=42,
        title="Fix case-sensitivity in list_tasks filter",
        body="Filtering by status is case sensitive.",
        labels=["bug"],
        author="testuser",
    )


def create_sample_triage(classification: str = "FEATURE") -> TriageResult:
    return TriageResult(
        classification=classification,
        confidence=0.95,
        routing_note=f"Routing for {classification}",
    )


def create_sample_root_cause() -> RootCauseReport:
    return RootCauseReport(
        file="src/task_tracker/core.py",
        line_range=(65, 75),
        hypothesis="list_tasks compares status directly without calling status.upper()",
        grep_evidence=["if task.status == status:"],
    )


def create_sample_spec() -> RequirementsSpec:
    return RequirementsSpec(
        scope="Fix case-sensitivity in core.py",
        acceptance_criteria=["list_tasks(status='open') matches 'OPEN'"],
        target_files=["src/task_tracker/core.py"],
    )


def create_sample_patch() -> PatchResult:
    return PatchResult(
        diff="--- a/src/task_tracker/core.py\n+++ b/src/task_tracker/core.py\n@@ -1 +1 @@\n-status\n+status.upper()",
        changed_files=["src/task_tracker/core.py"],
        explanation="Normalized status string to uppercase",
    )


def create_sample_test_result(passed: bool = True) -> TestResult:
    return TestResult(
        status="PASS" if passed else "FAIL",
        passed=5 if passed else 4,
        failed=0 if passed else 1,
        tracebacks=[] if passed else ["AssertionError: status mismatch"],
    )


def create_sample_review_result(approved: bool = True) -> ReviewResult:
    return ReviewResult(
        decision="APPROVED" if approved else "CHANGES_NEEDED",
        linter_output=[],
        critique=None if approved else "Needs docstring update",
    )


def create_sample_doc_updates() -> DocUpdates:
    return DocUpdates(
        docstring_diffs=["+ Add upper() explanation"],
        changelog_entry="Fixed case sensitivity in task filtering.",
    )


# ─── Happy Path Tests ─────────────────────────────────────────────────────────

def test_valid_minimal_session_state():
    """Verify state initialization with required issue field."""
    issue = create_sample_issue()
    state = SessionState(issue=issue)
    assert state.issue.id == 42
    assert state.status == "IN_PROGRESS"
    assert state.iteration_count == 0


def test_full_valid_feature_path_happy_path_state():
    """Verify complete Feature path sequence (Triage FEATURE -> spec -> patch -> tests -> review -> docs -> READY -> gate)."""
    state = SessionState(
        issue=create_sample_issue(),
        triage_result=create_sample_triage("FEATURE"),
        requirements_spec=create_sample_spec(),
        patch=create_sample_patch(),
        test_result=create_sample_test_result(passed=True),
        review_result=create_sample_review_result(approved=True),
        doc_updates=create_sample_doc_updates(),
        status="READY",
        gate_decision="APPROVE",
    )
    assert state.triage_result.classification == "FEATURE"
    assert state.status == "READY"
    assert state.gate_decision == "APPROVE"


def test_full_valid_bug_path_happy_path_state():
    """Verify complete Bug path sequence (Triage BUG -> root_cause -> spec -> patch -> tests -> review -> docs -> READY -> gate)."""
    state = SessionState(
        issue=create_sample_issue(),
        triage_result=create_sample_triage("BUG"),
        root_cause_report=create_sample_root_cause(),
        requirements_spec=create_sample_spec(),
        patch=create_sample_patch(),
        test_result=create_sample_test_result(passed=True),
        review_result=create_sample_review_result(approved=True),
        doc_updates=create_sample_doc_updates(),
        status="READY",
        gate_decision="APPROVE",
    )
    assert state.triage_result.classification == "BUG"
    assert state.root_cause_report is not None
    assert state.root_cause_report.file == "src/task_tracker/core.py"
    assert state.status == "READY"


# ─── Guard Boundary Tests ─────────────────────────────────────────────────────

def test_validator_guard_1_requirements_requires_triage_negative():
    """Guard 1 (Negative): requirements_spec without triage_result fails."""
    issue = create_sample_issue()
    spec = create_sample_spec()

    with pytest.raises(ValidationError) as exc_info:
        SessionState(issue=issue, requirements_spec=spec)
    assert "requirements_spec requires triage_result" in str(exc_info.value)


def test_validator_guard_1_requirements_requires_triage_positive():
    """Guard 1 (Positive): requirements_spec valid when triage_result present."""
    state = SessionState(
        issue=create_sample_issue(),
        triage_result=create_sample_triage("FEATURE"),
        requirements_spec=create_sample_spec(),
    )
    assert state.requirements_spec is not None


def test_validator_guard_1b_bug_path_negative_requires_root_cause():
    """Guard 1b (Negative): On BUG path, requirements_spec without root_cause_report fails."""
    issue = create_sample_issue()
    triage_bug = create_sample_triage("BUG")
    spec = create_sample_spec()

    with pytest.raises(ValidationError) as exc_info:
        SessionState(issue=issue, triage_result=triage_bug, requirements_spec=spec)
    assert "requirements_spec on BUG path requires root_cause_report" in str(exc_info.value)


def test_validator_guard_1b_bug_path_positive_with_root_cause():
    """Guard 1b (Positive): On BUG path, requirements_spec valid when root_cause_report present."""
    root_cause = create_sample_root_cause()
    state = SessionState(
        issue=create_sample_issue(),
        triage_result=create_sample_triage("BUG"),
        root_cause_report=root_cause,
        requirements_spec=create_sample_spec(),
    )
    assert state.root_cause_report.hypothesis == root_cause.hypothesis


def test_validator_guard_2_patch_requires_requirements_negative():
    """Guard 2 (Negative): patch without requirements_spec fails."""
    issue = create_sample_issue()
    triage = create_sample_triage()
    patch = create_sample_patch()

    with pytest.raises(ValidationError) as exc_info:
        SessionState(issue=issue, triage_result=triage, patch=patch)
    assert "patch requires requirements_spec" in str(exc_info.value)


def test_validator_guard_2_patch_requires_requirements_positive():
    """Guard 2 (Positive): patch valid when requirements_spec present."""
    state = SessionState(
        issue=create_sample_issue(),
        triage_result=create_sample_triage(),
        requirements_spec=create_sample_spec(),
        patch=create_sample_patch(),
    )
    assert state.patch is not None


def test_validator_guard_3_test_result_requires_patch_negative():
    """Guard 3 (Negative): test_result without patch fails."""
    issue = create_sample_issue()
    triage = create_sample_triage()
    spec = create_sample_spec()
    test_res = create_sample_test_result()

    with pytest.raises(ValidationError) as exc_info:
        SessionState(
            issue=issue,
            triage_result=triage,
            requirements_spec=spec,
            test_result=test_res,
        )
    assert "test_result requires patch" in str(exc_info.value)


def test_validator_guard_3_test_result_requires_patch_positive():
    """Guard 3 (Positive): test_result valid when patch present."""
    state = SessionState(
        issue=create_sample_issue(),
        triage_result=create_sample_triage(),
        requirements_spec=create_sample_spec(),
        patch=create_sample_patch(),
        test_result=create_sample_test_result(),
    )
    assert state.test_result is not None


def test_validator_guard_4_review_requires_test_result_negative():
    """Guard 4 (Negative): review_result without test_result fails."""
    issue = create_sample_issue()
    triage = create_sample_triage()
    spec = create_sample_spec()
    patch = create_sample_patch()
    review = create_sample_review_result()

    with pytest.raises(ValidationError) as exc_info:
        SessionState(
            issue=issue,
            triage_result=triage,
            requirements_spec=spec,
            patch=patch,
            review_result=review,
        )
    assert "review_result requires test_result" in str(exc_info.value)


def test_validator_guard_4_review_requires_test_result_positive():
    """Guard 4 (Positive): review_result valid when test_result present."""
    state = SessionState(
        issue=create_sample_issue(),
        triage_result=create_sample_triage(),
        requirements_spec=create_sample_spec(),
        patch=create_sample_patch(),
        test_result=create_sample_test_result(),
        review_result=create_sample_review_result(),
    )
    assert state.review_result is not None


def test_validator_guard_5_doc_updates_requires_review_negative():
    """Guard 5 (Negative - Case A): doc_updates without review_result fails."""
    issue = create_sample_issue()
    triage = create_sample_triage()
    spec = create_sample_spec()
    patch = create_sample_patch()
    test_res = create_sample_test_result()
    doc = create_sample_doc_updates()

    with pytest.raises(ValidationError) as exc_info:
        SessionState(
            issue=issue,
            triage_result=triage,
            requirements_spec=spec,
            patch=patch,
            test_result=test_res,
            doc_updates=doc,
        )
    assert "doc_updates requires review_result" in str(exc_info.value)


def test_validator_guard_5_doc_updates_requires_approved_decision_negative():
    """Guard 5 (Negative - Case B): doc_updates with review_result.decision == 'CHANGES_NEEDED' fails."""
    issue = create_sample_issue()
    triage = create_sample_triage()
    spec = create_sample_spec()
    patch = create_sample_patch()
    test_res = create_sample_test_result()
    rejected_review = create_sample_review_result(approved=False)
    doc = create_sample_doc_updates()

    with pytest.raises(ValidationError) as exc_info:
        SessionState(
            issue=issue,
            triage_result=triage,
            requirements_spec=spec,
            patch=patch,
            test_result=test_res,
            review_result=rejected_review,
            doc_updates=doc,
        )
    assert "decision == 'APPROVED'" in str(exc_info.value)


def test_validator_guard_5_doc_updates_valid_with_approved_review_positive():
    """Guard 5 (Positive): doc_updates valid when review_result.decision == 'APPROVED'."""
    state = SessionState(
        issue=create_sample_issue(),
        triage_result=create_sample_triage(),
        requirements_spec=create_sample_spec(),
        patch=create_sample_patch(),
        test_result=create_sample_test_result(passed=True),
        review_result=create_sample_review_result(approved=True),
        doc_updates=create_sample_doc_updates(),
    )
    assert state.doc_updates is not None
    assert state.doc_updates.changelog_entry is not None


def test_validator_guard_6_gate_decision_requires_doc_updates_on_in_progress_negative():
    """Guard 6 (Negative): gate_decision on IN_PROGRESS without doc_updates fails."""
    issue = create_sample_issue()
    triage = create_sample_triage()
    spec = create_sample_spec()
    patch = create_sample_patch()
    test_res = create_sample_test_result(passed=False)

    with pytest.raises(ValidationError) as exc_info:
        SessionState(
            issue=issue,
            triage_result=triage,
            requirements_spec=spec,
            patch=patch,
            test_result=test_res,
            gate_decision="APPROVE",
        )
    assert "gate_decision requires doc_updates" in str(exc_info.value)


def test_validator_guard_6_gate_decision_valid_on_partial_status_positive():
    """Guard 6 (Positive - PARTIAL): gate_decision valid on PARTIAL status without doc_updates."""
    state = SessionState(
        issue=create_sample_issue(),
        triage_result=create_sample_triage(),
        requirements_spec=create_sample_spec(),
        patch=create_sample_patch(),
        test_result=create_sample_test_result(passed=False),
        status="PARTIAL",
        gate_decision="APPROVE",
    )
    assert state.gate_decision == "APPROVE"
    assert state.status == "PARTIAL"


def test_validator_guard_6_gate_decision_valid_on_error_status_positive():
    """Guard 6 (Positive - ERROR): gate_decision valid on ERROR status without doc_updates."""
    state = SessionState(
        issue=create_sample_issue(),
        triage_result=create_sample_triage(),
        status="ERROR",
        gate_decision="REJECT",
    )
    assert state.gate_decision == "REJECT"
    assert state.status == "ERROR"
