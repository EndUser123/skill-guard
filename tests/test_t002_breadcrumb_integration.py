#!/usr/bin/env python3
"""
Test suite for T-002: Breadcrumb integration with skill hooks

Acceptance Criteria:
- Breadcrumb file created when skill invoked
- Steps marked complete when workflow transitions occur

Tests:
1. SessionStart hooks initialize breadcrumb trails
2. PostToolUse hooks mark steps as complete
3. TDD hooks mark RED→GREEN→REFACTOR transitions
4. Breadcrumb files created in correct locations
5. Terminal isolation prevents cross-contamination
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest


class TestBreadcrumbIntegration:
    """Test breadcrumb tracking integration with skill hooks."""

    def test_sessionstart_hooks_exist(self):
        """Test that SessionStart hooks exist for /code and /tdd skills."""
        code_hook = Path("P:/.claude/skills/code/hooks/SessionStart_breadcrumb_init.py")
        tdd_hook = Path("P:/.claude/skills/tdd/hooks/SessionStart_breadcrumb_init.py")

        assert code_hook.exists(), "/code SessionStart hook not found"
        assert tdd_hook.exists(), "/tdd SessionStart hook not found"

    def test_posttooluse_hooks_exist(self):
        """Test that PostToolUse hooks exist for breadcrumb tracking."""
        code_hook = Path("P:/.claude/skills/code/hooks/PostToolUse_breadcrumb_tracker.py")
        tdd_hook = Path("P:/.claude/skills/tdd/hooks/PostToolUse_tdd_state.py")

        assert code_hook.exists(), "/code PostToolUse hook not found"
        assert tdd_hook.exists(), "/tdd PostToolUse hook not found"

    def test_sessionstart_hook_executes_successfully(self):
        """Test that SessionStart hooks execute without errors."""
        code_hook = Path("P:/.claude/skills/code/hooks/SessionStart_breadcrumb_init.py")
        tdd_hook = Path("P:/.claude/skills/tdd/hooks/SessionStart_breadcrumb_init.py")

        # Test /code hook
        result = subprocess.run(
            [sys.executable, str(code_hook)],
            capture_output=True,
            text=True,
            input="{}",
            timeout=5
        )
        assert result.returncode == 0, f"/code SessionStart hook failed: {result.stderr}"
        assert json.loads(result.stdout).get("continue") == True

        # Test /tdd hook
        result = subprocess.run(
            [sys.executable, str(tdd_hook)],
            capture_output=True,
            text=True,
            input="{}",
            timeout=5
        )
        assert result.returncode == 0, f"/tdd SessionStart hook failed: {result.stderr}"
        assert json.loads(result.stdout).get("continue") == True

    def test_posttooluse_hook_executes_successfully(self):
        """Test that PostToolUse hooks execute without errors."""
        code_hook = Path("P:/.claude/skills/code/hooks/PostToolUse_breadcrumb_tracker.py")

        # Test with Read tool
        hook_input = {
            "tool_name": "Read",
            "tool_input": {"file_path": "test.py"}
        }

        result = subprocess.run(
            [sys.executable, str(code_hook)],
            capture_output=True,
            text=True,
            input=json.dumps(hook_input),
            timeout=5
        )
        assert result.returncode == 0, f"PostToolUse hook failed: {result.stderr}"
        assert json.loads(result.stdout).get("continue") == True

    def test_breadcrumb_imports_in_tdd_hook(self):
        """Test that TDD PostToolUse hook has breadcrumb imports."""
        tdd_hook_path = Path("P:/.claude/skills/tdd/hooks/PostToolUse_tdd_state.py")
        content = tdd_hook_path.read_text()

        # Check for skill_guard path
        assert "skill_guard_path = Path" in content, "Missing skill_guard path setup"
        assert "from skill_guard.breadcrumb.tracker import set_breadcrumb" in content, \
            "Missing set_breadcrumb import"

        # Check for fallback
        assert "BREADCRUMB_ENABLED = True" in content or "BREADCRUMB_ENABLED = False" in content, \
            "Missing BREADCRUMB_ENABLED flag"
        assert "set_breadcrumb = lambda" in content, "Missing fallback no-op for set_breadcrumb"

    def test_breadcrumb_calls_in_tdd_hook(self):
        """Test that TDD PostToolUse hook has breadcrumb calls at key transitions."""
        tdd_hook_path = Path("P:/.claude/skills/tdd/hooks/PostToolUse_tdd_state.py")
        content = tdd_hook_path.read_text()

        # Check for breadcrumb calls at key transitions
        expected_calls = [
            'set_breadcrumb("tdd", "write_failing_tests")',
            'set_breadcrumb("tdd", "confirm_tests_fail")',
            'set_breadcrumb("tdd", "implement_minimal_code")',
            'set_breadcrumb("tdd", "confirm_tests_pass")',
            'set_breadcrumb("tdd", "refactor_code")',
        ]

        for call in expected_calls:
            assert call in content, f"Missing breadcrumb call: {call}"

    def test_workflow_steps_loaded_for_critical_skills(self):
        """Test that workflow_steps can be loaded for critical skills."""
        from skill_guard.breadcrumb.tracker import _load_workflow_steps

        # Test critical skills
        for skill in ["code", "tdd", "trace", "arch"]:
            steps = _load_workflow_steps(skill)
            assert len(steps) > 0, f"{skill} should have workflow_steps"
            assert len(steps) >= 3, f"{skill} should have at least 3 workflow steps"

    def test_breadcrumb_files_created_in_terminal_scoped_dirs(self):
        """Test that breadcrumb files are created in terminal-scoped directories."""
        from skill_guard.breadcrumb.tracker import initialize_breadcrumb_trail
        from skill_guard.utils.terminal_detection import detect_terminal_id

        # Initialize breadcrumb trail
        initialize_breadcrumb_trail("test")

        # Check terminal ID
        terminal_id = detect_terminal_id()
        assert terminal_id, "Should detect terminal ID"

        # Check breadcrumb file location
        from skill_guard.breadcrumb.tracker import _get_breadcrumb_file
        trail_file = _get_breadcrumb_file("test")

        # Verify file path includes terminal_id
        assert str(terminal_id) in str(trail_file), \
            f"Breadcrumb file should be terminal-scoped: {trail_file}"

    def test_set_breadcrumb_creates_trail_if_not_exists(self):
        """Test that set_breadcrumb auto-initializes trail if it doesn't exist."""
        # Clear any existing trail
        from skill_guard.breadcrumb.tracker import (
            clear_breadcrumb_trail,
            get_breadcrumb_trail,
            set_breadcrumb,
        )
        clear_breadcrumb_trail("test_integration")

        # Set breadcrumb (should auto-initialize)
        set_breadcrumb("test_integration", "test_step")

        # Verify trail exists
        trail = get_breadcrumb_trail("test_integration")
        assert trail is not None, "Trail should be created by set_breadcrumb"

        # Verify step is marked complete
        completed = trail.get("completed_steps", [])
        assert "test_step" in completed, "Step should be marked complete"

    def test_set_breadcrumb_marks_steps_complete(self):
        """Test that set_breadcrumb marks steps as complete."""
        from skill_guard.breadcrumb.tracker import (
            get_breadcrumb_trail,
            initialize_breadcrumb_trail,
            set_breadcrumb,
        )

        # Initialize trail
        initialize_breadcrumb_trail("test_mark_complete")

        # Mark steps as complete
        set_breadcrumb("test_mark_complete", "step_1")
        set_breadcrumb("test_mark_complete", "step_2")

        # Verify steps marked complete
        trail = get_breadcrumb_trail("test_mark_complete")
        completed = trail.get("completed_steps", [])

        assert "step_1" in completed, "step_1 should be marked complete"
        assert "step_2" in completed, "step_2 should be marked complete"

    def test_verify_breadcrumb_trail_function(self):
        """Test that verify_breadcrumb_trail returns correct status."""
        from skill_guard.breadcrumb.tracker import (
            initialize_breadcrumb_trail,
            set_breadcrumb,
            verify_breadcrumb_trail,
        )

        # Initialize trail
        initialize_breadcrumb_trail("test_verify")

        # Verify incomplete
        is_complete, message = verify_breadcrumb_trail("test_verify")
        assert not is_complete, "Trail should be incomplete initially"
        assert "Missing" in message or "completed" in message.lower(), \
            f"Expected incomplete message, got: {message}"

        # Mark all steps complete
        trail_file = Path("P:/.claude/state") / "breadcrumbs_*" / "breadcrumb_test_verify.json"
        # Get the actual trail file
        from skill_guard.breadcrumb.tracker import _get_breadcrumb_file
        trail_file = _get_breadcrumb_file("test_verify")

        if trail_file.exists():
            import json
            trail = json.loads(trail_file.read_text())
            workflow_steps = trail.get("workflow_steps", [])

            # Mark all steps complete
            for step in workflow_steps:
                set_breadcrumb("test_verify", step)

            # Verify complete
            is_complete, message = verify_breadcrumb_trail("test_verify")
            assert is_complete, f"Trail should be complete after marking all steps: {message}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
