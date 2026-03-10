#!/usr/bin/env python3
"""
Test suite for T-003: Breadcrumb verification in global hooks

Acceptance Criteria:
- Warning shown when steps missing
- Incomplete workflows blocked in block mode
- Hook executes successfully
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest


class TestT003BreadcrumbVerifier:
    """Test breadcrumb verification hook."""

    def test_hook_file_exists(self):
        """Test that PreToolUse_breadcrumb_verifier.py exists."""
        hook_file = Path("P:/.claude/hooks/PreToolUse_breadcrumb_verifier.py")
        assert hook_file.exists(), "PreToolUse_breadcrumb_verifier.py not found"

    def test_hook_executes_successfully(self):
        """Test that the hook executes without errors."""
        hook_file = Path("P:/.claude/hooks/PreToolUse_breadcrumb_verifier.py")

        # Test with no active trails
        hook_input = {"tool_name": "Read", "tool_input": {"file_path": "test.py"}}

        result = subprocess.run(
            [sys.executable, str(hook_file)],
            capture_output=True,
            text=True,
            input=json.dumps(hook_input),
            timeout=5,
            env={
                "BREADCRUMB_VERIFIER_ENABLED": "false",  # Disabled to avoid trail checks
            }
        )
        assert result.returncode == 0, f"Hook failed: {result.stderr}"
        assert json.loads(result.stdout).get("continue") == True

    def test_warn_mode_shows_warning_for_incomplete_trail(self):
        """Test that warn mode shows warning for incomplete breadcrumb trail."""
        from skill_guard.breadcrumb.tracker import (
            clear_breadcrumb_trail,
            initialize_breadcrumb_trail,
        )

        hook_file = Path("P:/.claude/hooks/PreToolUse_breadcrumb_verifier.py")

        # Setup: Create incomplete breadcrumb trail
        clear_breadcrumb_trail("test_skill")
        initialize_breadcrumb_trail("test_skill")
        # Don't mark any steps as complete - trail is incomplete

        try:
            # Test with Bash tool (triggers verification)
            hook_input = {"tool_name": "Bash", "tool_input": {"command": "echo test"}}

            result = subprocess.run(
                [sys.executable, str(hook_file)],
                capture_output=True,
                text=True,
                input=json.dumps(hook_input),
                timeout=5,
                env={
                    "BREADCRUMB_VERIFIER_ENABLED": "true",
                    "BREADCRUMB_VERIFIER_MODE": "warn",
                }
            )

            assert result.returncode == 0, f"Hook failed: {result.stderr}"
            output = json.loads(result.stdout)
            assert output.get("continue") == True, "Should allow in warn mode"
            assert "warning" in output, "Should show warning in warn mode"
            assert "Incomplete" in output["warning"] or "Missing" in output["warning"], \
                f"Warning should mention incomplete trail: {output.get('warning')}"
        finally:
            # Cleanup
            clear_breadcrumb_trail("test_skill")

    def test_block_mode_blocks_incomplete_trail(self):
        """Test that block mode blocks tool execution for incomplete trail."""
        from skill_guard.breadcrumb.tracker import (
            clear_breadcrumb_trail,
            initialize_breadcrumb_trail,
        )

        hook_file = Path("P:/.claude/hooks/PreToolUse_breadcrumb_verifier.py")

        # Setup: Create incomplete breadcrumb trail
        clear_breadcrumb_trail("test_block_skill")
        initialize_breadcrumb_trail("test_block_skill")
        # Don't mark any steps as complete - trail is incomplete

        try:
            # Test with Skill tool (triggers verification)
            hook_input = {
                "tool_name": "Skill",
                "tool_input": {"skill": "test", "prompt": "test"}
            }

            result = subprocess.run(
                [sys.executable, str(hook_file)],
                capture_output=True,
                text=True,
                input=json.dumps(hook_input),
                timeout=5,
                env={
                    "BREADCRUMB_VERIFIER_ENABLED": "true",
                    "BREADCRUMB_VERIFIER_MODE": "block",
                }
            )

            assert result.returncode == 2, f"Should block with exit code 2, got {result.returncode}"
            output = json.loads(result.stdout)
            assert output.get("continue") == False, "Should block in block mode"
            assert "reason" in output, "Should provide blocking reason"
            assert "Incomplete" in output["reason"] or "Missing" in output["reason"], \
                f"Reason should mention incomplete trail: {output.get('reason')}"
        finally:
            # Cleanup
            clear_breadcrumb_trail("test_block_skill")

    def test_complete_trail_allows_execution(self):
        """Test that complete breadcrumb trail allows execution."""
        from skill_guard.breadcrumb.tracker import (
            clear_breadcrumb_trail,
            get_breadcrumb_trail,
            initialize_breadcrumb_trail,
            set_breadcrumb,
        )

        hook_file = Path("P:/.claude/hooks/PreToolUse_breadcrumb_verifier.py")

        # Setup: Create complete breadcrumb trail
        clear_breadcrumb_trail("test_complete_skill")
        initialize_breadcrumb_trail("test_complete_skill")

        # Mark all steps as complete
        trail = get_breadcrumb_trail("test_complete_skill")
        if trail:
            workflow_steps = trail.get("workflow_steps", [])
            for step in workflow_steps:
                set_breadcrumb("test_complete_skill", step)

        try:
            # Test in block mode (should allow because trail is complete)
            hook_input = {"tool_name": "Bash", "tool_input": {"command": "echo test"}}

            result = subprocess.run(
                [sys.executable, str(hook_file)],
                capture_output=True,
                text=True,
                input=json.dumps(hook_input),
                timeout=5,
                env={
                    "BREADCRUMB_VERIFIER_ENABLED": "true",
                    "BREADCRUMB_VERIFIER_MODE": "block",
                }
            )

            assert result.returncode == 0, f"Hook failed: {result.stderr}"
            output = json.loads(result.stdout)
            assert output.get("continue") == True, "Should allow when trail complete"
        finally:
            # Cleanup
            clear_breadcrumb_trail("test_complete_skill")

    def test_non_completion_tools_skipped(self):
        """Test that non-completion tools are skipped (no verification)."""
        from skill_guard.breadcrumb.tracker import (
            clear_breadcrumb_trail,
            initialize_breadcrumb_trail,
        )

        hook_file = Path("P:/.claude/hooks/PreToolUse_breadcrumb_verifier.py")

        # Setup: Create incomplete breadcrumb trail
        clear_breadcrumb_trail("test_skip_skill")
        initialize_breadcrumb_trail("test_skip_skill")

        try:
            # Test with Read tool (should skip verification)
            hook_input = {"tool_name": "Read", "tool_input": {"file_path": "test.py"}}

            result = subprocess.run(
                [sys.executable, str(hook_file)],
                capture_output=True,
                text=True,
                input=json.dumps(hook_input),
                timeout=5,
                env={
                    "BREADCRUMB_VERIFIER_ENABLED": "true",
                    "BREADCRUMB_VERIFIER_MODE": "block",
                }
            )

            assert result.returncode == 0, f"Hook failed: {result.stderr}"
            output = json.loads(result.stdout)
            assert output.get("continue") == True, "Should skip verification for Read tool"
        finally:
            # Cleanup
            clear_breadcrumb_trail("test_skip_skill")

    def test_disabled_hook_allows_all(self):
        """Test that disabled hook allows all tool execution."""
        hook_file = Path("P:/.claude/hooks/PreToolUse_breadcrumb_verifier.py")

        # Test with hook disabled
        hook_input = {"tool_name": "Bash", "tool_input": {"command": "test"}}

        result = subprocess.run(
            [sys.executable, str(hook_file)],
            capture_output=True,
            text=True,
            input=json.dumps(hook_input),
            timeout=5,
            env={
                "BREADCRUMB_VERIFIER_ENABLED": "false",
            }
        )

        assert result.returncode == 0, f"Hook failed: {result.stderr}"
        assert json.loads(result.stdout).get("continue") == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
