---
name: hooks_conceptual_guide
description: Philosophy and architecture of specialized self-validating agents with hooks
type: reference
---

# Hooks Conceptual Guide

Philosophy, architecture patterns, and design principles for specialized self-validating agents.

---

## The Big Idea

### Core Principle

**Specialized self-validation = Trusted automation**

```
Focused Agent + Specialized Validation = Trust
```

If you want agents to accomplish valuable work autonomously, they must be able to **validate their own work**. Validation increases trust, and trust saves your most valuable engineering resource: **time**.

### Why This Matters

Before specialized hooks, validation was global (in `settings.json`). Now you can define hooks that run **only for specific agents**, enabling:

- **CSV agents** that validate CSV structure after every file operation
- **Build agents** that run linters and type checkers on completion
- **UI agents** that validate HTML output
- **Database agents** that block write operations

This creates **deterministic layers** within agentic workflows—guaranteed validation that runs every time, without relying on the model to remember to validate.

---

## Philosophy: Specialization Beats Generalization

### The Trap of General-Purpose Agents

A general agent doing everything:
- ✗ Works sometimes, fails unpredictably
- ✗ No consistent validation strategy
- ✗ Hard to trust for critical operations
- ✗ Difficult to debug when things go wrong

### The Power of Specialized Agents

A focused agent with one purpose:
- ✓ Consistent, reliable, trustworthy
- ✓ Targeted validation for its specific domain
- ✓ Clear failure modes and recovery patterns
- ✓ Easier to reason about and debug

**Key insight**: A focused agent with one purpose **outperforms** an unfocused agent with many purposes—not just at the task, but at reliability and trustworthiness.

---

## Architecture Patterns

### Pattern 1: Agent per Operation Type

**Context**: Multi-agent pipeline with distinct stages

**Example**: Finance review pipeline
```
/review-finances
    │
    ├─> normalize-csv-agent (validates CSV + balance)
    ├─> categorize-csv-agent (validates CSV)
    ├─> merge-accounts-agent (validates merged output)
    ├─> graph-agent (validates PNG generation)
    └─> generative-ui-agent (validates HTML)
```

**Why this works**:
- Each agent has one job
- Validation is hyper-focused on that job's output
- Failures are isolated and clear
- Parallel execution is safe (each validates independently)

**When to use**:
- Multi-step workflows
- Different validation requirements per stage
- Need parallelization

### Pattern 2: Single Agent with Multiple Hooks

**Context**: One agent that needs validation at different lifecycle points

**Example**: Build agent
```yaml
# .claude/agents/build-agent.md
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "validate-build-command.sh"
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "quick-syntax-check.sh"
  Stop:
    - hooks:
        - type: command
          command: "run-full-test-suite.sh"
```

**Why this works**:
- Input validation (PreToolUse) prevents bad commands
- Incremental validation (PostToolUse) catches errors early
- Final validation (Stop) ensures overall quality

**When to use**:
- Agent performs related operations with different validation needs
- Want layered validation (lightweight during work, thorough at end)
- Single agent context is sufficient

### Pattern 3: Orchestrator with Specialized Sub-Agents

**Context**: Complex workflow needing coordination

**Example**: `/review-finances` orchestrator
```markdown
## Workflow

1. Use normalize-csv-agent to standardize formats
2. Use categorize-csv-agent to auto-categorize transactions
3. Use merge-accounts-agent to combine all accounts
4. Use graph-agent to generate visualizations
5. Use generative-ui-agent to create dashboard
```

**Why this works**:
- Orchestrator doesn't need to know validation details
- Each sub-agent validates its own work
- Clear separation of concerns
- Easy to modify individual stages

**When to use**:
- Complex multi-stage workflows
- Different teams/people maintain different stages
- Want composable, reusable agents

---

## Design Principles

### 1. One Agent, One Purpose

Every agent should do **one thing extraordinarily well**.

**Bad**: A "data-processing agent" that:
- Normalizes CSV files
- Categorizes transactions
- Merges accounts
- Generates graphs
- Creates HTML dashboards

**Good**: Five specialized agents:
- `normalize-csv-agent`: Converts formats, validates CSV structure
- `categorize-csv-agent`: Adds categories, validates CSV + category schema
- `merge-accounts-agent`: Combines files, validates merge integrity
- `graph-agent`: Generates plots, validates PNG output
- `generative-ui-agent`: Creates HTML, validates markup

**Why**: Each agent can be validated, tested, and debugged independently.

### 2. Validate at the Right Granularity

**PostToolUse** (per-operation):
- Use for: Format validation, syntax checking, invariant verification
- Example: After Edit/Write, check CSV structure
- Benefit: Catch errors immediately, clear feedback loop

**Stop** (completion):
- Use for: Cross-file validation, integration checks, quality gates
- Example: Run linter after all edits complete
- Benefit: Avoid redundant checks, comprehensive validation

**PreToolUse** (before operation):
- Use for: Input filtering, security checks, permission enforcement
- Example: Block destructive SQL commands
- Benefit: Prevent invalid operations, guardrails

### 3. Make Errors Actionable

When a validator fails, it should tell the agent **exactly what to fix**.

**Bad error message**:
```python
print("CSV validation failed", file=sys.stderr)
```

**Good error message**:
```python
print(f"Resolve this CSV error in {file_path}:", file=sys.stderr)
print(f"Missing required columns: {', '.join(missing)}", file=sys.stderr)
print(f"Add these columns to the CSV header row", file=sys.stderr)
```

**Pattern**: `[Action verb] this [error type] in [location]: [specific problem]`

### 4. Log Everything

Observability is critical for debugging and trust.

**Every validator should**:
- Log what it's checking
- Log validation results (pass/fail)
- Log time taken
- Log any anomalies detected

```python
import logging
logging.basicConfig(f'.claude/hooks/logs/{validator_name}.log')

def validate_csv(file_path):
    logging.info(f"Validating CSV: {file_path}")
    # ... validation logic ...
    logging.info(f"Validation result: {'PASS' if is_valid else 'FAIL'}")
    return is_valid
```

**Why**: When something goes wrong, you need to know:
- What validator ran?
- What did it check?
- What did it find?
- How long did it take?

### 5. Design for Recovery

Validators shouldn't just detect problems—they should enable recovery.

**Recovery patterns**:

1. **Self-correction loop**: Agent fixes error, re-validates, repeats
   ```
   Agent edits file → Validator fails → Agent fixes → Validator passes
   ```

2. **Incremental validation**: Check after each operation, not just at end
   ```
   Edit file 1 → Validate → Edit file 2 → Validate → ...
   ```

3. **Diagnostic hints**: Validator suggests what might be wrong
   ```
   "Balance mismatch: Expected $1100, got $1000. Check row 5 calculation."
   ```

---

## When to Use Hooks (vs Other Approaches)

### Use Hooks When:

✓ **Validation must be deterministic**
- Format requirements (CSV, HTML, JSON)
- Security constraints (SQL read-only)
- Business rules (balance calculations)

✓ **Validation is specific to agent/skill**
- CSV agent validates CSVs
- Build agent runs linters
- UI agent validates HTML

✓ **Validation should run every time**
- Can't rely on model to remember
- Must enforce invariants
- Quality gate is critical

✓ **Fast validation is acceptable**
- Sub-second validation
- Doesn't require complex reasoning
- Deterministic check

### Use Other Approaches When:

✗ **Validation requires complex reasoning**
- Need model's understanding (e.g., "is this code well-structured?")
- Context-dependent judgment
- Nuanced decision-making

✗ **Validation is expensive**
- Running full test suite after every edit
- Heavy computation
- External API calls

✗ **Validation is global/generic**
- Applies to all agents equally
- Not specific to agent's purpose
- Better in `settings.json`

---

## Anti-Patterns

### Anti-Pattern 1: Generalist Agent with Global Hooks

**Bad**:
```yaml
# settings.json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Edit|Write",
      "hooks": [{
        "command": "validate-everything.sh"
      }]
    }]
  }
}
```

**Problem**: One validator tries to handle all file types, all contexts.

**Better**: Specialized agents with specialized hooks:
- CSV agent with CSV validator
- HTML agent with HTML validator
- Build agent with linter hooks

### Anti-Pattern 2: Validation by Prompt Only

**Bad**:
```markdown
You are a CSV editor. Always validate your work to ensure CSV structure is correct.
```

**Problem**: Relies on model to remember and execute validation.

**Better**: PostToolUse hook that **always** runs validation:
```yaml
hooks:
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "validate-csv.py"
```

### Anti-Pattern 3: Over-V

**Bad**:
```yaml
hooks:
  PostToolUse:
    - matcher: "Read"
      hooks:
        - type: command
          command: "validate-csv.py"  # Validates on every Read
```

**Problem**: Unnecessary validation on read-only operations.

**Better**: Validate on write operations only:
```yaml
hooks:
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "validate-csv.py"
```

---

## Building Your Own Specialized Validators

### Step 1: Identify What Needs Validating

**Questions to ask**:
1. What is this agent's single purpose?
2. What could go wrong?
3. What would "correct" output look like?
4. How can I detect incorrect output?

**Examples**:
- CSV agent: Malformed CSV, missing columns, type mismatches
- HTML agent: Broken tags, unclosed elements, invalid structure
- Build agent: Lint errors, type errors, test failures

### Step 2: Choose Hook Type

| Validation Need | Best Hook |
|-----------------|-----------|
| Prevent bad operations | PreToolUse |
| Check output format | PostToolUse |
| Run comprehensive checks | Stop |
| Block dangerous commands | PreToolUse |

### Step 3: Write Deterministic Checker

**Characteristics of good validators**:
- **Fast**: Sub-second runtime
- **Deterministic**: Same input → same result
- **Specific**: Clear error messages
- **Actionable**: Agent knows how to fix failures

### Step 4: Test in Context

**Testing checklist**:
- [ ] Valid input passes
- [ ] Invalid input fails with clear error
- [ ] Error message guides correction
- [ ] Agent can self-correct based on error
- [ ] Hook runs at expected lifecycle point
- [ ] Performance is acceptable

### Step 5: Add Observability

**Logging checklist**:
- [ ] Log validation start (what, where, when)
- [ ] Log validation result (pass/fail, details)
- [ ] Log performance (time taken)
- [ ] Log anomalies (unexpected findings)

---

## Real-World Example: Finance Review Pipeline

### Problem Statement

Process raw bank CSV exports → generate financial insights dashboard.

### Challenges

1. **Format diversity**: Banks export different formats
2. **Data quality**: Missing values, type mismatches
3. **Calculation errors**: Balance must be correct
4. **Output quality**: HTML/visualizations must work

### Solution: Specialized Self-Validating Agents

```
/raw_bank_exports.csv
    ↓
[normalize-csv-agent]
  - Validates: CSV structure, column types
  - Output: Standardized format
    ↓
[categorize-csv-agent]
  - Validates: Category schema, coverage
  - Output: Categorized transactions
    ↓
[merge-accounts-agent]
  - Validates: Merge integrity, no duplicates
  - Output: Combined dataset
    ↓
[graph-agent]
  - Validates: PNG generation, file size
  - Output: 8 financial plots
    ↓
[generative-ui-agent]
  - Validates: HTML structure, tag closure
  - Output: Interactive dashboard
```

### Why This Works

1. **Each agent has one job** → Clear validation requirements
2. **Validation is specialized** → CSV agent validates CSV, HTML agent validates HTML
3. **Errors are caught early** → PostToolUse validation after each operation
4. **Recovery is automatic** → Agent sees error, fixes it, re-validates
5. **Parallel execution is safe** → Multiple CSV agents can run simultaneously

### Key Takeaways

- **Specialization**: 5 agents, each with domain-specific validation
- **Determinism**: Hooks **always** run, no reliance on model memory
- **Observability**: Every validator logs results
- **Trust**: End-to-end pipeline is validated at every stage

---

## Evolution: From Global to Specialized Hooks

### Before (Global Hooks Only)

```json
// settings.json
{
  "hooks": {
    "PostToolUse": [{
      "hooks": [{
        "command": "validate-everything.sh"
      }]
    }]
  }
}
```

**Limitations**:
- One validator for all contexts
- Can't target specific agent types
- Same validation for CSV editing and HTML generation

### After (Specialized Hooks)

```yaml
# .claude/agents/csv-edit-agent.md
hooks:
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "validate-csv.py"  # CSV-specific

# .claude/agents/generative-ui-agent.md
hooks:
  Stop:
    - hooks:
        - type: command
          command: "validate-html.py"  # HTML-specific
```

**Benefits**:
- Each agent validates its own domain
- Validation is hyper-focused on agent's output
- Clear separation of concerns
- Easier to debug and maintain

---

## Measuring Success

### Metrics for Specialized Self-Validation

**Reliability**:
- Validation pass rate (aim for >95%)
- Self-correction success rate (agent fixes its own errors)
- False positive rate (validator blocks valid output)

**Performance**:
- Validation time per operation (aim for <500ms)
- Overhead as % of total runtime (aim for <10%)

**Trust**:
- Reduction in manual review needed
- User confidence in agent output
- Time saved by catching errors automatically

### Anti-Pattern: Over-Optimizing Pass Rate

**Bad**: 100% pass rate achieved by making validator too lenient

**Good**: 95% pass rate with strict validation that catches real issues

**Why**: Validation should catch problems, not hide them. High pass rate from easy validation is meaningless.

---

## Related Concepts

### vs. Testing

| Aspect | Hooks | Tests |
|--------|-------|-------|
| Purpose | Validate agent output | Verify code correctness |
| Timing | During agent execution | Separate process |
| Scope | Agent-specific | Codebase-wide |
| Trigger | Tool use / agent stop | Test command |
| Frequency | Every operation | On demand / CI |

**Relationship**: Hooks validate **what** agents produce; tests validate **how** code works.

### vs. Constraints

| Aspect | Hooks | Constraints (allowed-tools) |
|--------|-------|----------------------------|
| Purpose | Validate output | Restrict capabilities |
| Timing | After/before operation | Frontend gate |
| Flexibility | Can check complex invariants | Binary allow/deny |
| Feedback | Rich error messages | Silent failure |

**Relationship**: Constraints prevent bad operations; hooks validate good output.

### vs. Model Instruction

| Aspect | Hooks | Model Instructions |
|--------|-------|-------------------|
| Determinism | **Always** runs | Model may forget |
| Validation | Programmatic check | Model's judgment |
| Speed | Fast (ms) | Variable |
| Reliability | Guaranteed | Probabilistic |

**Relationship**: Hooks enforce what model instructions suggest.

---

## Further Reading

### Internal Memory
- `hooks_operational_guide.md` - Implementation reference
- `hook_architecture.md` - Hook system design
- `integration_verification.md` - Testing hooks in context

### External Resources
- Claude Code Hooks Documentation
- Claude Code Subagents Documentation
- Claude Code Skills Documentation
- [Agentic Finance Review](https://github.com/disler/agentic-finance-review) - Working example

### Key Papers/Concepts
- "Agents + Code Beats Agents" - Why programmatic validation matters
- "Specialized Self-Validation" - Architecture pattern
- "Deterministic Layers in Agentic Workflows" - Design principle
