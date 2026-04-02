"""Tests for skill_forced_eval.py - Skill Forced-Eval Hook."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock the non-portable imports before importing the module
with patch.dict("sys.modules", {
    "__lib.hook_base": MagicMock(),
    "UserPromptSubmit_modules.base": MagicMock(),
    "UserPromptSubmit_modules.registry": MagicMock(),
}):
    from skill_guard import skill_forced_eval as sfe


class TestSafeId:
    """Tests for _safe_id sanitization."""

    @pytest.mark.parametrize("input_val,expected", [
        ("normal_id", "normal_id"),
        ("id-with-dots.and.dashes", "id-with-dots.and.dashes"),
        ("ID WITH SPACES", "ID_WITH_SPACES"),
        # Multiple special chars collapse to single underscore
        ("id!@#$%^&*()", "id_"),
        ("UPPERCASE", "UPPERCASE"),
        ("123numeric", "123numeric"),
    ])
    def test_safe_id_various_inputs(self, input_val: str, expected: str) -> None:
        """_safe_id should preserve alphanumeric, dots, hyphens, underscores."""
        result = sfe._safe_id(input_val)
        assert result == expected

    def test_safe_id_empty_string(self) -> None:
        """_safe_id on empty string returns empty."""
        result = sfe._safe_id("")
        assert result == ""


class TestExtractSlashCommands:
    """Tests for _extract_slash_commands."""

    def test_single_command(self) -> None:
        """Should extract single slash command."""
        result = sfe._extract_slash_commands("Use /gto to track goals")
        assert result == ["gto"]

    def test_multiple_commands(self) -> None:
        """Should extract multiple slash commands."""
        result = sfe._extract_slash_commands("Use /code and /docs together")
        assert set(result) == {"code", "docs"}

    def test_command_at_start(self) -> None:
        """Should detect command at start of prompt."""
        result = sfe._extract_slash_commands("/skill-name do something")
        assert result == ["skill-name"]

    def test_command_at_end(self) -> None:
        """Should detect command at end of prompt."""
        result = sfe._extract_slash_commands("Finish the task with /gto")
        assert result == ["gto"]

    def test_no_commands(self) -> None:
        """Should return empty list when no commands."""
        result = sfe._extract_slash_commands("Just a regular prompt")
        assert result == []

    def test_case_insensitive(self) -> None:
        """Should return lowercase commands regardless of input case."""
        result = sfe._extract_slash_commands("Use /GTO and /Code")
        assert set(result) == {"gto", "code"}


class TestGetMatchingSkills:
    """Tests for _get_matching_skills."""

    @patch.object(sfe, "_get_registered_skills", return_value={"gto", "code", "docs"})
    def test_returns_matching_registered(self, mock_registered) -> None:
        """Should return only skills that are both invoked and registered."""
        result = sfe._get_matching_skills("Use /gto and /unknown")
        assert result == ["gto"]

    @patch.object(sfe, "_get_registered_skills", return_value=set())
    def test_empty_when_no_registered(self, mock_registered) -> None:
        """Should return empty when no skills registered."""
        result = sfe._get_matching_skills("Use /gto")
        assert result == []


class TestFormatSkillList:
    """Tests for _format_skill_list."""

    def test_empty_skills(self) -> None:
        """Should return No skills found for empty list."""
        result = sfe._format_skill_list([], {})
        assert "No skills found" in result

    def test_single_skill_no_tools(self) -> None:
        """Should format skill without tools."""
        result = sfe._format_skill_list(["gto"], {})
        assert "- gto" in result


class TestDetectToolConflicts:
    """Tests for _detect_tool_conflicts."""

    def test_no_conflicts(self) -> None:
        """Should return empty when no conflicts."""
        metadata = {
            "skill_a": {"allowed_tools": ["Read"]},
            "skill_b": {"allowed_tools": ["Edit"]},
        }
        result = sfe._detect_tool_conflicts(metadata, ["skill_a", "skill_b"])
        assert result == []

    def test_bash_vs_readonly_conflict(self) -> None:
        """Should detect Bash vs read-only conflict."""
        metadata = {
            "bash_skill": {"allowed_tools": ["Bash"]},
            "readonly_skill": {"allowed_tools": ["Read", "Glob"]},
        }
        result = sfe._detect_tool_conflicts(metadata, ["bash_skill", "readonly_skill"])
        assert len(result) == 1


class TestCleanupStaleStateFiles:
    """Tests for _cleanup_stale_state_files."""

    def test_cleanup_removes_stale_files(self, tmp_path: Path) -> None:
        """Should remove state files older than TTL."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()

        stale_file = state_dir / "eval_state_test.json"
        stale_file.write_text(json.dumps({
            "created_at": time.time() - 600,
            "invoked_skills": ["gto"]
        }))

        with patch.object(sfe, "_STATE_DIR", state_dir):
            with patch.object(sfe, "_FALLBACK_STATE_DIR", tmp_path / "nonexistent"):
                removed = sfe._cleanup_stale_state_files()

        assert removed >= 1
        assert not stale_file.exists()


class TestClearCaches:
    """Tests for _clear_caches."""

    def test_clears_global_caches(self) -> None:
        """Should reset cached skill lists to None."""
        sfe._registered_skills = ["cached_skill"]
        sfe._skill_metadata = {"cached": {"meta": True}}

        sfe._clear_caches()

        assert sfe._registered_skills is None
        assert sfe._skill_metadata is None
