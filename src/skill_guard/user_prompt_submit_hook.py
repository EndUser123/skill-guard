r"""
user_prompt_submit_hook.py
==========================

UserPromptSubmit handler for execution contract runtime.

INVARIANT 2 (UPS creates the run):
  UserPromptSubmit hook is the ONLY hook that creates execution-state.json.
  It runs before any tool use, so the run state exists before PreToolUse checks.
  No other hook (PreToolUse, Stop, PostToolUse) creates a run.

INVARIANT 6 (contract type derived from SKILL.md):
  contract_type and response_requirements are derived from skill frontmatter
  via get_skill_config(). No hardcoded defaults — discovery from skill metadata.

Responsibilities:
1. Detect explicit /skill-name invocation from the prompt
2. Ignore non-skill slash commands (discover, ask, etc.)
3. Resolve skill metadata via get_skill_config()
4. Call runtime.create_run(...) to produce execution-state.json + run_created event

This hook MUST run before any tool use — it creates the authoritative run state
that PreToolUse reads. Fail-open: if run creation fails, allow all tools (no false blocks).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — resolve __lib shadowing
# ---------------------------------------------------------------------------

_HOOKS_DIR = Path(__file__).resolve().parent
_SKILL_GUARD_SRC = Path(r"P:\\\\\\packages/skill-guard/src")
_MAIN_HOOKS_DIR = Path(r"P:\\\\\\.claude/hooks")

for _p in (_MAIN_HOOKS_DIR, _HOOKS_DIR, _SKILL_GUARD_SRC):
    if _p.exists():
        _s = str(_p)
        if _s in sys.path:
            sys.path.remove(_s)
        sys.path.insert(0, _s)

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

from skill_guard.execution_runtime import ExecutionRuntime
from skill_guard.execution_run import ExecutionRun
from skill_guard.skill_auto_discovery import get_skill_config, discover_all_skills
from skill_guard.utils.terminal_detection import detect_terminal_id
from skill_guard.slash_command_observability import extract_command_name, extract_slash_command
from skill_guard.skill_enforcer import (
    build_command_context,
    is_topic_inquiry,
    log_command_intent_telemetry,
    should_block_command,
)

# Contract type mapping: skill config value → ExecutionRun contract_type
_CONTRACT_TYPE_MAP = {
    "workflow": "workflow-execution",
    "output": "structured-output",
    "hybrid": "hybrid",
    "analysis": "workflow-execution",  # analysis uses workflow-execution default
}


def _map_contract_type(config_contract: str) -> str:
    """Map skill config contract_type to ExecutionRun contract_type."""
    return _CONTRACT_TYPE_MAP.get(config_contract, "workflow-execution")


def _get_allowed_tools(skill_name: str) -> list[str]:
    """Derive allowed_tools from the target skill's frontmatter, not global discovery."""
    config = get_skill_config(skill_name, explicit_registry=None)
    tools = config.get("allowed_first_tools", [])
    # Fallback: infer from contract type if no explicit tools declared
    if not tools:
        contract = config.get("contract_type", "analysis")
        if contract in ("workflow", "hybrid"):
            tools = ["Bash"]
    return tools


def _get_required_artifacts(skill_name: str) -> list[str]:
    """Derive required_artifacts from skill frontmatter."""
    config = get_skill_config(skill_name, explicit_registry=None)
    artifacts = config.get("required_phase_artifacts", [])
    if not artifacts:
        # Also check required_markers / required_sections as artifact proxies
        artifacts = config.get("required_markers", []) + config.get("required_sections", [])
    return artifacts


def _get_response_requirements(skill_name: str) -> dict:
    """Derive response_requirements from skill frontmatter."""
    config = get_skill_config(skill_name, explicit_registry=None)
    return {
        "sections": config.get("required_sections", []),
        "prohibited_claims": config.get("prohibited_claims", []),
        "must_use_skill": config.get("must_use_skill", False),
        "evidence_bound": config.get("evidence_bound", False),
    }


# ---------------------------------------------------------------------------
# Non-skill commands that should NOT create runs
# ---------------------------------------------------------------------------

_NON_SKILL_COMMANDS = frozenset({
    "discover", "ask", "search", "research", "help", "config",
    "init", "review", "genius", "reason", "s",
    "status", "model", "cost", "stats", "clear",
})


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------

def handle_user_prompt_submit(data: dict) -> dict:
    """
    UserPromptSubmit handler for skill enforcement + execution contract run creation.

    Returns {"additionalContext": "..."} when enforcement fires, {"continue": True} otherwise.
    Run creation is a side effect; it does not change the return shape.

    Built-in commands and non-skill commands return early before run creation.
    """
    prompt = data.get("prompt", "") or data.get("userMessage", "") or ""
    session_id = data.get("session_id", "") or ""
    terminal_id = detect_terminal_id() or os.environ.get("CLAUDE_TERMINAL_ID", "unknown")

    normalized = str(prompt).strip()

    # Topic inquiries ("tell me about /cmd") bypass enforcement entirely
    if is_topic_inquiry(normalized):
        return {"continue": True}

    # Extract command + args
    command, args = extract_slash_command(normalized)
    if not command:
        return {"continue": True}

    # Built-ins, ignored commands, and non-skill commands pass through without creating runs
    if command in _NON_SKILL_COMMANDS or should_block_command(command):
        return {"continue": True}

    # Run creation (side effect, fail-open) — only for skills that will actually execute
    skill_name = command
    config = get_skill_config(skill_name, explicit_registry=None)
    if config.get("discovered") or config.get("has_execution", True):
        try:
            config_contract = config.get("contract_type", "analysis")
            runtime = ExecutionRuntime()
            run = runtime.create_run(
                skill_name=skill_name,
                contract_type=_map_contract_type(config_contract),
                session_id=session_id,
                required_artifacts=_get_required_artifacts(skill_name),
                allowed_tools=_get_allowed_tools(skill_name),
                blocked_tools=[],
                response_requirements=_get_response_requirements(skill_name),
            )
            turn_id = data.get("turn_id") or data.get("turnId")
            if turn_id and hasattr(run, "turn_id"):
                run.turn_id = turn_id
                runtime.store.save_run(run)
        except (OSError, RuntimeError, ValueError, KeyError):
            pass  # fail-open

    # Write telemetry (fail-open)
    try:
        log_command_intent_telemetry(terminal_id, session_id, prompt, command)
    except OSError:
        pass

    return {"additionalContext": build_command_context(command, args)}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def user_prompt_submit_main():
    """Subprocess entry point for UserPromptSubmit hook."""
    import json
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        print(json.dumps({"continue": True}))
        return
    result = handle_user_prompt_submit(payload)
    print(json.dumps(result))


if __name__ == "__main__":
    subcommand = sys.argv[1] if len(sys.argv) > 1 else ""
    if subcommand == "user_prompt_submit_main":
        user_prompt_submit_main()
    else:
        user_prompt_submit_main()