"""TDD contract auto-gate helper for skill-guard."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

from skill_guard.hook_compat import HookResult, register_hook
from .slash_command_observability import extract_command_name

_script_path = Path(__file__)
for _hooks_root in (
    Path(r"P:\.claude\hooks"),
    _script_path.parent.parent,
    _script_path.resolve().parent.parent,
):
    _hooks_root_str = str(_hooks_root)
    if _hooks_root_str not in sys.path:
        sys.path.insert(0, _hooks_root_str)

TDD_REQUIRED_SKILLS = frozenset({"code", "tdd"})
TDD_BYPASS_FLAGS = frozenset(
    {
        "--no-tdd",
        "--skip-tdd",
        "--bypass-tdd",
        "--no-test",
        "--bypass-test",
        "--bypass-contract",
    }
)
TDD_CONTRACT_BYPASS_ENV = "TDD_CONTRACT_BYPASS"

CODE_FILE_RE = re.compile(
    r"^/code\s+(?:'([^']+)'|\"([^\"]+)\"|([^\s]+?)(?:\s|$))",
    re.IGNORECASE,
)
IMPL_FILE_RE = re.compile(r"([a-zA-Z0-9_\-./\\]+\.py)")


def _is_tdd_bypassed(prompt: str) -> bool:
    normalized = prompt.strip().lower()
    for flag in TDD_BYPASS_FLAGS:
        if flag.lower() in normalized:
            return True
    return os.environ.get(TDD_CONTRACT_BYPASS_ENV) == "1"


def _extract_target_file(prompt: str, skill_name: str) -> str | None:
    normalized = prompt.strip()

    if skill_name == "code":
        match = CODE_FILE_RE.match(normalized)
        if match:
            for group in match.groups():
                if group and (group.endswith(".py") or "/" in group or "\\" in group):
                    return group
                if group:
                    py_match = re.search(r"([a-zA-Z0-9_\-./\\]+\.py)", group)
                    if py_match:
                        return py_match.group(1)

        py_match = re.search(r"([a-zA-Z0-9_\-./\\]+\.py)", normalized)
        if py_match:
            return py_match.group(1)

    elif skill_name == "tdd":
        parts = normalized.split()
        if len(parts) >= 2:
            target = parts[1]
            if target.startswith("--"):
                target = parts[2] if len(parts) > 2 else ""
            if target and (target.endswith(".py") or "/" in target or "\\" in target):
                return target
            if target:
                return f"src/{target}.py"

    return None


def _get_tdd_manager(context: Any):
    from tdd.tdd_phase_state import TDDPhaseStateManager

    session_id = str(getattr(context, "session_id", "") or "default")
    terminal_id = str(getattr(context, "terminal_id", "") or "default")

    return TDDPhaseStateManager(session_id=session_id, terminal_id=terminal_id)


def tdd_contract_auto_gate(context: Any) -> bool:
    """Auto-create TDD contract when TDD-requiring skill is invoked."""
    if _is_tdd_bypassed(str(getattr(context, "prompt", "") or "")):
        return False

    command = extract_command_name(str(getattr(context, "prompt", "") or ""))
    if not command or command.lower() not in TDD_REQUIRED_SKILLS:
        return False

    target_file = _extract_target_file(str(getattr(context, "prompt", "") or ""), command.lower())
    if not target_file:
        return False

    try:
        manager = _get_tdd_manager(context)
        existing = manager.get_phase(target_file)
        if existing is not None:
            return False
        manager.set_phase(target_file, "red")
    except Exception:
        pass

    return True


@register_hook("tdd_contract_auto_gate", priority=2.0)
def tdd_contract_auto_gate_hook(context: Any) -> HookResult:
    """Hook entrypoint for TDD contract bootstrapping."""
    tdd_contract_auto_gate(context)
    return HookResult.empty()


__all__ = ["tdd_contract_auto_gate", "tdd_contract_auto_gate_hook"]
