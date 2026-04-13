"""Tests for PreToolUse_skill_pattern_gate."""

import pytest
import sys
from pathlib import Path

# Add src to path for direct module import
SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_ROOT))

from skill_guard.PreToolUse.PreToolUse_skill_pattern_gate import handle_pre_tool_use


def test_handle_pre_tool_use_exists():
    """Smoke test: handle_pre_tool_use function is importable from the module."""
    assert callable(handle_pre_tool_use)
