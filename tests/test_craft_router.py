"""Tests for craft_router state machine."""
import sys
from pathlib import Path

# Ensure craft module is importable
CRAFT_DIR = Path("P:/.claude/skills/skill-craft")
sys.path.insert(0, str(CRAFT_DIR))

from craft_state import Phase, Finding
from craft_router import run_craft, _route_finding, _craft_lens_issues


def test_route_finding_routes_trigger_to_creator():
    """Keywords 'trigger', 'description' → skill-creator."""
    f = Finding(
        lens="TEST",
        gap="Trigger accuracy low",
        evidence="trigger phrases vague",
        owner="source skill",
        priority="HIGH",
        action="Fix trigger"
    )
    owner = _route_finding(f)
    assert owner == "skill-creator", f"Expected skill-creator, got {owner}"


def test_route_finding_routes_second_person_to_development():
    """Keywords 'second person', 'imperative form' → skill-development."""
    f = Finding(
        lens="TEST",
        gap="Body uses second person voice — rewrite in imperative form",
        evidence="Found 10 second person lines",
        owner="source skill",
        priority="MEDIUM",
        action="Rewrite"
    )
    owner = _route_finding(f)
    assert owner == "skill-development", f"Expected skill-development, got {owner}"


def test_route_finding_routes_wrong_scope_to_audit():
    """Keyword 'wrong scope' → skill-audit."""
    f = Finding(
        lens="TEST",
        gap="Skill has wrong scope",
        evidence="scope too broad",
        owner="source skill",
        priority="HIGH",
        action="Redefine scope"
    )
    owner = _route_finding(f)
    assert owner == "skill-audit", f"Expected skill-audit, got {owner}"


def test_route_finding_routes_missing_test_to_ship():
    """Keyword 'missing test' → skill-ship."""
    f = Finding(
        lens="TEST",
        gap="Missing test coverage",
        evidence="no tests found",
        owner="source skill",
        priority="MEDIUM",
        action="Add tests"
    )
    owner = _route_finding(f)
    assert owner == "skill-ship", f"Expected skill-ship, got {owner}"


def test_route_finding_defaults_to_source_skill():
    """No matching keyword → source skill."""
    f = Finding(
        lens="TEST",
        gap="Some unrelated issue",
        evidence="something happened",
        owner="source skill",
        priority="LOW",
        action="Fix it"
    )
    owner = _route_finding(f)
    assert owner == "source skill", f"Expected source skill, got {owner}"


def test_run_craft_against_gitready_completes():
    """run_craft against gitready completes without exception."""
    state = run_craft("P:/packages/gitready/skills/gitready")
    assert state.phase in (Phase.GATING, Phase.DONE)
    assert state.fidelity_score is not None
    assert state.cert_gate is not None


def test_run_craft_fidelity_measured():
    """Fidelity score is populated after PHASE 4."""
    state = run_craft("P:/packages/gitready/skills/gitready")
    assert state.fidelity_score.trigger_accuracy > 0
    assert state.fidelity_score.outcome_accuracy > 0
    assert state.fidelity_score.overall > 0


def test_run_craft_cert_gate_results():
    """Cert gate result is populated after PHASE 5."""
    state = run_craft("P:/packages/gitready/skills/gitready")
    assert state.cert_gate is not None
    # gitready is missing depends_on_skills, so cert gate should fail
    assert isinstance(state.cert_gate.failures, list)


def test_run_craft_loops_up_to_max():
    """run_craft increments loop_count each iteration."""
    state = run_craft("P:/packages/gitready/skills/gitready")
    assert state.loop_count >= 1
    assert state.loop_count <= 3  # MAX_LOOPS = 3


def test_run_craft_no_healthy_exit():
    """gitready has actionable findings, so should not exit 'skill is healthy'."""
    state = run_craft("P:/packages/gitready/skills/gitready")
    # If it exits healthy, there were no actionable findings
    if state.exit_reason:
        assert state.exit_reason != "No actionable findings — skill is healthy"


def test_run_craft_fidelity_score_populated():
    """Fidelity score is always populated after any loop iteration."""
    state = run_craft("P:/packages/gitready/skills/gitready")
    assert state.fidelity_score is not None
    assert 0.0 <= state.fidelity_score.overall <= 1.0
    assert isinstance(state.fidelity_score.passed, bool)