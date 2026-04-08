"""Tests for skill-audit."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit as audit_module
from audit import (
    audit,
    build_transfer_judgment_packet,
    discover_transfer_targets,
    _semantic_transfer_bonus_map,
    _operational_reference_text,
    _derive_handoff_offer,
    _derive_outcomes,
    _derive_verdict,
    _lens_command_discipline,
    _lens_structural_justification,
    _parse_skill,
    _lens_reference_integrity,
    _lens_process_enforcement,
    _lens_model_variance,
    _lens_contract_completeness,
    _lens_skill_contract_consistency,
    _lens_mechanism_leakage,
    _lens_question_strategy,
    _lens_operational_resilience,
    _lens_assurance_strategy,
    _lens_non_goals_clarity,
    Finding,
)
from validate import validate_shape, validate_frontmatter


class TestValidateShape:
    def test_missing_dir(self, tmp_path):
        valid, msg = validate_shape(tmp_path / "nonexistent")
        assert not valid
        assert "does not exist" in msg

    def test_missing_skill_md(self, tmp_path):
        skill = tmp_path / "bad-skill"
        skill.mkdir()
        valid, msg = validate_shape(skill)
        assert not valid
        assert "SKILL.md missing" in msg

    def test_truncated_skill_md(self, tmp_path):
        skill = tmp_path / "bad-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text("name: x")
        valid, msg = validate_shape(skill)
        assert not valid
        assert "truncated" in msg

    def test_valid_skill(self, tmp_path):
        skill = tmp_path / "test-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text("""---
name: test-skill
description: "A test skill that does things and validates shapes correctly"
---

# Test Skill
## Purpose
Does things.
""")
        valid, msg = validate_shape(skill)
        assert valid
        assert msg == "OK"


class TestValidateFrontmatter:
    def test_complete_frontmatter_no_warnings(self, tmp_path):
        skill = tmp_path / "test-complete"
        skill.mkdir()
        (skill / "SKILL.md").write_text("""---
name: test-complete
description: "A complete skill"
version: "1.0.0"
enforcement: strict
---

# Test Skill
""")
        warnings = validate_frontmatter("test-complete", skills_dir=tmp_path)
        assert warnings == [], f"Expected no warnings, got: {warnings}"

    def test_missing_enforcement_warns(self, tmp_path):
        skill = tmp_path / "test-missing-enforcement"
        skill.mkdir()
        (skill / "SKILL.md").write_text("""---
name: test-missing-enforcement
description: "Missing enforcement"
version: "1.0.0"
---

# Test Skill
""")
        warnings = validate_frontmatter("test-missing-enforcement", skills_dir=tmp_path)
        enforcement_warnings = [w for w in warnings if "enforcement" in w]
        assert len(enforcement_warnings) == 1, f"Expected 1 enforcement warning, got: {warnings}"

    def test_missing_version_warns(self, tmp_path):
        skill = tmp_path / "test-missing-version"
        skill.mkdir()
        (skill / "SKILL.md").write_text("""---
name: test-missing-version
description: "Missing version"
enforcement: strict
---

# Test Skill
""")
        warnings = validate_frontmatter("test-missing-version", skills_dir=tmp_path)
        version_warnings = [w for w in warnings if "version" in w]
        assert len(version_warnings) == 1, f"Expected 1 version warning, got: {warnings}"

    def test_missing_multiple_fields_warns(self, tmp_path):
        skill = tmp_path / "test-missing-multiple"
        skill.mkdir()
        (skill / "SKILL.md").write_text("""---
name: test-missing-multiple
description: "Has name and desc only"
---

# Test Skill
""")
        warnings = validate_frontmatter("test-missing-multiple", skills_dir=tmp_path)
        assert len(warnings) >= 2, f"Expected >=2 warnings (version, enforcement), got: {warnings}"

    def test_invalid_enforcement_value_warns(self, tmp_path):
        skill = tmp_path / "test-invalid-enforcement"
        skill.mkdir()
        (skill / "SKILL.md").write_text("""---
name: test-invalid-enforcement
description: "Invalid enforcement value"
version: "1.0.0"
enforcement: invalid_value
---

# Test Skill
""")
        warnings = validate_frontmatter("test-invalid-enforcement", skills_dir=tmp_path)
        enforcement_warnings = [w for w in warnings if "enforcement" in w]
        assert len(enforcement_warnings) == 1, f"Expected 1 enforcement warning, got: {warnings}"

    def test_nonexistent_skill_returns_empty(self, tmp_path):
        warnings = validate_frontmatter("nonexistent-skill-xyz", skills_dir=tmp_path)
        assert warnings == [], f"Expected no warnings for nonexistent skill, got: {warnings}"


class TestLensReferenceIntegrity:
    def test_missing_refs(self, tmp_path):
        skill = tmp_path / "test"
        skill.mkdir()
        md = """---
name: test
---

# Test
See `references/missing.md` for details.
"""
        parsed = _parse_skill(skill, md)
        findings = _lens_reference_integrity(parsed)
        assert len(findings) == 1
        assert findings[0].lens == "REFERENCE_INTEGRITY"
        assert "missing.md" in findings[0].gap

    def test_relative_resources_ref_resolves(self, tmp_path):
        skill = tmp_path / "test"
        skill.mkdir()
        resources_dir = skill / "resources"
        resources_dir.mkdir()
        (resources_dir / "shared_frameworks.md").write_text("# Shared")
        md = """---
name: test
---

# Test
Full framework: `./resources/shared_frameworks.md`
"""
        parsed = _parse_skill(skill, md)
        findings = _lens_reference_integrity(parsed)
        assert len(findings) == 0

    def test_templated_reference_is_not_flagged(self, tmp_path):
        skill = tmp_path / "test"
        skill.mkdir()
        md = """---
name: test
---

# Test
Templates are loaded from `./resources/{template}.md`.
"""
        parsed = _parse_skill(skill, md)
        findings = _lens_reference_integrity(parsed)
        assert len(findings) == 0


class TestLensProcessEnforcement:
    def test_unbacked_phase_invocation(self, tmp_path):
        skill = tmp_path / "test"
        skill.mkdir()
        md = """---
name: test
---

Phase 1 invokes /av2 for validation.
"""
        py = skill / "checker.py"
        py.write_text("import sys")
        parsed = _parse_skill(skill, md)
        findings = _lens_process_enforcement(parsed, [py])
        assert any(f.lens == "PROCESS_ENFORCEMENT" for f in findings)


class TestLensCommandDiscipline:
    def test_missing_quality_gate_is_flagged_for_broad_user_facing_skill(self):
        md = """---
name: broad-advisor
description: "Workflow advisor"
category: analysis
---

# Broad Advisor

## Purpose
Route and advise on user workflow requests.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_command_discipline(parsed)
        assert any("vague-input quality gate" in f.gap for f in findings)

    def test_branch_heavy_skill_without_path_enumeration_is_flagged(self):
        md = """---
name: router
description: "Routing workflow"
category: orchestration
---

# Router

If the query is about planning, route to /planning. Else route to /arch.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_command_discipline(parsed)
        assert any("logical paths" in f.gap for f in findings)

    def test_role_drift_and_missing_standardized_errors_are_flagged(self):
        md = """---
name: mega-skill
description: "Audit, implement, and publish skills"
category: orchestration
---

# Mega Skill

## Purpose
Audit strategy, implement hooks and validators, then publish to GitHub.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_command_discipline(parsed)
        assert any("single-responsibility drift" in f.gap for f in findings)
        assert any("standardized error" in f.gap for f in findings)

    def test_command_discipline_is_quiet_when_skill_has_gate_paths_and_errors(self):
        md = """---
name: disciplined-router
description: "Routing workflow"
category: orchestration
---

# Disciplined Router

## Input Quality Gate
When input is vague, ask one clarifying question before execution.

## Routing Table
Enumerate all logical paths and failure paths before invoking a downstream skill.

## Error Format
Use predictable error and block reason text.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_command_discipline(parsed)
        assert findings == []


class TestLensStructuralJustification:
    def test_missing_concrete_failure_and_tradeoffs_are_flagged(self):
        md = """---
name: builder
description: "Adds new validators and hooks"
category: strategy
---

# Builder

## Purpose
Add a new validator layer and a new hook for stronger enforcement.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_structural_justification(parsed)
        assert any("concrete failure" in f.gap for f in findings)
        assert any("simpler-alternative" in f.gap for f in findings)
        assert any("complexity tradeoff" in f.gap for f in findings)

    def test_principle_based_structural_justification_is_allowed(self):
        md = """---
name: builder
description: "Adds new validators and hooks"
category: strategy
---

# Builder

## Purpose
Add a new validator layer only when a concrete failure or recurring manual-review miss justifies it.

## Decision Criteria
- What concrete failure does this new hook or validator prevent?
- Is there a simpler alternative that reuses existing mechanisms?
- What complexity tax or maintenance overhead does this add?
- Is this likely to remain useful long-term, and is it reversible if it fails?
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_structural_justification(parsed)
        assert findings == []


class TestLensModelVariance:
    def test_vague_terms_detected(self):
        md = """## Phase 2
Optimize for clarity as needed.
"""
        findings = _lens_model_variance(md)
        assert len(findings) == 2
        lenses = {f.lens for f in findings}
        assert "MODEL_VARIANCE" in lenses

    def test_no_vague_terms(self):
        md = """## Phase 1
Execute the script with `--format json`.
"""
        findings = _lens_model_variance(md)
        assert len(findings) == 0


class TestLensContractCompleteness:
    def test_contract_completeness_is_quiet_when_skill_names_primitives(self, tmp_path):
        skill = tmp_path / "docs-first"
        skill.mkdir()
        md = """---
name: docs-first
description: "Contract-heavy skill"
---

# Docs First Skill
Uses Contract Authority Packet and evidence store for handoffs.
"""
        parsed = _parse_skill(skill, md)
        findings = _lens_contract_completeness(parsed, [])
        assert findings == []

    def test_contract_completeness_flags_raw_io_without_named_primitive(self, tmp_path):
        skill = tmp_path / "code-skill"
        skill.mkdir()
        md = """---
name: code-skill
description: "Writes handoff artifacts"
---

# Code Skill
This skill handles contract handoff state.
"""
        py = skill / "writer.py"
        py.write_text("from pathlib import Path\nPath('x').write_text('payload')\n")
        parsed = _parse_skill(skill, md)
        findings = _lens_contract_completeness(parsed, [py])
        assert len(findings) == 1
        assert findings[0].lens == "CONTRACT_COMPLETENESS"


class TestLensSkillContractConsistency:
    def test_enforcement_drift_detected(self):
        md = """---
name: drifted-skill
description: "A test skill"
version: "5.1"
enforcement: advisory
---

# Drifted Skill

The skill may not proceed without repair.

**Version:** 5.1
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_skill_contract_consistency(parsed)
        assert any("enforcement" in f.gap for f in findings)

    def test_footer_version_drift_detected(self):
        md = """---
name: drifted-version
description: "A test skill"
version: "5.1"
---

# Drifted Version

**Version:** 5.0
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_skill_contract_consistency(parsed)
        assert any("version drift" in f.gap for f in findings)


class TestLensMechanismLeakage:
    def test_mechanism_leakage_detected(self):
        md = """# Mechanism Leakage

```python
Agent(
  subagent_type="general-purpose",
  model="haiku",
  prompt="run the critic"
)
```

Output: P:/state/critic.json
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_mechanism_leakage(parsed)
        assert len(findings) == 1
        assert findings[0].lens == "MECHANISM_LEAKAGE"


class TestLensQuestionStrategy:
    def test_rca_missing_competing_cause_prompts_is_flagged(self):
        md = """---
name: rca
description: "Root cause analysis engine"
category: analysis
---

# RCA

## Purpose
Diagnose failures and recommend fixes.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_question_strategy(parsed)
        assert any("competing-cause self-check prompts" in f.gap for f in findings)

    def test_code_missing_implementation_risk_prompts_is_flagged(self):
        md = """---
name: code
description: "Feature development workflow"
category: development
---

# Code

## Purpose
Implement features and ship code changes.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_question_strategy(parsed)
        assert any("implementation-risk self-check prompts" in f.gap for f in findings)

    def test_tdd_missing_test_truth_prompts_is_flagged(self):
        md = """---
name: tdd
description: "Test-Driven Development workflow"
category: execution
---

# TDD

## Purpose
Write failing tests before code changes.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_question_strategy(parsed)
        assert any("test-truth self-check prompts" in f.gap for f in findings)

    def test_rns_missing_action_extraction_prompts_is_flagged(self):
        md = """---
name: rns
description: "Recommended next steps from arbitrary output"
category: analysis
---

# RNS

## Purpose
Convert findings into actions.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_question_strategy(parsed)
        assert any("action-extraction self-check prompts" in f.gap for f in findings)

    def test_pre_mortem_missing_failure_mode_prompts_is_flagged(self):
        md = """---
name: pre-mortem
description: "Adaptive adversarial critique"
category: analysis
---

# Pre-Mortem

## Purpose
Stress test a design before implementation.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_question_strategy(parsed)
        assert any("failure-mode self-check prompts" in f.gap for f in findings)

    def test_gto_missing_next_step_integrity_prompts_is_flagged(self):
        md = """---
name: gto
description: "Strategic next-step advisor"
category: analysis
---

# GTO

## Purpose
Recommend what to do next.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_question_strategy(parsed)
        assert any("next-step integrity self-check prompts" in f.gap for f in findings)


class TestLensAssuranceStrategy:
    def test_code_missing_smoke_and_critique_contracts_is_flagged(self):
        md = """---
name: code
description: "Feature development workflow"
category: development
---

# Code

## Purpose
Implement features and ship code changes.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_assurance_strategy(parsed)
        gaps = {f.gap for f in findings}
        assert "implementation workflow lacks explicit smoke validation contract" in gaps
        assert "implementation workflow lacks explicit critique-agent trigger policy" in gaps

    def test_planning_missing_critique_review_policy_is_flagged(self):
        md = """---
name: planning
description: "Implementation planning workflow"
category: planning
---

# Planning

## Purpose
Create implementation plans.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_assurance_strategy(parsed)
        assert any("planning workflow lacks explicit critique-agent review policy" == f.gap for f in findings)

    def test_arch_is_not_misclassified_as_code_for_assurance_or_questions(self):
        md = """---
name: arch
description: "Architecture advisor"
category: architecture
---

# Arch

## Purpose
Close architecture and guide /planning and /code without implementing changes directly.
"""
        parsed = _parse_skill(Path("."), md)
        assurance = _lens_assurance_strategy(parsed)
        question = _lens_question_strategy(parsed)
        assert not any("implementation workflow lacks explicit smoke validation contract" == f.gap for f in assurance)
        assert not any("Implementation skill lacks explicit implementation-risk self-check prompts" == f.gap for f in question)

    def test_present_assurance_sections_are_quiet(self):
        md = """---
name: tdd
description: "Test-Driven Development workflow"
category: execution
---

# TDD

## Purpose
Write failing tests before code changes.

## Behavior Smoke Proof
Run a minimal real execution proving the target behavior is attached to reality.

## Critique-Agent Triggers
Use a critique agent for stateful, contract-heavy, or integration-heavy test design.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_assurance_strategy(parsed)
        assert findings == []

    def test_recap_missing_catch_up_integrity_prompts_is_flagged(self):
        md = """---
name: recap
description: "Terminal-wide session catch-up"
category: session
---

# Recap

## Purpose
Summarize prior sessions and resume context.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_question_strategy(parsed)
        assert any("catch-up integrity self-check prompts" in f.gap for f in findings)

    def test_learn_missing_lesson_quality_prompts_is_flagged(self):
        md = """---
name: learn
description: "Intelligent lesson capture with novelty detection"
category: learning
---

# Learn

## Purpose
Store reusable lessons from sessions.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_question_strategy(parsed)
        assert any("lesson-quality self-check prompts" in f.gap for f in findings)

    def test_retro_missing_retrospective_integrity_prompts_is_flagged(self):
        md = """---
name: retro
description: "Self-contrast retrospective orchestrator"
category: analysis
---

# Retro

## Purpose
Run a retrospective and produce actions.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_question_strategy(parsed)
        assert any("retrospective-integrity self-check prompts" in f.gap for f in findings)

    def test_reflect_missing_reflection_upgrade_prompts_is_flagged(self):
        md = """---
name: reflect
description: "Self-improving skills from conversation transcripts"
category: learning
---

# Reflect

## Purpose
Propose skill improvements from conversation patterns.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_question_strategy(parsed)
        assert any("reflection-upgrade self-check prompts" in f.gap for f in findings)

    def test_skill_ship_strategic_questions_are_flagged(self):
        md = """---
name: skill-ship
description: "Ship a skill"
---

# Skill Ship

## Open-Ended Questions
- Should this skill exist in this form at all?
- Is the enforcement model fundamentally wrong?
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_question_strategy(parsed)
        assert len(findings) == 1
        assert findings[0].lens == "QUESTION_STRATEGY"
        assert "reopens strategic design questions" in findings[0].gap

    def test_skill_audit_implementation_trivia_questions_are_flagged(self):
        md = """---
name: skill-audit
description: "Audit a skill"
---

# Skill Audit

## Open-Ended Questions
- What exact hook filename should this use?
- Which helper function name should parse this JSON?
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_question_strategy(parsed)
        assert len(findings) == 1
        assert findings[0].lens == "QUESTION_STRATEGY"
        assert "implementation-trivia" in findings[0].gap

    def test_skill_audit_strategic_questions_are_allowed(self):
        md = """---
name: skill-audit
description: "Audit a skill"
---

# Skill Audit

## Open-Ended Questions
- What problem is this skill actually trying to solve?
- What would make this skill unnecessary?
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_question_strategy(parsed)
        assert findings == []

    def test_code_role_appropriate_prompts_are_allowed(self):
        md = """---
name: code
description: "Feature development workflow"
category: development
---

# Code

## Implementation-Risk Prompts
- What requirement or contract am I about to guess instead of read?
- What regression would recur unless I add or update a test now?
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_question_strategy(parsed)
        assert findings == []

    def test_gto_role_appropriate_prompts_are_allowed(self):
        md = """---
name: gto
description: "Strategic next-step advisor"
category: analysis
---

# GTO

## Next-Step Integrity Prompts
- What recommendation is being driven by stale artifacts rather than current evidence?
- What recommendation is being suggested because the skill is nearby, rather than because it truly owns the gap?
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_question_strategy(parsed)
        assert findings == []

    def test_reflect_role_appropriate_prompts_are_allowed(self):
        md = """---
name: reflect
description: "Self-improving skills from conversation transcripts"
category: learning
---

# Reflect

## Reflection-Upgrade Prompts
- What correction or preference here is a one-off local preference rather than a durable skill improvement?
- What lesson should be pushed into a validator, hook, or test instead of staying as prose?
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_question_strategy(parsed)
        assert findings == []

    def test_arch_missing_trace_and_challenge_modes_is_flagged(self):
        md = """---
name: arch
description: "Architecture advisor"
category: architecture
---

# Arch

## Purpose
Close architecture decisions and emit handoff packets.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_question_strategy(parsed)
        assert any("Architecture skill lacks appropriate internal-mode support" in f.gap for f in findings)

    def test_learn_missing_emerge_and_graduate_modes_is_flagged(self):
        md = """---
name: learn
description: "Intelligent lesson capture with novelty detection"
category: learning
---

# Learn

## Purpose
Store reusable lessons from sessions.

## Lesson-Quality Prompts
- What lesson sounds novel locally but is already known or too one-off to keep?
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_question_strategy(parsed)
        assert any("Lesson-capture skill lacks appropriate internal-mode support" in f.gap for f in findings)

    def test_shared_internal_modes_reference_satisfies_mode_expectation(self):
        md = """---
name: planning
description: "Implementation planning workflow"
category: planning
---

# Planning

## Purpose
Create implementation plans with strict readiness gating.

## Internal Discovery Modes
- `trace`: reconstruct prior decisions
- `challenge`: pressure-test the plan
- `graduate`: promote repeated planning defects into validators

Reference: `P:/.claude/skills/__lib/sdlc_internal_modes.md`
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_question_strategy(parsed)
        assert not any("internal-mode support" in f.gap for f in findings)


class TestLensOperationalResilience:
    def test_stateful_hook_skill_missing_resilience_contract_is_flagged(self):
        md = """---
name: test-orchestrator
category: orchestration
description: "Hook-heavy workflow skill"
---

# Test Orchestrator

## Purpose
This skill manages workflow state, hooks, and resumed phases.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_operational_resilience(parsed)
        assert any(f.lens == "OPERATIONAL_RESILIENCE" and "resilience contract" in f.gap for f in findings)
        assert any("cognitive/reasoning hook fit guidance" in f.gap for f in findings)

    def test_resilience_and_cognitive_hook_guidance_is_allowed(self):
        md = """---
name: test-orchestrator
category: orchestration
description: "Hook-heavy workflow skill"
---

# Test Orchestrator

This skill is multi-terminal safe via terminal-scoped state, uses TTL invalidation for stale data,
and is compact-resilient through interrupted workflow resume markers.
It reuses existing cognitive hooks from the Cognitive Steering Framework and treats extra reasoning hooks as out of scope unless a new gap is proven.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_operational_resilience(parsed)
        assert findings == []

    def test_orchestration_skill_missing_resume_contract_is_flagged(self):
        md = """---
name: planner
category: planning
description: "Planning workflow"
---

# Planner

## Routing Behavior
Invoke `/arch` automatically when blockers exist.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_operational_resilience(parsed)
        assert any("nested-workflow resume contract" in f.gap for f in findings)

    def test_orchestration_skill_resume_contract_is_allowed(self):
        md = """---
name: planner
category: planning
description: "Planning workflow"
---

# Planner

Invoke `/arch` automatically when blockers exist.
This is a nested subworkflow. Return to caller and resume automatically; user re-entry is not required.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_operational_resilience(parsed)
        assert not any("nested-workflow resume contract" in f.gap for f in findings)

    def test_context_reuse_drift_is_flagged_when_followup_skill_can_reask_known_subject(self):
        md = """---
name: arch
category: architecture
description: "Architecture workflow with clarity gate"
---

# Arch

## Stage 0.5: Clarity Gate
Context inference is mandatory.
Follow-up queries should use prior context and infer subject from recent substantive work.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_operational_resilience(parsed)
        assert any("redundant clarification" in f.gap for f in findings)

    def test_context_reuse_guard_is_allowed_when_redundant_clarification_is_forbidden(self):
        md = """---
name: arch
category: architecture
description: "Architecture workflow with clarity gate"
---

# Arch

## Stage 0.5: Clarity Gate
Context inference is mandatory.
Follow-up queries should use prior context and infer subject from recent substantive work.
Asking the user to restate a subject that recent session context already establishes is a workflow error.
Rewrite the query to be self-contained and continue.
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_operational_resilience(parsed)
        assert not any("redundant clarification" in f.gap for f in findings)

    def test_skill_ship_implementation_questions_are_allowed(self):
        md = """---
name: skill-ship
description: "Ship a skill"
---

# Skill Ship

## Open-Ended Questions
- What is the simplest implementation that still preserves the intended design?
- What do we need to prove before this is safe to ship?
"""
        parsed = _parse_skill(Path("."), md)
        findings = _lens_question_strategy(parsed)
        assert findings == []


class TestLensNonGoalsClarity:
    def test_missing_non_goals(self):
        md = "# Test Skill\n\n## Purpose\nSomething."
        findings = _lens_non_goals_clarity(md)
        assert len(findings) == 1
        assert findings[0].lens == "NON_GOALS_CLARITY"
        assert "missing" in findings[0].gap.lower()

    def test_non_goals_present(self):
        md = "# Test Skill\n\n## Non-Goals\nDoes not handle concurrent terminals."
        findings = _lens_non_goals_clarity(md)
        assert len(findings) == 0


class TestAuditRouter:
    def test_nonexistent_skill(self):
        findings = audit("/nonexistent-skill-xyz")
        assert len(findings) >= 1
        assert findings[0].lens == "SETUP"

    def test_valid_skill_returns_findings(self, tmp_path):
        skill = tmp_path / "test-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text("""---
name: test-skill
description: "A test skill"
---

# Test Skill
## Purpose
Does things.
""")
        findings = audit(str(skill))
        assert isinstance(findings, list)


class TestOutcomeSummary:
    def test_verdict_prefers_contract_language_for_strategic_high_findings(self):
        findings = [
            Finding(
                "OPERATIONAL_RESILIENCE",
                "skill lacks explicit operational resilience contract",
                "Missing stale-data guidance",
                "HIGH",
                "source skill",
            )
        ]
        verdict, rationale = _derive_verdict(findings)
        assert verdict == "RIGHT IDEA, WRONG CONTRACT"
        assert "strategy/contract" in rationale.lower()

    def test_outcomes_include_all_distinct_actions_in_priority_order(self):
        findings = [
            Finding("REFERENCE_INTEGRITY", "missing ref", "x", "HIGH", "source skill"),
            Finding("ASSURANCE_STRATEGY", "missing smoke proof", "y", "HIGH", "skill-ship"),
            Finding("REFERENCE_INTEGRITY", "another missing ref", "z", "MEDIUM", "source skill"),
        ]
        outcomes = _derive_outcomes(findings)
        assert outcomes[0][0].startswith("remove or repair broken promised references")
        assert outcomes[0][1] == "source skill"
        assert any("smoke proof" in action for action, _, _ in outcomes)
        assert len(outcomes) == 2

    def test_handoff_offer_prefers_skill_ship_when_it_owns_blocking_work(self):
        findings = [
            Finding("REFERENCE_INTEGRITY", "missing ref", "x", "HIGH", "source skill"),
            Finding("ASSURANCE_STRATEGY", "missing smoke proof", "y", "HIGH", "skill-ship"),
            Finding("TEMPLATE_SYSTEM", "template drift", "z", "MEDIUM", "skill-ship"),
        ]
        handoff = _derive_handoff_offer(findings)
        assert handoff is not None
        owner, rationale, actions = handoff
        assert owner == "skill-ship"
        assert "implementation or correctness" in rationale
        assert len(actions) == 2

    def test_handoff_offer_is_none_when_source_skill_owns_all_actions(self):
        findings = [
            Finding("REFERENCE_INTEGRITY", "missing ref", "x", "HIGH", "source skill"),
            Finding("NON_GOALS_CLARITY", "missing non-goals", "y", "LOW", "source skill"),
        ]
        assert _derive_handoff_offer(findings) is None

    def test_outcome_summary_prints_explicit_skill_ship_handoff(self, capsys):
        findings = [
            Finding("ASSURANCE_STRATEGY", "missing smoke proof", "y", "HIGH", "skill-ship"),
            Finding("REFERENCE_INTEGRITY", "missing ref", "x", "MEDIUM", "source skill"),
        ]
        audit_module.print_outcome_summary(findings)
        output = capsys.readouterr().out
        assert "## Recommended Handoff" in output
        assert "- Recommended next skill: `/skill-ship`" in output
        assert "- Offer this handoff with scope:" in output


class TestTransferReuseDiscovery:
    def test_direct_reference_target_is_ranked_first(self, tmp_path, monkeypatch):
        source = tmp_path / "adf"
        source.mkdir()
        (source / "SKILL.md").write_text("""---
name: adf
description: "Structural decision framework"
category: strategy
---

# ADF

Scope check. Complexity tax. Simpler alternative. Reversibility.
""")

        arch = tmp_path / "arch"
        arch.mkdir()
        (arch / "SKILL.md").write_text("""---
name: arch
description: "Architecture advisor"
category: architecture
---

# Arch

Route to `/adf` when query asks about extraction or over-engineering.
This workflow reasons about boundaries, complexity, and contracts.
""")

        planning = tmp_path / "planning"
        planning.mkdir()
        (planning / "SKILL.md").write_text("""---
name: planning
description: "Implementation planning"
category: planning
---

# Planning

This skill evaluates layers, validators, complexity bias, and contract boundaries.
""")

        monkeypatch.setattr(audit_module, "SKILLS_DIR", tmp_path)
        _, _, targets = discover_transfer_targets("/adf")
        assert targets[0].skill_name == "arch"
        assert targets[0].relation == "direct_consumer"

    def test_indirect_candidate_is_found_without_direct_reference(self, tmp_path, monkeypatch):
        source = tmp_path / "adf"
        source.mkdir()
        (source / "SKILL.md").write_text("""---
name: adf
description: "Structural decision framework"
category: strategy
---

# ADF

Use scope check, simpler alternative, complexity tax, evidence tiers, and reversibility before adding new boundaries to a workflow.
""")

        skill_audit = tmp_path / "skill-audit"
        skill_audit.mkdir()
        (skill_audit / "SKILL.md").write_text("""---
name: skill-audit
description: "Audit skill strategy and outcome quality"
category: analysis
---

# Skill Audit

This skill checks evidence, contracts, boundaries, enforcement, workflow tradeoffs, and architectural decisions.
""")

        monkeypatch.setattr(audit_module, "SKILLS_DIR", tmp_path)
        _, _, targets = discover_transfer_targets("/adf")
        assert any(t.skill_name == "skill-audit" and t.relation == "indirect_candidate" for t in targets)

    def test_typical_questions_mentions_do_not_count_as_direct_reference(self):
        md = """---
name: skill-audit
description: "Audit skill strategy"
category: analysis
---

# Skill Audit

2. **Transfer / Reuse Analysis**
   Typical questions:
   - "does `/adf` have value for `/skill-audit`?"

This skill checks evidence, contracts, boundaries, enforcement, workflow tradeoffs, and architectural decisions.
"""
        parsed = _parse_skill(Path("."), md)
        operational = _operational_reference_text(parsed)
        assert "/adf" not in operational

    def test_transfer_judgment_packet_keeps_direct_targets_and_bounds_indirects(self, tmp_path, monkeypatch):
        source = tmp_path / "adf"
        source.mkdir()
        (source / "SKILL.md").write_text("""---
name: adf
description: "Structural decision framework"
category: strategy
---

# ADF

Use scope check, simpler alternative, complexity tax, evidence tiers, and reversibility before adding new boundaries to a workflow.
""")

        arch = tmp_path / "arch"
        arch.mkdir()
        (arch / "SKILL.md").write_text("""---
name: arch
description: "Architecture advisor"
category: architecture
---

# Arch

Route to `/adf` when query asks about extraction or over-engineering.
This workflow reasons about boundaries, complexity, and contracts.
""")

        for idx in range(20):
            candidate = tmp_path / f"candidate-{idx}"
            candidate.mkdir()
            (candidate / "SKILL.md").write_text(f"""---
name: candidate-{idx}
description: "Analysis candidate"
category: analysis
---

# Candidate

This skill checks evidence, contracts, boundaries, complexity, workflow tradeoffs, and architectural decisions.
""")

        monkeypatch.setattr(audit_module, "SKILLS_DIR", tmp_path)
        packet = build_transfer_judgment_packet("/adf", max_indirect=5)
        assert any(t.skill_name == "arch" for t in packet.direct_targets)
        assert len(packet.indirect_candidates) == 5

    def test_semantic_bonus_can_promote_indirect_candidate_order(self, tmp_path, monkeypatch):
        source = tmp_path / "adf"
        source.mkdir()
        (source / "SKILL.md").write_text("""---
name: adf
description: "Structural decision framework"
category: strategy
---

# ADF

Scope checks, complexity tradeoffs, reversibility, evidence, and simpler alternatives.
""")
        arch = tmp_path / "arch"
        arch.mkdir()
        (arch / "SKILL.md").write_text("""---
name: arch
description: "Architecture advisor"
category: architecture
---

# Arch

Route to `/adf` for structural extraction and over-engineering checks.
""")
        planning = tmp_path / "planning"
        planning.mkdir()
        (planning / "SKILL.md").write_text("""---
name: planning
description: "Implementation planning"
category: planning
---

# Planning

Workflow orchestration, contract boundaries, phased plans, execution semantics, and evidence for execution tradeoffs.
""")
        skill_ship = tmp_path / "skill-ship"
        skill_ship.mkdir()
        (skill_ship / "SKILL.md").write_text("""---
name: skill-ship
description: "Implementation correctness"
category: execution
---

# Skill Ship

Implementation correctness, smoke validation, tests, hooks, validators, complexity tradeoffs, and evidence for simpler alternatives.
""")

        monkeypatch.setattr(audit_module, "SKILLS_DIR", tmp_path)
        monkeypatch.setattr(
            audit_module,
            "_semantic_transfer_bonus_map",
            lambda source, candidates: {"skill-ship": (4, "semantic embedding similarity=0.91")},
        )

        _, _, targets = discover_transfer_targets("/adf")
        indirects = [t for t in targets if t.relation == "indirect_candidate"]
        assert indirects[0].skill_name == "skill-ship"
        assert any("semantic embedding similarity=0.91" in reason for reason in indirects[0].reasons)

    def test_semantic_bonus_map_falls_back_cleanly_when_daemon_unavailable(self, tmp_path, monkeypatch):
        source = tmp_path / "adf"
        source.mkdir()
        source_parsed = _parse_skill(source, """---
name: adf
description: "Structural decision framework"
category: strategy
---

# ADF

Scope checks, complexity tradeoffs, evidence.
""")
        candidate = tmp_path / "planning"
        candidate.mkdir()
        candidate_parsed = _parse_skill(candidate, """---
name: planning
description: "Implementation planning"
category: planning
---

# Planning

Workflow orchestration, contract boundaries, execution semantics.
""")

        monkeypatch.setattr(audit_module, "_load_embed_client", lambda: None)
        assert _semantic_transfer_bonus_map(source_parsed, [candidate_parsed]) == {}

    def test_direct_consumers_stay_ahead_of_semantic_indirects(self, tmp_path, monkeypatch):
        source = tmp_path / "adf"
        source.mkdir()
        (source / "SKILL.md").write_text("""---
name: adf
description: "Structural decision framework"
category: strategy
---

# ADF

Scope checks, complexity tradeoffs, reversibility, evidence, and simpler alternatives.
""")
        arch = tmp_path / "arch"
        arch.mkdir()
        (arch / "SKILL.md").write_text("""---
name: arch
description: "Architecture advisor"
category: architecture
---

# Arch

Route to `/adf` for structural extraction and over-engineering checks.
""")
        planning = tmp_path / "planning"
        planning.mkdir()
        (planning / "SKILL.md").write_text("""---
name: planning
description: "Implementation planning"
category: planning
---

# Planning

Workflow orchestration, contract boundaries, phased plans, execution semantics.
""")

        monkeypatch.setattr(audit_module, "SKILLS_DIR", tmp_path)
        monkeypatch.setattr(
            audit_module,
            "_semantic_transfer_bonus_map",
            lambda source, candidates: {"planning": (9, "semantic embedding similarity=0.99")},
        )

        _, _, targets = discover_transfer_targets("/adf")
        assert targets[0].skill_name == "arch"
        assert targets[0].relation == "direct_consumer"


class TestFinding:
    def test_finding_is_namedtuple(self):
        f = Finding("TEST", "a gap", "evidence here", "HIGH")
        assert f.lens == "TEST"
        assert f.gap == "a gap"
        assert f.evidence == "evidence here"
        assert f.priority == "HIGH"
        assert f.owner == "source skill"
