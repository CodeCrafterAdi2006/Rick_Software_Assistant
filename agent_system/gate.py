from __future__ import annotations
import sys
from typing import Optional
from agent_system.schemas.state import SessionState
from agent_system.persona.decorator import apply_persona


class HumanGate:
    """Human Approval Gate Interface (Invariant I-1).
    Renders structured session summary and prompts human operator for gate decision:
    - [A] Approve: Proceeds to PR creation (Tool T-5).
    - [F] Request Changes: Injects human feedback and triggers single automated pass.
    - [R] Reject: Discards sandbox and terminates session without PR creation (Invariant I-3).
    """

    @staticmethod
    def render_summary(state: SessionState) -> str:
        """Renders formatted session summary string for CLI display."""
        lines = []
        lines.append("==================================================")
        header = apply_persona(f"HUMAN APPROVAL GATE SUMMARY: Issue #{state.issue.id} ({state.issue.title})")
        lines.append(f"           {header}")
        lines.append("==================================================")
        lines.append(f"Issue #{state.issue.id} : {state.issue.title}")
        lines.append(f"Author    : {state.issue.author}")
        lines.append(f"Labels    : {state.issue.labels}")
        if state.triage_result:
            lines.append(f"Triage    : {state.triage_result.classification} (Confidence: {state.triage_result.confidence:.2f})")
        
        if state.root_cause_report:
            lines.append(f"Root Cause: File {state.root_cause_report.file}:{state.root_cause_report.line_range}")
            lines.append(f"            Hypothesis: {state.root_cause_report.hypothesis}")

        if state.requirements_spec:
            lines.append(f"Req Scope : {state.requirements_spec.scope}")
            lines.append(f"Target Files: {state.requirements_spec.target_files}")

        if state.patch:
            lines.append(f"Patch Expl: {state.patch.explanation}")
            lines.append("--- Patch Diff Snippet ---")
            diff_lines = state.patch.diff.splitlines()[:10]
            lines.extend(diff_lines)
            if len(state.patch.diff.splitlines()) > 10:
                lines.append("... [diff truncated for display]")

        if state.test_result:
            lines.append(f"Test Run  : {state.test_result.status} (Passed: {state.test_result.passed}, Failed: {state.test_result.failed})")

        if state.review_result:
            lines.append(f"Code Review: {state.review_result.decision}")
            lines.append(f"Critique   : {state.review_result.critique}")

        if state.doc_updates:
            lines.append(f"Doc Updates: {state.doc_updates.changelog_entry}")

        lines.append(f"Iterations : {state.iteration_count}")
        lines.append(f"State Status: {state.status}")
        lines.append("==================================================")
        return "\n".join(lines)

    @staticmethod
    def prompt_decision(state: SessionState, interactive: bool = True, default_choice: Optional[str] = None) -> SessionState:
        """Prompts human operator for decision [A]/[F]/[R] in interactive mode, or uses default_choice in non-interactive/test mode."""
        print(HumanGate.render_summary(state))

        if state.status == "PARTIAL":
            print("\n[!] ATTENTION: Pipeline status is PARTIAL (Reflection loop cap reached). Human gate intervention required.")

        if not interactive or default_choice:
            choice = (default_choice or "A").strip().upper()
        else:
            print("\nPlease select a Gate Decision:")
            print("  [A] Approve         - Open Pull Request via GitHub API (Tool T-5)")
            print("  [F] Request Changes - Provide feedback & trigger automated retry pass")
            print("  [R] Reject          - Discard sandbox/branch & exit without PR")
            try:
                choice = input("Enter decision [A/F/R]: ").strip().upper()
            except (KeyboardInterrupt, EOFError):
                choice = "R"

        if choice.startswith("A"):
            state.gate_decision = "APPROVE"
            state.human_feedback = None
            print("[OK] Gate Decision: APPROVED.")
        elif choice.startswith("F"):
            state.gate_decision = "REQUEST_CHANGES"
            if interactive and not default_choice:
                try:
                    feedback = input("Enter feedback for Coding Assistant: ").strip()
                except (KeyboardInterrupt, EOFError):
                    feedback = "Please address code review feedback."
            else:
                feedback = "Please address code review feedback."
            state.human_feedback = feedback
            print(f"[OK] Gate Decision: REQUEST CHANGES. Feedback: '{feedback}'")
        elif choice.startswith("R"):
            state.gate_decision = "REJECT"
            state.human_feedback = None
            print("[OK] Gate Decision: REJECTED.")
        else:
            print("[!] Invalid choice. Defaulting to [R] Reject.")
            state.gate_decision = "REJECT"

        return state
