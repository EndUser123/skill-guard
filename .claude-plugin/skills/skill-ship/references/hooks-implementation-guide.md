---
name: hooks_operational_guide
description: Quick reference for implementing hooks in Claude Code - syntax, templates, patterns
type: reference
---

# Hooks Operational Guide

Quick reference for implementing hooks in custom commands, subagents, and skills.

## Quick Reference Tables

### Hook Types

| Hook | When It Fires | Use Case | Matcher Input |
|------|---------------|----------|---------------|
| `PreToolUse` | Before tool executes | Block dangerous ops, input validation | Tool name (e.g., "Bash", "Edit") |
| `PostToolUse` | After tool completes | Validate output, check invariants | Tool name (e.g., "Edit\|Write") |
| `Stop` | When agent finishes | Final validation, cleanup, batch checks | None (or agent type for settings.json) |

### Exit Codes

| Exit Code | Behavior | Use For |
|-----------|----------|---------|
| 0 | Success - proceed | Validation passed |
| 2 | Blocking error | stderr fed back to agent, must fix |
| Other | Non-blocking warning | Log but don't block |

### Environment Variables

| Variable | Available In | Description |
|----------|--------------|-------------|
| `$CLAUDE_PROJECT_DIR` | All hooks | Root of current project |
| `$CLAUDE_SKILL_DIR` | Skills only | Directory containing SKILL.md |
| `$CLAUDE_SESSION_ID` | All hooks | Current session ID for logging |
| `$TOOL_INPUT` | All hooks (stdin) | JSON input for hooked tool |

---

## Frontmatter Templates

### Custom Slash Command (`.claude/commands/*.md`)

```yaml
---
model: opus
description: Make modifications or report on csv files
argument-hint: [csv_file] [user_request]
allowed-tools: Glob, Grep, Read, Edit, Write
context: fork
agent: general-purpose
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate-command.sh"
          once: true
  PostToolUse:
    - matcher: "Read|Edit|Write"
      hooks:
        - type: command
          command: "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/validators/csv-validator.py"
  Stop:
    - hooks:
        - type: command
          command: "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/validators/final-check.sh"
---
```

### Subagent (`.claude/agents/*.md`)

```yaml
---
name: csv-edit-agent
description: Make modifications or report on csv files. Use only when directly requested.
tools: Glob, Grep, Read, Edit, Write
disallowedTools: Bash
model: opus
permissionMode: default
skills:
  - csv-conventions
hooks:
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/validators/csv-single-validator.py"
  Stop:
    - hooks:
        - type: command
          command: "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/validators/batch-csv-validator.py"
color: cyan
---
```

### Skill (`.claude/skills/*/SKILL.md`)

```yaml
---
name: csv-validator
description: CSV editing with automatic validation
allowed-tools: Read, Edit, Write, Glob
context: fork
agent: general-purpose
hooks:
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "python $CLAUDE_SKILL_DIR/scripts/validate.py"
disable-model-invocation: false
user-invocable: true
---
```

---

## Hook Input Schema (JSON via stdin)

### Edit/Write Tool Input
```json
{
  "tool": "Edit",
  "tool_input": {
    "file_path": "/path/to/file.csv",
    "old_string": "original content",
    "new_string": "modified content"
  }
}
```

### Read Tool Input
```json
{
  "tool": "Read",
  "tool_input": {
    "file_path": "/path/to/file.csv"
  }
}
```

### Bash Tool Input
```json
{
  "tool": "Bash",
  "tool_input": {
    "command": "echo 'hello'",
    "timeout": 120000
  }
}
```

---

## Validator Script Templates

### CSV Validator (Python)

```python
#!/usr/bin/env python3
"""
CSV single-file validator.
Validates CSV structure after Read/Edit/Write operations.
"""

import json
import sys
import pandas as pd
from pathlib import Path

def validate_csv(file_path: str) -> tuple[bool, str]:
    """Validate CSV file. Returns (is_valid, error_message)."""
    if not file_path or not file_path.endswith(".csv"):
        return True, "Not a CSV file, skipping validation"

    try:
        df = pd.read_csv(file_path)

        # Check required columns
        required_cols = ["date", "description", "amount"]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            return False, f"Missing required columns: {', '.join(missing)}"

        # Check for empty rows
        if df.empty:
            return False, "CSV file is empty"

        # Check data types
        if not pd.api.types.is_numeric_dtype(df.get("amount")):
            return False, "Amount column must be numeric"

        return True, "✓ CSV validation passed"

    except pd.errors.EmptyDataError:
        return False, "CSV file is empty or malformed"
    except Exception as e:
        return False, str(e)

def main():
    # Read hook input from stdin
    input_data = json.loads(sys.stdin.read())
    file_path = input_data.get("tool_input", {}).get("file_path")

    is_valid, message = validate_csv(file_path)

    if not is_valid:
        # Format error for agent correction
        print(f"Resolve this CSV error in {file_path}:", file=sys.stderr)
        print(message, file=sys.stderr)
        sys.exit(2)  # Blocking error

    print(message)
    sys.exit(0)

if __name__ == "__main__":
    main()
```

### HTML Validator (Python)

```python
#!/usr/bin/env python3
"""
HTML validator for generative UI output.
Validates HTML structure and basic syntax.
"""

import json
import sys
from pathlib import Path
from html.parser import HTMLParser
from typing import List

class HTMLValidationParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.errors: List[str] = []
        self.open_tags: List[str] = []

    def handle_starttag(self, tag, attrs):
        # Track opening tags for validation
        if tag not in ['br', 'hr', 'img', 'input', 'meta', 'link']:
            self.open_tags.append(tag)

    def handle_endtag(self, tag):
        # Check for matching close tag
        if tag in self.open_tags:
            last_open = self.open_tags.pop()
            if last_open != tag:
                self.errors.append(f"Mismatched tags: expected </{last_open}>, got </{tag}>")
        elif tag not in ['br', 'hr', 'img', 'input', 'meta', 'link']:
            self.errors.append(f"Closing tag </{tag}> without matching open tag")

def validate_html(file_path: str) -> tuple[bool, str]:
    """Validate HTML file. Returns (is_valid, error_message)."""
    if not file_path or not file_path.endswith(".html"):
        return True, "Not an HTML file, skipping validation"

    try:
        content = Path(file_path).read_text(encoding='utf-8')
        parser = HTMLValidationParser()
        parser.feed(content)

        if parser.open_tags:
            return False, f"Unclosed tags: {', '.join(parser.open_tags)}"

        if parser.errors:
            return False, "; ".join(parser.errors[:5])  # First 5 errors

        return True, "✓ HTML validation passed"

    except Exception as e:
        return False, str(e)

def main():
    input_data = json.loads(sys.stdin.read())
    file_path = input_data.get("tool_input", {}).get("file_path")

    is_valid, message = validate_html(file_path)

    if not is_valid:
        print(f"Resolve this HTML error in {file_path}:", file=sys.stderr)
        print(message, file=sys.stderr)
        sys.exit(2)

    print(message)
    sys.exit(0)

if __name__ == "__main__":
    main()
```

### PreToolUse Command Validator (Bash)

```bash
#!/usr/bin/env bash
# Block destructive database operations

# Read JSON input from stdin
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [ -z "$COMMAND" ]; then
    exit 0
fi

# Block SQL write operations (case-insensitive)
if echo "$COMMAND" | grep -iE '\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)\b' > /dev/null; then
    echo "Blocked: Write operations not allowed. Use SELECT queries only." >&2
    exit 2
fi

exit 0
```

### Stop Hook - Linter Runner (Bash)

```bash
#!/usr/bin/env bash
# Run linters and type checkers on agent completion

set -e

PROJECT_DIR="$1"

echo "Running post-agent validation..."

# Run Python linter
if [ -f "$PROJECT_DIR/pyproject.toml" ]; then
    echo "→ Running ruff linter..."
    cd "$PROJECT_DIR"
    uv run ruff check . || true
    uv run ruff format --check . || true
fi

# Run type checker
if [ -f "$PROJECT_DIR/pyproject.toml" ]; then
    echo "→ Running mypy type checker..."
    cd "$PROJECT_DIR"
    uv run mypy . || true
fi

echo "✓ Post-agent validation complete"
exit 0
```

---

## Common Validator Patterns

### Pattern 1: Single-File Validation (PostToolUse)

**Use when**: Validate output immediately after each file operation

```yaml
PostToolUse:
  - matcher: "Edit|Write"
    hooks:
      - type: command
        command: "validator.py"
```

**Validators**: CSV, HTML, JSON, YAML, XML

### Pattern 2: Batch Validation (Stop)

**Use when**: Validate all files at agent completion

```yaml
Stop:
  - hooks:
      - type: command
        command: "batch-validator.sh $CLAUDE_PROJECT_DIR"
```

**Validators**: Linters, type checkers, test suites, security scans

### Pattern 3: Input Filtering (PreToolUse)

**Use when**: Block dangerous operations before execution

```yaml
PreToolUse:
  - matcher: "Bash"
    hooks:
      - type: command
        command: "block-destructive.sh"
```

**Validators**: Command allowlists, SQL write blockers, path restrictions

### Pattern 4: Multi-Validation (Stop)

**Use when**: Run multiple validators at completion

```yaml
Stop:
  - hooks:
      - type: command
        command: "run-linter.sh"
      - type: command
        command: "run-type-checker.sh"
      - type: command
        command: "run-tests.sh"
```

---

## Matcher Syntax

### Single Tool
```yaml
matcher: "Edit"
```

### Multiple Tools (OR)
```yaml
matcher: "Edit|Write|Read"
```

### All Tools
```yaml
matcher: ".*"  # Or omit matcher field
```

### Negation (match all EXCEPT)
```yaml
# Not directly supported - use disallowedTools in frontmatter instead
```

---

## Troubleshooting

### Hook Not Running

1. **Check frontmatter syntax**: YAML must be valid, indentation matters
2. **Verify hook path**:
   - **Skill-based hooks**: Use relative paths (`../skills/<name>/hooks/`) NOT absolute paths
   - **Command/Agent hooks**: Use `$CLAUDE_PROJECT_DIR` or absolute paths
   - See: `memory/skill_hooks_path_resolution.md` for detailed explanation
3. **Check matcher**: Tool names are case-sensitive (e.g., "Edit" not "edit")
4. **Make script executable**: `chmod +x .claude/hooks/validators/script.sh`
5. **Test manually**: Run the validator script directly with test input

### Exit Code Not Blocking

1. **Use exit code 2**: Only code 2 blocks execution with stderr feedback
2. **Print to stderr**: Error messages must go to `stderr` (`>&2` in bash, `file=sys.stderr` in Python)
3. **Format for agent**: Start with "Resolve this X error in Y:" pattern

### Validator Receiving Wrong Input

1. **Check stdin parsing**: Hook input comes via stdin as JSON
2. **Extract correct field**: Use `tool_input.file_path` for file operations
3. **Handle missing fields**: Some tools may not have expected fields

### Performance Issues

1. **Use `once: true`**: Run hook only once per agent session
2. **Optimize validator**: Cache results, skip unnecessary checks
3. **Batch validation**: Use Stop hook instead of PostToolUse for many files

### Debugging Tips

```python
# Add logging to troubleshoot
import sys
logging.basicConfig(filename='/tmp/hook-debug.log', level=logging.DEBUG)

# Log received input
input_data = json.loads(sys.stdin.read())
logging.debug(f"Received input: {input_data}")

# Log validation steps
logging.debug(f"Validating file: {file_path}")
```

---

## Testing Your Hooks

### Unit Test Hook Script

```python
import subprocess
import json

def test_csv_validator():
    # Simulate hook input
    hook_input = {
        "tool": "Edit",
        "tool_input": {
            "file_path": "test.csv",
            "old_string": "old",
            "new_string": "new"
        }
    }

    # Run validator with simulated input
    result = subprocess.run(
        ["python", ".claude/hooks/validators/csv-validator.py"],
        input=json.dumps(hook_input),
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"Validator failed: {result.stderr}"

def test_csv_validator_blocks_invalid():
    hook_input = {
        "tool": "Edit",
        "tool_input": {
            "file_path": "invalid.csv",  # File with missing columns
            "old_string": "old",
            "new_string": "new"
        }
    }

    result = subprocess.run(
        ["python", ".claude/hooks/validators/csv-validator.py"],
        input=json.dumps(hook_input),
        capture_output=True,
        text=True
    )

    assert result.returncode == 2, "Should block invalid CSV"
    assert "Resolve this CSV error" in result.stderr
```

---

## Quick Implementation Checklist

- [ ] Create `.claude/hooks/validators/` directory
- [ ] Write validator script with stdin JSON parsing
- [ ] Make script executable (`chmod +x`)
- [ ] Add hooks section to frontmatter
- [ ] Use correct matcher for tool type
- [ ] Use exit code 2 for blocking errors
- [ ] Print errors to stderr with "Resolve this..." pattern
- [ ] Test validator manually with sample input
- [ ] Test in context with actual agent/skill
- [ ] Add logging for debugging
- [ ] Document validator purpose in comments

---

## Related Memory Files

- `memory/hooks_conceptual_guide.md` - Philosophy and patterns
- `memory/hook_architecture.md` - Hook system design
- `memory/integration_verification.md` - Testing hooks in context
- `memory/skill_hooks_path_resolution.md` - Skill-based hook path resolution lesson
- `memory/hook_debugging_lessons.md` - Hook debugging investigation scope and lessons
