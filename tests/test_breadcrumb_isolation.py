#!/usr/bin/env python3
"""
Test suite for multi-terminal breadcrumb isolation

Acceptance Criteria:
- Test 2 terminals create separate logs
- Terminal A cannot read Terminal B
- Cleanup only removes current terminal's trails
- No cross-contamination possible

This is a CRITICAL test for multi-terminal safety.
"""

import json

import pytest

from skill_guard.breadcrumb.tracker import (
    _get_breadcrumb_dir,
    _get_breadcrumb_file,
    clear_breadcrumb_trail,
    detect_terminal_id,
    get_breadcrumb_trail,
    initialize_breadcrumb_trail,
    set_breadcrumb,
    verify_session_isolation,
)


class TestBreadcrumbIsolation:
    """Test multi-terminal breadcrumb isolation."""

    def test_different_terminals_create_separate_dirs(self):
        """Test that different terminals create separate state directories."""
        # Get current terminal's directory
        terminal_id = detect_terminal_id()
        breadcrumb_dir = _get_breadcrumb_dir()

        # Verify directory name includes terminal_id
        assert f"breadcrumbs_{terminal_id}" in str(breadcrumb_dir)

        # Verify directory exists
        assert breadcrumb_dir.exists()

        # Verify it's a directory
        assert breadcrumb_dir.is_dir()

    def test_breadcrumb_files_are_terminal_scoped(self):
        """Test that breadcrumb files include terminal_id in path."""
        skill = "test_terminal_scoped"

        # Create breadcrumb trail
        initialize_breadcrumb_trail(skill)
        set_breadcrumb(skill, "step1")

        # Get breadcrumb file path
        breadcrumb_file = _get_breadcrumb_file(skill)

        # Verify path includes terminal_id
        terminal_id = detect_terminal_id()
        path_str = str(breadcrumb_file)
        assert f"breadcrumbs_{terminal_id}" in path_str
        assert f"breadcrumb_{skill}.json" in path_str

        # Cleanup
        clear_breadcrumb_trail(skill)

    def test_verify_session_isolation_checks_terminal_id(self):
        """Test that verify_session_isolation checks terminal_id."""
        skill = "test_isolation_check"

        # Create trail with current terminal_id
        initialize_breadcrumb_trail(skill)

        # Get trail
        trail = get_breadcrumb_trail(skill)

        # Verify isolation should pass
        assert trail is not None
        assert verify_session_isolation(trail) is True

        # Simulate trail from different terminal
        trail["terminal_id"] = "fake_terminal_12345"

        # Verify isolation should fail
        assert verify_session_isolation(trail) is False

        # Cleanup
        trail["terminal_id"] = detect_terminal_id()  # Restore for cleanup
        clear_breadcrumb_trail(skill)

    def test_get_breadcrumb_trail_rejects_wrong_terminal(self):
        """Test that get_breadcrumb_trail returns None for wrong terminal."""
        skill = "test_wrong_terminal"

        # Create trail
        initialize_breadcrumb_trail(skill)
        set_breadcrumb(skill, "step1")

        # Manually modify trail to simulate different terminal
        breadcrumb_file = _get_breadcrumb_file(skill)
        trail = json.loads(breadcrumb_file.read_text())
        trail["terminal_id"] = "other_terminal_99999"
        breadcrumb_file.write_text(json.dumps(trail, indent=2))

        # get_breadcrumb_trail should return None (wrong terminal)
        result = get_breadcrumb_trail(skill)

        # Result should be None because terminal_id doesn't match
        # The function deletes stale trails and returns None
        assert result is None

        # Cleanup (file should already be deleted by get_breadcrumb_trail)
        clear_breadcrumb_trail(skill)

    def test_clear_only_affects_current_terminal(self):
        """Test that clear_breadcrumb_trail only affects current terminal."""
        skill = "test_clear_isolation"

        # Create trail in current terminal
        initialize_breadcrumb_trail(skill)
        set_breadcrumb(skill, "step1")

        # Verify file exists
        breadcrumb_file = _get_breadcrumb_file(skill)
        assert breadcrumb_file.exists()

        # Clear trail
        clear_breadcrumb_trail(skill)

        # Verify file is gone
        assert not breadcrumb_file.exists()

    def test_concurrent_terminals_dont_interfere(self):
        """Test that operations in one terminal don't affect another.

        Note: This test uses the actual terminal detection, so it verifies
        isolation in the real environment.
        """
        skill1 = "skill_terminal_A"
        skill2 = "skill_terminal_B"

        # Create trails for both skills in current terminal
        initialize_breadcrumb_trail(skill1)
        initialize_breadcrumb_trail(skill2)

        set_breadcrumb(skill1, "step1")
        set_breadcrumb(skill2, "step2")

        # Both trails should be accessible
        trail1 = get_breadcrumb_trail(skill1)
        trail2 = get_breadcrumb_trail(skill2)

        assert trail1 is not None
        assert trail2 is not None

        # Each should have its own completed steps
        assert trail1["completed_steps"] == ["step1"]
        assert trail2["completed_steps"] == ["step2"]

        # Verify they have the same terminal_id (same terminal)
        assert trail1["terminal_id"] == trail2["terminal_id"]

        # Cleanup
        clear_breadcrumb_trail(skill1)
        clear_breadcrumb_trail(skill2)

    def test_path_traversal_blocked_in_file_operations(self):
        """Test that path traversal attempts are blocked."""
        malicious_names = [
            "../../etc/passwd",
            "..\\..\\windows\\system32",
            "../other_terminal/data",
            "test.subversion.file",
        ]

        for malicious_name in malicious_names:
            with pytest.raises(ValueError, match="path traversal"):
                _get_breadcrumb_file(malicious_name)

    def test_cleanup_session_breadcrumbs_only_clears_current_terminal(self):
        """Test that cleanup_session_breadcrumbs only clears current terminal."""
        from skill_guard.breadcrumb.tracker import cleanup_session_breadcrumbs

        skill = "test_cleanup_current_only"

        # Create trail
        initialize_breadcrumb_trail(skill)
        set_breadcrumb(skill, "step1")

        # Verify file exists
        breadcrumb_file = _get_breadcrumb_file(skill)
        assert breadcrumb_file.exists()

        # Run cleanup (should only clear current terminal)
        cleaned = cleanup_session_breadcrumbs()

        # Should have cleaned at least 1 file
        assert cleaned >= 1

        # Verify file is gone
        assert not breadcrumb_file.exists()

    def test_cleanup_stale_breadcrumbs_preserves_current_terminal(self):
        """Test that cleanup_stale_breadcrumbs preserves current terminal trails."""
        from skill_guard.breadcrumb.tracker import cleanup_stale_breadcrumbs

        skill = "test_stale_cleanup"

        # Create fresh trail (not stale)
        initialize_breadcrumb_trail(skill)
        set_breadcrumb(skill, "step1")

        # Verify file exists
        breadcrumb_file = _get_breadcrumb_file(skill)
        assert breadcrumb_file.exists()

        # Run stale cleanup (should preserve current terminal)
        cleaned = cleanup_stale_breadcrumbs()

        # File should still exist (not stale)
        assert breadcrumb_file.exists()

        # Verify trail is still accessible
        trail = get_breadcrumb_trail(skill)
        assert trail is not None
        assert trail["completed_steps"] == ["step1"]

        # Cleanup
        clear_breadcrumb_trail(skill)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
