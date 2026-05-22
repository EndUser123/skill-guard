r"""Ledger module integration for skill execution state.

Extracted from skill_execution_state.py (ARCH-003 refactor).
Provides lazy import of the hook_ledger module from Claude Code hooks.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


# Path must match HOOKS_LIB_DIR in skill_execution_state.py
# Kept here to avoid circular imports
_HOOKS_LIB_DIR = Path(r"P:/.claude/hooks/__lib")


# Module-level cache for hook_ledger (pattern from the legacy metadata cache)
_HOOKS_LEDGER_MODULE: Any = None


def _get_ledger_module() -> Any | None:
    """Import and return hook_ledger module from Claude Code hooks.

    Returns:
        hook_ledger module if available, None otherwise.

    Note:
        Follows the same lazy-import pattern as the legacy metadata cache.
        Uses the same path manipulation as breadcrumb/tracker.py.
    """
    global _HOOKS_LEDGER_MODULE
    if _HOOKS_LEDGER_MODULE is not None:
        return _HOOKS_LEDGER_MODULE

    try:
        if _HOOKS_LIB_DIR.exists() and str(_HOOKS_LIB_DIR) not in sys.path:
            sys.path.insert(0, str(_HOOKS_LIB_DIR))
        import hook_ledger  # type: ignore

        _HOOKS_LEDGER_MODULE = hook_ledger
        return hook_ledger
    except Exception:
        return None