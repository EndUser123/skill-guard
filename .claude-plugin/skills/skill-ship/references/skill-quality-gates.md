---
type: quality
load_when: quality
priority: mandatory
estimated_lines: 250
---

# Skill Quality Gates and Verification Systems

**Last Updated**: 2026-03-09

## Overview

The Claude Code hooks system includes comprehensive **quality gates** that prevent common skill development anti-patterns and ensure skills work as documented.

## Key Quality Systems

### 1. Integration Verifier

**Location**: `P:/.claude/hooks/posttooluse/integration_verifier.py`

**Purpose**: Prevents aspirational documentation by verifying skill integration claims.

**Problem Solved**: Skills document `suggest:` targets that don't exist or don't reciprocate, creating misleading documentation.

**Architecture**:
- **Detection**: Parses SKILL.md frontmatter for `suggest:` field
- **Verification**: Checks that suggested targets exist in skills directory
- **Reciprocity Check**: Verifies bidirectional integration (A suggests B → B should suggest A)
- **Fallback**: Regex extraction if YAML parsing fails

**Configuration**:
- `INTEGRATION_VERIFIER_ENABLED` (default: `true`) - Enable/disable the hook
- `INTEGRATION_VERIFIER_MODE` (default: `warn`) - Warn mode (true) or block mode (false)

**Test Coverage**: 9 unit tests covering skip patterns, detection scenarios, positive/negative cases

**Example Warning**:
```
⚠️ INTEGRATION VERIFIER WARNING

SKILL.md suggests non-existent skill: /nonexistent-skill

Missing integration:
  • /code suggests /async-bugs, but /async-bugs doesn't reciprocate

Fix: Add bidirectional integration or remove suggest: target
```

### 2. Observable Effect Verifier (SEV)

**Location**: `P:/.claude/hooks/posttooluse/observable_effect_verifier.py`

**Purpose**: Verifies expected side effects from code changes actually occur.

**Problem Solved**: Code that declares observable effects (e.g., logging FileHandler) but doesn't verify they work (e.g., log files created).

**Architecture**:
- **Detection**: Pattern matching in code (e.g., `logging.FileHandler`)
- **Verification**: File system checks (e.g., log file exists, writable)
- **Effect Verifiers**: Modular system for different effect types
  - `LoggingEffectVerifier` - Verifies logging configurations produce log files
  - Extensible for other effects (database connections, network sockets, etc.)

**Configuration**:
- `SEV_ENABLED` (default: `true`) - Enable/disable the hook
- Performance baseline: <100ms latency requirement

**Test Coverage**: 16 unit tests covering skip patterns, verification scenarios, positive/negative cases, performance baseline

### 3. Claim Verification Hooks

**Location**: `P:/.claude/hooks/StopHook_unverified_stance.py`

**Purpose**: Detects skeptical language without verification evidence (anti-sycophancy).

**Detection Patterns**:
- **Sycophantic doubt**: "You're right to push back/question/be skeptical"
- **Empty hedge**: "Let me verify", "That sounds high", "I doubt that" (without verification)
- **Sycophancy inversion**: Apology + same dismissive conclusion
- **Unfounded system claims**: "The system doesn't support X" (without evidence)

**Verification Tools** (exemptions from blocking):
- WebSearch, WebFetch, Bash, Read - When these tools are used, stance is considered verified

**Configuration**:
- `UNVERIFIED_STANCE_ENABLED` (default: `true`) - Enable/disable the hook
- `UNVERIFIED_STANCE_MODE` (default: `warn`) - Warn mode (true) or block mode (false)

**Test Coverage**: 9 unit tests covering detection scenarios, integration, output functions

### 4. Dependency Verification Gate

**Location**: `P:/.claude/hooks/PreToolUse_dependency_verification_gate.py`

**Purpose**: Prevents "lazy configuration errors" by requiring verification of external dependencies before installation.

**Problem Solved**: AI assumes package names without verification, causing 20+ minute wastes (e.g., exa MCP server wrong package name).

**Detection Patterns**:
- **npm install**: `npm install @scope/package` or `npm install package-name`
- **pip install**: `pip install package-name`
- **cargo add**: `cargo add crate-name`

**Verification Commands** (allowed without blocking):
- npm: `npm view package`, `npm search package`
- pip: `pip search package`, `pip index versions package`
- cargo: `cargo search package`

**Local Package Exemptions** (allowed without verification):
- `npm install ./path` - Local directory installs
- `npm install file:./package.tgz` - File protocol installs

**Configuration**:
- `DEPENDENCY_VERIFICATION_ENABLED` (default: `true`) - Enable/disable the hook

**Test Coverage**: 15 unit tests covering positive cases, negative cases, edge cases

## Testing Best Practices

### Anti-Mock Stance

**Policy**: Do not use Mock objects in tests, even if it requires more time to create tests.

**Rationale**:
1. **Fragility**: Mock objects encode implementation assumptions that break when code changes
2. **False Confidence**: Passing mock tests don't prove real integration works
3. **Maintenance Burden**: Mocks duplicate knowledge of implementation

**Examples**:

❌ **WRONG (Mock)**:
```python
mock_match = Mock()
mock_match.groups.return_value = ('X', 'Y')
result = extract_correction_description(content, mock_match)
```

✅ **CORRECT (Real regex)**:
```python
pattern = r"Don't use (\w+), use (\w+) instead"
match = re.search(pattern, "Don't use X, use Y instead")
result = extract_correction_description(content, match)
```

### Hook Testing Protocol

**Use pytest, not ad-hoc Bash pipes.** Hook tests live in `P:/.claude/hooks/tests/`.

**Critical**: Blocking = correct behavior for blocking hooks. Exit code 2 from a PreToolUse hook means the hook successfully blocked the action.

**Expected exit codes by hook type**:

| Hook Event | Exit 0 | Exit 2 |
|------------|--------|--------|
| PreToolUse | Allow/pass-through | **Block** (correct behavior) |
| PostToolUse | Always exit 0 | Advisory only — should not exit 2 |
| Stop | Allow stop | **Block** stop (force continuation) |
| UserPromptSubmit | Always exit 0 | N/A |

## Development Patterns

### Single-Source Dataclass Pattern

**Purpose**: Eliminate structural bug classes by co-locating related data in immutable dataclasses.

**When to Use**: When a module has multiple data structures that must stay aligned (e.g., pattern dictionaries and template dictionaries).

**Pattern**:
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ThinkProfile:
    """Single-source definition for a reasoning profile."""
    name: str
    template: str
    strong_patterns: list[str]
    weak_patterns: list[str] | None

# Single source of truth
_THINK_PROFILES: dict[str, ThinkProfile] = {
    "debug_rca": ThinkProfile(
        name="debug_rca",
        template="...",
        strong_patterns=[...],
        weak_patterns=[...],
    ),
}

# Derived dictionaries (for backward compatibility)
_PROFILES: dict[str, str] = {
    name: profile.template for name, profile in _THINK_PROFILES.items()
}
```

**Benefits**:
- **Compiler-enforced completeness**: Can't add a profile without all fields
- **Zero runtime overhead**: No invariant checks needed
- **Self-documenting**: All profile data visible in one place
- **Immutable**: `frozen=True` prevents accidental mutation

### Invariant Validation Pattern

**Purpose**: Enforce cross-structure consistency at import time using `if __debug__` guards.

**When to Use**: When a module has multiple data structures that must stay aligned.

**Pattern**:
```python
# Module-level invariant check (runs on import)
if __debug__:  # Only runs in dev/test, optimized out in production
    missing_templates = set(_COMPILED_STRONG.keys()) - set(_PROFILES.keys())
    missing_patterns = set(_PROFILES.keys()) - set(_COMPILED_STRONG.keys())

    if missing_templates or missing_patterns:
        raise AssertionError(
            f"Profile configuration mismatch in module_name:\n"
            f"  Missing templates: {missing_templates}\n"
            f"  Missing patterns: {missing_patterns}\n"
        )
```

**Benefits**:
- Fails fast during development, not at runtime in production
- Zero production overhead (`if __debug__` optimized out with `python -O`)
- Clear error message points to the problem

## Hook Registration Pattern

**CRITICAL**: All new hooks MUST be registered to execute.

### Router Registration Steps (3-Step Process)

1. **Export `process_prompt()` function**
   ```python
   def process_prompt(data: dict) -> dict:
       # ... hook logic ...
       return {"additionalContext": "injection text"}
   ```

2. **Register in router's `import_hook()` function**
   ```python
   elif name == "your_hook_name":
       import your_hook_file as mod
       return mod
   ```

3. **Add to `HOOK_PRIORITY` and `HOOK_DISPATCH` dictionaries**
   ```python
   # HOOK_PRIORITY - lower = earlier
   "your_hook_name": 4.5,

   # HOOK_DISPATCH - maps name to runner function
   "your_hook_name": run_your_hook_function,
   ```

### Standalone Registration

For SessionStart, standalone PreToolUse/PostToolUse, or hooks that cannot use router:

```json
{
  "hooks": {
    "YourEvent": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "python P:/.claude/hooks/__lib/hook_runner.py P:/.claude/hooks/your_hook.py --timeout 5.0",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

### Verification

Run the hook registration test to verify:
```bash
python P:/.claude/hooks/tests/test_hook_registration.py
```

This test catches "dead hooks" that exist but are not registered anywhere.

## Key Documentation Files

| File | Purpose |
|------|---------|
| `P:/.claude/hooks/PROTOCOL.md` | Complete hook I/O specifications |
| `P:/.claude/hooks/ARCHITECTURE.md` | Constitutional enforcement mapping |
| `P:/.claude/hooks/development_guide.md` | Hook development guidelines |
| `P:/.claude/hooks/docs/skill_enforcement.md` | Skill enforcement system documentation |
| `P:/.claude/hooks/SKILL_AUTHORS_GUIDE.md` | Author's guide for skill execution requirements |

## Environment Variables Reference

| Variable | Default | Purpose |
|----------|---------|---------|
| `INTEGRATION_VERIFIER_ENABLED` | `true` | Enable integration verification |
| `INTEGRATION_VERIFIER_MODE` | `warn` | Warn (true) or block (false) mode |
| `SEV_ENABLED` | `true` | Enable observable effect verification |
| `UNVERIFIED_STANCE_ENABLED` | `true` | Enable unverified stance detection |
| `UNVERIFIED_STANCE_MODE` | `warn` | Warn (true) or block (false) mode |
| `DEPENDENCY_VERIFICATION_ENABLED` | `true` | Enable dependency verification |
| `STRAWBERRY_VALIDATOR_VERBOSE` | `false` | Show validation warnings (verbose mode) |
| `CONSTITUTIONAL_HOOKS_BYPASS` | `false` | Bypass all constitutional hooks |

## Common Patterns

### Skill Development Checklist

When creating or improving skills, verify:

- [ ] **Integration claims verified**: All `suggest:` targets exist and reciprocate
- [ ] **Observable effects tested**: Side effects (logging, file handlers) verified
- [ ] **Dependencies checked**: External packages verified before installation
- [ ] **Tests written**: pytest tests (no mocks, real objects preferred)
- [ ] **Hook registered**: New hooks registered in router or settings.json
- [ ] **Documentation accurate**: SKILL.md reflects actual implementation (not aspirational)

### Quality Gate Integration

Skills should be aware of these quality gates during development:

1. **PreToolUse Gates**: Block actions before they execute
   - Dependency verification before installing packages
   - Intent validation before executing commands
   - Investigation gates before modifying code

2. **PostToolUse Gates**: Analyze output after tool completion
   - Integration verifier checks SKILL.md claims
   - Observable effect verifier checks side effects
   - Cleanup verifier checks for missing cleanup steps

3. **Stop Hooks**: Validate responses before completion
   - Unverified stance detection prevents empty claims
   - Completion claim verification requires evidence
   - Spec compliance detects deviations from requirements

## Monitoring and Debugging

### Health Check
```bash
python P:/.claude/hooks/tests/test_hook_registration.py
```

### View Logs
```bash
# Integration verifier logs
tail -20 P:/.claude/logs/integration_verifier.jsonl

# Observable effect verifier logs
tail -20 P:/.claude/logs/observable_effect_verifier.jsonl

# Unverified stance detection logs
tail -20 P:/.claude/logs/unverified_stance_blocks.log
```

### Enable Debug Logging
```bash
# For verbose validation output
export STRAWBERRY_VALIDATOR_VERBOSE=true

# For detailed dependency verification logs
export DEPENDENCY_VERIFICATION_DEBUG=1
```

## Troubleshooting

### "My skill is blocked for aspirational documentation"
**Check**:
1. Does `suggest:` field reference real skills?
2. Do those skills reciprocate (suggest back)?
3. Are YAML frontmatter fields properly formatted?

**Fix**: Add bidirectional integration or remove suggest: targets

### "Hook exists but doesn't execute"
**Check**:
1. Is hook registered in router or settings.json?
2. Is hook file executable (proper shebang)?
3. Run `test_hook_registration.py` to verify

**Fix**: Register hook following router pattern or add to settings.json

### "Tests fail with mock errors"
**Check**:
1. Are you using Mock objects in tests?
2. Can you test with real objects instead?

**Fix**: Rewrite tests using real objects and pytest fixtures
