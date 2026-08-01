from __future__ import annotations
from typing import Any, Dict, Optional

from agent_system.config.models import get_model_config
from agent_system.config.settings import Settings
from agent_system.schemas.state import SessionState, TestResult, ToolError
from agent_system.tools.pytest_runner import run_pytest_in_sandbox


class TestingAgent:
    """Testing Agent (Tier: lightweight).
    Applies generated patch to sandbox environment via Tool T-3 (run_pytest_in_sandbox)
    and collects structured pass/fail results and tracebacks.
    Per engineering.md §7.1, if tool fails (ToolError), sets test_result.status = "FAIL"
    with error traceback instead of crashing.
    """
    __test__ = False

    def __init__(self, tier: str = "lightweight") -> None:
        self.tier = tier
        self.config = get_model_config(tier)

    def run_tests(self, state: SessionState, session_id: str = "session_default") -> TestResult:
        """Runs pytest suite in isolated sandbox and records TestResult into state."""
        if state.patch is None:
            raise ValueError(
                "test_result requires patch to be set first — Testing Agent cannot run pytest without a patch to execute."
            )

        # Call Tool T-3 (Pytest Sandbox Runner)
        pytest_res = run_pytest_in_sandbox(session_id=session_id, patch_diff=state.patch.diff)

        if isinstance(pytest_res, ToolError):
            # Tool error handling per engineering.md §7.1:
            # Treat sandbox failure or pytest tool failure as test failure
            test_result = TestResult(
                status="FAIL",
                passed=0,
                failed=1,
                tracebacks=[f"Tool Error ({pytest_res.error_type}): {pytest_res.message}"]
            )
        else:
            status = pytest_res.get("status", "FAIL")
            passed = int(pytest_res.get("passed", 0))
            failed = int(pytest_res.get("failed", 0))
            tracebacks = pytest_res.get("tracebacks", [])
            if not isinstance(tracebacks, list):
                tracebacks = [str(tracebacks)]

            test_result = TestResult(
                status=status,
                passed=passed,
                failed=failed,
                tracebacks=[str(x) for x in tracebacks]
            )

        state.test_result = test_result
        return test_result
