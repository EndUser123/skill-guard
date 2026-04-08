# Claude Skills Display Output Templates

Copyable templates for consistent, readable Claude Skills output formatting.

---

## Universal Metadata Header

**All skill outputs SHOULD include this metadata block at the top:**

```markdown
---
**Session Context:**
- Skill: [skill-name]
- Model: [model-name if known]
- Timestamp: [ISO date or relative time]
- Related Tasks: [task IDs or references]
- Artifacts Created: [file paths or None]

**Transcript Reference:** [transcript_path if applicable]
---
```

**When to omit metadata:**
- Quick inline responses (< 3 lines)
- User explicitly requests minimal output
- Real-time streaming outputs

---

## Evidence Tier System

**Used in Template 1 and other evidence-based formats:**

| Tier | Quality | Description | Examples |
|------|---------|-------------|----------|
| **Tier 1** | Direct Observation | Saw it happen, read the code, ran the test | "Read line 42 in file.py", "Executed test and got output" |
| **Tier 2** | Strong Inference | High-confidence deduction from evidence | "Function X calls Y (verified in code), so Y must be loaded" |
| **Tier 3** | Correlation | Pattern matching, statistical evidence | "Error appears 90% of the time when flag is set" |
| **Tier 4** | Speculation | Low-confidence guess, needs verification | "Might be a race condition (unconfirmed)" |

**Rule:** Confidence score cannot exceed what your lowest evidence tier supports.
- Tier 1 → Up to 100% confidence
- Tier 2 → Up to 85% confidence
- Tier 3 → Up to 60% confidence
- Tier 4 → Up to 30% confidence

---

## Template 1: Strict Analysis Format (API-like output)

**Use for:** API responses, test results, bug reports, RCA analysis

```markdown
## Analysis: [One-line title]

**Confidence:** [Score]% (Tier [1-4])
**Evidence Tier:** [Highest tier used]

### Root Cause
[ROOT CAUSE: Tier X] [One-line summary]

**Technical:** [What broke - file, line, mechanism]
**Systemic:** [Why it was possible]

### Evidence
| Tier | Evidence | Source |
|------|----------|--------|
| 1 | [Specific finding] | [file:line or URL] |
| 2 | [Specific finding] | [file:line or URL] |
| 3 | [Specific finding] | [file:line or URL] |

### Action Items
1. [ ] [Specific action with owner and deadline]
2. [ ] [Specific action with owner and deadline]
```

---

## Template 2: Executive Summary Format (Flexible guidance)

**Use for:** Analysis reports, research summaries, recommendations

```markdown
# [Report Title]

## Executive Summary
[One-paragraph overview of key findings and recommendations]

## Key Findings
- **Critical:** [N] items - [Brief description]
- **High:** [N] items - [Brief description]
- **Medium:** [N] items - [Brief description]
- **Low:** [N] items - [Brief description]

## Detailed Analysis

### Critical Issues
[Each critical issue with severity, location, description, impact, recommended action]

### High Priority Issues
[Each high priority issue with details]

### Medium Priority Issues
[Each medium priority issue with details]

### Low Priority Issues
[Each low priority issue with details]

## Recommendations
1. **[Priority] Recommendation title**
   - Rationale: [Why this matters]
   - Impact: [Expected outcome]
   - Effort: [Low/Medium/High]

2. **[Priority] Recommendation title**
   - Rationale: [Why this matters]
   - Impact: [Expected outcome]
   - Effort: [Low/Medium/High]

## Completed Actions (If any)
**Only include this section if actions were completed during the session**
- [x] [Completed action 1]
- [x] [Completed action 2]

## Next Steps (Pending)
**Only list actions that need to be done next**
- [ ] [Pending action 1]
- [ ] [Pending action 2]

**Critical:** Do NOT mix completed actions with pending next steps.
```

---

## Template 3: Hypothesis Testing Format

**Use for:** Debugging, RCA, investigation tasks

```markdown
## Hypothesis Testing: [Problem description]

| Rank | Hypothesis | Confidence | Evidence |
|------|------------|------------|----------|
| 1 | [Hypothesis description] | [High/Med/Low] | [Supporting data] |
| 2 | [Hypothesis description] | [High/Med/Low] | [Supporting data] |
| 3 | [Hypothesis description] | [High/Med/Low] | [Supporting data] |

### Selected Hypothesis: [Hypothesis #1]
**Reasoning:** [Why this hypothesis is most likely]

### Verification Plan
1. [Test step 1]
2. [Test step 2]
3. [Test step 3]

### Test Results
**Outcome:** [Confirmed / Rejected / Inconclusive]

**Evidence:**
- [What was observed]
- [Measurements or outputs]
- [File paths or references]

**Conclusion:**
[What this means - confirmed diagnosis or next step]
```

---

## Template 4: Comparison Format

**Use for:** Tool selection, architecture decisions, feature comparisons

```markdown
## Comparison: [What's being compared]

| Feature | Option A | Option B | Option C | Recommendation |
|---------|----------|----------|----------|----------------|
| [Criterion 1] | [Details] | [Details] | [Details] | [Winner] |
| [Criterion 2] | [Details] | [Details] | [Details] | [Winner] |
| [Criterion 3] | [Details] | [Details] | [Details] | [Winner] |

### Summary
**Recommended:** [Option X]

**Key reasons:**
1. [Primary advantage with evidence]
2. [Secondary advantage with evidence]
3. [Tie-breaker consideration]

**Trade-offs:**
- [What you're giving up]
- [Migration cost if applicable]
- [Risk factors]
```

---

## Template 5: Workflow Progress Format

**Use for:** Long-running tasks, multi-step workflows, project tracking

```markdown
## Workflow Progress: [Project/task name]

### Phase 1: [Phase name]
- [x] [Completed task]
- [x] [Completed task]
- [ ] [Incomplete task]
- [ ] [Incomplete task]

### Phase 2: [Phase name]
- [ ] [Task not started]
- [ ] [Task not started]

### Phase 3: [Phase name]
- [ ] [Task not started]

### Current Status
**Phase:** [Current phase]
**Progress:** [X% complete or status description]
**Blockers:** [Any blockers or "None"]
**Next action:** [Specific next step]

**Estimated completion:** [If known]
**Dependencies:** [External dependencies or blockers]
```

---

## Template 6: Error Analysis Format

**Use for:** Bug reports, error investigations, failure analysis

```markdown
## Error Analysis: [Error name or code]

### Summary
**Error:** [Error message]
**Location:** [file:line or component]
**Severity:** [Critical/High/Medium/Low]

### Reproduction Steps
1. [Step 1]
2. [Step 2]
3. [Step 3]
**Result:** [What happens]

### Root Cause
**What caused the error:** [Technical explanation]
**Why it was possible:** [Systemic issue]

### Impact
- **Affected systems:** [What broke]
- **User impact:** [Who/what is affected]
- **Data loss:** [Yes/No with details]
- **Downtime:** [Duration if applicable]

### Resolution
**Fix:** [Description of the fix]
**Verified:** [How verification was done]
**Prevention:** [How to prevent recurrence]

### Related Issues
- [Similar errors or patterns]
- [Upstream/downstream effects]
```

---

## Template 7: Research Findings Format

**Use for:** Research tasks, documentation analysis, information gathering

```markdown
# Research: [Topic]

## Metadata
**Sources consulted:** [N] sources
**Date range:** [If time-bound]
**Scope:** [What was/wasn't covered]

## Sources Consulted
| Source | Type | Relevance | Key Takeaway |
|--------|------|-----------|--------------|
| [Source name] | [Doc/Code/URL] | [High/Med/Low] | [One-line summary] |
| [Source name] | [Doc/Code/URL] | [High/Med/Low] | [One-line summary] |

## Key Insights

### Insight 1: [Title]
**Finding:** [What was discovered]
**Evidence:** [Supporting details with citations]
**Implications:** [What this means for the project]
**Confidence:** [High/Med/Low]

### Insight 2: [Title]
**Finding:** [What was discovered]
**Evidence:** [Supporting details with citations]
**Implications:** [What this means for the project]
**Confidence:** [High/Med/Low]

## Open Questions
1. [Unresolved question]
2. [Unresolved question]

## Recommended Next Steps
1. [ ] [Specific action to answer open question]
2. [ ] [Specific action to validate findings]

**Sources:** [URLs or file paths for reference]
```

---

## Template 8: Code Review Format

**Use for:** Pull requests, diff analysis, code quality checks

```markdown
## Code Review: [PR/commit/diff description]

### Metadata
**Files changed:** [N] files
**Lines added:** [+N]
**Lines removed:** [-N]
**Review scope:** [What was reviewed]

### Critical Issues (Must Fix)
- **[File:line]**: [Issue description]
  - **Why:** [Security / correctness / performance impact]
  - **Suggested fix:** [Specific recommendation]

### High Priority Issues (Should Fix)
- **[File:line]**: [Issue description]
  - **Why:** [Maintainability / clarity impact]
  - **Suggested fix:** [Specific recommendation]

### Medium Priority Issues (Consider Fixing)
- **[File:line]**: [Issue description]
  - **Why:** [Style / optimization opportunity]
  - **Suggested fix:** [Specific recommendation]

### Positive Findings
- [Good patterns, well-written sections, clever solutions]

### Summary
**Overall assessment:** [Approve / Request changes / Reject]
**Risk level:** [High / Medium / Low]
**Blocking issues:** [N] critical issues must be addressed

**Recommendation:** [Merge with changes / Request revisions / Reject]
```

---

## Template 9: Performance Analysis Format

**Use for:** Profiling results, benchmarking, optimization analysis

```markdown
## Performance Analysis: [Component/function/system]

### Methodology
**What was measured:** [Metric description]
**Tools used:** [Profiler, benchmark tool]
**Test conditions:** [Hardware, data size, concurrency]
**Baseline:** [What you're comparing against]

### Results
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| [Metric 1] | [Value] | [Value] | [+/- X%] |
| [Metric 2] | [Value] | [Value] | [+/- X%] |
| [Metric 3] | [Value] | [Value] | [+/- X%] |

### Bottlenecks Identified
1. **[Bottleneck 1]**
   - **Location:** [File:line or function]
   - **Impact:** [X% of total time]
   - **Why:** [Root cause]

2. **[Bottleneck 2]**
   - **Location:** [File:line or function]
   - **Impact:** [X% of total time]
   - **Why:** [Root cause]

### Optimization Recommendations
1. **[Priority]** [Recommendation]
   - **Expected gain:** [Estimated improvement]
   - **Effort:** [Low/Medium/High]
   - **Risk:** [Low/Medium/High]

### Verification
**How to validate:** [Measurement approach]
**Regression risk:** [Potential side effects]
```

---

## Template 10: Security Audit Format

**Use for:** Security analysis, vulnerability assessment, compliance checks

```markdown
## Security Audit: [Component/system/scan]

### Metadata
**Audit date:** [Date]
**Scope:** [What was covered]
**Standards:** [OWASP / CWE / other frameworks]
**Tools used:** [Automated scanners, manual review]

### Critical Vulnerabilities (Fix Immediately)
- **[ID/CVE]**: [Vulnerability name]
  - **Severity:** Critical
  - **Location:** [File:line or component]
  - **Exploit scenario:** [How it can be exploited]
  - **Impact:** [Data loss / system compromise / etc]
  - **Fix:** [Specific remediation]

### High Severity Vulnerabilities
- **[ID/CVE]**: [Vulnerability name]
  - **Severity:** High
  - **Location:** [File:line or component]
  - **Exploit scenario:** [How it can be exploited]
  - **Impact:** [What's at risk]
  - **Fix:** [Specific remediation]

### Medium Severity Vulnerabilities
- **[ID/CVE]**: [Vulnerability name]
  - **Severity:** Medium
  - **Location:** [File:line or component]
  - **Impact:** [Limited risk]
  - **Fix:** [Specific remediation]

### Low Severity / Informational
- [Minor issues, best practice violations, potential improvements]

### Summary
**Total findings:** [N] Critical, [N] High, [N] Medium, [N] Low
**Overall posture:** [Excellent / Good / Fair / Poor]
**Recommended actions:**
1. [Immediate action required]
2. [Short-term priorities]
3. [Long-term improvements]

### Compliance Status
- **[Standard 1]:** [Compliant / Non-compliant with details]
- **[Standard 2]:** [Compliant / Non-compliant with details]
```

---

## Usage Guidelines

### Template Selection Guide

| Situation | Use Template | Why |
|-----------|--------------|-----|
| API responses, test results, RCA | Template 1 | Structured, evidence-based, machine-readable |
| Analysis reports, recommendations | Template 2 | Flexible, narrative, human-readable |
| Debugging, investigation | Template 3 | Hypothesis-driven, scientific method |
| Tool selection, architecture decisions | Template 4 | Comparison matrix, clear recommendations |
| Long-running workflows, projects | Template 5 | Progress tracking, phase-based |
| Bug reports, error investigations | Template 6 | Reproduction steps, impact analysis |
| Research, documentation review | Template 7 | Source tracking, insight extraction |
| Pull requests, code review | Template 8 | Diff-focused, severity-based |
| Performance profiling, benchmarking | Template 9 | Metrics-driven, bottleneck identification |
| Security analysis, compliance | Template 10 | Vulnerability tracking, risk assessment |

### Key Formatting Principles

**Structure:**
- Use **bold** for headers and emphasis
- Use tables for structured comparisons
- Use checklists for progress tracking
- Group related information under clear headers

**Evidence:**
- Include confidence levels when uncertain
- Cite evidence sources (file:line, URLs)
- Use evidence tiers to justify confidence scores
- Distinguish observation from inference

**Clarity:**
- Separate completed actions from pending next steps
- Use severity classifications (Critical/High/Medium/Low)
- Include impact and effort estimates for recommendations
- Provide concrete next steps with actionable items

**Metadata:**
- Always include session context when applicable
- Reference transcripts for reproducibility
- Track artifacts created during analysis
- Note related task IDs for traceability

---

## Template Quality Checklist

When using or modifying templates, ensure:

- [ ] Metadata header included (if applicable)
- [ ] Evidence sources cited
- [ ] Confidence levels justified
- [ ] Completed vs pending actions clearly separated
- [ ] Severity classifications used consistently
- [ ] Action items are specific and actionable
- [ ] Impact and effort estimates included for recommendations
- [ ] File paths and line numbers referenced where applicable
- [ ] Output is scannable (clear headers, structured sections)

---

## Source

Based on official Claude Skills documentation:
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices

And existing skill patterns from:
- `P:/.claude/skills/debugRCA/SKILL.md`
- `P:/.claude/skills/gto/SKILL.md`

**Version:** 2.0
**Last updated:** 2026-03-08
**Changes:** Added metadata header, evidence tier documentation, 3 new templates (code review, performance, security), improved existing templates with missing sections
