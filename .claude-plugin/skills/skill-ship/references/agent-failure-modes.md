---
type: quality
load_when: quality
priority: mandatory
estimated_lines: 150
---

# Agent Failure Modes Reference

> Common coding-agent failure patterns with mitigation strategies
> Source: Extracted from `/agent_team` skill

## Quick Checklist

Use this checklist when upgrading a prompt/skill for coding agents.

- `Spec drift`: require requirement-by-requirement completion evidence.
- `Tool misuse`: require explicit tool result evidence for critical steps.
- `Code hallucination`: require repo/doc verification before new APIs or dependencies.
- `Context drift`: require consistency with existing architecture/style in touched modules.
- `Verification gaps`: require tests/linters for touched scope; block finalization on unresolved failures.
- `Looping/non-convergence`: require retry budget and forced re-plan trigger.

## Common Failure Modes

### Spec drift
- Symptom: task is partially implemented or misread.
- Mitigation: final output must include requirement mapping with evidence.

### Tool misuse
- Symptom: wrong tool/args, ignored exit codes, assumed-success behavior.
- Mitigation: require exit code/result acknowledgment for risky commands and checks.

### Code hallucination
- Symptom: invented APIs, functions, packages, or signatures.
- Mitigation: require repo search and doc evidence before introducing anything new.

### Context drift
- Symptom: architecture/style inconsistency during long sessions or handoffs.
- Mitigation: reviewer confirms consistency with local module patterns.

### Verification gaps
- Symptom: tests/linters not run, or failures ignored.
- Mitigation: no finalization without test/lint outcomes for touched scope.

### Looping/non-convergence
- Symptom: repeated retries without strategy change.
- Mitigation: hard retry cap and re-plan after repeated failures.

## Enforcement Patterns

Use these as reusable clauses in commands/skills/hooks.

- `Completion gate`: "Task is complete only with requirement checklist + test/lint evidence."
- `Reviewer gate`: "Reviewer must report spec alignment, hallucination risk, test status, and scope risk."
- `Stop contract`: "If blocked, output BLOCKED reason, evidence, one decision question, and numbered next actions."
- `Retry policy`: "After N failed attempts, stop retries and propose a revised plan."

## Prompt Blocks

### Implementation Self-Check Block

```text
Before finalizing:
1) Re-read requirements and output a checklist mapping each requirement to evidence.
2) Confirm no invented APIs/dependencies were introduced; cite repo/doc evidence if new ones are required.
3) Run relevant tests/linters for touched scope and report outcomes.
4) If any check fails, do not finalize; re-plan and iterate.
```

### Reviewer/Critic Block

```text
Review the change for common coding-agent errors:
- spec mismatch
- tool/test misuse
- hallucinated APIs/dependencies
- architecture/style drift
- risky unjustified scope expansion
For each category, output either "no issue found" or concrete findings with file references and fixes.
```

## Integration with /skill-ship

### Phase 2: Creation

Add failure-mode awareness to skill creation:

```yaml
# Phase 2 workflow_steps:
- phase_2_creation: |
    Create skill structure WITH failure-mode awareness:
    - Apply Quick Checklist for coding-agent reliability
    - Use Enforcement Patterns as reusable clauses
    - Resources: references/agent-failure-modes.md
```

### Phase 3: Quality & Validation

Add failure-mode checks to Phase 3:

| Test | Status | Evidence | Fix |
|------|--------|----------|-----|
| Spec drift prevention | - | Requirement mapping in output | - |
| Tool misuse prevention | - | Exit code acknowledgment | - |
| Code hallucination prevention | - | Repo/doc evidence cited | - |
| Context drift prevention | - | Architecture/style consistency | - |
| Verification gaps | - | Tests/linters run for touched scope | - |
| Looping/non-convergence | - | Retry cap enforced | - |

## Benefits

| Benefit | Impact |
|---------|--------|
| **Reliability** | Coding agents produce correct, complete results |
| **Verification** | Explicit evidence requirements prevent false completion |
| **Safety** | Hallucination detection prevents invented APIs |
| **Convergence** | Retry caps prevent infinite loops |

---

**Source**: `/agent_team` skill (Failure Modes Reference)
**Related**: `references/anti-false-done-patterns.md` (completion evidence), `references/agent-command-templates.md` (command templates)
