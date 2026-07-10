r"""Slash command observability for skill-guard.

This module classifies slash-command prompts, discovers local command and skill
targets, and emits best-effort telemetry into the shared hook evidence store
when a turn scope is available.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from skill_guard.hook_compat import HookResult, register_hook

try:
    from evidence_store import append_tool_event, get_active_turn, resolve_session_id
except Exception:  # pragma: no cover - observability must fail open

    def append_tool_event(*args, **kwargs) -> bool:  # type: ignore[no-redef]
        return False

    def get_active_turn(session_id: str, terminal_id: str) -> str | None:  # type: ignore[no-redef]
        return None

    def resolve_session_id(explicit: str = "") -> str:  # type: ignore[no-redef]
        return explicit.strip()


def _claude_dir() -> Path:
    project_root = Path(os.environ.get("CLAUDE_PROJECT_DIR", "P:/"))
    return project_root / ".claude"


def _commands_dir() -> Path:
    return _claude_dir() / "commands"


def _skills_dir() -> Path:
    return _claude_dir() / "skills"


SLASH_COMMAND_RE = re.compile(r"^/([a-z0-9_-]+)(?:\s+(.*))?$", re.IGNORECASE)
NAMESPACED_SLASH_COMMAND_RE = re.compile(r"^/([a-z0-9_-]+):([a-z0-9_-]+)(?:\s+(.*))?$", re.IGNORECASE)
# Harness slash-command transcript entries wrap the command in XML tags:
#   <command-name>/plugin:skill</command-name> ... <command-args>args</command-args>
COMMAND_NAME_TAG_RE = re.compile(r"<command-name>\s*/?([a-z0-9_:-]+)\s*</command-name>", re.IGNORECASE)
COMMAND_ARGS_TAG_RE = re.compile(r"<command-args>(.*?)</command-args>", re.IGNORECASE | re.DOTALL)
LEADING_PROMPT_GLYPHS_RE = re.compile(r"^\s*(?:[❯›»>$#]+\s*)+")
BACKING_SKILL_RE = re.compile(r'Skill\(\s*["\']([A-Za-z0-9_-]+)["\']\s*\)')


BUILTIN_SLASH_COMMANDS = frozenset(
    {
        "add-dir",
        "agents",
        "autofix-pr",
        "batch",
        "bug",
        "clear",
        "compact",
        "config",
        "cost",
        "doctor",
        "help",
        "init",
        "listen",
        "login",
        "logout",
        "memory",
        "model",
        "mcp",
        "permissions",
        "recap",
        "release-notes",
        "reload-plugins",
        "remote-control",
        "remote-env",
        "rename",
        "resume",
        "review",
        "rewind",
        "sandbox",
        "schedule",
        "security-review",
        "setup-bedrock",
        "setup-vertex",
        "skills",
        "stats",
        "status",
        "statusline",
        "stickers",
        "tasks",
        "team-onboarding",
        "teleport",
        "terminal-setup",
        "theme",
        "vim",
    }
)

LIGHTWEIGHT_SLASH_COMMANDS = frozenset(
    {
        "clear-notifications",
        "constraints",
        "context-status",
        "obs",
        "recent",
        "standards",
    }
)


def _normalize_prompt(prompt: str) -> str:
    stripped = (prompt or "").strip()
    return LEADING_PROMPT_GLYPHS_RE.sub("", stripped)


def normalize_prompt(prompt: str) -> str:
    return _normalize_prompt(prompt)


def extract_slash_command(prompt: str) -> tuple[str | None, str]:
    """Return the slash command name and argument tail."""
    # Harness transcript entries carry the command in <command-name> XML tags,
    # not as a leading "/token" — parse those first (schema since CC 2.x).
    tag = COMMAND_NAME_TAG_RE.search(prompt or "")
    if tag:
        args_match = COMMAND_ARGS_TAG_RE.search(prompt)
        return tag.group(1).lower(), (args_match.group(1).strip() if args_match else "")
    normalized = _normalize_prompt(prompt)
    match = NAMESPACED_SLASH_COMMAND_RE.match(normalized)
    if match:
        # Namespaced skill: /plugin:skill-name → "plugin:skill-name"
        return (match.group(1).lower() + ":" + match.group(2).lower()), (match.group(3) or "").strip()
    match = SLASH_COMMAND_RE.match(normalized)
    if not match:
        return None, ""
    return match.group(1).lower(), (match.group(2) or "").strip()


def extract_command_name(prompt: str) -> str | None:
    command_name, _ = extract_slash_command(prompt)
    return command_name


def is_slash_prompt(prompt: str) -> bool:
    command_name, _ = extract_slash_command(prompt)
    return bool(command_name)


@lru_cache(maxsize=8)
def _local_command_paths(commands_dir: str) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    base = Path(commands_dir)
    if not base.exists():
        return paths
    for md in base.glob("*.md"):
        paths[md.stem.lower()] = md
    return paths


@lru_cache(maxsize=8)
def _skill_paths(skills_dir: str) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    base = Path(skills_dir)
    if not base.exists():
        return paths
    for child in base.iterdir():
        if not child.is_dir():
            continue
        skill_md = child / "SKILL.md"
        if skill_md.exists():
            paths[child.name.lower()] = skill_md
    return paths


def _extract_backing_skill(command_path: Path) -> str:
    try:
        content = command_path.read_text(encoding="utf-8")
    except OSError:
        return ""

    match = BACKING_SKILL_RE.search(content)
    if match:
        return match.group(1).strip().lower()
    return ""


def classify_slash_command(command_name: str) -> dict[str, str]:
    """Classify a slash command by available local sources."""
    command = (command_name or "").strip().lower()
    result = {
        "command_name": command,
        "command_family": "unknown",
        "command_path": "",
        "backing_target": "",
    }

    if not command:
        return result

    commands_dir = str(_commands_dir())
    skills_dir = str(_skills_dir())

    command_path = _local_command_paths(commands_dir).get(command)
    if command_path:
        result["command_family"] = "local_command"
        result["command_path"] = str(command_path)
        backing_skill = _extract_backing_skill(command_path)
        if not backing_skill and command in _skill_paths(skills_dir):
            backing_skill = command
        result["backing_target"] = backing_skill
        return result

    skill_path = _skill_paths(skills_dir).get(command)
    if skill_path:
        result["command_family"] = "skill"
        result["command_path"] = str(skill_path)
        result["backing_target"] = command
        return result

    if command in BUILTIN_SLASH_COMMANDS:
        result["command_family"] = "builtin"
    elif command in LIGHTWEIGHT_SLASH_COMMANDS:
        result["command_family"] = "lightweight"

    return result


def _resolve_session_id(context: Any) -> str:
    data = getattr(context, "data", {}) or {}
    session_id = (
        data.get("session_id")
        or data.get("sessionId")
        or data.get("CLAUDE_SESSION_ID")
        or getattr(context, "session_id", "")
        or ""
    )
    return resolve_session_id(str(session_id))


def _resolve_terminal_id(context: Any) -> str:
    data = getattr(context, "data", {}) or {}
    terminal_id = (
        data.get("terminal_id")
        or data.get("terminalId")
        or data.get("CLAUDE_TERMINAL_ID")
        or getattr(context, "terminal_id", "")
        or ""
    )
    return str(terminal_id).strip()


def _resolve_turn_id(context: Any, session_id: str, terminal_id: str) -> str:
    data = getattr(context, "data", {}) or {}
    turn_id = str(data.get("turn_id") or "").strip()
    if turn_id:
        return turn_id
    if session_id and terminal_id:
        return str(get_active_turn(session_id, terminal_id) or "").strip()
    return ""


def _append_slash_event(
    *,
    context: Any,
    event_type: str,
    command_name: str,
    command_args: str,
    prompt: str,
    command_family: str,
    command_path: str = "",
    backing_target: str = "",
    success: bool = True,
    reason: str = "",
) -> bool:
    session_id = _resolve_session_id(context)
    if not session_id:
        return False

    terminal_id = _resolve_terminal_id(context)
    turn_id = _resolve_turn_id(context, session_id, terminal_id)
    metadata: dict[str, Any] = {
        "slash_event_type": event_type,
        "command_name": command_name,
        "command_args": command_args,
        "command_family": command_family,
        "command_path": command_path,
        "backing_target": backing_target,
        "reason": reason,
        "turn_id": turn_id,
        "prompt": prompt,
        "hook_event_name": "UserPromptSubmit",
    }

    tool_name = {
        "requested": "SlashCommandRequested",
        "resolved": "SlashCommandResolved",
        "outcome": "SlashCommandOutcome",
    }.get(event_type, "SlashCommand")

    command_text = f"/{command_name}"
    if command_args:
        command_text = f"{command_text} {command_args}".strip()

    return append_tool_event(
        session_id=session_id,
        terminal_id=terminal_id,
        tool_name=tool_name,
        command=command_text,
        output_excerpt=reason,
        success=success,
        metadata=metadata,
    )


def record_slash_request(context: Any, command_name: str, command_args: str) -> bool:
    classification = classify_slash_command(command_name)
    return _append_slash_event(
        context=context,
        event_type="requested",
        command_name=classification["command_name"],
        command_args=command_args,
        prompt=getattr(context, "prompt", ""),
        command_family=classification["command_family"],
        command_path=classification["command_path"],
        backing_target=classification["backing_target"],
        success=True,
    )


def record_slash_resolution(context: Any, command_name: str, command_args: str) -> bool:
    classification = classify_slash_command(command_name)
    return _append_slash_event(
        context=context,
        event_type="resolved",
        command_name=classification["command_name"],
        command_args=command_args,
        prompt=getattr(context, "prompt", ""),
        command_family=classification["command_family"],
        command_path=classification["command_path"],
        backing_target=classification["backing_target"],
        success=True,
    )


def record_slash_outcome(
    context: Any,
    command_name: str,
    command_args: str,
    *,
    outcome: str,
    reason: str = "",
) -> bool:
    classification = classify_slash_command(command_name)
    success = outcome in {"completed", "allowed", "handled", "observed"}
    return _append_slash_event(
        context=context,
        event_type="outcome",
        command_name=classification["command_name"],
        command_args=command_args,
        prompt=getattr(context, "prompt", ""),
        command_family=classification["command_family"],
        command_path=classification["command_path"],
        backing_target=classification["backing_target"],
        success=success,
        reason=f"{outcome}{': ' + reason if reason else ''}",
    )


@register_hook("slash_command_observability", priority=0.6)
def slash_command_observability_hook(context: Any) -> HookResult:
    """Record slash command request and resolution telemetry."""
    prompt = str(getattr(context, "prompt", "") or "")
    command_name, command_args = extract_slash_command(prompt)
    if not command_name:
        return HookResult.empty()

    record_slash_request(context, command_name, command_args)
    record_slash_resolution(context, command_name, command_args)
    return HookResult.empty()


__all__ = [
    "BUILTIN_SLASH_COMMANDS",
    "LIGHTWEIGHT_SLASH_COMMANDS",
    "classify_slash_command",
    "extract_command_name",
    "extract_slash_command",
    "is_slash_prompt",
    "normalize_prompt",
    "slash_command_observability_hook",
    "record_slash_outcome",
    "record_slash_request",
    "record_slash_resolution",
]
