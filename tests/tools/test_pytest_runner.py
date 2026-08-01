import shutil
from pathlib import Path
from agent_system.tools.pytest_runner import setup_sandbox, apply_patch, run_pytest, run_pytest_in_sandbox, PROJECT_ROOT
from agent_system.schemas.state import ToolError


def test_setup_sandbox_success(tmp_path, monkeypatch):
    monkeypatch.setattr("agent_system.tools.pytest_runner.PROJECT_ROOT", PROJECT_ROOT)
    session_id = "test_setup_sandbox_12345"
    sandbox_path = setup_sandbox(session_id)
    
    assert not isinstance(sandbox_path, ToolError)
    assert sandbox_path.exists()
    assert (sandbox_path / "src" / "task_tracker" / "core.py").exists()
    
    shutil.rmtree(sandbox_path, ignore_errors=True)


def test_run_pytest_baseline(tmp_path):
    session_id = "test_pytest_baseline_12345"
    sandbox_path = setup_sandbox(session_id)
    
    result = run_pytest(sandbox_path)
    assert not isinstance(result, ToolError)
    assert result["status"] == "PASS"  # Baseline demo_repo tests pass
    assert result["passed"] > 0
    assert result["failed"] == 0
    
    shutil.rmtree(sandbox_path, ignore_errors=True)


def test_apply_patch_success(tmp_path, monkeypatch):
    session_id = "test_apply_patch_12345"
    sandbox_path = setup_sandbox(session_id)
    
    class MockProcess:
        returncode = 0
        stdout = ""
        stderr = ""

    def mock_run(*args, **kwargs):
        return MockProcess()

    monkeypatch.setattr("agent_system.tools.pytest_runner.subprocess.run", mock_run)
    
    res = apply_patch(sandbox_path, "fake diff")
    assert res is True
    
    shutil.rmtree(sandbox_path, ignore_errors=True)


def test_apply_patch_failure(monkeypatch):
    session_id = "test_apply_patch_fail_12345"
    sandbox_path = setup_sandbox(session_id)
    
    class MockProcess:
        returncode = 1
        stdout = ""
        stderr = "error: corrupt patch at line 10\n"

    def mock_run(*args, **kwargs):
        return MockProcess()

    monkeypatch.setattr("agent_system.tools.pytest_runner.subprocess.run", mock_run)
    
    res = apply_patch(sandbox_path, "invalid diff")
    assert isinstance(res, ToolError)
    assert res.tool == "T-3:pytest_runner"
    assert res.error_type == "PATCH_APPLY_FAILED"
    assert "Failed to apply patch" in res.message
    
    shutil.rmtree(sandbox_path, ignore_errors=True)


def test_run_pytest_in_sandbox_patch_failure_propagates_tool_error(monkeypatch):
    """Verify high-level run_pytest_in_sandbox propagates ToolError on git apply failure."""
    session_id = "test_wrapper_patch_fail_12345"

    class MockProcess:
        returncode = 1
        stdout = ""
        stderr = "error: patch does not apply\n"

    def mock_run(*args, **kwargs):
        return MockProcess()

    monkeypatch.setattr("agent_system.tools.pytest_runner.subprocess.run", mock_run)

    res = run_pytest_in_sandbox(session_id, patch_diff="invalid diff content")
    assert isinstance(res, ToolError)
    assert res.tool == "T-3:pytest_runner"
    assert res.error_type == "PATCH_APPLY_FAILED"

    # Cleanup sandbox
    sandbox_path = PROJECT_ROOT / ".sandbox" / session_id
    shutil.rmtree(sandbox_path, ignore_errors=True)


def test_run_pytest_in_sandbox_end_to_end():
    """Verify end-to-end sandbox creation and test execution."""
    session_id = "test_wrapper_e2e_12345"
    res = run_pytest_in_sandbox(session_id)
    
    assert not isinstance(res, ToolError)
    assert res["status"] == "PASS"
    assert res["passed"] > 0
    assert res["failed"] == 0

    # Cleanup sandbox
    sandbox_path = PROJECT_ROOT / ".sandbox" / session_id
    shutil.rmtree(sandbox_path, ignore_errors=True)


def test_run_pytest_unexpected_exit_code(monkeypatch):
    """Verify run_pytest returns ToolError on unexpected pytest exit code (e.g. exit 2)."""
    session_id = "test_pytest_err_code_12345"
    sandbox_path = setup_sandbox(session_id)

    class MockProcess:
        returncode = 2
        stdout = "Usage error"
        stderr = "pytest: error: invalid option"

    def mock_run(*args, **kwargs):
        return MockProcess()

    monkeypatch.setattr("agent_system.tools.pytest_runner.subprocess.run", mock_run)

    res = run_pytest(sandbox_path)
    assert isinstance(res, ToolError)
    assert res.tool == "T-3:pytest_runner"
    assert res.error_type == "PYTEST_EXECUTION_ERROR"
    assert "unexpected code 2" in res.message

    shutil.rmtree(sandbox_path, ignore_errors=True)
