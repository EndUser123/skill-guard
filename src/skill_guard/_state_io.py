r"""State I/O utilities for skill execution state management.

Extracted from skill_execution_state.py (ARCH-003 refactor).
Provides terminal-isolated state file operations.

All modules that need STATE_DIR or detect_terminal_id should import from here
to avoid circular imports with skill_execution_state.py.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


# =============================================================================
# SHARED CONSTANTS AND TERMINAL DETECTION
# =============================================================================

STATE_DIR = Path("P:/packages/.claude/state")


def detect_terminal_id() -> str:
    """Detect terminal ID for state isolation.

    Uses terminal_detection.py from utils for consistent ID detection.
    """
    try:
        from skill_guard.utils.terminal_detection import detect_terminal_id as shared_detect

        return shared_detect()
    except ImportError:
        terminal_id = os.environ.get("CLAUDE_TERMINAL_ID")
        if terminal_id:
            return terminal_id
        return ""


# =============================================================================
# STATE I/O
# =============================================================================


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON data atomically using write-to-temp-then-rename pattern.

    Retries once with gc.collect() on WinError 32 (PermissionError).
    Raises on repeated failure — callers must handle.
    """
    import gc

    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(data, indent=2)
    try:
        temp.write_text(text)
        os.replace(str(temp), str(path))
    except PermissionError:
        gc.collect()
        try:
            temp.write_text(text)
            os.replace(str(temp), str(path))
        except PermissionError:
            raise OSError(f"Failed to write {path} after retry") from None


def sanitize_terminal_id(terminal_id: str) -> str:
    """Sanitize terminal ID for use in file paths.

    Removes characters that are unsafe for filesystem paths.
    Colon is excluded because it causes issues on Windows (drive letter separator).
    """
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", terminal_id)


# Cached state directory per terminal_id (avoids repeated mkdir on every call)
_state_dir_cache: dict[str, Path] = {}


def _get_state_dir() -> Path:
    """Get the state directory for this terminal.

    Caches the result per terminal_id to avoid repeated directory
    creation syscalls on every invocation.
    """
    terminal_id = detect_terminal_id()
    cache_key = sanitize_terminal_id(terminal_id or "unknown")
    if cache_key in _state_dir_cache:
        return _state_dir_cache[cache_key]
    state_subdir = STATE_DIR / f"skill_execution_{cache_key}"
    state_subdir.mkdir(parents=True, exist_ok=True)
    _state_dir_cache[cache_key] = state_subdir
    return state_subdir


def _get_state_file_for_terminal(terminal_id: str) -> Path:
    """Return the compatibility state file for a specific terminal."""
    state_subdir = STATE_DIR / f"skill_execution_{sanitize_terminal_id(terminal_id or 'unknown')}"
    state_subdir.mkdir(parents=True, exist_ok=True)
    return state_subdir / "skill_execution_pending.json"


def _read_pending_state_file(terminal_id: str) -> dict[str, Any] | None:
    state_file = _get_state_file_for_terminal(terminal_id)
    if not state_file.exists():
        return None
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _write_pending_state_file(terminal_id: str, state: dict[str, Any]) -> bool:
    try:
        _atomic_write_json(_get_state_file_for_terminal(terminal_id), state)
        return True
    except OSError:
        return False


def _clear_pending_state_file(terminal_id: str) -> None:
    try:
        _get_state_file_for_terminal(terminal_id).unlink(missing_ok=True)
    except OSError:
        pass


# Legacy compat — used by _migration_helpers.py
def _get_state_file() -> Path:
    """Return the state file for the current terminal (legacy compat)."""
    state_subdir = _get_state_dir()
    return state_subdir / "skill_execution_pending.json"