---
name: migrate_skill_ct
description: "Audit and optionally patch target skills to the execution-contract frontmatter model. Use when a skill needs migration to workflow-execution, structured-output, or hybrid contract types."
version: "1.1.0"
category: development
enforcement: advisory
contract_type: workflow-execution
required_artifacts: []
response_requirements: {}
---
# migrate-skill-ct

Audits a target skill's SKILL.md frontmatter, classifies its migration readiness, and optionally generates or applies a minimal migration patch.

## When to Use

Use when the `skill_metadata_advisory` hook warns that a skill needs migration to the execution-contract model. You can also invoke directly:

- `/migrate-skill-ct <skill-name>` — auto-searches across all plugins
- `/migrate-skill-ct <plugin>:<skill-name>` — scoped to a specific plugin (e.g., `cc-skills-analysis:gto`)
- `/migrate-skill-ct <skill-name> --plugin <plugin>` — explicit plugin flag
- `/migrate-skill-ct <skill-name> --mode audit` — read-only classification
- `/migrate-skill-ct <skill-name> --mode patch` — propose changes without writing
- `/migrate-skill-ct <skill-name> --mode patch --write true` — apply patch to SKILL.md

If a bare skill name exists in multiple plugins, the skill raises an error naming each location and instructs you to use `--plugin` or the scoped form to disambiguate.

## Workflow Steps

### Step 1: Parse invocation

Extract `skill_name` from the prompt (required). Parse optional flags:
- `mode`: `audit` (default) or `patch`
- `write`: `false` (default) or `true`
- `plugin`: explicit plugin name (optional)

**Scoped form** (`plugin:skill-name`): if the first argument contains a colon, split on the colon — the left side is the plugin name, the right side is the skill name.

**Explicit `--plugin` flag**: overrides any plugin implied by the scoped form.

**Auto-search**: if no plugin is specified, search all plugins under `PLUGINS_DIR` for a matching skill. Raise an error if the skill exists in multiple plugins.

### Step 2: Load target skill frontmatter

Resolve the skill's SKILL.md path:

- **With `--plugin` or scoped form**: `PLUGINS_DIR/<plugin>/skills/<skill-name>/SKILL.md`
- **With auto-search**: scan `PLUGINS_DIR/*/skills/<skill-name>/SKILL.md` for candidates

`PLUGINS_DIR` defaults to `P:\\.claude-marketplace\plugins`. Override via the `PLUGINS_DIR` env var.

If the file does not exist, return an error immediately.

### Step 3: Classify migration status

Run the migration script:

```bash
cd "P:\\packages/skill-guard" && python skills/migrate_skill_ct/src/migrate_skill_contract.py --skill <skill-name> --mode <audit|patch> [--write true] [--plugin <plugin-name>]
```

The script wraps `classify_migration_status()` and `build_migration_result()` from `skill_guard._skill_frontmatter_loader`.

The classifier uses contract-era `contract_type` values (`workflow-execution`, `structured-output`, `hybrid`) and presence of core completion fields (`required_artifacts`, `response_requirements`):

| Status | Meaning |
|--------|---------|
| `UNMIGRATED` | Legacy skill — no contract-era contract_type or completion fields |
| `PARTIALLY_MIGRATED` | Has contract_type but missing core completion fields |
| `MIGRATED` | Has contract_type and all required completion fields |

### Step 4: Audit mode (default)

If status is `MIGRATED`:
- Return no-op: `action: "none"`, reason explaining migration is complete
- No file changes

If status is `UNMIGRATED` or `PARTIALLY_MIGRATED`:
- Return structured result: skill, status, action, reason, missing_fields
- No file changes

### Step 5: Patch mode

If status is `MIGRATED`: return no-op (same as audit).

If status is `UNMIGRATED` or `PARTIALLY_MIGRATED`:

**Proposed patch (`write=false`, the default):**
- Identify the exact frontmatter changes needed
- Report the proposed YAML patch as a diff
- Do not modify any files

**Applied patch (`write=true`):**
- Read the target SKILL.md
- Add or set only the missing fields identified by `build_migration_result`
- Write the updated SKILL.md back atomically
- Report exactly what changed (field name, old value, new value)
- Do NOT touch prose sections below the frontmatter `---` delimiters

### Step 6: Verify

After any patch (applied or proposed), confirm:
- The modified frontmatter parses as valid YAML
- Re-run classification to confirm `MIGRATED` (for applied patches only)

## Output Format

Return a structured response with these sections:

### Classification
- Skill name
- Prior status (before patch)
- Current status (after applied patch, if applicable)
- Reason for classification

### Missing Fields
- List of fields that were missing before the patch
- For each: field name, expected value, whether it was added

### Patch (if applicable)
- For `audit` mode: proposed YAML changes as a diff
- For `patch --write true`: exact fields changed, old → new values, files modified

### Verification
- YAML validity check result
- New classification result (applied patches only)

## Implementation Tooling

Choose based on workflow shape, not personal preference:

**Linear sequential workflows** (task → verify → simplify → review → PR):
- Pydantic for typed state models
- File-based phase gates (`.worktree-ready_{RUN_ID}`, etc.)
- State persisted in `.claude/.artifacts/{terminal_id}/{skill}/`
- No orchestration framework needed

**Branching or non-linear workflows** (conditional routing, human-in-the-loop, dynamic node selection):
- LangGraph appropriate when workflow graph has multiple paths, checkpoints, or conditional edges
- Consider whether the complexity is inherent to the problem or introduced by the tooling

**Use the simplest approach that fits the workflow complexity.** A linear pipeline doesn't need LangGraph; a workflow with dynamic branching does. The decision criterion is workflow shape, not preference.

**State persistence:** File-based (JSON in `.claude/.artifacts/`). Never in-memory — multi-terminal sessions share no memory space.

**Path handling:** Use env vars (`$CLAUDE_PLUGIN_ROOT`, `$TERMINAL_ID`) instead of hardcoded paths.

## Rules

- Do NOT patch when status is `MIGRATED`
- Do NOT touch prose sections below the frontmatter `---` delimiters
- Do NOT guess at values — use what `build_migration_result` reports as missing
- Prefer minimal patches: add only what `classify_migration_status` identifies as required
- If the target skill file cannot be read, return an error with the skill name and path attempted
- If a bare skill name resolves to multiple plugins, return an error naming each location — do not pick arbitrarily. Instruct the user to use `--plugin` or the `plugin:skill` scoped form to disambiguate.
