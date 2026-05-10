#!/usr/bin/env python3
r"""PreToolUse gate: block Glob/Grep if not scoped to the expected skill directory.

Phase 2 of the skill-dir correlation system:
  - Writer (skill_context_writer.py): detects slash-skill-name in user prompt and
    writes the expected skill directory to a state file.
  - Gate (this module): intercepts Glob/Grep and blocks searches that do not
    target the expected skill directory.

This prevents the "accurate reporting of wrong artifact" bug where an unscoped
Glob/Grep hits the wrong skill directory first and the AI reports findings from
the wrong entity.

BLOCK CONDITIONS:
  - State file exists AND
  - Tool is Glob or Grep AND
  - expected_dir is NOT found in the command string (backslash normalized to forward slash)

ENABLED: SKILL_DIR_GATE_ENABLED env var ("true"/"false", default "true")
FAIL OPEN: any exception → allow (never break tool execution)
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HOOKS_DIR = Path(r"P:\\\\\\.claude/hooks")
sys.path.insert(0, str(HOOKS_DIR))

_STATE_DIR = HOOKS_DIR / "state" / "skill_context"

_ENABLED = os.environ.get("SKILL_DIR_GATE_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)


def _safe_id(value: str) -> str:
    """Sanitize a string for use in filenames."""
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value)


def _skill_context_path(terminal_id: str) -> Path:
    """Return the path to the skill context state file for the given terminal."""
    safe_tid = _safe_id(terminal_id or "default")
    return _STATE_DIR / f"skill_context_{safe_tid}.json"


def _load_state(terminal_id: str) -> dict | None:
    """Load the skill context state file, or return None if missing/unreadable."""
    try:
        state_file = _skill_context_path(terminal_id)
        if not state_file.exists():
            return None
        return json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return None


def _is_skill_dir_in_command(command: str, expected_dir: str) -> bool:
    """Return True if expected_dir (e.g. '.claude/skills/ai-pcli') appears in command.

    Normalizes backslashes to forward slashes before checking.
    """
    normalized = command.replace("\\", "/")
    return expected_dir in normalized


def _get_command_from_input(tool_name: str, tool_input: dict) -> str | None:
    """Extract the path/pattern string from tool input."""
    if tool_name == "Glob":
        return tool_input.get("pattern") or tool_input.get("path") or None
    if tool_name == "Grep":
        return tool_input.get("path") or None
    return None


def run(data: dict) -> dict:
    """In-process entry point for PreToolUse router.

    Returns:
        {"continue": True} to allow, {"continue": False, "reason": "..."} to block.
    """
    if not _ENABLED:
        return {"continue": True}

    tool_name = data.get("tool_name", "")
    if tool_name not in ("Glob", "Grep"):
        return {"continue": True}

    # Resolve terminal_id — must match what the writer used
    terminal_id = (
        data.get("terminal_id")
        or data.get("terminalId")
        or os.environ.get("CLAUDE_TERMINAL_ID", "")
    ).strip()
    if not terminal_id:
        return {"continue": True}

    # Load state file
    state = _load_state(terminal_id)
    if state is None:
        return {"continue": True}

    expected_dir = state.get("expected_dir", "")
    if not expected_dir:
        return {"continue": True}

    # Extract command string from tool input
    tool_input = data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        tool_input = {}

    command = _get_command_from_input(tool_name, tool_input)

    # Grep without a path is always unscoped → block
    if tool_name == "Grep" and not command:
        return {
            "continue": False,
            "reason": f"[skill-dir-gate] BLOCKED: Grep has no path scope — expected {expected_dir}",
        }

    # Check if expected_dir appears in the command
    if command and _is_skill_dir_in_command(command, expected_dir):
        return {"continue": True}

    # Unscoped — block
    return {
        "continue": False,
        "reason": (
            f"[skill-dir-gate] BLOCKED: {tool_name} is not scoped to {expected_dir}/\n"
            f"Expected: {expected_dir}\n"
            f"Got: {command or '(empty)'}"
        ),
    }


def main() -> None:
    """Subprocess entry point — exits with code 0 (allow) or 2 (block)."""
    if not _ENABLED:
        sys.exit(0)

    raw_input = sys.stdin.read().strip()
    if not raw_input:
        sys.exit(0)

    try:
        raw_input = raw_input.lstrip("﻿")
        data = json.loads(raw_input)
    except json.JSONDecodeError:
        sys.exit(0)

    result = run(data)
    if result.get("continue") is False:
        print(result.get("reason", ""), file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
