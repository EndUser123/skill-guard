---
name: migrate-skill-ef
description: "Migrate legacy skills to the Evidence-First (-ef) model. Wires the skill into the shared enforce layer and standardizes tool-to-step mapping."
version: "1.0.0"
category: development
enforcement: strict
triggers:
  - migrate skill ef
  - migrate to ef
  - evidence first migration
  - /migrate-skill-ef
contract_type: workflow-execution
required_artifacts:
  - migration-report.json
allowed_tools_now:
  - Read
  - Bash
  - Glob
  - Grep
  - Write
  - Edit
response_requirements:
  sections:
    - analysis
    - changes
    - verification
---

# migrate-skill-ef

Automates the migration of legacy skills to the Evidence-First (-ef) architecture. This tool focuses on structural and logic changes required to participate in the shared `enforce/` cluster-wide gating system.

## When to Use

Use when a skill is still managing its own internal `phase_ledger.py` or lacks standardized tool-to-step breadcrumb tracking.

## Usage

- `/migrate-skill-ef <skill-name>`: Audit the target skill for EF compatibility.
- `/migrate-skill-ef <skill-name> --write true`: Apply structural and logic changes.

## Workflow

1.  **Analyze**: Inspect the target skill's `hooks/` and `__lib/` for legacy state management.
2.  **Logic Shift**: Replace local state writes with calls to the shared `cc-skills-sdlc/enforce` layer.
3.  **Hook Update**: Standardize `PostToolUse` and `Stop` hooks to use the `run(data)` pattern and verified identity handshake.
4.  **Verify**: Run syntax checks and ensure the skill correctly reports to the shared ledger.

## Output

Returns a report detailing:
- Identified legacy patterns.
- Proposed or applied changes (hook refactoring, import updates).
- Verification results.
