---
name: migrate_skill_ef
description: "Migrate legacy skills to the Evidence-First (-ef) model and execution-contract frontmatter. Handles both structural EF migration (enforce layer wiring) and frontmatter contract migration (contract_type, required_artifacts, response_requirements)."
version: "2.0.0"
category: development
enforcement: strict
contract_type: workflow-execution
required_artifacts: []
response_requirements: {}
---
# migrate-skill-ef

Unified migration tool that handles both structural EF migration and frontmatter contract migration for legacy skills.

## When to Use

Use when a skill needs one or more of:
- Migration to the evidence-first (-ef) architecture with shared `enforce/` gating
- Frontmatter contract fields (`contract_type`, `required_artifacts`, `response_requirements`)
- Standardized tool-to-step breadcrumb tracking
- `workflow_steps` with `first_tool` declarations for step-gate enforcement

## Usage

### Frontmatter Contract Migration

- `/migrate-skill-ef <skill-name>`: Audit frontmatter contract readiness
- `/migrate-skill-ef <skill-name> --plugin <plugin>`: Scope to specific plugin
- `/migrate-skill-ef <skill-name> --mode patch --write true`: Apply frontmatter patches
- `/migrate-skill-ef <plugin>:<skill-name>`: Scoped form (e.g., `cc-skills-analysis:gto`)

### EF Structural Migration

- `/migrate-skill-ef --ef <base-skill>`: Create a -ef variant wired to enforce layer
- `/migrate-skill-ef --ef <base-skill> --dry-run`: Preview without writing

### Batch Operations

- `/migrate-skill-ef --batch --skills-dir <path>`: Audit all skills in directory
- `/migrate-skill-ef --all --dry-run`: Plan patches for all UNMIGRATED skills
- `/migrate-skill-ef --all --write true`: Apply patches to all UNMIGRATED skills

## Workflow

### Step 1: Classify Frontmatter (Contract Migration)

Inspect the target skill's SKILL.md frontmatter and classify migration status:

| Status | Meaning |
|--------|---------|
| `UNMIGRATED` | Legacy skill — no contract-era `contract_type` or completion fields |
| `PARTIALLY_MIGRATED` | Has `contract_type` but missing core completion fields |
| `MIGRATED` | Has `contract_type` and all required completion fields |

Classification uses `classify_migration_status()` and `build_migration_result()` from `skill_guard._skill_frontmatter_loader`.

### Step 2: Patch Frontmatter (if needed)

For `UNMIGRATED` or `PARTIALLY_MIGRATED` skills:

**Audit mode** (default): Report missing fields and proposed YAML diff.
**Patch mode** (`--mode patch`): Propose specific changes.
**Apply mode** (`--mode patch --write true`): Atomically write changes to SKILL.md.

Patches only touch frontmatter between `---` delimiters. Prose sections are never modified.

**Contract type selection (mandatory):** `contract_type` MUST be one of these contract-era values:

| Value | When to use | Required companion field |
|-------|-------------|--------------------------|
| `workflow-execution` | Skill runs a multi-step workflow (tool calls, phases, state transitions) | `required_artifacts` |
| `structured-output` | Skill produces structured output (reports, analyses, formatted responses) | `response_requirements` |
| `hybrid` | Skill does both — runs workflow steps AND produces structured output | Both `required_artifacts` AND `response_requirements` |

Invalid values (will cause re-classification as UNMIGRATED): `advisory`, `analysis`, `workflow`, `output`, `diagnostic`, `blocking`, or any value not in the table above.

**Enforcement semantics:** All contract types imply the skill MUST be followed as written. The `enforcement` field (`strict` / `advisory` / `none`) controls how the runtime enforces compliance — it does NOT mean the skill is optional. Never describe a contract_type as "not blocking" or "can be skipped."

### Step 3: Analyze Structure (EF Migration)

If `--ef` is specified, inspect the target skill's `hooks/` and `__lib/` for legacy state management.

### Step 4: Logic Shift

Replace local state writes with calls to the shared `cc-skills-sdlc/enforce` layer.

### Step 5: Hook Update

Standardize `PostToolUse` and `Stop` hooks to use the `run(data)` pattern and verified identity handshake.

### Step 6: Step-Gate Readiness Check

`PreToolUse_workflow_step_gate.py` enforces step ordering during skill execution. It works at two precision levels:

| Level | How it works | Requires frontmatter changes? |
|-------|-------------|-------------------------------|
| **Heuristic** (default) | Matches command tokens against step names | No |
| **Precise** (recommended) | Checks `first_tool` field per step | Yes — add `first_tool` to each step dict |

**Audit checks:**

1. Does the skill have `workflow_steps`? If not, skip.
2. Are steps declared as strings or dicts? Strings work but lack `first_tool`.
3. For each step, is `first_tool` declared? If not, fallback to heuristic.
4. Does `verification.expected_artifacts` exist? If not, artifact-based gating unavailable.

**Patch behavior** (`--write true`): Convert string-only `workflow_steps` to dict form with `first_tool` inferred:

```yaml
# Before (heuristic-only)
workflow_steps:
  - Capture work input
  - Initialize file-based session

# After (precise enforcement)
workflow_steps:
  - id: Capture work input
  - id: Initialize file-based session
    first_tool: Bash
```

**`first_tool` common mappings:**

| Step pattern | Typical first_tool |
|-------------|-------------------|
| "Capture", "Analyze", "Extract", "Read" | `Read` |
| "Initialize", "Create session", "Run" | `Bash` |
| "Launch", "Dispatch", "Phase" | `Agent` |
| "Write", "Deliver", "Output" | `Write` |
| "Verify", "Test", "Check" | `Bash` |

### Step 7: Verify

Run syntax checks and ensure the skill correctly reports to the shared ledger. Re-run classification to confirm `MIGRATED` for applied patches.

## Implementation Tooling

**Linear sequential workflows**: Pydantic for typed state models, file-based phase gates, state in `.claude/.artifacts/{terminal_id}/{skill}/`.

**Branching workflows**: LangGraph for dynamic node routing; state machine with Pydantic for shallow branching.

**State persistence:** File-based (JSON in `.claude/.artifacts/`). Never in-memory.

**Path handling:** Use env vars (`$CLAUDE_PLUGIN_ROOT`, `$TERMINAL_ID`) instead of hardcoded paths.

## Output

Returns a report detailing:
- Frontmatter classification (UNMIGRATED / PARTIALLY_MIGRATED / MIGRATED)
- Missing fields and proposed patches
- Step-gate readiness (workflow_steps format, first_tool coverage)
- Applied or proposed changes (frontmatter patches, hook refactoring, step declarations)
- Verification results (YAML validity, re-classification)
