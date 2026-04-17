"""Turn marker helper for skill-guard.

Ensures there is an active DB-backed turn for downstream skill hooks.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from skill_guard.hook_compat import HookResult, register_hook

_script_path = Path(__file__)
for _hooks_root in (
    Path(r"P:\.claude\hooks"),
    _script_path.parent.parent,
    _script_path.resolve().parent.parent,
):
    _hooks_root_str = str(_hooks_root)
    if _hooks_root_str not in sys.path:
        sys.path.insert(0, _hooks_root_str)

try:
    from evidence_store import get_active_turn, start_turn
except Exception:  # pragma: no cover - must fail open

    def get_active_turn(session_id: str, terminal_id: str) -> str | None:  # type: ignore[no-redef]
        return None

    def start_turn(
        session_id: str,
        terminal_id: str,
        prompt: str = "",
        transcript_path: str = "",
    ) -> str:  # type: ignore[no-redef]
        return ""


def _resolve_context_value(context: Any, key: str, default: str = "") -> str:
    if hasattr(context, key):
        value = getattr(context, key)
        if isinstance(value, str):
            return value.strip()

    data = getattr(context, "data", {}) or {}
    value = data.get(key)
    if isinstance(value, str):
        return value.strip()
    return default


def ensure_turn_marker(context: Any) -> str | None:
    """Ensure a DB-backed turn exists and return the turn_id if found."""
    terminal_id = _resolve_context_value(context, "terminal_id")
    session_id = _resolve_context_value(context, "session_id")
    if not terminal_id:
        return None

    data = getattr(context, "data", None)
    if not isinstance(data, dict):
        data = {}
    turn_id = str(data.get("turn_id") or "").strip()
    if not turn_id:
        turn_id = get_active_turn(session_id, terminal_id) or ""
    if not turn_id:
        turn_id = start_turn(
            session_id=session_id,
            terminal_id=terminal_id,
            prompt=str(getattr(context, "prompt", "") or ""),
            transcript_path=str(data.get("transcript_path", "") or ""),
        )

    if turn_id and isinstance(data, dict):
        data["turn_id"] = turn_id

    return turn_id or None


@register_hook("turn_marker", priority=0.5)
def write_turn_marker(context: Any) -> HookResult:
    """Ensure a DB-backed turn exists for downstream hooks."""
    ensure_turn_marker(context)
    return HookResult.empty()


turn_marker_hook = write_turn_marker


__all__ = ["ensure_turn_marker", "turn_marker_hook", "write_turn_marker"]
