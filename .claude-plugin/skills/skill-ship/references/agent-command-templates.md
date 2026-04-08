---
type: workflow
load_when: creation
priority: recommended
estimated_lines: 250
---

# Agent Command Templates

> Reusable command templates for Claude Code workflows
> Source: Extracted from `/agent_team` skill

Use these templates when generating custom commands for Claude Code workflows.

## `/implement-task` Template

```text
Implement the requested task in the current repository.

Inputs:
- Task: <task description>
- Requirements:
  1) <requirement 1>
  2) <requirement 2>
- Constraints:
  - <constraint 1>
  - <constraint 2>

Process:
1) Inspect relevant files and existing patterns before editing.
2) Propose a short plan with affected files and test strategy.
3) Apply minimal, scoped changes aligned to existing architecture/style.
4) Run relevant tests/linters for touched scope.
5) If checks fail, iterate up to <N> attempts; then re-plan.

Do not:
- Invent APIs/dependencies without repo/doc verification.
- Finalize while tests/linters for touched scope are failing.
- Expand scope without explicit justification.

Final output format:
1) Requirement Checklist:
   - [x]/[ ] <requirement> -> <evidence: file/test>
2) Change Summary:
   - <file>: <what changed and why>
3) Validation:
   - <test/lint command> -> <result>
4) Risks:
   - <known edge cases or follow-ups>
```

## `/review-changes` Template

```text
Review the current diff and test outcomes as a skeptical senior reviewer.

Required review categories:
1) Spec alignment
2) Tool/test usage correctness
3) Hallucinated API/dependency risk
4) Architecture/style consistency
5) Scope and regression risk

Instructions:
- For each category, output either:
  - "No issue found", or
  - Concrete findings with file references and suggested fix.
- Flag missing validation if tests/linters were not run for touched scope.
- Call out broad/high-risk edits not justified by task requirements.

Final output format:
1) Findings (ordered by severity)
2) Validation gaps
3) Approval status:
   - APPROVE
   - APPROVE WITH FIXES
   - BLOCK
4) If blocked, include:
   - BLOCKED: <reason>
   - Next actions (numbered)
```

## `/implement-with-review` Composite Pattern

Use when users want one command that includes both delivery and critique.

```text
Run `/implement-task` first, then immediately run `/review-changes` on the result.
If review is BLOCK or APPROVE WITH FIXES, apply fixes and re-run review once.
Only finalize when:
- All requirements are mapped to evidence, and
- Validation for touched scope is green or explicitly accepted by user.
```

## Notes

- Keep templates short and adapt only placeholders (`<...>`).
- Prefer repository-specific constraints over generic policy text.
- Pair these templates with `references/agent-failure-modes.md` for deeper reliability upgrades.

## Integration with /skill-ship

### Phase 2: Creation

When creating skills with agent workflows, use these templates as starting points:

```yaml
# Phase 2 workflow_steps:
- phase_2_creation: |
    Create skill structure with command templates:
    - Use /implement-task for implementation commands
    - Use /review-changes for review commands
    - Use /implement-with-review for combined workflows
    - Resources: references/agent-command-templates.md
```

### Template Selection Guide

| Template | Use Case | Output Format |
|----------|----------|---------------|
| `/implement-task` | Feature implementation, bug fixes | Requirement checklist + change summary + validation |
| `/review-changes` | Code review, change verification | Findings + gaps + approval status |
| `/implement-with-review` | Complete delivery workflow | Combined implement + review |

## Benefits

| Benefit | Impact |
|---------|--------|
| **Consistency** | Standardized command structure across skills |
| **Reliability** | Built-in verification and evidence requirements |
| **Safety** | Hallucination and scope-creep prevention |
| **Efficiency** | Reusable templates reduce prompt engineering |

---

**Source**: `/agent_team` skill (Command Templates)
**Related**: `references/agent-failure-modes.md` (failure modes), `references/anti-false-done-patterns.md` (completion evidence)
