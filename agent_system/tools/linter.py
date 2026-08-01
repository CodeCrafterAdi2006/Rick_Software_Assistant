import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Union

from agent_system.schemas.state import ToolError

# Anchored project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_ruff_linter(target_dir: Union[str, Path]) -> Union[List[Dict[str, Any]], ToolError]:
    """Runs Ruff linter on the target directory and returns structured LinterIssue dicts."""
    target_path = Path(target_dir)
    
    if not target_path.exists():
        return ToolError(
            tool="T-4:linter",
            error_type="DIRECTORY_NOT_FOUND",
            message=f"Linter target directory not found: {target_path}",
            details={"target_dir": str(target_dir)}
        )

    ruff_bin = PROJECT_ROOT / ".venv" / "Scripts" / "ruff"
    if os.name == 'nt':
        ruff_bin = ruff_bin.with_suffix('.exe')
    if not ruff_bin.exists():
        import shutil
        found = shutil.which("ruff")
        if found:
            ruff_bin = Path(found)
        else:
            ruff_bin = Path("ruff")

    try:
        process = subprocess.run(
            [str(ruff_bin), "check", str(target_path), "--output-format=json"],
            capture_output=True,
            text=True,
        )
        
        # ruff returns 0 if no violations, 1 if violations found, 2 for other errors
        if process.returncode not in (0, 1):
            return ToolError(
                tool="T-4:linter",
                error_type="RUFF_EXECUTION_ERROR",
                message=f"Ruff exited with code {process.returncode}: {process.stderr}",
                details={"stdout": process.stdout, "stderr": process.stderr}
            )

        if not process.stdout.strip():
            return []

        # Parse JSON output
        try:
            issues = json.loads(process.stdout)
        except json.JSONDecodeError as e:
            return ToolError(
                tool="T-4:linter",
                error_type="RUFF_JSON_PARSE_ERROR",
                message=f"Failed to parse ruff output: {e}",
                details={"stdout": process.stdout}
            )

        linter_issues = []
        for issue in issues:
            # Map ruff severity to our schema
            # ruff doesn't give severity natively via json without mapping rules, but we can assume warnings vs errors based on rule prefixes
            # For simplicity: E/F=error, W=warning, I=info (or map to warning)
            rule = issue.get("code", "UNKNOWN")
            if rule.startswith("E") or rule.startswith("F"):
                severity = "error"
            elif rule.startswith("W"):
                severity = "warning"
            else:
                severity = "info"

            linter_issues.append({
                "rule_id": rule,
                "line": issue.get("location", {}).get("row", 1),
                "severity": severity,
                "message": issue.get("message", "Unknown error")
            })

        return linter_issues

    except Exception as e:
        return ToolError(
            tool="T-4:linter",
            error_type="UNHANDLED_LINTER_ERROR",
            message=f"Linter execution failed: {e}",
            details={}
        )
