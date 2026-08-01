from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from openai import OpenAI

from agent_system.config.models import get_model_config
from agent_system.config.settings import Settings
from agent_system.schemas.state import DocUpdates, SessionState, ToolError
from agent_system.tools.repo_search import grep_search

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class DocumentationWriterAgent:
    """Documentation Writer Agent (Tier: lightweight).
    Runs after Code Reviewer APPROVAL (Guard 5).
    Uses Tool T-2 (grep_search) on sandbox files to locate functions/docstrings,
    and generates docstring diffs, README updates, and CHANGELOG entries.
    """

    def __init__(self, tier: str = "lightweight") -> None:
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

    def write_documentation(self, state: SessionState, session_id: str = "session_default") -> DocUpdates:
        """Generates documentation updates (docstring diffs, README diff, changelog entry)."""
        # Guard 5 Validation: review_result must be set and decision == "APPROVED"
        if state.review_result is None:
            raise ValueError("doc_updates requires review_result to be set first — Documentation Writer cannot run without code review.")
        if state.review_result.decision != "APPROVED":
            raise ValueError("doc_updates requires review_result.decision == 'APPROVED' — Documentation Writer runs only after code review approval.")

        sandbox_dir = PROJECT_ROOT / ".sandbox" / session_id
        target_dir = sandbox_dir if sandbox_dir.exists() else PROJECT_ROOT / "demo_repo"

        # Tool T-2: grep sandbox files for docstrings and def keywords
        grep_results = grep_search("def ", target_dir=target_dir)
        docstring_context = []
        if isinstance(grep_results, list):
            for match in grep_results[:5]:
                docstring_context.append(f"{match.get('file')}:{match.get('line_number')}: {match.get('content')}")

        client = self._get_client()

        prompt = f"""You are the Documentation Writer Agent of an automated software engineering pipeline.
Your task is to update project documentation (docstrings, README, CHANGELOG) based on the approved patch.

Issue Title: {state.issue.title}
Requirements Scope: {state.requirements_spec.scope if state.requirements_spec else ''}
Patch Explanation: {state.patch.explanation if state.patch else ''}

Codebase Def Context:
{json.dumps(docstring_context, indent=2)}

Return a valid JSON object matching this schema:
{{
  "docstring_diffs": ["diff string for updated docstrings in changed files"],
  "readme_diff": "Optional diff string or update text for README.md",
  "changelog_entry": "Markdown changelog bullet summarizing change (e.g. '- Fixed status filter bug in list_tasks()')"
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
                            "content": "You are a precise technical documentation writer. Always return pure JSON.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )

                content = response.choices[0].message.content or "{}"
                data = json.loads(content)

                docstring_diffs = data.get("docstring_diffs", [])
                if not isinstance(docstring_diffs, list):
                    docstring_diffs = [str(docstring_diffs)]
                
                readme_diff = data.get("readme_diff", None)
                if readme_diff is not None:
                    readme_diff = str(readme_diff)

                changelog_entry = data.get("changelog_entry", f"- {state.issue.title}")
                if changelog_entry is not None:
                    changelog_entry = str(changelog_entry)

                doc_updates = DocUpdates(
                    docstring_diffs=[str(x) for x in docstring_diffs],
                    readme_diff=readme_diff,
                    changelog_entry=changelog_entry,
                )

                state.doc_updates = doc_updates
                return doc_updates

            except Exception as err:
                last_exception = err
                err_msg = str(err)
                if "401" in err_msg or "Invalid API Key" in err_msg or "Missing environment variable" in err_msg:
                    raise RuntimeError(f"LLM API call failed for DocumentationWriterAgent: {err}") from err

                if attempt < max_retries:
                    delay = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                    time.sleep(delay)
                else:
                    raise RuntimeError(
                        f"DocumentationWriterAgent retry limit reached ({max_retries} attempts): {last_exception}"
                    ) from last_exception

        raise RuntimeError(f"DocumentationWriterAgent failed: {last_exception}")
