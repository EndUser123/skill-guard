"""Auto-scaffolded test for exceptions."""

import pytest
from skill_guard.exceptions import (
    SkillGuardError,
    WorkflowStepsError,
    BreadcrumbStateError,
    DatabaseError,
)


def test_exceptions_exist():
    """Smoke test: exceptions module can be imported."""
    assert SkillGuardError is not None
    assert WorkflowStepsError is not None
    assert BreadcrumbStateError is not None
    assert DatabaseError is not None


def test_exception_inheritance():
    """Test that all exceptions inherit from SkillGuardError."""
    assert issubclass(WorkflowStepsError, SkillGuardError)
    assert issubclass(BreadcrumbStateError, SkillGuardError)
    assert issubclass(DatabaseError, SkillGuardError)
