from __future__ import annotations
import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Generator, List, Optional, Union

from agent_system.agents.orchestrator import OrchestratorAgent
from agent_system.agents.bug_investigation import BugInvestigationAgent
from agent_system.agents.requirements_analysis import RequirementsAnalysisAgent
from agent_system.agents.reflection_loop import run_reflection_loop
from agent_system.agents.documentation_writer import DocumentationWriterAgent
from agent_system.gate import HumanGate
from agent_system.logging.session_log import SessionLogger
from agent_system.schemas.state import IssuePayload, SessionState


def load_issue_payload(issue_path: str | Path) -> IssuePayload:
    """Load and validate an issue JSON file into an IssuePayload model."""
    path = Path(issue_path)
    if not path.exists():
        raise FileNotFoundError(f"Issue file not found at: {path.resolve()}")
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return IssuePayload(**data)


def run_to_gate_generator(
    issue_input: Union[str, Path, IssuePayload]
) -> Generator[SessionState, None, SessionState]:
    """Runs pipeline up to Human Gate, yielding SessionState after each agent handoff for live UI streaming."""
    if isinstance(issue_input, IssuePayload):
        issue = issue_input
    else:
        issue = load_issue_payload(issue_input)

    session_id = f"session_{uuid.uuid4().hex[:8]}"
    logger = SessionLogger(session_id)

    state = SessionState(
        session_id=session_id,
        issue=issue,
    )

    print(f"=== Multi-Agent Pipeline Starting ===")
    print(f"Session ID : {session_id}")
    print(f"Issue #{issue.id}: {issue.title}")
    print(f"Author     : {issue.author}")
    print(f"Labels     : {issue.labels}")
    print("-" * 50)

    try:
        # Step 1: Triage (Orchestrator)
        orchestrator = OrchestratorAgent()
        triage_res = orchestrator.triage(issue)
        state.triage_result = triage_res
        state.status = "IN_PROGRESS"

        logger.log_handoff(
            agent="Orchestrator",
            event="triage_complete",
            iteration_count=0,
            status="IN_PROGRESS",
            input_summary=f"Issue #{issue.id}: {issue.title}",
            output_summary=f"Triage complete: classified as {triage_res.classification}",
            model=orchestrator.config["model"],
            provider=orchestrator.config["provider"],
        )
        print(f"[OK] Triage complete — classified as {triage_res.classification}.")
        yield state

        # Step 2: Bug Investigation (if BUG path)
        if triage_res.classification == "BUG":
            bug_agent = BugInvestigationAgent()
            bug_agent.analyze(state)
            print(f"[OK] Bug Investigation complete — identified root cause in {state.root_cause_report.file}:{state.root_cause_report.line_range}")
            yield state

        # Step 3: Requirements Analysis
        req_agent = RequirementsAnalysisAgent()
        req_agent.analyze(state)
        print(f"[OK] Requirements Analysis complete — scope: {state.requirements_spec.scope}")
        yield state

        # Step 4: Reflection Loop (Coding Assistant ⇄ Testing Agent ⇄ Code Reviewer)
        run_reflection_loop(state, session_id=session_id)
        yield state

        # Step 5: Documentation Writer (if review APPROVED)
        if state.review_result and state.review_result.decision == "APPROVED":
            doc_agent = DocumentationWriterAgent()
            doc_agent.write_documentation(state, session_id=session_id)
            print(f"[OK] Documentation Writer complete — changelog: {state.doc_updates.changelog_entry}")
            yield state

        return state

    except ValueError as cfg_err:
        state.status = "ERROR"
        logger.log_error(
            agent="Orchestrator",
            error_type="CONFIG_ERROR",
            message=str(cfg_err),
            details={"issue_id": issue.id},
        )
        print(f"[X] PIPELINE ERROR (CONFIG_ERROR): {cfg_err}", file=sys.stderr)
        yield state
        return state

    except Exception as llm_err:
        state.status = "ERROR"
        logger.log_error(
            agent="Orchestrator",
            error_type="LLM_ERROR",
            message=str(llm_err),
            details={"issue_id": issue.id},
        )
        print(f"[X] PIPELINE ERROR (LLM_ERROR): {llm_err}", file=sys.stderr)
        yield state
        return state


def resume_after_gate(
    state: SessionState,
    decision: str,
    feedback: Optional[str] = None
) -> SessionState:
    """Resumes pipeline execution after human gate decision [A/F/R].
    Enforces validate_assignment=True Pydantic reverse-dependency state clearing on REQUEST_CHANGES.
    """
    decision = decision.upper()
    state.gate_decision = decision
    state.human_feedback = feedback

    if decision == "REQUEST_CHANGES":
        print(f"[!] Human Gate requested changes: '{feedback}'. Resetting downstream state for fresh reflection pass...")
        # Reset gate_decision and downstream state in reverse dependency order
        state.gate_decision = None
        state.doc_updates = None
        state.review_result = None
        state.test_result = None
        state.patch = None
        state.iteration_count = 0  # Reset for fresh human-guided reflection pass
        state.status = "IN_PROGRESS"
        state.validate_handoff_chain()

        # Re-run reflection loop for fresh pass
        run_reflection_loop(state, session_id=state.session_id)

        # Re-run documentation writer if approved on retry
        if state.review_result and state.review_result.decision == "APPROVED":
            doc_agent = DocumentationWriterAgent()
            doc_agent.write_documentation(state, session_id=state.session_id)

        return state

    elif decision == "APPROVE":
        from agent_system.tools.github_write import create_pull_request
        from agent_system.tools.cleanup import cleanup_sandbox

        issue = state.issue
        pr_title = f"Fix issue #{issue.id}: {issue.title}" if (state.triage_result and state.triage_result.classification == "BUG") else f"Feature issue #{issue.id}: {issue.title}"
        pr_body = f"""### Multi-Agent Pipeline Resolution Summary

**Issue #{issue.id}**: {issue.title}
**Classification**: {state.triage_result.classification if state.triage_result else 'N/A'}

#### Requirements Scope
{state.requirements_spec.scope if state.requirements_spec else 'N/A'}

#### Test Results
- **Status**: {state.test_result.status if state.test_result else 'N/A'}
- **Passed**: {state.test_result.passed if state.test_result else 0}, **Failed**: {state.test_result.failed if state.test_result else 0}

#### Code Review Critique
{state.review_result.critique if state.review_result else 'N/A'}

#### Changelog Entry
{state.doc_updates.changelog_entry if state.doc_updates else 'N/A'}
"""
        pr_res = create_pull_request(branch=f"fix/issue-{issue.id}", title=pr_title, body=pr_body)
        if not isinstance(pr_res, Exception):
            from agent_system.persona.decorator import apply_persona
            pr_url = pr_res.get('html_url') if isinstance(pr_res, dict) else pr_res
            msg = apply_persona(f"[OK] Pull Request created successfully! URL: {pr_url}")
            print(msg)
        
        cleanup_sandbox(state.session_id)
        if state.doc_updates is not None:
            state.status = "READY"

    elif decision == "REJECT":
        from agent_system.tools.cleanup import cleanup_sandbox
        cleanup_sandbox(state.session_id)
        print(f"[OK] Session Rejected. Sandbox discarded, no PR created.")

    print(f"=== Session Finished with Gate Decision: {state.gate_decision} ===")
    return state


def run_pipeline(
    issue_path: str | Path,
    interactive_gate: bool = False,
    gate_choice_override: Optional[str] = "A"
) -> SessionState:
    """Load issue, initialize session, run pipeline through agents & human gate, and return updated SessionState."""
    gen = run_to_gate_generator(issue_path)
    state = None
    for s in gen:
        state = s

    if state.status == "ERROR":
        return state

    # Prompt decision at human gate (loops if REQUEST_CHANGES in interactive/test mode)
    while True:
        HumanGate.prompt_decision(state, interactive=interactive_gate, default_choice=gate_choice_override)
        if state.gate_decision:
            decision = state.gate_decision
            feedback = state.human_feedback
            state = resume_after_gate(state, decision, feedback=feedback)
            if decision == "REQUEST_CHANGES":
                continue
        break

    return state


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Multi-Agent Software Engineering CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    run_parser = subparsers.add_parser("run", help="Run the multi-agent pipeline on an issue payload")
    run_parser.add_argument("--issue", required=True, help="Path to issue JSON file (e.g. issues/bug_42.json)")
    run_parser.add_argument("--non-interactive", action="store_true", help="Run in non-interactive mode (defaults to Approve)")
    run_parser.add_argument("--gate-choice", choices=["A", "F", "R"], help="Default choice for gate decision in non-interactive mode")

    args = parser.parse_args(argv)

    if args.command == "run":
        try:
            interactive = not args.non_interactive
            gate_choice = args.gate_choice or ("A" if not interactive else None)
            run_pipeline(args.issue, interactive_gate=interactive, gate_choice_override=gate_choice)
        except Exception as e:
            print(f"Error running pipeline: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
