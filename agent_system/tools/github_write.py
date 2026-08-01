import json
from typing import Any, Dict, Union
import urllib.request
import urllib.error

from agent_system.config.settings import Settings
from agent_system.schemas.state import ToolError


def create_pull_request(branch: str, title: str, body: str) -> Union[Dict[str, Any], ToolError]:
    """Creates a Pull Request via GitHub API. Mocks offline locally if GITHUB_LIVE_MODE is False."""
    live_mode = Settings.is_github_live_mode()

    if live_mode:
        token = Settings.get_api_key("GITHUB_TOKEN")
        if not token:
            return ToolError(
                tool="T-5:github_write",
                error_type="MISSING_GITHUB_TOKEN",
                message="GITHUB_LIVE_MODE is true but GITHUB_TOKEN is not set.",
                details={}
            )
        
        # Real HTTP request logic (simplified for the scope)
        payload = json.dumps({
            "title": title,
            "body": body,
            "head": branch,
            "base": "main"
        }).encode("utf-8")
        
        req = urllib.request.Request(
            "https://api.github.com/repos/demo/demo_repo/pulls",
            data=payload,
            method="POST"
        )
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Accept", "application/vnd.github+json")
        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            return ToolError(
                tool="T-5:github_write",
                error_type="GITHUB_API_ERROR",
                message=f"HTTP {e.code}: {e.reason}",
                details={"payload": title}
            )
        except Exception as e:
            return ToolError(
                tool="T-5:github_write",
                error_type="NETWORK_ERROR",
                message=str(e),
                details={}
            )
    else:
        # Offline Mock Mode
        mock_url = f"https://github.com/demo/demo_repo/pull/mock"
        return {
            "html_url": mock_url,
            "number": 999,
            "title": title,
            "state": "open",
            "mocked": True
        }
