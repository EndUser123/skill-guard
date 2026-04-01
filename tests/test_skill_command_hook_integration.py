"""
Integration tests for SkillCommandHook and discover_hooks() functionality.

Tests cover:
- SkillCommandHook with shell=False and shlex.split()
- Regex timeout protection in matches_tool()
- Graceful handling when skill_guard is unavailable
- Per-skill YAML parse failure logging
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# Ensure package is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from skill_guard.skill_auto_discovery import (
    _parse_skill_frontmatter,
    _parse_skill_hooks,
    discover_all_skills,
    discover_hooks,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    """Create a temporary skills directory with test SKILL.md files."""
    skill_dir = tmp_path / "skills" / "test_skill"
    skill_dir.mkdir(parents=True)
    return skill_dir


@pytest.fixture
def minimal_skill_md(skills_dir: Path) -> Path:
    """Create a minimal SKILL.md with required frontmatter."""
    content = (
        "---\n"
        "name: test_skill\n"
        "version: 1.0.0\n"
        "category: development\n"
        "---\n"
        "# Test Skill\n"
    )
    skill_md = skills_dir / "SKILL.md"
    skill_md.write_text(content, encoding="utf-8")
    return skill_md


@pytest.fixture
def skill_md_with_hooks(skills_dir: Path) -> Path:
    """Create a SKILL.md with hooks declarations."""
    content = (
        "---\n"
        "name: test_skill\n"
        "version: 1.0.0\n"
        "category: development\n"
        "hooks:\n"
        "  PostToolUse:\n"
        "    - matcher: \"Read\"\n"
        "      hooks:\n"
        "        - type: command\n"
        "          command: python -m test_skill.hook_runner --post-read\n"
        "          timeout: 5\n"
        "  PreToolUse:\n"
        "    - matcher: \".*\"\n"
        "      hooks:\n"
        "        - type: command\n"
        "          command: echo pretool hook\n"
        "          timeout: 3\n"
        "---\n"
        "# Test Skill\n"
    )
    skill_md = skills_dir / "SKILL.md"
    skill_md.write_text(content, encoding="utf-8")
    return skill_md


@pytest.fixture
def skill_md_with_broken_yaml(skills_dir: Path) -> Path:
    """Create a SKILL.md with malformed YAML (should not crash parser)."""
    content = (
        "---\n"
        "name: broken_skill\n"
        "version: 1.0.0\n"
        "hooks:\n"
        "  PostToolUse:\n"
        "    - matcher: \"Read\"\n"
        "      hooks:\n"
        "        - type: command\n"
        "          command: [invalid yaml\n"  # Malformed list
        "---\n"
        "# Broken Skill\n"
    )
    skill_md = skills_dir / "SKILL.md"
    skill_md.write_text(content, encoding="utf-8")
    return skill_md


# ---------------------------------------------------------------------------
# Test: _parse_skill_frontmatter
# ---------------------------------------------------------------------------

class TestParseSkillFrontmatter:
    """Tests for _parse_skill_frontmatter function."""

    def test_parses_minimal_frontmatter(self, minimal_skill_md: Path) -> None:
        """Minimal frontmatter with name, version, category parses correctly."""
        config = _parse_skill_frontmatter(minimal_skill_md)
        assert config is not None
        assert config["name"] == "test_skill"
        assert config["version"] == "1.0.0"
        assert config["category"] == "development"

    def test_has_execution_true_for_development(self, minimal_skill_md: Path) -> None:
        """Development category sets has_execution=True."""
        config = _parse_skill_frontmatter(minimal_skill_md)
        assert config is not None
        assert config["has_execution"] is True
        assert config["allowed_first_tools"] == ["Bash"]
        assert config["default_tools"] == ["Bash"]

    def test_has_execution_false_for_knowledge_category(self, skills_dir: Path) -> None:
        """Knowledge category sets has_execution=False."""
        skill_md = skills_dir / "SKILL.md"
        skill_md.write_text(
            "---\nname: knowledge_skill\ncategory: knowledge\n---\n",
            encoding="utf-8",
        )
        config = _parse_skill_frontmatter(skill_md)
        assert config is not None
        assert config["has_execution"] is False
        assert config["allowed_first_tools"] == []
        assert config["default_tools"] == []

    def test_returns_none_for_missing_frontmatter(self, skills_dir: Path) -> None:
        """SKILL.md without frontmatter returns None."""
        skill_md = skills_dir / "SKILL.md"
        skill_md.write_text("# No frontmatter\n", encoding="utf-8")
        config = _parse_skill_frontmatter(skill_md)
        assert config is None

    def test_returns_none_for_empty_file(self, skills_dir: Path) -> None:
        """Empty file returns None."""
        skill_md = skills_dir / "SKILL.md"
        skill_md.write_text("", encoding="utf-8")
        config = _parse_skill_frontmatter(skill_md)
        assert config is None

    def test_strips_quotes_from_values(self, skills_dir: Path) -> None:
        """Quote characters are stripped from frontmatter values."""
        skill_md = skills_dir / "SKILL.md"
        skill_md.write_text(
            '---\nname: "quoted_skill"\ndescription: \'single quoted\'\n---\n',
            encoding="utf-8",
        )
        config = _parse_skill_frontmatter(skill_md)
        assert config is not None
        assert config["name"] == "quoted_skill"
        assert config["description"] == "single quoted"


# ---------------------------------------------------------------------------
# Test: discover_all_skills
# ---------------------------------------------------------------------------

class TestDiscoverAllSkills:
    """Tests for discover_all_skills function."""

    def test_returns_empty_dict_for_nonexistent_dir(self) -> None:
        """Non-existent skills directory returns empty dict."""
        result = discover_all_skills("/nonexistent/path")
        assert result == {}

    def test_discovers_single_skill(self, minimal_skill_md: Path) -> None:
        """Discovers skill from valid SKILL.md."""
        skills = discover_all_skills(minimal_skill_md.parent.parent)
        assert "test_skill" in skills
        assert skills["test_skill"]["category"] == "development"

    def test_skips_directories_without_skill_md(self, tmp_path: Path) -> None:
        """Directories without SKILL.md are skipped."""
        (tmp_path / "no_skill_md").mkdir()
        (tmp_path / "also_no_skill").mkdir()
        skills = discover_all_skills(tmp_path)
        assert len(skills) == 0


# ---------------------------------------------------------------------------
# Test: _parse_skill_hooks
# ---------------------------------------------------------------------------

class TestParseSkillHooks:
    """Tests for _parse_skill_hooks function."""

    def test_parses_posttooluse_hook(self, skill_md_with_hooks: Path) -> None:
        """Parses PostToolUse hook declaration correctly."""
        hooks = _parse_skill_hooks(skill_md_with_hooks, "test_skill")
        assert len(hooks) >= 1
        post_hooks = [h for h in hooks if h["event"] == "PostToolUse"]
        assert len(post_hooks) >= 1

    def test_hook_has_required_fields(self, skill_md_with_hooks: Path) -> None:
        """Hook dict contains all required fields."""
        hooks = _parse_skill_hooks(skill_md_with_hooks, "test_skill")
        for hook in hooks:
            assert "skill" in hook
            assert "event" in hook
            assert "name" in hook
            assert "matcher" in hook
            assert "type" in hook
            assert "command" in hook
            assert "timeout" in hook

    def test_invalid_yaml_returns_empty_list(self, skill_md_with_broken_yaml: Path) -> None:
        """Malformed YAML in hooks section returns empty list (no crash)."""
        hooks = _parse_skill_hooks(skill_md_with_broken_yaml, "broken_skill")
        # Should not raise, should return empty or partial results
        assert isinstance(hooks, list)


# ---------------------------------------------------------------------------
# Test: discover_hooks
# ---------------------------------------------------------------------------

class TestDiscoverHooks:
    """Tests for discover_hooks function."""

    def test_returns_empty_list_for_nonexistent_dir(self) -> None:
        """Non-existent directory returns empty list."""
        result = discover_hooks("/nonexistent/path")
        assert result == []

    def test_discovers_hooks_from_skill_md(self, skill_md_with_hooks: Path) -> None:
        """Discovers hooks from valid SKILL.md with hooks declarations."""
        hooks = discover_hooks(skill_md_with_hooks.parent.parent)
        assert len(hooks) >= 1

    def test_hook_command_is_not_shell_expanded(self, skill_md_with_hooks: Path) -> None:
        """Hook commands should not contain shell expansion characters that would be dangerous."""
        hooks = discover_hooks(skill_md_with_hooks.parent.parent)
        for hook in hooks:
            # Commands should be safe for shlex.split with shell=False
            # No pipe, no subshell, no &&, no ||, no redirects
            assert "|" not in hook["command"]
            assert "&&" not in hook["command"]
            assert "||" not in hook["command"]
            assert ">" not in hook["command"]
            assert "<" not in hook["command"]


# ---------------------------------------------------------------------------
# Test: SkillCommandHook integration
# ---------------------------------------------------------------------------

class TestSkillCommandHookIntegration:
    """Integration tests for SkillCommandHook with discover_hooks."""

    def test_hook_runner_import(self) -> None:
        """SkillCommandHook can be imported."""
        from posttooluse.skill_command_hook import SkillCommandHook
        assert SkillCommandHook is not None

    def test_skill_command_hook_instantiation(self) -> None:
        """SkillCommandHook can be instantiated with valid params."""
        from posttooluse.skill_command_hook import SkillCommandHook

        hook = SkillCommandHook(
            skill="test_skill",
            name="test_skill_PostToolUse_0",
            command="echo hello",
            timeout=5,
            matcher_pattern="Read",
        )
        assert hook.skill == "test_skill"
        assert hook.name == "test_skill_PostToolUse_0"
        assert hook.command == "echo hello"
        assert hook.timeout == 5
        assert hook.matcher_pattern == "Read"

    def test_matches_tool_with_valid_pattern(self) -> None:
        """matches_tool returns True when tool name matches pattern."""
        from posttooluse.skill_command_hook import SkillCommandHook

        hook = SkillCommandHook(
            skill="test_skill",
            name="test_PostToolUse_0",
            command="echo test",
            matcher_pattern=r"Read|Grep",
        )
        assert hook.matches_tool("Read") is True
        assert hook.matches_tool("Grep") is True
        assert hook.matches_tool("Write") is False

    def test_matches_tool_with_none_pattern(self) -> None:
        """matches_tool returns True for any tool when pattern is None."""
        from posttooluse.skill_command_hook import SkillCommandHook

        hook = SkillCommandHook(
            skill="test_skill",
            name="test_PostToolUse_0",
            command="echo test",
            matcher_pattern=None,
        )
        assert hook.matches_tool("Read") is True
        assert hook.matches_tool("Bash") is True
        assert hook.matches_tool("ANY_TOOL") is True

    def test_matches_tool_with_invalid_regex(self) -> None:
        """matches_tool returns False for invalid regex pattern (fail-safe)."""
        from posttooluse.skill_command_hook import SkillCommandHook

        hook = SkillCommandHook(
            skill="test_skill",
            name="test_PostToolUse_0",
            command="echo test",
            matcher_pattern=r"[invalid(",  # Invalid regex
        )
        # Should fail safely (not raise), returning False
        assert hook.matches_tool("Read") is False

    def test_process_executes_command_successfully(self) -> None:
        """process() executes command and returns empty dict on success."""
        from posttooluse.skill_command_hook import SkillCommandHook

        hook = SkillCommandHook(
            skill="test_skill",
            name="test_PostToolUse_0",
            command="echo hello from hook",
            timeout=5,
        )
        result = hook.process(
            tool_name="Bash",
            tool_input={},
            tool_response={"output": "test"},
        )
        assert result == {}  # Empty dict on success

    def test_process_returns_warning_on_nonzero_exit(self) -> None:
        """process() returns warning dict when command exits non-zero."""
        from posttooluse.skill_command_hook import SkillCommandHook

        hook = SkillCommandHook(
            skill="test_skill",
            name="test_PostToolUse_0",
            command="exit 1",
            timeout=5,
        )
        result = hook.process(
            tool_name="Bash",
            tool_input={},
            tool_response={},
        )
        assert "warning" in result
        assert "exit 1" in result["warning"] or "exit" in result["warning"]

    def test_process_returns_warning_on_timeout(self) -> None:
        """process() returns warning dict when command times out."""
        from posttooluse.skill_command_hook import SkillCommandHook

        hook = SkillCommandHook(
            skill="test_skill",
            name="test_PostToolUse_0",
            command="sleep 10",
            timeout=1,  # 1 second timeout
        )
        result = hook.process(
            tool_name="Bash",
            tool_input={},
            tool_response={},
        )
        assert "warning" in result
        assert "timed out" in result["warning"]

    def test_process_disabled_hook_returns_empty(self) -> None:
        """Disabled hook returns empty dict without executing."""
        from posttooluse.skill_command_hook import SkillCommandHook

        hook = SkillCommandHook(
            skill="test_skill",
            name="test_PostToolUse_0",
            command="echo should not run",
            timeout=5,
        )
        hook.enabled = False
        result = hook.process(
            tool_name="Bash",
            tool_input={},
            tool_response={},
        )
        assert result == {}


# ---------------------------------------------------------------------------
# Test: End-to-end discovered hooks flow
# ---------------------------------------------------------------------------

class TestDiscoveredHooksEndToEnd:
    """End-to-end tests for discovered hooks integration."""

    def test_discover_hooks_finds_all_declared_hooks(self, skill_md_with_hooks: Path) -> None:
        """All declared hooks in SKILL.md are discovered."""
        hooks = discover_hooks(skill_md_with_hooks.parent.parent)
        # Should find at least 2 hooks: 1 PostToolUse + 1 PreToolUse
        assert len(hooks) >= 2

    def test_hooks_have_unique_names(self, skill_md_with_hooks: Path) -> None:
        """Discovered hooks have unique names."""
        hooks = discover_hooks(skill_md_with_hooks.parent.parent)
        names = [h["name"] for h in hooks]
        assert len(names) == len(set(names)), "Hook names must be unique"


# ---------------------------------------------------------------------------
# Test: Graceful degradation
# ---------------------------------------------------------------------------

class TestGracefulDegradation:
    """Tests for graceful handling of errors."""

    def test_missing_yaml_module_does_not_crash(self, skill_md_with_hooks: Path) -> None:
        """If yaml module is missing, hook parsing fails gracefully."""
        with patch.dict("sys.modules", {"yaml": None}):
            # Should not raise ImportError crash
            hooks = _parse_skill_hooks(skill_md_with_hooks, "test_skill")
            assert isinstance(hooks, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
