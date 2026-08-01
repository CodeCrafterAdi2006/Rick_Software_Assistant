from __future__ import annotations
from typing import Optional

from agent_system.agents.coding_assistant import CodingAssistantAgent
from agent_system.agents.testing_agent import TestingAgent
from agent_system.agents.code_reviewer import CodeReviewerAgent
from agent_system.schemas.state import SessionState


def run_reflection_loop(
    state: SessionState,
    session_id: str = "session_default",
    max_iterations: int = 3,
    coding_agent: Optional[CodingAssistantAgent] = None,
    testing_agent: Optional[TestingAgent] = None,
    reviewer_agent: Optional[CodeReviewerAgent] = None,
) -> SessionState:
    """Executes the Reflection Loop (Coding Assistant ⇄ Testing Agent ⇄ Code Reviewer).
    Iterates up to max_iterations (default: 3).
    If review decision is APPROVED, the loop completes successfully.
    If max_iterations is reached without approval, sets state.status = 'PARTIAL'.
    """
    if coding_agent is None:
        coding_agent = CodingAssistantAgent()
    if testing_agent is None:
        testing_agent = TestingAgent()
    if reviewer_agent is None:
        reviewer_agent = CodeReviewerAgent()

    while state.iteration_count < max_iterations:
        state.iteration_count += 1

        # 1. Coding Assistant generates patch
        coding_agent.generate_patch(state)

        # 2. Testing Agent executes tests in sandbox
        test_res = testing_agent.run_tests(state, session_id=session_id)

        # If tests fail, retry loop if iterations remain
        if test_res.status == "FAIL":
            continue

        # 3. Code Reviewer reviews patch and linter output
        review_res = reviewer_agent.review(state, session_id=session_id)

        # If reviewer approves, reflection loop succeeds
        if review_res.decision == "APPROVED":
            break

    # If max iterations exhausted without approval, flag as PARTIAL
    if not state.review_result or state.review_result.decision != "APPROVED":
        if state.iteration_count >= max_iterations:
            state.status = "PARTIAL"

    return state
