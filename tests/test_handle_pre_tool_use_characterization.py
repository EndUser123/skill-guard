"""Characterization tests for handle_pre_tool_use.

These tests CAPTURE CURRENT BEHAVIOR before refactoring.
Run with: pytest tests/test_handle_pre_tool_use_characterization.py -v

The function handle_pre_tool_use(data: dict) -> dict is a 271-line function
in PreToolUse_skill_pattern_gate.py that:
- Layer 0: Workflow steps enforcement (skill-first gate)
- Layer 0.5: State-file pending_command_intent check, topic drift prevention
- Layer 1: First-tool coherence validation
- Layer 1.5: Dynamic knowledge skill detection
- Layer 2: Execution pattern validation (regex + daemon)

These tests capture what the function DOES, not what it SHOULD do.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path for direct module import
SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_ROOT))

from skill_guard.PreToolUse.PreToolUse_skill_pattern_gate import handle_pre_tool_use


class TestHandlePreToolUseBasicSignature:
    """Tests for basic function existence and signature."""

    def test_handle_pre_tool_use_is_callable(self):
        """Characterization: function is importable and callable."""
        assert callable(handle_pre_tool_use)

    def test_handle_pre_tool_use_returns_dict(self):
        """Characterization: function returns a dict for minimal input."""
        result = handle_pre_tool_use({"tool_name": "Bash", "input": {}})
        assert isinstance(result, dict)

    def test_handle_pre_tool_use_signature_accepts_dict(self):
        """Characterization: function accepts dict with tool_name and input."""
        # Should not raise
        result = handle_pre_tool_use({"tool_name": "Read", "input": {"file_path": "test.txt"}})
        assert isinstance(result, dict)


class TestHandlePreToolUseStatelessSkillFirstGate:
    """Tests for the stateless skill-first gate (lines 665-731)."""

    def _base_state(self):
        return {
            "skill": "test-skill",
            "required_tools": ["Bash"],
            "allowed_first_tools": ["Bash"],
            "first_tool_validated": False,
        }

    def test_no_user_message_returns_empty(self):
        """Characterization: no user message means no slash command to enforce."""
        with patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_state", return_value={}), \
             patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_command_intent", return_value=None):
            result = handle_pre_tool_use({"tool_name": "Bash", "input": {"command": "ls"}})
        assert result == {}

    def test_no_state_returns_empty(self):
        """Characterization: no skill state means allow all tools."""
        with patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_state", return_value=None), \
             patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_command_intent", return_value=None):
            result = handle_pre_tool_use({"tool_name": "Bash", "input": {"command": "ls"}})
        assert result == {}


class TestHandlePreToolUseInvestigationTools:
    """Tests for investigation tools always-allowed behavior (line 735-736)."""

    def test_read_tool_is_allowed(self):
        """Characterization: Read tool is always allowed (investigation tool)."""
        with patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_state", return_value={"skill": "test"}), \
             patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_command_intent", return_value=None):
            result = handle_pre_tool_use({"tool_name": "Read", "input": {"file_path": "test.txt"}})
        assert result == {}

    def test_grep_tool_is_allowed(self):
        """Characterization: Grep tool is always allowed (investigation tool)."""
        with patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_state", return_value={"skill": "test"}), \
             patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_command_intent", return_value=None):
            result = handle_pre_tool_use({"tool_name": "Grep", "input": {"pattern": "test"}})
        assert result == {}

    def test_skill_tool_is_allowed(self):
        """Characterization: Skill tool is always allowed (investigation tool)."""
        with patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_state", return_value={"skill": "test"}), \
             patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_command_intent", return_value=None):
            result = handle_pre_tool_use({"tool_name": "Skill", "input": {"skill": "test"}})
        assert result == {}


class TestHandlePreToolUseTopicDriftPrevention:
    """Tests for topic drift prevention (lines 796-836)."""

    def test_topic_drift_blocks_do_not_distract(self):
        """Characterization: tool targeting deferred item triggers block."""
        state = {
            "skill": "test-skill",
            "workflow_stage": {
                "active_step": "step1",
                "do_not_distract": ["important.txt"],
            },
        }
        with patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_state", return_value=state), \
             patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_command_intent", return_value=None):
            result = handle_pre_tool_use({
                "tool_name": "Read",
                "input": {"file_path": "important.txt"},
                "user_message": "some context"
            })
        assert result.get("block") is True
        assert "TOPIC DRIFT PREVENTION" in result.get("reason", "")


class TestHandlePreToolUseKnowledgeSkillDetection:
    """Tests for dynamic knowledge skill detection (lines 851-863)."""

    def test_knowledge_skill_with_no_required_tools_returns_empty(self):
        """Characterization: skill with empty required_tools is treated as knowledge skill."""
        state = {
            "skill": "ask",
            "required_tools": [],
        }
        with patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_state", return_value=state), \
             patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_command_intent", return_value=None):
            result = handle_pre_tool_use({"tool_name": "Bash", "input": {"command": "ls"}})
        assert result == {}


class TestHandlePreToolUseExecutionPatternValidation:
    """Tests for execution pattern validation (lines 865-913)."""

    def _execution_state(self):
        return {
            "skill": "yt-is",
            "required_tools": ["Bash"],
            "allowed_first_tools": ["Bash"],
            "first_tool_validated": False,
            "required_first_command_patterns": [r"^csf-source\s+sync(?:\s|$)"],
            "required_first_command_hint": "Use csf-source sync first.",
            "first_command_validated": False,
        }

    def test_execution_pattern_valid_returns_empty(self):
        """Characterization: valid execution pattern allows tool."""
        with patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_state", return_value=self._execution_state()), \
             patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_command_intent", return_value=None), \
             patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate.get_skill_config", return_value={
                 "tools": ["Bash"],
                 "pattern": r"^csf-source\s+(sync|list|add|fetch)(?:\s|$)",
                 "hint": "Use csf-source via yt-is workflow.",
                 "intent_enabled": False,
             }), \
             patch("skill_guard.skill_execution_state.mark_first_tool_validated"), \
             patch("skill_guard.skill_execution_state.mark_first_command_validated"):
            result = handle_pre_tool_use({"tool_name": "Bash", "input": {"command": "csf-source sync"}})

        assert result == {}

    def test_execution_pattern_invalid_returns_block(self):
        """Characterization: invalid execution pattern blocks tool."""
        with patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_state", return_value=self._execution_state()), \
             patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_command_intent", return_value=None), \
             patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate.get_skill_config", return_value={
                 "tools": ["Bash"],
                 "pattern": r"^csf-source\s+(sync|list|add|fetch)(?:\s|$)",
                 "hint": "Use csf-source via yt-is workflow.",
                 "intent_enabled": False,
             }), \
             patch("skill_guard.skill_execution_state.mark_first_tool_validated"), \
             patch("skill_guard.skill_execution_state.mark_first_command_validated"):
            result = handle_pre_tool_use({"tool_name": "Bash", "input": {"command": "csf-source invalid"}})

        assert result.get("block") is True
        assert "execution pattern mismatch" in result.get("reason", "")


class TestHandlePreToolUseNoSkillConfig:
    """Tests for when no skill config is found (fail-open behavior)."""

    def test_no_skill_config_returns_empty(self):
        """Characterization: no valid skill config means fail-open (allow tool)."""
        state = {
            "skill": "unknown-skill",
            "required_tools": ["Bash"],
        }
        with patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_state", return_value=state), \
             patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_command_intent", return_value=None), \
             patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate.get_skill_config", return_value=None):
            result = handle_pre_tool_use({"tool_name": "Bash", "input": {"command": "ls"}})
        assert result == {}

    def test_empty_skill_config_returns_empty(self):
        """Characterization: empty skill config means fail-open (allow tool)."""
        state = {
            "skill": "test-skill",
            "required_tools": ["Bash"],
        }
        with patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_state", return_value=state), \
             patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate._read_pending_command_intent", return_value=None), \
             patch("skill_guard.PreToolUse.PreToolUse_skill_pattern_gate.get_skill_config", return_value={}):
            result = handle_pre_tool_use({"tool_name": "Bash", "input": {"command": "ls"}})
        assert result == {}
