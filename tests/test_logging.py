import json
import pytest
from pathlib import Path
from agent_system.logging.session_log import SessionLogger, PROJECT_ROOT


def test_logger_initialization_and_path(tmp_path):
    logger = SessionLogger(session_id="run-test123", log_dir=str(tmp_path))
    assert logger.session_id == "run-test123"
    assert logger.log_file.name == "session_run-test123.jsonl"


def test_default_log_dir_anchors_to_project_root():
    logger = SessionLogger(session_id="run-test-default")
    try:
        assert logger.log_dir == PROJECT_ROOT / "logs"
        assert logger.log_file == PROJECT_ROOT / "logs" / "session_run-test-default.jsonl"
    finally:
        if logger.log_file.exists():
            logger.log_file.unlink()


def test_log_handoff_format(tmp_path):
    logger = SessionLogger(session_id="run-test123", log_dir=str(tmp_path))
    
    entry = logger.log_handoff(
        agent="coding_assistant",
        event="handoff_out",
        iteration_count=1,
        status="IN_PROGRESS",
        input_summary="RequirementsSpec: 3 criteria",
        output_summary="PatchResult: +2 lines",
        tool_calls=[{"tool": "repo_search", "query": "list_tasks", "results_count": 3}],
        duration_ms=4812,
        model="gemini-2.5-flash",
        provider="google",
    )

    assert entry["session_id"] == "run-test123"
    assert entry["agent"] == "coding_assistant"
    assert entry["event"] == "handoff_out"
    assert entry["iteration_count"] == 1
    assert entry["status"] == "IN_PROGRESS"
    assert entry["input_summary"] == "RequirementsSpec: 3 criteria"
    assert entry["output_summary"] == "PatchResult: +2 lines"
    assert len(entry["tool_calls"]) == 1
    assert entry["tool_calls"][0]["tool"] == "repo_search"
    assert entry["model"] == "gemini-2.5-flash"
    assert entry["provider"] == "google"

    # Verify written file content is valid JSON line with matching summaries
    with open(logger.log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["agent"] == "coding_assistant"
        assert data["input_summary"] == "RequirementsSpec: 3 criteria"
        assert data["output_summary"] == "PatchResult: +2 lines"


def test_log_error_format(tmp_path):
    logger = SessionLogger(session_id="run-test123", log_dir=str(tmp_path))

    entry = logger.log_error(
        agent="coding_assistant",
        error_type="LLM_API_ERROR",
        message="429 Rate Limit Exceeded on Gemini 2.5 Flash",
        retry_count=3,
        details={"provider": "google", "model": "gemini-2.5-flash"},
    )

    assert entry["session_id"] == "run-test123"
    assert entry["agent"] == "coding_assistant"
    assert entry["event"] == "error"
    assert entry["error_type"] == "LLM_API_ERROR"
    assert entry["message"] == "429 Rate Limit Exceeded on Gemini 2.5 Flash"
    assert entry["retry_count"] == 3
    assert entry["details"]["provider"] == "google"


def test_log_gate_decision_format(tmp_path):
    logger = SessionLogger(session_id="run-test123", log_dir=str(tmp_path))
    
    entry = logger.log_gate_decision(
        agent="orchestrator",
        gate_status="READY",
        iteration_count=1,
        human_decision="APPROVE",
        duration_ms=0,
    )

    assert entry["session_id"] == "run-test123"
    assert entry["event"] == "gate_decision"
    assert entry["gate_status"] == "READY"
    assert entry["human_decision"] == "APPROVE"


def test_read_entries(tmp_path):
    logger = SessionLogger(session_id="run-test123", log_dir=str(tmp_path))
    
    logger.log_handoff(
        agent="orchestrator",
        event="handoff_in",
        iteration_count=0,
        status="IN_PROGRESS",
        input_summary="Issue #42 ingested",
        output_summary="Classified as BUG",
    )
    
    logger.log_error(
        agent="coding_assistant",
        error_type="SANDBOX_ERROR",
        message="git apply failed",
        retry_count=1,
    )

    logger.log_gate_decision(
        agent="orchestrator",
        gate_status="READY",
        iteration_count=1,
        human_decision="APPROVE",
    )

    entries = logger.read_entries()
    assert len(entries) == 3
    assert entries[0]["agent"] == "orchestrator"
    assert entries[1]["event"] == "error"
    assert entries[1]["error_type"] == "SANDBOX_ERROR"
    assert entries[2]["human_decision"] == "APPROVE"
