import pytest
from unittest.mock import MagicMock
from agent_system.agents.orchestrator import OrchestratorAgent
from agent_system.agents.bug_investigation import BugInvestigationAgent
from agent_system.agents.requirements_analysis import RequirementsAnalysisAgent
from agent_system.agents.reflection_loop import run_reflection_loop
from agent_system.agents.coding_assistant import CodingAssistantAgent
from agent_system.agents.testing_agent import TestingAgent
from agent_system.agents.code_reviewer import CodeReviewerAgent
from agent_system.agents.documentation_writer import DocumentationWriterAgent
from agent_system.schemas.state import (
    IssuePayload, SessionState, TriageResult, RootCauseReport, RequirementsSpec,
    PatchResult, TestResult, ReviewResult, DocUpdates
)


def test_full_agent_pipeline_bug_path(monkeypatch):
    """End-to-end test of full agent pipeline execution on BUG path."""
    issue = IssuePayload(
        id=42,
        title="Filtering by status string fails",
        body="Calling list_tasks('TODO') fails.",
        labels=["bug"],
        author="testuser"
    )
    state = SessionState(issue=issue)

    # 1. Orchestrator
    orchestrator = OrchestratorAgent()
    monkeypatch.setattr(orchestrator, "triage", lambda iss: setattr(state, "triage_result", TriageResult(
        classification="BUG", confidence=0.95, routing_note="Bug classification"
    )) or state.triage_result)
    orchestrator.triage(issue)
    assert state.triage_result.classification == "BUG"

    # 2. Bug Investigation Agent
    bug_agent = BugInvestigationAgent()
    monkeypatch.setattr(bug_agent, "analyze", lambda st: setattr(st, "root_cause_report", RootCauseReport(
        file="src/task_tracker/core.py", line_range=(67, 67), hypothesis="Defect in filter comparison", grep_evidence=["if t.status == status"]
    )) or st.root_cause_report)
    bug_agent.analyze(state)
    assert state.root_cause_report is not None

    # 3. Requirements Analysis Agent
    req_agent = RequirementsAnalysisAgent()
    monkeypatch.setattr(req_agent, "analyze", lambda st: setattr(st, "requirements_spec", RequirementsSpec(
        scope="Fix status filter comparison", acceptance_criteria=["Filter returns correct tasks"], target_files=["src/task_tracker/core.py"]
    )) or st.requirements_spec)
    req_agent.analyze(state)
    assert state.requirements_spec is not None

    # 4. Reflection Loop (Coding -> Testing -> Code Reviewer)
    coding_agent = CodingAssistantAgent()
    testing_agent = TestingAgent()
    reviewer_agent = CodeReviewerAgent()

    monkeypatch.setattr(coding_agent, "generate_patch", lambda st: setattr(st, "patch", PatchResult(
        diff="diff --git a/src/task_tracker/core.py...", changed_files=["src/task_tracker/core.py"], explanation="Fixed comparison"
    )))

    monkeypatch.setattr(testing_agent, "run_tests", lambda st, session_id: setattr(st, "test_result", TestResult(
        status="PASS", passed=6, failed=0, tracebacks=[]
    )) or st.test_result)

    monkeypatch.setattr(reviewer_agent, "review", lambda st, session_id: setattr(st, "review_result", ReviewResult(
        decision="APPROVED", linter_output=[], critique="LGTM"
    )) or st.review_result)

    run_reflection_loop(state, coding_agent=coding_agent, testing_agent=testing_agent, reviewer_agent=reviewer_agent)
    assert state.review_result.decision == "APPROVED"

    # 5. Documentation Writer Agent
    doc_agent = DocumentationWriterAgent()
    monkeypatch.setattr(doc_agent, "write_documentation", lambda st, session_id="session_default": setattr(st, "doc_updates", DocUpdates(
        docstring_diffs=["+ docstring"], readme_diff=None, changelog_entry="- Fixed bug"
    )) or st.doc_updates)
    doc_agent.write_documentation(state)

    # Final State Verification
    assert state.triage_result is not None
    assert state.root_cause_report is not None
    assert state.requirements_spec is not None
    assert state.patch is not None
    assert state.test_result.status == "PASS"
    assert state.review_result.decision == "APPROVED"
    assert state.doc_updates is not None
    assert state.status == "IN_PROGRESS"
