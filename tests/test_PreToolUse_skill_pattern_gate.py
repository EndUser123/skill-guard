"""Tests for PreToolUse_skill_pattern_gate."""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch

# Add src to path for direct module import
SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_ROOT))

from skill_guard.PreToolUse.PreToolUse_skill_pattern_gate import handle_pre_tool_use


def test_handle_pre_tool_use_exists():
    """Smoke test: handle_pre_tool_use function is importable from the module."""
    assert callable(handle_pre_tool_use)


def _base_skill_state() -> dict:
    return {
        "skill": "yt-is",
        "required_tools": ["Bash"],
        "allowed_first_tools": ["Bash"],
        "first_tool_validated": False,
        "required_first_command_patterns": [r"^csf-source\s+sync(?:\s|$)"],
        "required_first_command_hint": "Use csf-source sync first, then list or fetch.",
        "first_command_validated": False,
    }


def test_handle_pre_tool_use_allows_required_first_command():
    """First Bash command that matches the skill contract should be allowed."""
    with patch(
        "skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_state",
        return_value=_base_skill_state(),
    ), patch(
        "skill_guard.PreToolUse.PreToolUse_skill_pattern_gate.get_skill_config",
        return_value={
            "tools": ["Bash"],
            "pattern": r"^csf-source\s+(sync|list|add|fetch)(?:\s|$)",
            "hint": "Use csf-source via the documented yt-is workflow.",
            "intent_enabled": False,
            "discovered": True,
        },
    ), patch(
        "skill_guard.skill_execution_state.mark_first_tool_validated"
    ), patch(
        "skill_guard.skill_execution_state.mark_first_command_validated"
    ):
        result = handle_pre_tool_use({"tool_name": "Bash", "input": {"command": "csf-source sync"}})

    assert result == {}


def test_handle_pre_tool_use_blocks_wrong_first_command():
    """First Bash command that skips the required command should be blocked."""
    with patch(
        "skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_state",
        return_value=_base_skill_state(),
    ), patch(
        "skill_guard.PreToolUse.PreToolUse_skill_pattern_gate.get_skill_config",
        return_value={
            "tools": ["Bash"],
            "pattern": r"^csf-source\s+(sync|list|add|fetch)(?:\s|$)",
            "hint": "Use csf-source via the documented yt-is workflow.",
            "intent_enabled": False,
            "discovered": True,
        },
    ), patch(
        "skill_guard.skill_execution_state.mark_first_tool_validated"
    ), patch(
        "skill_guard.skill_execution_state.mark_first_command_validated"
    ):
        result = handle_pre_tool_use({"tool_name": "Bash", "input": {"command": "csf-source list"}})

    assert result.get("block") is True
    assert "FIRST-COMMAND COHERENCE MISMATCH" in result.get("reason", "")
