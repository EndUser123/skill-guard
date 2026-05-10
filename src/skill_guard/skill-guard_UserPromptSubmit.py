#!/usr/bin/env python3
"""Namespaced UserPromptSubmit entrypoint for skill-guard."""

from __future__ import annotations

import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent
_SKILL_GUARD_SRC = Path(r"P:\packages\skill-guard\src")
_MAIN_HOOKS_DIR = Path(r"P:\.claude\hooks")

for _p in (_MAIN_HOOKS_DIR, _HOOKS_DIR, _SKILL_GUARD_SRC):
    if _p.exists():
        _s = str(_p)
        if _s in sys.path:
            sys.path.remove(_s)
        sys.path.insert(0, _s)

from skill_guard.user_prompt_submit_hook import user_prompt_submit_main


if __name__ == "__main__":
    user_prompt_submit_main()
