"""Utility helper functions for task_tracker."""

import re


def sanitize_title(raw_title: str) -> str:
    """Sanitize title by stripping extra spaces and normalizing whitespace."""
    if not raw_title:
        return ""
    cleaned = raw_title.strip()
    return re.sub(r"\s+", " ", cleaned)


def format_task_summary(task_id: str, title: str, status: str, priority: int) -> str:
    """Return a formatted single-line representation of a task."""
    return f"[{task_id}] ({status}) P{priority}: {title}"
