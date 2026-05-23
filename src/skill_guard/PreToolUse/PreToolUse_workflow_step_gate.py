"""PreToolUse hook that advises against skipping workflow steps during skill execution.

When a skill with workflow_steps is active, this gate checks whether the current
tool call appears to belong to a later step than the one we're on. If so, it
returns an advisory reminding the agent to complete the current step first.

This is advisory-only (never blocks) because:
  - Pattern matching is heuristic, not exact
  - Some skills legitimately allow out-of-order execution
  - False positives would be more harmful than false negatives

Design:
  - Reads skill execution state from the pending state file
  - Loads workflow_steps from the skill's SKILL.md frontmatter
  - Checks Bash commands against step-specific patterns
  - Checks Read/Write/Edit against artifact paths from verification.expected_artifacts
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Ensure skill_guard package is importable
_SRC_DIR = Path(__file__).resolve().parent.parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


def _read_skill_state() -> dict[str, Any]:
    """Read the current skill execution state from the pending state file."""
    try:
        from skill_guard._state_io import _read_pending_state_file, detect_terminal_id
        terminal_id = detect_terminal_id()
        if not terminal_id:
            return {}
        state = _read_pending_state_file(terminal_id)
        return state or {}
    except Exception:
        return {}


def _load_workflow_steps(skill_name: str) -> list[dict[str, Any]]:
    """Load workflow_steps from a skill's SKILL.md frontmatter."""
    try:
        from skill_guard.breadcrumb.tracker import _load_workflow_steps as _load
        result = _load(skill_name)
        return result.steps if result else []
    except Exception:
        return []


def _load_expected_artifacts(skill_name: str) -> list[str]:
    """Load expected_artifacts from a skill's verification section."""
    try:
        import yaml
    except ImportError:
        return []

    skill_dir = Path(r"P:/.claude/skills") / skill_name.lower()
    skill_file = skill_dir / "SKILL.md"

    if not skill_file.exists():
        # Try plugin locations
        for plugin_dir in Path("P:/packages/.claude-marketplace/plugins").iterdir():
            candidate = plugin_dir / "skills" / skill_name / "SKILL.md"
            if candidate.exists():
                skill_file = candidate
                break

    if not skill_file.exists():
        return []

    try:
        content = skill_file.read_text(encoding="utf-8", errors="replace")
        parts = content.split("---")
        if len(parts) < 3:
            return []
        fm_data = yaml.safe_load(parts[1])
        if not isinstance(fm_data, dict):
            return []
        verification = fm_data.get("verification", {})
        return verification.get("expected_artifacts", [])
    except Exception:
        return []


def _get_ordered_artifact_groups(
    steps: list[dict[str, Any]],
    expected_artifacts: list[str],
) -> dict[int, list[str]]:
    """Map artifact paths to step indices based on ordering.

    Artifacts are assigned to steps in order: the first artifact
    to step 1, second to step 2, etc. This is a heuristic that
    works because expected_artifacts typically lists outputs in
    step order.
    """
    if not expected_artifacts or not steps:
        return {}

    # Filter to artifact paths (not URL patterns)
    concrete_paths = [
        a for a in expected_artifacts
        if not a.startswith("http") and "{terminal_id}" not in a
    ]

    # Assign to steps
    groups: dict[int, list[str]] = {}
    for i, artifact in enumerate(concrete_paths):
        step_idx = min(i + 1, len(steps) - 1)  # Skip step 0 (setup), assign to step 1+
        groups.setdefault(step_idx, []).append(artifact)

    return groups


def _check_artifact_existence(
    artifacts: list[str],
    terminal_id: str = "",
) -> list[str]:
    """Return list of artifact paths that DON'T exist yet."""
    missing = []
    for artifact in artifacts:
        # Expand {terminal_id} placeholder
        expanded = artifact.replace("{terminal_id}", terminal_id)
        if not Path(expanded).exists():
            missing.append(expanded)
    return missing


def run(data: dict[str, Any]) -> dict[str, Any] | None:
    """Check if a tool call skips workflow steps during skill execution.

    Returns:
        {"continue": True, "reason": "..."} with advisory, or None to allow silently.
    """
    if os.environ.get("WORKFLOW_STEP_GATE_ENABLED", "true").lower() != "true":
        return None

    tool_name = data.get("tool_name", "")

    # Only gate on tool calls that happen during skill execution
    if tool_name not in ("Bash", "Write", "Edit", "MultiEdit", "Agent"):
        return None

    # Read current skill state
    state = _read_skill_state()
    if not state:
        return None

    skill_name = state.get("skill_name", "")
    if not skill_name:
        return None

    # Check if skill is in executing phase
    phase = state.get("phase", "")
    if phase not in ("loaded", "executing"):
        return None

    # Load workflow steps
    steps = _load_workflow_steps(skill_name)
    if not steps or len(steps) < 2:
        return None  # No multi-step workflow to gate on

    current_step_idx = state.get("workflow_stage", {}).get("step_index", 0)

    # For the first tool call after skill load, check if it skips Step 1
    if current_step_idx == 0 and tool_name == "Bash":
        command = data.get("tool_input", {}).get("command", "")

        # Heuristic: check if command contains indicators of later steps
        later_step_indicators = _extract_later_step_indicators(steps, 0)
        for indicator in later_step_indicators:
            if indicator and indicator in command:
                step_names = [s.get("id", f"Step {i+1}") for i, s in enumerate(steps)]
                return {
                    "continue": True,
                    "reason": (
                        f"WORKFLOW STEP ADVISORY: Skill '{skill_name}' has {len(steps)} steps.\n"
                        f"Current: Step 1 — {step_names[0]}\n"
                        f"Command matches: Step {steps[0].get('id', '?')} patterns\n"
                        f"Full workflow:\n"
                        + "\n".join(
                            f"  {'→' if i == 0 else ' '} {i+1}. {name}"
                            for i, name in enumerate(step_names)
                        )
                        + "\nComplete Step 1 before running Step 2 commands."
                    ),
                }

    # For artifact-producing tool calls, check if prior step artifacts exist
    if tool_name in ("Write", "Edit", "MultiEdit"):
        expected = _load_expected_artifacts(skill_name)
        if expected:
            terminal_id = state.get("terminal_id", "")
            artifact_groups = _get_ordered_artifact_groups(steps, expected)

            # Check if any prior step's artifacts are missing
            for step_idx in range(0, current_step_idx):
                if step_idx in artifact_groups:
                    missing = _check_artifact_existence(
                        artifact_groups[step_idx], terminal_id
                    )
                    if missing:
                        return {
                            "continue": True,
                            "reason": (
                                f"WORKFLOW STEP ADVISORY: Prior step artifacts missing.\n"
                                f"Step {step_idx + 1} artifacts not yet created:\n"
                                + "\n".join(f"  - {m}" for m in missing[:3])
                                + "\nComplete prior steps before producing later artifacts."
                            ),
                        }

    return None


def _extract_later_step_indicators(
    steps: list[dict[str, Any]],
    current_idx: int,
) -> list[str]:
    """Extract text indicators from steps beyond current_idx.

    Looks for unique strings in step IDs and names that could appear
    in bash commands for those steps.
    """
    indicators = []
    for i in range(current_idx + 1, len(steps)):
        step = steps[i]
        step_id = step.get("id", "")

        # Extract distinctive tokens from step names
        # e.g., "Initialize file-based session" → "premortem_io", "session_dir"
        # e.g., "Launch Phase 1" → "p1_initial_review", "p1_findings"
        tokens = _step_to_command_tokens(step_id)
        indicators.extend(tokens)

    return indicators


def _step_to_command_tokens(step_id: str) -> list[str]:
    """Convert a step name to likely command tokens.

    Maps common step names to the distinctive substrings that would
    appear in bash commands for those steps.
    """
    step_lower = step_id.lower()

    # Phase-specific patterns (most common workflow step names)
    _PATTERN_MAP: list[tuple[str, list[str]]] = [
        ("phase 1", ["p1_", "phase1", "triage", "specialist"]),
        ("phase 2", ["p2_", "phase2", "meta_critique", "meta-critique"]),
        ("phase 3", ["p3_", "phase3", "synthesis"]),
        ("session", ["premortem_io", "session_dir", "find_or_create_session"]),
        ("capture work", []),  # Step 1 — no distinctive bash tokens
        ("deliver", ["rns", "render"]),
        ("verification", ["verification"]),
        ("execute", ["step_8", "implement"]),
    ]

    for pattern, tokens in _PATTERN_MAP:
        if pattern in step_lower:
            return tokens

    return []


if __name__ == "__main__":
    try:
        raw = sys.stdin.read().strip()
        input_data = json.loads(raw) if raw else {}
    except Exception:
        input_data = {}

    result = run(input_data)
    if result is None:
        result = {"continue": True}

    print(json.dumps(result))
