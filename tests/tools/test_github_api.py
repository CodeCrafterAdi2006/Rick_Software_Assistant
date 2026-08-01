from agent_system.tools.github_read import fetch_issue
from agent_system.tools.github_write import create_pull_request
from agent_system.schemas.state import ToolError


def test_fetch_issue_offline_mock_bug_42(monkeypatch):
    """Verify T-1 offline fallback loads bug_42.json payload."""
    monkeypatch.setenv("GITHUB_LIVE_MODE", "false")
    
    res = fetch_issue(42)
    assert not isinstance(res, ToolError)
    assert res["id"] == 42
    assert "bug" in res["title"].lower() or "bug" in res["labels"] or len(res["labels"]) > 0


def test_fetch_issue_offline_mock_feature_43(monkeypatch):
    """Verify T-1 offline fallback loads feature_43.json payload (*_43.json pattern)."""
    monkeypatch.setenv("GITHUB_LIVE_MODE", "false")

    res = fetch_issue(43)
    assert not isinstance(res, ToolError)
    assert res["id"] == 43
    assert "priority" in res["title"].lower()


def test_fetch_issue_offline_mock_partial_44(monkeypatch):
    """Verify T-1 offline fallback loads partial_44.json payload (*_44.json pattern)."""
    monkeypatch.setenv("GITHUB_LIVE_MODE", "false")

    res = fetch_issue(44)
    assert not isinstance(res, ToolError)
    assert res["id"] == 44


def test_fetch_issue_offline_mock_not_found(monkeypatch):
    """Verify T-1 offline fallback returns ToolError when issue id does not exist."""
    monkeypatch.setenv("GITHUB_LIVE_MODE", "false")
    
    res = fetch_issue(9999)
    assert isinstance(res, ToolError)
    assert res.tool == "T-1:github_read"
    assert res.error_type == "ISSUE_NOT_FOUND"


def test_create_pull_request_offline_mock(monkeypatch):
    """Verify T-5 offline fallback generates synthetic PR dict."""
    monkeypatch.setenv("GITHUB_LIVE_MODE", "false")
    
    res = create_pull_request("fix/issue-42", "Fix bug 42", "Resolves #42")
    assert not isinstance(res, ToolError)
    assert res["mocked"] is True
    assert res["state"] == "open"
    assert res["html_url"] == "https://github.com/demo/demo_repo/pull/mock"
