from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Root directory of the repository (parent of agent_system)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class SessionLogger:
    """Structured JSONL Logger adhering to NFR-1.
    Writes log entries for agent handoffs, tool calls, error events, and human gate decisions.
    """

    def __init__(self, session_id: str, log_dir: Optional[str] = None):
        self.session_id = session_id
        if log_dir is None:
            self.log_dir = PROJECT_ROOT / "logs"
        else:
            self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"session_{self.session_id}.jsonl"

    def _get_timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _append_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return entry

    def log_handoff(
        self,
        agent: str,
        event: str,
        iteration_count: int,
        status: str,
        input_summary: str,
        output_summary: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        duration_ms: int = 0,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Logs an agent handoff in/out event with summaries and tool calls."""
        entry = {
            "timestamp": self._get_timestamp(),
            "session_id": self.session_id,
            "agent": agent,
            "event": event,
            "iteration_count": iteration_count,
            "status": status,
            "input_summary": input_summary,
            "output_summary": output_summary,
            "tool_calls": tool_calls if tool_calls is not None else [],
            "duration_ms": duration_ms,
            "model": model,
            "provider": provider,
        }
        return self._append_entry(entry)

    def log_error(
        self,
        agent: str,
        error_type: str,
        message: str,
        retry_count: int = 0,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Logs an error event (e.g. LLM API failure, Pydantic ValidationError, sandbox failure)."""
        entry = {
            "timestamp": self._get_timestamp(),
            "session_id": self.session_id,
            "agent": agent,
            "event": "error",
            "error_type": error_type,
            "message": message,
            "retry_count": retry_count,
            "details": details if details is not None else {},
        }
        return self._append_entry(entry)

    def log_gate_decision(
        self,
        agent: str,
        gate_status: str,
        iteration_count: int,
        human_decision: str,
        duration_ms: int = 0,
    ) -> Dict[str, Any]:
        """Logs a human approval gate decision (APPROVE, REQUEST_CHANGES, REJECT)."""
        entry = {
            "timestamp": self._get_timestamp(),
            "session_id": self.session_id,
            "agent": agent,
            "event": "gate_decision",
            "gate_status": gate_status,
            "iteration_count": iteration_count,
            "human_decision": human_decision,
            "duration_ms": duration_ms,
        }
        return self._append_entry(entry)

    def read_entries(self) -> List[Dict[str, Any]]:
        """Reads all JSONL entries from the session log file."""
        if not self.log_file.exists():
            return []
        entries = []
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries
