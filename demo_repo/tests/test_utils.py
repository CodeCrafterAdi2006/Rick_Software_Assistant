"""Unit tests for task_tracker utils."""

from task_tracker.utils import format_task_summary, sanitize_title


def test_sanitize_title():
    assert sanitize_title("  Fix   login   bug  ") == "Fix login bug"
    assert sanitize_title("") == ""


def test_format_task_summary():
    summary = format_task_summary("a1b2c3d4", "Fix bug", "TODO", 3)
    assert summary == "[a1b2c3d4] (TODO) P3: Fix bug"
