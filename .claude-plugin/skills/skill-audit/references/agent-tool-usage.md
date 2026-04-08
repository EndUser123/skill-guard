# Agent and Task Tool Usage

**Applies to:** Auditing skills that invoke subagents via the Agent/Task tool.

## Critical: Task and Agent Are the Same Tool

The `Task` tool was **renamed to `Agent`** in Claude Code v2.1.63. They are the same invocation mechanism. `Task(...)` remains as a backward-compatible alias.

When auditing a skill that says "via Agent tool" or "via Task tool" — they mean the same thing. The skill's choice of name is not a meaningful distinction.

## Tool Parameters

| Parameter | Required | Purpose |
|-----------|----------|---------|
| `subagent_type` | **Yes** | Which specialized agent to invoke (e.g., `general-purpose`, `adversarial-security`) |
| `prompt` | **Yes** | Instructions for the subagent |
| `description` | **Yes** | Short summary for task tracking |
| `model` | No | Override model (`sonnet`, `opus`, `haiku`) |
| `run_in_background` | No | If `true`, agent runs non-blocking/parallel |

## What to Check in Skill Audits

### Mechanism Leakage (Lens 9)
- Does the skill hardcode `Agent(...)` or `Task(...)` calls in policy text?
- Is the subagent type named explicitly (correct) or misspelled (bug)?
- Does the skill reference an agent that doesn't exist in `P:/.claude/agents/`?

### Skill Contract Consistency (Lens 8)
- Does the skill say "via Agent tool" in one section and "via Task tool" in another? This is **not** a contradiction — they are the same tool.
- Does the skill promise parallel execution but use sequential dispatch?

### Parallel Execution Claims
- `run_in_background=True` = non-blocking parallel execution
- Without it, agents run sequentially (blocking)
- Up to 10 subagents can run in parallel

### File-Based Handoff Pattern
When a skill dispatches multiple subagents that each write findings to disk:
- Look for: session directory creation, dispatch manifest, JSON file paths in prompts
- Verify: the skill checks for JSON availability before proceeding to synthesis phase
- This is the `/pre-mortem` / `/sqa` L0 pattern — proper isolation and idempotent dispatch

## Common Errors to Flag

1. **`subagent_type: "haiku"`** — haiku is a model, not an agent type. Should be `model: "haiku"`
2. **Missing `description`** — Agent/Task tool silently fails if description is absent
3. **Sequential dispatch claimed as parallel** — skill says "parallel" but launches agents one-by-one without `run_in_background=True`
4. **No completion check** — skill dispatches agents but doesn't verify JSON files exist before synthesis

## Agent Discovery

Current agent list at runtime:
```bash
python scripts/list_agents.py --names
```

## References

- `/skill-ship/references/agent-tool-usage.md` — full agent tool reference
- `P:/.claude/agents/_README.md` — agent definitions
- Claude Code v2.1.63 changelog — Task → Agent rename
