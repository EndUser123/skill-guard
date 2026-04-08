# PROCEDURE-Type Skills: Embedded Workflow Enforcement

## Purpose

Document the correct architecture for PROCEDURE-type skills, emphasizing that workflow enforcement should be embedded directly in skill steps, NOT implemented as global hooks in settings.json.

## Problem: Global Hooks Architecture Mistake

### What Happened

When implementing phase enforcement for /p (Code Maturation Pipeline), I made a critical architectural mistake:

1. **Created hook scripts** in `.claude/hooks/p/`:
   - `phase_gate.py` - PreToolUse hook to block phase dispatch
   - `validate_phase_exit.py` - PostToolUse hook to validate exit criteria
   - `verify_final_state.py` - Stop hook to verify completion

2. **Registered hooks globally** in `settings.json`:
   ```json
   {
     "hooks": {
       "PreToolUse": [{
         "matcher": "tool == 'Task'",
         "hooks": [{
           "type": "command",
           "command": "uv run P:/.claude/hooks/p/phase_gate.py",
           "timeout": 5
         }]
       }]
     }
   }
   ```

3. **Added hooks section** to /p's SKILL.md frontmatter pointing to these scripts

### Why This Was Wrong

**User Feedback**: "you are putting the hooks in the wrong location. they are supposed to be skill based, not .claude/hooks based."

**Root Cause**: Misunderstanding the difference between:
- **Global hooks** (in `.claude/hooks/` + `settings.json`) - Run for ALL operations across entire Claude Code
- **Skill-based hooks** (in SKILL.md frontmatter) - Run only when that skill is invoked
- **PROCEDURE-type skills** (like /p) - Skills where Claude reads SKILL.md and executes workflow manually

**Impact**:
- Global hooks would run for EVERY Task tool use, not just /p operations
- Defeats the purpose of skill-specific enforcement
- Violates the architectural principle that PROCEDURE-type skills should manage their own workflow

## Solution: Embedded Workflow Enforcement

### Correct Architecture for /p

For PROCEDURE-type skills where Claude reads SKILL.md and executes manually:

1. **Remove external hook scripts** - Delete `.claude/hooks/p/` directory entirely
2. **Remove global registrations** - Remove all PreToolUse/PostToolUse/Stop entries from `settings.json`
3. **Embed enforcement in workflow** - Integrate phase validation directly into skill steps

### Implementation in /p SKILL.md

**Frontmatter** (no hooks section):
```yaml
---
name: p
version: 2.0.0
description: "Code Maturation Pipeline - auto-detects state and runs appropriate quality gates with embedded phase enforcement"
# NO hooks section - enforcement is embedded in workflow steps
---
```

**Step 4.5: Validate Exit Criteria** (embedded in workflow):
```python
def validate_p1_exit_criteria(target: str, flags: list[str]) -> tuple[bool, list[str]]:
    """Validate P1 exit criteria by running actual verification commands."""
    violations = []

    # Check 1: All existing tests pass (CRITICAL - always blocking)
    try:
        result = subprocess.run(
            ["pytest", target, "--tb=no", "-q"],
            capture_output=True,
            text=True,
            timeout=300
        )

        # Parse pytest output for failures
        failed_match = re.search(r'(\d+)\s+failed', result.stdout)
        if failed_match:
            failed_count = int(failed_match.group(1))
            violations.append(f"Exit criteria violated: {failed_count} tests failing")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass  # pytest not available - not blocking for P1

    return (len(violations) == 0, violations)
```

**Phase marker creation** (when validation passes):
```python
# Validation passed - create phase marker for next phase prerequisite
from pathlib import Path
from datetime import datetime

state_dir = Path(".claude/state")
state_dir.mkdir(parents=True, exist_ok=True)

marker_file = state_dir / f"p{phase}-complete.marker"
timestamp = datetime.now().isoformat()
marker_file.write_text(f"Phase {phase} completed at {timestamp}\n")
```

**Step 5: Check HALT Conditions** (embedded in workflow):
```python
# If HALT condition met:
if not passed:
    print("## Pipeline Status: HALTED")
    print(f"**Status:** 🛑 HALTED at Phase {phase}")
    print(f"**Reason:** Exit criteria validation failed")
    print(f"**Violations:**")
    for violation in violations:
        print(f"  - {violation}")
    # HALT - do not proceed to next phase
    return
```

## Key Principles

### 1. Skill Type Determines Architecture

| Skill Type | Execution Model | Hook Strategy |
|------------|-----------------|---------------|
| **PROCEDURE** (like /p) | Claude reads SKILL.md, executes manually | **Embedded validation** in workflow steps |
| **COMMAND** (CLI tools) | Delegates to external binary/script | **Skill-based hooks** in SKILL.md frontmatter |
| **AGENT** (subagents) | Dispatches Task subagents | **Stop hooks** to verify completion |

### 2. Global Hooks Are For Cross-Cutting Concerns

Global hooks in `.claude/hooks/` + `settings.json` should ONLY be used for:
- Constitutional enforcement (TDD mandates, investigation gates)
- Safety constraints (path protection, credential filtering)
- System-wide monitoring (performance tracking, observability)

NOT for skill-specific workflow logic.

### 3. Phase Markers Enable Progression

For multi-phase workflows like /p:
- **Phase markers** (`.claude/state/pN-complete.marker`) track completion
- **Prerequisite checking** (does previous phase marker exist?) prevents skipping phases
- **Exit criteria validation** (actual commands, not self-reporting) ensures quality

## Cross-Platform Bugs Fixed

### Bug 1: Unix `date` Command Doesn't Exist on Windows

**Wrong** (Unix-only):
```python
timestamp = subprocess.run(['date', '-Iseconds'], capture_output=True, text=True).stdout.strip()
```

**Correct** (cross-platform):
```python
from datetime import datetime
timestamp = datetime.now().isoformat()
```

### Bug 2: Relative Path Resolution Issues

**Wrong** (depends on current working directory):
```python
state_dir = Path(".claude/state")
```

**Correct** (resolves relative to hook file):
```python
hook_file = Path(__file__).resolve()
state_dir = hook_file.parent.parent.parent / "state"
```

## Detection: How to Recognize This Mistake

### Signs You're Making This Mistake

1. **Creating hook scripts** in `.claude/hooks/{skill_name}/`
2. **Registering global hooks** in `settings.json` with skill-specific matchers
3. **Adding hooks section** to SKILL.md that points to external scripts
4. **Hook scripts run for ALL operations**, not just when skill is invoked

### Correct Approach for PROCEDURE-Type Skills

1. **Embed validation logic** directly in skill workflow steps
2. **Run verification commands** inline as part of workflow execution
3. **Create state files** (markers) to track progress between phases
4. **HALT on violations** by stopping workflow execution (return/exit)

## Related Documentation

- **`skill-based-hooks.md`** - Complete guide to skill-based hooks system
- **`skill-quality-gates.md`** - Quality verification systems for skill development
- **`skill-based-self-verification.md`** - disler's self-verification patterns for agents

## Learning Date

2026-03-09

## Context

/p phase enforcement implementation - initially implemented as global hooks (WRONG), corrected to embedded workflow validation (CORRECT).
