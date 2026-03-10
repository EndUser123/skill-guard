"""
Terminal ID detection module for skill-guard package.

Provides terminal identification with consistent format across all sources.
This is a simplified version adapted from the hooks/terminal_detection.py
module for use as a library dependency.

FORMAT: {source}_{id}
  - env_{uuid}        : From CLAUDE_TERMINAL_ID environment variable
  - fallback_{pid}    : Fallback using process ID

Priority order:
1. CLAUDE_TERMINAL_ID environment variable (process-scoped, inherited)
2. TERMINAL_ID, TERM_ID, SESSION_TERMINAL environment variables
3. Fallback: process ID

This simplified version is designed for library use where hooks
state files may not be available.
"""

import os

# Source prefixes for normalized format
SOURCE_ENV = "env"
SOURCE_FALLBACK = "fallback"

# Environment variable priority order (highest to lowest)
TERMINAL_ENV_VARS = [
    "CLAUDE_TERMINAL_ID",  # Priority 1 (process-scoped, inherited by subprocesses)
    "TERMINAL_ID",         # Priority 2
    "TERM_ID",             # Priority 2
    "SESSION_TERMINAL",    # Priority 2
]


def _normalize_id(raw_id: str, source: str) -> str:
    """
    Normalize terminal ID to consistent format: {source}_{id}.

    If ID already has a known prefix, preserve it (idempotent).

    Args:
        raw_id: Raw terminal ID from detection source
        source: Source identifier (env, fallback)

    Returns:
        Normalized ID in format {source}_{id}
    """
    known_prefixes = (f"{SOURCE_ENV}_", f"{SOURCE_FALLBACK}_")

    # Already normalized - return as-is (idempotent)
    if raw_id.startswith(known_prefixes):
        return raw_id

    # Legacy format: ConsoleHost_XXXX -> treat as env source
    if raw_id.startswith("ConsoleHost_"):
        return f"{SOURCE_ENV}_{raw_id[12:]}"

    # Legacy format: session_XXXX -> treat as env source (came from SessionStart)
    if raw_id.startswith("session_"):
        return f"{SOURCE_ENV}_{raw_id[8:]}"

    # Standard normalization
    return f"{source}_{raw_id}"


def detect_terminal_id() -> str:
    """
    Detect terminal ID using priority order.

    Returns normalized format: {source}_{id}

    Priority order:
    1. Environment variables (process-scoped, inherited correctly)
    2. Fallback using process ID

    Returns:
        str: Normalized terminal identifier string
    """
    # Try environment variables first (most reliable)
    for env_var in TERMINAL_ENV_VARS:
        terminal_id = os.environ.get(env_var)
        if terminal_id:
            return _normalize_id(terminal_id, SOURCE_ENV)

    # Fallback: use process ID
    return _normalize_id(f"term_{os.getpid()}", SOURCE_FALLBACK)


def detect_terminal_id_with_source() -> tuple[str, str]:
    """
    Detect terminal ID and return both ID and detection source.

    Returns:
        tuple[str, str]: (terminal_id, source) where source is 'env' or 'fallback'
    """
    # Try environment variables first (most reliable)
    for env_var in TERMINAL_ENV_VARS:
        terminal_id = os.environ.get(env_var)
        if terminal_id:
            return terminal_id, SOURCE_ENV

    # Fallback: use process ID
    return f"term_{os.getpid()}", SOURCE_FALLBACK
