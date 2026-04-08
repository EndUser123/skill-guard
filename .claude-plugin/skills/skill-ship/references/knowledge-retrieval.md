---
type: workflow
load_when: discovery
priority: recommended
estimated_lines: 150
---

# Knowledge Retrieval Guide

Phase 1.5 of the skill-ship workflow systematically queries knowledge sources before building a skill.

## Purpose

Retrieve relevant patterns, lessons, and research from:
- **CKS** (Constitutional Knowledge System) - Project wisdom with FAISS vector search
- **NotebookLM** - Source-grounded research from uploaded documents
- **memory.md** - 70+ topic files with lessons learned, patterns, anti-patterns

## When to Use

**Use Phase 1.5 when**:
- Creating complex skills (>5 steps)
- Improving existing skills
- Domain has prior work/lessons to leverage
- User wants comprehensive pattern analysis

**Skip Phase 1.5 when**:
- Simple skills (<5 steps, straightforward execution)
- User explicitly declines knowledge retrieval
- Domain has no existing CKS/memory entries
- Quick prototyping/experimental work

## Query Patterns

### CKS Query Pattern

```bash
# Search for domain-specific patterns
/cks "hook patterns"          # General hook patterns
/cks "skill optimization"     # Skill-specific patterns
/cks "testing strategies"     # Testing patterns

# Search for pattern types
/cks "anti-pattern"           # Anti-patterns
/cks "lessons learned"        # Lessons from previous work
```

### NotebookLM Query Pattern

```markdown
# Check auth first
/nlm auth status

# List notebooks to find relevant ones
/nlm notebook list

# Query specific notebook
/nlm notebook query <id> "What patterns exist for [domain]?"
/nlm notebook query <id> "Best practices for [skill type]"
```

**Security Note**: Always use the Skill tool (`/nlm`) instead of bash commands. Input validation is handled by the skill itself.

### Memory.md Query Pattern

```markdown
# Always read MEMORY.md first for topic index
Read ~/.claude/projects/P--/memory/MEMORY.md

# Then read specific topic files based on keywords
Read ~/.claude/projects/P--/memory/working_principles.md
Read ~/.claude/projects/P--/memory/skill_optimization_patterns.md
Read ~/.claude/projects/P--/memory/discovery_patterns.md
```

**Cross-Platform Note**: Memory path varies by platform. Use `~/.claude/` for Unix-style or `C:\Users\brsth\.claude\` for Windows-style paths. The Read tool handles both formats.

### GTO Skill Coverage Awareness (Phase 1.5)

When building skills in categories that emit GTO-trackable findings (verification, critique, gap analysis, orchestration), query for GTO skill coverage patterns:

```markdown
# Query CKS for GTO integration patterns
/cks "gto skill coverage"

# Read the GTO skill coverage reference
Read P:/.claude/skills/skill-ship/references/gto-skill-coverage.md

# Query memory for skill coverage / gto integration lessons
Read ~/.claude/projects/P--/memory/gto_self_verifying_implementation.md
```

**When this applies**: Skills that produce durable findings consumed by GTO (verification results, quality reports, gap analyses, orchestration outputs).

**What to retrieve**: The `gto-skill-coverage.md` reference doc contains the complete API — import path, call signature, output location, activation signals, and best-effort wrapper patterns.

## Output Format

Use Template 2 (Executive Summary Format):

```markdown
## Knowledge Retrieval Summary

### CKS Results
[Relevant patterns found in CKS - cite sources with file:line]

### NotebookLM Results
[Relevant research from notebooks - cite notebook IDs]

### Memory.md Results
[Relevant topic files and lessons - cite file names]

### Recommendations
[What patterns/lessons should be incorporated into the skill]
```

## Key Principles

1. **Present as recommendations, not requirements** - The phase identifies patterns/lessons, but doesn't automatically apply them
2. **Cite sources** - Always reference where information came from (file:line, notebook ID, topic file)
3. **Be selective** - Focus on patterns/lessons directly relevant to the skill being built
4. **Respect user choice** - Allow user to skip if they want to proceed without retrieval
