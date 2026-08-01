from __future__ import annotations
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agent_system.schemas.state import ToolError

# Anchored project root (parent of agent_system)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def grep_search(
    query: str,
    target_dir: Optional[str | Path] = None,
    file_pattern: Optional[str] = None,
    case_sensitive: bool = False,
) -> Union[List[Dict[str, Any]], ToolError]:
    """Perform a structured code grep search over files in target_dir.

    Args:
        query: String or regex pattern to search for.
        target_dir: Root directory to search (defaults to PROJECT_ROOT / "demo_repo").
        file_pattern: Glob pattern to filter filenames (e.g. "*.py").
        case_sensitive: Whether the search is case sensitive (default: False).

    Returns:
        Structured list of match dicts on success, or ToolError object on failure per engineering.md §7.1.
    """
    if not query:
        return []

    search_root = Path(target_dir) if target_dir else (PROJECT_ROOT / "demo_repo")
    if not search_root.exists():
        return ToolError(
            tool="T-2:repo_search",
            error_type="DIRECTORY_NOT_FOUND",
            message=f"Search target directory not found: {search_root.resolve()}",
            details={"target_dir": str(target_dir), "query": query},
        )

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(query, flags=flags)
    except re.error as err:
        try:
            pattern = re.compile(re.escape(query), flags=flags)
        except Exception as esc_err:
            return ToolError(
                tool="T-2:repo_search",
                error_type="INVALID_REGEX_QUERY",
                message=f"Invalid search regex pattern '{query}': {esc_err}",
                details={"query": query},
            )

    # Excluded directories
    ignore_dirs = {".git", "__pycache__", ".venv", ".pytest_cache", ".sandbox", "egg-info"}

    matches: List[Dict[str, Any]] = []

    try:
        for root, dirs, files in os.walk(search_root):
            # Filter out ignored directories in-place
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]

            for filename in files:
                file_path = Path(root) / filename

                # Apply file_pattern glob filter if provided
                if file_pattern and not file_path.match(file_pattern):
                    continue

                # Read and search file content line by line
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        for line_idx, line in enumerate(f, start=1):
                            if pattern.search(line):
                                try:
                                    rel_path = file_path.relative_to(search_root).as_posix()
                                except ValueError:
                                    rel_path = file_path.as_posix()

                                matches.append({
                                    "file": rel_path,
                                    "line_number": line_idx,
                                    "content": line.rstrip("\r\n"),
                                })
                except Exception:
                    continue

        return matches
    except Exception as err:
        return ToolError(
            tool="T-2:repo_search",
            error_type="UNHANDLED_TOOL_ERROR",
            message=f"Repo search failed: {err}",
            details={"query": query, "target_dir": str(search_root)},
        )
