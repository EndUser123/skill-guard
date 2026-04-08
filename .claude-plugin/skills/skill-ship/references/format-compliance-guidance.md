---
type: quality
load_when: quality
priority: recommended
estimated_lines: 150
---

# Format Compliance Guidance

**Problem**: Claude Code frequently ignores documented output formats in SKILL.md files, creating inconsistent outputs and requiring user corrections.

**Root Cause**: This is a known model behavior issue (GitHub Issues #6450, #742) where Claude's ingrained "helpful assistant" patterns override specific format/style instructions.

## Solutions (Priority Order)

### Option A: Architecture Fix (RECOMMENDED FIRST CHOICE)

**Separate process from context using external template files.**

**Implementation**:
1. Create `reference/output-template.md` with exact format structure
2. Keep SKILL.md under 50 lines with minimal process steps
3. Each step references the template: "Generate report using reference/output-template.md"

**Why it works**:
- Reduces instruction budget (SKILL.md stays short)
- Template file is read as content (not instructions)
- Model focuses on following template structure

**Example transformation**:
```yaml
# ❌ WRONG - format buried in skill
## Output Format

Generate a reflection with these sections:
- Session Summary (duration, work, files, decisions)
- User Corrections (context, learning, future)
...

# ✅ RIGHT - external template reference
## Output

Generate reflection using the template in references/session-reflection-template.md
```

**Cost**: Low (create one template file per skill)
**Maintenance**: Low (update template when format changes)
**Reliability**: High (addresses root cause)

---

### Option B: Hook-Based Gate (TECHNICAL ENFORCEMENT)

**Use hooks to literally block non-compliant output.**

**Implementation**:
```bash
# PostToolUse hook: Enforcer
# After skill invocation, validate output format
# If format doesn't match template, inject correction

# PreToolUse hook: Gate
# Block next action if format not followed
```

**Two-file system**:
1. **Enforcer hook** (PostToolUse): Injects mandatory format after output
2. **Gate hook** (PreToolUse): Blocks next action if format invalid

**Why it works**: Can't proceed until format is correct

**Cost**: Medium (requires hook development and testing)
**Maintenance**: Medium (hooks need updates when format changes)
**Reliability**: Very High (enforcement is guaranteed)

**Downside**: Complex, may feel heavy-handed for simple skills

---

### Option C: Both A + B (FOR PERSISTENT ISSUES)

**Apply architecture fix (Option A) + hook gate (Option B) for guaranteed compliance.**

**When to use**:
- Critical workflows where format compliance is mandatory
- Skills with history of format issues despite clear instructions
- Multi-step processes where wrong format breaks subsequent steps

**Implementation**:
1. Apply Option A (template file + minimal SKILL.md)
2. Add validation hook that checks output against template
3. If validation fails, halt with specific error message

**Cost**: Higher (both template and hooks)
**Maintenance**: Higher (two systems to maintain)
**Reliability**: Very High (belt + suspenders approach)

---

## Decision Framework

### Use Option A (Architecture Fix) when:
- ✅ Skill has simple, single-step output
- ✅ Format is straightforward (template < 50 lines)
- ✅ Skill is still in development (format may change)
- ✅ You want minimal maintenance overhead

### Use Option B (Hook Gate) when:
- ✅ Format compliance is business-critical
- ✅ Skill has complex, multi-stage output
- ✅ You have existing hook infrastructure
- ✅ Format is stable and won't change often

### Use Option C (Both) when:
- ✅ Option A alone has been tried and failed
- ✅ Skill is production-critical (can't fail)
- ✅ You have resources for maintenance
- ✅ Zero tolerance for format violations

---

## Implementation Checklist

### For Option A (Architecture Fix):
- [ ] Create `reference/output-template.md` with exact format
- [ ] Reduce SKILL.md to < 50 lines
- [ ] Add step: "Generate using reference/output-template.md"
- [ ] Test: Invoke skill 5 times, verify format matches
- [ ] Adjust: If format still varies, simplify template further

### For Option B (Hook Gate):
- [ ] Create validation script for format checking
- [ ] Add PostToolUse hook to invoke validation
- [ ] Add PreToolUse hook to block on validation failure
- [ ] Test: Trigger format violation, verify block occurs
- [ ] Document: Add hook behavior to skill documentation

### For Option C (Both):
- [ ] Complete Option A checklist
- [ ] Complete Option B checklist
- [ ] Integration test: Verify hook + template work together
- [ ] Load test: Test format compliance under 20+ invocations
- [ ] Monitor: Track format compliance rate over time

---

## Anti-Patterns to Avoid

### ❌ Verbose format instructions in SKILL.md
**Problem**: Long instructions fragment model attention
```yaml
## Output Format (50 lines of detailed instructions...)
```

**Fix**: Move to template, keep one-line reference

### ❌ Examples without explicit structure
**Problem**: Examples don't enforce format
```yaml
Example output:
[Shows one good example but no template]
```

**Fix**: Provide actual template file that must be followed

### ❌ "Stay in character" style instructions
**Problem**: Style instructions conflict with training patterns
```yaml
Output style: Professional, sober, no exclamation marks!
```

**Fix**: Define structure, not style (GitHub #6450 shows style instructions are unreliable)

---

## Success Metrics

**Option A Success**:
- Format matches template in ≥ 90% of invocations
- SKILL.md stays under 50 lines
- No user corrections about format

**Option B Success**:
- All non-compliant output is blocked
- Error messages clearly state what's wrong
- No false positives (valid output blocked)

**Option C Success**:
- 100% format compliance
- Zero user corrections
- Acceptable latency overhead (< 1 second)

---

## References

- GitHub Issue #6450: Output Styles ignored (style instruction reliability)
- GitHub Issue #742: Instructions not followed (sequential pattern issues)
- mindstudio.ai blog: Skills architecture (process vs context separation)
- Reddit 116-config: Hook-based enforcement examples
- Claude API docs: Increase consistency (prefill response technique)
