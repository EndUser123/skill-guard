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
    get_breadcrumb_trail,
    initialize_breadcrumb_trail,
    set_breadcrumb,
    verify_breadcrumb_trail,
)


class TestT005TieredVerification:
    """Test tiered verification integration."""

    def test_minimal_level_pass(self):
        """Test MINIMAL level passes with duration and tool count."""
        skill = "test_minimal_pass"

        # Setup: Initialize trail with workflow steps
        clear_breadcrumb_trail(skill)
        initialize_breadcrumb_trail(
            skill,
            workflow_steps=["step1", "step2", "step3"],
        )

        # Mark only one step complete (MINIMAL doesn't check workflow)
        set_breadcrumb(skill, "step1")

        # Manually update trail to simulate MINIMAL requirements
        trail = get_breadcrumb_trail(skill)
        if trail:
            trail["tool_count"] = 3  # >= 2 tools
            trail["initialized_at"] = time.time() - 15.0  # > 10s ago
            import json
            from pathlib import Path

            breadcrumb_file = Path(
                f"P:/packages/skill-guard/.state/breadcrumb_{skill.lower()}.json"
            )
            breadcrumb_file.write_text(json.dumps(trail, indent=2))

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

        # Setup: Initialize trail
        clear_breadcrumb_trail(skill)
        initialize_breadcrumb_trail(
            skill,
            workflow_steps=["step1", "step2"],
        )

        # Manually update trail to simulate short duration
        trail = get_breadcrumb_trail(skill)
        if trail:
            trail["tool_count"] = 5  # >= 2 tools (OK)
            trail["initialized_at"] = time.time() - 5.0  # <= 10s (FAIL)
            import json
            from pathlib import Path

            breadcrumb_file = Path(
                f"P:/packages/skill-guard/.state/breadcrumb_{skill.lower()}.json"
            )
            breadcrumb_file.write_text(json.dumps(trail, indent=2))

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

        # Setup: Initialize trail
        clear_breadcrumb_trail(skill)
        initialize_breadcrumb_trail(
            skill,
            workflow_steps=["step1", "step2", "verify", "step3"],
        )

        # Mark >= 2 steps complete including verification
        set_breadcrumb(skill, "step1")
        set_breadcrumb(skill, "verify")

        # Manually update trail to meet MINIMAL requirements
        trail = get_breadcrumb_trail(skill)
        if trail:
            trail["tool_count"] = 3  # >= 2 tools
            trail["initialized_at"] = time.time() - 15.0  # > 10s
            import json
            from pathlib import Path

            breadcrumb_file = Path(
                f"P:/packages/skill-guard/.state/breadcrumb_{skill.lower()}.json"
            )
            breadcrumb_file.write_text(json.dumps(trail, indent=2))

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

        # Setup: Initialize trail
        clear_breadcrumb_trail(skill)
        initialize_breadcrumb_trail(
            skill,
            workflow_steps=["step1", "step2", "step3"],
        )

        # Mark ALL steps complete
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

        # Setup: Initialize trail
        clear_breadcrumb_trail(skill)
        initialize_breadcrumb_trail(
            skill,
            workflow_steps=["step1", "step2", "step3"],
        )

        # Mark only 2 of 3 steps complete
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
