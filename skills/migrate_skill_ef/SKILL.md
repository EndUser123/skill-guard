---
name: migrate_skill_ef
description: "Migrate legacy skills to the Evidence-First (-ef) model. Wires the skill into the shared enforce layer and standardizes tool-to-step mapping."
version: "1.1.0"
category: development
enforcement: strict
contract_type: workflow-execution
required_artifacts: []
response_requirements: {}
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

## Implementation Tooling

Choose based on workflow shape, not personal preference:

**Linear sequential workflows** (analyze → shift → update → verify):
- Pydantic for typed state models
- File-based phase gates (`.phase-entered_{PHASE}_{RUN_ID}`, etc.)
- State persisted in `.claude/.artifacts/{terminal_id}/{skill}/`
- No orchestration framework needed

**Branching or non-linear workflows** (conditional routing, human-in-the-loop, dynamic node selection):
- LangGraph appropriate when workflow graph has multiple paths, checkpoints, or conditional edges
- Consider whether the complexity is inherent to the problem or introduced by the tooling

**Use the simplest approach that fits the workflow complexity.** The decision criterion is workflow shape, not preference.

**State persistence:** File-based (JSON in `.claude/.artifacts/`). Never in-memory — multi-terminal sessions share no memory space.

**Path handling:** Use env vars (`$CLAUDE_PLUGIN_ROOT`, `$TERMINAL_ID`) instead of hardcoded paths.

## Output

Returns a report detailing:
- Identified legacy patterns.
- Proposed or applied changes (hook refactoring, import updates).
- Verification results.
