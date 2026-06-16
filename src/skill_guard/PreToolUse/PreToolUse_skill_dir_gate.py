#!/usr/bin/env python3
r"""PreToolUse gate: enforce skill directory scope for executing tools.

SCOPE RULES (v2.0):
  - READ-ONLY tools (Read, Grep, Glob) -> always allowed against P:\packages\...
    regardless of skill context. No blocking.
  - EXECUTING/MUTATING tools (Bash, Write, Edit, MultiEdit, Task, etc.) ->
    scope-gated. Must match expected_dir from skill context state.

SKILL CONTEXT SHOW/RESET API:
  Bash(python P:/packages/.claude-marketplace/plugins/skill-guard/tools/skill_context.py show)
  Bash(python P:/packages/.claude-marketplace/plugins/skill-guard/tools/skill_context.py reset)

ENABLED: SKILL_DIR_GATE_ENABLED env var ("true"/"false", default "true")
FAIL OPEN: any exception -> allow (never break tool execution)
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

def _normalize_stdout(data: dict) -> dict:
    """Normalize hook output to Claude Code Zod-valid schema."""
    if data.get('decision') == 'allow':
        return {'decision': 'approve'}
    if data.get('decision') == 'block':
        return {'decision': 'block', 'reason': data.get('reason', '')}
    if 'allow' in data:
        if data['allow'] is False:
            return {'decision': 'block', 'reason': data.get('reason', '')}
        return {'decision': 'approve'}
    if 'continue' in data:
        if data['continue'] is False:
            return {'decision': 'block', 'reason': data.get('reason', '')}
        return {'decision': 'approve'}
    if 'ok' in data:
        return {'decision': 'approve'}
    return data



HOOKS_DIR = Path(r"P:\\.claude/hooks")
sys.path.insert(0, str(HOOKS_DIR))

_STATE_DIR = HOOKS_DIR / "state" / "skill_context"

_ENABLED = os.environ.get("SKILL_DIR_GATE_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)

# ---------------------------------------------------------------------------
# TOOL CLASSIFICATION (v2.0)
# ---------------------------------------------------------------------------

READ_ONLY_TOOLS = frozenset({
    "Read",
    "Grep",
    "Glob",
    "WebFetch",
    "mcp__plugin_context7_context7__query-docs",
    "mcp__plugin_serena_serena__read_file",
    "mcp__plugin_serena_serena__get_symbols_overview",
    "mcp__plugin_serena_serena__get_diagnostics_for_file",
    "mcp__plugin_serena_serena__find_symbol",
    "mcp__plugin_serena_serena__find_declaration",
    "mcp__plugin_serena_serena__find_implementations",
    "mcp__plugin_serena_serena__find_referencing_symbols",
    "mcp__plugin_serena_serena__search_for_pattern",
    "mcp__plugin_serena_serena__list_dir",
    "mcp__plugin_serena_serena__get_current_config",
    "mcp__plugin_serena_serena__list_memories",
    "mcp__plugin_serena_serena__read_memory",
})

EXECUTE_TOOLS = frozenset({
    "Bash",
    "Write",
    "Edit",
    "MultiEdit",
    "Task",
    "Agent",
    "NotebookEdit",
    "CallTool",
    "mcp__plugin_serena_serena__create_text_file",
    "mcp__plugin_serena_serena__delete_lines",
    "mcp__plugin_serena_serena__insert_at_line",
    "mcp__plugin_serena_serena__insert_after_symbol",
    "mcp__plugin_serena_serena__insert_before_symbol",
    "mcp__plugin_serena_serena__replace_content",
    "mcp__plugin_serena_serena__replace_lines",
    "mcp__plugin_serena_serena__replace_symbol_body",
    "mcp__plugin_serena_serena__delete_memory",
    "mcp__plugin_serena_serena__edit_memory",
    "mcp__plugin_serena_serena__rename_memory",
    "mcp__plugin_serena_serena__write_memory",
    "mcp__plugin_serena_serena__execute_shell_command",
    "mcp__plugin_serena_serena__onboarding",
    "mcp__plugin_serena_serena__activate_project",
    "mcp__plugin_serena_serena__open_dashboard",
    "mcp__plugin_serena_serena__remove_project",
    "mcp__plugin_serena_serena__rename_symbol",
    "mcp__plugin_serena_serena__safe_delete_symbol",
    "mcp__plugin_serena_serena__restart_language_server",
})

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


def _is_skill_dir_in_command(command: str, expected_dir: str, skill_name: str) -> bool:
    """Return True if expected_dir or skill_name appears in command.

    Normalizes backslashes to forward slashes before checking.
    Matches on:
    - Full expected_dir path
    - Skill name as a directory segment: /{skill_name}/ or /{skill_name}
    """
    normalized = command.replace("\\", "/")
    if expected_dir in normalized:
        return True
    # Also match when command contains the skill name as a path segment
    # e.g. pattern "**/skills/chs/**" should match skill_name "chs"
    if f"/{skill_name}/" in normalized or normalized.endswith(f"/{skill_name}"):
        return True
    return False


def _get_command_from_input(tool_name: str, tool_input: dict) -> str | None:
    """Extract the path/pattern string from tool input."""
    if tool_name == "Glob":
        return tool_input.get("pattern") or tool_input.get("path") or None
    if tool_name == "Grep":
        return tool_input.get("path") or None
    if tool_name == "Bash":
        return tool_input.get("command", "").split("&&")[0].split("||")[0].strip() or None
    # MCP write tools — extract first path arg
    if tool_name in (
        "Write",
        "Edit",
        "MultiEdit",
        "NotebookEdit",
        "mcp__plugin_serena_serena__create_text_file",
        "mcp__plugin_serena_serena__replace_content",
        "mcp__plugin_serena_serena__replace_lines",
        "mcp__plugin_serena_serena__insert_at_line",
        "mcp__plugin_serena_serena__insert_after_symbol",
        "mcp__plugin_serena_serena__insert_before_symbol",
        "mcp__plugin_serena_serena__replace_symbol_body",
    ):
        return tool_input.get("file_path") or tool_input.get("relative_path") or None
    return None


def run(data: dict) -> dict:
    """In-process entry point for PreToolUse router.

    Returns:
        {"continue": True} to allow, {"continue": False, "reason": "..."} to block.
    """
    if not _ENABLED:
        return {"continue": True}

    tool_name = data.get("tool_name", "")

    # v2.0: Read-only tools always pass — developer can inspect any path
    if tool_name in READ_ONLY_TOOLS:
        return {"continue": True}

    # Executing tools remain scope-gated
    if tool_name not in EXECUTE_TOOLS:
        return {"continue": True}  # unknown tools fail open

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
    skill_name = state.get("expected_skill", "")
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

    # Check if any valid path appears in the command
    valid_paths = state.get("valid_paths", [])
    if not valid_paths:
        # Backward compat: build from expected_dir + source_dir
        valid_paths = [expected_dir]
        source_dir = state.get("source_dir", "") or ""
        if source_dir:
            valid_paths.append(source_dir)

    if command and any(
        _is_skill_dir_in_command(command, p, skill_name) for p in valid_paths
    ):
        return {"continue": True}

    # Unscoped - block
    nl = '\\n'
    paths_str = ", ".join(valid_paths)
    cmd_str = command or "(empty)"
    reason = (
        f"[skill-dir-gate] BLOCKED: {tool_name} is not scoped"
        + nl + f"Expected one of: {paths_str}"
        + nl + f"Got: {cmd_str}"
    )
    return {"continue": False, "reason": reason}



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
