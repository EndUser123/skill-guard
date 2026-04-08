---
type: quality
load_when: quality
priority: mandatory
estimated_lines: 450
---

# Skill Anti-Patterns Catalog

Comprehensive collection of anti-patterns to avoid when creating or modifying Claude Code skills. Organized by severity and category.

---

## Severity Legend

| Severity | Meaning | Impact |
|----------|---------|--------|
| 🔴 **CRITICAL** | Blocks skill execution or causes runtime errors | Skill won't load or function |
| ⚠️ **WARNING** | Degrades experience but functional | Suboptimal triggering or behavior |
| ℹ️ **INFO** | Style/best practice suggestion | Works but could be better |

---

## Frontmatter Critical (🔴)

### Missing YAML delimiters
**Pattern:** SKILL.md without `---` delimiters around frontmatter
```markdown
# Wrong:
name: my-skill
description: My skill

# Correct:
---
name: my-skill
description: My skill
---
```

**Impact:** Skill won't load - YAML parser can't identify frontmatter

---

### Missing required fields
**Pattern:** SKILL.md without `name` or `description` fields
```yaml
# Wrong:
---
name: my-skill
# Missing description

# Correct:
---
name: my-skill
description: My skill description
---
```

**Impact:** Skill won't load - missing required metadata

---

### `description` contains angle brackets
**Pattern:** Description includes `<` or `>` characters
```yaml
# Wrong:
description: Use for <HTML> and <CSS> tasks

# Correct:
description: Use for HTML and CSS tasks
```

**Impact:** Anthropic's validator rejects descriptions with angle brackets

---

### `name` doesn't match directory name
**Pattern:** SKILL.md name doesn't match folder name
```
# Wrong:
Directory: skills/my-cool-skill/
SKILL.md name: my_skill

# Correct:
Directory: skills/my-skill/
SKILL.md name: my-skill
```

**Impact:** May cause registration or lookup issues

---

### `description` uses YAML block scalar (`|`)
**Pattern:** Description uses literal block scalar with `|`
```yaml
# Wrong:
description: |
  This is a multi-line
  description using block scalar

# Correct:
description: This is a single-line description using inline string
```

**Impact:** Known to fail with blank lines in Claude Desktop's strictyaml parser

---

## Trigger Warnings (⚠️)

### Second person ("Use this when you want...")
**Pattern:** Description uses second-person address
```yaml
# Wrong:
description: Use this when you want to create dashboards

# Correct:
description: MUST BE USED when the user asks to "create a dashboard"
```

**Impact:** May trigger incorrectly - should use third person

---

### Vague triggers ("helps with X", "data processing tool")
**Pattern:** Generic description that could apply to many skills
```yaml
# Wrong:
description: This skill helps with data processing

# Correct:
description: MUST BE USED when the user asks to "parse JSON files", "extract data from CSV", or mentions JSON parsing, CSV data extraction, or file-based data processing
```

**Impact:** Poor triggering - lost in similar skills

---

### Overly specific triggers (lists exact queries)
**Pattern:** Description lists every possible query verbatim
```yaml
# Wrong:
description: Use for "create skill", "build skill", "write skill", "make skill", "design skill", "develop skill"...

# Correct:
description: MUST BE USED when the user asks to "create a skill", "build a skill", or mentions skill creation, skill development, or building new skills from scratch
```

**Impact:** Bloats description, may hit token limits, doesn't generalize

---

### Description lists tool names instead of user intent
**Pattern:** Description focuses on implementation (tools used) not goals
```yaml
# Wrong:
description: This skill uses pypdf, pdfplumber, and regex to process PDF files

# Correct:
description: MUST BE USED when the user asks to "extract data from PDF forms", "fill PDF forms automatically", or mentions PDF form processing, automated form filling, or structured PDF data extraction
```

**Impact:** Users don't care about tools; they care about what they can accomplish

---

### Description exceeds 1024 characters
**Pattern:** Description is too long
```yaml
# Wrong:
description: [800+ characters of detailed explanation...]

# Correct:
description: Concise description under 1024 chars focusing on trigger phrases and user intent
```

**Impact:** May be truncated, violates spec limit

---

## Description Warnings (⚠️)

### Missing trigger phrases
**Pattern:** Description doesn't include specific phrases users would say
```yaml
# Weak:
description: A tool for working with web APIs

# Better:
description: MUST BE USED when the user asks to "call an API", "make HTTP requests", "fetch from a URL", or mentions API calls, HTTP requests, web API integration, or fetching data from endpoints
```

**Impact:** Misses triggering opportunities

---

### No "pushy" language for under-triggering
**Pattern:** Passive description when skill should be proactive
```yaml
# Too passive:
description: Create dashboards for data visualization

# Better (pushy):
description: MUST BE USED when the user asks to "create a dashboard". Make sure to use this skill whenever the user mentions dashboards, data visualization, or wants to display any kind of data visually, even if they don't explicitly ask for a "dashboard."
```

**Impact:** Under-triggering in situations where skill would be useful

---

## Content Info (ℹ️)

### SKILL.md > 500 lines
**Pattern:** Main SKILL.md file is too long
```markdown
# Better structure:
SKILL.md (core concepts, <300 lines)
references/ (detailed docs)
examples/ (working code)
scripts/ (utilities)
```

**Impact:** Context bloat, harder to maintain

---

### Duplicate content across SKILL.md and memory/
**Pattern:** Same content in skill file and memory system
```markdown
# Instead of duplicating:
SKILL.md: [full tutorial]
memory/tutorial.md: [same tutorial]

# Reference from SKILL.md:
See: memory/tutorial.md for complete tutorial
```

**Impact:** Context bloat, maintenance burden (update in two places)

---

### Missing examples in SKILL.md
**Pattern:** SKILL.md has instructions but no examples
```markdown
# Better:
## Usage

Example:
Input: "create a skill for JSON parsing"

Output: [expected result]
```

**Impact:** Users uncertain how to use skill

---

### Scripts are not executable
**Pattern:** Helper scripts in scripts/ without execute permission
```bash
# After creation:
chmod +x scripts/helper.py
```

**Impact:** Scripts can't be executed directly

---

## Hook Quality (⚠️)

### PROCEDURE skill uses global hooks instead of embedded enforcement
**Pattern:** PROCEDURE-type skill defines global hooks when it should use embedded workflow steps
```yaml
# Wrong for PROCEDURE:
hooks:
  PreToolUse: my-procedure-hook.py

# Correct for PROCEDURE:
workflow_steps:
  - step_1: Do X
  - step_2: Do Y
```

**Impact:** Architectural mismatch - see references/procedure-type-skills-embedded-enforcement.md

---

### Hook lacks idempotency
**Pattern:** Hook produces different outputs on repeated invocations
```python
# Wrong - accumulates state:
results.append(data)

# Correct - idempotent:
return process(data)  # Pure function
```

**Impact:** Unpredictable behavior in multi-terminal environments

---

### Hook stderr treated as error
**Pattern:** Hook writes to stderr for informational messages
```python
# Wrong:
print(f"Processing {file}", file=sys.stderr)  # Shows as error

# Correct:
print(f"Processing {file}")  # stdout is fine for info
```

**Impact:** False error detections, noisy logs

---

## Reference Integrity (⚠️)

### Referenced file doesn't exist
**Pattern:** SKILL.md references non-existent file
```markdown
# Verify first that references/guide.md exists before:
See: references/guide.md for details
```

**Impact:** Broken link, user can't access documentation

---

### Relative path ambiguity
**Pattern:** Reference uses `../` or assumes working directory
```markdown
# Wrong:
See: ../other-skill/SKILL.md

# Correct (skill-root relative):
See: references/workflow-phases.md
```

**Impact:** Links break when skill is moved or installed differently

---

## Testing Anti-Patterns (⚠️)

### Tests mock instead of integration
**Pattern:** Unit tests mock external dependencies instead of testing integration
```python
# May miss real issues:
def test_parse_pdf():
    pdf = MockPDF()
    result = parse(pdf)  # Doesn't test real PDF parsing

# Better - use real files:
def test_parse_pdf():
    with open("tests/fixtures/sample.pdf") as pdf:
        result = parse(pdf)  # Tests real behavior
```

**Impact:** Tests pass but integration fails

---

### Tests don't verify completion evidence
**Pattern:** Tests check return values but not actual completion
```python
# Incomplete:
def test_skill():
    result = skill.process(input)
    assert result is not None

# Better - verify actual completion:
def test_skill():
    result = skill.process(input)
    assert result.status == "COMPLETE"
    assert result.evidence["files_created"] > 0
```

**Impact:** False positives - tests pass but work not done

---

## Frontmatter Optional Fields (ℹ️)

### Using unsupported top-level keys
**Pattern:** Frontmatter includes keys not in spec
```yaml
# Wrong (spec violation):
---
version: 1.0
author: Me
category: utilities
---
```

**Impact:** May be rejected, should move to `metadata` field

---

### Nested `metadata` objects
**Pattern:** `metadata` contains nested objects or arrays
```yaml
# Wrong:
metadata:
  config:
    setting: value  # Nested object

# Correct (flatten):
metadata:
  config-setting: value  # Flattened key
```

**Impact:** Spec violation, may not parse correctly

---

## Checklist for Anti-Pattern Prevention

Before committing a skill, verify:

- [ ] Frontmatter has `---` delimiters
- [ ] `name` and `description` present
- [ ] `name` matches directory name
- [ ] Description < 1024 characters, no `<` or `>`
- [ ] No `|` block scalar in description
- [ ] Description uses third person, not second
- [ ] Description includes specific trigger phrases
- [ ] SKILL.md < 500 lines (move excess to references/)
- [ ] No duplicate content with memory/ system
- [ ] All referenced files exist
- [ ] Scripts have execute permissions
- [ ] PROCEDURE skills use workflow_steps, not global hooks
- [ ] Tests use real data, not just mocks
- [ ] Tests verify completion evidence, not just return values

---

**See Also:**
- `references/context-bloat-prevention.md` - Context bloat patterns
- `references/skill-quality-gates.md` - Quality verification systems
- `description-optimization-guide.md` - Complete description optimization guide
