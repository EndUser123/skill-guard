#!/usr/bin/env python3
"""
Test suite for T-005: Tiered verification integration

Acceptance Criteria:
- verify_breadcrumb_trail() uses tiered enforcement
- MINIMAL level checks duration and tool count
- STANDARD level checks workflow phases
- STRICT level checks all steps
"""


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
        import json
        from pathlib import Path

        skill_lower = skill.lower()
        breadcrumb_file = Path(
            f"P:/packages/skill-guard/.state/breadcrumb_{skill_lower}.json"
        )

        trail = {
            "skill": skill_lower,
            "terminal_id": "test-terminal",
            "initialized_at": time.time() - age_seconds,
            "workflow_steps": workflow_steps,
            "completed_steps": [],
            "current_step": None,
            "last_updated": time.time(),
            "tool_count": tool_count,
        }

        breadcrumb_file.parent.mkdir(parents=True, exist_ok=True)
        breadcrumb_file.write_text(json.dumps(trail, indent=2))

    def test_minimal_level_pass(self):
        """Test MINIMAL level passes with duration and tool count."""
        skill = "test_minimal_pass"

        # Setup: Create trail with MINIMAL requirements met
        clear_breadcrumb_trail(skill)
        self._create_test_trail(
            skill,
            workflow_steps=["step1", "step2", "step3"],
            tool_count=3,  # >= 2 tools
            age_seconds=15.0,  # > 10s
        )

        try:
            # Verify: Should pass MINIMAL (duration > 10s, tools >= 2)
            is_complete, message = verify_breadcrumb_trail(skill)
            assert is_complete, f"MINIMAL should pass: {message}"
            assert "MINIMAL" in message or "duration" in message.lower()
        finally:
            clear_breadcrumb_trail(skill)

    def test_minimal_level_fails_duration(self):
        """Test MINIMAL level fails on short duration."""
        skill = "test_minimal_duration"

        # Setup: Create trail with short duration
        clear_breadcrumb_trail(skill)
        self._create_test_trail(
            skill,
            workflow_steps=["step1", "step2"],
            tool_count=5,  # >= 2 tools (OK)
            age_seconds=5.0,  # <= 10s (FAIL)
        )

        try:
            # Verify: Should fail MINIMAL (duration <= 10s)
            is_complete, message = verify_breadcrumb_trail(skill)
            assert not is_complete, "Should fail MINIMAL on short duration"
            assert "too short" in message.lower()
        finally:
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

        # Setup: Create trail and mark ALL steps complete
        clear_breadcrumb_trail(skill)
        self._create_test_trail(
            skill,
            workflow_steps=["step1", "step2", "step3"],
        )
        set_breadcrumb(skill, "step1")
        set_breadcrumb(skill, "step2")
        set_breadcrumb(skill, "step3")

        try:
            # Verify: Should pass STRICT (all steps complete)
            is_complete, message = verify_breadcrumb_trail(skill)
            assert is_complete, f"STRICT should pass: {message}"
            assert "STRICT" in message or "all" in message.lower()
        finally:
            clear_breadcrumb_trail(skill)

    def test_strict_level_fails_incomplete(self):
        """Test STRICT level fails with incomplete steps."""
        skill = "test_strict_fail"

        # Setup: Create trail and mark only 2 of 3 steps complete
        clear_breadcrumb_trail(skill)
        self._create_test_trail(
            skill,
            workflow_steps=["step1", "step2", "step3"],
        )
        set_breadcrumb(skill, "step1")
        set_breadcrumb(skill, "step2")

        try:
            # Verify: Should fail STRICT (missing step3)
            is_complete, message = verify_breadcrumb_trail(skill)
            assert not is_complete, "Should fail STRICT with incomplete steps"
            assert "missing" in message.lower() or "step3" in message
        finally:
            clear_breadcrumb_trail(skill)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
