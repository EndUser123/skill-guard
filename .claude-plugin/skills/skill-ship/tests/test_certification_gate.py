"""Tests for CertificationGate - priority-ordered validation with fail-fast composition."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from validators.certification_gate import (
    CertificationGate,
    CertificationResult,
    check_certification,
)


def make_skill_content(total_lines: int = 20, include_all_required_fields: bool = True) -> str:
    frontmatter = [
        "---",
        "name: test-skill",
        "description: Test skill description",
        "version: 1.0.0",
        "category: testing",
        "triggers:",
        "  - /test-skill",
        '  - "test skill"',
        "aliases:",
        "  - /test-skill",
        "  - /ts",
    ]
    if include_all_required_fields:
        frontmatter.extend(
            [
                "suggest:",
                "  - /related-skill",
            ]
        )
    frontmatter.extend(
        [
            "depends_on_skills: []",
        ]
    )
    if include_all_required_fields:
        frontmatter.extend(
            [
                "workflow_steps:",
                "  - step_one: First step",
            ]
        )
    frontmatter.extend(
        [
            "enforcement: advisory",
            "---",
            "",
        ]
    )
    prefix = "\n".join(frontmatter)
    prefix_lines = len(prefix.splitlines())
    body_lines = max(total_lines - prefix_lines, 1)
    body = "\n".join([f"Line {i}" for i in range(body_lines)])
    return prefix + body


class TestCertificationResult:
    """Test suite for CertificationResult dataclass."""

    def test_is_valid_alias_for_is_complete(self):
        """is_valid should be an alias for is_complete."""
        result = CertificationResult(
            is_complete=True,
            status="PASS",
            confidence=1.0,
        )
        assert result.is_valid is True
        assert result.is_complete is True

    def test_is_valid_false_when_incomplete(self):
        """is_valid should be False when is_complete is False."""
        result = CertificationResult(
            is_complete=False,
            status="FAIL",
            confidence=0.0,
            checks_failed=["Context size check failed"],
        )
        assert result.is_valid is False

    def test_default_values(self):
        """Test default values for optional fields."""
        result = CertificationResult(
            is_complete=True,
            status="PASS",
            confidence=1.0,
        )
        assert result.checks_passed == []
        assert result.checks_failed == []
        assert result.verified_checks == []
        assert result.blocked_items == []
        assert result.reason is None


class TestCertificationGate:
    """Test suite for CertificationGate orchestrator."""

    def test_check_returns_certification_result(self, tmp_path):
        """check() should return a CertificationResult."""
        # Create SKILL.md with valid content
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(make_skill_content())

        gate = CertificationGate(tmp_path)
        result = gate.check()

        assert isinstance(result, CertificationResult)

    def test_pass_within_limits(self, tmp_path):
        """SKILL.md with 200 lines should pass certification."""
        skill_file = tmp_path / "SKILL.md"
        content = make_skill_content(total_lines=200)
        skill_file.write_text(content)

        result = check_certification(tmp_path)

        assert result.status == "PASS"
        assert result.is_complete is True
        assert result.confidence == 1.0

    def test_warn_at_300_lines(self, tmp_path):
        """SKILL.md with exactly 300 lines should pass (not warn)."""
        skill_file = tmp_path / "SKILL.md"
        content = make_skill_content(total_lines=300)
        skill_file.write_text(content)

        result = check_certification(tmp_path)

        assert result.status == "PASS"
        assert result.is_complete is True

    def test_warn_above_300_lines(self, tmp_path):
        """SKILL.md with 350 lines should return WARN (not FAIL)."""
        skill_file = tmp_path / "SKILL.md"
        content = make_skill_content(total_lines=350)
        skill_file.write_text(content)

        result = check_certification(tmp_path)

        assert result.status == "PASS"  # WARN doesn't block completion
        assert result.is_complete is True
        # Warnings are tracked in blocked_items
        assert len(result.blocked_items) > 0

    def test_warn_at_500_lines(self, tmp_path):
        """SKILL.md with exactly 500 lines should warn (not fail)."""
        skill_file = tmp_path / "SKILL.md"
        content = make_skill_content(total_lines=500)
        skill_file.write_text(content)

        result = check_certification(tmp_path)

        assert result.status == "PASS"  # WARN doesn't block
        assert result.is_complete is True

    def test_fail_above_500_lines(self, tmp_path):
        """SKILL.md with 550 lines should FAIL certification."""
        skill_file = tmp_path / "SKILL.md"
        content = make_skill_content(total_lines=550)
        skill_file.write_text(content)

        result = check_certification(tmp_path)

        assert result.status == "FAIL"
        assert result.is_complete is False
        assert result.confidence == 0.0

    def test_fail_missing_skill_file(self, tmp_path):
        """Missing SKILL.md should FAIL certification."""
        empty_dir = tmp_path / "empty_skill"
        empty_dir.mkdir()

        result = check_certification(empty_dir)

        assert result.status == "FAIL"
        assert result.is_complete is False

    def test_skip_context_size_check(self, tmp_path):
        """skip_checks parameter should skip context_size validation."""
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(make_skill_content())

        result = check_certification(tmp_path, skip_checks=["context_size"])

        # Should not fail with valid frontmatter when context_size is skipped
        assert result.status == "PASS"
        assert result.is_complete is True

    def test_partial_results_on_fail(self, tmp_path):
        """On FAIL, should still return partial results."""
        skill_file = tmp_path / "SKILL.md"
        content = make_skill_content(total_lines=550)
        skill_file.write_text(content)

        gate = CertificationGate(tmp_path)
        result = gate.check()

        # On FAIL, should have checks_failed tracking the context_size_check
        assert "context_size_check" in result.checks_failed
        # blocked_items should contain the failure message
        assert len(result.blocked_items) > 0

    def test_confidence_calculation(self, tmp_path):
        """Confidence should be calculated from checks_passed / total."""
        skill_file = tmp_path / "SKILL.md"
        content = make_skill_content(total_lines=200)
        skill_file.write_text(content)

        result = check_certification(tmp_path)

        # With no failures, confidence should be 1.0
        assert result.confidence == 1.0

    def test_blocked_items_tracks_warnings(self, tmp_path):
        """blocked_items should track warnings."""
        skill_file = tmp_path / "SKILL.md"
        content = make_skill_content(total_lines=350)
        skill_file.write_text(content)

        result = check_certification(tmp_path)

        # Warnings go to blocked_items
        assert len(result.blocked_items) > 0

    def test_reason_provided_on_failure(self, tmp_path):
        """reason field should be set on failure."""
        skill_file = tmp_path / "SKILL.md"
        content = make_skill_content(total_lines=550)
        skill_file.write_text(content)

        result = check_certification(tmp_path)

        assert result.reason is not None
        assert "500" in result.reason

    def test_convenience_function_alias(self, tmp_path):
        """check_certification should be alias for CertificationGate().check()."""
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(make_skill_content())

        result1 = check_certification(tmp_path)
        gate = CertificationGate(tmp_path)
        result2 = gate.check()

        assert result1.status == result2.status
        assert result1.is_complete == result2.is_complete

    def test_fail_missing_required_frontmatter_field(self, tmp_path):
        """Missing required frontmatter fields should block certification."""
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(make_skill_content(include_all_required_fields=False))

        result = check_certification(tmp_path)

        assert result.status == "FAIL"
        assert result.is_complete is False
        assert "frontmatter" in result.reason.lower()
        assert "suggest" in result.reason or "workflow_steps" in result.reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
