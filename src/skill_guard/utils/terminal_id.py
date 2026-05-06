"""
Terminal ID normalization module.

Canonical source for terminal ID normalization across all packages.
Ensures consistent prefix handling prevents state file path divergence.

FORMAT: {source}_{id}
  - env_{id}      : From CLAUDE_TERMINAL_ID or other env vars
  - console_{hex} : Windows GetConsoleWindow() handle (stable per terminal)

Legacy conversions:
  - ConsoleHost_XXXX -> console_{XXXX}
  - session_XXXX   -> env_{XXXX}
"""

from __future__ import annotations

# Source constants (exported for use by callers)
SOURCE_ENV = "env"
SOURCE_CONSOLE = "console"

# Known prefixes for idempotent normalization
_KNOWN_PREFIXES = (f"{SOURCE_ENV}_", f"{SOURCE_CONSOLE}_")


def normalize_terminal_id(raw_id: str, source: str = SOURCE_ENV) -> str:
    """
    Normalize terminal ID to consistent format: {source}_{id}.

    If ID already has a known prefix, preserve it (idempotent).
    Otherwise, apply legacy conversions and return normalized format.

    Args:
        raw_id: Raw terminal ID string
        source: Default source to use if no legacy prefix matches
               (default: "env" for backward compatibility)

    Returns:
        Normalized terminal ID in {source}_{id} format
    """
    # Idempotent: don't add duplicate prefix, but still sanitize
    if raw_id.startswith(_KNOWN_PREFIXES):
        # Already normalized — still apply filename-safe filter
        result = raw_id
    elif raw_id.startswith("ConsoleHost_"):
        result = f"{SOURCE_CONSOLE}_{raw_id[12:]}"
    elif raw_id.startswith("session_"):
        result = f"{SOURCE_ENV}_{raw_id[8:]}"
    else:
        result = f"{source}_{raw_id}"
    # Ensure filename-safe: filter chars invalid on Windows (all platforms)
    for ch in (":", "<", ">", "|", '"', "*", "?"):
        result = result.replace(ch, "-")
    return result
