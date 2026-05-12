#!/usr/bin/env python3
"""Namespaced PreToolUse entrypoint for skill-guard."""

from __future__ import annotations

import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent
_SKILL_GUARD_SRC = Path(__file__).resolve().parents[1]
_MAIN_HOOKS_DIR = Path.home() / ".claude" / "hooks"

for _p in (_MAIN_HOOKS_DIR, _HOOKS_DIR, _SKILL_GUARD_SRC):
    if _p.exists():
        _s = str(_p)
        if _s in sys.path:
            sys.path.remove(_s)
        sys.path.insert(0, _s)

from skill_guard.execution_hooks import pre_tool_use_main


if __name__ == "__main__":
    pre_tool_use_main()
