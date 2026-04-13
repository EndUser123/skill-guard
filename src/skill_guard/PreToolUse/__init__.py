"""PreToolUse hooks for skill-guard.

This package contains PreToolUse hook implementations that run before
tool execution to enforce skill patterns.
"""

from .PreToolUse_skill_pattern_gate import handle_pre_tool_use

__all__ = ["handle_pre_tool_use"]
