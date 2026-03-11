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

# Source prefixes for normalized format
SOURCE_ENV = "env"
SOURCE_CONSOLE = "console"
SOURCE_FALLBACK = "fallback"  # Deprecated: kept for backward compat only; not used in detection

# Environment variable priority order (highest to lowest)
TERMINAL_ENV_VARS = [
    "CLAUDE_TERMINAL_ID",  # Priority 1 (explicit override)
    "TERMINAL_ID",         # Priority 2
    "TERM_ID",             # Priority 2
    "SESSION_TERMINAL",    # Priority 2
]


def _normalize_id(raw_id: str, source: str) -> str:
    """
    Normalize terminal ID to consistent format: {source}_{id}.

    If ID already has a known prefix, preserve it (idempotent).
    """
    known_prefixes = (f"{SOURCE_ENV}_", f"{SOURCE_CONSOLE}_")

    if raw_id.startswith(known_prefixes):
        return raw_id

    # Legacy format: ConsoleHost_XXXX -> console source
    if raw_id.startswith("ConsoleHost_"):
        return f"{SOURCE_CONSOLE}_{raw_id[12:]}"

    # Legacy format: session_XXXX -> env source (came from SessionStart)
    if raw_id.startswith("session_"):
        return f"{SOURCE_ENV}_{raw_id[8:]}"

    return f"{source}_{raw_id}"


def _detect_console_window() -> str:
    """
    Detect Windows console window handle via GetConsoleWindow().

    Returns the hex handle string (without prefix) if successful, "" otherwise.

    All subprocesses attached to the same console share the same handle,
    making this stable across sibling hook invocations with different PIDs.
    """
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


def detect_terminal_id() -> str:
    """
    Detect terminal ID.

    Returns normalized format: {source}_{id}, or "" if not detectable.

    Priority:
    1. CLAUDE_TERMINAL_ID and other env vars
    2. Windows GetConsoleWindow() handle
    3. "" — PID fallback is intentionally absent; callers must handle empty string.
    """
    for env_var in TERMINAL_ENV_VARS:
        value = os.environ.get(env_var)
        if value:
            return _normalize_id(value, SOURCE_ENV)

    handle = _detect_console_window()
    if handle:
        return _normalize_id(handle, SOURCE_CONSOLE)

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
            return _normalize_id(value, SOURCE_ENV), SOURCE_ENV

    handle = _detect_console_window()
    if handle:
        return _normalize_id(handle, SOURCE_CONSOLE), SOURCE_CONSOLE

    return "", ""
