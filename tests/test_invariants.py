import hashlib
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from pydantic import ValidationError

from agent_system.cli import run_pipeline
from agent_system.schemas.state import (
    IssuePayload, SessionState, TriageResult, RootCauseReport, RequirementsSpec,
    PatchResult, TestResult, ReviewResult, DocUpdates
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def compute_dir_sha256(dir_path: Path) -> str:
    """Computes a combined SHA-256 cryptographic hash of all file contents in a directory tree."""
    hasher = hashlib.sha256()
    for path in sorted(dir_path.rglob("*")):
        if path.is_file():
            hasher.update(path.relative_to(dir_path).as_posix().encode("utf-8"))
            hasher.update(path.read_bytes())
    return hasher.hexdigest()


@pytest.fixture
def mock_all_agents(monkeypatch):
    """Mocks agent execution steps to cleanly test end-to-end pipeline invariants."""
    monkeypatch.setenv("GROQ_API_KEY", "mock_groq_key")
    monkeypatch.setenv("GOOGLE_AI_API_KEY", "mock_google_key")

    # Mock Orchestrator
    monkeypatch.setattr("agent_system.agents.orchestrator.OrchestratorAgent.triage", lambda self, iss: TriageResult(
        classification="BUG", confidence=0.95, routing_note="Triage complete"
    ))

    # Mock Bug Investigation
    monkeypatch.setattr("agent_system.agents.bug_investigation.BugInvestigationAgent.analyze", lambda self, st: setattr(st, "root_cause_report", RootCauseReport(
        file="src/task_tracker/core.py", line_range=(67, 67), hypothesis="Bug hypothesis", grep_evidence=["core.py:67"]
    )) or st.root_cause_report)

    # Mock Requirements Analysis
    monkeypatch.setattr("agent_system.agents.requirements_analysis.RequirementsAnalysisAgent.analyze", lambda self, st: setattr(st, "requirements_spec", RequirementsSpec(
        scope="Fix core.py bug", acceptance_criteria=["Tests pass"], target_files=["src/task_tracker/core.py"]
    )) or st.requirements_spec)

    # Mock Reflection Loop
    def mock_loop(st, session_id):
        st.patch = PatchResult(diff="fake diff", changed_files=["src/task_tracker/core.py"], explanation="Fixed")
        st.test_result = TestResult(status="PASS", passed=6, failed=0, tracebacks=[])
        st.review_result = ReviewResult(decision="APPROVED", linter_output=[], critique="LGTM")
        return st

    monkeypatch.setattr("agent_system.cli.run_reflection_loop", mock_loop)

    # Mock Doc Writer
    monkeypatch.setattr("agent_system.agents.documentation_writer.DocumentationWriterAgent.write_documentation", lambda self, st, session_id="session_default": setattr(st, "doc_updates", DocUpdates(
        docstring_diffs=["+ docstring"], readme_diff=None, changelog_entry="- Fixed bug"
    )) or st.doc_updates)


def test_invariant_1_pr_gated_behind_approve(mock_all_agents, monkeypatch):
    """Invariant I-1 (Positive): Tool T-5 (create_pull_request) is ONLY called when gate decision is APPROVE."""
    mock_t5 = MagicMock(return_value={"html_url": "https://github.com/demo/demo_repo/pull/1", "mocked": True})
    monkeypatch.setattr("agent_system.tools.github_write.create_pull_request", mock_t5)

    state = run_pipeline("issues/bug_42.json", interactive_gate=False, gate_choice_override="A")

    assert state.gate_decision == "APPROVE"
    assert state.status == "READY"
    assert mock_t5.call_count == 1
    assert "fix/issue-42" in mock_t5.call_args.kwargs.get("branch", "")


def test_invariant_1_pr_never_created_on_non_approve_paths(mock_all_agents, monkeypatch):
    """Invariant I-1 (Negative): Tool T-5 is NEVER called on REJECT, REQUEST_CHANGES (prior to re-approval), or PARTIAL states."""
    mock_t5 = MagicMock()
    monkeypatch.setattr("agent_system.tools.github_write.create_pull_request", mock_t5)

    # Case A: REJECT decision yields 0 PR calls
    state_reject = run_pipeline("issues/bug_42.json", interactive_gate=False, gate_choice_override="R")
    assert state_reject.gate_decision == "REJECT"
    assert mock_t5.call_count == 0

    # Case B: PARTIAL status presentation yields 0 PR calls
    def mock_partial_loop(st, session_id):
        st.patch = PatchResult(diff="bad diff", changed_files=["src/task_tracker/core.py"], explanation="Bad")
        st.test_result = TestResult(status="FAIL", passed=0, failed=1, tracebacks=["Fail"])
        st.iteration_count = 3
        st.status = "PARTIAL"
        return st

    monkeypatch.setattr("agent_system.cli.run_reflection_loop", mock_partial_loop)
    state_partial = run_pipeline("issues/bug_42.json", interactive_gate=False, gate_choice_override="R")
    assert state_partial.status == "PARTIAL"
    assert mock_t5.call_count == 0

    # Case C: REQUEST_CHANGES intermediate state yields 0 PR calls
    mock_t5_c = MagicMock()
    monkeypatch.setattr("agent_system.tools.github_write.create_pull_request", mock_t5_c)
    rc_choices = ["F", "R"]
    def mock_prompt_rc(state, interactive=True, default_choice=None):
        c = rc_choices.pop(0) if rc_choices else "R"
        if c == "F":
            state.gate_decision = "REQUEST_CHANGES"
            state.human_feedback = "Need changes"
        else:
            state.gate_decision = "REJECT"
        return state

    monkeypatch.setattr("agent_system.gate.HumanGate.prompt_decision", mock_prompt_rc)
    state_rc = run_pipeline("issues/bug_42.json", interactive_gate=False)
    assert mock_t5_c.call_count == 0


def test_invariant_2_demo_repo_mutation_isolation(mock_all_agents, monkeypatch):
    """Invariant I-2: Original working directory demo_repo/ is NEVER mutated during pipeline runs (Cryptographic SHA-256 tree hash proof)."""
    demo_repo_dir = PROJECT_ROOT / "demo_repo"
    hash_before = compute_dir_sha256(demo_repo_dir)

    mock_t5 = MagicMock(return_value={"html_url": "https://github.com/demo/demo_repo/pull/1"})
    monkeypatch.setattr("agent_system.tools.github_write.create_pull_request", mock_t5)

    run_pipeline("issues/bug_42.json", interactive_gate=False, gate_choice_override="A")

    hash_after = compute_dir_sha256(demo_repo_dir)

    # Cryptographic proof of zero mutation across directory tree
    assert hash_before == hash_after


def test_invariant_3_reject_discards_sandbox_and_no_pr(mock_all_agents, monkeypatch):
    """Invariant I-3: Selecting REJECT discards sandbox/branch and NEVER invokes Tool T-5 PR creation."""
    mock_t5 = MagicMock()
    monkeypatch.setattr("agent_system.tools.github_write.create_pull_request", mock_t5)

    state = run_pipeline("issues/bug_42.json", interactive_gate=False, gate_choice_override="R")

    assert state.gate_decision == "REJECT"
    assert mock_t5.call_count == 0  # Invariant I-3: Zero calls to T-5 PR creation tool

    sandbox_path = PROJECT_ROOT / ".sandbox" / state.session_id
    assert not sandbox_path.exists()  # Invariant I-3: Sandbox deleted from disk


def test_request_changes_resets_downstream_state_and_forces_retesting(mock_all_agents, monkeypatch):
    """Verify selecting REQUEST_CHANGES clears patch, test_result, review_result, doc_updates and forces re-testing/re-reviewing."""
    mock_t5 = MagicMock(return_value={"html_url": "https://github.com/demo/demo_repo/pull/1"})
    monkeypatch.setattr("agent_system.tools.github_write.create_pull_request", mock_t5)

    pass_counter = {"count": 0}

    def mock_tracked_loop(st, session_id):
        pass_counter["count"] += 1
        st.patch = PatchResult(diff=f"diff_{pass_counter['count']}", changed_files=["src/task_tracker/core.py"], explanation=f"Pass {pass_counter['count']}")
        st.test_result = TestResult(status="PASS", passed=6, failed=0, tracebacks=[])
        st.review_result = ReviewResult(decision="APPROVED", linter_output=[], critique="Approved")
        return st

    monkeypatch.setattr("agent_system.cli.run_reflection_loop", mock_tracked_loop)

    choices = ["F", "A"]
    def mock_prompt(state, interactive=True, default_choice=None):
        c = choices.pop(0) if choices else "A"
        if c == "F":
            state.gate_decision = "REQUEST_CHANGES"
            state.human_feedback = "Please add comment"
        else:
            state.gate_decision = "APPROVE"
        return state

    monkeypatch.setattr("agent_system.gate.HumanGate.prompt_decision", mock_prompt)

    state = run_pipeline("issues/bug_42.json", interactive_gate=False)

    assert pass_counter["count"] == 2  # Proves reflection loop ran TWICE (fresh pass on retry)
    assert state.patch.diff == "diff_2"
    assert state.gate_decision == "APPROVE"


def test_guard_chain_validation_on_assignment_and_reset():
    """Verify Pydantic ConfigDict(validate_assignment=True) enforces guard chain validation on direct field mutations."""
    issue = IssuePayload(id=42, title="Bug", body="Body", labels=["bug"], author="user")
    triage = TriageResult(classification="BUG", confidence=0.9, routing_note="Bug")
    root = RootCauseReport(file="core.py", line_range=(1, 1), hypothesis="h", grep_evidence=[])
    spec = RequirementsSpec(scope="s", acceptance_criteria=["c"], target_files=["core.py"])
    patch = PatchResult(diff="d", changed_files=["core.py"], explanation="e")
    test_res = TestResult(status="PASS", passed=1, failed=0, tracebacks=[])

    state = SessionState(issue=issue, triage_result=triage, root_cause_report=root, requirements_spec=spec, patch=patch, test_result=test_res)

    # Attempting out-of-order patch removal while test_result is still set raises ValidationError via validate_assignment=True!
    with pytest.raises(ValidationError) as exc_info:
        state.patch = None
    assert "test_result requires patch to be set first" in str(exc_info.value)
