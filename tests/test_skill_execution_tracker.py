"""Tests for skill_execution_tracker."""

import pytest
import sys
from pathlib import Path

# Add src to path for direct module import
SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_ROOT))

from skill_guard.posttooluse.skill_execution_tracker import SkillExecutionTracker


def test_skill_execution_tracker_class_exists():
    """Smoke test: SkillExecutionTracker class is importable."""
    assert SkillExecutionTracker is not None
    assert callable(SkillExecutionTracker)
