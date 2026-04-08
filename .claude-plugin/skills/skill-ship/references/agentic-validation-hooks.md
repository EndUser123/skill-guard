# Agentic Validation Hooks

> Self-correcting patterns using PostToolUse validation + state transitions
> Source: Extracted from `/agentic-validation` skill

## Purpose

Skills can validate their own output and enforce state transitions using hooks. This creates self-correcting systems that catch errors before users encounter them.

## Three Patterns

### Pattern 1: Validation

**Flow:** `Tool → PostToolUse → Validator → Pass/Fail`

```python
# PostToolUse_validator.py
if tool_name == "Write":
    if not validate_yaml(filepath):
        return {
            "hookSpecificOutput": {
                "additionalContext": "❌ YAML syntax error. Fix and retry."
            }
        }
```

**Use cases:** CSV syntax validation, code quality checks, format verification

### Pattern 2: State Transition

**Flow:** `Router → State → Block → Transition → Allow`

```python
# PreToolUse: Block if not allowed
if tool_name not in read_state().get("allowed_tools", []):
    sys.exit(2)  # Block tool use

# PostToolUse: Transition phases
if tool_name == "Skill":
    write_state(phase="execute", allowed_tools=["Bash"])
```

**Use cases:** Multi-phase workflows, skill enforcement, sequential validation

### Pattern 3: Combined

**Flow:** `Validate → Pass: Next Phase | Fail: Retry`

```python
if validate(file) and state["phase"] == "draft":
    write_state(phase="review", allowed_tools=["Edit"])
else:
    write_state(phase="draft", allowed_tools=["Write"])  # Retry
```

## Implementation

### Hook Locations

| Hook Type | Purpose | Example |
|-----------|---------|---------|
| `PostToolUse_<name>.py` | Validation, transitions | Validate YAML after Write |
| `PreToolUse_<name>.py` | Blocking gates | Block Edit if not in review phase |
| `UserPromptSubmit_<name>.py` | Workflow init | Initialize state for skill execution |

### State Template

```python
{
    "phase": "draft",           # Current phase
    "allowed_tools": ["Write"], # Tools permitted in this phase
    "expires_at": 1769667278,   # Prevent stale state
    "terminal_id": "abc123"     # Multi-terminal isolation
}
```

### Critical Requirements

| Requirement | Why | How |
|-------------|-----|-----|
| **Expiration** | Prevent stale state blocking future sessions | Always set/check `expires_at` |
| **Isolation** | Multi-terminal safety | Use CWD hash in state filenames |
| **Specific errors** | Actionable feedback | "YAML syntax error at line 15" not "Invalid file" |
| **Restrictive → expand** | Start tight, loosen after validation | Begin with Read-only, add Write after validation |

## Example: Skill YAML Validation

```python
# P:/.claude/skills/myskill/hooks/PostToolUse_myskill_yaml_validator.py

import sys
import yaml
from pathlib import Path

def validate_yaml_frontmatter(file_path: str) -> bool:
    """Validate SKILL.md YAML frontmatter."""
    content = Path(file_path).read_text(encoding="utf-8")

    if not content.startswith("---"):
        return False

    # Extract YAML section
    yaml_end = content.find("---", 3)
    yaml_section = content[3:yaml_end]

    try:
        frontmatter = yaml.safe_load(yaml_section)
        required_fields = ["name", "description", "category", "triggers"]
        return all(field in frontmatter for field in required_fields)
    except yaml.YAMLError:
        return False

def post_tool_use_handler(tool_input, tool_result, execution_context):
    """PostToolUse hook for YAML validation."""
    if tool_input.get("tool_name") == "Write" and "SKILL.md" in tool_input.get("file_path", ""):
        file_path = tool_input["file_path"]

        if not validate_yaml_frontmatter(file_path):
            return {
                "hookSpecificOutput": {
                    "additionalContext": (
                        "❌ YAML frontmatter validation failed.\n"
                        "Required fields: name, description, category, triggers\n"
                        "Fix and retry."
                    )
                }
            }

    return {}
```

## Example: Phase Transition Enforcement

```python
# P:/.claude/skills/myskill/hooks/PreToolUse_myskill_phase_enforcer.py

import sys
import json
from pathlib import Path

STATE_FILE = Path(".claude/state/myskill_workflow.json")

def read_state() -> dict:
    """Read current workflow state."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"phase": "init", "allowed_tools": ["Skill"]}

def write_state(**updates):
    """Update workflow state."""
    state = read_state()
    state.update(updates)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

def pre_tool_use_handler(tool_input, execution_context):
    """PreToolUse hook for phase enforcement."""
    state = read_state()
    allowed_tools = state.get("allowed_tools", [])

    if tool_input.get("tool_name") not in allowed_tools:
        phase = state.get("phase", "unknown")
        sys.stderr.write(
            f"🔴 BLOCKED: Tool '{tool_input['tool_name']}' not allowed in phase '{phase}'\n"
            f"Allowed tools: {', '.join(allowed_tools)}\n"
        )
        sys.exit(2)  # Block tool use

    return {}

# PostToolUse handler to transition phases
def post_tool_use_handler(tool_input, tool_result, execution_context):
    """Transition phases based on tool completion."""
    state = read_state()

    if state["phase"] == "init" and tool_input.get("tool_name") == "Skill":
        write_state(phase="draft", allowed_tools=["Write"])
    elif state["phase"] == "draft" and tool_input.get("tool_name") == "Write":
        write_state(phase="review", allowed_tools=["Read", "Bash"])

    return {}
```

## Production Examples

From `/agentic-validation`:

| File | Pattern | Purpose |
|------|---------|---------|
| `skill_enforcement_gate.py` | State Transition | Enforce skill execution order |
| `PostToolUse_validator.py` | Validation | Validate output format |

## Integration with /skill-ship

### Phase 4: Optimization

Add self-validation hooks to Phase 4:

```yaml
# Phase 4 workflow_steps:
- phase_4_optimization: |
    Add hooks for mechanical continuation AND validation patterns:
    - Validation Pattern: PostToolUse → Validator → Pass/Fail
    - State Transition: PreToolUse → Block → Transition → Allow
    - Resources: references/agentic-validation-hooks.md
```

### Template Library

Extract hook templates to `resources/`:

| Template | Purpose |
|----------|---------|
| `validation-hook-template.py` | PostToolUse validation scaffold |
| `state-transition-template.py` | PreToolUse/PostToolUse state management |
| `combined-hook-template.py` | Validation + transitions together |

## Benefits

| Benefit | Impact |
|---------|--------|
| **Self-correcting** | Skills catch their own errors |
| **Enforcement** | Cannot skip validation steps |
| **Multi-terminal safe** | State isolation prevents cross-session interference |
| **Debuggable** | Clear error messages for each validation failure |

---

**Source**: `/agentic-validation` skill
**Related**: `references/stophook-generation.md` (mechanical continuation), `references/workflow-phases.md` (Phase 4 Optimization)
