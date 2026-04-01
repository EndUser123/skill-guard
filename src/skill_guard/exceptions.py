"""
Skill Guard Exceptions
=====================

Custom exceptions for skill_guard package.
"""

from __future__ import annotations


class SkillGuardError(Exception):
    """Base exception for skill_guard errors."""

    pass


class WorkflowStepsError(SkillGuardError):
    """Raised when workflow_steps cannot be loaded or parsed."""

    pass


class BreadcrumbStateError(SkillGuardError):
    """Raised when breadcrumb state operations fail."""

    pass


class DatabaseError(SkillGuardError):
    """Raised when database operations fail."""

    pass


__all__ = [
    "SkillGuardError",
    "WorkflowStepsError",
    "BreadcrumbStateError",
    "DatabaseError",
]
