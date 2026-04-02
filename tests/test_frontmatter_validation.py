"""Tests for frontmatter validation in skill_execution_state."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from skill_guard import skill_execution_state


class TestValidateSkillFrontmatter:
    """Tests for _validate_skill_frontmatter function."""

    def _make_skill_md(self, tmp_path: Path, frontmatter: str) -> Path:
        """Create a skill directory with SKILL.md for testing."""
        skill_dir = tmp_path / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(f"---\n{frontmatter}\n---\n# Test Skill\n", encoding="utf-8")
        return skill_file

    def test_validate_returns_empty_for_complete_frontmatter(self, tmp_path: Path) -> None:
        """Complete frontmatter with all required fields returns no warnings."""
        self._make_skill_md(
            tmp_path,
            "name: test-skill\ndescription: A test skill\nversion: '1.0.0'\nenforcement: strict\ncategory: development",
        )
        with patch.object(skill_execution_state, "STATE_DIR", tmp_path):
            warnings = skill_execution_state._validate_skill_frontmatter("test-skill")
        assert warnings == [], f"Expected no warnings, got: {warnings}"

    def test_validate_warns_missing_enforcement(self, tmp_path: Path) -> None:
        """Missing enforcement field produces a warning."""
        self._make_skill_md(
            tmp_path,
            "name: test-skill\ndescription: A test skill\nversion: '1.0.0'\ncategory: development",
        )
        with patch.object(skill_execution_state, "STATE_DIR", tmp_path):
            warnings = skill_execution_state._validate_skill_frontmatter("test-skill")
        enforcement_warnings = [w for w in warnings if "enforcement" in w]
        assert len(enforcement_warnings) == 1, f"Expected 1 enforcement warning, got: {warnings}"

    def test_validate_warns_missing_name(self, tmp_path: Path) -> None:
        """Missing name field produces a warning."""
        self._make_skill_md(
            tmp_path,
            "description: A test skill\nversion: '1.0.0'\nenforcement: strict\ncategory: development",
        )
        with patch.object(skill_execution_state, "STATE_DIR", tmp_path):
            warnings = skill_execution_state._validate_skill_frontmatter("test-skill")
        name_warnings = [w for w in warnings if "name" in w]
        assert len(name_warnings) == 1, f"Expected 1 name warning, got: {warnings}"

    def test_validate_warns_missing_description(self, tmp_path: Path) -> None:
        """Missing description field produces a warning."""
        self._make_skill_md(
            tmp_path,
            "name: test-skill\nversion: '1.0.0'\nenforcement: strict\ncategory: development",
        )
        with patch.object(skill_execution_state, "STATE_DIR", tmp_path):
            warnings = skill_execution_state._validate_skill_frontmatter("test-skill")
        desc_warnings = [w for w in warnings if "description" in w]
        assert len(desc_warnings) == 1, f"Expected 1 description warning, got: {warnings}"

    def test_validate_warns_missing_version(self, tmp_path: Path) -> None:
        """Missing version field produces a warning."""
        self._make_skill_md(
            tmp_path,
            "name: test-skill\ndescription: A test skill\nenforcement: strict\ncategory: development",
        )
        with patch.object(skill_execution_state, "STATE_DIR", tmp_path):
            warnings = skill_execution_state._validate_skill_frontmatter("test-skill")
        version_warnings = [w for w in warnings if "version" in w]
        assert len(version_warnings) == 1, f"Expected 1 version warning, got: {warnings}"

    def test_validate_warns_missing_multiple_fields(self, tmp_path: Path) -> None:
        """Multiple missing fields produce multiple warnings."""
        self._make_skill_md(tmp_path, "name: test-skill\ndescription: A test skill")
        with patch.object(skill_execution_state, "STATE_DIR", tmp_path):
            warnings = skill_execution_state._validate_skill_frontmatter("test-skill")
        assert len(warnings) >= 2, f"Expected >=2 warnings for missing version/enforcement, got: {warnings}"

    def test_validate_returns_empty_for_nonexistent_skill(self, tmp_path: Path) -> None:
        """Nonexistent skill returns empty list (no error)."""
        with patch.object(skill_execution_state, "STATE_DIR", tmp_path):
            warnings = skill_execution_state._validate_skill_frontmatter("nonexistent-skill")
        assert warnings == [], f"Expected no warnings for nonexistent skill, got: {warnings}"

    def test_validate_invalid_enforcement_value(self, tmp_path: Path) -> None:
        """Invalid enforcement value produces a warning."""
        self._make_skill_md(
            tmp_path,
            "name: test-skill\ndescription: A test skill\nversion: '1.0.0'\nenforcement: invalid_value\ncategory: development",
        )
        with patch.object(skill_execution_state, "STATE_DIR", tmp_path):
            warnings = skill_execution_state._validate_skill_frontmatter("test-skill")
        enforcement_warnings = [w for w in warnings if "enforcement" in w]
        assert len(enforcement_warnings) == 1, f"Expected 1 enforcement warning, got: {warnings}"

    def test_validate_accepts_all_valid_enforcement_values(self, tmp_path: Path) -> None:
        """All valid enforcement values (strict, advisory, none) produce no warning."""
        for tier in ("strict", "advisory", "none"):
            skill_dir = tmp_path / "skills" / f"test-skill-{tier}"
            skill_dir.mkdir(parents=True)
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text(
                f"---\nname: test-skill-{tier}\ndescription: Test\nversion: '1.0.0'\nenforcement: {tier}\ncategory: dev\n---\n# Test\n",
                encoding="utf-8",
            )
        for tier in ("strict", "advisory", "none"):
            with patch.object(skill_execution_state, "STATE_DIR", tmp_path):
                warnings = skill_execution_state._validate_skill_frontmatter(f"test-skill-{tier}")
            assert warnings == [], f"Expected no warnings for enforcement={tier}, got: {warnings}"


class TestSkillLoadedIncludesFrontmatterWarnings:
    """Tests that set_skill_loaded includes frontmatter_warnings in state."""

    def _make_skill_md(self, tmp_path: Path, skill_name: str, frontmatter: str) -> None:
        """Create a skill directory with SKILL.md."""
        skill_dir = tmp_path / "skills" / skill_name
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(f"---\n{frontmatter}\n---\n# Test Skill\n", encoding="utf-8")

    def test_set_skill_loaded_includes_frontmatter_warnings(
        self, tmp_path: Path, monkeypatch: pytest
    ) -> None:
        """set_skill_loaded adds frontmatter_warnings to state when fields are missing."""
        self._make_skill_md(
            tmp_path,
            "test-frontmatter-warnings",
            "name: test-frontmatter-warnings\ndescription: Test skill",
            # Missing version and enforcement
        )

        captured_states: list[dict] = []

        def mock_append_event(*args, **kwargs) -> None:
            if args[3] == "skill_loaded":
                captured_states.append(args[4])

        monkeypatch.setattr(skill_execution_state, "_get_active_turn_scope", lambda: ("test-terminal", "test-turn"))
        monkeypatch.setattr(skill_execution_state, "_get_ledger_module", lambda: type("MockLedger", (), {"append_event": mock_append_event}))
        monkeypatch.setattr(skill_execution_state, "STATE_DIR", tmp_path)

        skill_execution_state.set_skill_loaded("test-frontmatter-warnings")

        assert len(captured_states) == 1, f"Expected 1 state, got {len(captured_states)}"
        state = captured_states[0]
        assert "frontmatter_warnings" in state, f"frontmatter_warnings not in state: {state.keys()}"
        assert len(state["frontmatter_warnings"]) >= 2, (
            f"Expected >=2 warnings (version, enforcement), got: {state['frontmatter_warnings']}"
        )

    def test_set_skill_loaded_no_warnings_for_complete_frontmatter(
        self, tmp_path: Path, monkeypatch: pytest
    ) -> None:
        """set_skill_loaded has empty frontmatter_warnings when all fields present."""
        self._make_skill_md(
            tmp_path,
            "test-complete-skill",
            "name: test-complete-skill\ndescription: Complete\nversion: '1.0.0'\nenforcement: strict\ncategory: dev",
        )

        captured_states: list[dict] = []

        def mock_append_event(*args, **kwargs) -> None:
            if args[3] == "skill_loaded":
                captured_states.append(args[4])

        monkeypatch.setattr(skill_execution_state, "_get_active_turn_scope", lambda: ("test-terminal", "test-turn"))
        monkeypatch.setattr(skill_execution_state, "_get_ledger_module", lambda: type("MockLedger", (), {"append_event": mock_append_event}))
        monkeypatch.setattr(skill_execution_state, "STATE_DIR", tmp_path)

        skill_execution_state.set_skill_loaded("test-complete-skill")

        assert len(captured_states) == 1
        state = captured_states[0]
        assert state.get("frontmatter_warnings") == [], f"Expected no warnings, got: {state.get('frontmatter_warnings')}"
