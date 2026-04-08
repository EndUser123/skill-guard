# Skill-Complete Workflow Examples

This directory contains worked examples demonstrating the full skill-ship lifecycle from discovery through distribution.

## Example Workflows

### 1. New Skill Creation: "git-conventional-commits"

**Scenario**: User wants to create a skill that enforces conventional commit message format

**Phase 1: Discovery & Intent**
```
User Request: "I want to create a skill for git conventional commits"

Intent Extraction:
- What should this skill enable Claude to do?
  → Automatically format commit messages according to conventional commits spec
  → Validate commit messages before they're created
  → Guide users to write better commit messages

- Triggering phrases?
  → "commit these changes", "create a commit", "git commit"

- Output format?
  → Formatted commit message, validation feedback

- Objective verification needed?
  → Yes - commit messages must follow spec (conventionalcommits.org)

AUTOMATED CONFLICT DETECTION:
Invoke /similarity with skill description
→ Found: /git-conventional-commits (87% similarity)
→ Overlapping features: Commit format enforcement, validation

Decision: Enhance existing /git-conventional-commits skill instead of creating new
```

**Phase 2: Creation & Structuring**
```
Skill Coordination:
- Invoke /skill-creator for draft SKILL.md
- Apply /skill-development progressive disclosure patterns
- Use Template 1 (Strict Analysis Format) for validation output

Result: Enhanced SKILL.md with:
- Improved description for better triggering
- Progressive disclosure: main logic in SKILL.md, validation rules in references/
- Test prompts added to evals/evals.json
```

**Phase 3: Quality & Validation**
```
Invoke /testing-skills for validation:

Test Results:
| Test | Status | Evidence | Fix |
|------|--------|----------|-----|
| YAML completeness | ✓ | All required fields present | None |
| Trigger accuracy | ✓ | "git commit" triggers skill | None |
| Output consistency | ✗ | Inconsistent format for merge commits | Add merge commit template |
| Execution flow | ✓ | All paths complete | None |
| Test coverage | ✓ | 3 test prompts in evals/ | None |

Selected Issues:
**Priority:** Medium
**Issue:** Merge commits don't follow conventional commits format
**Fix:** Add merge commit detection and formatting template to references/

Validation Plan:
1. Add merge commit template to references/commit-templates.md
2. Update SKILL.md with merge commit workflow
3. Re-run /testing-skills for validation
```

**Phase 3.5: Evaluation & Iteration**
```
Invoke /skill-creator eval suite:

Test Prompts (evals/evals.json):
1. "Fix the authentication bug" → Expected: "fix(auth): resolve JWT validation"
2. "Add user profile feature" → Expected: "feat(user): add profile page"
3. "Update documentation" → Expected: "docs(readme): update installation guide"

Performance Metrics:
| Metric | Score | Target | Status |
|--------|-------|--------|--------|
| Trigger accuracy | 85% | ≥80% | ✓ |
| Output consistency | 92% | ≥90% | ✓ |
| Execution success | 98% | ≥95% | ✓ |
| Variance analysis | Low variance | Low variance | ✓ |

Iteration Plan:
1. Trigger accuracy 85% meets threshold - no description optimization needed
2. Output consistency 92% exceeds target - proceed to optimization
```

**Phase 4: Optimization & Enhancement**
```
Skill Coordination:
- /av2: Analyze for mechanical continuation (not multi-phase workflow - skip)
- /output-style-extractor: Verify Template 1 compliance ✓

Optimization Analysis:
**Skill:** git-conventional-commits
**Location:** P:\.claude\skills\git-conventional-commits\SKILL.md:45
**Optimization Type:** Format

Issues Identified:
| Issue | Impact | Fix |
|-------|--------|-----|
| Merge commit format missing | Medium | Added merge commit template |
| Type descriptions unclear | Low | Clarified in references/commit-types.md |

Resolution:
**Continuation Enforcement:** Skipped (single-phase workflow)
**Format Standardization:** Template 1 applied consistently
**Performance:** No optimizations needed
```

**Phase 5: Distribution & Documentation**
```
Skill Coordination:
- Invoke /sharing-skills for GitHub PR workflow

Distribution Progress:
### Phase 1: Preparation
- [x] Skill validated
- [x] Output format documented (Template 1)
- [x] PR description written

### Phase 2: Git Workflow
- [x] Fork repository (user's fork)
- [x] Create feature branch (enhance/conventional-commits)
- [x] Commit changes (conventional commits!)
- [x] Push to remote

### Phase 3: PR Creation
- [x] Open pull request
- [x] Add reviewers (skill-creator maintainer)
- [x] Link to original issue

### Current Status
**Phase:** Complete
**Blockers:** None
**Next action:** Await review and merge
```

---

### 2. Skill Improvement: "/debug" Enhancement

**Scenario**: User wants to improve the existing /debug skill with structured debugging workflow

**Phase 1: Discovery & Intent**
```
User Request: "Improve the /debug skill with better debugging workflow"

Intent Extraction:
- What should be improved?
  → Add systematic debugging methodology
  → Integrate with debugRCA for root cause analysis
  → Add hypothesis testing framework

- Existing skill analysis?
  → /debug exists but lacks structured workflow
  → No progressive disclosure
  → No integration with /rca

AUTOMATED CONFLICT DETECTION:
Invoke /similarity with improvement intent
→ Found: /debug (100% - exact match)
→ Found: /rca (65% similarity - related but distinct)
→ No conflicts - enhancement request for existing skill

Decision: Proceed with /debug enhancement
```

**Phase 2: Creation & Structuring**
```
Skill Coordination:
- Read existing /debug SKILL.md
- Apply /skill-development structure patterns
- Integrate /rca workflow points
- Add progressive disclosure for advanced techniques

Changes:
1. Added workflow_steps to frontmatter for skill-first enforcement
2. Created references/debugging-methodology.md with systematic approach
3. Integrated /rca as "Phase 4: Root Cause Analysis"
4. Added hypothesis testing template (Template 3)
```

**Phase 3: Quality & Validation**
```
Invoke /testing-skills for validation:

Test Results:
| Test | Status | Evidence | Fix |
|------|--------|----------|-----|
| YAML completeness | ✓ | workflow_steps added | None |
| Trigger accuracy | ✓ | "debug this" triggers | None |
| Output consistency | ✓ | Template 3 applied | None |
| Execution flow | ✗ | Missing transition to /rca | Add explicit handoff |
| Absence claim verification | ✓ | Verified no existing /rca integration | None |
| Test coverage | ✗ | No evals/ for complex workflow | Add test cases |

Selected Issues:
**Priority:** High
**Issue:** Missing explicit /rca handoff may confuse users
**Fix:** Add "When to escalate to /rca" section to SKILL.md

Validation Plan:
1. Add escalation criteria to Phase 4
2. Create evals/evals.json with debugging scenarios
3. Re-run /testing-skills for validation
```

**Phase 3.5: Evaluation & Iteration**
```
Invoke /skill-creator eval suite:

Test Prompts (evals/evals.json):
1. "My API is returning 500 errors" → Expected: Systematic debugging flow
2. "This test is flaky" → Expected: Hypothesis testing framework
3. "I don't know why it's failing" → Expected: Suggest /rca escalation

Performance Metrics:
| Metric | Score | Target | Status |
|--------|-------|--------|--------|
| Trigger accuracy | 78% | ≥80% | ✗ |
| Output consistency | 88% | ≥90% | ✗ |
| Execution success | 92% | ≥95% | ✗ |
| Variance analysis | Medium variance | Low variance | ✗ |

Iteration Plan:
1. Trigger accuracy < 80% → Optimize description
2. Output inconsistency → Standardize Template 3 usage
3. Execution failures → Fix /rca handoff logic
4. High variance → Add more specific debugging paths
5. Re-run eval suite after fixes
```

**Phase 4: Optimization & Enhancement**
```
Skill Coordination:
- /av2: Add StopHook for multi-phase workflow enforcement
- /output-style-extractor: Enforce Template 3 consistency

Optimization Analysis:
**Skill:** debug
**Location:** P:\.claude\skills\debug\SKILL.md:1
**Optimization Type:** Continuation + Format

Issues Identified:
| Issue | Impact | Fix |
|-------|--------|-----|
| No phase enforcement | High | Add StopHook with breadcrumb check |
| Inconsistent hypothesis format | Medium | Enforce Template 3 structure |
| Missing /rca handoff | High | Add explicit escalation criteria |

Resolution:
**Continuation Enforcement:** StopHook added - validates phase completion before proceeding
**Format Standardization:** Template 3 enforced for all hypothesis outputs
**Performance:** Added caching for common debugging patterns

Hook Implementation (.claude/hooks/debug/stop_hook.py):
```python
#!/usr/bin/env python3
import sys
from pathlib import Path

def main():
    breadcrumb_file = Path.home() / ".claude" / "state" / "debug-phase.marker"

    if not breadcrumb_file.exists():
        print("ERROR: Debug workflow incomplete - missing phase marker", file=sys.stderr)
        print("Please complete all debugging phases before stopping", file=sys.stderr)
        sys.exit(2)  # Block execution

    # Clean up phase marker on successful completion
    breadcrumb_file.unlink(missing_ok=True)
    sys.exit(0)  # Allow execution

if __name__ == "__main__":
    main()
```
```

**Phase 5: Distribution & Documentation**
```
Skill Coordination:
- Local skill - skip /sharing-skills
- Document changes in CHANGELOG.md

Distribution Progress:
### Phase 1: Preparation
- [x] Skill validated
- [x] Output format documented (Template 3)
- [x] Hook added (StopHook for phase enforcement)

### Phase 2: Local Deployment
- [x] Update existing /debug skill
- [x] Test StopHook registration
- [x] Verify workflow enforcement

### Current Status
**Phase:** Deployed locally
**Blockers:** None
**Next action:** Monitor usage and collect feedback
```

---

### 3. Complex Skill: "/cwo" Orchestrator

**Scenario**: User wants to verify the 16-step CWO orchestrator skill for quality and compliance

**Phase 1: Discovery & Intent**
```
User Request: "Audit the /cwo skill for quality"

Intent Extraction:
- What should be verified?
  → SKILL.md frontmatter completeness
  → workflow_steps enforcement capability
  → Integration with orchestrated skills
  → Progressive disclosure compliance

- Skill type?
  → PROCEDURE-type skill (16-step workflow)
  → Requires embedded enforcement, not global hooks

AUTOMATED CONFLICT DETECTION:
Invoke /similarity with "/cwo orchestrator"
→ Found: /cwo (100% - exact match)
→ Found: /orchestrator (72% similarity - general orchestrator)
→ No conflicts - audit request for existing skill

Decision: Proceed with /cwo quality audit
```

**Phase 2: Creation & Structuring**
```
Audit Analysis:
✓ workflow_steps present in frontmatter
✓ Progressive disclosure applied (main workflow in SKILL.md, detailed guides in references/)
✓ 16 orchestrated skills all exist and reciprocate in suggest:
  - /cks (knowledge system)
  - /nse (next step engine)
  - /discover (codebase exploration)
  - /analyze (unified analysis)
  - /arch (architecture guidance)
  - /p (code maturation pipeline)
  - /verify (verification orchestrator)
  - ... (9 more)

Finding: Well-structured, follows all best practices
```

**Phase 3: Quality & Validation**
```
Invoke /testing-skills for validation:

Test Results:
| Test | Status | Evidence | Fix |
|------|--------|----------|-----|
| YAML completeness | ✓ | All required fields + workflow_steps | None |
| Trigger accuracy | ✓ | "orchestrate this workflow" triggers | None |
| Output consistency | ✓ | Template 5 (Workflow Progress) used | None |
| Execution flow | ✓ | All 16 steps complete successfully | None |
| Absence claim verification | ✓ | Verified no global hooks used | None |
| Test coverage | ✓ | Comprehensive integration tests | None |
| Integration verification | ✓ | All 16 orchestrated skills exist | None |

Validation Result: **PASSED** - No issues found
```

**Phase 3.5: Evaluation & Iteration**
```
Skip evaluation for orchestrator skill:
- Complex workflow with subjective outputs
- User explicitly declined ("just audit for quality")
- No objective verification needed for coordination patterns
```

**Phase 4: Optimization & Enhancement**
```
Skill Coordination:
- /av2: Verify embedded enforcement (PROCEDURE-type)
- /output-style-extractor: Verify Template 5 compliance

Optimization Analysis:
**Skill:** cwo
**Location:** P:\.claude\skills\cwo\SKILL.md:1
**Optimization Type:** Architecture verification

Issues Identified:
| Issue | Impact | Fix |
|-------|--------|-----|
| None | N/A | N/A |

Resolution:
**Continuation Enforcement:** Embedded enforcement verified (phase markers, not hooks)
**Format Standardization:** Template 5 applied consistently
**Performance:** No optimizations needed

Architecture Compliance:
✓ PROCEDURE-type skill uses embedded validation (Step 4.5, Step 5)
✓ Phase markers track completion (.claude/state/pN-complete.marker)
✓ No global hooks in .claude/hooks/ (follows procedure-type-skills-embedded-enforcement.md)
```

**Phase 5: Distribution & Documentation**
```
Skill Coordination:
- Production-ready skill - skip distribution
- Document audit results

Audit Summary:
**Skill:** CWO (Concurrent Workflow Orchestrator)
**Status:** PRODUCTION READY
**Quality Score:** 100% (all tests passed)
**Architecture:** Compliant with PROCEDURE-type best practices
**Recommendation:** No changes needed

### Current Status
**Phase:** Audit complete
**Blockers:** None
**Next action:** Continue using /cwo for complex workflows
```

---

## Template Reference

These examples demonstrate the seven output format templates:

### Template 1: Strict Analysis Format
**Use:** API responses, test results, bug reports, RCA
**Example:** git-conventional-commits validation output

### Template 2: Executive Summary Format
**Use:** Analysis reports, research, recommendations
**Example:** Discovery Summary from Phase 1

### Template 3: Hypothesis Testing Format
**Use:** Debugging, RCA, investigation
**Example:** /debug skill hypothesis testing

### Template 4: Comparison Format
**Use:** Tool selection, architecture decisions
**Example:** Similarity Analysis conflict table

### Template 5: Workflow Progress Format
**Use:** Long-running tasks, multi-step workflows
**Example:** /cwo 16-step orchestration, Distribution Progress

### Template 6: Error Analysis Format
**Use:** Bug reports, error investigations
**Example:** Optimization Analysis issues table

### Template 7: Research Findings Format
**Use:** Research tasks, documentation analysis
**Example:** External research synthesis for skill improvement

---

## Key Takeaways

1. **Automated conflict detection** prevents redundant skill creation (Example 1)
2. **Progressive disclosure** keeps SKILL.md lean while maintaining depth (Example 2)
3. **PROCEDURE vs COMMAND architecture** matters for enforcement strategy (Example 3)
4. **Template consistency** improves readability and usability (all examples)
5. **Integration verification** ensures orchestrated skills exist and reciprocate (Example 3)
6. **Quality validation** catches issues before distribution (all examples)
7. **Iterative evaluation** improves triggering accuracy and output consistency (Example 2)

---

## Quick Reference

### When to Skip Phases

**Skip Phase 3.5 (Evaluation) when:**
- Simple skills with objectively verifiable outputs
- User explicitly declines evaluation
- Skills with subjective outputs (writing style, art)

**Skip Phase 5 (Distribution) when:**
- Local skill improvements
- Plugin skills (use plugin distribution workflow)
- Skills not intended for sharing

### Common Patterns

**New skill with high similarity (>80%):**
→ Enhance existing skill instead

**Existing skill improvement:**
→ Add progressive disclosure if >300 lines
→ Consider /av2 for multi-phase workflows
→ Integrate evals/ for complex skills

**PROCEDURE-type skills:**
→ Use embedded enforcement, not global hooks
→ Phase markers for workflow tracking
→ References/ for detailed guides

**COMMAND-type skills:**
→ skill-based hooks for enforcement
→ workflow_steps in frontmatter
→ Stop hooks for multi-phase workflows
