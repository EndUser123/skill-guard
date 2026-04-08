# StopHook Generation Toolkit

> Mechanical continuation enforcement for multi-phase skills
> Reference documentation extracted from `/av2` (v4.1.0)

## Purpose

Transforms skills into mechanically-enforced execution pipelines where the LLM **cannot stop** except at explicit halt gates.

This prevents LLMs from exercising unauthorized discretion in multi-stage workflows:
- Stopping after completing a stage ("task complete")
- Describing work instead of doing it
- Skipping stages based on perceived efficiency

## How It Works

```
Claude tries to stop
        ↓
StopHook fires (registered in settings.json)
        ↓
Reads state file → workflow incomplete?
        ↓
YES: exit(2) + stderr message → Claude MUST continue
NO:  exit(0) → Claude stops normally
```

## Architecture

```
P:/.claude/settings.json
    └── hooks.Stop[] → "python P:/.claude/skills/{skill}/hooks/StopHook_{skill}_continuation.py"

P:/.claude/hooks/state/
    ├── {skill}_workflow.json        # Primary format
    └── {skill}-stage-progress.json  # Legacy fallback format

P:/.claude/skills/{skill}/hooks/
    ├── StopHook_{skill}_continuation.py     # Blocks premature stops
    └── PostToolUse_{skill}_state_tracker.py # Updates state on tool use
```

### State File Format

**Primary format** (`{skill}_workflow.json`):
```json
{
  "current_stage": 3,
  "max_stage": 7,
  "complete": false,
  "halted": false,
  "halt_reason": null
}
```

**Legacy format** (fallback, `{skill}-stage-progress.json`):
```json
{
  "last_completed_stage": 3,
  "timestamp": 1769667278.53
}
```

The StopHook includes a **bridge adapter** that reads the primary format first, falls back to legacy.

### Halt Gates

Workflow can be explicitly halted (allowing stop) when:
- CRITICAL security findings detected
- CRITICAL performance issues found
- User-defined halt conditions met

Set `halted: true` in state to allow stopping mid-workflow.

## Session Isolation (v4.3)

Continuation enforcement is **session-scoped** to prevent cross-session bleed.

**Problem solved:**
```
Session A: Run /v → incomplete at Stage 3 → close session
Session B: Unrelated question → try to stop → OLD state blocks → Claude invokes /v
```

**Solution:**
```
PostToolUse (Skill) → Creates session marker when skill invoked
StopHook           → Only enforces if session marker exists
SessionEnd         → Deletes session marker
```

**Behavior:**
| Session Marker | Workflow State | Result |
|----------------|----------------|--------|
| ❌ Missing | Any | ALLOW stop |
| ✅ Exists | Complete | ALLOW stop |
| ✅ Exists | Incomplete | BLOCK stop |

## Usage

The StopHook generation toolkit is located at `P:/.claude/skills/av2/`:

```bash
# Full optimization pipeline
python P:/.claude/skills/av2/scripts/optimize.py <skill>

# Check compliance only
python P:/.claude/skills/av2/scripts/constitutional_check.py <skill>

# Generate hooks directly
python P:/.claude/skills/av2/scripts/generate_stop_hook.py <skill>

# Test hook behavior
python P:/.claude/skills/av2/test_stophook_e2e.py
```

## Hook Registration

Generated hooks must be registered in `P:/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": ".*",
        "hooks": [{
          "type": "command",
          "command": "python P:/.claude/skills/{skill}/hooks/StopHook_{skill}_continuation.py",
          "timeout": 3,
          "layer": "-3_{skill}_continuation",
          "critical": true
        }]
      }
    ]
  }
}
```

Layer `-3` ensures it fires before other Stop hooks.

## Expected Output

When workflow is incomplete and LLM tries to stop:
```
Exit code: 2
Stderr: 🔴 BLOCKED: /skill workflow incomplete.
        Current: Stage 3
        MANDATORY: Execute Stage 4 (TDD) NOW.
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Hook allows stop when incomplete | `halted: true` in state | Set `halted: false` |
| Hook not firing | Not registered in settings.json | Add to hooks.Stop[] |
| Wrong stage shown | State file stale | Delete workflow JSON, use legacy |
| Exit 0 unexpectedly | State file missing | Initialize state file |

## Constitutional Requirements

For multi-phase skills using StopHook enforcement:

| # | Requirement | Implementation |
|---|-------------|----------------|
| 1 | Continuation Enforcement | StopHook + exit(2) |
| 2 | Gate Enforcement | Block unauthorized paths |
| 3 | Explicit Halt Gates | Defined stop conditions |
| 4 | Execution Directive | "EXECUTE, don't describe" |
| 5 | Complete Stage Sequence | Clear start→finish path |
| 6 | Intermediate Step Enforcement | Multi-step stages need mandatory markers |

### Invariant #6: Intermediate Step Enforcement

For stages with sub-steps (Layer 1, Layer 2, etc.), check enforcement in priority order:

| Priority | Mechanism | Robustness | Detection |
|----------|-----------|------------|-----------|
| 1 | **Mechanical** | Cannot bypass | State tracker + StopHook layer gating |
| 2 | **Behavioral** | Can be ignored | Text markers + anti-shortcut warnings |

**Mechanical enforcement** (recommended):
- State tracker tracks `stage_3_layers.layer_N_complete`
- StopHook blocks if `all_layers_complete()` is false
- Cannot be bypassed by attention decay

---

**Extracted from**: `/av2` skill (v4.1.0)
**Scripts location**: `P:/.claude/skills/av2/scripts/`
**Status**: Operational - continuation enforcement verified
