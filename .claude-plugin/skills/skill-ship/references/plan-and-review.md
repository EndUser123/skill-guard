---
type: workflow
load_when: creation
priority: recommended
estimated_lines: 150
---

# Plan-and-Review Before Code Changes

> Create plan → adversarial review → execute workflow for risky changes
> Source: Extracted from `/refactor` skill (lines 877-933)

## Purpose

For complex skill changes (>5 workflow steps), separate planning from execution. This prevents architecture mistakes that are expensive to fix later.

## The Workflow

```
1. CREATE REFACTORING PLAN
   ├── Document all changes with risk analysis
   ├── Effort estimates and rollback strategies
   └── Output: Plan JSON + markdown

2. ADVERSARIAL REVIEW OF PLAN
   ├── Stress-test the plan itself (not tests yet)
   ├── Review for risks, complexity, dependencies
   └── Output: Review findings, recommendations

3. REVISE PLAN (if needed)
   ├── Address critical issues found
   ├── **Produce clean final plan artifact** — findings synthesized, NOT appended raw
   ├── **Artifact must pass artifact-rubric.md before proceeding to execute**
   └── Re-review if major changes

4. EXECUTE (only after plan approval)
   └── Implement with confidence
```

## Plan Structure

### Refactor Plan Schema

```json
{
  "metadata": {
    "created_at": "2026-03-16T12:00:00Z",
    "target_path": ".claude/skills/my-skill/",
    "session_id": "abc123"
  },
  "overview": {
    "total_findings": 15,
    "priority_breakdown": {"P0": 3, "P1": 5, "P2": 5, "P3": 2},
    "effort_estimate": "4-6 hours",
    "risk_level": "MEDIUM"
  },
  "changes_by_priority": [
    {
      "priority": "P0",
      "changes": [
        {
          "id": "P0-001",
          "description": "Fix YAML syntax error in frontmatter",
          "files": ["SKILL.md"],
          "risk_analysis": "LOW - Simple syntax fix",
          "rollback_strategy": "git revert HEAD"
        }
      ]
    }
  ],
  "execution_order": [
    "1. Fix P0 issues (bugs, race conditions)",
    "2. Fix P1 issues (error handling)",
    "3. Address P2 issues (DRY violations)",
    "4. Fix P3 issues (conventions)"
  ],
  "validation_strategy": {
    "test_approach": "Characterization tests for each change",
    "rollback_trigger": "Any test failure or unexpected behavior",
    "validation_tools": ["pytest", "yaml-lint"]
  }
}
```

### Plan to Markdown

```python
from lib.refactor_plan import plan_to_markdown

markdown = plan_to_markdown(plan)
```

Output:
```markdown
# Refactoring Plan: my-skill

## Overview
- **Total findings**: 15
- **Priority breakdown**: P0: 3, P1: 5, P2: 5, P3: 2
- **Effort estimate**: 4-6 hours
- **Risk level**: MEDIUM

## Changes by Priority

### P0: Bugs & Race Conditions
1. **P0-001**: Fix YAML syntax error
   - Files: SKILL.md
   - Risk: LOW
   - Rollback: `git revert HEAD`

## Execution Order
1. Fix P0 issues
2. Fix P1 issues
3. Address P2 issues
4. Fix P3 issues

## Validation Strategy
- Test approach: Characterization tests
- Rollback trigger: Any test failure
- Validation tools: pytest, yaml-lint
```

## Adversarial Review

### Review Findings Schema

```json
{
  "findings": [
    {
      "id": "RISK-001",
      "severity": "HIGH",
      "description": "Regex changes marked as LOW risk",
      "concern": "Regex can introduce syntax errors",
      "recommendation": "Mark as MEDIUM or HIGH risk"
    }
  ],
  "recommendations": [
    {
      "id": "REC-001",
      "action": "Use AST-based refactoring (LibCST) instead of regex",
      "rationale": "AST is safer for structural changes"
    }
  ],
  "risk_factors": [
    "Batch operations increase risk",
    "Effort > 8 hours, consider splitting"
  ],
  "overall_assessment": "CONDITIONAL"
}
```

### Review Checklist

From `/refactor` plan review:

| Check | Finding | Action |
|-------|---------|--------|
| **RISK-001** | Regex changes marked as LOW risk | Mark as MEDIUM or HIGH risk |
| **ROLLBACK-001** | Insufficient rollback strategy | Add specific revert commands |
| **COMPLEX-001** | Batch operations (higher risk) | Recommend splitting into smaller sessions |
| **IMPORT-001** | Import changes can break loading | Add test for module import |
| **EFFORT-001** | Large refactoring (>8 hours) | Split into multiple sessions |
| **PRIORITY-001** | Too many P0 issues | Fix bugs first, then refactor |

### What the Review Checks

1. **Regex risk**: Regex can introduce syntax errors → Mark appropriate risk level
2. **Rollback planning**: Each change needs specific rollback command
3. **Batch operations**: Larger changes = higher risk, consider splitting
4. **Import changes**: Can break module loading, need import tests
5. **Effort vs risk**: Large refactors should be split
6. **Priority balance**: Too many P0 issues suggests wrong focus

## Integration with /skill-ship

### Phase 2: Creation (for complex skills)

```yaml
# Phase 2 workflow_steps:
- phase_2_creation_complex: |
    For complex skills (>5 workflow steps):
    1. Create structured plan (changes, risks, rollback)
    2. Adversarial review of plan (not tests yet)
    3. Revise plan if critical issues found
    4. Execute only after plan approval
```

### When to Use Plan-and-Review

| Skill Complexity | Use Plan-and-Review? |
|-----------------|---------------------|
| Simple (<3 steps) | No |
| Medium (3-5 steps) | Optional |
| Complex (>5 steps) | **Yes, required** |
| Multi-file changes | **Yes, required** |
| Breaking changes | **Yes, required** |

## Benefits

| Benefit | Impact |
|---------|--------|
| **Prevent architecture mistakes** | Catch issues before implementation |
| **Better estimates** | Realistic effort and timeline |
| **Rollback safety** | Clear revert strategy for each change |
| **Stakeholder alignment** | Plan review gets buy-in before coding |
| **Confidence** | Execute with certainty after review |

## Real-World Example

### What This Would Have Prevented

From `/refactor` (lines 933-938):

> "This would have prevented the 8 syntax errors:
> The plan review would have flagged:
> - 'Batch consolidation using regex' → COMPLEX-001
> - 'Regex changes marked as LOW risk' → RISK-001
> - Recommendation: 'Use AST-based refactoring (LibCST) instead of regex'"

The review caught that regex-based batch refactoring was high-risk. AST-based refactoring would have prevented 8 syntax errors.

## Libraries

### refactor_plan.py

```python
from lib.refactor_plan import (
    create_refactor_plan,
    plan_to_markdown,
    save_plan
)

# Create plan from findings
plan = create_refactor_plan(
    findings=[...],
    target_path=".claude/skills/my-skill/",
    session_id="abc123"
)

# Convert to markdown
markdown = plan_to_markdown(plan)

# Save to file
plan_file = save_plan(plan, output_dir=Path(".evidence/refactor/"))
```

### plan_review.py

```python
from lib.plan_review import (
    adversarial_review_plan,
    review_to_markdown
)

# Review plan
review = adversarial_review_plan(plan)

# Convert review to markdown
markdown = review_to_markdown(review)

# Check assessment
if review["overall_assessment"] == "APPROVED":
    print("Plan approved - proceed with execution")
elif review["overall_assessment"] == "CONDITIONAL":
    print("Plan approved with conditions - address recommendations first")
else:  # ADVISED_AGAINST
    print("Plan not approved - revise and resubmit")
```

---

**Source**: `/refactor` skill (Plan and Review Libraries)
**Related**: `references/workflow-phases.md` (Phase 2 Creation)
