# Subagent Result Envelope Pattern

> Standardize how subagents return findings to avoid context bloat
> Source: Extracted from `/refactor` skill (lines 496-520)

## Purpose

When `/skill-ship` spawns agents (e.g., `/similarity` in Phase 1), large responses consume context and degrade performance. The Result Envelope pattern ensures agents write findings to disk and return only a small summary.

## The Problem

```python
# WRONG: Agent returns full analysis inline
agent_response = """
Full analysis of 50 files with detailed explanations...
(20,000 tokens of context consumed)
"""
```

## The Solution

```python
# CORRECT: Agent writes artifact, returns envelope
agent_response = {
  "status": "done",
  "artifact": ".claude/state/agent-similarity.json",
  "summary": "Found 3 similar skills: /v (85%), /code (78%), /verify (72%)",
  "metrics": {"artifact_bytes": 2048, "files_read": 4}
}
```

## Result Envelope Schema

```json
{
  "status": "done" | "blocked" | "retry",
  "artifact": ".claude/state/{agent-name}.json",
  "summary": "≤3 short lines — no code, no diffs, no large analysis",
  "metrics": {
    "artifact_bytes": 2048,
    "files_read": 4
  }
}
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | enum | Yes | `done`: completed successfully, `blocked`: needs user input, `retry`: transient failure |
| `artifact` | string | Yes | Path to full output file (relative to project root) |
| `summary` | string | Yes | 1-3 sentence summary, max 200 chars |
| `metrics` | object | No | Optional metrics for observability |

## Implementation

### For Agent Creators

```python
def write_result_envelope(agent_name: str, findings: list) -> dict:
    """Write findings to disk and return result envelope."""
    import json
    from pathlib import Path
    from datetime import datetime

    # Write full findings to artifact
    state_dir = Path(".claude/state")
    state_dir.mkdir(parents=True, exist_ok=True)

    artifact_file = state_dir / f"agent-{agent_name}.json"
    artifact_file.write_text(json.dumps(findings, indent=2), encoding="utf-8")

    # Return envelope
    return {
        "status": "done",
        "artifact": str(artifact_file),
        "summary": f"Found {len(findings)} items. See artifact for details.",
        "metrics": {"artifact_bytes": artifact_file.stat().st_size}
    }
```

### For Orchestrators

```python
def consume_agent_result(envelope: dict) -> list:
    """Read artifact if needed for detailed analysis."""
    from pathlib import Path

    # Use summary for quick decisions
    if envelope["status"] == "done":
        print(envelope["summary"])

    # Read full artifact only when necessary
    if need_detailed_analysis(envelope):
        artifact_path = Path(envelope["artifact"])
        return json.loads(artifact_path.read_text(encoding="utf-8"))
```

## Routing Rules

From `/refactor` (lines 517-520):

1. **Phase boundaries = context resets** — Use handoff system between phases
2. **Sequential by default** — High-output agents run sequentially
3. **Targeted file reads** — Use `Grep` first, then `Read` with `offset`/`limit`
4. **Spike before high-output** — Produce type-signature-only diff first for large changes

## Integration Points

### Phase 1: Discovery

`/skill-ship` auto-invokes `/similarity` in Phase 1. Require result envelope:

```yaml
# Phase 1 workflow_steps:
- phase_1_discovery: |
    Run /similarity with result envelope pattern
    → Summary: "Found N similar skills"
    → Artifact: .claude/state/agent-similarity.json
```

### Phase 3: Quality

Validation agents should use result envelope for test results:

```json
{
  "status": "done",
  "artifact": ".claude/state/agent-validation.json",
  "summary": "3 checks passed, 1 failed (description length)",
  "metrics": {"tests_run": 4, "passed": 3, "failed": 1}
}
```

## Benefits

| Benefit | Impact |
|---------|--------|
| **Context savings** | 90%+ reduction in agent output context |
| **Faster orchestration** | Orchestrator can process multiple agents without loading full artifacts |
| **Debugging** | Artifacts persisted for post-mortem analysis |
| **Composability** | Multiple agent outputs can be merged without context explosion |

## Examples

### Similarity Analysis

```python
# /similarity agent with result envelope
findings = [
    {"skill": "/v", "similarity": 0.85, "reason": "Validation workflow"},
    {"skill": "/code", "similarity": 0.78, "reason": "Feature development"},
    {"skill": "/verify", "similarity": 0.72, "reason": "Quality gate"}
]

envelope = {
    "status": "done",
    "artifact": ".claude/state/agent-similarity.json",
    "summary": "Found 3 similar skills: /v (85%), /code (78%), /verify (72%)",
    "metrics": {"artifact_bytes": 412, "skills_analyzed": 50}
}
```

### Validation Results

```python
# testing-skills validation with result envelope
envelope = {
    "status": "done",
    "artifact": ".claude/state/agent-validation.json",
    "summary": "PASS: 4/5 checks. FAIL: Description > 100 chars",
    "metrics": {
        "checks_total": 5,
        "checks_passed": 4,
        "checks_failed": 1,
        "artifact_bytes": 2048
    }
}
```

---

**Source**: `/refactor` skill (Subagent Output Routing Rules)
**Related**: `references/workflow-phases.md` (Phase 1 Discovery)
