from pathlib import Path
from agent_system.tools.linter import run_ruff_linter
from agent_system.schemas.state import ToolError
from agent_system.tools.pytest_runner import PROJECT_ROOT


def test_linter_success():
    # Run linter on the demo_repo/src
    target_dir = PROJECT_ROOT / "demo_repo" / "src"
    
    issues = run_ruff_linter(target_dir)
    assert not isinstance(issues, ToolError)
    assert isinstance(issues, list)
    
    # Check the schema format of the returned issues
    for issue in issues:
        assert "rule_id" in issue
        assert "line" in issue
        assert "severity" in issue
        assert "message" in issue


def test_linter_invalid_dir():
    target_dir = PROJECT_ROOT / "demo_repo" / "nonexistent"
    
    res = run_ruff_linter(target_dir)
    assert isinstance(res, ToolError)
    assert res.error_type == "DIRECTORY_NOT_FOUND"
    assert res.tool == "T-4:linter"
