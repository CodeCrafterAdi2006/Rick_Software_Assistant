from __future__ import annotations
import json
import time
from typing import Any, Dict, List, Optional
from openai import OpenAI

from agent_system.config.models import get_model_config
from agent_system.config.settings import Settings
from agent_system.schemas.state import RequirementsSpec, SessionState


class RequirementsAnalysisAgent:
    """Requirements Analysis Agent (Tier: heavy).
    Analyzes issues (and RootCauseReport if BUG) to produce a structured RequirementsSpec.
    Enforces Guard #1: requirements_spec cannot be created if triage_result is None.
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

    def analyze(self, state: SessionState) -> RequirementsSpec:
        """Generates RequirementsSpec from issue (and root cause report if available)."""
        # Guard #1 Validation: triage_result must be set before requirements analysis runs
        if state.triage_result is None:
            raise ValueError(
                "requirements_spec requires triage_result to be set first — "
                "Orchestrator must classify the issue before Requirements Analysis runs."
            )

        issue = state.issue
        classification = state.triage_result.classification
        root_cause = state.root_cause_report

        bug_context = ""
        if classification == "BUG" and root_cause:
            bug_context = f"""
Root Cause Report:
- Target File: {root_cause.file}
- Target Lines: {root_cause.line_range}
- Hypothesis: {root_cause.hypothesis}
- Evidence Snippets: {root_cause.grep_evidence}
"""

        prompt = f"""You are the Requirements Analysis Agent of an automated software engineering system.
Analyze the following issue and produce a clear, binary-testable requirements specification.

Issue Title: {issue.title}
Classification: {classification}
Issue Body:
{issue.body}
{bug_context}

Return a valid JSON object matching this schema:
{{
  "scope": "Clear description of the scope of changes required",
  "acceptance_criteria": [
    "Binary testable assertion 1",
    "Binary testable assertion 2"
  ],
  "target_files": [
    "relative/path/to/target_file.py"
  ],
  "out_of_scope": [
    "Optional items explicitly out of scope"
  ]
}}
"""

        client = self._get_client()
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
                            "content": "You are a precise software requirements analyst. Always return pure JSON.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )

                content = response.choices[0].message.content or "{}"
                data = json.loads(content)

                scope = str(data.get("scope", f"Implement fix/feature for {issue.title}"))
                acc_crit = data.get("acceptance_criteria", ["Issue issue resolution verified via tests."])
                if not isinstance(acc_crit, list):
                    acc_crit = [str(acc_crit)]
                
                target_files = data.get("target_files", [root_cause.file if root_cause else "src/task_tracker/core.py"])
                if not isinstance(target_files, list):
                    target_files = [str(target_files)]

                out_of_scope = data.get("out_of_scope", [])
                if not isinstance(out_of_scope, list):
                    out_of_scope = []

                spec = RequirementsSpec(
                    scope=scope,
                    acceptance_criteria=[str(x) for x in acc_crit],
                    target_files=[str(x) for x in target_files],
                    out_of_scope=[str(x) for x in out_of_scope],
                )
                
                state.requirements_spec = spec
                return spec

            except Exception as err:
                last_exception = err
                err_msg = str(err)
                if "401" in err_msg or "Invalid API Key" in err_msg or "Missing environment variable" in err_msg:
                    raise RuntimeError(f"LLM API call failed for RequirementsAnalysisAgent: {err}") from err

                if attempt < max_retries:
                    delay = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                    time.sleep(delay)
                else:
                    raise RuntimeError(
                        f"RequirementsAnalysisAgent retry limit reached ({max_retries} attempts): {last_exception}"
                    ) from last_exception

        raise RuntimeError(f"RequirementsAnalysisAgent failed: {last_exception}")
