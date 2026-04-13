#!/usr/bin/env python3
"""
PreToolUse_skill_pattern_gate.py
================================

PreToolUse hook that validates skill execution patterns BEFORE allowing tools.

This is the PRIMARY defense against skill substitution - it blocks invalid
tool usage at the PreToolUse stage, preventing the substitute analysis from
ever being generated.

PROBLEM SOLVED:
LLM loads skill documentation, then provides its own analysis instead of
executing the skill's designated workflow. Stop hook is a safety net;
this hook prevents the problem in real-time.

PARALLEL VALIDATION:
- Regex: Fast pattern matching against tool commands
- Daemon: Semantic similarity via embedding model
- Decision matrix handles disagreements and failures

LAYER 0: WORKFLOW STEPS ENFORCEMENT (v4.0):
- Skills declaring workflow_steps in SKILL.md frontmatter MUST be invoked
  via Skill tool before any other tool can be used.
- Detects pending_command_intent from skill_enforcer.py (UserPromptSubmit)
- Checks breadcrumb tracker's _load_workflow_steps() for workflow steps
- Blocks BEFORE first tool executes (prevents wasted generation)
- Terminal-scoped state files prevent cross-terminal contamination

FIRST-TOOL COHERENCE (v3.5):
- Skills declaring allowed_first_tools in SKILL.md frontmatter get
  first-tool gating: the first non-investigation tool must be in the list.
- Prevents intent misclassification (e.g., running tests when user asked
  "what skills use X?" which requires code search).
- Applies to ALL skills including knowledge/consultation skills.

AUTHOR: CSF NIP
VERSION: 4.0.0
"""

from __future__ import annotations

import json
import importlib.util
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

_script_path = Path(__file__)
for _hooks_root in (
    Path(r"P:\.claude\hooks"),
    _script_path.parent.parent,
    _script_path.resolve().parent.parent,
):
    _hooks_root_str = str(_hooks_root)
    if _hooks_root_str not in sys.path:
        sys.path.insert(0, _hooks_root_str)


_SKILL_GUARD_SRC = Path(r"P:\packages\skill-guard\src").resolve()
if _SKILL_GUARD_SRC.exists():
    _skill_guard_src_str = str(_SKILL_GUARD_SRC)
    if _skill_guard_src_str not in sys.path:
        sys.path.insert(0, _skill_guard_src_str)


def _clear_shadowed_hook_packages() -> None:
    """Drop cached __lib modules so the hooks-root package can import cleanly."""
    for module_name in list(sys.modules):
        if module_name != "__lib" and not module_name.startswith("__lib."):
            continue
        del sys.modules[module_name]


_clear_shadowed_hook_packages()
try:
    from __lib.hook_constants import KNOWLEDGE_SKILLS
except ImportError:
    KNOWLEDGE_SKILLS = set()

# Import skill auto-discovery for universal enforcement (LOGIC-002: add local exception handling)
try:
    from skill_guard.skill_auto_discovery import get_skill_config
except (ImportError, AttributeError):
    get_skill_config = None

# Import robust command extractor from skill_enforcer for stateless skill-first check
from UserPromptSubmit_modules.skill_enforcer import extract_command_name

# =============================================================================
# CONFIGURATION
# =============================================================================

ENABLED = os.environ.get("SKILL_PATTERN_ENFORCEMENT_ENABLED", "true").lower() == "true"
DAEMON_ENABLED = os.environ.get("SKILL_INTENT_DAEMON_ENABLED", "true").lower() == "true"
FIRST_TOOL_COHERENCE_ENABLED = (
    os.environ.get("FIRST_TOOL_COHERENCE_ENABLED", "true").lower() == "true"
)

STATE_DIR = Path("P:/.claude/state")
DISAGREEMENT_LOG = Path("P:/.claude/logs/skill_execution_gate.jsonl")
COHERENCE_LOG = Path("P:/.claude/logs/first_tool_coherence.jsonl")

# Investigation tools - ALWAYS allowed (for understanding the problem)
INVESTIGATION_TOOLS = {
    "Read",
    "Grep",
    "Glob",
    "AskUserQuestion",
    "Skill",
    # Analysis tools (for planning, not execution)
    "WebSearch",
    "WebFetch",
    "mcp__4_5v_mcp__analyze_image",
    "mcp__web_reader__webReader",
}


# =============================================================================
# SKILL EXECUTION REGISTRY (Extended v3.2 Schema)
# =============================================================================
# Each skill declares:
#   - tools: List of tool names that count as execution
#   - pattern: Optional regex that must appear in tool input (e.g., command)
#   - hint: User-facing message when blocked (NEW in v3.2)
#   - intent_enabled: Use daemon semantic validation (NEW in v3.2)

SKILL_EXECUTION_REGISTRY = {
    # External CLI skills (require Bash with specific command)
    "ask-olymp": {
        "tools": ["Bash", "Task"],
        "pattern": r"ask_cli\.py|ask-olymp",
        "hint": "Use /ask-olymp via ask_cli.py with opencode provider",
        "intent_enabled": False,
    },
    "olymp": {  # Alias
        "tools": ["Bash", "Task"],
        "pattern": r"ask_cli\.py|ask-olymp",
        "hint": "Use /ask-olymp via ask_cli.py with opencode provider",
        "intent_enabled": False,
    },
    # RCA/Truth - CLI launcher pattern (v3.2: fixed for python -m rca.hook_launcher)
    "rca": {
        "tools": ["Bash", "Task"],
        "pattern": r"rca\.hook_launcher|python.*-m.*rca|rca\s+\w+\.py",
        "hint": "Use /rca via python -m rca.hook_launcher or the rca CLI",
        "intent_enabled": True,
    },
    "truth": {
        "tools": ["Bash", "Task"],
        "pattern": r"src\.truth|validator|verify|truth_cli",
        "hint": "Use /truth via truth_cli.py or src.truth imports",
        "intent_enabled": True,
    },
    # Git operations
    "git": {
        "tools": ["Bash"],
        "pattern": r"git\s+",
        "hint": "Use git commands directly via Bash",
        "intent_enabled": False,
    },
    "commit": {
        "tools": ["Bash"],
        "pattern": r"git\s+commit",
        "hint": "Use git commit via Bash",
        "intent_enabled": False,
    },
    "push": {
        "tools": ["Bash"],
        "pattern": r"git\s+push",
        "hint": "Use git push via Bash",
        "intent_enabled": False,
    },
    # Build/test
    "build": {
        "tools": ["Bash", "Task"],
        "pattern": r"build|npm|pip|pytest|make",
        "hint": "Use build tools via Bash or Task",
        "intent_enabled": False,
    },
    # /test skill - requires actual test execution, not analysis
    "test": {
        "tools": ["Bash", "Task"],
        "pattern": r"pytest|python\s+-m\s+pytest|npm\s+test|coverage",
        "hint": "Run /test via actual test execution (pytest, npm test) - do not provide prose analysis without running tests",
        "intent_enabled": False,
    },
    # Web skills
    "research": {
        "tools": ["Bash", "Task"],
        "pattern": r"(python(\.exe)?\s+(-m\s+research\.cli|.*[\\/]research[\\/]cli\.py)|uv\s+run\s+(-m\s+)?research\.cli)",
        "hint": "Use /research via python -m research.cli (or research/cli.py)",
        "intent_enabled": False,
    },
    # Orchestration
    "orchestrator": {
        "tools": ["Bash", "Task"],
        "pattern": r"orchestrat",
        "hint": "Use orchestrator via Bash or Task",
        "intent_enabled": False,
    },
}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def _extract_command(tool_name: str, tool_input: dict) -> str:
    """Extract clean command string from tool input for pattern matching.

    Args:
        tool_name: Name of the tool being used
        tool_input: Input parameters passed to the tool

    Returns:
        Cleaned command string (lowercase, stripped) or empty string
    """
    if tool_name == "Bash":
        # Bash command is in "command" field
        cmd = tool_input.get("command", "")
        return str(cmd).lower().strip() if cmd else ""

    elif tool_name == "Task":
        # Task prompt is in "prompt" field
        prompt = tool_input.get("prompt", "")
        return str(prompt).lower().strip() if prompt else ""

    # For other tools, no command extraction
    return ""


def _check_regex(command: str, pattern: str) -> bool:
    """Check if command matches the required regex pattern.

    Args:
        command: The extracted command string (already lowercase)
        pattern: Regex pattern to match against

    Returns:
        True if pattern matches, False otherwise
    """
    if not pattern:
        return False

    try:
        return bool(re.search(pattern, command, re.IGNORECASE))
    except re.error:
        return False


def _check_daemon_intent(command: str, skill: str, timeout: float = 2.5) -> bool:
    """Check if command matches skill intent via daemon semantic validation.

    Args:
        command: The extracted command string
        skill: Skill name to check intent against
        timeout: Seconds to wait for daemon response

    Returns:
        True if daemon confirms intent match, False on error/no match
    """
    if not DAEMON_ENABLED:
        return False

    try:
        # Import here to avoid issues if daemon_client unavailable
        # Guard against sys.path accumulation (memory leak)
        _csf_src = str(Path("P:/__csf/src"))
        if _csf_src not in sys.path:
            sys.path.insert(0, _csf_src)
        from daemons.daemon_client import DaemonClient

        client = DaemonClient(auto_start=False, enable_fallback=True)

        # Query daemon for skill intent
        result = client.query("skill_intent", {"command": command, "skill": skill}, timeout=timeout)

        if result.get("status") == "success":
            intent_data = result.get("result", {})
            return intent_data.get("match", False)

    except ImportError:
        # Daemon client not available, fail gracefully (no stderr - Claude Code treats it as error)
        pass
    except Exception as e:
        # Daemon query failed, fail gracefully (no stderr - Claude Code treats it as error)
        pass

    return False


def _read_pending_state() -> dict | None:
    """Read current skill execution state from state file.

    Returns:
        State dict or None if no skill loaded
    """
    try:
        # Import shared state management
        sys.path.insert(0, str(Path(__file__).absolute().parent.parent))
        from skill_execution_state import read_pending_state

        return read_pending_state()
    except ImportError:
        # Fallback to direct read
        try:
            from skill_execution_state import _get_state_file

            state_file = _get_state_file()
            if state_file.exists():
                return json.loads(state_file.read_text())
        except Exception:
            pass
    return None


# TTL for pending_command_intent state file entries (90 seconds)
SKILL_FIRST_INTENT_TTL_SECONDS = 90


def _read_pending_command_intent() -> dict | None:
    """Read pending_command_intent state file for post-compaction slash detection.

    This reads the state file written by skill_enforcer.py (UserPromptSubmit hook)
    to detect slash commands that were invoked but whose transcript context was
    lost due to session compaction.

    Returns:
        State dict from pending_command_intent.json or None if:
        - File doesn't exist
        - Entry is stale (older than TTL)
        - Fingerprint matches current prompt (already handled this turn)
        - Terminal ID cannot be determined
    """
    # Get terminal ID via centralized detection.
    # This uses the same get_terminal_id() function as skill_enforcer.py, ensuring
    # consistent terminal ID detection across both producer (skill_enforcer) and
    # consumer (this hook) of the pending_command_intent state file.
    try:
        from __lib.hook_base import get_terminal_id
    except Exception:
        _hooks_root = Path(r"P:\.claude\hooks")
        _hook_base_path = _hooks_root / "__lib" / "hook_base.py"
        _hook_base_spec = importlib.util.spec_from_file_location(
            "_hooks_hook_base",
            _hook_base_path,
        )
        if _hook_base_spec is None or _hook_base_spec.loader is None:
            terminal_id = ""
        else:
            _hook_base_module = importlib.util.module_from_spec(_hook_base_spec)
            _hook_base_spec.loader.exec_module(_hook_base_module)
            get_terminal_id = _hook_base_module.get_terminal_id
            terminal_id = get_terminal_id(None)
    else:
        terminal_id = get_terminal_id(None)

    if not terminal_id:
        return None

    # Try the current terminal ID plus common bare/prefixed variants.
    candidate_terminal_ids = [terminal_id]
    if terminal_id.startswith("env_"):
        candidate_terminal_ids.append(terminal_id[4:])
    elif terminal_id.startswith("console_"):
        candidate_terminal_ids.append(terminal_id[8:])
    else:
        candidate_terminal_ids.extend([f"env_{terminal_id}", f"console_{terminal_id}"])

    state = None
    for candidate_terminal_id in dict.fromkeys(candidate_terminal_ids):
        state_file = (
            Path("P:/.claude/hooks/state/terminals")
            / candidate_terminal_id
            / "pending_command_intent.json"
        )
        if not state_file.exists():
            continue

        try:
            state = json.loads(state_file.read_text())
            break
        except Exception:
            continue

    if state is None:
        return None

    # Check TTL - discard entries older than 90 seconds
    created_at = state.get("created_at", 0)
    if created_at:
        age = time.time() - created_at
        if age > SKILL_FIRST_INTENT_TTL_SECONDS:
            return None

    # Check prompt fingerprint - if it matches current prompt, skip
    # (this turn already handled the slash command)
    fingerprint = state.get("prompt_fingerprint", "")
    if fingerprint:
        # Get current prompt fingerprint if available
        # The state file tracks what prompt was used - if current prompt matches,
        # we've already processed this slash command this turn
        current_fingerprint = os.environ.get("CLAUDE_PROMPT_FINGERPRINT", "")
        if current_fingerprint and fingerprint == current_fingerprint:
            return None

    return state


def _log_disagreement(
    skill: str, command: str, regex_result: bool, daemon_result: bool | None, decision: str
) -> None:
    """Log regex/daemon disagreement for pattern tuning.

    Args:
        skill: Skill being validated
        command: Command that was checked
        regex_result: True/False from regex check
        daemon_result: True/False/None from daemon (None = error)
        decision: Final decision made ("allow" or "block")
    """
    try:
        DISAGREEMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": time.time(),
            "event": "disagreement",
            "skill": skill,
            "command": command[:200],  # Truncate long commands
            "regex_match": regex_result,
            "daemon_match": daemon_result,
            "decision": decision,
        }
        with open(DISAGREEMENT_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


# =============================================================================
# FIRST-TOOL COHERENCE CHECK (v3.5)
# =============================================================================


def _log_coherence_event(
    event: str,
    skill: str,
    tool_name: str,
    allowed: list[str],
    decision: str,
) -> None:
    """Log first-tool coherence decisions for analysis."""
    try:
        COHERENCE_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": time.time(),
            "event": event,
            "skill": skill,
            "tool_name": tool_name,
            "allowed_first_tools": allowed,
            "decision": decision,
        }
        with open(COHERENCE_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def _check_first_tool_coherence(tool_name: str, state: dict) -> dict:
    """Check if the first non-investigation tool matches the skill's declaration.

    Skills can declare allowed_first_tools in their SKILL.md frontmatter.
    When present, the first substantive tool call must be in that list.
    This prevents intent misclassification (e.g., running python tests
    when the user asked a discovery question requiring code search).

    Args:
        tool_name: Name of the tool being called
        state: Current skill execution state

    Returns:
        Empty dict to allow, or {"block": True, "reason": "..."} to block
    """
    if not FIRST_TOOL_COHERENCE_ENABLED:
        return {}

    # Only check if skill declares allowed_first_tools
    allowed = state.get("allowed_first_tools", [])
    if not allowed:
        return {}

    # Skip if first tool already validated
    if state.get("first_tool_validated", False):
        return {}

    # This IS the first non-investigation tool call — check coherence
    skill = state.get("skill", "")

    if tool_name in allowed:
        # Match! Mark as validated via state management
        try:
            sys.path.insert(0, str(Path(__file__).absolute().parent.parent))
            from skill_execution_state import (
                mark_first_tool_validated,
            )

            mark_first_tool_validated()
        except ImportError:
            pass

        _log_coherence_event("first_tool_pass", skill, tool_name, allowed, "allow")
        return {}

    # MISMATCH: first tool is not in the allowed set
    _log_coherence_event("first_tool_blocked", skill, tool_name, allowed, "block")
    return {
        "block": True,
        "reason": (
            f"⛔ FIRST-TOOL COHERENCE MISMATCH for /{skill}\n\n"
            f"Your first action tool is '{tool_name}', but /{skill} expects "
            f"one of: {', '.join(allowed)}.\n\n"
            f"Re-read the user's question and choose the right tool.\n"
            f"For discovery questions ('what uses X?'), start with Grep/Glob.\n"
            f"For verification questions ('does X work?'), start with Bash.\n"
            f"For test execution, start with Bash (pytest/npm test)."
        ),
    }


def _load_frontmatter_execution_config(skill_name: str) -> dict:
    """Read execution config from a skill's SKILL.md frontmatter.

    Reads execution_tools, execution_pattern, and execution_hint fields.
    Called fresh every invocation — no caching, always current, multi-terminal safe.

    Args:
        skill_name: Skill name (without slash)

    Returns:
        Dict with tools/pattern/hint keys, or empty dict if not declared.
    """
    skill_file = Path("P:/.claude/skills") / skill_name / "SKILL.md"
    if not skill_file.exists():
        return {}
    try:
        import yaml

        content = skill_file.read_text(encoding="utf-8", errors="replace")
        parts = content.split("---")
        if len(parts) < 3:
            return {}
        fm = yaml.safe_load(parts[1])
        if not isinstance(fm, dict):
            return {}
        tools = fm.get("execution_tools", [])
        if not isinstance(tools, list) or not tools:
            return {}
        return {
            "tools": [str(t) for t in tools],
            "pattern": str(fm.get("execution_pattern", "")),
            "hint": str(fm.get("execution_hint", "")),
            "intent_enabled": bool(fm.get("execution_intent_enabled", False)),
        }
    except Exception:
        return {}


# =============================================================================
# MAIN HANDLER
# =============================================================================


def handle_pre_tool_use(data: dict) -> dict:
    """Main PreToolUse handler for skill pattern validation.

    Checks three layers:
    0. Workflow steps enforcement: Skills with workflow_steps MUST use Skill tool first
    1. First-tool coherence (v3.5): Does the first tool match the skill's
       declared allowed_first_tools? Applies to ALL skills including knowledge.
    2. Execution pattern validation (v3.2): Does the tool command match the
       skill's required execution pattern? Applies to execution-type skills.

    Args:
        data: Hook input dict with tool_name, tool_input, etc.

    Returns:
        Empty dict to allow, or {"block": true, "reason": "..."} to block
    """
    # Extract tool information
    tool_name = data.get("tool_name", "")
    tool_input = data.get("input", {})

    # =========================================================================
    # STATELESS SKILL-FIRST GATE (Per-Turn Check)
    # =========================================================================
    # This implements a stateless skill-first check that only examines:
    # 1. The current user message for slash commands
    # 2. The current tool call for Skill usage
    #
    # This eliminates circular dependencies on state files and prevents deadlocks.
    # If no slash command was used, or if Skill tool was used first, allow all tools.

    # Get user message from input data
    user_message = ""
    try:
        # Try multiple possible locations for user message
        user_message = str(data.get("user_message", "") or data.get("prompt", "") or "")
    except Exception:
        pass

    # Extract slash command from user message using robust regex (handles edge cases)
    slash_command = extract_command_name(user_message)

    # Stateless skill-first check
    if slash_command:
        # User typed a slash command - check if Skill tool is being used
        if tool_name == "Skill":
            # Skill tool is being used - check if it matches the slash command
            tool_input = data.get("input", {})
            skill_name = tool_input.get("skill", "")

            if skill_name.lower() == slash_command.lower():
                # Skill tool matches the slash command - allow it
                return {}

        # Slash command was used but Skill tool wasn't called first
        # Check if the skill has workflow_steps
        # Ensure skill_guard is in sys.path (QUAL-004: subprocess may not have module-level setup)
        from __lib.skill_guard_path import ensure_skill_guard_in_syspath
        ensure_skill_guard_in_syspath()
        try:
            from skill_guard.breadcrumb.tracker import _load_workflow_steps

            result = _load_workflow_steps(slash_command)
            workflow_steps = result.steps

            if workflow_steps:
                # Skill has workflow_steps - block with helpful message
                return {
                    "block": True,
                    "reason": (
                        f"⛔ SKILL-FIRST GATE\n\n"
                        f"You typed /{slash_command} but haven't called Skill('{slash_command}') yet.\n\n"
                        f"The skill /{slash_command} has {len(workflow_steps)} declared workflow steps.\n\n"
                        f"Your FIRST action must be: Skill(skill='{slash_command}')\n\n"
                        f"Do NOT respond with prose analysis or use other tools before calling Skill.\n"
                        f"Do NOT bypass this gate by outputting inline analysis text without calling Skill(...)."
                    ),
                }
        except ImportError:
            # breadcrumb system not available - allow tools (fail open)
            pass
        except Exception:
            # Error checking workflow_steps - allow tools (fail open)
            pass

    # =========================================================================
    # END STATELESS SKILL-FIRST GATE
    # =========================================================================

    # Always allow investigation tools before any state-file gating.
    # These tools are used to understand the problem, not execute the skill.
    if tool_name in INVESTIGATION_TOOLS:
        return {}

    # =========================================================================
    # LAYER 0.5 (STATE-FILE): Read pending_command_intent for post-compaction detection
    # =========================================================================
    # After compaction, the current user message may not contain the slash command
    # (transcript is compacted). The pending_command_intent.json state file survives
    # compaction and records what slash command was invoked.
    #
    # This layer reads that state file to detect slash commands that would otherwise
    # be invisible post-compaction. If a slash command is found in the state file
    # and the Skill tool hasn't been called yet this turn, block.
    #
    # TTL: Entries older than SKILL_FIRST_INTENT_TTL_SECONDS are discarded as stale.
    # Fingerprint: If fingerprint matches current prompt, skip (already handled this turn).

    intent_state = _read_pending_command_intent()
    if intent_state:
        slash_from_state = intent_state.get("skill", "")
        if slash_from_state:
            # Check if Skill tool is being used this turn
            if tool_name != "Skill":
                # Skill tool not called yet - check if this is a skill with workflow_steps
                try:
                    from skill_guard.breadcrumb.tracker import _load_workflow_steps

                    result = _load_workflow_steps(slash_from_state)
                    workflow_steps = result.steps

                    if workflow_steps:
                        # Skill has workflow_steps - block until Skill tool is called
                        return {
                            "block": True,
                            "reason": (
                                f"⛔ SKILL-FIRST GATE (state-file)\n\n"
                                f"Pending slash command /{slash_from_state} detected from prior state.\n\n"
                                f"The skill /{slash_from_state} has {len(workflow_steps)} declared workflow steps.\n\n"
                                f"Your FIRST action must be: Skill(skill='{slash_from_state}')\n\n"
                                f"Do NOT respond with prose analysis or use other tools before calling Skill.\n"
                                f"Do NOT bypass this gate by outputting inline analysis text without calling Skill(...)."
                            ),
                        }
                except ImportError:
                    # breadcrumb system not available - allow tools (fail open)
                    pass
                except Exception:
                    # Error checking workflow_steps - allow tools (fail open)
                    pass

    # Read current skill state
    state = _read_pending_state()

    if not state:
        # No skill loaded, allow all tools
        return {}

    skill = state.get("skill", "")
    if not skill:
        return {}

    # =========================================================================
    # LAYER 0.5: Topic drift prevention (v1.0)
    # Prevents pivoting to discovered-but-deferred issues (do_not_distract).
    # Active when workflow_stage.active_step is set and do_not_distract has items.
    # =========================================================================
    workflow_stage = state.get("workflow_stage", {})
    active_step = workflow_stage.get("active_step", "")
    do_not_distract = workflow_stage.get("do_not_distract", [])

    if active_step and do_not_distract:
        # Check if tool is being used for something in do_not_distract list
        # Extract what the tool is targeting from tool_input
        target_info = ""
        if tool_name == "Read":
            target_info = tool_input.get("file_path", "")
        elif tool_name == "Edit":
            target_info = tool_input.get("file_path", "")
        elif tool_name == "Write":
            target_info = tool_input.get("file_path", "")
        elif tool_name == "Bash":
            target_info = tool_input.get("command", "")

        # Check if target matches any do_not_distract item
        target_lower = target_info.lower()
        for blocked in do_not_distract:
            blocked_lower = blocked.lower()
            # Check for partial match in target or user message
            if (
                blocked_lower in target_lower
                or blocked_lower in user_message.lower()
            ):
                return {
                    "block": True,
                    "reason": (
                        f"⛔ TOPIC DRIFT PREVENTION\n\n"
                        f"You are working on: {active_step}\n\n"
                        f"The tool targets something you've deferred: '{blocked}'\n\n"
                        f"Complete the current step first, then address deferred items.\n\n"
                        f"To bypass: Add --allow-topic-switch to your message."
                    ),
                }

    # =========================================================================
    # LAYER 1: First-tool coherence (v3.5)
    # Applies to ALL skills that declare allowed_first_tools, including
    # knowledge/consultation skills like /ask, /discover, /test.
    # =========================================================================
    coherence_result = _check_first_tool_coherence(tool_name, state)
    if coherence_result.get("block"):
        return coherence_result

    # =========================================================================
    # LAYER 1.5: Dynamic knowledge skill detection (ROBUST)
    # Check if skill requires execution by inspecting state, not hardcoded set
    # =========================================================================
    # Method 1: Check state's required_tools field (most authoritative)
    required_tools_state = state.get("required_tools", [])
    if not required_tools_state:
        # Skill declares no execution required → treat as knowledge skill
        return {}

    # Method 2: Check if skill is in explicit KNOWLEDGE_SKILLS (fallback)
    if skill in KNOWLEDGE_SKILLS:
        return {}

    # =========================================================================
    # LAYER 2: Execution pattern validation (v3.2)
    # Only applies to execution-type skills (not knowledge skills).
    # =========================================================================
    # Get skill configuration — explicit registry, then auto-discovery
    skill_config = get_skill_config(skill, SKILL_EXECUTION_REGISTRY)
    if not skill_config or not skill_config.get("tools"):
        # No valid config found, fail open
        return {}

    # Check if this tool counts as execution
    required_tools = skill_config.get("tools", [])
    if tool_name not in required_tools:
        # This tool doesn't count as execution for this skill
        # For non-execution tools, allow (user may be preparing)
        return {}

    # Extract command for validation
    command = _extract_command(tool_name, tool_input)
    pattern = skill_config.get("pattern", "")
    hint = skill_config.get("hint", "")
    intent_enabled = skill_config.get("intent_enabled", False)

    # Run parallel validation
    regex_match = _check_regex(command, pattern) if pattern else False

    daemon_match = False
    if intent_enabled:
        # Run daemon check in parallel with regex
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_check_daemon_intent, command, skill)
            try:
                daemon_match = future.result(timeout=2.5)
            except Exception:
                daemon_match = False  # Timeout or error

    # Decision matrix
    decision = _make_decision(
        skill, command, regex_match, daemon_match, intent_enabled, pattern, hint
    )

    # Log disagreements for tuning
    if intent_enabled and (regex_match != daemon_match):
        _log_disagreement(skill, command, regex_match, daemon_match, decision["action"])

    if decision["action"] == "block":
        return {"block": True, "reason": decision["reason"]}

    return {}


def _make_decision(
    skill: str,
    command: str,
    regex_match: bool,
    daemon_match: bool,
    intent_enabled: bool,
    pattern: str,
    hint: str,
) -> dict:
    """Make allow/block decision using decision matrix.

    Decision Matrix:
    1. Both True → ALLOW (PASS)
    2. Regex=True, Daemon=False → ALLOW (regex wins, log concern)
    3. Regex=False, Daemon=True → BLOCK (daemon caught semantic match)
    4. Both False → BLOCK (FAIL, neither validates)
    5. Regex=True, Daemon=Error → ALLOW (daemon down, regex sufficient)
    6. Regex=False, Daemon=Error → BLOCK (daemon down, regex fails)

    Args:
        skill: Skill being validated
        command: Command that was checked
        regex_match: Result from regex check
        daemon_match: Result from daemon check
        intent_enabled: Whether daemon check was enabled
        pattern: The regex pattern used
        hint: User-facing hint message

    Returns:
        Dict with "action" ("allow"/"block") and "reason" (for blocks)
    """
    # Case 1: Both match - PASS
    if regex_match and daemon_match:
        return {
            "action": "allow",
            "reason": "",
        }

    # Case 2: Regex matches, daemon doesn't - allow with log
    if regex_match and not daemon_match and intent_enabled:
        # Daemon semantic check disagrees with regex
        # Log the disagreement but allow (regex is stricter)
        return {
            "action": "allow",
            "reason": "",
        }

    # Case 3: Regex fails, daemon matches - BLOCK
    if not regex_match and daemon_match:
        return {
            "action": "block",
            "reason": (
                f"⛔ [{skill}] execution pattern mismatch.\n\n"
                f"📋 Command:\n{command[:200]}\n\n"
                f"🔍 Expected pattern:\n{pattern}\n\n"
                f"💡 How to fix:\n{hint}\n\n"
                f"🎯 Why this was blocked:\n"
                f"Semantic analysis detected this is a /{skill} invocation, "
                f"but the command pattern doesn't match the required format.\n"
                f"The command must contain the expected pattern to proceed."
            ),
        }

    # Case 4: Both fail - BLOCK with detailed hint
    if not regex_match and not daemon_match:
        return {
            "action": "block",
            "reason": (
                f"⛔ [{skill}] execution pattern mismatch.\n\n"
                f"📋 Command:\n{command[:200]}\n\n"
                f"🔍 Expected pattern:\n{pattern}\n\n"
                f"💡 How to fix:\n{hint}\n\n"
                f"🎯 Why this was blocked:\n"
                f"This doesn't match the required execution pattern for /{skill}. "
                f"Commands for /{skill} must include the pattern shown above."
            ),
        }

    # Case 5: Regex matches, daemon error/timeout - ALLOW
    if regex_match and not intent_enabled:
        # Daemon not enabled for this skill, regex sufficient
        return {
            "action": "allow",
            "reason": "",
        }

    # Case 6: Regex fails, daemon error - BLOCK with hint
    return {
        "action": "block",
        "reason": (
            f"⛔ [{skill}] execution pattern mismatch.\n\n"
            f"📋 Command:\n{command[:200]}\n\n"
            f"🔍 Expected pattern:\n{pattern}\n\n"
            f"💡 How to fix:\n{hint}\n\n"
            f"🎯 Why this was blocked:\n"
            f"The command doesn't contain the required pattern for /{skill}."
        ),
    }


# =============================================================================
# HOOK ENTRY POINT
# =============================================================================


def main():
    """Hook entry point - handles JSON input from stdin."""
    try:
        # Read hook input
        payload = json.loads(sys.stdin.read())

        # Check if enforcement is enabled
        if not ENABLED:
            print(json.dumps({}))
            sys.exit(0)

        # Process the tool use
        result = handle_pre_tool_use(payload)

        # Output result
        print(json.dumps(result))
        sys.exit(0)

    except json.JSONDecodeError:
        # Bad stdin - fail open (allow tool to proceed)
        print(json.dumps({}))
        sys.exit(0)

    except Exception as e:
        # Unexpected error - fail open silently (no stderr - Claude Code treats it as error)
        # Critical: PreToolUse exceptions block ALL tools
        import traceback

        # Log error to diagnostics only, not stderr
        try:
            from pathlib import Path
            log_path = Path("P:/.claude/hooks/logs/diagnostics/skill_pattern_gate_errors.log")
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                from datetime import datetime
                ts = datetime.now().isoformat()
                f.write(f"[{ts}] Error: {e}\n{traceback.format_exc()}\n")
        except Exception:
            pass  # If logging fails, continue anyway

        print(json.dumps({}))  # Allow tool to proceed
        sys.exit(0)


if __name__ == "__main__":
    main()
