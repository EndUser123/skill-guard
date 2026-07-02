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

_SHARED_LIB = Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent / ".claude" / "hooks" / "__lib"
if str(_SHARED_LIB) not in sys.path:
    sys.path.insert(0, str(_SHARED_LIB))
try:
    from stop_block_log import _extract_block_ctx, _log_stop_block  # noqa: E402
except ImportError:
    def _extract_block_ctx(event: str, input_data: bytes) -> dict:  # type: ignore[misc]
        return {}
    def _log_stop_block(hook_name: str, reason: str, child_stderr: str, ctx: dict | None) -> None:  # type: ignore[misc]
        pass

def _normalize_stdout(data: dict) -> dict:
    """Normalize hook output to Claude Code Zod-valid schema."""
    def _allow() -> dict:
        # ponytail: "approve" is invalid for Stop (JSON validation failed —
        # see stop_hook_output_schema memory) and unneeded for PreToolUse;
        # on allow, emit {} but keep any additionalContext.
        out: dict = {}
        if data.get('additionalContext'):
            out['additionalContext'] = data['additionalContext']
        return out
    if data.get('decision') == 'allow':
        return _allow()
    if data.get('decision') == 'block':
        return {'decision': 'block', 'reason': data.get('reason', '')}
    if 'allow' in data:
        if data['allow'] is False:
            return {'decision': 'block', 'reason': data.get('reason', '')}
        return _allow()
    if 'continue' in data:
        if data['continue'] is False:
            return {'decision': 'block', 'reason': data.get('reason', '')}
        return _allow()
    if 'ok' in data:
        return _allow()
    return data



# ---------------------------------------------------------------------------
# Path setup — resolve __lib shadowing from P:\\\\\\__csf/__lib
# ---------------------------------------------------------------------------

_HOOKS_DIR = Path(__file__).resolve().parent
_SKILL_GUARD_SRC = Path(r"P:/packages/.claude-marketplace/plugins/skill-guard/src")
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
from skill_guard.slash_command_observability import extract_command_name
from skill_guard.skill_enforcer import should_block_command

# ---------------------------------------------------------------------------
# Tool input helpers
# ---------------------------------------------------------------------------

_INVESTIGATION_TOOLS = frozenset({
    "Read", "Grep", "Glob", "AskUserQuestion",
    "WebSearch", "WebFetch",
    "mcp__4_5v_mcp__analyze_image",
    "mcp__web_reader__webReader",
})


def _extract_slash_command(prompt: str) -> str | None:
    """Namespaced-aware extractor (delegates to the shared slash_command_observability).

    Replaces the prior colon-truncating regex `^/([a-zA-Z][\w-]*)`, which mis-extracted
    `/cc-skills-utils:plugin-installer` as `cc-skills-utils`. The shared extractor
    handles NAMESPACED_SLASH_COMMAND_RE and returns the full `plugin:skill-name`.
    """
    return extract_command_name(prompt)


def _artifact_written(tool_name: str, tool_input: dict[str, Any]) -> bool:
    """Return True when this tool writes a tracked artifact file.r"""
    if tool_name not in {"Write", "Edit", "MultiEdit"}:
        return False
    path = tool_input.get("file_path", "")
    return bool(path and not path.startswith(r"P:\\\\\\tmp") and not path.startswith("/tmp"))


# ---------------------------------------------------------------------------
# Action-authority gate (Tier 1, deterministic)
# ---------------------------------------------------------------------------
# ponytail: read last user message from per-session transcript JSONL each fire.
# No persisted auth state — multi-terminal isolated + stale-immune by construction.

_SYSREMINDER_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL | re.IGNORECASE)
_BYPASS_RE = re.compile(r"--allow-unsolicited|--allow-unrequested", re.IGNORECASE)
_CONFIRM_RE = re.compile(
    r"\b(?:yes|yeah|yep|ok|okay|sure|please|go\s+ahead|do\s+it|proceed|continue"
    r"|approved|lgtm|looks\s+good|ship\s+it|go\s+for\s+it|sounds\s+good)\b",
    re.IGNORECASE,
)
# ponytail: file-mutation imperatives only — noun-ambiguous verbs (build, ship,
# patch, clean, bump, generate, wire) excluded because they false-match inside
# questions ("status of the build?"). "ship it" is covered by _CONFIRM_RE.
_IMPERATIVE_RE = re.compile(
    r"\b(?:fix|edit|update|change|modify|add|create|write|implement|refactor"
    r"|move|rename|delete|remove|migrate)\b",
    re.IGNORECASE,
)
# ponytail: single-line append in "a" mode (O_APPEND) is atomic per write at the
# OS level, so concurrent terminals don't corrupt records. If measurement shows
# interleaving, add msvcrt/fcntl locking here — telemetry is best-effort.
_AMBIGUOUS_LOG = Path("P:/.claude/logs/diagnostics/action_authority_ambiguous.jsonl")


def _strip_injections(text: str) -> str:
    """Remove <system-reminder> blocks from user-authored text."""
    return _SYSREMINDER_RE.sub("", text or "")


def _parse_transcript_for_last_user_message(transcript_path: str) -> str | None:
    """Return text of the last user-authored message in the transcript JSONL.

    Skips tool_result entries (role:user with only tool_result blocks).
    Returns None if the transcript is missing/unreadable (callers fail-open).
    Returns '' only when the file is readable but holds no user text.
    """
    try:
        path = Path(transcript_path)
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8")
    except Exception:
        return None
    for line in reversed(content.split("\n")):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("role") != "user" and entry.get("type") != "user":
            continue
        message = entry.get("message", entry)
        if not isinstance(message, dict):
            continue
        blocks = message.get("content", [])
        if isinstance(blocks, str):
            text = blocks
        elif isinstance(blocks, list):
            parts = [
                b["text"] for b in blocks
                if isinstance(b, dict) and b.get("type") == "text" and "text" in b
            ]
            text = "\n".join(parts)
        else:
            text = ""
        if text.strip():
            return text
    return ""


def _log_ambiguous(data: dict, authored: str) -> None:
    """Best-effort append of an ambiguous-slice record (multi-terminal safe)."""
    tool_input = data.get("tool_input") or data.get("input", {})
    if not isinstance(tool_input, dict):
        tool_input = {}
    rec = {
        "ts": time.time(),
        "session_id": data.get("session_id", ""),
        "tool": data.get("tool_name", ""),
        "target": str(tool_input.get("file_path", "")),
        "authored": authored[:300],
    }
    try:
        _AMBIGUOUS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _AMBIGUOUS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _action_authority_gate(data: dict) -> dict | None:
    """Tier 1 deterministic action-authority gate for Write|Edit|MultiEdit.

    Returns {"continue": False, "reason": ...} to BLOCK, or None to allow.
    Reads the last user-authored message from transcript_path (per-session,
    fresh each fire) — no persisted auth state.
    """
    if data.get("tool_name") not in ("Write", "Edit", "MultiEdit"):
        return None
    tool_input = data.get("tool_input") or data.get("input", {})
    if not isinstance(tool_input, dict):
        tool_input = {}
    norm = str(tool_input.get("file_path", "")).replace("\\", "/").lower()

    # Inherent-allow short-circuit: artifacts/state/session/temp roots.
    if any(p in norm for p in (
        ".claude/.artifacts/", ".claude/state/", ".claude/.session/",
        "/tmp/", ":/temp/", ":/tmp/",
    )):
        return None

    raw = _parse_transcript_for_last_user_message(data.get("transcript_path", ""))
    if raw is None:
        return None  # missing/unreadable transcript → fail-open (step 10)
    if _BYPASS_RE.search(raw):  # bypass flag anywhere in raw user text
        return None
    authored = _strip_injections(raw).strip()

    # Empty-after-strip → BLOCK (the MEMORY.md catch).
    if not authored:
        return {
            "continue": False,
            "reason": (
                "⛔ ACTION-AUTHORITY GATE\n"
                "Write/Edit attempted with no recent user instruction authorizing file changes.\n"
                "After stripping system/hook advisories, the session's last user message is empty.\n"
                "If this work was requested, rephrase so the instruction is explicit, "
                "or add --allow-unsolicited."
            ),
        }

    has_confirm = bool(_CONFIRM_RE.search(authored))
    has_imperative = bool(_IMPERATIVE_RE.search(authored))
    is_question = "?" in authored

    # Pure question (no imperative, no confirm) → BLOCK.
    if is_question and not has_imperative and not has_confirm:
        return {
            "continue": False,
            "reason": (
                "⛔ ACTION-AUTHORITY GATE\n"
                "Write/Edit attempted but the session's last user message is a question, "
                f"not an instruction:\n\"{authored[:160]}\"\n"
                "If you intended this as authorization, rephrase as an instruction "
                "or add --allow-unsolicited."
            ),
        }

    # Clear imperative (not in a question) → allow.
    if has_imperative and not is_question:
        return None
    # Bare confirmation → allow.
    if has_confirm:
        return None
    # Ambiguous (verb-in-question, declarative intent) → allow + telemetry.
    _log_ambiguous(data, authored)
    return None


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
    0. Universal skill-first gate: if the user typed `/<skill>`, block every non-Skill
       tool until Skill() is called. Runs BEFORE any run-state check so it fires even
       when there is no active run yet (the user's reported failure mode).
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

    # ------------------------------------------------------------------
    # Layer 0: UNIVERSAL skill-first gate (no workflow_steps requirement).
    # Runs BEFORE the investigation allowlist so the Skill() tool itself is
    # subject to the skill-first contract (its name must match the typed
    # slash command). Other investigation tools (Read/Grep/Glob) still pass
    # freely — they don't satisfy or bypass Skill().
    # ------------------------------------------------------------------
    user_message = str(
        data.get("user_message") or data.get("prompt") or data.get("message") or ""
    )
    slash_command = _extract_slash_command(user_message) if user_message else None
    if slash_command:
        # Allow the matching Skill() tool call itself
        if tool_name == "Skill":
            skill_name = tool_input.get("skill", "") if isinstance(tool_input, dict) else ""
            if skill_name and skill_name.lower() == slash_command.lower():
                # Skill() matches — proceed; do not block
                pass
            else:
                # Skill tool called but the named skill doesn't match the typed
                # slash command — block to keep the user on the intended path.
                _probe_log("skill_first", "block", tool_name, terminal_id, "", slash_command, reason="skill_name_mismatch")
                return _normalize_stdout({
                    "continue": False,
                    "reason": (
                        f"⛔ SKILL-FIRST GATE\n\n"
                        f"You typed /{slash_command} but called Skill('{skill_name}') instead.\n\n"
                        f"Your FIRST action must be: Skill(skill='{slash_command}')\n\n"
                        f"Do NOT respond with prose analysis or use other tools before calling Skill.\n"
                        f"Do NOT bypass this gate by outputting inline analysis text without calling Skill(...)."
                    ),
                })
        else:
            enforce = not should_block_command(slash_command)
            if enforce:
                _probe_log("skill_first", "block", tool_name, terminal_id, "", slash_command, reason="skill_first_universal")
                return _normalize_stdout({
                    "continue": False,
                    "reason": (
                        f"⛔ SKILL-FIRST GATE\n\n"
                        f"You typed /{slash_command} but haven't called Skill('{slash_command}') yet.\n\n"
                        f"Skill() is required before any other tool for every manually-invoked skill.\n\n"
                        f"Your FIRST action must be: Skill(skill='{slash_command}')\n\n"
                        f"Do NOT respond with prose analysis or use other tools before calling Skill.\n"
                        f"Do NOT bypass this gate by outputting inline analysis text without calling Skill(...)."
                    ),
                })

    # ------------------------------------------------------------------
    # Layer 0.5: Action-authority gate (Tier 1).
    # Block Write/Edit/MultiEdit when the session's last user message has no
    # instruction authorizing file changes (the MEMORY.md failure mode).
    # Runs before run-state checks so it fires even with no active run.
    # ------------------------------------------------------------------
    if tool_name in ("Write", "Edit", "MultiEdit"):
        _aa_block = _action_authority_gate(data)
        if _aa_block:
            _probe_log("action_authority", "block", tool_name, terminal_id, "", "",
                       reason=_aa_block.get("reason", "")[:200])
            return _normalize_stdout(_aa_block)

    # Always allow investigation tools (Read/Grep/Glob/etc.) — but NOT Skill,
    # which is now gated by Layer 0 above so a mismatched Skill() call can be
    # blocked.
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
        print(json.dumps({}))
        return
    result = handle_pre_tool_use(payload)
    print(json.dumps(_normalize_stdout(result)))


def stop_main():
    """Subprocess Stop entry point."""
    raw = sys.stdin.buffer.read()
    block_ctx = _extract_block_ctx("Stop", raw)
    try:
        payload = json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        print(json.dumps({}))
        return
    result = handle_stop(payload)
    if result.get("allow") is False:
        reason = result.get("reason", "")
        _log_stop_block("skill-guard_Stop", reason, "", block_ctx)
        print(json.dumps({"decision": "block", "reason": reason}))
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
