"""PostToolUse hooks for skill-guard.

This package contains PostToolUse hook implementations that run after
tool execution to track skill-related state.
"""

import sys
from pathlib import Path

from .skill_execution_tracker import SkillExecutionTracker


# Cache for the hooks posttooluse module reference
_hooks_posttooluse_module = None


def __getattr__(name: str):
    """Lazy import of skill_command_hook from hooks path.

    This handles the case where skill_guard.posttooluse is already in sys.modules
    (polluted by conftest.py sys.path setup) but we need to access the hooks
    version of skill_command_hook. By temporarily removing the skill_guard.posttooluse
    from sys.modules during the import, we ensure Python resolves posttooluse
    via sys.path to the hooks version.
    """
    global _hooks_posttooluse_module

    if name == "skill_command_hook":
        hooks_paths = (
            Path(r"P:\.claude\hooks"),
            Path(__file__).parent.parent.parent / ".claude" / "hooks",
        )
        for hooks_root in hooks_paths:
            skill_command_hook_path = hooks_root / "posttooluse" / "skill_command_hook.py"
            if skill_command_hook_path.exists():
                hooks_posttooluse = str(hooks_root / "posttooluse")

                # Temporarily remove skill_guard.posttooluse AND bare posttooluse
                # so Python re-searches sys.path and finds the hooks version
                sg_posttooluse = sys.modules.pop("skill_guard.posttooluse", None)
                _bare_posttooluse = sys.modules.pop("posttooluse", None)
                try:
                    # Add hooks/posttooluse to sys.path
                    if hooks_posttooluse not in sys.path:
                        sys.path.insert(0, hooks_posttooluse)

                    # Import the hooks posttooluse package and get skill_command_hook
                    import posttooluse as hooks_postmod
                    from posttooluse.skill_command_hook import SkillCommandHook

                    # Cache the hooks posttooluse module for future imports
                    _hooks_posttooluse_module = hooks_postmod

                    # Register posttooluse.skill_command_hook in sys.modules
                    # so that "from posttooluse.skill_command_hook import X" works
                    sys.modules["posttooluse.skill_command_hook"] = SkillCommandHook

                    return SkillCommandHook
                finally:
                    # Restore both to sys.modules
                    if sg_posttooluse is not None:
                        sys.modules["skill_guard.posttooluse"] = sg_posttooluse
                    if _bare_posttooluse is not None:
                        sys.modules["posttooluse"] = _bare_posttooluse
                return
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["SkillExecutionTracker"]
