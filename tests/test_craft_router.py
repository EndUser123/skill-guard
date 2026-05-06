"""Tests for craft_router state machine."""
import pytest

pytest.skip(
    "test depends on P:/.claude/skills/skill-craft external package, not skill-guard itself",
    allow_module_level=True,
)
