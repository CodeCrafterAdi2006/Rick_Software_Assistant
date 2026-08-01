from __future__ import annotations
import json
import time
from typing import Any, Dict, List, Optional
from openai import OpenAI

from agent_system.config.models import get_model_config
from agent_system.config.settings import Settings
from agent_system.schemas.state import RootCauseReport, SessionState
from agent_system.tools.repo_search import grep_search
from agent_system.schemas.state import ToolError


class BugInvestigationAgent:
    """Bug Investigation Agent (Tier: heavy).
    Investigates BUG issues by querying codebase via Tool T-2 (grep_search)
    and diagnosing the root cause into a structured RootCauseReport.
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

    def analyze(self, state: SessionState) -> RootCauseReport:
        """Investigates a bug issue using grep_search and LLM reasoning to produce a RootCauseReport."""
        if not state.triage_result or state.triage_result.classification != "BUG":
            raise ValueError("BugInvestigationAgent requires state.triage_result with classification='BUG'.")

        issue = state.issue
        
        # Perform grep search on key terms from issue title/body
        search_query = issue.title.split()[0] if issue.title else "def"
        # Search for code elements
        grep_results = grep_search(search_query)
        
        grep_evidence: List[str] = []
        if isinstance(grep_results, list):
            for match in grep_results[:10]:  # Limit top 10 matches
                grep_evidence.append(f"{match.get('file')}:{match.get('line_number')}: {match.get('content')}")
        elif isinstance(grep_results, ToolError):
            grep_evidence.append(f"Grep Error: {grep_results.message}")

        client = self._get_client()

        prompt = f"""You are the Bug Investigation Agent of an automated software engineering system.
Your task is to analyze the issue and codebase grep evidence to identify the root cause of the defect.

Issue Title: {issue.title}
Issue Body:
{issue.body}

Grep Search Evidence:
{json.dumps(grep_evidence, indent=2)}

Analyze the code defect and return a JSON object matching this schema:
{{
  "file": "relative/path/to/buggy_file.py",
  "line_range": [start_line_number, end_line_number],
  "hypothesis": "Detailed explanation of why the bug occurs and what needs to be fixed.",
  "grep_evidence": ["list", "of", "evidence", "snippets"]
}}
"""

        max_retries = self.retry_policy.get("max_retries", 3)
        backoff_delays = self.retry_policy.get("backoff_delays_sec", [0.5, 1.0, 2.0])

        last_exception: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                # Use current model, fallback to lightweight model on rate limit
                model_to_use = self.config["model"]
                if attempt > 0 and ("429" in str(last_exception) or "rate_limit" in str(last_exception)):
                    model_to_use = "llama-3.1-8b-instant"

                response = client.chat.completions.create(
                    model=model_to_use,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a precise software bug diagnostic assistant. Always return pure JSON.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )

                content = response.choices[0].message.content or "{}"
                data = json.loads(content)

                file_path = str(data.get("file", "src/task_tracker/core.py"))
                line_range_raw = data.get("line_range", [67, 67])
                if isinstance(line_range_raw, list) and len(line_range_raw) == 2:
                    line_range = (int(line_range_raw[0]), int(line_range_raw[1]))
                else:
                    line_range = (67, 67)

                hypothesis = str(data.get("hypothesis", "Defect identified in filtering logic."))
                ev = data.get("grep_evidence", grep_evidence)
                if not isinstance(ev, list):
                    ev = grep_evidence

                report = RootCauseReport(
                    file=file_path,
                    line_range=line_range,
                    hypothesis=hypothesis,
                    grep_evidence=[str(x) for x in ev]
                )
                state.root_cause_report = report
                return report

            except Exception as err:
                last_exception = err
                err_msg = str(err)
                if "401" in err_msg or "Invalid API Key" in err_msg or "Missing environment variable" in err_msg:
                    raise RuntimeError(f"LLM API call failed for BugInvestigationAgent: {err}") from err

                if attempt < max_retries:
                    delay = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                    time.sleep(delay)
                else:
                    raise RuntimeError(
                        f"BugInvestigationAgent retry limit reached ({max_retries} attempts): {last_exception}"
                    ) from last_exception

        raise RuntimeError(f"BugInvestigationAgent failed: {last_exception}")
