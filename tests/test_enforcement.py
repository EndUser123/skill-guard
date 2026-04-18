"""Tests for breadcrumb enforcement levels."""

import os
import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from skill_guard.breadcrumb.enforcement import (
    EnforcementLevel,
    get_enforcement_level,
    verify_with_enforcement,
)


@pytest.fixture(autouse=True)
def set_minimal_enforcement(monkeypatch):
    """Set MINIMAL enforcement for tests that test MINIMAL behavior."""
    # Tests that need MINIMAL explicitly set it
    # Tests that need STANDARD rely on the default (env var not set)
    pass  # No-op by default; specific tests override


def test_enforcement_level_enum():
    """Smoke test: EnforcementLevel enum has expected values."""
    assert EnforcementLevel.MINIMAL.value == "MINIMAL"
    assert EnforcementLevel.STANDARD.value == "STANDARD"
    assert EnforcementLevel.STRICT.value == "STRICT"


def test_enforcement_level_str():
    """EnforcementLevel str representation."""
    assert str(EnforcementLevel.STANDARD) == "STANDARD"


def test_verify_with_enforcement_no_trail():
    """verify_with_enforcement returns True when no trail exists."""
    is_complete, message = verify_with_enforcement("nonexistent_skill", None, 0.0, 0)
    assert is_complete is True


def test_verify_with_enforcement_minimal_duration_short(monkeypatch):
    """MINIMAL fails when duration is too short."""
    monkeypatch.setenv("BREADCRUMB_ENFORCEMENT_LEVEL", "MINIMAL")
    trail = {"workflow_steps": ["step1", "step2"], "completed_steps": ["step1", "step2"]}
    is_complete, message = verify_with_enforcement("test_skill", trail, 5.0, 2)
    assert is_complete is False
    assert "too short" in message.lower()


def test_verify_with_enforcement_minimal_tool_count_low(monkeypatch):
    """MINIMAL fails when tool count is too low."""
    monkeypatch.setenv("BREADCRUMB_ENFORCEMENT_LEVEL", "MINIMAL")
    trail = {"workflow_steps": ["step1", "step2"], "completed_steps": ["step1", "step2"]}
    is_complete, message = verify_with_enforcement("test_skill", trail, 15.0, 1)
    assert is_complete is False
    assert "too few tools" in message.lower()


def test_verify_with_enforcement_strict_missing_steps(monkeypatch):
    """STRICT fails when workflow steps are incomplete."""
    monkeypatch.setenv("BREADCRUMB_ENFORCEMENT_LEVEL", "STRICT")
    trail = {
        "workflow_steps": ["step1", "step2", "step3"],
        "completed_steps": ["step1"],
        "steps": {
            "step1": {"evidence": {"verified": True}},
        },
    }
    is_complete, message = verify_with_enforcement("test_skill", trail, 15.0, 5)
    assert is_complete is False
    assert "Missing workflow steps" in message


def test_verify_with_enforcement_strict_missing_evidence(monkeypatch):
    """STRICT fails when evidence is missing."""
    monkeypatch.setenv("BREADCRUMB_ENFORCEMENT_LEVEL", "STRICT")
    trail = {
        "workflow_steps": ["step1"],
        "completed_steps": ["step1"],
        "steps": {
            "step1": {"status": "done"},  # no evidence
        },
    }
    is_complete, message = verify_with_enforcement("test_skill", trail, 15.0, 5)
    assert is_complete is False
    assert "Evidence required" in message


def test_verify_with_enforcement_strict_complete(monkeypatch):
    """STRICT passes when all steps complete with evidence."""
    monkeypatch.setenv("BREADCRUMB_ENFORCEMENT_LEVEL", "STRICT")
    trail = {
        "workflow_steps": ["step1", "step2"],
        "completed_steps": ["step1", "step2"],
        "steps": {
            "step1": {"evidence": {"verified": True}},
            "step2": {"evidence": {"verified": True}},
        },
    }
    is_complete, message = verify_with_enforcement("test_skill", trail, 15.0, 5)
    assert is_complete is True


# Run: pytest tests/test_enforcement.py -v
