#!/usr/bin/env python3
"""
Tool Pattern Inference System
=============================

Infers workflow steps from tool usage patterns.

Maps Claude Code tools to workflow steps for automatic breadcrumb tracking:
- WebSearch → research
- Read → requirements
- Edit/Write → tdd
- Bash → verification
- etc.

This enables automatic breadcrumb tracking without manual set_breadcrumb() calls.
"""

from __future__ import annotations

from typing import Any

# =============================================================================
# TOOL-TO-STEP MAPPINGS
# =============================================================================

# Default tool-to-step mappings
# Maps tool names to workflow step names
DEFAULT_TOOL_MAPPINGS: dict[str, str] = {
    # Research tools
    "WebSearch": "research",
    "mcp__tavily-mcp__tavily_search": "research",
    "mcp__tavily-mcp__tavily_research": "research",
    "mcp__perplexity__perplexity_search": "research",
    "mcp__perplexity__perplexity_ask": "research",
    "mcp__perplexity__perplexity_research": "research",
    "mcp__exa__get_code_context_exa": "research",

    # Requirements tools
    "Read": "requirements",
    "Glob": "requirements",
    "Grep": "requirements",
    "LSP": "requirements",

    # TDD/Implementation tools
    "Edit": "tdd",
    "Write": "tdd",
    "NotebookEdit": "tdd",

    # Verification tools
    "Bash": "verification",
    "Skill": "verification",

    # Planning tools
    "AskUserQuestion": "planning",
    "EnterPlanMode": "planning",
    "ExitPlanMode": "planning",

    # Agent tools
    "Agent": "agent_coordination",
}


# =============================================================================
# INFERENCE ENGINE
# =============================================================================

def _infer_step_from_tool(tool_name: str, tool_input: dict[str, Any]) -> str | None:
    """Infer workflow step from tool usage.

    Args:
        tool_name: Name of the tool being used
        tool_input: Input parameters passed to the tool

    Returns:
        Inferred step name (e.g., "research", "tdd") or None if not mappable
    """
    # Normalize tool name (remove special prefix if present)
    normalized_name = tool_name

    # Handle MCP tool names (format: mcp__server_name__tool_name)
    if normalized_name.startswith("mcp__"):
        # Use full tool name for mapping
        pass

    # Check exact match first
    if normalized_name in DEFAULT_TOOL_MAPPINGS:
        return DEFAULT_TOOL_MAPPINGS[normalized_name]

    # Check prefix match for tool categories
    for mapped_tool, step in DEFAULT_TOOL_MAPPINGS.items():
        if normalized_name.startswith(mapped_tool):
            return step

    # Special inference rules based on tool name patterns
    if "search" in normalized_name.lower():
        return "research"

    if "read" in normalized_name.lower() or "get" in normalized_name.lower():
        return "requirements"

    if "edit" in normalized_name.lower() or "write" in normalized_name.lower():
        return "tdd"

    if "bash" in normalized_name.lower() or "run" in normalized_name.lower():
        return "verification"

    if "agent" in normalized_name.lower():
        return "agent_coordination"

    # No inference possible
    return None


def _normalize_step_name(step: str) -> str:
    """Normalize step name to match workflow_steps format.

    Args:
        step: Raw step name from inference

    Returns:
        Normalized step name (lowercase, underscores for spaces)
    """
    return step.lower().replace(" ", "_").replace("-", "_")


def infer_step_from_tool_use(tool_name: str, tool_input: dict[str, Any]) -> str | None:
    """Public API: Infer workflow step from tool usage.

    This is the main entry point for tool pattern inference.
    Called by hooks to automatically set breadcrumbs.

    Args:
        tool_name: Name of the tool being used (e.g., "Read", "WebSearch")
        tool_input: Input parameters passed to the tool

    Returns:
        Normalized step name (e.g., "research", "tdd") or None if not mappable

    Example:
        >>> infer_step_from_tool_use("WebSearch", {"query": "pytest async"})
        "research"
        >>> infer_step_from_tool_use("Read", {"file_path": "src/main.py"})
        "requirements"
        >>> infer_step_from_tool_use("UnknownTool", {})
        None
    """
    # Infer raw step name
    raw_step = _infer_step_from_tool(tool_name, tool_input)

    if not raw_step:
        return None

    # Normalize to match workflow_steps format
    return _normalize_step_name(raw_step)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_supported_tools() -> list[str]:
    """Get list of supported tool names for inference.

    Returns:
        List of tool names that can be mapped to workflow steps
    """
    return list(DEFAULT_TOOL_MAPPINGS.keys())


def add_tool_mapping(tool_name: str, step_name: str) -> None:
    """Add a custom tool-to-step mapping.

    Args:
        tool_name: Name of the tool to map
        step_name: Workflow step name to map to

    Example:
        >>> add_tool_mapping("MyCustomTool", "custom_step")
        >>> infer_step_from_tool_use("MyCustomTool", {})
        "custom_step"
    """
    DEFAULT_TOOL_MAPPINGS[tool_name] = step_name


def remove_tool_mapping(tool_name: str) -> None:
    """Remove a tool-to-step mapping.

    Args:
        tool_name: Name of the tool to unmap
    """
    DEFAULT_TOOL_MAPPINGS.pop(tool_name, None)


def clear_custom_mappings() -> None:
    """Clear all custom tool mappings (not implemented).

    Note:
        Current implementation doesn't track custom vs default mappings.
        This function is a placeholder for future enhancement.
    """
    pass
