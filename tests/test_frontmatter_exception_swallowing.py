"""Characterization tests for _load_skill_frontmatter exception swallowing.

These tests CAPTURE CURRENT BEHAVIOR before refactoring.
Run with: pytest tests/test_frontmatter_exception_swallowing.py -v

The bug: _load_skill_frontmatter() at line 386 uses `except Exception: pass`
which silently swallows YAML parse failures AND also catches KeyboardInterrupt
and SystemExit (which should NEVER be caught with `except Exception`).

These tests document what the code currently DOES, not what it SHOULD do.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestLoadSkillFrontmatterExceptionSwallowing:
    """Tests that capture the current silent exception swallowing behavior."""

    @pytest.fixture
    def skill_file_mock(self, tmp_path):
        """Create a mock SKILL.md file path in temp directory."""
        skill_dir = tmp_path / "skills" / "test_skill"
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"
        return skill_file

    def test_yaml_parse_failure_returns_none_silently(self, skill_file_mock, monkeypatch):
        """Characterization: YAML parse failures are silently absorbed, returning default dict.

        Given: A SKILL.md with invalid YAML in the frontmatter section
        When: _load_skill_frontmatter attempts to parse it
        Then: No exception is raised, instead returns default result dict
        """
        import yaml
        # Create SKILL.md with invalid YAML between --- markers
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

        # This should NOT raise - current behavior swallows the exception
        result = _load_skill_frontmatter("test_skill")

        # Default result is returned (all defaults, no parsed data)
        assert result["contract_type"] == "analysis"
        assert result["allowed_first_tools"] == []

    def test_keyboard_interrupt_caught_by_except_exception(self, skill_file_mock, monkeypatch):
        """Characterization: KeyboardInterrupt is caught by 'except Exception: pass'.

        Given: A SKILL.md with valid frontmatter
        When: yaml.safe_load raises KeyboardInterrupt
        Then: No KeyboardInterrupt propagates - it is silently swallowed
        """
        import yaml

        skill_file_mock.write_text(
            "---\ncontract_type: test\n---\n# Skill\n",
            encoding="utf-8"
        )

        original_safe_load = yaml.safe_load

        def mock_safe_load_with_interrupt(data):
            raise KeyboardInterrupt("User pressed Ctrl+C")

        monkeypatch.setattr(yaml, "safe_load", mock_safe_load_with_interrupt)
        monkeypatch.setattr(Path, "exists", lambda self: True)

        from skill_guard.skill_execution_state import _load_skill_frontmatter

        # This should NOT raise KeyboardInterrupt - current behavior swallows it
        # The 'except Exception: pass' catches it since KeyboardInterrupt IS-A Exception
        result = _load_skill_frontmatter("test_skill")

        # Default result is returned
        assert result["contract_type"] == "analysis"

    def test_system_exit_caught_by_except_exception(self, skill_file_mock, monkeypatch):
        """Characterization: SystemExit is caught by 'except Exception: pass'.

        Given: A SKILL.md with valid frontmatter
        When: yaml.safe_load raises SystemExit
        Then: No SystemExit propagates - it is silently swallowed
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

        from skill_guard.skill_execution_state import _load_skill_frontmatter

        # This should NOT raise SystemExit - current behavior swallows it
        # The 'except Exception: pass' catches it since SystemExit IS-A Exception
        result = _load_skill_frontmatter("test_skill")

        # Default result is returned
        assert result["contract_type"] == "analysis"

    def test_yaml_errors_indistinguishable_from_success(self, skill_file_mock, monkeypatch):
        """Characterization: YAML YAMLError looks identical to successful parse in results.

        Given: A SKILL.md with YAML parseable but semantically wrong content
        When: _load_skill_frontmatter runs
        Then: Same default result as when YAML completely fails to parse
        """
        import yaml

        # Case 1: Completely unparseable YAML
        skill_file_mock.write_text(
            "---\ninvalid[[[ yaml: content\n---\n# Skill\n",
            encoding="utf-8"
        )

        def mock_read_text_unparseable(self, encoding=None, errors=None):
            return "---\ninvalid[[[ yaml: content\n---\n# Skill\n"

        monkeypatch.setattr(Path, "read_text", mock_read_text_unparseable)
        monkeypatch.setattr(Path, "exists", lambda self: True)

        from skill_guard.skill_execution_state import _load_skill_frontmatter

        result_unparseable = _load_skill_frontmatter("test_skill")

        # Case 2: YAML parses but returns wrong type (not a dict)
        skill_file_mock.write_text(
            "---\n- just a list\n- not a dict\n---\n# Skill\n",
            encoding="utf-8"
        )

        def mock_read_text_list(self, encoding=None, errors=None):
            return "---\n- just a list\n- not a dict\n---\n# Skill\n"

        monkeypatch.setattr(Path, "read_text", mock_read_text_list)

        result_list = _load_skill_frontmatter("test_skill")

        # Both return the same default result - errors are indistinguishable from success
        assert result_unparseable == result_list
        assert result_unparseable["allowed_first_tools"] == []
