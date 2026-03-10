"""
Breadcrumb Trail Verification System
=================================

Workflow step verification system for skill execution.

This module provides the breadcrumb trail pattern for enforcing skill
workflow adherence:
1. Skills declare workflow_steps in SKILL.md frontmatter
2. Skill hooks call breadcrumb functions as steps complete
3. Global hooks verify breadcrumb trail completion
4. Block or advise when trail is incomplete

State files are terminal-scoped for multi-terminal safety.
Automatic cleanup on SessionEnd and PreCompact prevents filesystem litter.

Usage:
    >>> from skill_guard.breadcrumb import (
    ...     initialize_breadcrumb_trail,
    ...     set_breadcrumb,
    ...     verify_breadcrumb_trail
    ... )
    ...
    >>> # In skill hooks:
    >>> initialize_breadcrumb_trail("research")
    >>> set_breadcrumb("research", "analyze_query_intent")
    >>> is_complete, message = verify_breadcrumb_trail("research")
"""

from .tracker import (
    cleanup_session_breadcrumbs,
    cleanup_stale_breadcrumbs,
    clear_breadcrumb_trail,
    format_breadcrumb_status,
    get_active_breadcrumb_trails,
    get_breadcrumb_trail,
    initialize_breadcrumb_trail,
    set_breadcrumb,
    verify_breadcrumb_trail,
    verify_session_isolation,
)

__all__ = [
    "initialize_breadcrumb_trail",
    "set_breadcrumb",
    "get_breadcrumb_trail",
    "get_active_breadcrumb_trails",
    "verify_breadcrumb_trail",
    "clear_breadcrumb_trail",
    "format_breadcrumb_status",
    "cleanup_session_breadcrumbs",
    "cleanup_stale_breadcrumbs",
    "verify_session_isolation",
]
