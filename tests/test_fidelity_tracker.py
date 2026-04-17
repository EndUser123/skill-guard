"""Tests for fidelity_tracker usage fidelity measurement."""
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure skill-craft module is importable
CRAFT_DIR = Path("P:/.claude/skills/skill-craft")
sys.path.insert(0, str(CRAFT_DIR))

from fidelity_tracker import (
    _discover_eval_set,
    _measure_structural,
    _structural_outcome_score,
    measure_fidelity,
)
from fidelity_tracker import FidelityConfig
from craft_state import FidelityScore


class TestDiscoverEvalSet:
    """Eval set discovery logic."""

    def test_finds_local_eval_set(self, tmp_path):
        """Finds eval set in target_path/eval_sets/default.json."""
        skill_dir = tmp_path / "myskill"
        skill_dir.mkdir()
        eval_dir = skill_dir / "eval_sets"
        eval_dir.mkdir()
        eval_file = eval_dir / "default.json"
        eval_file.write_text('[{"query": "test", "should_trigger": true}]')

        found = _discover_eval_set(skill_dir)
        assert found is not None
        assert found == eval_file

    def test_returns_none_when_no_eval_set(self, tmp_path):
        """Returns None when no eval set exists."""
        skill_dir = tmp_path / "myskill"
        skill_dir.mkdir()

        found = _discover_eval_set(skill_dir)
        assert found is None

    def test_missing_skill_dir(self, tmp_path):
        """Returns None when target_path doesn't exist."""
        missing = tmp_path / "does_not_exist"
        found = _discover_eval_set(missing)
        assert found is None


class TestStructuralOutcomeScore:
    """Structural proxy for outcome accuracy."""

    def test_perfect_imperative_form(self, tmp_path):
        """High score when no second-person and many imperative lines."""
        skill_dir = tmp_path / "goodskill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\nname: good\ndescription: This skill should be used when needed.\n---\n"
            "# Good Skill\n\n"
            "To use this skill, run the command.\n"
            "Create a new project with the scaffold.\n"
            "Fix the configuration file.\n"
            "Validate the input parameters.\n"
            "Generate the output artifact.\n"
            "Configure the service properly.\n"
            "Initialize the workspace.\n"
        )

        score = _structural_outcome_score(skill_dir)
        assert score == 1.0

    def test_second_person_reduces_score(self, tmp_path):
        """Presence of second-person voice reduces outcome accuracy."""
        skill_dir = tmp_path / "badskill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\nname: bad\ndescription: This skill should be used when needed.\n---\n"
            "# Bad Skill\n\n"
            "You run this command to create a project.\n"
            "Your configuration will be validated.\n"
        )

        score = _structural_outcome_score(skill_dir)
        assert score == 0.5

    def test_no_skill_md_returns_zero(self, tmp_path):
        """Missing SKILL.md returns 0.0 outcome accuracy."""
        skill_dir = tmp_path / "noskill"
        skill_dir.mkdir()
        score = _structural_outcome_score(skill_dir)
        assert score == 0.0


class TestMeasureStructural:
    """Structural fallback when no eval set available."""

    def test_trigger_accuracy_full_desc(self, tmp_path):
        """Proper third-person description gives trigger_accuracy=1.0."""
        skill_dir = tmp_path / "triggergood"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: test\n"
            "description: This skill should be used when the user asks to create a package.\n"
            "---\n"
            "# Test Skill\n"
            "To scaffold a project, run the command.\n"
        )

        trigger, outcome = _measure_structural(skill_md)
        assert trigger == 1.0

    def test_trigger_accuracy_short_desc(self, tmp_path):
        """Description not starting with 'This skill should be used' gives 0.5."""
        skill_dir = tmp_path / "triggerbad"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: test\n"
            "description: Creates packages for you.\n"
            "---\n"
            "# Test Skill\n"
        )

        trigger, outcome = _measure_structural(skill_md)
        assert trigger == 0.5

    def test_trigger_accuracy_missing_desc(self, tmp_path):
        """Missing description gives 0.5 trigger accuracy."""
        skill_dir = tmp_path / "nodesc"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("---\nname: test\n---\n# Test Skill\n")

        trigger, outcome = _measure_structural(skill_md)
        assert trigger == 0.5


class TestMeasureFidelity:
    """measure_fidelity end-to-end."""

    def test_missing_skill_md_returns_zero(self, tmp_path):
        """Missing SKILL.md returns zeroed FidelityScore."""
        skill_dir = tmp_path / "noskill"
        skill_dir.mkdir()

        score = measure_fidelity(str(skill_dir))
        assert score.trigger_accuracy == 0.0
        assert score.outcome_accuracy == 0.0
        assert score.overall == 0.0
        assert score.passed is False

    def test_uses_eval_set_when_present(self, tmp_path):
        """When eval set exists, fidelity is measured via eval (not structural)."""
        skill_dir = tmp_path / "witheval"
        skill_dir.mkdir()
        eval_dir = skill_dir / "eval_sets"
        eval_dir.mkdir()
        eval_file = eval_dir / "default.json"
        eval_file.write_text('[{"query": "test", "should_trigger": true}]')
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: test\n"
            "description: This skill should be used when needed.\n"
            "---\n"
            "# Test\n"
            "To do the thing, run the command.\n"
            "Create the artifact properly.\n"
            "Validate all inputs correctly.\n"
        )

        # Should not raise — eval_bridge will fail internally and fall back to structural
        # but the function should not crash
        score = measure_fidelity(str(skill_dir))
        assert isinstance(score, FidelityScore)
        assert 0.0 <= score.overall <= 1.0

    def test_default_config_values(self, tmp_path):
        """Default FidelityConfig has sensible thresholds."""
        skill_dir = tmp_path / "defaulttest"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: test\n"
            "description: This skill should be used when needed.\n"
            "---\n"
            "# Test\n"
            "To create a project, run this.\n"
            "Fix the configuration file.\n"
            "Validate all parameters.\n"
            "Generate the output.\n"
            "Configure properly.\n"
        )

        config = FidelityConfig()
        assert config.trigger_weight == 0.4
        assert config.outcome_weight == 0.5
        assert config.degradation_weight == 0.1
        assert config.trigger_threshold == 0.5
        assert config.outcome_threshold == 0.75
        assert config.default_fidelity_threshold == 0.8

    def test_degradation_delta_with_baseline(self, tmp_path):
        """Degradation delta compares current to baseline."""
        skill_dir = tmp_path / "degradation"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: test\n"
            "description: This skill should be used when needed.\n"
            "---\n"
            "# Test\n"
        )

        baseline = FidelityScore(
            trigger_accuracy=0.9,
            outcome_accuracy=0.9,
            degradation_delta=0.0,
            overall=0.9,
            passed=True,
        )

        score = measure_fidelity(str(skill_dir), baseline_score=baseline)
        # degradation_delta = baseline.overall - current_overall
        # current overall should be computed from the structural score
        assert isinstance(score.degradation_delta, float)

    def test_passed_false_when_below_threshold(self, tmp_path):
        """Score below default_fidelity_threshold marks passed=False."""
        skill_dir = tmp_path / "lowquality"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        # No description -> trigger=0.5, low outcome
        skill_md.write_text("---\nname: test\ndescription: Bad desc\n---\n# Test\n")

        score = measure_fidelity(str(skill_dir))
        # 0.5 * 0.4 + low * 0.5 + 1.0 * 0.1 likely < 0.8 threshold
        assert score.passed is False


class TestStructuralOutcomeEdgeCases:
    """Edge cases in structural outcome scoring."""

    def test_empty_body(self, tmp_path):
        """Empty SKILL.md body returns 0.5 (imperative form check fails)."""
        skill_dir = tmp_path / "empty"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("---\nname: test\ndescription: This skill should be used.\n---\n")

        score = _structural_outcome_score(skill_dir)
        assert score == 0.5

    def test_only_second_person(self, tmp_path):
        """All second-person lines -> 0.5 score."""
        skill_dir = tmp_path / "allyou"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\nname: test\ndescription: This skill should be used.\n---\n"
            "# Test\n"
            "You need to run this command.\n"
            "Your project will be created.\n"
        )

        score = _structural_outcome_score(skill_dir)
        assert score == 0.5

    def test_mixed_imperative_and_second_person(self, tmp_path):
        """Mixed voice -> 0.5 (second person present)."""
        skill_dir = tmp_path / "mixed"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\nname: test\ndescription: This skill should be used.\n---\n"
            "# Test\n"
            "You need to run this.\n"
            "Create the project.\n"
            "Fix the file.\n"
        )

        score = _structural_outcome_score(skill_dir)
        assert score == 0.5
