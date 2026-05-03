"""Tests for skill_execution_tracker."""

import pytest
from skill_guard.posttooluse.skill_execution_tracker import SkillExecutionTracker


def test_skill_execution_tracker_class_exists():
    """Smoke test: SkillExecutionTracker class is importable."""
    assert SkillExecutionTracker is not None
    assert callable(SkillExecutionTracker)
