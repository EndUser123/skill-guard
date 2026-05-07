r"""
skill_frontmatter_loader.py
===========================

Pure frontmatter parsing — no state, no I/O on other files.

Provides:
- _load_skill_frontmatter(skill_name) -> dict
- _normalize_string_list(value) -> list[str]
- _infer_contract_type(frontmatter) -> str
- _validate_skill_frontmatter(skill_name) -> list[str]
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

try:
    import yaml
except ImportError:
    yaml = None  # pyyaml declared as optional dependency

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_CONTRACT_TYPES = {"workflow", "output", "hybrid", "analysis"}

# Contract-era types — distinct from legacy classification above.
# A skill with contract_type=workflow (legacy) is UNMIGRATED;
# one with contract_type=workflow-execution (contract-era) can be MIGRATED.
_CONTRACT_ERA_TYPES = frozenset({"workflow-execution", "structured-output", "hybrid"})

_VALID_ENFORCEMENT_VALUES = {"strict", "advisory", "none"}


def _normalize_string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _infer_contract_type(frontmatter: dict[str, Any]) -> str:
    explicit = str(frontmatter.get("contract_type", "") or "").strip().lower()
    if explicit in _VALID_CONTRACT_TYPES:
        return explicit

    workflow_signals = bool(
        _normalize_string_list(frontmatter.get("workflow_steps", []))
        or _normalize_string_list(frontmatter.get("required_phase_artifacts", []))
        or str(frontmatter.get("workflow_binding", "") or "").strip().lower()
        in {"exclusive", "hard"}
        or str(frontmatter.get("workflow_enforcement", "") or "").strip().lower()
        in {"hard", "strict"}
    )
    output_signals = bool(
        bool(frontmatter.get("layer1_enforcement"))
        or _normalize_string_list(frontmatter.get("required_markers", []))
        or _normalize_string_list(frontmatter.get("required_sections", []))
        or str(frontmatter.get("final_output_schema", "") or "").strip()
        or str(frontmatter.get("output_enforcement", "") or "").strip().lower()
        in {"hard", "strict", "warn", "advisory"}
    )

    if workflow_signals and output_signals:
        return "hybrid"
    if workflow_signals:
        return "workflow"
    if output_signals:
        return "output"
    return "analysis"


def _load_skill_frontmatter(skill_name: str) -> dict[str, Any] | None:
    """Load execution metadata from a skill's SKILL.md frontmatter.

    Reads the skill's YAML frontmatter and extracts execution-related
    metadata fields used by the skill guard.

    Args:
        skill_name: Skill name (without slash)

    Returns:
        Dict with frontmatter fields used by execution/governance tracking,
        or None if the file cannot be read or parsed.
    """
    result: dict[str, Any] = {
        "contract_type": "analysis",
        "allowed_first_tools": [],
        "required_first_command_patterns": [],
        "required_first_command_hint": "",
        "enforcement": "",
        "enforcement_tier": "",
        "workflow_steps": [],
        "completion_criteria": [],
        "required_phase_artifacts": [],
        "workflow_binding": "",
        "workflow_enforcement": "",
        "phase_recovery_mode": "",
        "user_override": "",
        "layer1_enforcement": False,
        "usage_markers": [],
        "output_enforcement": "",
        "final_output_schema": "",
        "required_markers": [],
        "required_sections": [],
    }
    skill_dir = Path(r"P:\\\\.claude/skills") / skill_name
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        return None

    if yaml is None:
        return None

    try:
        content = skill_file.read_text(encoding="utf-8", errors="replace")
        parts = content.split("---")
        if len(parts) < 3:
            return None
        fm_data = yaml.safe_load(parts[1])
        # Distinguish YAML parse errors from wrong-type results:
        # - YAMLError (parse failure) -> return None
        # - non-dict YAML -> return default dict (distinguishable)
        if not isinstance(fm_data, dict):
            return None if fm_data is None else result
        result["contract_type"] = _infer_contract_type(fm_data)
        aft = fm_data.get("allowed_first_tools", [])
        if isinstance(aft, list):
            result["allowed_first_tools"] = [str(t) for t in aft]
        elif isinstance(aft, str) and aft.strip():
            result["allowed_first_tools"] = [aft.strip()]
        rfcp = fm_data.get("required_first_command_patterns", [])
        if isinstance(rfcp, list):
            result["required_first_command_patterns"] = [
                str(pattern) for pattern in rfcp if str(pattern).strip()
            ]
        elif isinstance(rfcp, str) and rfcp.strip():
            result["required_first_command_patterns"] = [rfcp.strip()]
        rfch = fm_data.get("required_first_command_hint", "")
        if isinstance(rfch, str):
            result["required_first_command_hint"] = rfch.strip()
        enforcement = fm_data.get("enforcement", "")
        if isinstance(enforcement, str):
            result["enforcement"] = enforcement.strip()
        output_enforcement = fm_data.get("output_enforcement", "")
        if isinstance(output_enforcement, str):
            result["output_enforcement"] = output_enforcement.strip()
        enforcement_tier = fm_data.get("enforcement_tier", "")
        if isinstance(enforcement_tier, str):
            result["enforcement_tier"] = enforcement_tier.strip()
        completion_criteria = fm_data.get("completion_criteria", [])
        if isinstance(completion_criteria, list):
            result["completion_criteria"] = completion_criteria
        final_output_schema = fm_data.get("final_output_schema", "")
        if isinstance(final_output_schema, str):
            result["final_output_schema"] = final_output_schema.strip()
        rpa = fm_data.get("required_phase_artifacts", [])
        if isinstance(rpa, list):
            result["required_phase_artifacts"] = [
                str(artifact) for artifact in rpa if str(artifact).strip()
            ]
        elif isinstance(rpa, str) and rpa.strip():
            result["required_phase_artifacts"] = [rpa.strip()]
        wf_steps = fm_data.get("workflow_steps", [])
        if isinstance(wf_steps, list):
            normalized_steps: list[str] = []
            for step in wf_steps:
                if isinstance(step, str):
                    text = step.strip()
                    if text:
                        normalized_steps.append(text)
                elif isinstance(step, dict):
                    for key, value in step.items():
                        key_text = str(key).strip()
                        value_text = str(value).strip() if value is not None else ""
                        if key_text and value_text:
                            normalized_steps.append(f"{key_text}: {value_text}")
                        elif key_text:
                            normalized_steps.append(key_text)
                        elif value_text:
                            normalized_steps.append(value_text)
                elif step is not None:
                    text = str(step).strip()
                    if text:
                        normalized_steps.append(text)
            result["workflow_steps"] = normalized_steps
        elif isinstance(wf_steps, str) and wf_steps.strip():
            result["workflow_steps"] = [wf_steps.strip()]
        workflow_binding = fm_data.get("workflow_binding", "")
        if isinstance(workflow_binding, str):
            result["workflow_binding"] = workflow_binding.strip()
        workflow_enforcement = fm_data.get("workflow_enforcement", "")
        if isinstance(workflow_enforcement, str):
            result["workflow_enforcement"] = workflow_enforcement.strip()
        phase_recovery_mode = fm_data.get("phase_recovery_mode", "")
        if isinstance(phase_recovery_mode, str):
            result["phase_recovery_mode"] = phase_recovery_mode.strip()
        user_override = fm_data.get("user_override", "")
        if isinstance(user_override, str):
            result["user_override"] = user_override.strip()
        usage_markers = fm_data.get("usage_markers", [])
        if isinstance(usage_markers, list):
            result["usage_markers"] = [
                str(marker) for marker in usage_markers if str(marker).strip()
            ]
        elif isinstance(usage_markers, str) and usage_markers.strip():
            result["usage_markers"] = [usage_markers.strip()]
        result["layer1_enforcement"] = bool(fm_data.get("layer1_enforcement"))
        result["required_markers"] = _normalize_string_list(fm_data.get("required_markers", []))
        result["required_sections"] = _normalize_string_list(
            fm_data.get("required_sections", [])
        )
    except (yaml.YAMLError, ImportError):
        return None
    return result


def _validate_skill_frontmatter(skill_name: str) -> list[str]:
    """Validate skill SKILL.md frontmatter for required fields.

    Checks that required fields are present and that enforcement value
    is one of the valid tiers (strict, advisory, none).

    Args:
        skill_name: Name of the skill to validate.

    Returns:
        List of warning strings for missing or invalid fields.
        Empty list if skill doesn't exist or has no issues.
    r"""
    warnings: list[str] = []
    skill_dir = Path(r"P:\\\\.claude/skills") / skill_name
    skill_file = skill_dir / "SKILL.md"

    if not skill_file.exists():
        return warnings

    if yaml is None:
        return warnings

    try:
        content = skill_file.read_text(encoding="utf-8", errors="replace")
        parts = content.split("---")
        if len(parts) < 3:
            return warnings
        fm_data = yaml.safe_load(parts[1])
        if not isinstance(fm_data, dict):
            return warnings

        required_fields = ["name", "description", "version", "enforcement"]
        for field in required_fields:
            if field not in fm_data or not str(fm_data.get(field) or "").strip():
                warnings.append(f"Missing required frontmatter field: {field}")

        enforcement = fm_data.get("enforcement", "")
        if enforcement and enforcement not in _VALID_ENFORCEMENT_VALUES:
            warnings.append(
                f"Invalid enforcement value '{enforcement}'; "
                f"must be one of: {', '.join(sorted(_VALID_ENFORCEMENT_VALUES))}"
            )

        workflow_steps = fm_data.get("workflow_steps", [])
        normalized_workflow_steps: list[str] = []
        if isinstance(workflow_steps, list):
            for step in workflow_steps:
                if isinstance(step, str):
                    text = step.strip()
                    if text:
                        normalized_workflow_steps.append(text)
                elif isinstance(step, dict):
                    for key, value in step.items():
                        key_text = str(key).strip()
                        value_text = str(value).strip() if value is not None else ""
                        if key_text and value_text:
                            normalized_workflow_steps.append(f"{key_text}: {value_text}")
                        elif key_text:
                            normalized_workflow_steps.append(key_text)
                        elif value_text:
                            normalized_workflow_steps.append(value_text)
                elif step is not None:
                    text = str(step).strip()
                    if text:
                        normalized_workflow_steps.append(text)
        required_first_command_patterns = fm_data.get(
            "required_first_command_patterns", []
        )
        workflow_binding = str(fm_data.get("workflow_binding", "") or "").strip().lower()
        required_phase_artifacts = fm_data.get("required_phase_artifacts", [])
        if normalized_workflow_steps and not required_first_command_patterns:
            if required_phase_artifacts or workflow_binding in {"exclusive", "hard"}:
                return warnings
            warnings.append(
                "Missing required_first_command_patterns for a workflow skill; "
                "the first backend command will not be enforced."
            )

    except Exception:
        pass

    return warnings


def _has_contract_field(frontmatter: dict[str, Any] | None, field: str) -> bool:
    """Return True if the field exists and has a non-None value.

    For list fields (required_artifacts, response_requirements), an empty list
    is treated as explicitly set — the skill has declared its intent to require
    zero artifacts / no structural requirements. This is distinct from the field
    being absent (not yet migrated).
    """
    if frontmatter is None:
        return False
    val = frontmatter.get(field)
    if val is None:
        return False
    if isinstance(val, list):
        return True  # empty list is an explicit declaration, not absent
    if isinstance(val, str):
        return bool(val.strip())
    return True


def is_contract_era(frontmatter: dict[str, Any] | None) -> bool:
    """Return True if contract_type is a contract-era value (not legacy)."""
    if frontmatter is None:
        return False
    ct = str(frontmatter.get("contract_type", "") or "").strip().lower()
    return ct in _CONTRACT_ERA_TYPES


def classify_migration_status(
    frontmatter: dict[str, Any] | None,
    validation_warnings: list[str] | None = None,
) -> Literal["UNMIGRATED", "PARTIALLY_MIGRATED", "MIGRATED"]:
    """Classify a skill's migration readiness for the execution-contract runtime.

    Uses only the parsed frontmatter dict and an optional list of validation warnings
    generated by _validate_skill_frontmatter(). No I/O, no state access.

    Rules
    -----
    UNMIGRATED:
        - contract_type is absent OR not in the contract-era set
          (workflow-execution, structured-output, hybrid), AND
        - contract-era completion fields are absent
          (required_artifacts, response_requirements).

    PARTIALLY_MIGRATED:
        - contract_type is a contract-era value, AND
        - at least one of these is true:
            - workflow-execution is missing required_artifacts
            - structured-output is missing response_requirements
            - hybrid is missing either required_artifacts or response_requirements
            - allowed_tools_now is absent for an execution-oriented skill
            - validation warnings are present

    MIGRATED:
        - contract_type is a contract-era value, AND
        - the core completion field for that type is present
          (required_artifacts for workflow-execution,
           response_requirements for structured-output,
           both for hybrid), AND
        - no relevant validation warnings are present.
    """
    if frontmatter is None:
        return "UNMIGRATED"

    contract_type = str(frontmatter.get("contract_type", "") or "").strip().lower()
    is_era = is_contract_era(frontmatter)

    if not is_era:
        has_ra = _has_contract_field(frontmatter, "required_artifacts")
        has_rr = _has_contract_field(frontmatter, "response_requirements")
        if has_ra or has_rr:
            # Has completion fields but no contract_type — partial.
            return "PARTIALLY_MIGRATED"
        return "UNMIGRATED"

    # contract_type is one of workflow-execution, structured-output, hybrid
    has_ra = _has_contract_field(frontmatter, "required_artifacts")
    has_rr = _has_contract_field(frontmatter, "response_requirements")

    if contract_type == "workflow-execution":
        return "MIGRATED" if has_ra else "PARTIALLY_MIGRATED"
    elif contract_type == "structured-output":
        return "MIGRATED" if has_rr else "PARTIALLY_MIGRATED"
    elif contract_type == "hybrid":
        return "MIGRATED" if (has_ra and has_rr) else "PARTIALLY_MIGRATED"

    return "PARTIALLY_MIGRATED"


def build_migration_result(
    skill_name: str,
    frontmatter: dict[str, Any] | None,
    validation_warnings: list[str] | None = None,
) -> dict:
    """Build a reusable migration result dict for migration helpers and CLIs.

    Maps classify_migration_status() to a structured dict with action, reason,
    missing_fields, and validation_warnings. Used to return a cheap no-op for
    already-migrated skills without scanning the filesystem.

    Returns
    -------
    {
        "skill": str,
        "status": "UNMIGRATED" | "PARTIALLY_MIGRATED" | "MIGRATED",
        "action": "none" | "plan",
        "reason": str,
        "missing_fields": list[str],
        "validation_warnings": list[str],
    }

    action is "none" for MIGRATED (cheap no-op), "plan" otherwise.
    """
    if frontmatter is None:
        return {
            "skill": skill_name,
            "status": "UNMIGRATED",
            "action": "plan",
            "reason": "Skill frontmatter could not be loaded. Manual audit required.",
            "missing_fields": ["*"],
            "validation_warnings": validation_warnings or [],
        }

    status = classify_migration_status(frontmatter, validation_warnings)
    warnings = validation_warnings or []

    missing: list[str] = []
    contract_type = str(frontmatter.get("contract_type", "") or "").strip().lower()

    if not is_contract_era(frontmatter):
        if not _has_contract_field(frontmatter, "required_artifacts"):
            missing.append("required_artifacts")
        if not _has_contract_field(frontmatter, "response_requirements"):
            missing.append("response_requirements")
    else:
        if contract_type in ("workflow-execution", "hybrid"):
            if not _has_contract_field(frontmatter, "required_artifacts"):
                missing.append("required_artifacts")
        if contract_type in ("structured-output", "hybrid"):
            if not _has_contract_field(frontmatter, "response_requirements"):
                missing.append("response_requirements")

    if status == "MIGRATED":
        return {
            "skill": skill_name,
            "status": status,
            "action": "none",
            "reason": "Skill already has contract_type and required contract fields; no migration needed.",
            "missing_fields": missing,
            "validation_warnings": warnings,
        }
    if status == "PARTIALLY_MIGRATED":
        return {
            "skill": skill_name,
            "status": status,
            "action": "plan",
            "reason": f"Skill has contract_type but is missing {len(missing)} contract field(s): {', '.join(missing)}.",
            "missing_fields": missing,
            "validation_warnings": warnings,
        }
    return {
        "skill": skill_name,
        "status": status,
        "action": "plan",
        "reason": "Skill is legacy with no contract metadata. Propose full migration plan.",
        "missing_fields": missing,
        "validation_warnings": warnings,
    }