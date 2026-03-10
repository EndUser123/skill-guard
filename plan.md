# Fix Plan: skill-guard Security and Anti-Pattern Issues

## Overview

Fix 5 issues identified by NotebookLM multi-source analysis: incorrect import paths, path traversal vulnerability, brittle sys.path manipulation, disk I/O on import, and contradictory documentation.

**Severity**: 1 Critical (security), 2 High, 1 Medium, 1 Low

## Architecture

**Target Files**:
- `src/skill_guard/breadcrumb/tracker.py` (3 issues)
- `src/skill_guard/skill_execution_state.py` (2 issues)

**Key Changes**:
1. Correct import path to utils submodule
2. Add path traversal validation
3. Remove brittle sys.path lazy loading
4. Remove auto-migration side effect
5. Fix documentation contradiction

## Data Flow

```
Current (Issue #1):
  tracker.py → skill_guard.terminal_detection [FAILS]
  tracker.py → skill_execution_state.detect_terminal_id [FALLBACK]

Fixed (Issue #1):
  tracker.py → skill_guard.utils.terminal_detection [SUCCESS]

Current (Issue #2):
  skill_name → replace("/", "_") → PATH_TO_FILE

Fixed (Issue #2):
  skill_name → validate_no_dots() → replace("/", "_") → PATH_TO_FILE
                ↳ BLOCK if contains "." or ".."

Current (Issue #3):
  _get_skill_execution_registry() → sys.path.insert → import

Fixed (Issue #3):
  _get_skill_execution_registry() → direct import from utils
  OR return empty dict if registry unavailable (acceptable default)

Current (Issue #4):
  import skill_execution_state → migrate_legacy_state() [SIDE EFFECT]

Fixed (Issue #4):
  import skill_execution_state → [no side effects]
  Migration: explicit function call only when needed
```

## Error Handling

**Issue #2 (Path Traversal)**:
- Validation blocks malicious skill names with `.` or `..`
- Raises ValueError with clear message: "Invalid skill name: contains path traversal characters"
- Fails closed (security) rather than sanitizing silently

**Issue #3 (Registry Import)**:
- If PreToolUse_skill_pattern_gate unavailable, return empty dict
- Log warning to stderr (already implemented for empty required_tools)
- System continues with knowledge skill defaults (safe degradation)

**Issue #4 (Migration)**:
- Remove auto-migration on import
- Migration becomes explicit: `migrate_legacy_state()` called by hooks if needed
- No breaking changes: legacy state migration still available, just not automatic

## Test Strategy

**Issue #1 (Import Path)**:
- Test: Import succeeds without fallback
- Verify: No ImportError warnings

**Issue #2 (Path Traversal)**:
- Positive tests: Valid skill names pass (`package`, `/package`)
- Negative tests: Invalid names blocked (`../etc`, `../../pass`, `./hidden`)
- Edge cases: Empty string, whitespace, mixed case

**Issue #3 (sys.path Removal)**:
- Test: Function works without PreToolUse directory
- Verify: Returns empty dict instead of crashing

**Issue #4 (Import Side Effects)**:
- Test: Import module without file I/O
- Verify: No state files created/modified on import
- Regression: Legacy state migration still works when explicitly called

**Issue #5 (Documentation)**:
- Test: Docstring accurately reflects implementation
- Verify: No contradictions between docs and code

## Standards Compliance

**Python 2025+ Standards** (`/code-python`):
- Type hints: Already present
- Error handling: Add ValueError for path validation
- Imports: Use absolute imports from utils submodule
- Documentation: Fix contradictory docstring

**Security**:
- Input validation: Reject `.` and `..` in skill names
- Fail-closed: Block rather than sanitize for security issues
- No silent fallbacks: Use correct import path

## Ramifications

**Breaking Changes**: None
- Issue #1: Fix import path (was broken anyway)
- Issue #2: Block edge case inputs (security fix)
- Issue #3: Remove brittle pattern (improves reliability)
- Issue #4: Remove automatic migration (migration still available)
- Issue #5: Documentation only (clarifies intent)

**Backwards Compatibility**:
- Existing valid skill names: Continue to work
- Legacy state migration: Still available via explicit call
- Registry import: Falls back to empty dict (already happens)

**Performance Impact**:
- Issue #1: Faster (no fallback needed)
- Issue #2: Negligible (string validation)
- Issue #3: Faster (no sys.path manipulation)
- Issue #4: Faster (no I/O on import)

## Pre-Mortem Analysis

**Failure Mode 1**: "Import still fails after fix"
- Root cause: `skill_guard/utils/terminal_detection.py` not in package
- Preventive action: Verify file exists before implementing fix
- Test: Import skill_guard.utils.terminal_detection succeeds

**Failure Mode 2**: "Path validation breaks legitimate skill names"
- Root cause: Skill named like `v2.0` or `package.json` blocked by `.` check
- Preventive action: Review all existing skills for `.` in names
- Test: Check P:/.claude/skills/ for dots in directory names

**Failure Mode 3**: "Registry import breaks hook functionality"
- Root cause: SKILL_EXECUTION_REGISTRY required for enforcement
- Preventive action: Verify hooks work with empty dict fallback
- Test: Run PreToolUse_skill_pattern_gate with empty registry

**Failure Mode 4**: "Legacy state not migrated, breaks old sessions"
- Root cause: Auto-migration removed, old state files not handled
- Preventive action: Document migration requirement for upgrades
- Test: Simulate upgrade from pre-v3.2 state

**Failure Mode 5**: "Documentation contradiction recurs"
- Root cause: MAX_TRAIL_AGE_SECONDS changed but docs not updated
- Preventive action: Add inline comment linking constant to docs
- Test: Review docstring after code changes
