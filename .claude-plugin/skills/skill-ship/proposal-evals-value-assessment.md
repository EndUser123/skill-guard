# Evals Value Assessment - Phase 3.5 Enhancement

## Insertion Point
Add this section after line 222 in `references/workflow-phases.md`:
```
**Goal**: Validate skill performance through empirical testing and iteration

**Evals Value Assessment** (NEW - RUN FIRST):
```

## Decision Tree

```python
# Pseudocode for evals recommendation
def should_recommend_evals(skill_analysis, user_request):
    """
    Returns: "RECOMMENDED" | "OPTIONAL" | "SKIP"
    """
    score = 0

    # 1. User explicit request (strongest signal)
    if user_request == "evals":
        return "RECOMMENDED"
    if user_request == "no_evals":
        return "SKIP"

    # 2. Skill characteristics (auto-detected)
    if skill_analysis["trigger_clarity"] == "ambiguous":
        score += 3  # Need to test if description works

    if skill_analysis["user_facing"] and skill_analysis["workflow_branches"] > 2:
        score += 2  # Multiple paths need coverage testing

    if skill_analysis["type"] == "knowledge" and not skill_analysis["has_objective_output"]:
        score -= 2  # Subjective outputs hard to eval

    if skill_analysis["mature"] and skill_analysis["field_tested"]:
        score -= 3  # Already proven in practice

    # 3. Decision thresholds
    if score >= 3:
        return "RECOMMENDED"
    elif score >= 1:
        return "OPTIONAL"
    else:
        return "SKIP"
```

## Assessment Criteria

| Criterion | Points | Rationale |
|-----------|--------|-----------|
| **User explicitly requests evals** | +5 | User knows they need testing |
| **Ambiguous trigger phrases** | +3 | Need to verify skill actually triggers |
| **User-facing + multiple workflow paths** | +2 | Complex workflow needs coverage |
| **New skill (not field-tested)** | +2 | No real-world validation yet |
| **Subjective output (writing/art)** | -2 | Hard to measure objectively |
| **Mature + battle-tested** | -3 | Already proven in practice |
| **Infrastructure/internal skill** | -2 | Users don't invoke directly |

## Output Format

Add to Phase 3.5 after assessment:

```markdown
### Evals Recommendation: [RECOMMENDED/OPTIONAL/SKIP]

**Assessment Score**: [X]/10

**Rationale**:
- [Criterion 1]: [+/-X points] - [Reason]
- [Criterion 2]: [+/-X points] - [Reason]

**Decision**: [RECOMMENDED/OPTIONAL/SKIP]

**If RECOMMENDED**:
→ Create evals/evals.json with test prompts
→ Run evaluation suite with skill-creator
→ Use results for description optimization

**If OPTIONAL**:
→ Ask user: "Add evals for trigger accuracy testing? (y/n)"
→ Proceed based on user preference

**If SKIP**:
→ Note: "Evals skipped - [reason]"
→ Proceed to Phase 4 (Optimization)
```

## Implementation

### File: `references/workflow-phases.md`

**Insert after line 222**:

```markdown
**Evals Value Assessment** (NEW):

Before choosing evaluation mode, assess whether evals provide value:

| Assessment | Score | Action |
|------------|-------|--------|
| User explicitly requested evals | +5 | **RECOMMEND** - User wants testing |
| Ambiguous trigger phrases | +3 | **RECOMMEND** - Test trigger accuracy |
| User-facing + 3+ workflow branches | +2 | **RECOMMEND** - Test coverage needed |
| New skill (no field testing) | +2 | **OPTIONAL** - Consider for confidence |
| Mature + battle-tested | -3 | **SKIP** - Already proven |
| Subjective outputs (writing/art) | -2 | **SKIP** - Hard to measure |
| Infrastructure/internal | -2 | **SKIP** - Not user-facing |

**Thresholds**:
- Score ≥ 3: **RECOMMENDED** - Add evals to workflow
- Score 1-2: **OPTIONAL** - Ask user preference
- Score ≤ 0: **SKIP** - Note rationale and continue

**Output**: Display assessment with rationale and decision
```

### File: `SKILL.md` (skill-ship)

**Update Phase 3.5 table entry**:

| Phase | Goal | Key Skills | Template | Skip When |
|-------|------|------------|----------|-----------|
| **3.5. Evals Assessment** | Determine if evals provide value | internal: assessment logic | Template 2 | Score ≤ 0 (auto-skip) |
| **3.5. Evaluation** | Empirical testing with evals | skill-creator (evals) | Template 1 | Assessment says SKIP |

## Example Outputs

### Example 1: Evals Recommended (Score: 5)
```
### Evals Recommendation: RECOMMENDED

**Assessment Score**: 5/10

**Rationale**:
- Ambiguous trigger phrases ("fix this", "help with X"): +3 points
- User-facing skill with multiple workflow paths: +2 points

**Decision**: RECOMMENDED

This skill has ambiguous triggers and multiple workflow branches. Evals will:
1. Verify the skill triggers on expected user queries
2. Test all workflow branches work correctly
3. Provide data for description optimization

→ Proceed with evals/evals.json creation
```

### Example 2: Evals Optional (Score: 2)
```
### Evals Recommendation: OPTIONAL

**Assessment Score**: 2/10

**Rationale**:
- New skill (no field testing yet): +2 points

**Decision**: OPTIONAL

This skill is new but has clear, specific triggers. Evals could help
validate trigger accuracy, but the skill description is well-defined.

User preference: Add evals for trigger testing? (y/n)
```

### Example 3: Evals Skipped (Score: -3)
```
### Evals Recommendation: SKIP

**Assessment Score**: -3/10

**Rationale**:
- Mature, battle-tested skill: -3 points

**Decision**: SKIP

This skill is proven in practice with extensive field testing. Evals would
provide marginal value over existing real-world validation.

Note: Evals skipped - skill already validated through use
→ Proceed to Phase 4 (Optimization)
```

## Benefits

1. **Targeted evals**: Only recommend evals when they provide actual value
2. **User respect**: Honor "no_evals" requests explicitly
3. **Efficiency**: Skip evals for mature/internal skills
4. **Clarity**: Explain WHY evals are/aren't recommended
5. **Flexibility**: Allow users to override with explicit request

## Testing

After implementation, verify with these test cases:

| Skill Type | Triggers | Maturity | Expected Score | Expected Decision |
|------------|----------|----------|----------------|-------------------|
| New user-facing skill | Ambiguous | New | +5 | RECOMMENDED |
| Mature infrastructure skill | Specific | Battle-tested | -3 | SKIP |
| New internal utility | Specific | New | -1 | SKIP |
| User workflow skill | Clear | New | +2 | OPTIONAL |
| User explicitly requests evals | Any | Any | +5 | RECOMMENDED |
