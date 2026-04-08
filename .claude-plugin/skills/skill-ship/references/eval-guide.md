---
type: evaluation
load_when: evaluation
priority: mandatory
estimated_lines: 200
---

# Skill Evaluation Guide

Complete guide for using skill-creator's evaluation system with /skill-ship.

## Overview

Phase 3.5 (Evaluation & Iteration) of the skill-ship workflow uses skill-creator's evaluation system to empirically test skill performance through:

1. **Eval suites**: Structured test prompts in `evals/evals.json`
2. **Performance reports**: Variance analysis via `eval-viewer/generate_review.py`
3. **Description optimization**: Improving skill triggering accuracy

## Evaluation Modes

Phase 3.5 offers two distinct evaluation modes:

### Trial Mode (Before Installing)
**Purpose**: "Try before commit" - quick informal testing
- Test-drive skill with 2-3 representative tasks
- Evaluate: Does it help? Clear instructions?
- Decision: keep, pass, or try another
- Use case: Informal skill evaluation, personal use

### Evaluation Mode (Before Publishing)
**Purpose**: "Evaluate before publish" - formal quality audit
- Spawn specialized reviewers for structure/safety/usefulness
- Comprehensive quality audit with formal test suite
- Generate recommendations for improvements
- Use case: Skills intended for public sharing

**Mode Selection**: Phase 3.5 will ask: "Trial mode (test-drive) or Evaluation mode (quality audit)?"

## Prerequisites

### Required: skill-creator Plugin

The evaluation system requires the skill-creator plugin from:

```
~/.claude/plugins/cache/claude-plugins-official/skill-creator/
```

**Installation**: If not present, install via:
```bash
# Using universal-skills-manager
/universal-skills-manager search skill-creator
```

### Verify Installation

```bash
# Check if skill-creator plugin exists
ls ~/.claude/plugins/cache/claude-plugins-official/skill-creator/

# Should show:
# - skill-creator/
#   - scripts/
#     - generate_review.py
#   - SKILL.md
```

## Creating an Eval Suite

### Directory Structure

```
.claude/skills/your-skill/
├── SKILL.md
├── evals/
│   └── evals.json          # Test prompts and success criteria
└── references/
    └── workflow-phases.md
```

### evals.json Structure

See `examples/eval-example.json` for a complete template.

**Required fields**:
```json
{
  "skill_name": "your-skill-name",
  "benchmarks": {
    "trigger_accuracy_target": 0.80,
    "output_consistency_target": 0.90,
    "execution_success_target": 0.95
  },
  "evals": [
    {
      "id": "unique-test-id",
      "name": "Human-readable test name",
      "prompt": "Test prompt to run",
      "expected_behavior": {
        "should_trigger": true,
        "target_skill": "/skill-name"
      },
      "success_criteria": [
        "Specific outcome 1",
        "Specific outcome 2"
      ],
      "priority": "high|medium|low"
    }
  ]
}
```

### Test Categories

**1. Trigger Tests** (trigger-*)
Test if skill activates with expected phrases:
```json
{
  "id": "trigger-001",
  "prompt": "help me create a skill for code review",
  "expected_behavior": {
    "should_trigger": true,
    "target_skill": "/skill-ship"
  },
  "success_criteria": [
    "User sees skill-ship workflow phases",
    "Phase 1 discovery begins"
  ]
}
```

**2. Execution Tests** (execution-*)
Test specific workflow phases:
```json
{
  "id": "execution-002",
  "name": "Phase 3 quality validation",
  "prompt": "validate this new skill: /my-skill",
  "expected_behavior": {
    "should_trigger": true,
    "phase": "quality"
  },
  "success_criteria": [
    "Invokes /testing-skills with skill path",
    "Returns validation report"
  ]
}
```

**3. Output Tests** (output-*)
Test output format consistency:
```json
{
  "id": "output-001",
  "prompt": "create a skill for api documentation",
  "success_criteria": [
    "Uses Template 2 (Executive Summary Format)",
    "No markdown syntax errors"
  ]
}
```

**4. Integration Tests** (integration-*)
Test end-to-end workflows:
```json
{
  "id": "integration-001",
  "prompt": "help me build and ship a new claude skill from scratch",
  "expected_behavior": {
    "full_workflow": true
  },
  "success_criteria": [
    "Phase 1: Discovery with similarity check",
    "Phase 2: Creation with progressive disclosure",
    "Phase 3: Quality validation",
    "Context preserved across all phases"
  ]
}
```

## Running the Eval Suite

### Step 1: Create evals/evals.json

Place your test suite in the skill directory:
```bash
.claude/skills/your-skill/evals/evals.json
```

### Step 2: Run Evaluation

Invoke skill-creator's eval system:
```bash
# Via skill-ship
/skill-ship eval /your-skill

# Or directly via skill-creator
/skill-creator eval /your-skill
```

### Step 3: Generate Performance Report

Use eval-viewer to analyze results:
```bash
python ~/.claude/plugins/cache/claude-plugins-official/skill-creator/eval-viewer/generate_review.py
```

This generates a performance report with:
- **Trigger accuracy**: % of tests that correctly activated the skill
- **Output consistency**: % of tests with format-compliant output
- **Execution success**: % of tests that completed without errors
- **Variance analysis**: Comparison against benchmarks

## Interpreting Results

### Performance Metrics

| Metric | Target | Action if Below Target |
|--------|--------|----------------------|
| Trigger accuracy | ≥80% | Run description optimization |
| Output consistency | ≥90% | Review output format templates |
| Execution success | ≥95% | Debug workflow execution paths |
| Variance | Low variance | No action needed |

### Variance Analysis

**Low variance**: Consistent performance across multiple runs ✅
**High variance**: Unreliable behavior, needs investigation ⚠️

Example variance report:
```
Trigger Accuracy: 82% (target: ≥80%) ✅
Variance: Low (±2% across 5 runs)

Output Consistency: 75% (target: ≥90%) ❌
Variance: High (±15% across 5 runs)
Issue: Template 2 format not consistently applied
Fix: Review output-format-templates.md examples
```

## Description Optimization

If trigger accuracy < 80%, optimize the skill description:

### Problem: Poor Triggering

**Symptom**: Skill doesn't activate with expected phrases
**Diagnosis**: Description keywords don't match user language
**Solution**: Optimize description using skill-creator's optimizer

### Optimization Process

1. **Analyze failing prompts**: Which phrases didn't trigger?
2. **Extract keywords**: What terms do users actually use?
3. **Update description**: Add missing keywords to skill description
4. **Re-run eval suite**: Verify improvement

### Example

**Before** (poor triggering):
```yaml
description: "Skill for creating and improving Claude capabilities"
```

**After** (optimized):
```yaml
description: "Create, improve, or audit skills. Use when building new capabilities, enhancing existing skills, or validating skill quality."
```

**Result**: Trigger accuracy improved from 65% → 88%

## Best Practices

### 1. Start Small
Begin with 3-5 high-priority tests covering:
- 1 trigger test (basic activation)
- 1 execution test (core workflow)
- 1 output test (format validation)

### 2. Test Real User Scenarios
Use actual user queries from:
- Support requests
- Documentation examples
- Your own usage patterns

### 3. Independent Tests
Each test should validate ONE thing:
- ✅ Good: "Test Phase 1 similarity conflict detection"
- ❌ Bad: "Test entire workflow from Phase 1 to Phase 5"

### 4. Clear Success Criteria
Avoid subjective success criteria:
- ✅ Good: "Displays conflict table with overlapping features"
- ❌ Bad: "Provides good user experience"

### 5. Priority Levels
Mark critical tests as `priority: "high"`:
- High: Core functionality must work
- Medium: Important but not blocking
- Low: Nice-to-have features

## Continuous Improvement

### When to Run Evals

1. **Before shipping**: Verify production readiness
2. **After changes**: Ensure no regressions
3. **Regular intervals**: Catch performance degradation
4. **User reports**: Validate reported issues

### Iteration Loop

```
1. Run eval suite
   ↓
2. Analyze performance report
   ↓
3. Identify gaps (trigger accuracy < 80%, etc.)
   ↓
4. Apply fixes (description optimization, bug fixes)
   ↓
5. Re-run eval suite
   ↓
6. Verify improvement
   ↓
7. Repeat until satisfaction threshold met
```

### Satisfaction Threshold

- **Minimum viable**: 70% overall pass rate
- **Production ready**: 80% overall pass rate
- **Excellent**: 90%+ overall pass rate

## Example Workflow

### Scenario: Improving /skill-ship Triggering

**Issue**: Users say "create a skill" but skill-ship doesn't activate

**Step 1**: Create eval test
```json
{
  "id": "trigger-phrase-test",
  "prompt": "create a skill for code review",
  "expected_behavior": {
    "should_trigger": true,
    "target_skill": "/skill-ship"
  }
}
```

**Step 2**: Run eval suite
```bash
/skill-creator eval /skill-ship
```

**Result**: 65% trigger accuracy (below 80% target)

**Step 3**: Analyze failures
- Failing prompts use "create" verb
- Current description uses "build" and "develop"

**Step 4**: Optimize description
```yaml
# Before
description: "Master coordinator for skill creation and improvement..."

# After
description: "Create, build, or improve skills. Master coordinator for comprehensive skill development..."
```

**Step 5**: Re-run eval
```bash
/skill-creator eval /skill-ship
```

**Result**: 88% trigger accuracy ✅

**Step 6**: Ship improvement
Update SKILL.md with optimized description

## Troubleshooting

### Issue: Eval suite won't run

**Symptom**: "evals/evals.json not found"
**Fix**: Create evals/ directory and evals.json file

### Issue: Performance report missing

**Symptom**: "eval-viewer/generate_review.py not found"
**Fix**: Verify skill-creator plugin is installed

### Issue: High variance in results

**Symptom**: Unreliable behavior across runs
**Fix**:
- Check for non-deterministic workflows (randomness, external dependencies)
- Review success criteria (are they objective?)
- Isolate flaky tests

### Issue: All tests passing but users report problems

**Symptom**: 100% pass rate but real-world failures
**Fix**: Add tests based on actual user scenarios, not idealized cases

## Integration with skill-ship Workflow

### Phase 3.5: Evaluation & Iteration

When to run evals:
- After Phase 2 (Creation & Structuring) complete
- After Phase 3 (Quality & Validation) passes
- Before Phase 4 (Optimization & Enhancement)

### Skip Criteria

Skip Phase 3.5 evaluation when:
- Simple skills with objectively verifiable outputs (file transforms, data extraction)
- User explicitly declines evaluation ("just vibe with me")
- Skills with subjective outputs (writing style, art)

## References

- **Example eval suite**: `examples/eval-example.json`
- **skill-creator documentation**: `~/.claude/plugins/cache/claude-plugins-official/skill-creator/SKILL.md`
- **Output format templates**: `references/output-format-templates.md`
- **Workflow phases**: `references/workflow-phases.md`

## Status

Production Standard (v1.0)
Last Updated: March 14, 2026
