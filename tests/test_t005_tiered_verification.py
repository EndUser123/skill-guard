#!/usr/bin/env python3
"""
Test suite for T-005: Tiered verification integration

Acceptance Criteria:
- verify_breadcrumb_trail() uses tiered enforcement
- MINIMAL level checks duration and tool count
- STANDARD level checks workflow phases
- STRICT level checks all steps
"""

import json
import os
import time

import pytest

from skill_guard.breadcrumb.tracker import (
    clear_breadcrumb_trail,
    set_breadcrumb,
    verify_breadcrumb_trail,
)


class TestT005TieredVerification:
    """Test tiered verification integration."""

    def _create_test_trail(
        self, skill: str, workflow_steps: list[str], tool_count: int = 0, age_seconds: float = 0.0
    ) -> None:
        """Helper to create a test breadcrumb trail.

        Args:
            skill: Skill name
            workflow_steps: List of workflow step names
            tool_count: Number of tools used (default 0)
            age_seconds: How old the trail is in seconds (default 0.0 = now)
        """
        from skill_guard.breadcrumb.tracker import _get_breadcrumb_file, detect_terminal_id

        skill_lower = skill.lower()
        # Use the actual breadcrumb file path from tracker module
        breadcrumb_file = _get_breadcrumb_file(skill_lower)

        trail = {
            "skill": skill_lower,
            "terminal_id": detect_terminal_id(),  # Use actual terminal ID for session isolation
            "initialized_at": time.time() - age_seconds,
            "workflow_steps": workflow_steps,
            "completed_steps": [],
            "current_step": None,
            "last_updated": time.time(),
            "tool_count": tool_count,
        }

        breadcrumb_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            trail_json = json.dumps(trail, indent=2)
            print(f"DEBUG: Writing trail JSON (first 300 chars): {trail_json[:300]}")
            breadcrumb_file.write_text(trail_json)
            # Verify write
            written = breadcrumb_file.read_text()
            print(f"DEBUG: Written content length: {len(written)} chars")
        except Exception as e:
            print(f"ERROR: Failed to write breadcrumb file: {e}")
            raise

    def test_minimal_level_pass(self):
        """Test MINIMAL level passes with duration and tool count."""
        skill = "test_minimal_pass"

        # Set environment variable to override to MINIMAL
        original = os.environ.get("BREADCRUMB_ENFORCEMENT_LEVEL")
        os.environ["BREADCRUMB_ENFORCEMENT_LEVEL"] = "MINIMAL"

        try:
            # Setup: Create trail with MINIMAL requirements met
            clear_breadcrumb_trail(skill)
            self._create_test_trail(
                skill,
                workflow_steps=["step1", "step2", "step3"],
                tool_count=3,  # >= 2 tools
                age_seconds=15.0,  # > 10s
            )

            # Verify: Should pass MINIMAL (duration > 10s, tools >= 2)
            is_complete, message = verify_breadcrumb_trail(skill)
            assert is_complete, f"MINIMAL should pass: {message}"
            assert "MINIMAL" in message or "duration" in message.lower()
        finally:
            if original is None:
                os.environ.pop("BREADCRUMB_ENFORCEMENT_LEVEL", None)
            else:
                os.environ["BREADCRUMB_ENFORCEMENT_LEVEL"] = original
            clear_breadcrumb_trail(skill)

    def test_minimal_level_fails_duration(self):
        """Test MINIMAL level fails on short duration."""
        skill = "test_minimal_duration"

        # Set environment variable to override to MINIMAL
        original = os.environ.get("BREADCRUMB_ENFORCEMENT_LEVEL")
        os.environ["BREADCRUMB_ENFORCEMENT_LEVEL"] = "MINIMAL"

        try:
            # Setup: Create trail with short duration
            clear_breadcrumb_trail(skill)
            self._create_test_trail(
                skill,
                workflow_steps=["step1", "step2"],
                tool_count=5,  # >= 2 tools (OK)
                age_seconds=5.0,  # <= 10s (FAIL)
            )

            # Verify: Should fail MINIMAL (duration <= 10s)
            # Debug: Check what get_breadcrumb_trail returns
            from skill_guard.breadcrumb.tracker import (
                _get_breadcrumb_file,
                detect_terminal_id,
                get_breadcrumb_trail,
            )

            # Check if file exists
            breadcrumb_file = _get_breadcrumb_file(skill)
            print(f"DEBUG: File exists: {breadcrumb_file.exists()}")
            if breadcrumb_file.exists():
                file_content = breadcrumb_file.read_text()
                print(f"DEBUG: File content (first 500 chars): {file_content[:500]}")
                import json
                try:
                    trail_data = json.loads(file_content)
                    print(f"DEBUG: Trail terminal_id: {trail_data.get('terminal_id')}")
                    print(f"DEBUG: Current terminal_id: {detect_terminal_id()}")
                except:
                    pass

            trail_debug = get_breadcrumb_trail(skill)
            print(f"DEBUG: trail after create: {trail_debug}")

            is_complete, message = verify_breadcrumb_trail(skill)
            print(f"DEBUG: is_complete={is_complete}, message={message}")
            if is_complete:
                # Debug: See why it passed when it should fail
                print(f"DEBUG: Unexpected pass. Message: {message}")
            assert not is_complete, f"Should fail MINIMAL on short duration. Got message: {message}"
            assert "too short" in message.lower()
        finally:
            if original is None:
                os.environ.pop("BREADCRUMB_ENFORCEMENT_LEVEL", None)
            else:
                os.environ["BREADCRUMB_ENFORCEMENT_LEVEL"] = original
            clear_breadcrumb_trail(skill)

    def test_standard_level_pass(self):
        """Test STANDARD level passes with workflow phases."""
        skill = "test_standard_pass"

        # Setup: Create trail and mark >= 2 steps complete including verification
        clear_breadcrumb_trail(skill)
        self._create_test_trail(
            skill,
            workflow_steps=["step1", "step2", "verify", "step3"],
            tool_count=3,  # >= 2 tools
            age_seconds=15.0,  # > 10s
        )
        set_breadcrumb(skill, "step1")
        set_breadcrumb(skill, "verify")

        try:
            # Verify: Should pass STANDARD (>=2 steps + verification)
            is_complete, message = verify_breadcrumb_trail(skill)
            assert is_complete, f"STANDARD should pass: {message}"
            assert "STANDARD" in message
        finally:
            clear_breadcrumb_trail(skill)

    def test_strict_level_pass(self):
        """Test STRICT level passes with all steps complete."""
        skill = "test_strict_pass"

        # Set environment variable to override to STRICT
        original = os.environ.get("BREADCRUMB_ENFORCEMENT_LEVEL")
        os.environ["BREADCRUMB_ENFORCEMENT_LEVEL"] = "STRICT"

        try:
            # Setup: Create trail and mark ALL steps complete
            clear_breadcrumb_trail(skill)
            self._create_test_trail(
                skill,
                workflow_steps=["step1", "step2", "step3"],
            )
            set_breadcrumb(skill, "step1")
            set_breadcrumb(skill, "step2")
            set_breadcrumb(skill, "step3")

            # Verify: Should pass STRICT (all steps complete)
            is_complete, message = verify_breadcrumb_trail(skill)
            assert is_complete, f"STRICT should pass: {message}"
            assert "STRICT" in message or "all" in message.lower()
        finally:
            if original is None:
                os.environ.pop("BREADCRUMB_ENFORCEMENT_LEVEL", None)
            else:
                os.environ["BREADCRUMB_ENFORCEMENT_LEVEL"] = original
            clear_breadcrumb_trail(skill)

    def test_strict_level_fails_incomplete(self):
        """Test STRICT level fails with incomplete steps."""
        skill = "test_strict_fail"

        # Set environment variable to override to STRICT
        original = os.environ.get("BREADCRUMB_ENFORCEMENT_LEVEL")
        os.environ["BREADCRUMB_ENFORCEMENT_LEVEL"] = "STRICT"

        try:
            # Setup: Create trail and mark only 2 of 3 steps complete
            clear_breadcrumb_trail(skill)
            self._create_test_trail(
                skill,
                workflow_steps=["step1", "step2", "step3"],
            )
            set_breadcrumb(skill, "step1")
            set_breadcrumb(skill, "step2")

            # Verify: Should fail STRICT (missing step3)
            is_complete, message = verify_breadcrumb_trail(skill)
            assert not is_complete, "Should fail STRICT with incomplete steps"
            assert "missing" in message.lower() or "step3" in message
        finally:
            if original is None:
                os.environ.pop("BREADCRUMB_ENFORCEMENT_LEVEL", None)
            else:
                os.environ["BREADCRUMB_ENFORCEMENT_LEVEL"] = original
            clear_breadcrumb_trail(skill)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
