# Skill-Based Hooks System

**Last Updated**: 2026-03-09

## Overview

The Claude Code hooks system includes comprehensive **skill-based enforcement** that ensures skills are executed correctly and not bypassed or substituted with generic analysis.

## Key Components

### 1. Skill Enforcement System

**Location**: `P:/.claude/hooks/docs/skill_enforcement.md`

**Purpose**: Forces Claude to use the `Skill()` tool before executing slash commands, preventing:
- Direct Bash/Edit execution bypassing skill instructions
- Investigation/searching behavior instead of execution
- Skill output simulation via `python -c`

**Architecture**:
```
UserPromptSubmit Router (priority 1) → Injects skill directive
PreToolUse Gate (fallback) → Blocks Bash/Edit/Write until Skill used
PostToolUse Handler → Clears state OR allows Bash for execution skills
```

**State Machine**: IDLE → PENDING (Bash/Edit blocked) → READ (Bash allowed for execution skills) → IDLE

**Injection Message**:
```
🔴 CRITICAL TOOL CONSTRAINT 🔴
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⛔ BLOCKED until Skill tool used:
   - Bash, Edit, Write, Task, Grep, WebSearch

✓ After Skill is read, follow its instructions.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 2. Skill Pattern Gate

**Location**: `P:/.claude/hooks/PreToolUse/PreToolUse_skill_pattern_gate.py`

**Purpose**: Primary defense against skill substitution - validates skill execution patterns BEFORE allowing tools.

**Features**:
- **Parallel validation**: Regex pattern matching + semantic similarity via embedding model
- **First-tool coherence** (v3.5): Skills can declare `allowed_first_tools` in SKILL.md frontmatter
- **Auto-discovery**: Automatically discovers all skills from `.claude/skills/*/SKILL.md`

**Skill Execution Registry Examples**:
```python
"rca": {
    "tools": ["Bash", "Task"],
    "pattern": r"src\.rca|SimpleRCAEngine|RCAEngine",
    "hint": "Use /rca via src.rca imports",
    "intent_enabled": True,
},
"test": {
    "tools": ["Bash", "Task"],
    "pattern": r"pytest|python\s+-m\s+pytest",
    "hint": "Run /test via actual test execution - do not provide prose analysis",
    "intent_enabled": False,
}
```

### 3. Auto-Discovery System

**Location**: `P:/.claude/hooks/skill_auto_discovery.py`

**Purpose**: Automatically discovers ALL skills without manual registration.

**Configuration Sources** (priority order):
1. Explicit `SKILL_EXECUTION_REGISTRY` (backwards compatibility)
2. Frontmatter `allowed_first_tools` field
3. Script detection from `scripts/` directory
4. Default tools based on category

**Discovery**: Scans `.claude/skills/*/SKILL.md` for frontmatter metadata

**Benefits**:
- ✅ Zero maintenance - new skills automatically enforced
- ✅ Backwards compatible - explicit registry still works
- ✅ Scalable - supports 184+ skills
- ✅ Developer friendly - declare metadata in SKILL.md

## Skill Classification

### Knowledge Skills (default)

**Characteristics**:
- Provide consultation, analysis, documentation
- Don't execute code or run commands
- Examples: `/pre-mortem`, `/reflect`, `/ask`, `/s`, `/analyze`, `/discover`
- **State**: No state file written
- **Required**: No declaration needed (default behavior)

**Example Frontmatter**:
```yaml
---
name: pre-mortem
category: knowledge
---
```

### Execution Skills

**Characteristics**:
- Run commands, execute code, perform operations
- Require specific tool patterns
- Examples: `/rca`, `/build`, `/test`, `/research`
- **State**: State file written
- **Required**: Must declare in registry or frontmatter

**Example Frontmatter**:
```yaml
---
name: rca
category: development
allowed_first_tools: ["Bash", "Task"]
execution: |
  1. Import src.rca modules
  2. Run RCA engine
  3. Generate analysis
---
```

## How to Use Skill-Based Hooks

### For Skill Development

When creating or improving skills, you can configure execution behavior:

**Option 1: Frontmatter Declaration** (Recommended)
```yaml
---
name: your-skill
category: development
allowed_first_tools: ["Bash", "Task"]
execution_tools: ["Bash", "Task"]
execution_pattern: "your_pattern_here"
execution_hint: "Use /your-skill via ..."
execution_intent_enabled: false
---
```

**Option 2: SKILL_EXECUTION_REGISTRY** (Preferred for Hooks)
```python
SKILL_EXECUTION_REGISTRY = {
    "your-skill-name": {
        "tools": ["Bash", "Task"],
        "pattern": r"your_pattern_here",
        "hint": "Use /your-skill via ...",
        "intent_enabled": False,
    },
}
```

**Option 3: Auto-Discovery** (Automatic)
- Add `scripts/your-script.py` to skill directory
- Auto-discovery will detect script and create pattern matching
- Or just add SKILL.md - auto-discovery handles the rest

### For Skill Invocation

When using skills:
1. **Always call `Skill()` tool first** - system blocks tools until skill is loaded
2. **Follow skill instructions** - don't substitute your own analysis
3. **Use declared tools** - respect `allowed_first_tools` and execution patterns
4. **Check state files** - for execution skills, state is tracked per session

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `SKILL_PATTERN_ENFORCEMENT_ENABLED` | `"true"` | Enable/disable skill pattern gate |
| `SKILL_INTENT_DAEMON_ENABLED` | `"true"` | Enable daemon semantic validation |
| `FIRST_TOOL_COHERENCE_ENABLED` | `"true"` | Enable first-tool coherence checks |
| `SKILL_ENFORCEMENT_ENABLED` | `"true"` | Master enable/disable for skill enforcement |
| `SKILL_ENFORCEMENT_DEBUG` | `"0"` | Verbose stderr logging |

## Investigation Tools

Tools that are ALWAYS allowed (for understanding the problem):
```python
INVESTIGATION_TOOLS = {
    "Read", "Grep", "Glob", "AskUserQuestion", "Skill",
    # Analysis tools (for planning, not execution)
    "WebSearch", "WebFetch", "mcp__4_5v_mcp__analyze_image",
    "mcp__web_reader__webReader",
}
```

## Monitoring and Debugging

### Health Check
```bash
python P:/.claude/hooks/check_skill_enforcement.py
```

### View Logs
```bash
# Skill enforcement logs
tail -20 P:/.claude/logs/skill_enforcement.jsonl

# Skill execution gate logs
tail -20 P:/.claude/logs/skill_execution_gate.jsonl

# First-tool coherence logs
tail -20 P:/.claude/logs/first_tool_coherence.jsonl
```

### Enable Debug Logging
```bash
export SKILL_ENFORCEMENT_DEBUG=1
```

## Key Documentation Files

- `P:/.claude/hooks/docs/skill_enforcement.md` - System overview
- `P:/.claude/hooks/SKILL_AUTHORS_GUIDE.md` - Author guide
- `P:/.claude/hooks/SKILL_AUTO_DISCOVERY_SUMMARY.md` - Implementation summary
- `P:/.claude/hooks/SKILL_PATTERN_GATE_ARCHITECTURAL_FIX.md` - Fix documentation
- `P:/.claude/hooks/PreToolUse/PreToolUse_skill_pattern_gate.py` - Main enforcement hook
- `P:/.claude/hooks/skill_auto_discovery.py` - Auto-discovery module

## Common Patterns

### CLI Skills (python -m module)
```python
"my-cli": {
    "tools": ["Bash", "Task"],
    "pattern": r"python(\.exe)?\s+(-m\s+)?my_cli\.py|my_cli",
    "hint": "Use /my-cli via python -m my_cli or python my_cli.py",
    "intent_enabled": False,
}
```

### Python Import Skills
```python
"rca": {
    "tools": ["Bash", "Task"],
    "pattern": r"src\.rca|SimpleRCAEngine|RCAEngine",
    "hint": "Use /rca via src.rca imports",
    "intent_enabled": True,
}
```

### Knowledge Skills with First-Tool Coherence
```yaml
---
allowed_first_tools: ["Grep", "Glob", "Read", "Task", "WebSearch"]
---
```

This ensures the first non-investigation tool matches the skill's intent.

## Troubleshooting

### "My skill is being blocked"
**Check**:
1. Is skill in `SKILL_EXECUTION_REGISTRY`?
2. Does `tools` field exist and is not empty?
3. Does `pattern` match actual command syntax?

**Fix**: Add proper registry entry or frontmatter declaration

### "Users bypass the hook for my skill"
**Check**:
1. Is pattern too restrictive (blocks legitimate usage)?
2. Is hint message unclear?
3. Review block logs at `P:/.claude/logs/skill_execution_gate.jsonl`

**Fix**: Relax pattern or improve hint message

### "Warning: Skill X has empty required_tools"
**Diagnosis**: Skill is in `SKILL_EXECUTION_REGISTRY` but has empty `tools` field

**Fix**: Add `tools` field to registry entry OR remove from registry if it's a knowledge skill

## Best Practices

1. **Always call Skill() first** - system enforces this
2. **Respect skill instructions** - don't substitute your own analysis
3. **Use declared tools** - follow `allowed_first_tools` patterns
4. **Declare execution requirements** - in frontmatter or registry
5. **Test with debug enabled** - use `SKILL_ENFORCEMENT_DEBUG=1`
6. **Monitor logs regularly** - check for high block rates or bypasses

## Skill Hook Path Resolution

**Critical**: When defining hooks in SKILL.md, always use **relative paths**, not absolute paths.

### Why

The Claude Code harness executes skill-based hooks from `P:\.claude\hooks\` directory. Absolute paths in SKILL.md get transformed incorrectly, causing path duplication errors.

### Wrong (absolute path)
```yaml
hooks:
  Stop:
    - matcher: "gto"      # WRONG: matcher is silently ignored for Stop events
      hooks:
        - type: command
          command: "python P:/.claude/skills/gto/hooks/gto_verify_wrapper.py"
```
Result: `hooks/hooks/gto_verify_wrapper.py` (path duplication)

### Correct (relative path with once)
```yaml
hooks:
  Stop:
    - once: true          # Ensures hook fires only once per session
      hooks:
        - type: command
          command: "python ../skills/gto/hooks/gto_verify_wrapper.py"
```
Result: Correctly resolves from `P:\.claude\hooks\` to `P:\.claude\skills\gto\hooks\`

**Note**: Stop events do not support matchers — they always fire on every occurrence.
Use `once: true` to ensure the hook runs only once per skill session.

### Skill Hook Caching

Changes to SKILL.md hooks don't take effect until:
- Session restart/compaction, OR
- Skill hooks are reloaded by harness

**Verification**: Test wrapper from hooks directory:
```bash
cd "P:\.claude\hooks" && python ../skills/<your-skill>/hooks/<your-script>.py
```

## Related Memory Files

- `memory/hook_architecture.md` - General hook patterns and enforcement model
- `memory/hooks_conceptual_guide.md` - Philosophy and architecture of specialized self-validating agents with hooks
- `memory/hooks_operational_guide.md` - Quick reference for implementing hooks in Claude Code
- `memory/skill_hooks_path_resolution.md` - Skill-based hook path resolution lesson
- `memory/integration_verification.md` - Skill and hook integration verification patterns
