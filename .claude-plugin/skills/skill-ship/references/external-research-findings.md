# External Research: Claude Code Hooks & Skill Enforcement

**Research Date**: 2026-03-09
**Query**: Claude Code skill-based hooks and associated best practices
**Sources**: 15+ technical resources, official docs, community tutorials, security research

## Executive Summary

External research confirms and expands upon the internal skill enforcement system. Key findings:

- **Hook system evolved from 7 to 14 events** (February 2026 update)
- **12% of 2,857 agent skills are malicious** - supply chain security critical
- **Exit code 2 = successful block** (not an error) - confirmed pattern
- **Stderr anti-pattern** - hooks writing to stderr trigger false errors
- **Community best practices** align with internal patterns

## Key External Insights

### 1. Hook System Architecture Evolution

**From smartscope.blog (February 2026 Edition)**:

Claude Code hooks expanded significantly:
- **Events**: 7 → 14 (doubled)
- **Handler types**: Command, Prompt, Agent, HTTP, MCP tool hooks
- **Async support**: Added January 2026 for long-running operations
- **Frontmatter hooks**: Define in SKILL.md for skills/agents
- **Interactive CLI**: `/hooks` command for management
- **JSON output**: Structured responses for advanced control

**Comparison with Internal System**:
- ✅ Our 5-phase enforcement (SessionStart → PreToolUse → PostToolUse → Stop) matches official pattern
- ✅ Router pattern used internally aligns with "consolidated hooks" best practice
- ✅ Frontmatter declaration (allowed_first_tools) matches "hook frontmatter" feature
- ⚠️ We have 5 main events vs. 14 official - opportunity to expand?

### 2. Security Best Practices

**From grith.ai security audit**:

> "We Audited 2,857 Agent Skills. 12% Were Malicious."

**Critical Security Patterns**:

1. **Supply Chain Attacks**:
   - Malicious skills distributed via registries
   - Prompt injection vulnerabilities
   - Unauthorized data exfiltration

2. **Protective Measures**:
   - **Skill scanning before installation** (like our dependency verification gate)
   - **Verified skill registries** (like our integration verifier)
   - **Sandboxed execution** (limit file system access)

**Alignment with Internal System**:
- ✅ `PreToolUse_dependency_verification_gate.py` - prevents lazy configuration errors
- ✅ `integration_verifier.py` - prevents aspirational documentation
- ✅ Pattern gate validation - blocks unauthorized command patterns
- ⚠️ Consider adding skill supply chain scanning

### 3. Hook Development Patterns

**From egghead.io tutorial**:

**Bash Command Restriction Pattern**:
```typescript
// Only allow specific script patterns
if (input.tool_name === "Bash") {
  const allowedPattern = /^bun run scripts\/.+/;

  if (!allowedPattern.test(bashInput.command)) {
    process.exit(2); // Block execution
  }
}
```

**Comparison with Our Pattern Gate**:
```python
# P:/.claude/hooks/PreToolUse/PreToolUse_skill_pattern_gate.py
SKILL_EXECUTION_REGISTRY = {
    "rca": {
        "tools": ["Bash", "Task"],
        "pattern": r"src\.rca|SimpleRCAEngine|RCAEngine",
        "hint": "Use /rca via src.rca imports",
    },
}
```

**Key Similarity**: Both use regex patterns to enforce allowed commands

### 4. Testing & Validation Patterns

**From community discussions (Reddit, GitHub issues)**:

**Critical Testing Insight**:
> "Exit code 2 = correct blocking behavior, not an error"

**Expected Exit Codes**:
| Hook Event | Exit 0 | Exit 2 |
|------------|--------|--------|
| PreToolUse | Allow/pass-through | **Block** (correct behavior) |
| PostToolUse | Always exit 0 | Advisory only — should not exit 2 |
| Stop | Allow stop | **Block** stop (force continuation) |

**Internal Test Compliance**:
- ✅ Our tests assert exit code 2 for blocking (correct)
- ✅ Test suite follows pytest pattern (not ad-hoc Bash)
- ✅ Tests verify hooks block as designed

### 5. Common Anti-Patterns

**From DataCamp tutorial and Medium articles**:

**Anti-Patterns to Avoid**:

1. **❌ Writing to stderr**:
   ```python
   # WRONG - triggers false errors
   print("Error occurred", file=sys.stderr)

   # RIGHT - use stdout or logging
   print("Debug info", file=sys.stdout)  # If debug mode
   logger.info("Event occurred")  # For file-based logging
   ```

2. **❌ Blocking without clear messages**:
   ```python
   # WRONG - silent failure
   if not_allowed:
       sys.exit(2)

   # RIGHT - explain why
   if not_allowed:
       print(f"Blocked: {tool_name} not in allowed list")
       sys.exit(2)
   ```

3. **❌ Replacing permission system**:
   - Hooks should add safety rails, not replace user permission model
   - Don't block actions user explicitly allowed

**Internal Compliance Check**:
- ✅ `LOGGING_STANDARD.md` - documents stdout/stderr separation
- ✅ Hooks use `logger.addHandler(logging.NullHandler())`
- ✅ PostToolUse hooks use stdout for warnings, not stderr
- ⚠️ Some hooks may need review for stderr usage

### 6. Advanced Hook Features

**From official documentation (code.claude.com)**:

**Hook Input Schema** (matches our PROTOCOL.md):
```json
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../session.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "tool_name": "Bash",
  "tool_input": {...}
}
```

**Hook Output Schema** (matches our PROTOCOL.md):
- PreToolUse: `{"continue": bool, "reason": "..."}`
- PostToolUse: `{"warning": "..."}` or `{}`
- Stop: `{"allow": bool, "reason": "..."}`

**Verification**: Our PROTOCOL.md is accurate and up-to-date

### 7. Workflow Automation Examples

**From community tutorials**:

**Code Formatting Hook** (DataCamp):
```python
import subprocess
import sys
import json

# Read hook input
data = json.load(sys.stdin)

# Run formatter on Python file writes
if data["tool_name"] == "Write" and data["tool_input"]["file_path"].endswith('.py'):
    file_path = data["tool_input"]["file_path"]
    subprocess.run(['ruff', 'format', file_path])
    print(f"Formatted {file_path}", file=sys.stdout)

# Always exit 0 (informational hook)
sys.exit(0)
```

**Comparison with Internal Hooks**:
- ✅ `PostToolUse_ruff_fix_gate.py` - auto-fixes Python code quality issues
- ✅ Similar pattern: detect file type → run formatter → report result
- ✅ Uses stdout for notifications, stderr only for actual errors

## Gap Analysis: Internal vs. External

### ✅ Strengths (What We Do Well)

1. **Comprehensive Enforcement System**:
   - Skill pattern gate with parallel validation
   - Auto-discovery system (zero maintenance)
   - Integration verifier (prevents aspirational docs)
   - Observable effect verifier (validates side effects)

2. **Quality Gates**:
   - Dependency verification gate (prevents lazy config errors)
   - Claim verification hooks (prevents empty claims)
   - Completion claim verification (requires runtime evidence)
   - Cleanup verifier (ensures proper cleanup steps)

3. **Testing & Documentation**:
   - Comprehensive pytest test suite
   - PROTOCOL.md documentation
   - ARCHITECTURE.md constitutional mapping
   - Development guide for hook authors

### ⚠️ Potential Improvements

1. **Skill Supply Chain Security**:
   - **External finding**: 12% of agent skills are malicious
   - **Recommendation**: Add skill scanning before installation
   - **Reference**: `skill-scanner-guard` pattern (OpenClaw)

2. **Hook Event Coverage**:
   - **External finding**: Claude Code has 14 hook events
   - **Current internal**: 5 main events (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop)
   - **Opportunity**: Explore Prompt hooks, Agent hooks, HTTP hooks, MCP hooks

3. **Async Hook Support**:
   - **External finding**: Async hooks added January 2026
   - **Current internal**: Mostly synchronous
   - **Opportunity**: Add async support for long-running validations

4. **Frontmatter Hook Declaration**:
   - **External finding**: Hooks can be declared in SKILL.md frontmatter
   - **Current internal**: Hooks registered in settings.json or router
   - **Opportunity**: Support frontmatter declaration for skill-specific hooks

### 🔄 Actionable Recommendations

**High Priority**:
1. Add skill supply chain scanning (malware detection)
2. Document stderr anti-pattern in training materials
3. Explore async hooks for long-running operations

**Medium Priority**:
4. Research additional hook events (Prompt, Agent, HTTP, MCP)
5. Evaluate frontmatter hook declaration pattern
6. Share our enforcement patterns as best practices

**Low Priority**:
7. Contribute back to community (blog posts, tutorials)
8. Engage with official documentation updates

## Best Practices Summary

### **For Hook Development**:

1. **Exit Codes Matter**:
   - Exit 0 = allow/pass-through
   - Exit 2 = block (correct behavior for PreToolUse)
   - Exit code 2 ≠ error, it's successful blocking

2. **Stdout vs Stderr**:
   - Use stdout for debug output and notifications
   - Use stderr only for actual errors
   - Use logging module for file-based logging

3. **Clear Communication**:
   - Always explain why actions are blocked
   - Provide actionable hints for resolution
   - Log important events to transcript (stdout)

4. **Testing Protocol**:
   - Use pytest, not ad-hoc Bash pipes
   - Assert exit code 2 for blocking behavior
   - Test hooks in `P:/.claude/hooks/tests/`

### **For Skill-Based Systems**:

1. **Pattern Validation**:
   - Use regex patterns to enforce allowed commands
   - Provide clear hints for resolution
   - Support both execution and knowledge skills

2. **Auto-Discovery**:
   - Automatically discover skills from `.claude/skills/*/SKILL.md`
   - Support frontmatter declaration of requirements
   - Zero maintenance overhead

3. **Quality Gates**:
   - Integration verification (reciprocity checks)
   - Observable effect verification (side effects)
   - Dependency verification (external packages)
   - Claim verification (evidence requirements)

4. **Supply Chain Security**:
   - Scan skills for malicious patterns
   - Use verified skill registries
   - Implement sandboxed execution

## Key External Resources

**Official Documentation**:
- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks)
- [Hooks Complete Guide (Feb 2026)](https://smartscope.blog/en/generative-ai/claude/claude-code-hooks-guide/)

**Community Tutorials**:
- [Claude Code Hooks: A Practical Guide](https://www.datacamp.com/tutorial/claude-code-hooks)
- [Secure Your Claude Skills with Custom PreToolUse Hooks](https://egghead.io/secure-your-claude-skills-with-custom-pre-tool-use-hooks~dhqko)
- [Claude Code Internals: Hooks](https://kotrotsos.medium.com/claude-code-internals-part-14-hooks-5d307392b026)

**Security Research**:
- [We Audited 2,857 Agent Skills. 12% Were Malicious](https://grith.ai/blog/agent-skills-supply-chain)
- [Secure Skill Factory Standard](https://spec-weave.com/docs/skills/verified/secure-skill-factory-standard/)

**Community Discussions**:
- [Post/PreToolUse Hooks Not Executing #6305](https://github.com/anthropics/claude-code/issues/6305)
- [Claude Code Hooks Tutorial Reddit](https://www.reddit.com/r/ClaudeAI/comments/1phausw/claude_code_hooks_tutorial_posttooluse_hook_to/)
- [Trying to get simple hooks working](https://www.reddit.com/r/ClaudeAI/comments/1lsxnsy/trying_to_get_simple_hooks_working/)

## Research Methodology

**Multi-Provider Search**:
- tavily (comprehensive web search)
- exa (high-quality technical content)
- Perplexity AI (attempted - auth error)
- zai (AI synthesis)

**Synthesis Approach**:
1. Cross-reference external findings with internal implementation
2. Identify gaps and improvement opportunities
3. Validate internal patterns against community best practices
4. Extract actionable recommendations

**Quality Assessment**:
- Official documentation (high confidence)
- Security research (high confidence)
- Community tutorials (medium confidence)
- Reddit discussions (low-medium confidence)

---

**Next Steps**: Consider creating improvement tasks based on gap analysis above.
