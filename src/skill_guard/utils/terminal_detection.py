"""
Terminal ID detection module for skill-guard package.

Provides terminal identification with consistent format across all sources.

FORMAT: {source}_{id}
  - env_{id}      : From CLAUDE_TERMINAL_ID or other env vars
  - console_{hex} : Windows GetConsoleWindow() handle (stable per terminal)

Priority order:
1. CLAUDE_TERMINAL_ID environment variable (explicit user/system override)
2. TERMINAL_ID, TERM_ID, SESSION_TERMINAL environment variables
3. Windows GetConsoleWindow() handle (stable across all subprocesses in same console)
4. Returns "" — callers must handle missing terminal ID; PID fallback is forbidden
   because PID differs per subprocess and silently breaks cross-hook state sharing.
"""

import os
import sys

# Canonical terminal ID normalization (single source of truth)
from skill_guard.utils.terminal_id import SOURCE_CONSOLE, SOURCE_ENV, normalize_terminal_id

SOURCE_FALLBACK = "fallback"  # Deprecated: kept for backward compat only; not used in detection

# Environment variable priority order (highest to lowest)
TERMINAL_ENV_VARS = [
    "CLAUDE_TERMINAL_ID",  # Priority 1 (explicit override)
    "TERMINAL_ID",  # Priority 2
    "TERM_ID",  # Priority 2
    "SESSION_TERMINAL",  # Priority 2
]


def _detect_console_window() -> str:
    """
    Detect Windows terminal ID via WT_SESSION or GetConsoleWindow().

    Priority:
    1. WT_SESSION (Windows Terminal) - UUID environment variable
    2. GetConsoleWindow() - Fallback for other terminals

    Returns the hex handle/UUID string (without prefix) if successful, "" otherwise.

    All subprocesses attached to the same terminal share the same identifier,
    making this stable across sibling hook invocations with different PIDs.

    Note: GetConsoleWindow() returns None in hook subprocess context, so
    WT_SESSION is the primary method for Windows Terminal.
    """
    # Priority 1: WT_SESSION (Windows Terminal - most reliable on Windows)
    wt_session = os.environ.get("WT_SESSION")
    if wt_session:
        return wt_session  # Return UUID, caller adds prefix

    # Priority 2: GetConsoleWindow() fallback (for non-Windows Terminal scenarios)
    if sys.platform != "win32":
        return ""
    try:
        import ctypes

        handle = ctypes.windll.kernel32.GetConsoleWindow()
        if handle:
            return hex(handle)[2:]  # e.g. "1a2b3c" — caller adds prefix
    except Exception:
        pass
    return ""


def _read_from_state_file() -> str | None:
    """
    Read terminal_id from SessionStart's terminal-specific state file.

    MULTI-TERMINAL ISOLATION: Each terminal has its own state file.
    Filename format: terminal_{hex_handle}.json

    This function:
    1. Detects the current console handle via GetConsoleWindow()
    2. Looks for terminal_{handle}.json matching this handle
    3. Returns the normalized terminal_id if found and valid

    Returns:
        Terminal ID string if found and valid, None otherwise.
    """
    try:
        import json
        from pathlib import Path

        # Try to find project root
        project_root = os.environ.get("PROJECT_ROOT")
        if not project_root:
            return None

        # Step 1: Detect console handle to find our terminal-specific file
        handle = _detect_console_window()
        if not handle:
            return None

        # Step 2: Look for terminal-specific state file
        state_dir = Path(project_root) / ".claude" / "state"
        state_file = state_dir / f"terminal_{handle}.json"

        if not state_file.exists():
            return None

        # Step 3: Read and validate state file
        with open(state_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        terminal_id = data.get("terminal_id")
        if terminal_id:
            # Validate timestamp (state file must be recent - within 24 hours)
            import time

            timestamp = data.get("timestamp", 0)
            if time.time() - timestamp < 86400:  # 24 hours
                return terminal_id

    except Exception:
        pass

    return None


def detect_terminal_id() -> str:
    """
    Detect terminal ID with multi-terminal isolation.

    Returns normalized format: {source}_{id}, or "" if not detectable.

    Priority:
    1. Read from terminal-specific state file (SessionStart wrote this)
    2. CLAUDE_TERMINAL_ID and other env vars
    3. Windows GetConsoleWindow() handle
    4. "" — PID fallback is intentionally absent; callers must handle empty string.

    MULTI-TERMINAL ISOLATION: Each terminal reads from its own state file,
    preventing cross-terminal contamination when running 5+ concurrent terminals.
    """
    # Priority 1: Read from terminal-specific state file (authoritative source)
    terminal_id = _read_from_state_file()
    if terminal_id:
        # State file already contains normalized ID
        return terminal_id

    # Priority 2: CLAUDE_TERMINAL_ID and other env vars
    for env_var in TERMINAL_ENV_VARS:
        value = os.environ.get(env_var)
        if value:
            return normalize_terminal_id(value, SOURCE_ENV)

    # Priority 3: Windows GetConsoleWindow() handle (direct detection)
    handle = _detect_console_window()
    if handle:
        return normalize_terminal_id(handle, SOURCE_CONSOLE)

    # Priority 4: Return "" if no detection method succeeded
    return ""


def detect_terminal_id_with_source() -> tuple[str, str]:
    """
    Detect terminal ID and return both ID and detection source.

    Returns:
        tuple[str, str]: (terminal_id, source) — terminal_id may be "" if undetectable.
    """
    for env_var in TERMINAL_ENV_VARS:
        value = os.environ.get(env_var)
        if value:
            return normalize_terminal_id(value, SOURCE_ENV), SOURCE_ENV

    handle = _detect_console_window()
    if handle:
        return normalize_terminal_id(handle, SOURCE_CONSOLE), SOURCE_CONSOLE

    return "", ""
