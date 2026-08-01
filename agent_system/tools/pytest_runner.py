import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Union

from agent_system.schemas.state import ToolError

# Anchored project root (parent of agent_system)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def setup_sandbox(session_id: str) -> Union[Path, ToolError]:
    """Copies demo_repo/ to .sandbox/{session_id}/."""
    sandbox_base = PROJECT_ROOT / ".sandbox"
    target_sandbox = sandbox_base / session_id
    demo_repo = PROJECT_ROOT / "demo_repo"

    try:
        # Create base sandbox dir if it doesn't exist
        sandbox_base.mkdir(parents=True, exist_ok=True)
        
        # If this session's sandbox already exists, we remove it to start fresh.
        # Although per engineering.md, we might overwrite, copytree requires the dst to not exist
        # or we use dirs_exist_ok=True. We'll use dirs_exist_ok=True to overwrite in place.
        if target_sandbox.exists():
            shutil.rmtree(target_sandbox)
            
        shutil.copytree(demo_repo, target_sandbox)
        subprocess.run(["git", "init"], cwd=target_sandbox, capture_output=True)
        return target_sandbox
    except Exception as e:
        return ToolError(
            tool="T-3:pytest_runner",
            error_type="SANDBOX_CREATION_FAILED",
            message=f"Failed to copy demo_repo to sandbox: {e}",
            details={"session_id": session_id}
        )


def apply_patch(sandbox_dir: Path, diff: str) -> Union[bool, ToolError]:
    """Applies a git patch to the sandbox directory."""
    try:
        diff_text = diff.strip()
        if not diff_text:
            return True

        # Clean leading whitespace before diff headers if LLM prepended space/newlines
        raw_lines = diff_text.splitlines()
        lines = []
        for line in raw_lines:
            if line.lstrip().startswith("diff --git"):
                lines.append(line.lstrip())
            else:
                lines.append(line)

        # Normalize LLM diff headers if missing a/ and b/ prefixes
        normalized_lines = []
        for line in lines:
            if line.startswith("--- ") and not line.startswith("--- a/"):
                filepath = line[4:].strip()
                normalized_lines.append(f"--- a/{filepath.lstrip('/')}")
            elif line.startswith("+++ ") and not line.startswith("+++ b/"):
                filepath = line[4:].strip()
                normalized_lines.append(f"+++ b/{filepath.lstrip('/')}")
            else:
                normalized_lines.append(line)
        
        normalized_diff = "\n".join(normalized_lines) + "\n"

        process = subprocess.run(
            ["git", "apply", "--ignore-space-change", "--ignore-whitespace", "--recount", "--unidiff-zero"],
            input=normalized_diff,
            text=True,
            cwd=sandbox_dir,
            capture_output=True,
        )
        if process.returncode != 0:
            # Fallback retry without unidiff-zero if needed
            process = subprocess.run(
                ["git", "apply", "--ignore-space-change", "--ignore-whitespace", "--recount"],
                input=diff,
                text=True,
                cwd=sandbox_dir,
                capture_output=True,
            )

        if process.returncode != 0:
            return ToolError(
                tool="T-3:pytest_runner",
                error_type="PATCH_APPLY_FAILED",
                message=f"Failed to apply patch: {process.stderr}",
                details={"stdout": process.stdout, "stderr": process.stderr}
            )
        return True
    except Exception as e:
        return ToolError(
            tool="T-3:pytest_runner",
            error_type="PATCH_APPLY_ERROR",
            message=f"Exception during patch application: {e}",
            details={}
        )


def run_pytest(sandbox_dir: Path) -> Union[Dict[str, Any], ToolError]:
    """Runs pytest inside the sandbox and returns structured output."""
    try:
        # Resolve pytest path from the active environment
        pytest_bin = PROJECT_ROOT / ".venv" / "Scripts" / "pytest"
        if os.name == 'nt':
            pytest_bin = pytest_bin.with_suffix('.exe')
        if not pytest_bin.exists():
            import shutil
            found = shutil.which("pytest")
            if found:
                pytest_bin = Path(found)
            else:
                pytest_bin = Path("pytest")  # Fallback to PATH if not in typical Windows .venv location
            
        process = subprocess.run(
            [str(pytest_bin), "-q", "--tb=short"],
            cwd=sandbox_dir,
            capture_output=True,
            text=True,
        )
        
        # Parse output for passed/failed counts and tracebacks
        output = process.stdout + "\n" + process.stderr
        
        passed = 0
        failed = 0
        tracebacks = []
        
        if " passed" in output:
            import re
            m = re.search(r'(\d+) passed', output)
            if m:
                passed = int(m.group(1))
        if " failed" in output:
            import re
            m = re.search(r'(\d+) failed', output)
            if m:
                failed = int(m.group(1))
                
        # Basic status extraction
        if process.returncode == 0:
            status = "PASS"
        elif process.returncode == 1:
            status = "FAIL"
            # Extract basic tb
            if "FAILURES" in output:
                tracebacks.append(output.split("FAILURES")[-1].strip())
            else:
                tracebacks.append(output)
        else:
            # Pytest returns 2 for usage error, 3 for internal error, 4 for command line error, 5 for no tests collected
            return ToolError(
                tool="T-3:pytest_runner",
                error_type="PYTEST_EXECUTION_ERROR",
                message=f"Pytest exited with unexpected code {process.returncode}",
                details={"stdout": process.stdout, "stderr": process.stderr}
            )
            
        return {
            "status": status,
            "passed": passed,
            "failed": failed,
            "tracebacks": tracebacks
        }
    except Exception as e:
        return ToolError(
            tool="T-3:pytest_runner",
            error_type="PYTEST_SYSTEM_ERROR",
            message=f"Failed to run pytest subprocess: {e}",
            details={}
        )


def run_pytest_in_sandbox(session_id: str, patch_diff: Optional[str] = None) -> Union[Dict[str, Any], ToolError]:
    """Sets up sandbox, applies patch (if provided), and runs pytest."""
    sandbox_dir = setup_sandbox(session_id)
    if isinstance(sandbox_dir, ToolError):
        return sandbox_dir
        
    if patch_diff:
        patch_res = apply_patch(sandbox_dir, patch_diff)
        if isinstance(patch_res, ToolError):
            return patch_res
            
    return run_pytest(sandbox_dir)
