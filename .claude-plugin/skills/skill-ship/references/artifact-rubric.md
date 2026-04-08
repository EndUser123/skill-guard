---
type: core
load_when: phase_3d
priority: mandatory
estimated_lines: 120
---

# Artifact Quality Rubric

Reference document for Phase 3d artifact quality validation. Loaded only when target skill emits durable artifacts.

## When to Load This Rubric

Activate Phase 3d when target skill has any of:
- `produces_artifact: true` in SKILL.md frontmatter
- Skill writes files to disk (plans, reports, configs)
- Skill output is consumed by another agent or human for implementation

**Does NOT activate for**: utility skills (formatters, calculators, validators) whose output is transient.

---

## The 5 Quality Criteria

### 1. Single-Purpose Artifact

**Rule**: Artifact addresses exactly one goal. Not multiple goals mixed together.

**Pass signals**:
- Title/topic is singular: "Refactor X" not "Refactor X and add Y and fix Z"
- Scope is bounded: clear start and end state
- No "while we're at it" additions

**Fail signals**:
- Artifact has multiple unrelated sections
- "Also note that..." findings appended mid-document
- Scope creep visible in table of contents

**Example — FAIL**:
```
# Plan: Migrate auth AND add logging AND refactor API

## Section 1: Auth migration
## Section 2: Logging (unrelated)
## Section 3: API refactor (separate goal)
```

**Example — PASS**:
```
# Plan: Migrate auth middleware to token-based sessions
[Single scoped goal, bounded scope]
```

---

### 2. No Raw Findings Embedded

**Rule**: Audit logs, adversarial review raw output, or diagnostic findings must be synthesized into the spec — not copy-pasted as-is.

**Pass signals**:
- Findings are paraphrased and integrated into requirements
- Evidence is cited but not embedded as raw blobs
- "As noted in review: X" style citations (not raw logs)

**Fail signals**:
- Full adversarial review output pasted into plan
- Raw grep/output snippets embedded without synthesis
- Finding lists copied verbatim without resolution

**Example — FAIL**:
```
## Review Findings

[Full raw output from adversarial review agent, 40 lines]
```

**Example — PASS**:
```
## Incorporated Findings
- Finding: Session tokens stored in plaintext (INV-001) → Fixed by encrypting at rest
- Finding: No expiration on refresh tokens → Added 24h TTL
```

---

### 3. No Placeholder Residue

**Rule**: No unresolved templates, TODOs, or placeholder markers in final artifact.

**Pass signals**:
- No `{{TODO}}`, `{{FIXME}}`, `[UNRESOLVED]`
- No `{{replace with X}}` or `{{add details}}`
- All bracketed placeholders filled or explicitly deferred

**Fail signals**:
- `{{TODO: add file paths}}`
- `[UNRESOLVED: needs further investigation]`
- `### Step 3: {{fill in}}`

---

### 4. Contradiction-Free Status

**Rule**: No conflicting status indicators in the same artifact.

**Pass signals**:
- Status is internally consistent throughout
- "Status: ACCEPTED" means no blocking P0/P1 issues remain
- Deferrals are explicit with rationale, not implicit

**Fail signals**:
- "Status: ACCEPTED" with P0 blockers listed below
- "Ready to implement" with "Note: X is unresolved"
- "Complete" section followed by "Open questions"

**Example — FAIL**:
```
## Status: ACCEPTED

## Remaining Blockers
- P0: Race condition in step 3 — not yet fixed
```

---

### 5. Decision-Complete Handoff

**Rule**: All P0/P1 findings are either incorporated or explicitly deferred with rationale. No unresolved high-severity issues.

**Pass signals**:
- Every P0/P1 has a resolution or documented deferral
- Deferrals include: what, why, who owns resolution, when
- Implementation can proceed without clarification calls

**Fail signals**:
- P0 findings listed but not addressed
- "Will be handled in follow-up PR" with no owner
- "TBD" on critical path items

---

## Rubric Application

| Criterion | Severity if Failed | Blocking? |
|-----------|------------------|-----------|
| Single-purpose | P1 | Yes |
| No raw findings | P2 | No |
| No placeholder residue | P1 | Yes |
| Contradiction-free | P0 | Yes |
| Decision-complete | P0 | Yes |

**Gate**: Artifact must pass all P0 and P1 criteria to proceed. P2 failures are noted but do not block.

---

## Ready vs. Not-Ready Examples

### Not-Ready Artifact

```markdown
# Plan: Add caching layer AND logging to API service

## Status: READY

## Findings
[Full 80-line adversarial review output pasted here]

## Open Questions
- {{TODO: resolve auth token format}}

## P0 Blockers
- Race condition in cache invalidation (not fixed)
```

### Ready Artifact

```markdown
# Plan: Add Redis caching layer to GET /api/users endpoint

## Status: READY

## Incorporated Findings
- Finding: Cache stampede risk → Added mutex on cache miss
- Finding: No TTL → Set 5-minute expiration

## Deferred (with rationale)
- Monitoring dashboard (P2) → Follow-up in separate sprint

## Verification
Test: Run load test, verify p99 < 50ms
```
