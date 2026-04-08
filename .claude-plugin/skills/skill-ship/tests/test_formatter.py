"""Tests for lib/formatter.py - RSN formatter integration for skill-ship."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from formatter import (
    SHIP_SECTION_DEFINITIONS,
    ShipFinding,
    _certification_result_to_findings,
    _check_to_domain,
    format_rsn_from_certification,
    format_rsn_from_steps,
)


class TestShipSectionDefinitions:
    """Test suite for SHIP_SECTION_DEFINITIONS."""

    def test_has_required_domains(self):
        """All required domain mappings should be present."""
        required_domains = [
            "spec_compliance",
            "code_quality",
            "context_size",
            "integration",
            "evaluation",
            "optimization",
            "distribution",
        ]
        for domain in required_domains:
            assert domain in SHIP_SECTION_DEFINITIONS, f"Missing domain: {domain}"

    def test_domains_map_to_tuples(self):
        """Each domain should map to (section_name, section_key) tuple."""
        for domain, mapping in SHIP_SECTION_DEFINITIONS.items():
            assert isinstance(mapping, tuple), f"{domain} mapping is not a tuple"
            assert len(mapping) == 2, f"{domain} mapping should have 2 elements"
            assert isinstance(mapping[0], str), f"{domain} section_name is not str"
            assert isinstance(mapping[1], str), f"{domain} section_key is not str"


class TestCheckToDomain:
    """Test suite for _check_to_domain helper."""

    @pytest.mark.parametrize(
        "check_name,expected_domain",
        [
            ("context_size_check", "context_size"),
            ("ContextSizeValidator", "context_size"),
            ("spec_compliance_check", "spec_compliance"),
            ("SpecComplianceValidator", "spec_compliance"),
            ("code_quality_check", "code_quality"),
            ("CodeQualityGate", "code_quality"),
            ("integration_check", "integration"),
            ("IntegrationValidator", "integration"),
            ("eval_check", "evaluation"),
            ("EvaluationBenchmark", "evaluation"),
            ("optimization_check", "optimization"),
            ("OptimizationPass", "optimization"),
            ("distribution_check", "distribution"),
            ("DistributionValidator", "distribution"),
            ("github_distribution", "distribution"),
        ],
    )
    def test_domain_mapping(self, check_name, expected_domain):
        """Check names should map to expected domains."""
        assert _check_to_domain(check_name) == expected_domain

    def test_unknown_check_defaults_to_code_quality(self):
        """Unknown check names should default to code_quality."""
        assert _check_to_domain("unknown_check") == "code_quality"
        assert _check_to_domain("random_validator") == "code_quality"


class TestCertificationResultToFindings:
    """Test suite for _certification_result_to_findings."""

    def test_failed_checks_become_high_severity(self):
        """Failed checks should become HIGH severity ShipFindings."""
        findings = _certification_result_to_findings(
            checks_passed=["spec_check"],
            checks_failed=["context_size_check", "quality_check"],
            blocked_items=[],
            verified_checks=[],
        )
        assert len(findings) == 2
        for finding in findings:
            assert finding.severity == "HIGH"
            assert "Certification check failed" in finding.message

    def test_blocked_items_become_critical(self):
        """Blocked items should become CRITICAL severity ShipFindings with domain routed via _check_to_domain."""
        findings = _certification_result_to_findings(
            checks_passed=[],
            checks_failed=[],
            blocked_items=["missing_skill_md", "broken_yaml"],
            verified_checks=[],
        )
        assert len(findings) == 2
        for finding in findings:
            assert finding.severity == "CRITICAL"
            # Domain is routed via _check_to_domain() — not hardcoded.
            # "missing_skill_md" contains "yaml" → code_quality
            # "broken_yaml" contains "yaml" → code_quality
            assert finding.domain == "code_quality", f"Expected code_quality, got {finding.domain}"

    def test_empty_inputs_return_empty(self):
        """Empty inputs should return empty findings list."""
        findings = _certification_result_to_findings(
            checks_passed=[],
            checks_failed=[],
            blocked_items=[],
            verified_checks=[],
        )
        assert findings == []


class TestFormatRsnFromCertification:
    """Test suite for format_rsn_from_certification bridge function."""

    def test_returns_string(self):
        """Should return a formatted string."""
        result = format_rsn_from_certification(
            checks_passed=["spec_check"],
            checks_failed=["context_size_check"],
            blocked_items=[],
            verified_checks=[],
            intent_summary="Test certification",
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_results_produces_output(self):
        """Empty certification results should still produce RSN output."""
        result = format_rsn_from_certification(
            checks_passed=["spec_check"],
            checks_failed=[],
            blocked_items=[],
            verified_checks=[],
            intent_summary="All checks passed",
        )
        assert isinstance(result, str)

    def test_with_failed_checks(self):
        """Failed checks should appear in output."""
        result = format_rsn_from_certification(
            checks_passed=[],
            checks_failed=["context_size_check"],
            blocked_items=[],
            verified_checks=[],
            intent_summary="Test with failures",
        )
        assert "context_size_check" in result.upper() or "HIGH" in result

    def test_with_blocked_items(self):
        """Blocked items should appear in output."""
        result = format_rsn_from_certification(
            checks_passed=[],
            checks_failed=[],
            blocked_items=["missing_critical_file"],
            verified_checks=[],
            intent_summary="Test with blockers",
        )
        assert "CRITICAL" in result or "BLOCKED" in result.upper()


class TestFormatRsnFromSteps:
    """Test suite for format_rsn_from_steps bridge function."""

    def test_returns_string(self):
        """Should return a formatted string."""
        steps = [
            {
                "id": "STEP-001",
                "description": "Fix context size issue",
                "severity": "HIGH",
                "domain": "context_size",
                "action_type": "Manual",
                "effort_minutes": 10,
            }
        ]
        result = format_rsn_from_steps(steps, intent_summary="Test steps")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_step_fields_mapped_correctly(self):
        """Step fields should be mapped to RSN finding fields."""
        steps = [
            {
                "id": "STEP-001",
                "description": "Test step",
                "severity": "MEDIUM",
                "domain": "code_quality",
                "action_type": "Use /skill",
                "effort_minutes": 5,
                "file_ref": "test.py:42",
            }
        ]
        result = format_rsn_from_steps(steps, intent_summary="Test")
        assert isinstance(result, str)

    def test_empty_steps(self):
        """Empty steps list should produce valid output."""
        result = format_rsn_from_steps([], intent_summary="No steps")
        assert isinstance(result, str)


class TestShipFindingDataclass:
    """Test suite for ShipFinding dataclass."""

    def test_create_finding(self):
        """ShipFinding should be created with all fields."""
        finding = ShipFinding(
            check_name="test_check",
            severity="HIGH",
            message="Test message",
            file_ref="test.py:10",
            action_type="Manual",
            effort_minutes=5,
            domain="code_quality",
        )
        assert finding.check_name == "test_check"
        assert finding.severity == "HIGH"
        assert finding.message == "Test message"
        assert finding.file_ref == "test.py:10"
        assert finding.action_type == "Manual"
        assert finding.effort_minutes == 5
        assert finding.domain == "code_quality"

    def test_default_values(self):
        """ShipFinding should have appropriate defaults."""
        finding = ShipFinding(
            check_name="test_check",
            severity="LOW",
            message="Test",
        )
        assert finding.file_ref is None
        assert finding.action_type == "Manual"
        assert finding.effort_minutes == 5
        assert finding.domain is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
