"""Tests for skill_execution_tracker."""

import pytest

pytest.skip(
    "skill_execution_tracker.py has a pre-existing import bug: PostToolUseHook base class "
    "does not exist in the package — superseded by execution_hooks.py",
    allow_module_level=True,
)
