# Skill-Based Self-Verification Patterns

**Last Updated**: 2026-03-09

## Source

**Author**: disler (IndyDevDan)
**Repositories**:
- [agentic-finance-review](https://github.com/disler/agentic-finance-review) - Specialized self-validating agents using hooks
- [claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery) - Comprehensive hooks reference

## Core Concept

**Specialized Self-Validation** = Focused Agent + Specialized Validation = Trusted Automation

The key insight: **Specialized hooks embed in prompts, subagents, and skills**. Before this feature, hooks were global (in `settings.json`). Now you can define hooks that run only for specific agents, enabling:

- **CSV agents** that validate CSV structure after every file operation
- **Build agents** that run linters and type checkers on completion
- **UI agents** that validate HTML output

## Hook Frontmatter Specification

### Command/Skill Frontmatter

```yaml
---
model: opus
description: Make modifications or report on csv files
argument-hint: [csv_file] [user_request]
allowed-tools: Glob, Grep, Read, Edit, Write
hooks:
  PostToolUse:
    - matcher: "Read|Edit|Write"
      hooks:
        - type: command
          command: "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/validators/csv-single-validator.py"
---
```

### Subagent Frontmatter

```yaml
---
name: csv-edit-agent
description: Make modifications or report on csv files. Use only when directly requested.
tools: Glob, Grep, Read, Edit, Write
model: opus
hooks:
  PostToolUse:
    - matcher: "Read|Edit|Write"
      hooks:
        - type: command
          command: "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/validators/csv-single-validator.py"
color: cyan
---
```

## Frontmatter Fields

| Field | Purpose |
| --- | --- |
| `model` | Which model to use (opus, sonnet, haiku) |
| `description` | When Claude should invoke this command/skill |
| `argument-hint` | Shows users expected arguments |
| `allowed-tools` | Restricts tool access for security/focus |
| `hooks` | Specialized validation hooks |
| `name` | Subagent name (for subagents only) |
| `tools` | Tools available to subagent |
| `color` | Terminal display color (for subagents) |

## Hook Events and Use Cases

| Hook Event | When It Fires | Use Case | Exit Code Impact |
| --- | --- | --- | --- |
| `PreToolUse` | Before a tool runs | Block dangerous operations | 0=allow, 2=block |
| `PostToolUse` | After tool completes | Validate output | 0=success, 2=blocking error |
| `Stop` | When agent finishes | Final validation/cleanup | 0=success, 2=blocking error |

## Exit Codes Matter

| Exit Code | Behavior | Use Case |
| --- | --- | --- |
| 0 | Success - proceed normally | Validation passed |
| 2 | Blocking error - stderr fed back to Claude | Validation failed, self-correct |
| Other | Non-blocking error | Advisory warning |

## Validator Script Architecture

### Input Format (JSON via stdin)

```json
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../session.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "data.csv",
    "content": "..."
  }
}
```

### Output Format

```python
import sys
import json

def main():
    # Read hook input from stdin
    data = json.load(sys.stdin)

    # Perform validation
    if validate(data["tool_input"]):
        # Success - proceed
        print("✓ Validation passed")
        sys.exit(0)
    else:
        # Blocking error - show Claude what's wrong
        print("✗ Validation failed: CSV structure invalid", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
```

## Prompts vs Subagents

| Feature | Prompt (Slash Command) | Subagent |
| --- | --- | --- |
| Context | Runs in current context | Isolated context window |
| Parallelism | Sequential | Can run multiple in parallel |
| Arguments | Uses `$1`, `$2`, `$ARGUMENTS` | Infers from prompt |
| Invocation | `/csv-edit file.csv "add row"` | "Use csv-edit-agent to..." |
| Best For | Single-user operations | Multi-agent pipelines |

## Real-World Examples

### CSV Edit with Self-Correction

```markdown
User: /csv-edit savings.csv "add a row for a $100 deposit"

Agent: [Reads file]
Hook: [Validates CSV structure] ✓

Agent: [Edits file to add row]
Hook: [Validates CSV structure]
  ✗ Balance mismatch! Expected $1100, got $1000

Agent: [Fixes balance calculation]
Hook: [Validates CSV structure] ✓

Agent: "Added deposit row with correct balance."
```

**Pattern**: PostToolUse validation after every file operation catches errors immediately, enabling self-correction before completion.

### Multi-Agent Pipeline

```markdown
/review-finances mar checkings.csv savings.csv
    │
    ├─> normalize-csv-agent (validates CSV + balance)
    ├─> categorize-csv-agent (validates CSV)
    ├─> merge-accounts-agent (validates merged output)
    ├─> graph-agent (validates PNG generation)
    └─> generative-ui-agent (validates HTML)
```

**Pattern**: Each agent in the pipeline has specialized validation for its output. Downstream agents can trust upstream work.

### Parallel Execution

```markdown
User: "Use one CSV edit agent per file in mock-input-data/"

Claude: [Spawns 4 agents in parallel]
  ├─> csv-edit-agent (checkings.csv)
  ├─> csv-edit-agent (savings.csv)
  ├─> csv-edit-agent (credit.csv)
  └─> csv-edit-agent (expenses.csv)

[All 4 agents validate their work independently]
```

**Pattern**: Parallel agents with independent validation scales horizontally. Each agent's hooks run in isolation.

### Multiple Stop Hooks

```yaml
---
name: normalize-csv-agent
hooks:
  Stop:
    - matcher: ".*"
      hooks:
        - type: command
          command: "uv run .claude/hooks/validators/csv-validator.py"
        - type: command
          command: "uv run .claude/hooks/validators/balance-validator.py"
---
```

**Pattern**: Multiple validators can run at Stop event. All must pass (exit 0) for agent to complete successfully.

## Project Structure

```
.claude/
├── commands/          # Custom slash commands (prompts)
│   ├── csv-edit.md    # CSV editing with PostToolUse validation
│   ├── build.md       # Build command with Stop validation
│   └── review-finances.md  # Orchestrator command
├── agents/            # Subagents for parallel work
│   ├── csv-edit-agent.md
│   ├── normalize-csv-agent.md
│   └── generative-ui-agent.md
└── hooks/
    └── validators/    # Validation scripts
        ├── csv-single-validator.py
        ├── csv-validator.py
        ├── html-validator.py
        └── ...
```

## Why Specialized Agents Win

A focused agent with one purpose **outperforms** an unfocused agent with many purposes.

| Approach | Result |
| --- | --- |
| General agent doing everything | Works sometimes, fails unpredictably |
| Specialized agent + validation | Consistent, reliable, trustworthy |

```text
Specialization + Deterministic Validation = Trust
```

## Best Practices

### 1. Read the Docs

Actually read the documentation. Don't just paste it into your agent.

### 2. Build Focused Agents

One agent, one purpose, extraordinary results.

### 3. Add Specialized Validation

Every good engineer validates their work. Your agents should too.

### 4. Use Hooks Strategically

- **PostToolUse**: For each operation (immediate feedback)
- **Stop**: For final validation (before completion)
- **PreToolUse**: To block dangerous operations (guardrails)

### 5. Log Everything

Observability is critical. Use stdout for information, stderr only for blocking errors.

## Integration with Skill-Based Hooks System

The internal skill-based hooks enforcement system (`P:/.claude/hooks/docs/skill_enforcement.md`) and disler's self-verification patterns are **complementary**:

| Aspect | Internal Enforcement | Self-Verification |
| --- | --- | --- |
| **Purpose** | Force Skill() tool use | Validate agent output |
| **Scope** | Global (all skills) | Per-skill/per-agent |
| **Enforcement** | PreToolUse blocking | PostToolUse/Stop validation |
| **Focus** | Correct skill invocation | Correct work output |

**Combined Pattern**:

```yaml
---
name: specialized-agent
allowed_first_tools: ["Read", "Grep"]  # Internal enforcement
hooks:
  PostToolUse:  # Self-verification
    - matcher: "Write"
      hooks:
        - type: command
          command: "validators/output-validator.py"
---
```

**Result**: Agent is forced to use Skill() tool first, AND validates its output before completion.

## Security Considerations

### Input Validation

Validators should sanitize input from hook payload:

```python
# Safe: Validate file paths
file_path = Path(data["tool_input"]["file_path"]).resolve()
if not str(file_path).startswith(str(Path.cwd())):
    sys.exit(2)  # Block path traversal
```

### Allowed Tools

Restrict tool access in command/skill frontmatter:

```yaml
allowed-tools: Glob, Grep, Read, Edit, Write  # No Bash, no WebSearch
```

### Deterministic Validation

Validators should be **deterministic scripts**, not LLM calls:

```python
# Good: Deterministic CSV validation
if not validate_csv_structure(file_path):
    sys.exit(2)

# Bad: LLM-based validation (non-deterministic)
result = ask_claude("Is this CSV valid?")
```

## Performance Impact

| Hook Event | Performance Impact | Mitigation |
| --- | --- | --- |
| PreToolUse | Low (blocking only) | Fast checks only |
| PostToolUse | Medium (after every tool) | Cache results, async validation |
| Stop | Low (once per agent) | Comprehensive validation OK |

## Troubleshooting

### "Hook is not firing"

**Check**:
1. Is hook registered in frontmatter (`hooks:` section)?
2. Does `matcher` regex match tool name?
3. Is validator script executable?
4. Check hook logs: `tail -20 .claude/logs/*.jsonl`

### "Validator exits with code 2 but Claude continues"

**Issue**: Wrong exit code usage.

**Fix**: Use exit code 2 for blocking errors, not other codes. Exit 2 = successful block.

### "Multiple Stop hooks - which one ran last?"

**Check**: Logs show execution order. All must exit 0 for agent to complete.

### "Parallel agents - which validator failed?"

**Check**: Agent output includes stderr from failed validator. Each agent's hooks run in isolation.

## Advanced Patterns

### Conditional Hooks

```yaml
hooks:
  PostToolUse:
    - matcher: "Write"
      when: "tool_input.file_path.endswith('.csv')"
      hooks:
        - type: command
          command: "validators/csv-validator.py"
```

### Chained Validators

```yaml
hooks:
  Stop:
    - hooks:
        - type: command
          command: "validators/step1-validator.py"
        - type: command
          command: "validators/step2-validator.py"
        - type: command
          command: "validators/step3-validator.py"
```

### Adaptive Validation

```python
# Validator script
def validate_complexity(data):
    tool_name = data["tool_name"]
    if tool_name == "Write":
        # Comprehensive validation for writes
        return validate_write(data)
    elif tool_name == "Read":
        # Light validation for reads
        return validate_read(data)
```

## Key Takeaways

1. **Specialization Wins**: Focused agents + validation beat general agents
2. **Hook Events Matter**: Choose right event (PreToolUse vs PostToolUse vs Stop)
3. **Exit Codes Control Flow**: 0 = proceed, 2 = block
4. **Deterministic Validation**: Scripts, not LLM calls
5. **Observability**: Log everything, stderr for errors only
6. **Parallelism**: Independent agents scale horizontally
7. **Trust Through Verification**: Validation increases trust, trust saves time

## References

- **disler/agentic-finance-review**: https://github.com/disler/agentic-finance-review
- **disler/claude-code-hooks-mastery**: https://github.com/disler/claude-code-hooks-mastery
- **Internal Skill Enforcement**: `P:/.claude/hooks/docs/skill_enforcement.md`
- **Hook Protocol**: `P:/.claude/hooks/PROTOCOL.md`
