"""Skill metadata advisory logic for skill-guard."""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Any

from skill_guard.hook_compat import HookResult, register_hook
from .slash_command_observability import classify_slash_command
from skill_guard.skill_execution_state import _load_skill_frontmatter
from .slash_command_observability import extract_command_name
from skill_guard._skill_frontmatter_loader import classify_migration_status
from skill_guard.skill_auto_discovery import KNOWLEDGE_SKILLS

_script_path = Path(__file__)
for _hooks_root in (
    Path(r"$CLAUDE_ROOT/hooks"),
    _script_path.parent.parent,
    _script_path.resolve().parent.parent,
):
    _hooks_root_str = str(_hooks_root)
    if _hooks_root_str not in sys.path:
        sys.path.insert(0, _hooks_root_str)

try:
    from notification_queue import add_notification
except Exception:  # pragma: no cover - advisory should fail open

    def add_notification(
        notification_type: str,
        message: str,
        source: str = "unknown",
        priority: int = 1,
        session_id: str = "",
    ) -> None:  # type: ignore[no-redef]
        return None


logger = logging.getLogger(__name__)

_VALID_CONTRACT_TYPES = {"workflow", "output", "hybrid", "analysis"}


def _normalize_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _classify_contract(metadata: dict) -> str:
    explicit = str(metadata.get("contract_type", "") or "").strip().lower()
    if explicit in _VALID_CONTRACT_TYPES:
        return explicit

    workflow_signals = bool(
        _normalize_list(metadata.get("workflow_steps", []))
        or _normalize_list(metadata.get("required_phase_artifacts", []))
        or str(metadata.get("workflow_binding", "") or "").strip().lower()
        in {"exclusive", "hard"}
        or str(metadata.get("workflow_enforcement", "") or "").strip().lower()
        in {"hard", "strict"}
    )
    output_signals = bool(
        metadata.get("layer1_enforcement")
        or _normalize_list(metadata.get("required_markers", []))
        or _normalize_list(metadata.get("required_sections", []))
        or str(metadata.get("final_output_schema", "") or "").strip()
        or str(metadata.get("output_enforcement", "") or "").strip().lower()
        in {"hard", "strict", "warn", "advisory"}
    )

    if workflow_signals and output_signals:
        return "hybrid"
    if workflow_signals:
        return "workflow"
    if output_signals:
        return "output"
    return "analysis"


def _enhancement_reasons(metadata: dict) -> list[str]:
    """Return reasons a skill looks like it should be hardened."""
    reasons: list[str] = []
    contract_type = _classify_contract(metadata)

    workflow_steps = _normalize_list(metadata.get("workflow_steps", []))
    enforcement = str(metadata.get("enforcement", "") or "").strip().lower()
    workflow_binding = str(metadata.get("workflow_binding", "") or "").strip().lower()
    workflow_enforcement = str(metadata.get("workflow_enforcement", "") or "").strip().lower()
    required_phase_artifacts = _normalize_list(metadata.get("required_phase_artifacts", []))
    usage_markers = _normalize_list(metadata.get("usage_markers", []))
    output_enforcement = str(metadata.get("output_enforcement", "") or "").strip().lower()
    final_output_schema = str(metadata.get("final_output_schema", "") or "").strip()
    required_markers = _normalize_list(metadata.get("required_markers", []))
    required_sections = _normalize_list(metadata.get("required_sections", []))

    workflow_like = contract_type in {"workflow", "hybrid"} or bool(workflow_steps)
    output_like = contract_type in {"output", "hybrid"} or bool(
        metadata.get("layer1_enforcement")
        or required_markers
        or required_sections
        or final_output_schema
        or output_enforcement
    )

    if workflow_like:
        if enforcement in {"", "advisory", "none"}:
            reasons.append(
                f"enforcement is {enforcement or 'unset'} even though the skill declares workflow contract"
            )

        if workflow_binding not in {"exclusive"}:
            reasons.append(
                "workflow_binding is not exclusive, so lookalike workflows can satisfy the skill"
            )

        if workflow_enforcement not in {"hard", "strict"}:
            reasons.append(
                "workflow_enforcement is not hard, so phase execution is not strictly protected"
            )

        if not required_phase_artifacts:
            reasons.append(
                "required_phase_artifacts is missing, so the runtime cannot verify declared phases"
            )

    if output_like:
        if output_enforcement in {"", "advisory", "none"} and contract_type in {"output", "hybrid"}:
            reasons.append(
                f"output_enforcement is {output_enforcement or 'unset'} even though the skill declares an output contract"
            )
        if not (final_output_schema or required_markers or required_sections or usage_markers):
            reasons.append(
                "final_output_schema / required_markers / required_sections are missing, so the final artifact cannot be checked"
            )
        if metadata.get("layer1_enforcement") and not usage_markers:
            reasons.append(
                "layer1_enforcement is enabled but usage_markers is empty, so final output checks have no contract"
            )

    return reasons


def _build_warning(skill_name: str, metadata: dict, reasons: list[str]) -> str:
    """Build a concise enhancement advisory."""
    workflow_steps = _normalize_list(metadata.get("workflow_steps", []))
    lines = [
        f"⚠️ **Skill /{skill_name}** looks undercontracted and should be enhanced before relying on it.",
        "",
        f"**Detected workflow steps**: {len(workflow_steps)}",
        "",
        "**Why this matters**:",
    ]
    lines.extend(f"- {reason}" for reason in reasons)
    lines.extend(
        [
            "",
            "**Suggested enhancement**:",
            "- Add `contract_type: workflow` for phase-oriented skills and `contract_type: output` for artifact-oriented skills.",
            "- Add `workflow_binding: exclusive` and `workflow_enforcement: hard` for mandatory workflows.",
            "- Add `required_phase_artifacts` so the runtime can verify phase completion.",
            "- Add `output_enforcement: warn|hard` plus `final_output_schema` or `required_markers` for final artifact checks.",
            "- Add `layer1_enforcement: true` plus `usage_markers` when the final output shape must be checked end-to-end.",
            "",
            "If this skill is central to the task, harden its SKILL.md before treating the workflow as authoritative.",
        ]
    )
    return "\n".join(lines)


def _build_notification_message(skill_name: str, reasons: list[str]) -> str:
    """Build a short user-facing notification for the statusline."""
    if not reasons:
        return f"⚠️ /{skill_name} needs skill contract hardening."

    summary = "; ".join(reasons[:2])
    if len(reasons) > 2:
        summary += f" (+{len(reasons) - 2} more)"

    message = f"⚠️ /{skill_name} needs skill contract hardening: {summary}"
    if len(message) > 180:
        message = message[:177].rstrip() + "..."
    return message


def _get_session_id(context: Any) -> str:
    """Return the best available session identity for notification scoping."""
    data = getattr(context, "data", {}) or {}
    for key in ("session_id", "sessionId", "CLAUDE_SESSION_ID"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if getattr(context, "session_id", ""):
        return str(getattr(context, "session_id")).strip()
    return ""


def skill_metadata_advisory(context: Any) -> str | None:
    """Warn when an invoked skill still looks like it needs contract hardening."""
    prompt = str(getattr(context, "prompt", "") or "")
    data = getattr(context, "data", {}) or {}

    candidate = extract_command_name(prompt)
    if not candidate:
        candidate = extract_command_name(str(data.get("userMessage", "")))
    if not candidate:
        return None

    metadata = _load_skill_frontmatter(candidate)
    if metadata is None:
        metadata = {}

    # Skip migration advisories for knowledge/reference skills — these are
    # documentation-only and have no execution contract to migrate.
    is_knowledge = (
        candidate in KNOWLEDGE_SKILLS
        or metadata.get("category") in ("knowledge", "meta")
        or not metadata
    )

    # Emit migration-status advisory notification (non-blocking)
    if not is_knowledge:
        status = classify_migration_status(metadata)
        if status == "UNMIGRATED":
            try:
                add_notification(
                    notification_type="warning",
                    message=(
                        f"Skill '/{candidate}' appears to be legacy and not yet migrated to the execution-contract model. "
                        f"Hint: run '/migrate-skill-ef {candidate}' to audit or generate a migration plan. "
                        f"Contract-era skills should use the -ct suffix naming standard."
                    ),
                    source=f"skill_metadata_advisory:{candidate}",
                    priority=1,
                    session_id=_get_session_id(context),
                )
            except Exception:
                pass
        elif status == "PARTIALLY_MIGRATED":
            try:
                add_notification(
                    notification_type="info",
                    message=(
                        f"Skill '/{candidate}' has some contract metadata but appears incomplete for its contract type. "
                        f"Hint: run '/migrate-skill-ef {candidate}' to inspect missing fields and generate a patch plan."
                    ),
                    source=f"skill_metadata_advisory:{candidate}",
                    priority=1,
                    session_id=_get_session_id(context),
                )
            except Exception:
                pass
    # MIGRATED and knowledge skills: silent, no migration notification

    reasons = _enhancement_reasons(metadata)
    if not reasons:
        return None

    warning = _build_warning(candidate, metadata, reasons)
    notification = _build_notification_message(candidate, reasons)
    logger.info("Skill metadata advisory triggered for /%s", candidate)
    try:
        add_notification(
            notification_type="warning",
            message=notification,
            source=f"skill_metadata_advisory:enhancement:{candidate}",
            priority=2,
            session_id=_get_session_id(context),
        )
    except Exception:
        pass
    return warning


@register_hook("skill_metadata_advisory", priority=5.0)
def skill_metadata_advisory_hook(context: Any) -> HookResult:
    """Hook entrypoint that returns advisory context when warranted."""
    prompt = str(getattr(context, "prompt", "") or "")
    data = getattr(context, "data", {}) or {}

    candidate = extract_command_name(prompt)
    if not candidate:
        candidate = extract_command_name(str(data.get("userMessage", "")))
    if not candidate:
        return HookResult.empty()

    classification = classify_slash_command(candidate)
    if classification["command_family"] not in {"skill", "local_command"}:
        return HookResult.empty()

    warning = skill_metadata_advisory(context)
    if not warning:
        return HookResult.empty()

    return HookResult(context=warning, tokens=len(warning) // 4, priority=5.0)


__all__ = ["skill_metadata_advisory", "skill_metadata_advisory_hook"]
