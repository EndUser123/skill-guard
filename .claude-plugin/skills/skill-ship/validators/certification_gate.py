"""CertificationGate - Priority-ordered validation with fail-fast composition.

GTO v3 Pattern: CertificationGate orchestrates multiple validators with:
- Priority-ordered checks (first fail → early return)
- Partial results (checks_passed, checks_failed) even on failure
- Typed result dataclasses per validator
- Convenience function + class duality for simple/advanced use

This module implements the same architectural pattern as ViabilityGate in GTO v3,
adapted for skill certification workflow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from .context_size import ValidationResult, validate_context_size

_REQUIRED_FRONTMATTER_FIELDS = (
    "name",
    "description",
    "version",
    "category",
    "triggers",
    "aliases",
    "suggest",
    "depends_on_skills",
    "workflow_steps",
    "enforcement",
)
_VALID_ENFORCEMENT_VALUES = {"strict", "advisory", "none"}


@dataclass
class CertificationResult:
    """Result of skill certification check.

    GTO v3 Result Pattern:
        - status: Literal["PASS", "FAIL"] for overall result
        - is_complete: True if all certification checks passed
        - checks_passed: List of checks that passed
        - checks_failed: List of checks that failed (blocks completion)
        - confidence: Confidence score (0.0-1.0) based on checks passed
        - verified_checks: List of specific verifications completed
        - blocked_items: List of items blocking certification
    """

    is_complete: bool
    status: Literal["PASS", "FAIL"]
    confidence: float  # 0.0-1.0
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)
    verified_checks: list[str] = field(default_factory=list)
    blocked_items: list[str] = field(default_factory=list)
    reason: str | None = None

    @property
    def is_valid(self) -> bool:
        """Alias for is_complete for API compatibility."""
        return self.is_complete


class CertificationGate:
    """Orchestrate skill certification with priority-ordered validation.

    Validates skills through multiple checkers in priority order:
    1. Context size check (Phase 3b - Code Quality)
    2. YAML frontmatter required-field check
    3. Future: Trigger accuracy check

    Early return on first FAIL (fail-fast).
    Partial results returned even on failure.

    GTO v3 Gate Pattern:
        - Priority-ordered checks
        - Early return on critical failure
        - Partial results for non-critical failures
        - Typed result dataclasses
    """

    def __init__(self, skill_path: str | Path | None = None):
        """Initialize certification gate.

        Args:
            skill_path: Path to skill directory (defaults to cwd)
        """
        self.skill_path = Path(skill_path) if skill_path else Path.cwd()

    def check(self, skip_checks: list[str] | None = None) -> CertificationResult:
        """Run all certification checks in priority order.

        Args:
            skip_checks: Optional list of check names to skip

        Returns:
            CertificationResult with pass/fail status and details
        """
        skip_checks = skip_checks or []
        checks_passed = []
        checks_failed = []
        verified_checks = []
        blocked_items = []

        # Priority 1: Context size validation (Phase 3b)
        if "context_size" not in skip_checks:
            context_result = self._check_context_size()

            # Map ValidationResult to CertificationResult fields
            if context_result.status == "fail":
                checks_failed.append("context_size_check")
                # Early return on critical failure
                return CertificationResult(
                    is_complete=False,
                    status="FAIL",
                    confidence=0.0,
                    checks_passed=checks_passed,
                    checks_failed=checks_failed,
                    verified_checks=verified_checks,
                    blocked_items=context_result.findings,
                    reason=context_result.findings[0]
                    if context_result.findings
                    else "Context size check failed",
                )
            elif context_result.status == "warn":
                # Non-critical - continue but track as blocked items
                checks_passed.append("context_size_check")
                blocked_items.extend(context_result.findings)
            else:
                checks_passed.append("context_size_check")

        # Priority 2: YAML frontmatter validation (future)
        if "frontmatter" not in skip_checks:
            frontmatter_result = self._check_frontmatter()

            if frontmatter_result.status == "fail":
                checks_failed.append("frontmatter_check")
                return CertificationResult(
                    is_complete=False,
                    status="FAIL",
                    confidence=0.0,
                    checks_passed=checks_passed,
                    checks_failed=checks_failed,
                    verified_checks=verified_checks,
                    blocked_items=frontmatter_result.findings,
                    reason=frontmatter_result.findings[0]
                    if frontmatter_result.findings
                    else "Frontmatter check failed",
                )
            elif frontmatter_result.status == "warn":
                checks_passed.append("frontmatter_check")
                blocked_items.extend(frontmatter_result.findings)
            else:
                checks_passed.append("frontmatter_check")

        # Priority 3: Trigger accuracy (future)
        # if "triggers" not in skip_checks:
        #     ...

        # All checks passed or only warnings
        is_complete = len(checks_failed) == 0
        confidence = self._calculate_confidence(checks_passed, checks_failed)

        return CertificationResult(
            is_complete=is_complete,
            status="PASS" if is_complete else "FAIL",
            confidence=confidence,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            verified_checks=verified_checks,
            blocked_items=blocked_items,
        )

    def _check_context_size(self) -> ValidationResult:
        """Run context size validation.

        Args:
            None

        Returns:
            ValidationResult from context_size validator
        """
        return validate_context_size(str(self.skill_path))

    def _check_frontmatter(self) -> ValidationResult:
        """Validate required SKILL.md frontmatter fields.

        This is intentionally strict about presence of the local schema's required
        fields. New skills should not be declared complete if they omit fields that
        the skill-ship schema marks as mandatory.
        """
        skill_file = self.skill_path / "SKILL.md"
        if not skill_file.exists():
            return ValidationResult(status="fail", findings=[f"SKILL.md not found at {skill_file}"])

        try:
            content = skill_file.read_text(encoding="utf-8")
        except Exception as exc:
            return ValidationResult(status="fail", findings=[f"Error reading SKILL.md: {exc}"])

        frontmatter = _extract_frontmatter(content)
        if frontmatter is None:
            return ValidationResult(
                status="fail",
                findings=["SKILL.md missing YAML frontmatter block"],
            )

        values = _extract_top_level_frontmatter_values(frontmatter)
        missing = [field for field in _REQUIRED_FRONTMATTER_FIELDS if field not in values]
        if missing:
            return ValidationResult(
                status="fail",
                findings=[
                    "SKILL.md frontmatter missing required field(s): "
                    + ", ".join(missing)
                ],
            )

        enforcement = values.get("enforcement", "").strip()
        if enforcement not in _VALID_ENFORCEMENT_VALUES:
            return ValidationResult(
                status="fail",
                findings=[
                    "SKILL.md frontmatter has invalid enforcement value: "
                    f"{enforcement or '<empty>'}"
                ],
            )

        return ValidationResult(status="pass")

    def _calculate_confidence(self, checks_passed: list[str], checks_failed: list[str]) -> float:
        """Calculate confidence score based on checks passed.

        Args:
            checks_passed: List of passed check names
            checks_failed: List of failed check names

        Returns:
            Confidence score 0.0-1.0
        """
        total = len(checks_passed) + len(checks_failed)
        if total == 0:
            return 0.5  # Neutral if no checks ran
        return len(checks_passed) / total


# Convenience function for simple API
def check_certification(
    skill_path: str | Path | None = None,
    skip_checks: list[str] | None = None,
) -> CertificationResult:
    """Quick certification check for skill.

    Args:
        skill_path: Path to skill directory (defaults to cwd)
        skip_checks: Optional list of check names to skip

    Returns:
        CertificationResult indicating if skill is certified

    Example:
        >>> result = check_certification("skills/my-skill")
        >>> if result.is_complete:
        ...     print(f"Certified! Confidence: {result.confidence:.0%}")
    """
    gate = CertificationGate(skill_path)
    return gate.check(skip_checks)


def _extract_frontmatter(content: str) -> str | None:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index])
    return None


def _extract_top_level_frontmatter_values(frontmatter: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in frontmatter.splitlines():
        if not raw_line or raw_line.startswith((" ", "\t", "-")):
            continue
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        values[key.strip()] = value.strip()
    return values
