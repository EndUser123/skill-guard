"""Auto-scaffolded test for skill_auto_discovery."""

import pytest
from skill_guard.skill_auto_discovery import discover_all_skills, discover_hooks


def test_skill_auto_discovery_module_importable():
    """Smoke test: skill_auto_discovery module can be imported."""
    # The module should be importable via the package
    assert discover_all_skills is not None
    assert discover_hooks is not None


# TODO: Add more tests based on actual functionality
# Run: pytest tests/test_skill_auto_discovery.py -v
