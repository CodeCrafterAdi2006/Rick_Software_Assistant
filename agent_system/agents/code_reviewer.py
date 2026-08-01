from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from openai import OpenAI

from agent_system.config.models import get_model_config
from agent_system.config.settings import Settings
from agent_system.schemas.state import LinterIssue, ReviewResult, SessionState, ToolError
from agent_system.tools.linter import run_ruff_linter

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class CodeReviewerAgent:
    """Code Reviewer Agent (Tier: heavy).
    Evaluates generated patch using Tool T-4 (run_ruff_linter) and LLM critique over requirements spec,
    patch diff, and test results.
    Produces ReviewResult with decision ("APPROVED" or "CHANGES_NEEDED").
    """

    def __init__(self, tier: str = "heavy") -> None:
        self.tier = tier
        self.config = get_model_config(tier)
        self.retry_policy = Settings.get_retry_policy()

    def _get_client(self) -> OpenAI:
        api_key_env = self.config["api_key_env"]
        api_key = Settings.get_api_key(api_key_env)
        if not api_key:
            raise ValueError(
                f"Missing environment variable '{api_key_env}' for model tier '{self.tier}'."
            )
        return OpenAI(
            base_url=self.config["base_url"],
            api_key=api_key,
        )

    def review(self, state: SessionState, session_id: str = "session_default") -> ReviewResult:
        """Runs linter tool on sandbox and performs LLM code review."""
        if state.test_result is None:
            raise ValueError(
                "review_result requires test_result to be set first — Code Reviewer cannot evaluate a patch until test results are present."
            )

        sandbox_dir = PROJECT_ROOT / ".sandbox" / session_id
        if not sandbox_dir.exists():
            target_dir = PROJECT_ROOT / "demo_repo" / "src"
        else:
            target_dir = sandbox_dir / "src"

        # Execute Tool T-4 (Linter)
        lint_res = run_ruff_linter(target_dir=target_dir)

        linter_issues: List[LinterIssue] = []
        if isinstance(lint_res, list):
            for issue in lint_res:
                linter_issues.append(
                    LinterIssue(
                        rule_id=str(issue.get("rule_id", "UNKNOWN")),
                        line=int(issue.get("line", 1)),
                        severity=issue.get("severity", "warning"),
                        message=str(issue.get("message", "Lint warning")),
                    )
                )

        client = self._get_client()

        prompt = f"""You are the Code Reviewer Agent of an automated software engineering pipeline.
Review the following code patch against the requirements specification, test results, and linter output.

Requirements Scope: {state.requirements_spec.scope if state.requirements_spec else 'N/A'}
Acceptance Criteria: {state.requirements_spec.acceptance_criteria if state.requirements_spec else []}
Patch Diff:
{state.patch.diff if state.patch else ''}

Test Result Status: {state.test_result.status}
Passed: {state.test_result.passed}, Failed: {state.test_result.failed}
Test Tracebacks: {state.test_result.tracebacks}

Linter Violations Count: {len(linter_issues)}

Decide whether to APPROVE or request CHANGES_NEEDED.
Return a valid JSON object matching this schema:
{{
  "decision": "APPROVED" or "CHANGES_NEEDED",
  "critique": "Detailed code review critique explaining approval or requested changes."
}}
"""

        max_retries = self.retry_policy.get("max_retries", 3)
        backoff_delays = self.retry_policy.get("backoff_delays_sec", [0.5, 1.0, 2.0])

        last_exception: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                model_to_use = self.config["model"]
                if attempt > 0 and ("429" in str(last_exception) or "rate_limit" in str(last_exception)):
                    model_to_use = "llama-3.1-8b-instant"

                response = client.chat.completions.create(
                    model=model_to_use,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a thorough Python code reviewer. Always return pure JSON.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )

                content = response.choices[0].message.content or "{}"
                data = json.loads(content)

                decision = str(data.get("decision", "APPROVED")).upper()
                if decision not in ("APPROVED", "CHANGES_NEEDED"):
                    decision = "APPROVED"

                critique = str(data.get("critique", "Code review completed."))

                review_result = ReviewResult(
                    decision=decision,  # type: ignore[arg-type]
                    linter_output=linter_issues,
                    critique=critique,
                )

                state.review_result = review_result
                return review_result

            except Exception as err:
                last_exception = err
                err_msg = str(err)
                if "401" in err_msg or "Invalid API Key" in err_msg or "Missing environment variable" in err_msg:
                    raise RuntimeError(f"LLM API call failed for CodeReviewerAgent: {err}") from err

                if attempt < max_retries:
                    delay = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                    time.sleep(delay)
                else:
                    raise RuntimeError(
                        f"CodeReviewerAgent retry limit reached ({max_retries} attempts): {last_exception}"
                    ) from last_exception

        raise RuntimeError(f"CodeReviewerAgent failed: {last_exception}")
