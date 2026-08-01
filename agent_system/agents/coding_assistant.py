from __future__ import annotations
import json
import time
from typing import Any, Dict, List, Optional
from openai import OpenAI

from agent_system.config.models import get_model_config
from agent_system.config.settings import Settings
from agent_system.schemas.state import PatchResult, SessionState
from agent_system.tools.repo_search import grep_search
from agent_system.schemas.state import ToolError


class CodingAssistantAgent:
    """Coding Assistant Agent (Tier: heavy).
    Generates code patches (unified diff format) satisfying the RequirementsSpec.
    Uses Tool T-2 (grep_search) to inspect target codebase files.
    Incorporates feedback from previous test failures or reviewer critiques during reflection loop retries.
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

    def generate_patch(self, state: SessionState) -> PatchResult:
        """Generates unified diff patch fulfilling requirements spec and reflection feedback."""
        if state.requirements_spec is None:
            raise ValueError("patch requires requirements_spec to be set first — Coding Assistant cannot generate a patch without a requirements spec.")

        spec = state.requirements_spec
        issue = state.issue
        
        # Grep search over target files for extra context
        grep_context = []
        for file in spec.target_files:
            grep_res = grep_search("def ", target_dir=None, file_pattern=f"*{file.split('/')[-1]}")
            if isinstance(grep_res, list):
                for match in grep_res[:5]:
                    grep_context.append(f"{match.get('file')}:{match.get('line_number')}: {match.get('content')}")

        # Feedback from previous iterations if retrying loop
        feedback_context = ""
        if state.test_result and state.test_result.status == "FAIL":
            feedback_context += f"\nPrevious Test Failure Tracebacks:\n" + "\n".join(state.test_result.tracebacks)
        if state.review_result and state.review_result.decision == "CHANGES_NEEDED":
            feedback_context += f"\nPrevious Code Review Critique:\n{state.review_result.critique}\nLinter Warnings: {state.review_result.linter_output}"

        client = self._get_client()

        prompt = f"""You are the Coding Assistant Agent of an automated software engineering pipeline.
Generate a valid unified diff patch that satisfies the requirements specification.

Issue Title: {issue.title}
Requirements Scope: {spec.scope}
Acceptance Criteria:
{json.dumps(spec.acceptance_criteria, indent=2)}
Target Files: {spec.target_files}

Code Snippet Context:
{json.dumps(grep_context, indent=2)}
{feedback_context}

Return a valid JSON object matching this schema:
{{
  "diff": "unified diff format string starting with 'diff --git a/... b/...'",
  "changed_files": ["list/of/changed_files.py"],
  "explanation": "Concise summary of code modifications made"
}}
"""

        max_retries = self.retry_policy.get("max_retries", 3)
        backoff_delays = self.retry_policy.get("backoff_delays_sec", [0.5, 1.0, 2.0])

        last_exception: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=self.config["model"],
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert Python software engineer. Always return pure JSON with valid unified diffs.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )

                content = response.choices[0].message.content or "{}"
                data = json.loads(content)

                diff = str(data.get("diff", ""))
                changed_files = data.get("changed_files", spec.target_files)
                if not isinstance(changed_files, list):
                    changed_files = spec.target_files
                explanation = str(data.get("explanation", "Patch generated."))

                patch_result = PatchResult(
                    diff=diff,
                    changed_files=[str(x) for x in changed_files],
                    explanation=explanation,
                )

                state.patch = patch_result
                return patch_result

            except Exception as err:
                last_exception = err
                err_msg = str(err)
                if "401" in err_msg or "Invalid API Key" in err_msg or "Missing environment variable" in err_msg:
                    raise RuntimeError(f"LLM API call failed for CodingAssistantAgent: {err}") from err

                if attempt < max_retries:
                    delay = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                    time.sleep(delay)
                else:
                    raise RuntimeError(
                        f"CodingAssistantAgent retry limit reached ({max_retries} attempts): {last_exception}"
                    ) from last_exception

        raise RuntimeError(f"CodingAssistantAgent failed: {last_exception}")
