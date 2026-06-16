"""Skill enforcement logic for skill-guard.

Authoritative source for slash command enforcement: detection, blocking decisions,
context building, and state management for the skill-first execution model.

The hook registration shim at:
  .claude/hooks/UserPromptSubmit_modules/skill_enforcer.py
imports from here and registers the hook function using the local HookContext/HookResult system.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Path resolution (env-based, not __file__-based)
# ---------------------------------------------------------------------------


def _hooks_dir() -> Path:
    project_root = Path(os.environ.get("CLAUDE_PROJECT_DIR", "P:/"))
    return project_root / ".claude" / "hooks"


def _intent_state_dir() -> Path:
    return _hooks_dir() / "state"


def _session_data_dir() -> Path:
    return _hooks_dir() / "session_data"


def _fallback_state_dir() -> Path:
    return Path(tempfile.gettempdir()) / "claude_hooks" / "state"


def _fallback_session_data_dir() -> Path:
    return Path(tempfile.gettempdir()) / "claude_hooks" / "session_data"


def _hook_health_report() -> Path:
    return _hooks_dir() / "logs" / "diagnostics" / "hook_health.json"


def _fallback_hook_health_report() -> Path:
    return Path(tempfile.gettempdir()) / "claude_hooks" / "hook_health.json"


# ---------------------------------------------------------------------------
# TTL utilities — optional, fail-open
# ---------------------------------------------------------------------------

def _write_monotonic_ts_default() -> float:
    return time.time()


def _sanitize_future_ts_default(ts: float) -> float:
    return min(ts, time.time() + 60)


try:
    _hooks_lib = _hooks_dir() / "__lib"
    if _hooks_lib.exists() and str(_hooks_lib) not in sys.path:
        sys.path.insert(0, str(_hooks_lib))
    from ttl_utils import write_monotonic_ts as _write_monotonic_ts
    from ttl_utils import sanitize_future_ts as _sanitize_future_ts
except ImportError:
    _write_monotonic_ts = _write_monotonic_ts_default  # type: ignore[assignment]
    _sanitize_future_ts = _sanitize_future_ts_default  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Imports from slash_command_observability (single source of truth)
# ---------------------------------------------------------------------------

import re as _re

from skill_guard.slash_command_observability import (
    BUILTIN_SLASH_COMMANDS,
    extract_slash_command,
    extract_command_name,
    is_slash_prompt,
)

# ---------------------------------------------------------------------------
# Topic-inquiry detection (self-contained — no local imports needed)
# ---------------------------------------------------------------------------

_TOPIC_INQUIRY_PATTERNS: tuple[_re.Pattern[str], ...] = (
    _re.compile(r"tell me about\s+/\S+", _re.IGNORECASE),
    _re.compile(r"explain\s+/\S+", _re.IGNORECASE),
    _re.compile(r"describe\s+/\S+", _re.IGNORECASE),
    _re.compile(r"what is\s+/\S+", _re.IGNORECASE),
    _re.compile(r"find information about\s+/\S+", _re.IGNORECASE),
    _re.compile(r"search for\s+/\S+", _re.IGNORECASE),
    _re.compile(r"about\s+/\S+", _re.IGNORECASE),
    _re.compile(r"regarding\s+/\S+", _re.IGNORECASE),
    _re.compile(r"concerning\s+/\S+", _re.IGNORECASE),
    _re.compile(r"/\S+\s+usage", _re.IGNORECASE),
    _re.compile(r"usage of\s+/\S+", _re.IGNORECASE),
    _re.compile(r"errors?.*\s+regarding\s+/\S+", _re.IGNORECASE),
    _re.compile(r"errors?.*\s+about\s+/\S+", _re.IGNORECASE),
)


def is_topic_inquiry(prompt: str | None) -> bool:
    """Return True when prompt asks ABOUT a slash command rather than invoking it."""
    if not prompt:
        return False
    return any(p.search(prompt) for p in _TOPIC_INQUIRY_PATTERNS)

# COMMAND_BLOCKLIST is BUILTIN_SLASH_COMMANDS — the authoritative set.
# Do not maintain a separate hardcoded list here.
COMMAND_BLOCKLIST = BUILTIN_SLASH_COMMANDS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SLASH_EXECUTION_LANE = """
INSTRUCTION: Execute skill {command}

Step 1: Call Skill("{command}") to load workflow  ← YOUR FIRST ACTION, no exceptions
Step 2: Follow the skill's documented procedure exactly

Do NOT use Bash, Read, Glob, Grep, or any other tool before Skill() is called.
Path validation, directory checks, and orientation all happen INSIDE the skill, after loading.
Do NOT substitute your own analysis or improvise.
""".strip()

# Plugin (colon-namespaced) slash commands AUTO-LOAD their SKILL.md — the CLI
# injects the full skill content as a user turn when /plugin:skill is typed. So
# the "call Skill() first / do not use Bash" contract above is both redundant and
# harmful: it forbids the one action the model needs (executing), which makes the
# model write its tool calls as prose and stall. For plugin commands, tell it the
# skill is loaded and to execute the workflow directly by INVOKING tools.
PLUGIN_SLASH_EXECUTION_LANE = """
INSTRUCTION: Execute skill {command}

The skill's SKILL.md is ALREADY LOADED in this turn (the slash command injected it
above). You do NOT need to call the Skill tool — it is redundant here.

Execute the skill's documented workflow NOW by actually INVOKING tools (Bash, Read,
Write, etc.) as the skill directs. Do NOT write tool calls as prose and stop. Do NOT
substitute your own analysis or improvise.
""".strip()

HELP_REQUEST_LANE = """
The user passed a help flag ({flag}). After calling Skill("{command}"):
- Look for a flags/options/usage section in the skill's documentation.
- Display that section as a formatted list. This is a valid prose-only response.
- Do NOT run the skill's main execution script.
""".strip()

_HELP_FLAGS = frozenset({"--list", "--help", "-h", "--flags", "--usage"})

ENFORCEMENT_CONFIG_FILE = "config/skill_enforcement.json"

DEFAULT_ENFORCEMENT_CONFIG: dict = {
    "mode": "all",
    "ignored_commands": [],
    "enforced_skills": [],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value)


def _prompt_fingerprint(prompt: str) -> str:
    text = (prompt or "").strip()
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _is_help_request(args: str) -> bool:
    tokens = set(args.strip().split()) if args else set()
    return bool(tokens) and tokens.issubset(_HELP_FLAGS)


def _load_enforcement_config() -> dict:
    config = dict(DEFAULT_ENFORCEMENT_CONFIG)
    config_file = _hooks_dir() / ENFORCEMENT_CONFIG_FILE
    try:
        if config_file.exists():
            data = json.loads(config_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                config.update(data)
    except Exception:
        pass
    return config


def _health_report_paths() -> list[Path]:
    override = os.environ.get("HOOK_HEALTH_REPORT_PATH", "").strip()
    if override:
        return [Path(override)]
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return [_fallback_hook_health_report()]
    return [_hook_health_report(), _fallback_hook_health_report()]


# ---------------------------------------------------------------------------
# Command detection (delegates to slash_command_observability)
# ---------------------------------------------------------------------------


def is_command_directive(prompt: str) -> bool:
    """Return True if prompt is a slash command invocation.

    Note: topic-inquiry filtering (e.g. "tell me about /s") is applied
    by the calling shim via is_topic_inquiry before this function is called.
    """
    return is_slash_prompt(prompt)


# extract_command_name and extract_slash_command re-exported from slash_command_observability.

# ---------------------------------------------------------------------------
# Skill discovery
# ---------------------------------------------------------------------------


def _skill_exists(command: str) -> bool:
    """Return True if a SKILL.md exists for this command in any skill directory."""
    cmd = command.lower()
    # Namespaced command: plugin:skill-name — search the matching plugin only
    if ":" in cmd:
        plugin_name, skill_name = cmd.split(":", 1)
    else:
        plugin_name, skill_name = None, cmd

    candidates: list[Path] = []
    hooks = _hooks_dir()

    project_skills = hooks.parent / "skills"
    if project_skills.is_dir():
        candidates.append(project_skills / skill_name / "SKILL.md")

    user_skills = Path.home() / ".claude" / "skills"
    if user_skills.is_dir():
        candidates.append(user_skills / skill_name / "SKILL.md")

    plugin_cache = Path.home() / ".claude" / "plugins" / "cache"
    if plugin_cache.is_dir():
        for marketplace_dir in plugin_cache.iterdir():
            if not marketplace_dir.is_dir():
                continue
            for plugin_dir in marketplace_dir.iterdir():
                if not plugin_dir.is_dir():
                    continue
                if plugin_name and plugin_dir.name.lower() != plugin_name:
                    continue
                for version_dir in plugin_dir.iterdir():
                    candidates.append(version_dir / "skills" / skill_name / "SKILL.md")

    return any(p.is_file() for p in candidates)


# ---------------------------------------------------------------------------
# Enforcement decision
# ---------------------------------------------------------------------------


def should_block_command(command: str) -> bool:
    """Return True if this command should bypass skill-first enforcement.

    A command is blocked (i.e. passes through to the CLI unchanged) when:
    1. It is a known Claude Code built-in (BUILTIN_SLASH_COMMANDS).
    2. It appears in the project-level ignored_commands config.
    3. Allowlist mode is active and the command is not in the allowlist.
    4. No SKILL.md exists for the command (dynamic built-in detection).
    """
    cmd = command.lower()

    if cmd in BUILTIN_SLASH_COMMANDS:
        return True

    config = _load_enforcement_config()
    ignored = {
        str(x).strip().lower()
        for x in config.get("ignored_commands", [])
        if str(x).strip()
    }
    if cmd in ignored:
        return True

    mode = str(config.get("mode", "all")).strip().lower()
    if mode == "allowlist":
        allowlist = {
            str(x).strip().lower()
            for x in config.get("enforced_skills", [])
            if str(x).strip()
        }
        return cmd not in allowlist

    if not _skill_exists(cmd):
        return True

    return False


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------


def log_command_intent_telemetry(
    terminal_id: str, session_id: str, prompt: str, command: str
) -> None:
    """Write command intent state file (telemetry only, not used for gate enforcement)."""
    if not terminal_id:
        return

    safe_terminal = _safe_id(terminal_id)
    payload = {
        "skill": command,
        "prompt": prompt,
        "prompt_fingerprint": _prompt_fingerprint(prompt),
        "timestamp": datetime.now().isoformat(),
        "created_at": _sanitize_future_ts(_write_monotonic_ts()),
        "session_id": session_id,
        "terminal_id": terminal_id,
        "skill_loaded": False,
        "execution_tools_used": False,
        "satisfied": False,
    }
    content = json.dumps(payload)

    wrote = False
    for base in (_intent_state_dir(), _fallback_state_dir()):
        try:
            state_file = base / f"terminals/{terminal_id}/pending_command_intent.json"
            state_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = state_file.with_suffix(".tmp")
            for attempt in range(2):
                try:
                    tmp.write_text(content, encoding="utf-8")
                    tmp.replace(state_file)
                    break
                except OSError:
                    if attempt == 1:
                        raise
                    time.sleep(0.05)
            try:
                (base / f"pending_command_intent_{safe_terminal}.json").unlink(missing_ok=True)
                if session_id:
                    (base / f"pending_command_intent_{safe_terminal}_{_safe_id(session_id)}.json").unlink(
                        missing_ok=True
                    )
            except Exception:
                pass
            wrote = True
            break
        except Exception:
            continue
    if not wrote:
        raise OSError("Failed to persist pending command intent")


def clear_command_intent(terminal_id: str, session_id: str) -> None:
    """Clear any pending command intent for this terminal."""
    safe_terminal = _safe_id(terminal_id) if terminal_id else ""
    safe_session = _safe_id(session_id) if session_id else ""

    for base in (_intent_state_dir(), _fallback_state_dir()):
        try:
            if terminal_id:
                (base / f"terminals/{terminal_id}/pending_command_intent.json").unlink(missing_ok=True)
            if safe_terminal:
                (base / f"pending_command_intent_{safe_terminal}.json").unlink(missing_ok=True)
                if safe_session:
                    (base / f"pending_command_intent_{safe_terminal}_{safe_session}.json").unlink(
                        missing_ok=True
                    )
            if safe_session:
                (base / f"pending_command_intent_{safe_session}.json").unlink(missing_ok=True)
        except Exception:
            continue


def store_active_command(terminal_id: str, session_id: str, prompt: str, command: str) -> None:
    """Persist active command state for command_execution_validator."""
    safe_terminal = _safe_id(terminal_id) if terminal_id else ""
    payload = {
        "command_name": command,
        "do_not_rules": [],
        "timestamp": datetime.now().isoformat(),
        "prompt": prompt,
        "session_id": session_id,
        "terminal_id": terminal_id,
    }
    content = json.dumps(payload)
    wrote = False
    for base in (_session_data_dir(), _fallback_session_data_dir()):
        try:
            base.mkdir(parents=True, exist_ok=True)
            if safe_terminal:
                (base / f"active_command_{safe_terminal}.json").write_text(content, encoding="utf-8")
            (base / "active_command.json").write_text(content, encoding="utf-8")
            wrote = True
            break
        except Exception:
            continue
    if not wrote:
        raise OSError("Failed to persist active command state")


# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------


def _check_workflow_steps_advisory(command: str) -> str | None:
    # Plugin-namespaced skills (plugin:skill format) are in the plugin cache,
    # not in .claude/skills/. _load_workflow_steps can't find them, so it
    # would emit a false "no workflow_steps" advisory. Skip it entirely.
    if ":" in command:
        return None
    try:
        from skill_guard.breadcrumb.tracker import _load_workflow_steps

        result = _load_workflow_steps(command)
        if not result.steps:
            return (
                f"\nNOTE: /{command} has no declared workflow_steps. "
                f"You MUST still follow the skill's Execution section exactly. "
                f"Responding with prose without executing the skill workflow is not acceptable.\n"
            )
    except (ImportError, Exception):
        pass
    return None


def build_main_health_context() -> str:
    """Build hook health report context for /main command."""
    checked_paths = _health_report_paths()
    lines = []
    for candidate in checked_paths:
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for hook_name, status in sorted(data.items()):
                        lines.append(f"- {hook_name}: {status}")
            except Exception:
                pass
    if lines:
        return "\n\n**Hook Health Report:**\n" + "\n".join(lines)
    paths_to_display = checked_paths if checked_paths else [_hook_health_report(), _fallback_hook_health_report()]
    checked = "\n".join(f"- {path}" for path in paths_to_display)
    return "No startup health report found yet\nChecked:\n" + checked


def build_command_context(command: str, args: str, context=None) -> str:
    """Build context injection text that forces Skill() tool invocation."""
    parts = []

    # Plugin (colon-namespaced) commands auto-load their SKILL.md, so steer them
    # to execute directly instead of demanding a redundant Skill() tool call.
    if ":" in command:
        parts.append(PLUGIN_SLASH_EXECUTION_LANE.replace("{command}", command))
    else:
        advisory = _check_workflow_steps_advisory(command)
        if advisory:
            parts.append(advisory)
        parts.append(SLASH_EXECUTION_LANE.replace("{command}", command))

    parts.append(f"**Detected Command**: /{command}")

    if args and args.strip():
        parts.append(f"**Command Args**: {args.strip()}")
        if _is_help_request(args):
            detected_flag = next(t for t in args.strip().split() if t in _HELP_FLAGS)
            parts.append(
                HELP_REQUEST_LANE.replace("{flag}", detected_flag).replace("{command}", command)
            )

    if command.lower() == "main":
        parts.append(build_main_health_context())

    return "\n\n".join(parts)


__all__ = [
    "COMMAND_BLOCKLIST",
    "SLASH_EXECUTION_LANE",
    "HELP_REQUEST_LANE",
    "build_command_context",
    "build_main_health_context",
    "clear_command_intent",
    "extract_command_name",
    "extract_slash_command",
    "is_command_directive",
    "is_topic_inquiry",
    "log_command_intent_telemetry",
    "should_block_command",
    "store_active_command",
]
