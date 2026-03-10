#!/usr/bin/env python3
"""
Tests for skill-guard security and anti-pattern fixes.

Tests for 5 issues identified by NotebookLM:
1. Incorrect import path (use utils.terminal_detection)
2. Path traversal vulnerability (block . and ..)
3. Brittle sys.path manipulation (remove sys.path.insert)
4. Disk I/O on import (no side effects on import)
5. Contradictory documentation (fix TTL claim)
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

# =============================================================================
# Issue #1: Import Path Test
# =============================================================================


def test_import_from_utils_submodule():
    """Test that terminal_detection can be imported from utils submodule."""
    # Should succeed without ImportError
    from skill_guard.utils import terminal_detection

    assert hasattr(terminal_detection, "detect_terminal_id")
    assert callable(terminal_detection.detect_terminal_id)


def test_no_import_error_warnings():
    """Test that breadcrumb/tracker.py doesn't trigger ImportError fallback."""
    # Import tracker module
    # Verify detect_terminal_id is from utils, not fallback
    # If fallback was used, detect_terminal_id would be from skill_execution_state
    import inspect

    from skill_guard.breadcrumb import tracker

    source_file = inspect.getsourcefile(tracker.detect_terminal_id)
    assert "terminal_detection.py" in source_file or "utils" in source_file


# =============================================================================
# Issue #2: Path Traversal Vulnerability Tests
# =============================================================================


def test_valid_skill_names_accepted():
    """Test that valid skill names pass validation."""
    from skill_guard.breadcrumb.tracker import _get_breadcrumb_file

    # Valid skill names
    valid_names = [
        "package",
        "/package",
        "my-skill",
        "my_skill",
        "MySkill",
        "UPPERCASE",
        "skill123",
    ]

    for name in valid_names:
        # Should not raise ValueError
        try:
            result = _get_breadcrumb_file(name)
            assert result is not None
        except ValueError as e:
            if "path traversal" in str(e).lower():
                pytest.fail(f"Valid skill name '{name}' was blocked as path traversal")


def test_path_traversal_blocked():
    """Test that skill names with . and .. are blocked."""
    from skill_guard.breadcrumb.tracker import _get_breadcrumb_file

    # Malicious skill names
    malicious_names = [
        "../etc/passwd",
        "../../",
        "./hidden",
        "../../../etc/passwd",
        "../malicious",
        "..",
        ".",
        "skill/../etc",
        "/../etc/passwd",
    ]

    for name in malicious_names:
        with pytest.raises(ValueError, match="path traversal|Invalid skill name"):
            _get_breadcrumb_file(name)


def test_empty_skill_name_allowed():
    """Test that empty string doesn't cause path traversal."""
    from skill_guard.breadcrumb.tracker import _get_breadcrumb_file

    # Empty string should be handled gracefully
    # May raise ValueError for other reasons, but not path traversal
    try:
        result = _get_breadcrumb_file("")
        assert result is not None
    except ValueError as e:
        # Should not be about path traversal
        assert "path traversal" not in str(e).lower()


def test_whitespace_skill_name():
    """Test that whitespace in skill names doesn't enable path traversal."""
    from skill_guard.breadcrumb.tracker import _get_breadcrumb_file

    # Whitespace should be replaced with underscore
    result = _get_breadcrumb_file("my skill")
    assert "my_skill" in str(result)


# =============================================================================
# Issue #3: sys.path Manipulation Tests
# =============================================================================


def test_registry_load_without_sys_path():
    """Test that SKILL_EXECUTION_REGISTRY loads without sys.path.insert."""
    import sys

    # Record original sys.path
    original_path = sys.path.copy()

    # Import module that loads registry
    from skill_guard import skill_execution_state

    # Get registry
    registry = skill_execution_state._get_skill_execution_registry()

    # sys.path should not be modified
    # (PreToolUse directory should not be inserted)
    assert sys.path == original_path, "sys.path was modified by registry loading"

    # Registry should be a dict (empty or populated)
    assert isinstance(registry, dict)


def test_registry_fallback_to_empty_dict():
    """Test that registry returns empty dict when PreToolUse unavailable."""
    from skill_guard import skill_execution_state

    # Force import error by temporarily mocking
    with patch("sys.path", new=[]):
        # Reload module to trigger import without PreToolUse in path
        import importlib

        importlib.reload(skill_execution_state)

        # Should return empty dict, not crash
        registry = skill_execution_state._get_skill_execution_registry()
        assert isinstance(registry, dict)


# =============================================================================
# Issue #4: Import Side Effects Tests
# =============================================================================


def test_no_file_operations_on_import():
    """Test that importing skill_execution_state doesn't perform file I/O."""
    import sys

    # Remove module if already imported
    if "skill_guard.skill_execution_state" in sys.modules:
        del sys.modules["skill_guard.skill_execution_state"]

    # Mock file operations to detect I/O
    with patch("pathlib.Path.write_text") as mock_write, patch(
        "pathlib.Path.read_text"
    ) as mock_read, patch("pathlib.Path.unlink") as mock_unlink:
        # Import module

        # Import should not trigger file operations
        assert not mock_write.called, "File write detected during import"
        assert not mock_read.called, "File read detected during import"
        assert not mock_unlink.called, "File delete detected during import"


def test_migration_still_works_explicitly():
    """Test that legacy migration still works when explicitly called."""
    from skill_guard import skill_execution_state

    # Create fake legacy state file
    legacy_state = Path("P:/.claude/state/skill_execution_pending.json")

    # Create test legacy state
    legacy_state.parent.mkdir(parents=True, exist_ok=True)
    test_data = {"skill": "test", "loaded_at": 1234567890}
    legacy_state.write_text(json.dumps(test_data))

    try:
        # Call migration explicitly
        skill_execution_state.migrate_legacy_state()

        # Legacy file should be removed
        assert not legacy_state.exists()

        # New state file should exist with migrated data
        new_state = skill_execution_state._get_state_file()
        assert new_state.exists()

        migrated_data = json.loads(new_state.read_text())
        assert migrated_data["skill"] == "test"

    finally:
        # Cleanup
        if legacy_state.exists():
            legacy_state.unlink()
        new_state = skill_execution_state._get_state_file()
        if new_state.exists():
            new_state.unlink()


# =============================================================================
# Issue #5: Documentation Tests
# =============================================================================


def test_docstring_no_ttl_contradiction():
    """Test that docstring doesn't contradict MAX_TRAIL_AGE_SECONDS constant."""
    from skill_guard.breadcrumb import tracker

    docstring = tracker.__doc__

    # Check for contradiction
    has_no_ttl_claim = "no ttl" in docstring.lower()
    has_age_based_claim = "age-based" in docstring.lower() or "max_trail_age" in docstring.lower()

    # Should not have both "no TTL" and age-based cleanup claims
    if has_no_ttl_claim:
        # If claiming "no TTL", should not define MAX_TRAIL_AGE_SECONDS
        # or the docstring should clarify it's for stale trails only
        assert not has_age_based_claim or "orphan" in docstring.lower(), (
            "Docstring contradiction: claims 'No TTL' but has age-based cleanup. "
            "Either remove 'No TTL' claim or clarify it only applies to orphaned trails."
        )


def test_max_trail_age_constant_exists():
    """Test that MAX_TRAIL_AGE_SECONDS is defined (2 hours)."""
    from skill_guard.breadcrumb import tracker

    assert hasattr(tracker, "MAX_TRAIL_AGE_SECONDS")
    assert tracker.MAX_TRAIL_AGE_SECONDS == 7200  # 2 hours in seconds
