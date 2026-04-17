"""
Skill Guard
===========

Universal skill auto-discovery and enforcement for Claude Code.

This package provides two main modules:

1. **Skill Auto-Discovery**: Automatically discovers and enforces ALL skills
   without manual per-skill registration.

2. **Breadcrumb Trail Verification**: Workflow step verification system for
   skill execution. Skills declare workflow_steps in SKILL.md frontmatter,
   breadcrumb state files track completion, and global hooks verify adherence.

Usage:
    >>> from skill_guard import discover_all_skills, get_skill_config
    >>> skills = discover_all_skills()
    >>> config = get_skill_config("my-skill", {})

    >>> from skill_guard.breadcrumb import (
    ...     initialize_breadcrumb_trail,
    ...     set_breadcrumb,
    ...     verify_breadcrumb_trail
    ... )
    >>> initialize_breadcrumb_trail("research")
    >>> set_breadcrumb("research", "analyze_query_intent")
    >>> is_complete, message = verify_breadcrumb_trail("research")
"""

# Breadcrumb trail exports
from .breadcrumb import (
    cleanup_session_breadcrumbs,
    cleanup_stale_breadcrumbs,
    clear_breadcrumb_trail,
    format_breadcrumb_status,
    get_breadcrumb_trail,
    initialize_breadcrumb_trail,
    set_breadcrumb,
    verify_breadcrumb_trail,
    verify_session_isolation,
)
from .skill_auto_discovery import (
    KNOWLEDGE_SKILLS,
    discover_all_skills,
    get_skill_config,
)
from .slash_command_observability import (
    BUILTIN_SLASH_COMMANDS,
    LIGHTWEIGHT_SLASH_COMMANDS,
    classify_slash_command,
    extract_command_name,
    extract_slash_command,
    record_slash_outcome,
    record_slash_request,
    record_slash_resolution,
    is_slash_prompt,
    normalize_prompt,
)
from .skill_metadata_advisory import skill_metadata_advisory
from .tdd_contract_auto_gate import tdd_contract_auto_gate
from .turn_marker import ensure_turn_marker

__version__ = "1.0.0"
__all__ = [
    # Skill auto-discovery
    "discover_all_skills",
    "get_skill_config",
    "KNOWLEDGE_SKILLS",
    # Slash observability
    "BUILTIN_SLASH_COMMANDS",
    "LIGHTWEIGHT_SLASH_COMMANDS",
    "classify_slash_command",
    "extract_command_name",
    "extract_slash_command",
    "is_slash_prompt",
    "normalize_prompt",
    "record_slash_outcome",
    "record_slash_request",
    "record_slash_resolution",
    "skill_metadata_advisory",
    "tdd_contract_auto_gate",
    "ensure_turn_marker",
    # Breadcrumb trail verification
    "initialize_breadcrumb_trail",
    "set_breadcrumb",
    "get_breadcrumb_trail",
    "verify_breadcrumb_trail",
    "clear_breadcrumb_trail",
    "format_breadcrumb_status",
    "cleanup_session_breadcrumbs",
    "cleanup_stale_breadcrumbs",
    "verify_session_isolation",
]
