#!/usr/bin/env python3
from __future__ import annotations

r"""
Skill Execution Tracker
=======================

PostToolUse hook that tracks Skill and tool usage for execution validation.
Works with StopHook_skill_execution_gate.py to prevent skill substitution.

When an execution-type skill is loaded (via Skill tool), this hook
tracks subsequent tool usage to determine if the skill was properly executed.

Also writes loaded_skill to checkpoint task metadata for SessionStart restoration.
"""

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Add parent hooks directory for imports.
# Keep both the symlink-local hooks root and the resolved package root so the
# module works whether it is launched through P:\\\\\\.claude/hooks or imported
# directly from the package source tree.
_script_path = Path(__file__)
for _hooks_root in (
    Path(r"$CLAUDE_ROOT/hooks"),
    _script_path.parent.parent,
    _script_path.resolve().parent.parent,
):
    _hooks_root_str = str(_hooks_root)
    if _hooks_root_str not in sys.path:
        sys.path.insert(0, _hooks_root_str)


class SkillExecutionTracker:
    """Tracks skill loads and tool usage for execution validation.

    Non-blocking - just tracks state for the Stop hook to validate.
    Base class is injected in __init__ to avoid circular import issues.
    r"""

    tool_matcher = {"Skill", "Bash", "Write", "Edit", "MultiEdit", "Task"}

    env_var = "SKILL_EXECUTION_GATE_ENABLED"
    default_enabled = True

    def __init__(self):
        # Import PostToolUseHook here (not at module level) to avoid sys.path
        # conflicts when skill_guard.posttooluse and P:\\\\\\‎.claude/hooks/posttooluse
        # are both in the module graph during pytest runs.
        from posttooluse.base import PostToolUseHook
        # Dynamically inject base class to avoid circular import at class definition time
        self.__class__.__bases__ = (PostToolUseHook,)
        PostToolUseHook.__init__(self)
        self._import_functions()

    def _import_functions(self):
        """Fail-fast import of state management functions."""
        from skill_execution_state import (
            detect_terminal_id,
            record_tool_use,
            set_skill_loaded,
            update_workflow_stage,
        )
        self._set_skill_loaded = set_skill_loaded
        self._record_tool_use = record_tool_use
        self._detect_terminal_id = detect_terminal_id
        self._update_workflow_stage = update_workflow_stage
        self._imports_ok = True

    def _load_workflow_steps(self, skill_name: str):
        """Import _load_workflow_steps from skill_guard.breadcrumb.tracker.

        Fails fast if the module or function is unavailable.
        """
        from skill_guard.breadcrumb.tracker import _load_workflow_steps as _lw
        return _lw(skill_name)

    def process(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_response: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Track skill and tool usage.

        Non-blocking - returns passed=True always.
        State is written for Stop hook to validate.
        """
        if not self._imports_ok:
            return {"passed": True, "skipped": True, "reason": "import_failed"}

        if tool_name == "Skill":
            # Extract skill name
            skill_name = self._extract_skill_name(tool_input)
            if skill_name:
                self._set_skill_loaded(skill_name)
                # Write loaded_skill to checkpoint task for SessionStart restoration
                self._update_checkpoint_task_with_skill(skill_name)
                # Initialize workflow_stage with step info from skill's workflow_steps
                steps_result = self._load_workflow_steps(skill_name)
                if steps_result and steps_result.steps:
                    first_step = steps_result.steps[0]
                    self._update_workflow_stage(
                        active_step=first_step.get("id", ""),
                        total_steps=len(steps_result.steps),
                        step_index=0,
                    )
                elif steps_result and not steps_result.steps:
                    # Skill has no workflow_steps but has parse_error? skip silently
                    pass
                return {
                    "passed": True,
                    "metadata": {"skill_loaded": skill_name}
                }
        else:
            # Track all other tool usage
            self._record_tool_use(tool_name, tool_input)
            return {
                "passed": True,
                "metadata": {"tool_recorded": tool_name}
            }

        return {"passed": True}

    def _update_checkpoint_task_with_skill(self, skill_name: str) -> None:
        """Update checkpoint task with loaded_skill metadata.

        This allows SessionStart to restore skill execution context after compaction.
        """
        try:
            # Get terminal ID for checkpoint task naming
            terminal_id = self._detect_terminal_id()
            if not terminal_id:
                return

            # Get project root from environment
            project_root = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd()))

            # Find the most recent checkpoint task for this terminal
            # Task name format: CHECKPOINT: {task_name}__{terminal_id}
            # We need to find the task with our terminal_id suffix
            db_path = project_root / ".cks" / "storage" / "cks.db"
            if not db_path.exists():
                return

            # Import TaskRepository
            from ..repositories.task_repository import TaskRepository
            task_repo = TaskRepository(db_path=str(db_path))

            # Find the checkpoint task by querying for tasks with our terminal_id
            # The task name ends with __{terminal_id}
            cursor = task_repo.conn.cursor()
            cursor.execute("""
                SELECT name, strategic_context
                FROM tasks
                WHERE name LIKE ?
                ORDER BY updated_at DESC
                LIMIT 1
            """, (f"%__{terminal_id}",))

            result = cursor.fetchone()
            if result:
                task_name, strategic_context_json = result
                # Parse existing strategic_context
                try:
                    if strategic_context_json:
                        strategic_context = json.loads(strategic_context_json)
                    else:
                        strategic_context = {}
                except json.JSONDecodeError:
                    strategic_context = {}

                # Update with loaded_skill
                strategic_context["loaded_skill"] = skill_name
                strategic_context["loaded_skill_at"] = datetime.now(UTC).isoformat()

                # Update the task
                cursor.execute("""
                    UPDATE tasks
                    SET strategic_context = ?
                    WHERE name = ?
                """, (json.dumps(strategic_context), task_name))
                task_repo.conn.commit()

        except Exception:
            # Non-blocking: log but don't fail the hook
            pass

    def _extract_skill_name(self, tool_input: dict[str, Any] | str) -> str:
        """Extract skill name from various input formats."""
        if isinstance(tool_input, dict):
            return tool_input.get("skill", "") or tool_input.get("name", "")
        elif isinstance(tool_input, str):
            return tool_input
        return ""
