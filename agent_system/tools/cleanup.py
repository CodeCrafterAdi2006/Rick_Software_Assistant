from __future__ import annotations
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def cleanup_sandbox(session_id: str) -> bool:
    """Removes .sandbox/{session_id}/ directory from disk on session completion or rejection.
    Returns True if sandbox existed and was removed, False if no sandbox was present.
    """
    sandbox_dir = PROJECT_ROOT / ".sandbox" / session_id
    if sandbox_dir.exists():
        try:
            shutil.rmtree(sandbox_dir, ignore_errors=True)
            return True
        except Exception:
            return False
    return False
