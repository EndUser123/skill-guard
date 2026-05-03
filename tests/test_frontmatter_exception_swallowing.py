"""Tests for _load_skill_frontmatter exception handling.

These tests verify the CORRECT exception handling behavior:
- yaml.YAMLError and ImportError are caught and return None (with logging)
- KeyboardInterrupt and SystemExit propagate (NOT caught by the function)

Run with: pytest tests/test_frontmatter_exception_swallowing.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestLoadSkillFrontmatterExceptionHandling:
    """Tests for correct exception handling in _load_skill_frontmatter."""

    @pytest.fixture
    def skill_file_mock(self, tmp_path):
        """Create a mock SKILL.md file path in temp directory."""
        skill_dir = tmp_path / "skills" / "test_skill"
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"
        return skill_file

    def test_yaml_parse_failure_returns_none(self, skill_file_mock, monkeypatch):
        """YAML parse failures return None with logging.

        Given: A SKILL.md with invalid YAML in the frontmatter section
        When: _load_skill_frontmatter attempts to parse it
        Then: No exception is raised, returns None (with warning logged)
        """
        import yaml

        skill_file_mock.write_text(
            "---\ninvalid: yaml: content: here\n  missing: proper: structure\n---\n"
            "# Skill Content\n",
            encoding="utf-8"
        )

        def mock_read_text(self, encoding=None, errors=None):
            return "---\ninvalid: yaml: content: here\n  missing: proper: structure\n---\n# Skill Content\n"

        # Mock Path to use our temp file
        monkeypatch.setattr(Path, "read_text", mock_read_text)
        monkeypatch.setattr(Path, "exists", lambda self: True)

        from skill_guard.skill_execution_state import _load_skill_frontmatter

        # This should NOT raise - YAML errors are caught and return None
        result = _load_skill_frontmatter("test_skill")

        # Now returns None for YAML errors (logged warning)
        assert result is None

    def test_keyboard_interrupt_propagates(self, skill_file_mock, monkeypatch):
        """KeyboardInterrupt is NOT caught - it propagates.

        Given: A SKILL.md with valid frontmatter
        When: yaml.safe_load raises KeyboardInterrupt
        Then: KeyboardInterrupt propagates out of the function
        """
        import yaml

        skill_file_mock.write_text(
            "---\ncontract_type: test\n---\n# Skill\n",
            encoding="utf-8"
        )

        original_safe_load = yaml.safe_load

        def mock_safe_load_with_interrupt(data):
            raise KeyboardInterrupt("User pressed Ctrl+C")

        # Mock both yaml.safe_load and the path operations
        monkeypatch.setattr(yaml, "safe_load", mock_safe_load_with_interrupt)
        monkeypatch.setattr(Path, "exists", lambda self: True)
        monkeypatch.setattr(Path, "read_text", lambda self, encoding=None, errors=None: "---\ncontract_type: test\n---\n# Skill\n")

        from skill_guard.skill_execution_state import _load_skill_frontmatter

        # KeyboardInterrupt should propagate, not be caught
        with pytest.raises(KeyboardInterrupt):
            _load_skill_frontmatter("test_skill")

    def test_system_exit_propagates(self, skill_file_mock, monkeypatch):
        """SystemExit is NOT caught - it propagates.

        Given: A SKILL.md with valid frontmatter
        When: yaml.safe_load raises SystemExit
        Then: SystemExit propagates out of the function
        """
        import yaml

        skill_file_mock.write_text(
            "---\ncontract_type: test\n---\n# Skill\n",
            encoding="utf-8"
        )

        def mock_safe_load_with_system_exit(data):
            raise SystemExit("sys.exit called")

        monkeypatch.setattr(yaml, "safe_load", mock_safe_load_with_system_exit)
        monkeypatch.setattr(Path, "exists", lambda self: True)
        monkeypatch.setattr(Path, "read_text", lambda self, encoding=None, errors=None: "---\ncontract_type: test\n---\n# Skill\n")

        from skill_guard.skill_execution_state import _load_skill_frontmatter

        # SystemExit should propagate, not be caught
        with pytest.raises(SystemExit):
            _load_skill_frontmatter("test_skill")

    def test_yaml_errors_distinguishable_from_non_dict_results(self, skill_file_mock, monkeypatch):
        """YAML parse errors return None, but non-dict YAML returns default dict (now distinguishable).

        Given: Two SKILL.md files - one with unparseable YAML, one with YAML that parses to a list
        When: _load_skill_frontmatter runs on each
        Then: Unparseable YAML returns None, non-dict YAML returns default dict (they are now distinguishable)
        """
        import yaml

        # Case 1: YAML that actually fails to parse (raises YAMLError) -> returns None
        # Use key: value without colon properly - "invalid: yaml: content" is invalid YAML
        skill_file_mock.write_text(
            "---\ninvalid: yaml: content: here\n  missing: proper: structure\n---\n# Skill\n",
            encoding="utf-8"
        )

        def mock_read_text_unparseable(self, encoding=None, errors=None):
            return "---\ninvalid: yaml: content: here\n  missing: proper: structure\n---\n# Skill\n"

        monkeypatch.setattr(Path, "read_text", mock_read_text_unparseable)
        monkeypatch.setattr(Path, "exists", lambda self: True)

        from skill_guard.skill_execution_state import _load_skill_frontmatter

        result_unparseable = _load_skill_frontmatter("test_skill")

        # Case 2: YAML parses but returns wrong type (not a dict) -> returns default dict
        skill_file_mock.write_text(
            "---\n- just a list\n- not a dict\n---\n# Skill\n",
            encoding="utf-8"
        )

        def mock_read_text_list(self, encoding=None, errors=None):
            return "---\n- just a list\n- not a dict\n---\n# Skill\n"

        monkeypatch.setattr(Path, "read_text", mock_read_text_list)

        result_list = _load_skill_frontmatter("test_skill")

        # Now distinguishable: unparseable returns None, non-dict returns default dict
        assert result_unparseable is None
        assert result_list is not None
        assert result_list["contract_type"] == "analysis"  # default dict, not None