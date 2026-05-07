---
name: migrate-skill-ct
description: "Audit and optionally patch target skills to the execution-contract frontmatter model. Use when a skill needs migration to workflow-execution, structured-output, or hybrid contract types."
version: "1.0.0"
category: development
enforcement: advisory
triggers:
  - migrate skill ct
  - migrate skill contract
  - skill migration
  - execution contract migration
  - skill frontmatter upgrade
  - migrate skill
contract_type: workflow-execution
required_artifacts:
  - migration-report.json
allowed_tools_now:
  - Read
  - Bash
  - Glob
  - Grep
response_requirements:
  sections:
    - classification
    - missing_fields
    - patch
    - verification
---

# migrate-skill-ct

Audits a target skill's SKILL.md frontmatter, classifies its migration readiness, and optionally generates or applies a minimal migration patch.

## When to Use

Use when the `skill_metadata_advisory` hook warns that a skill needs migration to the execution-contract model. You can also invoke directly:

- `/migrate-skill-ct <skill-name>`
- `/migrate-skill-ct <skill-name> --mode audit`
- `/migrate-skill-ct <skill-name> --mode patch`
- `/migrate-skill-ct <skill-name> --mode patch --write true`

## Workflow Steps

### Step 1: Parse invocation

Extract `skill_name` from the prompt (required). Parse optional flags:
- `mode`: `audit` (default) or `patch`
- `write`: `false` (default) or `true`

### Step 2: Load target skill frontmatter

Read the target skill's SKILL.md from `P:\\\\.claude-marketplace/plugins/<skill_name>/SKILL.md` (default). Override via `--skills-dir` argument or `SKILL_DIR` env var.

If the file does not exist, return an error immediately.

### Step 3: Classify migration status

Run the migration script:

```bash
cd "P:\\\\packages/skill-guard" && python skills/migrate_skill_ct/src/migrate_skill_contract.py --skill <skill-name> --mode <audit|patch> [--write true] [--skills-dir P:\\\\.claude-marketplace/plugins]
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

## Rules

- Do NOT patch when status is `MIGRATED`
- Do NOT touch prose sections below the frontmatter `---` delimiters
- Do NOT guess at values — use what `build_migration_result` reports as missing
- Prefer minimal patches: add only what `classify_migration_status` identifies as required
- If the target skill file cannot be read, return an error with the skill name and path attempted
