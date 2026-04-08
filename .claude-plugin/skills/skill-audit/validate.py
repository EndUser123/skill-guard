"""
validate.py — basic shape validation and frontmatter validation for /skill-audit.
"""

from __future__ import annotations

from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

# Valid enforcement tier values (must match skill_execution_state.py)
_VALID_ENFORCEMENT_VALUES = {"strict", "advisory", "none"}


def validate_shape(skill_path: Path) -> tuple[bool, str]:
    """
    Check that skill directory has minimum viable structure.
    Returns (is_valid, message).
    """
    if not skill_path.exists():
        return False, f"Skill path does not exist: {skill_path}"

    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False, "SKILL.md missing"

    content = skill_md.read_text()
    if len(content) < 100:
        return False, "SKILL.md appears truncated (< 100 chars)"

    # Must have at least name and description in frontmatter
    has_name = "name:" in content
    has_desc = "description:" in content
    if not (has_name and has_desc):
        return False, "SKILL.md missing required frontmatter fields (name, description)"

    return True, "OK"


def validate_frontmatter(skill_name: str, skills_dir: Path | None = None) -> list[str]:
    """Validate skill SKILL.md frontmatter for required fields.

    Checks that required fields are present and that enforcement value
    is one of the valid tiers (strict, advisory, none).

    Args:
        skill_name: Name of the skill to validate.
        skills_dir: Optional Path to skills directory. Defaults to P:/.claude/skills.

    Returns:
        List of warning strings for missing or invalid fields.
        Empty list if skill doesn't exist or has no issues.
    """
    warnings: list[str] = []
    if skills_dir is None:
        skills_dir = Path("P:/.claude/skills")
    skill_file = skills_dir / skill_name / "SKILL.md"

    # Return empty list for nonexistent skills (not an error condition)
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

        # Check required fields
        required_fields = ["name", "description", "version", "enforcement"]
        for field in required_fields:
            if field not in fm_data or not str(fm_data.get(field) or "").strip():
                warnings.append(f"Missing required frontmatter field: {field}")

        # Validate enforcement value
        enforcement = fm_data.get("enforcement", "")
        if enforcement and enforcement not in _VALID_ENFORCEMENT_VALUES:
            warnings.append(
                f"Invalid enforcement value '{enforcement}'; "
                f"must be one of: {', '.join(sorted(_VALID_ENFORCEMENT_VALUES))}"
            )

    except Exception:
        pass

    return warnings
