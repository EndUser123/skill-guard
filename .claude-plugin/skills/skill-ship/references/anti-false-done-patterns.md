# Anti-False-Done Guardrails

> Explicit completion evidence requirements to prevent premature "done" claims
> Source: Extracted from `/agent_team` (lines 113-136)

## Purpose

Prevent skills from claiming completion without verification. False completion claims waste user time and erode trust.

## The Problem

```python
# WRONG: Agent claims completion without evidence
print("Skill complete!")
# (No verification tests run)
# (No evidence collected)
# (User discovers broken behavior later)
```

## The Solution

Require explicit evidence for each completion claim:

```python
# CORRECT: Agent provides evidence before claiming complete
evidence = {
    "RED": {"test_file": "test_skill.py", "status": "FAIL"},
    "GREEN": {"test_file": "test_skill.py", "status": "PASS"},
    "VERIFY": {"validation": "YAML valid", "status": "PASS"}
}
if all(e["status"] == "PASS" for e in evidence.values()):
    print("Skill complete with evidence")
```

## Completion Evidence Requirements

### For Code Changes

| Phase | Evidence Required | Verification |
|-------|------------------|--------------|
| **RED** | Test FAILS before changes | `pytest test_file.py -v` shows failure |
| **GREEN** | Test PASSES after changes | `pytest test_file.py -v` shows success |
| **REGRESSION** | No new test failures | `pytest tests/ -v` shows no new failures |
| **VERIFY** | Validation checks pass | YAML syntax, triggers work, execution verified |

### For Documentation Changes

| Evidence Type | Required |
|---------------|----------|
| **Links** | All referenced files exist |
| **Syntax** | Markdown/YAML syntax valid |
| **Accuracy** | Code examples match actual behavior |

### For Workflow Skills

| Evidence Type | Required |
|---------------|----------|
| **Execution** | Workflow runs end-to-end without blocking |
| **Output** | Output format matches template |
| **Edge Cases** | Edge cases documented and tested |

## Implementation

### Evidence Collection Function

```python
from .evidence import collect_test_evidence, verify_tdd_red, verify_tdd_green

def provide_completion_evidence(skill_name: str) -> dict:
    """Collect and verify completion evidence."""
    evidence = {}

    # 1. RED phase: Characterization test must fail
    red_artifact = collect_test_evidence(f"pytest tests/test_{skill_name}.py -v")
    red_result = verify_tdd_red(red_artifact)
    evidence["RED"] = {
        "test_file": red_artifact.metadata.get("test_file"),
        "status": "PASS" if red_result.is_verified else "FAIL"
    }

    # 2. GREEN phase: Test must pass after implementation
    green_artifact = collect_test_evidence(f"pytest tests/test_{skill_name}.py -v")
    green_result = verify_tdd_green(green_artifact)
    evidence["GREEN"] = {
        "test_file": green_artifact.metadata.get("test_file"),
        "status": "PASS" if green_result.is_verified else "FAIL",
        "failure_output": green_result.failure_output if not green_result.is_verified else None
    }

    # 3. REGRESSION phase: No new failures
    regression_artifact = collect_test_evidence("pytest tests/ -v")
    failed = regression_artifact.data.get("test_stats", {}).get("failed", 0)
    evidence["REGRESSION"] = {
        "status": "PASS" if failed == 0 else "FAIL",
        "new_failures": failed
    }

    # 4. VERIFY phase: Validation checks
    evidence["VERIFY"] = validate_skill_structure(skill_name)

    return evidence

def can_claim_complete(evidence: dict) -> bool:
    """Check if all evidence shows PASS status."""
    return all(e["status"] == "PASS" for e in evidence.values())
```

### Blocker Contract Pattern

When stopping before completion, output a blocker contract:

```python
def format_blocker(blocker: str, current_task: str, evidence: dict) -> str:
    """Format a blocker contract for incomplete work."""
    return f"""
BLOCKED: {blocker}

Current Task: {current_task}

Evidence:
{format_evidence(evidence)}

Required Action:
1. Fix blocker issue
2. Re-run verification
3. Claim complete only with evidence

Next Steps:
1a: Fix {blocker}
1b: Verify fix with test
1c: Re-check completion evidence
"""
```

Example blocker output:
```
BLOCKED: YAML syntax error in SKILL.md

Current Task: Phase 2 - Create skill structure

Evidence:
RED: PASS (test_skill.py fails as expected)
GREEN: FAIL (test_skill.py should pass but has syntax error)
REGRESSION: N/A (not reached)
VERIFY: FAIL (YAML parse error at line 15)

Required Action:
Fix YAML syntax, then re-run tests

Next Steps:
1a: Fix YAML syntax error (line 15)
1b: Run pytest tests/test_skill.py -v
1c: Verify GREEN phase passes
```

## Integration with /skill-ship

### Phase 3: Quality & Validation

Add completion evidence requirements to Phase 3:

```yaml
# Phase 3 workflow_steps:
- phase_3_quality: |
    Validate YAML, triggers, execution paths
    AND collect completion evidence:
    - RED: Characterization tests FAIL
    - GREEN: Tests PASS after changes
    - REGRESSION: No new failures
    - VERIFY: Validation checks pass
```

### Quality Gate Table

| Test | Status | Evidence | Fix |
|------|--------|----------|-----|
| YAML completeness | - | - | - |
| Trigger accuracy | - | - | - |
| RED phase | - | `pytest ... -v` output showing failure | - |
| GREEN phase | - | `pytest ... -v` output showing success | - |
| REGRESSION phase | - | `pytest tests/ -v` showing no new failures | - |

## Anti-Regression Review Gate

From `/agent_team` (lines 129-136):

Add regression review to completion checks:

```python
regression_review_checks = [
    "spec_alignment",      # Does output match specification?
    "hallucination_risk",  # Any fake APIs/dependencies?
    "test_lint_status",    # Tests and linting pass?
    "architecture_drift",  # Unintended structural changes?
    "risky_broad_edits",   # Large edits justified by scope?
]
```

## Error Messages Reference

| Phase | Error Message | User Action |
|-------|--------------|-------------|
| **RED** | `TDD RED violated: {test_file} must FAIL before changes` | Write test capturing current behavior |
| **GREEN** | `TDD GREEN failed: {test_file} must PASS. Failures: {output}` | Fix code to make test pass |
| **REGRESSION** | `REGRESSION failed: {N} new failures detected` | Fix regressions before completing |

## Benefits

| Benefit | Impact |
|---------|--------|
| **Trust** | Users can rely on "complete" claims |
| **Speed** | No time wasted on broken skills |
| **Quality** | Evidence-driven development |
| **Debugging** | Evidence artifacts for post-mortem |

---

**Source**: `/agent_team` (Build Reliability Guardrails), `/refactor` (TDD Checkpoint)
**Related**: `references/workflow-phases.md` (Phase 3 Quality & Validation)
