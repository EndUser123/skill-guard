#!/usr/bin/env python3
"""
probe_hook_payload_logger.py — Instrumented hook to log Stop payload keys.

Purpose: Empirical investigation — log the top-level keys present in the
subprocess stdin JSON received from Stop_router.run_hook_subprocess().

Run by: User manually in a Claude Code session (see manual test instructions).

Output: P:/.claude/tmp/HOOK_PAYLOADS/probe_<timestamp>.jsonl
  Each line: {"ts": ..., "keys": [...], "terminal_id": "...", "hook": "probe_hook_payload_logger.py"}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime

# Safe log directory — write to .claude/tmp/, not hooks/
_LOG_DIR = Path("P:/.claude/tmp/HOOK_PAYLOADS")
_HOOK_NAME = "probe_hook_payload_logger.py"


def _write_log(entry: dict) -> None:
    """Append a JSON line to the log file, creating directory as needed."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = _LOG_DIR / "probe_log.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _extract_terminal_id(data: dict) -> str:
    """Extract terminal_id from the payload."""
    return str(data.get("terminal_id") or data.get("terminalId") or "unknown")


def run(data: dict) -> dict:
    """
    Entry point for subprocess hooks.

    Expected input (JSON from stdin, parsed by Stop_router.run_hook_subprocess):
    - Top-level keys from _build_validator_input + Stop_router injection
    - Notable injected keys: rca_turn, rca_skill, session_start_ts
    - skill_state: optional dict with 'skill' key
    """
    keys = sorted(data.keys())

    terminal_id = _extract_terminal_id(data)

    entry = {
        "ts": datetime.now().isoformat(),
        "keys": keys,
        "key_count": len(keys),
        "terminal_id": terminal_id,
        "hook": _HOOK_NAME,
    }

    # Also log rca_turn specifically if present (key question from investigation)
    if "rca_turn" in data:
        entry["rca_turn_value"] = data["rca_turn"]
    if "rca_skill" in data:
        entry["rca_skill_value"] = data["rca_skill"]
    if "session_start_ts" in data:
        entry["session_start_ts_value"] = data["session_start_ts"]
    if "skill_state" in data:
        entry["skill_state_value"] = data["skill_state"]

    _write_log(entry)

    # Return allow — this probe should not interfere with normal operation
    return {"allow": True}


if __name__ == "__main__":
    # Called by Stop_router.run_hook_subprocess: JSON payload is read from stdin
    # and passed as `data` argument. This block handles direct invocation
    # for manual testing (e.g., echo '{"assistant_response":"test"}' | python probe_hook_payload_logger.py)
    try:
        raw_input = sys.stdin.read()
        if raw_input.strip():
            data = json.loads(raw_input)
            result = run(data)
            print(json.dumps(result))
        else:
            # No stdin — called as module, not subprocess
            print(json.dumps({"allow": True, "note": "probe: no stdin"}))
    except json.JSONDecodeError as e:
        print(json.dumps({"allow": True, "note": f"probe: JSON parse error {e}"}), file=sys.stderr)
        sys.exit(1)