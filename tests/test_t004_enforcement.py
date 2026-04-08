#!/usr/bin/env python3
"""
Test suite for T-004: Enforcement level system

Acceptance Criteria:
- All three enforcement levels work
- SKILL.md overrides respected
- Default is STANDARD
"""

import os

import pytest

from skill_guard.breadcrumb.enforcement import (
    EnforcementLevel,
    _verify_minimal,
    _verify_standard,
    _verify_strict,
    get_enforcement_level,
    verify_with_enforcement,
)


class TestT004EnforcementLevel:
    """Test enforcement level system."""

    def test_enforcement_level_enum(self):
        """Test that EnforcementLevel enum has three values."""
        assert EnforcementLevel.MINIMAL.value == "MINIMAL"
        assert EnforcementLevel.STANDARD.value == "STANDARD"
        assert EnforcementLevel.STRICT.value == "STRICT"

    def test_get_enforcement_level_default(self):
        """Test that default enforcement level is STANDARD."""
        # Test with skill that has no enforcement_level in frontmatter
        level = get_enforcement_level("nonexistent_skill")
        assert level == EnforcementLevel.STANDARD

    def test_get_enforcement_level_env_override(self):
        """Test that environment variable overrides SKILL.md."""
        # Set environment variable
        original_value = os.environ.get("BREADCRUMB_ENFORCEMENT_LEVEL")
        try:
            os.environ["BREADCRUMB_ENFORCEMENT_LEVEL"] = "MINIMAL"
            level = get_enforcement_level("test_skill")
            assert level == EnforcementLevel.MINIMAL
        finally:
            # Restore original value
            if original_value is None:
                os.environ.pop("BREADCRUMB_ENFORCEMENT_LEVEL", None)
            else:
                os.environ["BREADCRUMB_ENFORCEMENT_LEVEL"] = original_value

    def test_verify_minimal_level(self):
        """Test MINIMAL level verification."""
        # Should pass: duration > 10s, tools >= 2
        is_complete, message = _verify_minimal(
            workflow_steps=["step1", "step2", "step3"],
            completed_steps=["step1"],  # Only 1/3 steps
            duration_seconds=15.0,  # > 10s
            tool_count=3,  # >= 2
        )
        assert is_complete, f"Should pass MINIMAL: {message}"
        assert "MINIMAL" in message

    def test_verify_minimal_level_fails_duration(self):
        """Test MINIMAL level fails on short duration."""
        is_complete, message = _verify_minimal(
            workflow_steps=["step1", "step2"],
            completed_steps=["step1"],
            duration_seconds=5.0,  # <= 10s
            tool_count=5,
        )
        assert not is_complete, "Should fail MINIMAL on short duration"
        assert "too short" in message.lower()

    def test_verify_minimal_level_fails_tool_count(self):
        """Test MINIMAL level fails on insufficient tools."""
        is_complete, message = _verify_minimal(
            workflow_steps=["step1", "step2"],
            completed_steps=["step1"],
            duration_seconds=15.0,  # > 10s
            tool_count=1,  # < 2
        )
        assert not is_complete, "Should fail MINIMAL on tool count"
        assert "too few tools" in message.lower()

    def test_verify_standard_level(self):
        """Test STANDARD level verification."""
        # Should pass: MINIMAL checks + >=2 steps + verification
        is_complete, message = _verify_standard(
            workflow_steps=["step1", "step2", "step3", "verify"],
            completed_steps=["step1", "step2", "verify"],  # >= 2 steps + verification
            duration_seconds=15.0,  # > 10s
            tool_count=3,  # >= 2
        )
        assert is_complete, f"Should pass STANDARD: {message}"
        assert "STANDARD" in message

    def test_verify_standard_level_fails_no_verification(self):
        """Test STANDARD level fails without verification step."""
        is_complete, message = _verify_standard(
            workflow_steps=["step1", "step2", "step3"],
            completed_steps=["step1", "step2"],  # >= 2 steps
            duration_seconds=15.0,  # > 10s
            tool_count=3,  # >= 2
        )
        assert not is_complete, "Should fail STANDARD without verification"
        assert "verification" in message.lower()

    def test_verify_strict_level(self):
        """Test STRICT level verification."""
        # Should pass: ALL steps completed
        is_complete, message = _verify_strict(
            workflow_steps=["step1", "step2", "step3"],
            completed_steps=["step1", "step2", "step3"],  # All steps
            duration_seconds=5.0,  # Even short duration is ok
            tool_count=1,  # Even low tool count is ok
        )
        assert is_complete, f"Should pass STRICT: {message}"
        assert "STRICT" in message

    def test_verify_strict_level_fails_incomplete(self):
        """Test STRICT level fails with incomplete steps."""
        is_complete, message = _verify_strict(
            workflow_steps=["step1", "step2", "step3"],
            completed_steps=["step1", "step2"],  # Missing step3
            duration_seconds=20.0,
            tool_count=5,
        )
        assert not is_complete, "Should fail STRICT with incomplete steps"
        assert "missing" in message.lower()

    def test_verify_with_enforcement_no_trail(self):
        """Test verify_with_enforcement with no trail."""
        is_complete, message = verify_with_enforcement(
            "test_skill",
            trail=None,  # No trail
            duration_seconds=0.0,
            tool_count=0,
        )
        assert is_complete, "No trail should pass"
        assert "no workflow steps" in message.lower()

    def test_verify_with_enforcement_no_workflow_steps(self):
        """Test verify_with_enforcement with empty workflow_steps gets default enforcement."""
        # After change: empty workflow_steps now gets default ["invoke_skill", "apply_guidance"]
        # and verification proceeds (all skills are enforced)
        is_complete, message = verify_with_enforcement(
            "test_skill",
            trail={"workflow_steps": [], "completed_steps": []},
            duration_seconds=0.0,
            tool_count=0,
        )
        # Should fail MINIMAL level (duration <= 10s, tool_count < 2)
        assert not is_complete, "Default workflow_steps should be enforced and fail MINIMAL checks"
        assert "MINIMAL" in message or "invoke_skill" in message or "apply_guidance" in message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
