from __future__ import annotations
import json
import time
from typing import Optional
from openai import OpenAI, APIError, APIConnectionError, RateLimitError

from agent_system.config.models import get_model_config
from agent_system.config.settings import Settings
from agent_system.schemas.state import IssuePayload, TriageResult


class OrchestratorAgent:
    """Orchestrator / Triage Agent responsible for classifying incoming issues into BUG or FEATURE."""

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

    def triage(self, issue: IssuePayload) -> TriageResult:
        """Classify issue payload into BUG or FEATURE via LLM inference with retry policy."""
        client = self._get_client()

        prompt = f"""You are the Orchestrator/Triage Agent of an automated software engineering pipeline.
Analyze the following GitHub Issue and classify it as either "BUG" (a defect, crash, unexpected behavior, or inconsistency) or "FEATURE" (a request for new functionality or enhancement).

Issue Title: {issue.title}
Issue Labels: {issue.labels}
Issue Author: {issue.author}
Issue Body:
{issue.body}

Return a valid JSON object matching this schema:
{{
  "classification": "BUG" or "FEATURE",
  "confidence": float between 0.00 and 1.00,
  "routing_note": "A concise explanation of why this classification was chosen."
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
                            "content": "You are a precise issue triage assistant. Always return pure JSON.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )

                content = response.choices[0].message.content or "{}"
                data = json.loads(content)

                classification = str(data.get("classification", "BUG")).upper()
                if classification not in ("BUG", "FEATURE"):
                    classification = "BUG"

                confidence = float(data.get("confidence", 0.90))
                routing_note = str(
                    data.get("routing_note", "Triage completed via LLM analysis.")
                )

                return TriageResult(
                    classification=classification,  # type: ignore[arg-type]
                    confidence=confidence,
                    routing_note=routing_note,
                )

            except Exception as err:
                last_exception = err

                # Non-retryable errors (missing config or 401 invalid key) fail immediately
                err_msg = str(err)
                if "401" in err_msg or "Invalid API Key" in err_msg or "Missing environment variable" in err_msg:
                    raise RuntimeError(f"LLM API call failed for Orchestrator triage: {err}") from err

                # If attempts remaining, sleep with exponential backoff per engineering.md §7.1
                if attempt < max_retries:
                    delay = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                    time.sleep(delay)
                else:
                    break

        raise RuntimeError(
            f"LLM API call failed after {max_retries} retries for Orchestrator triage: {last_exception}"
        ) from last_exception
