import json
import os
from pathlib import Path
from typing import Any, Dict, Union
import urllib.request
import urllib.error

from agent_system.config.settings import Settings
from agent_system.schemas.state import ToolError

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def fetch_issue(issue_number: int) -> Union[Dict[str, Any], ToolError]:
    """Fetches an issue payload. Mocks offline locally if GITHUB_LIVE_MODE is False."""
    live_mode = Settings.is_github_live_mode()

    if live_mode:
        token = Settings.get_api_key("GITHUB_TOKEN")
        if not token:
            return ToolError(
                tool="T-1:github_read",
                error_type="MISSING_GITHUB_TOKEN",
                message="GITHUB_LIVE_MODE is true but GITHUB_TOKEN is not set.",
                details={}
            )
        
        # Real HTTP request logic (simplified for the scope)
        req = urllib.request.Request(f"https://api.github.com/repos/demo/demo_repo/issues/{issue_number}")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Accept", "application/vnd.github+json")
        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            return ToolError(
                tool="T-1:github_read",
                error_type="GITHUB_API_ERROR",
                message=f"HTTP {e.code}: {e.reason}",
                details={"url": req.full_url}
            )
        except Exception as e:
            return ToolError(
                tool="T-1:github_read",
                error_type="NETWORK_ERROR",
                message=str(e),
                details={}
            )

    # Offline Mock Mode
    else:
        # Search for any file matching bug_{issue_number}.json or feature_{issue_number}.json
        issues_dir = PROJECT_ROOT / "issues"
        if issues_dir.exists():
            for f in issues_dir.glob(f"*_{issue_number}.json"):
                try:
                    with open(f, "r") as fp:
                        return json.load(fp)
                except Exception as e:
                    return ToolError(
                        tool="T-1:github_read",
                        error_type="MOCK_READ_ERROR",
                        message=f"Failed to read local issue {f.name}: {e}",
                        details={}
                    )
                    
        return ToolError(
            tool="T-1:github_read",
            error_type="ISSUE_NOT_FOUND",
            message=f"Local issue mock for #{issue_number} not found in {issues_dir}.",
            details={}
        )
