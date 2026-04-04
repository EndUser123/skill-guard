#!/usr/bin/env python3
"""
StopHook_skill_execution_gate.py
=================================

Safety net for skill execution validation.

This is the SECONDARY defense - the PreToolUse hook handles real-time
blocking. This Stop hook only fires when PreToolUse failed to block,
indicating a system issue that should be logged.

PROBLEM SOLVED:
Claude loads skill documentation, then provides its own analysis instead
of executing the skill's designated workflow.

v3.2 CHANGES:
- Simplified to safety net only (PreToolUse is primary defense)
- Late violation logging indicates PreToolUse failure
- Extended registry schema with hint and intent_enabled

v3.3 CHANGES:
- Added Layer 1 marker-based governance (from v3.0 port)
- extract_response_text() reads from transcript_path JSONL
- Governance state read from skill_governance_state.json
- Two-strike pattern: retry on first bypass, hard block on second

v3.4 CHANGES:
- Slash command bypass detection: blocks when user types /command but
  assistant ignores it and responds with prose (no tools used)
- Extracts user prompt from transcript_path to detect slash commands
- Works even when no governance state exists (skill file not found)
- Excludes built-in CLI commands, lightweight skills, and knowledge skills

AUTHOR: CSF NIP
VERSION: 3.4.1
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

HOOKS_DIR = Path(__file__).resolve().parent
SKILL_GUARD_SRC = Path("P:/packages/skill-guard/src")

# Import hook_main decorator
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))
if SKILL_GUARD_SRC.exists() and str(SKILL_GUARD_SRC) not in sys.path:
    sys.path.insert(0, str(SKILL_GUARD_SRC))
try:
    from __lib.hook_base import hook_main
    from __lib.hook_constants import KNOWLEDGE_SKILLS
except ImportError:
    lib_dir = HOOKS_DIR / "__lib"
    if str(lib_dir) not in sys.path:
        sys.path.insert(0, str(lib_dir))
    from hook_base import hook_main
    from hook_constants import KNOWLEDGE_SKILLS

from __lib.runtime_env import get_active_turn_id as _get_active_turn_id
from __lib.runtime_env import get_terminal_id as _get_terminal_id
from __lib.runtime_env import ledger_available as _ledger_available

LEDGER_AVAILABLE = _ledger_available()

# =============================================================================
# CONFIGURATION
# =============================================================================

ENABLED = os.environ.get("SKILL_EXECUTION_GATE_ENABLED", "true").lower() == "true"

STATE_DIR = Path("P:/.claude/state")

# Per-terminal log files (multi-terminal safe - no shared state)
_log_tid = ""
try:
    from __lib.terminal_detection import detect_terminal_id

    _log_tid = detect_terminal_id() or ""
except Exception:
    pass
_tid_suffix = f"_{_log_tid}" if _log_tid else ""
LOG_FILE = Path(f"P:/.claude/logs/skill_execution_gate{_tid_suffix}.jsonl")
DEBUG_LOG_FILE = Path(f"P:/.claude/logs/skill_execution_gate{_tid_suffix}_debug.log")

# Stale timeout (prevents blocking indefinitely)
STALE_TIMEOUT = 300  # 5 minutes

DEBUG = os.environ.get("SKILL_EXEC_DEBUG", "0") == "1"

# Slash commands that are NOT skills (built-in CLI commands)
# These should never be blocked by skill enforcement
BUILTIN_SLASH_COMMANDS = {
    "help",
    "clear",
    "compact",
    "cost",
    "doctor",
    "init",
    "login",
    "logout",
    "memory",
    "permissions",
    "review",
    "status",
    "terminal-setup",
    "vim",
    "bug",
    "config",
    "model",
    "tasks",
    "listen",
}

# Slash commands that are lightweight/meta and don't need enforcement
LIGHTWEIGHT_SLASH_COMMANDS = {
    "context-status",
    "clear-notifications",
    "obs",
    "recent",
    "constraints",
    "standards",
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
    "multi-llm": {  # Alias
        "tools": ["Bash", "Task"],
        "pattern": r"ask_cli\.py",
        "hint": "Use /ask-olymp via ask_cli.py with opencode provider",
        "intent_enabled": False,
    },
    # RCA/Truth - Python engines (v3.2: tighter pattern)
    "rca": {
        "tools": ["Bash", "Task"],
        "pattern": r"src\.rca|SimpleRCAEngine|RCAEngine|EnhancementRouter",
        "hint": "Use /rca via src.rca imports (SimpleRCAEngine, EnhancementRouter)",
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
    # File exploration skills - require Read/Glob/Grep
    "discover": {
        "tools": ["Read", "Glob", "Grep", "Bash"],
        "pattern": None,
        "hint": "Use Read, Glob, Grep, or Bash for file exploration",
        "intent_enabled": False,
    },
    "arch": {
        "tools": ["Read", "Grep", "Glob"],
        "pattern": None,
        "hint": "Use /arch via Read tool (loads templates directly, no Skill tool needed)",
        "intent_enabled": False,
    },
    # /verify - Orchestrator skill with workflow_steps (EXECUTOR-style)
    "verify": {
        "tools": ["Skill", "Bash"],
        "pattern": r"__main__\.py|verifier\.py|tier[0123]",
        "hint": "Use /verify via Skill tool + Bash (orchestrates tiers via __main__.py)",
        "intent_enabled": True,
    },
    "code": {
        "tools": ["Read", "Grep", "Glob"],
        "pattern": None,
        "hint": "Use /code via Read tool (loads templates directly, no Skill tool needed)",
        "intent_enabled": False,
    },
    "trace": {
        "tools": ["Read", "Grep", "Glob"],
        "pattern": None,
        "hint": "Use /trace via Read tool (loads templates directly, no Skill tool needed)",
        "intent_enabled": False,
    },
    "pre-mortem": {
        "tools": ["Read", "Grep", "Glob"],
        "pattern": None,
        "hint": "Use /pre-mortem via Read tool (loads templates directly, no Skill tool needed)",
        "intent_enabled": False,
    },
    "aid": {
        "tools": ["Bash"],
        "pattern": r"aid\s+|ai-distiller",
        "hint": "Use aid via ai-distiller",
        "intent_enabled": False,
    },
    # Web skills
    "crawl": {
        "tools": ["WebFetch", "Bash"],
        "pattern": None,
        "hint": "Use WebFetch or Bash for web crawling",
        "intent_enabled": False,
    },
    "research": {
        "tools": ["Bash", "Task"],
        "pattern": r"(python(\.exe)?\s+(-m\s+research\.cli|.*[\\/]research[\\/]cli\.py)|uv\s+run\s+(-m\s+)?research\.cli)",
        "hint": "Use /research via python -m research.cli (or research/cli.py)",
        "intent_enabled": False,
    },
    # Task management
    "tm": {
        "tools": ["Bash", "Task"],
        "pattern": r"tm|taskmaster",
        "hint": "Use taskmaster via Bash or Task",
        "intent_enabled": False,
    },
    # Orchestration
    "exec": {
        "tools": ["Bash", "Task"],
        "pattern": None,
        "hint": "Use exec via Bash or Task",
        "intent_enabled": False,
    },
    "flow": {
        "tools": ["Bash", "Task"],
        "pattern": None,
        "hint": "Use flow via Bash or Task",
        "intent_enabled": False,
    },
    "orchestrator": {
        "tools": ["Bash", "Task"],
        "pattern": r"orchestrat",
        "hint": "Use orchestrator via Bash or Task",
        "intent_enabled": False,
    },
    # Quality/Analysis skills - require observation tools, session activity tracker
    "q": {
        "tools": ["Read", "Grep", "Glob"],
        "pattern": r"session.*activity|wt_session|q_context",
        "hint": "Use /q via session activity tracker (WT_SESSION) as PRIMARY source, git as verification only",
        "intent_enabled": False,
    },
    "duf": {
        "tools": ["Read", "Grep", "Glob"],
        "pattern": r"pre-mortem|cognitive.*check",
        "hint": "Use /duf via session activity tracker first",
        "intent_enabled": False,
    },
    # Validation pipeline (PROCEDURE skill - sequential stages)
    "v": {
        "tools": ["Bash", "Task"],
        "pattern": r"\.claude[\\/]skills[\\/]v[\\/]scripts[\\/]stage|pylint.*delta|adversarial.*(security|performance|quality|testing)",
        "hint": "Use /v via sequential stage execution (stage1_syntax, stage2_pylint_delta, stage3_adversarial, etc.)",
        "intent_enabled": False,
    },
    "quality": {  # Alias
        "tools": ["Bash", "Task"],
        "pattern": r"\.claude[\\/]skills[\\/]v[\\/]scripts[\\/]stage|pylint.*delta|adversarial.*(security|performance|quality|testing)",
        "hint": "Use /v via sequential stage execution (stage1_syntax, stage2_pylint_delta, stage3_adversarial, etc.)",
        "intent_enabled": False,
    },
    "pipeline": {  # Alias
        "tools": ["Bash", "Task"],
        "pattern": r"\.claude[\\/]skills[\\/]v[\\/]scripts[\\/]stage|pylint.*delta|adversarial.*(security|performance|quality|testing)",
        "hint": "Use /v via sequential stage execution (stage1_syntax, stage2_pylint_delta, stage3_adversarial, etc.)",
        "intent_enabled": False,
    },
}

_SNAPSHOT_CACHE_KEY = "__skill_exec_transcript_snapshot"


def _extract_text_content(message_content: object) -> str:
    """Extract text blocks from Claude transcript message content."""
    if isinstance(message_content, list):
        return " ".join(
            block.get("text", "")
            for block in message_content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    if isinstance(message_content, str):
        return message_content
    return ""


def _extract_tool_use_content(message_content: object) -> list[dict]:
    """Extract tool use blocks from Claude transcript message content.

    Returns full tool blocks including input parameters for skill verification.
    """
    if not isinstance(message_content, list):
        return []
    tools: list[dict] = []
    for block in message_content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            name = str(block.get("name", "")).strip()
            if name:
                tools.append(block)
    return tools


def _parse_transcript_snapshot(input_data: dict) -> dict:
    """Read transcript_path once and extract the latest user/assistant data."""
    snapshot = {
        "user_prompt": "",
        "tools_used": [],
        "response_text": "",
        "transcript_path": input_data.get("transcript_path", ""),
        "transcript_read": False,
    }

    transcript_path = snapshot["transcript_path"]
    if not transcript_path:
        return snapshot

    try:
        transcript = Path(transcript_path)
        content = transcript.read_text(encoding="utf-8")  # Atomic - no TOCTOU gap
        snapshot["transcript_read"] = True

        found_user = False
        found_assistant = False
        all_tools: list[
            dict
        ] = []  # FIXED: Changed from list[str] to match _extract_tool_use_content() return type

        for line in reversed(content.strip().split("\n")):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            role = entry.get("role", "")
            msg_type = entry.get("type", "")
            message = entry.get("message", entry)
            message_content = message.get("content", entry.get("content", ""))

            is_assistant = (
                (msg_type == "message" and role == "assistant")
                or msg_type == "assistant"
                or role == "assistant"
            )
            is_user = role == "user" or (msg_type == "message" and role == "user")

            if is_assistant:
                if not found_assistant:
                    snapshot["response_text"] = _extract_text_content(message_content)
                    found_assistant = True
                # Collect tools from ALL assistant messages in this turn,
                # not just the last one.  Tool calls (e.g. Skill) appear in an
                # earlier assistant message; the final assistant message only
                # contains text.
                all_tools.extend(_extract_tool_use_content(message_content))

            elif is_user and msg_type != "system-reminder":
                # system-reminder entries have role="user" but are not real user
                # prompts — they must not trigger the break condition, otherwise
                # the reverse scan stops before reaching Skill tool_call entries.
                text = _extract_text_content(message_content).strip()
                if text:
                    # Real user prompt (not a tool_result whose role happens to
                    # be "user").  This marks the start of the current turn.
                    snapshot["user_prompt"] = text
                    found_user = True
                # tool_result user messages have no text — keep scanning
                # backwards so we reach the assistant tool_use messages.
                if found_user and found_assistant:
                    break

        snapshot["tools_used"] = all_tools

    except Exception as e:
        log(f"Error reading transcript snapshot: {e}")

    return snapshot


def _get_transcript_snapshot(input_data: dict) -> dict:
    """Return cached transcript snapshot for this Stop invocation."""
    cached = input_data.get(_SNAPSHOT_CACHE_KEY)
    if isinstance(cached, dict):
        return cached

    snapshot = _parse_transcript_snapshot(input_data)
    input_data[_SNAPSHOT_CACHE_KEY] = snapshot
    return snapshot


def extract_user_prompt(input_data: dict) -> str:
    """Extract the user's LAST prompt from transcript_path.

    Reads the JSONL transcript to find the most recent user message.
    This is used to detect if the user typed a slash command that
    the assistant then ignored without invoking the Skill tool.
    """
    direct_prompt = (
        input_data.get("user_prompt") or input_data.get("prompt") or input_data.get("message") or ""
    )
    if str(direct_prompt).strip():
        return str(direct_prompt).strip()
    return str(_get_transcript_snapshot(input_data).get("user_prompt", "")).strip()


def _extract_slash_command(prompt: str) -> str | None:
    """Extract slash command name from prompt.

    Returns the command name (e.g., 'debugRCA') or None if not a slash command.
    """
    match = re.match(r"^/([a-zA-Z][\w-]*)", prompt.strip())
    if match:
        return match.group(1)
    return None


def log(msg: str) -> None:
    """Debug logging."""
    if DEBUG:
        try:
            DEBUG_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[skill_exec_gate] {msg}\n")
        except OSError:
            pass


def log_event(event: str, data: dict) -> None:
    """Log structured event for analysis using atomic rename.

    Write to .tmp in same directory, flush+fsync, rename over original.
    This prevents JSONL corruption on crash-mid-write in multi-terminal scenarios.
    """
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        entry = {"timestamp": time.time(), "event": event, **data}
        line = json.dumps(entry) + "\n"

        # Atomic rename: write to .tmp, flush+sync, rename over original
        # .tmp in same directory = same filesystem = atomic rename on NTFS
        tmp_file = LOG_FILE.parent / f"{LOG_FILE.stem}.{os.getpid()}.tmp"
        with tmp_file.open("w", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        tmp_file.replace(LOG_FILE)
    except Exception:
        pass


# =============================================================================
# LAYER 1: MARKER-BASED GOVERNANCE
# =============================================================================


def _get_governance_state_file() -> Path:
    """Get governance state file path for this terminal."""
    terminal_id = ""
    try:
        from __lib.terminal_detection import detect_terminal_id

        terminal_id = detect_terminal_id()
    except ImportError:
        terminal_id = os.environ.get("CLAUDE_TERMINAL_ID", "")
    if not terminal_id:
        terminal_id = "unknown"
    state_dir = STATE_DIR / f"skill_execution_{terminal_id}"
    return state_dir / "skill_governance_state.json"


def _read_governance_state() -> dict | None:
    """Read governance state written by the router."""
    gov_file = _get_governance_state_file()
    if not gov_file.exists():
        return None
    try:
        state = json.loads(gov_file.read_text(encoding="utf-8"))
        # Stale check
        if time.time() - state.get("loaded_at", 0) > STALE_TIMEOUT:
            log("Stale governance state, clearing")
            gov_file.unlink(missing_ok=True)
            return None
        return state
    except (json.JSONDecodeError, OSError) as e:
        log(f"Error reading governance state: {e}")
        return None


def _update_governance_retry(state: dict) -> None:
    """Increment retry_count in governance state."""
    try:
        state["retry_count"] = state.get("retry_count", 0) + 1
        gov_file = _get_governance_state_file()
        gov_file.write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        pass


def _clear_governance_state() -> None:
    """Remove governance state file."""
    try:
        gov_file = _get_governance_state_file()
        gov_file.unlink(missing_ok=True)
    except Exception:
        pass


def _normalize_tool_names(items: list) -> list[str]:
    """Extract plain tool names from mixed list of strings or tool_use dicts.

    Claude transcript stores tool_use blocks as full dicts:
      {"type": "tool_use", "name": "Skill", ...}
    or as plain strings: "Skill".
    str() on a dict produces '{"type": "tool_use", "name": "Skill", ...}'
    which would incorrectly pass "Skill" membership checks.

    Returns list of plain tool name strings, e.g. ["Skill", "Bash"].
    """
    names: list[str] = []
    for item in items:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("name", "")).strip()
        else:
            name = ""
        if name:
            names.append(name)
    return names


def extract_tools_used(input_data: dict) -> list[str]:
    """Extract tool names used in the current assistant response.

    Returns a list of tool names (e.g., ["Edit", "Read", "Skill"]) from the
    most recent assistant message.

    Claude Code provides a transcript_path pointing to a JSONL file.
    The last assistant entry contains content blocks with type "tool_use".
    """
    supplied_tools = input_data.get("tools_used", [])
    if isinstance(supplied_tools, list) and supplied_tools:
        return _normalize_tool_names(supplied_tools)

    snapshot = _get_transcript_snapshot(input_data)
    tools_used = snapshot.get("tools_used", [])
    if isinstance(tools_used, list):
        return _normalize_tool_names(tools_used)
    return []


def extract_response_text(input_data: dict) -> str:
    """Extract assistant response text from Stop hook input.

    Claude Code provides a transcript_path pointing to a JSONL file.
    The last assistant entry contains the response in:
      {"type": "message", "role": "assistant", "message": {"content": [{"type": "text", "text": "..."}]}}
    """
    response = ""

    response = str(_get_transcript_snapshot(input_data).get("response_text", ""))

    # Fallback: conversation/messages array in stdin data
    if not response:
        conversation = input_data.get("conversation", []) or input_data.get("messages", [])
        if isinstance(conversation, list):
            for msg in reversed(conversation):
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        response = " ".join(
                            b.get("text", "")
                            for b in content
                            if isinstance(b, dict) and b.get("type") == "text"
                        )
                    else:
                        response = str(content)
                    break

    # Fallback: direct fields
    if not response:
        response = input_data.get("response", "") or input_data.get("assistant_response", "")

    return str(response)


def _check_governance_markers(input_data: dict) -> dict:
    """Layer 1 marker-based governance check.

    Returns:
        {"allow": True/False, "reason": "..."} or empty dict if no governance active.
    """
    gov_state = input_data.get("governance") or _read_governance_state()
    if not gov_state:
        return {}  # No governance active

    skill = gov_state.get("skill", "unknown")
    markers = gov_state.get("markers", [])
    retry_count = int(gov_state.get("retry_count", 0) or 0)

    if not markers:
        if input_data.get("governance") is None:
            _clear_governance_state()
        return {}

    # Extract response text
    response = extract_response_text(input_data)
    log(f"Governance check for /{skill}: response length={len(response)}, markers={markers[:3]}")

    # Missing/empty response data is a transport issue, not proof of bypass.
    # Fail open and clear state to avoid retry loops on partial transcript writes.
    if not response.strip():
        log(f"Governance skipped for /{skill}: missing assistant response text")
        log_event(
            "governance_skipped_missing_response",
            {
                "skill": skill,
                "retry_count": retry_count,
            },
        )
        if input_data.get("governance") is None:
            _clear_governance_state()
        return {"allow": True, "reason": "missing_response_data"}

    # Check markers (case-insensitive substring)
    response_lower = response.lower()
    found = [m for m in markers if m.lower() in response_lower]

    if found:
        log(f"Governance PASS for /{skill}: found markers {found[:3]}")
        log_event("governance_pass", {"skill": skill, "found_markers": found})
        if input_data.get("governance") is None:
            _clear_governance_state()
        return {"allow": True, "reason": f"skill_markers_present: {found[:3]}"}

    # VIOLATION: no markers found
    log(f"Governance VIOLATION for /{skill}: no markers in {len(response)} chars")
    log_event(
        "governance_violation",
        {
            "skill": skill,
            "expected_markers": markers[:5],
            "retry_count": retry_count,
            "response_length": len(response),
        },
    )

    if input_data.get("governance") is None and retry_count == 0:
        _update_governance_retry(gov_state)
        return {
            "allow": False,
            "reason": (
                f"SKILL BYPASSED - RETRY REQUIRED\n\n"
                f"You invoked /{skill} but your response doesn't follow the skill workflow.\n\n"
                f"Expected: Response should contain skill markers like:\n"
                + "\n".join(f'  - "{m}"' for m in markers[:5])
                + f"\n\nActual: None of these markers were found in your response.\n\n"
                f"Follow the /{skill} skill instructions that were injected.\n"
                f"This is attempt 1/2. Next bypass will be blocked."
            ),
        }

    if input_data.get("governance") is None:
        _clear_governance_state()
    return {
        "allow": False,
        "reason": (
            f"SKILL GOVERNANCE FAILURE\n\n"
            f"/{skill} was invoked but the response did not follow the skill workflow.\n\n"
            f"Required markers: {markers[:5]}\n"
            f"Found: None\n\n"
            f"You MUST follow the skill's workflow. Re-read the skill instructions."
        ),
    }


# =============================================================================
# TOOL-BASED STATE MANAGEMENT (v3.2 legacy)
# =============================================================================


def _get_state_file() -> Path:
    """Get the state file path for this terminal."""
    try:
        from skill_execution_state import _get_state_file

        return _get_state_file()
    except ImportError:
        # Fallback to generic location
        return STATE_DIR / "skill_execution_pending.json"


def _read_state() -> dict | None:
    """Read current skill execution state."""
    state_file = _get_state_file()
    if not state_file.exists():
        return None

    try:
        return json.loads(state_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _clear_state() -> None:
    """Clear the current skill execution state."""
    state_file = _get_state_file()
    state_file.unlink(missing_ok=True)


# =============================================================================
# VALIDATION
# =============================================================================


def _is_stale(state: dict) -> bool:
    """Check if state is stale (older than STALE_TIMEOUT)."""
    loaded_at = state.get("loaded_at", 0)
    return (time.time() - loaded_at) > STALE_TIMEOUT


def _check_pattern_match(command: str, pattern: str) -> bool:
    """Check if command matches the required pattern."""
    if not pattern:
        return True  # No pattern requirement

    try:
        return bool(re.search(pattern, command, re.IGNORECASE))
    except re.error:
        return False


def validate_execution(state: dict, tool_history: list) -> dict:
    """Validate that skill was properly executed.

    Args:
        state: Skill execution state from state file
        tool_history: List of tools used in this session

    Returns:
        Dict with "satisfied" (bool) and "reason" (str)
    """
    skill = state.get("skill", "")

    # Check if stale
    if _is_stale(state):
        log_event("stale_state", {"skill": skill})
        return {
            "satisfied": True,  # Don't block on stale state
            "reason": f"State for '{skill}' is stale ({STALE_TIMEOUT}s timeout)",
        }

    # Get required tools
    required_tools = state.get("required_tools", [])
    if not required_tools:
        # No tool requirement, consider satisfied
        return {"satisfied": True, "reason": ""}

    # Check if any required tool was used
    tools_used = state.get("tools_used", [])
    execution_tool_used = any(t in required_tools for t in tools_used)

    if not execution_tool_used:
        # No execution tool used - violation
        # v3.2: This is a LATE violation (PreToolUse should have blocked)
        hint = state.get("hint", f"Use /{skill} via its designated execution mechanism")
        reason = (
            f"⚠️ LATE VIOLATION DETECTED: /{skill} execution not satisfied.\n"
            f"💡 {hint}\n"
            f"🔧 PreToolUse hook should have blocked this - check hook status.\n"
            f"📋 Required tools: {', '.join(required_tools)}\n"
            f"📋 Tools used: {', '.join(tools_used) if tools_used else 'None'}"
        )
        log_event(
            "late_violation",
            {
                "skill": skill,
                "required_tools": required_tools,
                "tools_used": tools_used,
            },
        )
        return {"satisfied": False, "reason": reason}

    # Check pattern match for commands
    pattern = state.get("pattern", "")
    if pattern:
        commands_run = state.get("commands_run", [])
        pattern_matched = any(_check_pattern_match(cmd, pattern) for cmd in commands_run)

        if not pattern_matched:
            hint = state.get("hint", f"Use /{skill} with correct command pattern")
            reason = (
                f"⚠️ LATE VIOLATION DETECTED: /{skill} command pattern not matched.\n"
                f"💡 {hint}\n"
                f"🔧 PreToolUse hook should have blocked this - check hook status.\n"
                f"📋 Pattern: {pattern}\n"
                f"📋 Commands run: {commands_run[:3]}"
            )
            log_event(
                "late_violation_pattern",
                {
                    "skill": skill,
                    "pattern": pattern,
                    "commands": commands_run,
                },
            )
            return {"satisfied": False, "reason": reason}

    return {"satisfied": True, "reason": ""}


def run(input_data: dict) -> dict | None:
    """In-process validator protocol for Stop_router."""
    if not ENABLED:
        return None

    tools_used_this_turn = extract_tools_used(input_data)
    user_prompt = extract_user_prompt(input_data)
    slash_cmd = _extract_slash_command(user_prompt) if user_prompt else None

    # Resolve active turn ID: prefer input_data, fall back to ledger
    terminal_id = _get_terminal_id(input_data)
    active_turn_id = _get_active_turn_id(terminal_id)

    router_snapshot_active = (
        input_data.get("skill_state") is not None
        or input_data.get("governance") is not None
        or bool(input_data.get("turn_id"))
    )

    # R1 Consumer: Surface frontmatter_warnings from skill_loaded event.
    # This reads the warning written by set_skill_loaded() in skill_execution_state.
    # Advisory-only: warnings are displayed but do not block execution.
    if LEDGER_AVAILABLE and terminal_id and active_turn_id:
        try:
            from __lib.hook_ledger import _load_db_skill_events

            _skill_events = _load_db_skill_events(str(terminal_id))
            # Find the skill_loaded event for the current turn
            for _event in reversed(_skill_events):  # Most recent first
                _payload = _event.get("payload", {})
                if (
                    _payload.get("turn_id") == str(active_turn_id)
                    and _event.get("event_type") == "skill_loaded"
                ):
                    _warnings = _payload.get("frontmatter_warnings", [])
                    if _warnings:
                        _skill_name = _payload.get("skill", "unknown")
                        _warn_lines = "\n  ".join(f"* {w}" for w in _warnings)
                        log(
                            f"FRONTMATTER WARNINGS for /{_skill_name}: "
                            f"{_warnings} (advisory, non-blocking)"
                        )
                        return {
                            "block": False,
                            "reason": (
                                f"\n⚠️ SKILL FRONTMATTER ADVISORY: /{_skill_name}\n"
                                f"  {_warn_lines}\n"
                                f"Fix: Add missing fields to "
                                f"P:/.claude/skills/{_skill_name}/SKILL.md\n"
                            ),
                        }
                    break  # Found the event for this turn, no need to check older events
        except Exception:
            pass  # Ledger read failure — fail open, don't block

    # Stateless per-turn check: If slash command was used, verify Skill tool was called
    # AND that the model actually executed something afterwards.
    #
    # Calling Skill() is NECESSARY but not SUFFICIENT. The model must also:
    #   a) Use at least one execution tool (Bash, Task, Read, Grep, Glob, Write, Edit…), OR
    #   b) Be responding to a legitimate prose-only request (help flags: --list/--help/-h)
    #
    # This is the systemic fix for the "prose bypass" pattern: model calls Skill(), reads
    # the content, then responds with its own analysis instead of running the workflow.
    # Works for ALL skills regardless of whether they declare workflow_steps.
    _EXECUTION_TOOLS = {
        "Bash",
        "Task",
        "Read",
        "Grep",
        "Glob",
        "Write",
        "Edit",
        "MultiEdit",
        "WebFetch",
        "WebSearch",
    }
    _HELP_FLAGS = frozenset({"--list", "--help", "-h", "--flags", "--usage"})

    def _is_help_only_request(prompt: str) -> bool:
        """True when the user's args are exclusively help flags — prose is the correct response."""
        import re as _re

        m = _re.match(r"^/[a-z0-9-]+\s+(.*)", (prompt or "").strip(), _re.IGNORECASE)
        if not m:
            return False
        tokens = set(m.group(1).strip().split())
        return bool(tokens) and tokens.issubset(_HELP_FLAGS)

    if (
        slash_cmd
        and slash_cmd not in BUILTIN_SLASH_COMMANDS
        and slash_cmd not in LIGHTWEIGHT_SLASH_COMMANDS
        and slash_cmd not in KNOWLEDGE_SKILLS
    ):
        if "Skill" in tools_used_this_turn:
            execution_tools_after_skill = _EXECUTION_TOOLS.intersection(tools_used_this_turn)
            help_request = _is_help_only_request(user_prompt or "")

            if execution_tools_after_skill or help_request:
                log(
                    f"Slash command /{slash_cmd} executed via Skill tool - allowing stop "
                    f"(execution_tools={execution_tools_after_skill}, help_request={help_request})"
                )
                if not router_snapshot_active:
                    _clear_governance_state()
                return None

            # Skill() was called but no execution tools used and not a help request.
            # This is the "prose bypass" pattern: model read the skill and responded with text.
            log(
                f"PROSE BYPASS: /{slash_cmd} - Skill() called but no execution tools used. "
                f"Tools: {tools_used_this_turn}"
            )
            log_event(
                "prose_bypass_after_skill",
                {
                    "skill": slash_cmd,
                    "tools_used": tools_used_this_turn,
                    "user_prompt": (user_prompt or "")[:200],
                },
            )
            if not router_snapshot_active:
                _clear_governance_state()
            return {
                "block": True,
                "reason": (
                    f"SKILL WORKFLOW NOT EXECUTED\n\n"
                    f'You called Skill("{slash_cmd}") but then responded with prose instead of '
                    f"executing the skill's workflow.\n\n"
                    f"After loading a skill you MUST execute its workflow using tools "
                    f"(Bash, Task, Read, etc.).\n\n"
                    f"Re-read the skill's Execution section and run it now."
                ),
            }

        # Skill was not called. Check if the hook system itself blocked all attempts
        # (system failure) before blaming the model (genuine violation).
        _all_blocked = False
        if LEDGER_AVAILABLE and active_turn_id:
            try:
                from __lib.hook_ledger import _load_db_events

                _events = _load_db_events(str(active_turn_id))
                _invoked = [e for e in _events if e.get("event_type") == "tool_invoked"]
                _blocked = [e for e in _events if e.get("event_type") == "tool_blocked"]
                _all_blocked = len(_invoked) > 0 and len(_blocked) == len(_invoked)
            except Exception:
                _all_blocked = False

        if _all_blocked:
            log(f"Hook system blocked all tool attempts for /{slash_cmd} - suppressing stop block")
            log_event(
                "hook_system_blocked_all_tools",
                {
                    "skill": slash_cmd,
                    "invoked": len(_invoked),
                    "blocked": len(_blocked),
                },
            )
            if not router_snapshot_active:
                _clear_governance_state()
            return None

        # TRANSCRIPT PARSE FAILURE FALLBACK: If transcript parse returned empty
        # tools_used (e.g. transcript not flushed, system-reminder broke reverse-scan,
        # or post-compact transcript is empty), check the ledger for a skill_loaded
        # event from this terminal. This survives compaction because the ledger is
        # SQLite on disk.
        if not tools_used_this_turn and LEDGER_AVAILABLE and terminal_id:
            try:
                from __lib.hook_ledger import _load_db_skill_events

                _skill_events = _load_db_skill_events(str(terminal_id))
                _skill_confirmed = any(
                    e.get("payload", {}).get("skill", "").lower() == slash_cmd.lower()
                    for e in _skill_events
                )
                if _skill_confirmed:
                    log(
                        f"Slash command /{slash_cmd} confirmed via ledger skill_loaded event "
                        f"(transcript parse found no tools — likely post-compact transcript gap). "
                        f"Allowing stop."
                    )
                    log_event(
                        "skill_confirmed_via_ledger",
                        {
                            "skill": slash_cmd,
                            "transcript_tools": tools_used_this_turn,
                            "event_count": len(_skill_events),
                        },
                    )
                    if not router_snapshot_active:
                        _clear_governance_state()
                    return None
            except Exception:
                pass  # Ledger fallback — fail open

        # Slash command invoked but Skill tool never called.
        # Advisory-only: warn but allow the response through to avoid dead-end blocks.
        log(f"SLASH COMMAND ADVISORY: /{slash_cmd} - tools used: {tools_used_this_turn}")
        log_event(
            "slash_command_ignored",
            {
                "skill": slash_cmd,
                "user_prompt": (user_prompt or "")[:200],
                "tools_used": tools_used_this_turn,
                "enforcement": "advisory",
            },
        )
        if not router_snapshot_active:
            _clear_governance_state()
        return {
            "block": False,
            "reason": (
                f"\n⚠️ SLASH COMMAND REMINDER: /{slash_cmd} was not executed via Skill tool.\n"
                f'Next time, call Skill("{slash_cmd}") as your first action.\n'
            ),
        }

    # Continue with remaining checks (non-slash-command path)

    if not tools_used_this_turn:
        if (
            slash_cmd
            and slash_cmd not in BUILTIN_SLASH_COMMANDS
            and slash_cmd not in LIGHTWEIGHT_SLASH_COMMANDS
            and slash_cmd not in KNOWLEDGE_SKILLS
        ):
            # Check if the hook system itself blocked all tool attempts this turn.
            # Distinguishes: Claude bypassed (genuine violation) vs hooks blocked everything (system failure).
            if LEDGER_AVAILABLE and slash_cmd and active_turn_id:
                try:
                    from __lib.hook_ledger import _load_db_events

                    _events = _load_db_events(str(active_turn_id))
                    _invoked = [e for e in _events if e.get("event_type") == "tool_invoked"]
                    _blocked = [e for e in _events if e.get("event_type") == "tool_blocked"]
                    _all_blocked = len(_invoked) > 0 and len(_blocked) == len(_invoked)
                except Exception:
                    _all_blocked = False

                if _all_blocked:
                    # Don't shame the LLM — the hook system blocked every attempt
                    log_event(
                        "hook_system_blocked_all_tools",
                        {
                            "skill": slash_cmd,
                            "invoked": len(_invoked),
                            "blocked": len(_blocked),
                        },
                    )
                    if not router_snapshot_active:
                        _clear_governance_state()
                    return None  # Allow stop without blocking

            log(
                f"SLASH COMMAND BYPASS (no tools): user typed /{slash_cmd} but assistant used NO tools at all"
            )
            log_event(
                "slash_command_bypass_no_tools",
                {
                    "skill": slash_cmd,
                    "user_prompt": user_prompt[:200],
                },
            )
            if not router_snapshot_active:
                _clear_governance_state()
            return {
                "block": False,
                "reason": (
                    f"\n⚠️ SLASH COMMAND REMINDER: /{slash_cmd} was not executed.\n"
                    f"You responded with prose without using any tools.\n"
                    f'Next time, call Skill("{slash_cmd}") first, then follow its workflow.\n'
                ),
            }

        if not router_snapshot_active:
            _clear_governance_state()
        return None

    if "Skill" not in tools_used_this_turn:
        if (
            slash_cmd
            and slash_cmd not in BUILTIN_SLASH_COMMANDS
            and slash_cmd not in LIGHTWEIGHT_SLASH_COMMANDS
            and slash_cmd not in KNOWLEDGE_SKILLS
        ):
            execution_tools_used = {
                tool_name
                for tool_name in tools_used_this_turn
                if tool_name
                in (
                    "Bash",
                    "Task",
                    "Read",
                    "Grep",
                    "Glob",
                    "Write",
                    "Edit",
                    "WebFetch",
                    "WebSearch",
                )
            }

            if not execution_tools_used:
                log(
                    f"SLASH COMMAND BYPASS: user typed /{slash_cmd} but assistant used no execution tools. "
                    f"Tools: {tools_used_this_turn}"
                )
                log_event(
                    "slash_command_bypass",
                    {
                        "skill": slash_cmd,
                        "user_prompt": user_prompt[:200],
                        "tools_used": tools_used_this_turn,
                    },
                )
                if not router_snapshot_active:
                    _clear_governance_state()
                return {
                    "block": False,
                    "reason": (
                        f"\n⚠️ SLASH COMMAND REMINDER: /{slash_cmd} was not executed via Skill tool.\n"
                        f"Tools used ({', '.join(tools_used_this_turn)}) did not include Skill.\n"
                        f"Next time, call Skill(\"{slash_cmd}\") first, then follow its workflow.\n"
                    ),
                }

        if not router_snapshot_active:
            _clear_governance_state()
        log(f"Skipping governance: Skill tool not used. Tools used: {tools_used_this_turn}")
        return None

    gov_result = _check_governance_markers(input_data)
    if gov_result and not gov_result.get("allow", True):
        return {"block": True, "reason": gov_result["reason"]}

    # Mid-sentence slash: if prompt doesn't start with /, don't block. Let the LLM
    # use semantic judgment to determine if it's an invocation or mention.
    if user_prompt and not user_prompt.strip().startswith("/"):
        return None

    state = input_data.get("skill_state") or _read_state()
    if not isinstance(state, dict):
        return None

    skill = state.get("skill", "")
    if skill in KNOWLEDGE_SKILLS:
        if input_data.get("skill_state") is None:
            _clear_state()
        return None

    result = validate_execution(state, [])
    if input_data.get("skill_state") is None:
        _clear_state()

    if result["satisfied"]:
        return None
    return {"block": True, "reason": result["reason"]}


# =============================================================================
# VERIFICATION REMINDER (TASK-004)
# =============================================================================


def check_verification_reminder(steps: dict | None) -> dict[str, bool | str | None]:
    """
    Check if verification steps are incomplete and return reminder.

    This is a warn-only function that never blocks execution. It filters
    verification steps from the breadcrumb trail and returns a reminder
    message if any are incomplete.

    Args:
        steps: Steps dict from breadcrumb trail. Can be None or non-dict.

    Returns:
        {"allow": True, "reminder": None} if no pending verifications
        {"allow": True, "reminder": "..."} if pending verifications exist

    Behavior:
        - Filters steps by kind=verification and status!=done
        - Always returns allow=True (warn-only, never blocks)
        - Handles malformed input gracefully (None, non-dict, missing fields)
        - Recognizes optional steps: audit_quality_checks,
          trace_manual_verification, done_final_certification

    Examples:
        >>> steps = {"step1": {"kind": "verification", "status": "pending"}}
        >>> result = check_verification_reminder(steps)
        >>> result["allow"]
        True
        >>> "verification" in result["reminder"].lower()
        True
    """
    # Handle None or non-dict input gracefully
    if not isinstance(steps, dict):
        return {"allow": True, "reminder": None}

    # Filter verification steps with status != done
    pending_verification_steps = []
    for step_id, step in steps.items():
        if not isinstance(step, dict):
            continue
        kind = step.get("kind", "")
        status = step.get("status", "")
        if kind == "verification" and status != "done":
            pending_verification_steps.append(step_id)

    # If no pending verification steps, return allow with no reminder
    if not pending_verification_steps:
        return {"allow": True, "reminder": None}

    # Build reminder message with both readable name and original step_id
    reminder = (
        "⚠️ PENDING VERIFICATION STEPS\n\nThe following verification steps are not yet complete:\n"
    )
    for step_id in pending_verification_steps:
        step_name = step_id.replace("_", " ").title()
        reminder += f"  • {step_name} ({step_id})\n"
    reminder += "\nPlease complete these verification steps before finishing."

    return {"allow": True, "reminder": reminder}


# =============================================================================
# STOP HANDLER
# =============================================================================


@hook_main
def main():
    """Main entry point - reads stdin and delegates to run()."""
    try:
        input_text = sys.stdin.read().strip()
        input_data = json.loads(input_text) if input_text else {}
    except (json.JSONDecodeError, Exception):
        input_data = {}
    result = run(input_data)
    if result and result.get("block"):
        print(json.dumps({"decision": "block", "reason": result["reason"]}))
        return
    print(json.dumps({}))


if __name__ == "__main__":
    main()
