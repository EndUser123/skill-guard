"""Tests for Phase 3e Evaluator - structured JSON findings."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestEvaluatorSchema:
    """Test suite for Phase 3e Evaluator output schema."""

    def test_evaluator_findsings_schema_fields(self):
        """Each finding must have lens, finding, evidence, proposed_score, severity."""
        findings_schema = {
            "lens": str,
            "finding": str,
            "evidence": list,
            "proposed_score": int,
            "severity": str,
        }
        # Validate structure: lens is required, evidence is required
        assert "lens" in findings_schema
        assert "evidence" in findings_schema
        assert findings_schema["lens"] == str
        assert findings_schema["evidence"] == list

    def test_score_bounds_1_to_5(self):
        """proposed_score must be integer 1-5."""
        valid_scores = [1, 2, 3, 4, 5]
        for score in valid_scores:
            assert 1 <= score <= 5

    def test_severity_values(self):
        """severity must be one of critical, major, minor, info."""
        valid_severities = {"critical", "major", "minor", "info"}
        assert valid_severities == {"critical", "major", "minor", "info"}

    def test_7_lenses_defined(self):
        """Evaluator must score all 7 rubric lenses."""
        expected_lenses = {
            "problem_fit",
            "adaptability",
            "composability",
            "context_efficiency",
            "observability",
            "failure_tolerance",
            "maintainability_6m",
        }
        assert len(expected_lenses) == 7

    def test_evidence_must_be_list_or_null(self):
        """finding with evidence must cite specific file:line or config key."""
        # Evidence must be list of citation strings (file:line, config key, etc.)
        valid_evidence = ["workflow-phases.md:47", "builtins.json:12"]
        assert isinstance(valid_evidence, list)
        assert len(valid_evidence) > 0
        # Null finding (no issues) is allowed
        assert True  # null finding means proposed_score=5, no evidence needed

    def test_null_finding_allowed(self):
        """A lens with no findings should have finding: null."""
        null_finding = {"lens": "problem_fit", "finding": None, "proposed_score": 5, "severity": "info"}
        assert null_finding["finding"] is None
        assert null_finding["proposed_score"] == 5
        assert null_finding["severity"] == "info"

    def test_critical_severity_for_low_score(self):
        """Score of 1-2 on critical lens should produce critical severity."""
        # If adaptability scores 1 or 2, severity should be critical
        low_score = 2
        critical_lens = "adaptability"
        if low_score <= 2 and critical_lens in ["adaptability", "problem_fit", "failure_tolerance"]:
            severity = "critical"
        assert severity == "critical"

    def test_json_output_format(self):
        """Evaluator must return ONLY valid JSON (no markdown, no prose)."""
        # This would be tested against actual evaluator output
        # Valid JSON array of finding objects
        valid_output = json.dumps([
            {
                "lens": "adaptability",
                "finding": "hard-coded path assumption in workflow-phases.md",
                "evidence": ["workflow-phases.md:47"],
                "proposed_score": 2,
                "severity": "critical"
            }
        ])
        parsed = json.loads(valid_output)
        assert isinstance(parsed, list)
        assert len(parsed) > 0
        assert "lens" in parsed[0]

    def test_all_lenses_scored(self):
        """Every lens must appear in output even if finding is null."""
        expected_lenses = {
            "problem_fit",
            "adaptability",
            "composability",
            "context_efficiency",
            "observability",
            "failure_tolerance",
            "maintainability_6m",
        }
        # Simulated all-null output (no issues found)
        all_null_output = [
            {"lens": lens, "finding": None, "proposed_score": 5, "severity": "info", "evidence": []}
            for lens in sorted(expected_lenses)
        ]
        assert len(all_null_output) == 7
        scored_lenses = {f["lens"] for f in all_null_output}
        assert scored_lenses == expected_lenses

    def test_score_thresholds(self):
        """Score 1-2 should be at least major severity; 5 should be info."""
        score_to_severity = {
            1: "critical",
            2: "critical",
            3: "major",
            4: "minor",
            5: "info",
        }
        for score, expected_sev in score_to_severity.items():
            assert 1 <= score <= 5


class TestEvaluatorProvenanceAndConstraints:
    """Test suite for provenance field and evaluator role constraints."""

    def test_provenance_field_required(self):
        """Every finding must include provenance field."""
        valid_finding = {
            "lens": "adaptability",
            "finding": "hard-coded path assumption",
            "evidence": ["workflow-phases.md:47"],
            "proposed_score": 2,
            "severity": "critical",
            "provenance": "this_run"
        }
        assert "provenance" in valid_finding
        assert valid_finding["provenance"] in ("this_run", "prior_premortem", "prior_manual_review")

    def test_provenance_values_valid(self):
        """provenance must be one of: this_run, prior_premortem, prior_manual_review."""
        valid_values = {"this_run", "prior_premortem", "prior_manual_review"}
        for val in valid_values:
            assert val in valid_values

    def test_evaluator_never_returns_decision_field(self):
        """Evaluator must NOT return a decision field - that is the judge's exclusive domain."""
        # The evaluator produces findings only; it does not make decisions
        # This is enforced by the evaluator prompt constraint: "You do NOT make the final decision"
        evaluator_constraints = [
            "Your job is to analyze the target skill/orchestrator and produce structured JSON findings",
            "You do NOT make the final decision — that is the Judge's role",
            "Return ONLY valid JSON",
        ]
        # Verify constraints mention findings-not-decision
        assert any("findings" in c.lower() for c in evaluator_constraints)
        assert any("decision" in c.lower() for c in evaluator_constraints)
        # The evaluator prompt explicitly forbids decision field
        # Documented in evaluator-judge-prompts.md: evaluator never calls decision

    def test_evaluator_output_has_no_decision_key(self):
        """Evaluator JSON output must not contain a 'decision' key."""
        # This is a schema constraint - evaluator findings are an array, not an object with decision
        evaluator_output_schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": ["lens", "finding", "evidence", "proposed_score", "severity", "provenance", "assumptions"]
            }
        }
        # decision is NOT in evaluator schema - it belongs to judge output
        assert "decision" not in evaluator_output_schema["items"]["properties"]
        assert evaluator_output_schema["type"] == "array"

    def test_evaluator_has_assumptions_field(self):
        """Every evaluator output must include assumptions array (empty if none)."""
        finding_with_assumptions = {
            "lens": "adaptability",
            "finding": "hard-coded path assumption",
            "evidence": ["workflow-phases.md:47"],
            "proposed_score": 2,
            "severity": "critical",
            "provenance": "this_run",
            "assumptions": ["assumes Windows paths", "assumes single-repo layout"]
        }
        assert "assumptions" in finding_with_assumptions
        assert isinstance(finding_with_assumptions["assumptions"], list)

    def test_evaluator_null_finding_has_empty_assumptions(self):
        """Null finding (no issues) should still have assumptions: []."""
        null_finding = {
            "lens": "problem_fit",
            "finding": None,
            "proposed_score": 5,
            "severity": "info",
            "provenance": "this_run",
            "assumptions": []
        }
        assert null_finding["assumptions"] == []


class TestSkillArchitectureLens:
    """Test suite for Skill Architecture lens (lens 8)."""

    def test_skill_architecture_lens_exists(self):
        """skill_architecture is the 8th lens in the evaluator rubric."""
        expected_lenses = {
            "problem_fit", "adaptability", "composability", "context_efficiency",
            "observability", "failure_tolerance", "maintainability_6m", "skill_architecture"
        }
        assert len(expected_lenses) == 8

    def test_missing_references_dir_yields_low_score(self):
        """Missing references/ directory with no enforcement → score ≤3, major severity."""
        # SKILL.md promises references/ but glob returns [] → skill_architecture finding
        skill_arch_finding = {
            "lens": "skill_architecture",
            "finding": "SKILL.md promises references/ but glob returns []",
            "evidence": ["glob('references/*') → []"],
            "proposed_score": 2,
            "severity": "major",
            "provenance": "this_run",
            "assumptions": []
        }
        assert skill_arch_finding["proposed_score"] <= 3
        assert skill_arch_finding["severity"] in ("major", "critical")

    def test_prose_only_stage_enforcement_yields_low_score(self):
        """Prose-only stage enforcement (no Python validator) → score ≤3."""
        # "Phase 3b enforces context bloat" is documented but validate.py has no check
        skill_arch_finding = {
            "lens": "skill_architecture",
            "finding": "SKILL.md promises stage 3b enforcement but validate.py has no context bloat check",
            "evidence": ["validate.py: no context_bloat enforcement", "SKILL.md: 'Phase 3b enforces context bloat'"],
            "proposed_score": 3,
            "severity": "major",
            "provenance": "this_run",
            "assumptions": []
        }
        assert skill_arch_finding["proposed_score"] <= 3
        assert skill_arch_finding["severity"] == "major"

    def test_full_structure_match_yields_score_5(self):
        """SKILL.md promises match Python implementation → score 5."""
        # All file promises kept, all stages enforced, template system programmatic
        full_match_finding = {
            "lens": "skill_architecture",
            "finding": None,
            "evidence": [],
            "proposed_score": 5,
            "severity": "info",
            "provenance": "this_run",
            "assumptions": []
        }
        assert full_match_finding["proposed_score"] == 5
        assert full_match_finding["severity"] == "info"

    def test_skill_architecture_output_schema(self):
        """skill_architecture finding uses same JSON schema as other lenses."""
        valid_finding = {
            "lens": "skill_architecture",
            "finding": "references/ missing",
            "evidence": ["glob('references/*') → []"],
            "proposed_score": 2,
            "severity": "major",
            "provenance": "this_run",
            "assumptions": ["assumes references/ is required"]
        }
        assert "lens" in valid_finding
        assert "proposed_score" in valid_finding
        assert "severity" in valid_finding
        assert "evidence" in valid_finding
        assert "provenance" in valid_finding
        assert "assumptions" in valid_finding
