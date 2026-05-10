"""Regression tests for namespaced skill-guard hook entrypoints."""

from __future__ import annotations

import json
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
HOOKS_JSON = PACKAGE_ROOT / "hooks" / "hooks.json"


def test_skill_guard_hooks_use_namespaced_entrypoints() -> None:
    manifest = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for entries in manifest["hooks"].values()
        for match in entries
        for hook in match["hooks"]
    ]

    assert "python \"$CLAUDE_PLUGIN_ROOT/src/skill_guard/skill-guard_PreToolUse.py\"" in commands
    assert "python \"$CLAUDE_PLUGIN_ROOT/src/skill_guard/skill-guard_Stop.py\"" in commands
    assert "python \"$CLAUDE_PLUGIN_ROOT/src/skill_guard/skill-guard_UserPromptSubmit.py\"" in commands
    assert all("execution_hooks.py" not in command for command in commands)
    assert all("user_prompt_submit_hook.py" not in command for command in commands)
