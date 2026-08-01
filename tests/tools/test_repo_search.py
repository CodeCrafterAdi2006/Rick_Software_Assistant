import pytest
from pathlib import Path
from agent_system.schemas.state import ToolError
from agent_system.tools.repo_search import grep_search, PROJECT_ROOT


def test_grep_search_demo_repo_bug_line():
    """Verify Tool T-2 locates line 67 in core.py matching issue #42 root cause."""
    matches = grep_search("t.status == status")
    assert isinstance(matches, list)
    assert len(matches) >= 1

    # Check match fields
    core_match = next(m for m in matches if "core.py" in m["file"])
    assert core_match["file"] == "src/task_tracker/core.py"
    assert core_match["line_number"] == 67
    assert "if t.status == status" in core_match["content"]


def test_grep_search_case_insensitive():
    matches_upper = grep_search("TASKMANAGER", case_sensitive=False)
    matches_lower = grep_search("taskmanager", case_sensitive=False)
    assert isinstance(matches_upper, list)
    assert isinstance(matches_lower, list)
    assert len(matches_upper) == len(matches_lower)
    assert len(matches_upper) > 0


def test_grep_search_case_sensitive():
    matches_exact = grep_search("TaskManager", case_sensitive=True)
    matches_lower = grep_search("taskmanager", case_sensitive=True)
    assert isinstance(matches_exact, list)
    assert isinstance(matches_lower, list)
    assert len(matches_exact) > 0
    assert len(matches_lower) == 0


def test_grep_search_file_pattern():
    matches_py = grep_search("def list_tasks", file_pattern="*.py")
    assert isinstance(matches_py, list)
    assert len(matches_py) > 0

    matches_txt = grep_search("def list_tasks", file_pattern="*.txt")
    assert isinstance(matches_txt, list)
    assert len(matches_txt) == 0


def test_grep_search_custom_target_dir(tmp_path):
    sub_dir = tmp_path / "src"
    sub_dir.mkdir()
    sample_file = sub_dir / "sample.py"
    sample_file.write_text("def custom_function():\n    return 42\n", encoding="utf-8")

    matches = grep_search("custom_function", target_dir=tmp_path)
    assert isinstance(matches, list)
    assert len(matches) == 1
    assert matches[0]["file"] == "src/sample.py"
    assert matches[0]["line_number"] == 1


def test_grep_search_nonexistent_dir_returns_tool_error():
    """Verify Tool T-2 returns a structured ToolError object on nonexistent directory per engineering.md §7.1."""
    res = grep_search("query", target_dir="nonexistent_directory_123")
    assert isinstance(res, ToolError)
    assert res.tool == "T-2:repo_search"
    assert res.error_type == "DIRECTORY_NOT_FOUND"
    assert "Search target directory not found" in res.message


def test_grep_search_empty_query():
    res = grep_search("")
    assert isinstance(res, list)
    assert res == []
