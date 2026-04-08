# Agent and Task Tool Usage

**Applies to:** All skills that dispatch subagents via the Agent/Task tool.

## Critical: Task and Agent Are the Same Tool

The `Task` tool was **renamed to `Agent`** in Claude Code v2.1.63. They are the same invocation mechanism. `Task(...)` remains as a backward-compatible alias.

> **Practical consequence:** When a skill references "Agent tool" or "Task tool", they mean the same thing. The parameter names are identical. Do not treat them as separate mechanisms.

## Tool Parameters

Both `Agent(...)` and `Task(...)` accept the same parameters:

| Parameter | Required | Purpose |
|-----------|----------|---------|
| `subagent_type` | **Yes** | Which specialized agent to invoke (e.g., `general-purpose`, `Explore`, `adversarial-security`) |
| `prompt` | **Yes** | Instructions for the subagent |
| `description` | **Yes** | Short summary for task tracking |
| `model` | No | Override model (`sonnet`, `opus`, `haiku`) |
| `run_in_background` | No | If `true`, agent runs non-blocking/parallel |
| `name` | No | Custom name for agent (team coordination) |
| `team_name` | No | Spawn agent into specific team |

**Common mistake:** Writing `subagent_type: "haiku"` — haiku is a model, not an agent type. Use `model: "haiku"` to override model.

## Parallel Execution

- Up to **10 subagents** can run in parallel via the Agent tool
- Use `run_in_background=True` for fire-and-forget parallelism
- Each subagent runs in its **own isolated context**
- Subagents cannot see each other's work — they report summaries back to the orchestrator
- **No inter-agent communication** in standard mode

## When to Use Agent Teams (Coordination)

Standard subagent isolation is fine when:
- Each specialist works independently on separate files/domains
- Results only need to be synthesized at the end
- No negotiation or dynamic task distribution needed

Use **Agent Teams** (with `TaskCreate`, `TaskList`, `SendMessage`) when:
- Agents must coordinate work dynamically (divide a task, claim dependencies)
- Agents need to communicate with each other during execution
- Blocked tasks need to auto-unblock when dependencies complete

For `/sqa` L0: 7 specialists + 1 critic — standard parallel agents are sufficient. No inter-agent coordination needed.

## Dispatching Named Agents

Named agents (like `adversarial-logic`, `Explore`, `Plan`) are invoked via `subagent_type`:

```
Agent(
    subagent_type="adversarial-security",
    prompt="Analyze <target> for security issues. Write findings to <path>",
    description="Security analysis",
    run_in_background=True
)
```

For the current list of available agents:
```bash
python scripts/list_agents.py --names
python scripts/list_agents.py --json  # with descriptions
```

Sources: `~/.claude/skills/skill-ship/references/agent-tool-usage.md` (this file), `P:/.claude/agents/_README.md`

## Agent Tool in Skill Frontmatter

Some skills declare `parallel_agents: true` in frontmatter to indicate they dispatch multiple agents simultaneously. This is advisory metadata — the actual mechanism is the `run_in_background` parameter.

## References

- Skill invocation: `SKILL.md` frontmatter `triggers:`
- Agent definitions: `P:/.claude/agents/*.md`
- Teams feature: Claude Code `--agent` CLI flag, `team_name` parameter
