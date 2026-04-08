---
type: quality
load_when: quality
priority: mandatory
estimated_lines: 200
---

# Context Bloat Prevention for SKILL.md

**Reference Document**: Anti-context bloat patterns and detection for SKILL.md optimization

**Purpose**: Prevent SKILL.md files from becoming bloated with embedded documentation, which increases context usage and maintenance burden. This guide implements the "single source of truth" principle from `questioning_patterns.md` Pattern 4.

**Version**: 1.0.0
**Last Updated**: 2026-03-15

---

## Problem Statement

**Context bloat** occurs when SKILL.md files become excessively large (>300 lines) due to:
1. **Embedded documentation**: Detailed examples, patterns, and guides that should reference external files
2. **Duplicate content**: Content that already exists in `memory/` system
3. **Redundant explanations**: Repeating information available in references/

**Impact**:
- Increased context usage during skill execution
- Maintenance burden (Swiss cheese pattern - updating multiple files)
- Platform truncation risk (MEMORY.md limited to 200 lines, similar risks for SKILL.md)
- Reduced skill performance and triggering accuracy

---

## Size Limits and Enforcement

### SKILL.md Size Guidelines

| Size Range | Action | Rationale |
|------------|--------|-----------|
| **0-200 lines** | ✅ Optimal | Target range for most skills |
| **200-300 lines** | ⚠️ Warning | Consider extracting content to references/ |
| **300-500 lines** | ❌ Block | Must extract content before proceeding |
| **500+ lines** | 🚨 Critical | Immediate restructuring required |

### Enforcement in Phase 3 Quality Check

During `/skill-ship` Phase 3 (Quality & Validation):

```python
# Pseudo-code for size validation
skill_lines = count_lines("SKILL.md")

if skill_lines > 500:
    return BLOCK("SKILL.md exceeds 500 lines. Extract content to references/ before proceeding.")
elif skill_lines > 300:
    return WARN(f"SKILL.md is {skill_lines} lines. Extract content to references/ recommended.")
elif skill_lines > 200:
    return INFO(f"SKILL.md is {skill_lines} lines. Consider extraction for optimal performance.")
```

---

## Content Extraction Strategy

### What to Extract

**Extract to references/ when**:
- Content is >20 lines
- Content is explanatory documentation (examples, patterns, guides)
- Content is domain-specific (API conventions, testing patterns)
- Content is reference material (templates, checklists)

**Keep in SKILL.md when**:
- Content is <10 lines
- Content is critical for skill execution (workflow steps, triggers)
- Content defines the skill's structure and purpose
- Content is high-frequency usage (>80% of skill invocations)

### Extraction Pattern

**Before** (bloated SKILL.md):
```markdown
## Story Points Guide

Story points are a relative estimation technique... [50 lines of detailed explanation]

### Fibonacci Validation

Valid story points follow Fibonacci sequence... [30 lines of validation rules]

### Critical Path Analysis

Critical path analysis identifies... [40 lines of methodology]
```

**After** (optimized SKILL.md):
```markdown
## Story Points Guide

See: `references/story-points-guide.md` for complete methodology and examples.

### Fibonacci Validation

See: `C:\Users\brsth\.claude\projects\P--\memory\questioning_patterns.md` Pattern 3.

### Critical Path Analysis

See: `references/critical-path-analysis.md` for implementation details.
```

---

## Duplicate Content Detection

### Memory System Integration

**Check for duplicates** against:
- `C:\Users\brsth\.claude\projects\P--\memory\questioning_patterns.md`
- `C:\Users\brsth\.claude\projects\P--\memory\reasoning_flaws.md`
- `C:\Users\brsth\.claude\projects\P--\memory\working_principles.md`
- Other relevant memory/ files

**Detection Pattern**:
```python
# Check for duplicate content
def check_duplicates(skill_content, memory_files):
    duplicates = []
    for mem_file in memory_files:
        if similar_content(skill_content, mem_file):
            duplicates.append(mem_file)
    return duplicates
```

**Replacement Strategy**:
- Remove duplicate content from SKILL.md
- Add reference: `See: memory/{filename}.md for detailed explanation`

### Example: Questioning Patterns

**Before** (duplicate):
```markdown
## Questioning Patterns

When implementing features, ask:
1. Why this specific value?
2. Are you sure about concurrency?
3. Is this optimal or over-engineering?
```

**After** (reference):
```markdown
## Questioning Patterns

Apply meta-cognitive questioning patterns during implementation.

**See**: `C:\Users\brsth\.claude\projects\P--\memory\questioning_patterns.md` for complete three-question litmus test.
```

---

## Reference Integrity Validation

### Reference Link Format

**Valid reference formats**:
```markdown
See: `references/filename.md` for details
See: `C:\Users\brsth\.claude\projects\P--\memory\filename.md`
See: references/workflow-phases.md#phase-1
```

### Validation Check

During Phase 3 validation:

```python
# Validate all references exist
def validate_references(skill_content):
    references = extract_references(skill_content)
    missing = []
    for ref in references:
        if not file_exists(ref):
            missing.append(ref)
    return missing
```

**Action on missing references**:
- **Block**: If critical reference missing (e.g., workflow-phases.md)
- **Warn**: If optional reference missing
- **Fix**: Create missing reference file or remove link

---

## Progressive Disclosure Enforcement

### SKILL.md Structure

**Optimal structure** (progressive disclosure):
1. **Frontmatter** (lines 1-30): YAML metadata, triggers, aliases
2. **Purpose** (lines 31-50): Brief skill description and when to use
3. **Quick Start** (lines 51-100): Essential workflow steps
4. **References** (lines 101-200): Links to detailed documentation
5. **Templates** (lines 201-250): Output format examples (if applicable)

### Progressive Disclosure Pattern

**Level 1**: SKILL.md (≤200 lines)
- Frontmatter + purpose + quick reference links
- Links to references/ for detailed content

**Level 2**: references/ (unlimited)
- Detailed guides, patterns, examples
- Specific to skill domain

**Level 3**: memory/ system (project-wide)
- Cross-project patterns and principles
- Shared across all skills

---

## Context Optimization Checklist

### Phase 3 Validation Checklist

When running `/skill-ship` Phase 3 quality checks:

- [ ] **Size Check**: SKILL.md ≤300 lines (warn at 200, block at 500)
- [ ] **Duplicate Detection**: No duplicate content with memory/ system
- [ ] **Reference Integrity**: All referenced files exist
- [ ] **Progressive Disclosure**: Content properly structured across levels
- [ ] **Memory Integration**: References to memory/ instead of duplication
- [ ] **Extraction Audit**: Large sections (>20 lines) extracted to references/

---

## Implementation Examples

### Example 1: Plan-Workflow Skill Bloat

**Problem**: plan-workflow SKILL.md bloated to 1200+ lines with embedded examples and patterns.

**Solution**:
1. Extract Story Points Guide → `references/story-points-guide.md`
2. Extract Fibonacci validation → Reference `memory/questioning_patterns.md`
3. Extract Critical Path methodology → `references/critical-path-analysis.md`
4. Keep in SKILL.md: Frontmatter, purpose, workflow phases overview, reference links

**Result**: SKILL.md reduced from 1200+ lines to ~250 lines (80% reduction)

### Example 2: Research Skill Documentation

**Problem**: research skill embedded 200+ lines of provider-specific documentation.

**Solution**:
1. Extract provider docs → `references/provider-specific.md`
2. Extract search strategies → `references/search-strategies.md`
3. Keep in SKILL.md: Core workflow, trigger examples, reference links

**Result**: SKILL.md reduced from 400+ lines to ~180 lines (55% reduction)

---

## Related Documentation

### Memory System
- `C:\Users\brsth\.claude\projects\P--\memory\memory_management.md` - Memory system guide and split criteria
- `C:\Users\brsth\.claude\projects\P--\memory\questioning_patterns.md` - Meta-cognitive questioning patterns (Pattern 4: Swiss cheese maintenance)
- `C:\Users\brsth\.claude\projects\P--\memory\reasoning_flaws.md` - Three technical reasoning flaws to avoid

### Skill Development
- `references/skill-quality-gates.md` - Quality verification systems
- `references/workflow-phases.md` - Detailed phase-by-phase instructions
- `examples/WORKFLOW-EXAMPLES.md` - Complete workflow demonstrations

### Hooks System
- `P:\.claude/hooks\PROTOCOL.md` - Complete hook I/O specifications
- `P:\.claude\hooks\ARCHITECTURE.md` - Constitutional enforcement mapping

---

## Automated Enforcement (Future)

### Proposed Hook: PreToolUse_skill_structure_gate.py

**Purpose**: Automatically validate SKILL.md structure before skill execution

**Checks**:
1. Line count validation (warn >200, block >500)
2. Reference integrity (all referenced files exist)
3. Duplicate content detection (vs memory/ system)
4. Progressive disclosure compliance

**Implementation**:
```python
# Pseudo-code for proposed hook
def pre_tool_use_check(event):
    if event.tool == "Skill" and event.skill_path:
        skill_md = Path(event.skill_path) / "SKILL.md"

        # Size check
        lines = count_lines(skill_md)
        if lines > 500:
            return Block(f"SKILL.md too large: {lines} lines")

        # Reference integrity
        missing = validate_references(skill_md)
        if missing:
            return Warn(f"Missing references: {missing}")

        # Duplicate detection
        duplicates = check_duplicates(skill_md, memory_files)
        if duplicates:
            return Warn(f"Duplicate content found: {duplicates}")
```

---

## Troubleshooting

### SKILL.md Too Large

**Symptoms**:
- Skill triggering < 80%
- Slow skill execution
- Difficulty finding relevant content

**Diagnosis**:
```bash
# Check line count
wc -l SKILL.md

# Find large sections
awk 'BEGIN{section=""} /^##/{section=$0} NF>50{print NF, section}' SKILL.md | sort -rn | head -10
```

**Solution**:
1. Identify sections >20 lines
2. Extract to references/ or reference memory/
3. Replace with reference link
4. Validate references exist

### Missing References

**Symptoms**:
- Phase 3 validation fails
- Reference links broken

**Diagnosis**:
```bash
# Extract all references
grep -oE 'See: `[^`]+`' SKILL.md | while read ref; do
    file=$(echo "$ref" | sed 's/See: `//;s/`//')
    if [ ! -f "$file" ]; then
        echo "Missing: $file"
    fi
done
```

**Solution**:
1. Create missing reference file
2. OR remove broken reference link
3. Re-run Phase 3 validation

---

## Changelog

**2026-03-15**: Initial version created based on context bloat discussion in plan-workflow skill review.
- Established size limits (200/300/500 line thresholds)
- Documented extraction patterns for references/ and memory/ integration
- Added Phase 3 validation checklist for context bloat prevention
- Proposed automated enforcement via PreToolUse_skill_structure_gate.py hook
