#!/usr/bin/env python3
"""Skill context show/reset CLI.

Usage:
    python skill_context.py show [terminal_id]
    python skill_context.py reset [terminal_id]

If terminal_id is omitted, uses CLAUDE_TERMINAL_ID env var or "default".
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HOOKS_DIR = Path(r"P:\.claude\hooks")
_STATE_DIR = HOOKS_DIR / "state" / "skill_context"

def _safe_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value)

def _state_path(terminal_id: str) -> Path:
    tid = _safe_id(terminal_id or "default")
    return _STATE_DIR / f"skill_context_{tid}.json"

def show(terminal_id: str) -> int:
    path = _state_path(terminal_id)
    if not path.exists():
        print(f"No skill context for terminal '{terminal_id}'")
        return 1
    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"State file: {path}")
    print(f"  expected_skill : {data.get('expected_skill', '')}")
    print(f"  expected_dir   : {data.get('expected_dir', '')}")
    print(f"  resolved       : {data.get('resolved', False)}")
    print(f"  session_id     : {data.get('session_id', '')}")
    print(f"  terminal_id    : {data.get('terminal_id', '')}")
    return 0

def reset(terminal_id: str) -> int:
    path = _state_path(terminal_id)
    if path.exists():
        path.unlink()
        print(f"Cleared skill context for '{terminal_id}'")
    else:
        print(f"No skill context to clear for '{terminal_id}'")
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("show", "reset"):
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]
    tid = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("CLAUDE_TERMINAL_ID", "default")

    fn = {"show": show, "reset": reset}[cmd]
    sys.exit(fn(tid))
