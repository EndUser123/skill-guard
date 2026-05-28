r"""
execution_hooks.py
==================

PreToolUse and Stop hook handlers using ExecutionRuntime + ArtifactsExecutionStore.

INVARIANT 3 (PreToolUse hard gate):
  PreToolUse is a fail-closed contract gate. Any tool NOT in allowed_tools_now
  AND NOT in blocked_tools is BLOCKED. Only investigation tools (Read, Grep, Glob,
  etc.) pass through regardless of run state. This is the ONLY hook that emits
  tool_allowed / tool_blocked events to execution-events.jsonl.

INVARIANT 4 (Stop is pure):
  Stop reads execution-state.json, applies contract rules, emits run_ended,
  returns allow/fail. No recursion, no LLM calls, no breadcrumb reads.
  Stop does not own tool events — PreToolUse does.

PreToolUse (hard blocker):
  - load_active_run(tid) → check tool against allowed_tools_now / blocked_tools
  - record_tool_use(run, tool_name, allowed) → emits event, transitions phase, sets FAILED
  - Returns {"continue": True/False, ...}

Stop (narrow — no recursion, no heavy analysis):
  - evaluate_completion(run, response_text) → status
  - finalize_run(run, status) → emits run_ended, clears state
  - Returns {"allow": True/False, ...}
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

def _normalize_stdout(data: dict) -> dict:
    """Normalize hook output to Claude Code Zod-valid schema."""
    if data.get('decision') == 'allow':
        return {'decision': 'approve'}
    if data.get('decision') == 'block':
        return {'decision': 'block', 'reason': data.get('reason', '')}
    if 'allow' in data:
        if data['allow'] is False:
            return {'decision': 'block', 'reason': data.get('reason', '')}
        return {'decision': 'approve'}
    if 'continue' in data:
        if data['continue'] is False:
            return {'decision': 'block', 'reason': data.get('reason', '')}
        return {'decision': 'approve'}
    if 'ok' in data:
        return {'decision': 'approve'}
    return data



# ---------------------------------------------------------------------------
# Path setup — resolve __lib shadowing from P:\\\\\\__csf/__lib
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
# Imports from this package
# ---------------------------------------------------------------------------

from skill_guard.execution_runtime import (
    ExecutionRuntime,
    ResponseCheckResult,
    validate_response_requirements,
)
from skill_guard.utils.terminal_detection import detect_terminal_id

# ---------------------------------------------------------------------------
# Tool input helpers
# ---------------------------------------------------------------------------

_INVESTIGATION_TOOLS = frozenset({
    "Read", "Grep", "Glob", "AskUserQuestion", "Skill",
    "WebSearch", "WebFetch",
    "mcp__4_5v_mcp__analyze_image",
    "mcp__web_reader__webReader",
})


def _extract_slash_command(prompt: str) -> str | None:
    match = re.match(r"^/([a-zA-Z][\w-]*)", prompt.strip())
    return match.group(1) if match else None


def _artifact_written(tool_name: str, tool_input: dict[str, Any]) -> bool:
    """Return True when this tool writes a tracked artifact file.r"""
    if tool_name not in {"Write", "Edit", "MultiEdit"}:
        return False
    path = tool_input.get("file_path", "")
    return bool(path and not path.startswith(r"P:\\\\\\tmp") and not path.startswith("/tmp"))


# ---------------------------------------------------------------------------
# PreToolUse handler
# ---------------------------------------------------------------------------

_HOOKS_LIB_DIR = Path(r"P:\\\\\\.claude/hooks/__lib")

_STOP_HOOK: dict[str, Any] = {}  # Populated by Stop hook registration


# PRETOOL PROBE BEGIN — correlate with legacy gate log
import time as _probe_time
import json as _probe_json
from pathlib import Path as _probe_path

_PROBE_LOG = _probe_path(r"P:\\\\\\.claude/tmp/PRETOOL_GATE_PROBE.jsonl")
_PROBE_LOG.parent.mkdir(parents=True, exist_ok=True)


def _probe_log(gate_name: str, decision: str, tool_name: str, terminal_id: str, run_id: str, skill_name: str, reason: str = "") -> None:
    entry = {
        "ts": _probe_time.time(),
        "gate": gate_name,
        "tool": tool_name,
        "terminal_id": terminal_id,
        "run_id": run_id,
        "skill": skill_name,
        "decision": decision,
        "reason": reason[:200] if reason else "",
    }
    try:
        with _probe_log.open("a", encoding="utf-8") as _f:
            _f.write(_probe_json.dumps(entry) + "\n")
    except Exception:
        pass
# PRETOOL PROBE END


def handle_pre_tool_use(data: dict, runtime: ExecutionRuntime | None = None) -> dict[str, Any]:
    """
    PreToolUse handler for execution contract enforcement.

    Checks:
    1. Is there an active run for this terminal?
    2. Is the requested tool allowed (in allowed_tools_now or not in blocked_tools)?
    3. If not allowed: record_tool_use(allowed=False), block.
    4. If allowed: record_tool_use(allowed=True), allow.

    PreToolUse is the SOLE owner of tool allow/block events.
    PostToolUse MUST NOT emit tool_allowed / tool_blocked events.
    """
    tool_name = data.get("tool_name", "")
    tool_input = data.get("input", {})
    terminal_id = detect_terminal_id() or os.environ.get("CLAUDE_TERMINAL_ID", "unknown")

    # Always allow investigation tools
    if tool_name in _INVESTIGATION_TOOLS:
        _probe_log("runtime", "allow_investigation", tool_name, terminal_id, "", "", reason="investigation_tool")
        return {"continue": True}

    if runtime is None:
        runtime = ExecutionRuntime()
    run = runtime.load_active_run()

    if run is None:
        _probe_log("runtime", "no_run", tool_name, terminal_id, "", "", reason="no_active_run")
        return {"continue": True}

    # Check tool permission
    blocked = tool_name in run.blocked_tools or (
        run.allowed_tools_now and tool_name not in run.allowed_tools_now
    )

    if blocked:
        runtime.record_tool_use(run, tool_name=tool_name, allowed=False, reason="not_in_allowed")
        _probe_log("runtime", "block", tool_name, terminal_id, run.run_id, run.skill_name, reason="not_in_allowed")
        return {
            "continue": False,
            "reason": (
                f"⛔ TOOL BLOCKED BY CONTRACT\n\n"
                f"Skill: /{run.skill_name}\n"
                f"Contract: {run.contract_type}\n"
                f"Blocked tool: {tool_name}\n"
                f"Allowed tools: {', '.join(run.allowed_tools_now) if run.allowed_tools_now else 'none'}\n\n"
                f"Use only the tools permitted by this skill's contract."
            ),
        }

    # Allowed: record and pass through
    runtime.record_tool_use(run, tool_name=tool_name, allowed=True)
    _probe_log("runtime", "allow", tool_name, terminal_id, run.run_id, run.skill_name)
    return {"continue": True}


# ---------------------------------------------------------------------------
# Stop hook handler
# ---------------------------------------------------------------------------

def _parse_transcript_for_response(transcript_path: str) -> str:
    """Read transcript_path and extract the assistant's response text."""
    try:
        path = Path(transcript_path)
        if not path.exists():
            return ""
        content = path.read_text(encoding="utf-8")
        for line in reversed(content.strip().split("\n")):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            role = entry.get("role", "")
            msg_type = entry.get("type", "")
            is_assistant = (
                role == "assistant"
                or msg_type == "assistant"
                or msg_type == "message"
            )
            if is_assistant:
                message = entry.get("message", entry)
                content_blocks = message.get("content", [])
                if isinstance(content_blocks, list):
                    return " ".join(
                        b.get("text", "") for b in content_blocks
                        if isinstance(b, dict) and b.get("type") == "text"
                    )
                elif isinstance(content_blocks, str):
                    return content_blocks
                elif isinstance(content_blocks, dict):
                    # Handle dict content (e.g., {"type": "text", "text": "..."})
                    if content_blocks.get("type") == "text" and "text" in content_blocks:
                        return content_blocks["text"]
    except Exception as e:
        # Log specific exceptions but don't silently swallow - let them bubble up
        import sys
        print(f"Error parsing transcript entry: {e}", file=sys.stderr)
        raise
    return ""


def handle_stop(data: dict) -> dict[str, Any]:
    """
    Stop handler for execution contract evaluation.

    Narrow role:
    - Read state via runtime.load_active_run()
    - Determine status via evaluate_completion()
    - Emit run_ended event
    - Return allow/fail based on status

    No recursion, no heavy analysis, no re-reading transcript for tool use.
    Response text is only used for structured-output / hybrid completion checks.
    """
    terminal_id = detect_terminal_id() or os.environ.get("CLAUDE_TERMINAL_ID", "unknown")

    runtime = ExecutionRuntime()
    run = runtime.load_active_run()

    if run is None:
        return {"allow": True}

    # Extract response text for structured-output checks
    response_text: str | None = None
    transcript_path = data.get("transcript_path", "")
    if transcript_path and run.contract_type in ("structured-output", "hybrid"):
        response_text = _parse_transcript_for_response(transcript_path)

    status = runtime.evaluate_completion(run, response_text)
    runtime.finalize_run(run, status)

    if status == "failed":
        return {
            "allow": False,
            "reason": (
                f"SKILL CONTRACT NOT SATISFIED: /{run.skill_name}\n"
                f"Contract type: {run.contract_type}\n"
                f"Missing requirements: {', '.join(run.missing_requirements) if run.missing_requirements else 'none'}\n\n"
                f"Complete the skill's workflow requirements before stopping."
            ),
        }

    # ACTIVE or COMPLETE → allow stop
    return {"allow": True}


# ---------------------------------------------------------------------------
# Entry points (Subprocess hooks: PreToolUse + Stop via hooks.json)
# ---------------------------------------------------------------------------

def pre_tool_use_main():
    """Subprocess PreToolUse entry point."""
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        print(json.dumps({"decision": "approve"}))
        return
    result = handle_pre_tool_use(payload)
    print(json.dumps(_normalize_stdout(result)))


def stop_main():
    """Subprocess Stop entry point."""
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        print(json.dumps({}))
        return
    result = handle_stop(payload)
    if result.get("allow") is False:
        print(json.dumps({"decision": "block", "reason": result.get("reason", "")}))
    else:
        print(json.dumps({}))


if __name__ == "__main__":
    subcommand = sys.argv[1] if len(sys.argv) > 1 else ""
    if subcommand == "pre_tool_use_main":
        pre_tool_use_main()
    elif subcommand == "stop_main":
        stop_main()
    else:
        # Default: detect from environment
        if os.environ.get("CLAUDE_HOOK_EVENT") == "Stop":
            stop_main()
        else:
            pre_tool_use_main()