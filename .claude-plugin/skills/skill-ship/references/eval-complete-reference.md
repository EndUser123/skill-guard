---
type: evaluation
load_when: evaluation
priority: mandatory
estimated_lines: 500
---

# Complete Evaluation System Reference

Comprehensive guide for skill evaluation, grading, and benchmark analysis. Consolidated from skill-creator plugin specifications.

---

## Table of Contents

1. [Evaluation System Overview](#evaluation-system-overview)
2. [Grader Agent Specification](#grader-agent-specification)
3. [Analyzer Agent Specification](#analyzer-agent-specification)
4. [JSON Schemas](#json-schemas)
5. [Statistical Analysis Methods](#statistical-analysis-methods)
6. [Quality Rubrics](#quality-rubrics)

---

## Evaluation System Overview

The skill-creator evaluation system consists of three main components:

1. **Grader Agent** - Evaluates expectations against execution transcripts and outputs
2. **Analyzer Agent** - Identifies patterns and anomalies in benchmark results
3. **Statistical Aggregation** - Computes mean, stddev, and deltas across multiple runs

### Key Principles

- **Evidence-based grading** - Every PASS/FAIL must cite specific evidence
- **Burden of proof** - The expectation must prove itself true; uncertainty = FAIL
- **Pattern detection** - Identify non-discriminating assertions, high-variance evals, flaky tests
- **Avoid overfitting** - Generalize from specific failures to broader categories

---

## Grader Agent Specification

The Grader reviews a transcript and output files, then determines whether each expectation passes or fails with clear evidence.

### Role

You have two jobs: grade the outputs, and critique the evals themselves. A passing grade on a weak assertion is worse than useless — it creates false confidence. When you notice an assertion that's trivially satisfied, or an important outcome that no assertion checks, say so.

### Inputs

- **expectations**: List of expectations to evaluate (strings)
- **transcript_path**: Path to the execution transcript (markdown file)
- **outputs_dir**: Directory containing output files from execution

### Process

#### Step 1: Read the Transcript

1. Read the transcript file completely
2. Note the eval prompt, execution steps, and final result
3. Identify any issues or errors documented

#### Step 2: Examine Output Files

1. List files in outputs_dir
2. Read/examine each file relevant to the expectations
3. Note contents, structure, and quality

#### Step 3: Evaluate Each Assertion

For each expectation:

1. **Search for evidence** in the transcript and outputs
2. **Determine verdict**:
   - **PASS**: Clear evidence the expectation is true AND the evidence reflects genuine task completion, not just surface-level compliance
   - **FAIL**: No evidence, or evidence contradicts the expectation, or the evidence is superficial (e.g., correct filename but empty/wrong content)
3. **Cite the evidence**: Quote the specific text or describe what you found

#### Step 4: Extract and Verify Claims

Beyond the predefined expectations, extract implicit claims from the outputs and verify them:

1. **Extract claims** from the transcript and outputs:
   - Factual statements ("The form has 12 fields")
   - Process claims ("Used pypdf to fill the form")
   - Quality claims ("All fields were filled correctly")

2. **Verify each claim**:
   - **Factual claims**: Can be checked against the outputs or external sources
   - **Process claims**: Can be verified from the transcript
   - **Quality claims**: Evaluate whether the claim is justified

3. **Flag unverifiable claims**: Note claims that cannot be verified with available information

This catches issues that predefined expectations might miss.

#### Step 5: Critique the Evals

After grading, consider whether the evals themselves could be improved. Only surface suggestions when there's a clear gap.

Good suggestions test meaningful outcomes — assertions that are hard to satisfy without actually doing the work correctly. Think about what makes an assertion *discriminating*: it passes when the skill genuinely succeeds and fails when it doesn't.

**Suggestions worth raising:**
- An assertion that passed but would also pass for a clearly wrong output (e.g., checking filename existence but not file content)
- An important outcome you observed — good or bad — that no assertion covers at all
- An assertion that can't actually be verified from the available outputs

Keep the bar high. The goal is to flag things the eval author would say "good catch" about, not to nitpick every assertion.

### Grading Criteria

**PASS when**:
- The transcript or outputs clearly demonstrate the expectation is true
- Specific evidence can be cited
- The evidence reflects genuine substance, not just surface compliance (e.g., a file exists AND contains correct content, not just the right filename)

**FAIL when**:
- No evidence found for the expectation
- Evidence contradicts the expectation
- The expectation cannot be verified from available information
- The evidence is superficial — the assertion is technically satisfied but the underlying task outcome is wrong or incomplete
- The output appears to meet the assertion by coincidence rather than by actually doing the work

**When uncertain**: The burden of proof to pass is on the expectation.

### Output Format

```json
{
  "expectations": [
    {
      "text": "The output includes the name 'John Smith'",
      "passed": true,
      "evidence": "Found in transcript Step 3: 'Extracted names: John Smith, Sarah Johnson'"
    }
  ],
  "summary": {
    "passed": 2,
    "failed": 1,
    "total": 3,
    "pass_rate": 0.67
  },
  "claims": [
    {
      "claim": "The form has 12 fillable fields",
      "type": "factual",
      "verified": true,
      "evidence": "Counted 12 fields in field_info.json"
    }
  ],
  "eval_feedback": {
    "suggestions": [
      {
        "assertion": "The output includes the name 'John Smith'",
        "reason": "A hallucinated document that mentions the name would also pass — consider checking it appears as the primary contact with matching phone and email from the input"
      }
    ],
    "overall": "Assertions check presence but not correctness. Consider adding content verification."
  }
}
```

---

## Analyzer Agent Specification

The Analyzer has two modes: (1) Post-hoc analysis of blind comparisons, and (2) Benchmark results pattern analysis.

### Mode 1: Post-hoc Comparison Analysis

Analyze blind comparison results to understand WHY the winner won and generate improvement suggestions.

#### Process

1. **Read Comparison Result** - Note the winning side, reasoning, and scores
2. **Read Both Skills** - Identify structural differences in instructions, tools, examples
3. **Read Both Transcripts** - Compare execution patterns and tool usage
4. **Analyze Instruction Following** - Score 1-10 how closely each agent followed their skill
5. **Identify Winner Strengths** - What made the winner better?
6. **Identify Loser Weaknesses** - What held the loser back?
7. **Generate Improvement Suggestions** - Prioritized by impact (high/medium/low)

#### Output Format

```json
{
  "comparison_summary": {
    "winner": "A",
    "winner_skill": "path/to/winner/skill",
    "loser_skill": "path/to/loser/skill",
    "comparator_reasoning": "Brief summary of why comparator chose winner"
  },
  "winner_strengths": [
    "Clear step-by-step instructions for handling multi-page documents",
    "Included validation script that caught formatting errors"
  ],
  "loser_weaknesses": [
    "Vague instruction 'process the document appropriately' led to inconsistent behavior",
    "No script for validation, agent had to improvise"
  ],
  "instruction_following": {
    "winner": {"score": 9, "issues": ["Minor: skipped optional logging step"]},
    "loser": {"score": 6, "issues": ["Did not use the skill's formatting template"]}
  },
  "improvement_suggestions": [
    {
      "priority": "high",
      "category": "instructions",
      "suggestion": "Replace 'process the document appropriately' with explicit steps",
      "expected_impact": "Would eliminate ambiguity that caused inconsistent behavior"
    }
  ]
}
```

### Mode 2: Benchmark Results Pattern Analysis

Review all benchmark run results and generate freeform notes that help the user understand skill performance. Focus on patterns that wouldn't be visible from aggregate metrics alone.

#### Process

1. **Read Benchmark Data** - Load benchmark.json with all run results
2. **Analyze Per-Assertion Patterns**:
   - Always pass in both configs? (may not differentiate skill value)
   - Always fail in both configs? (may be broken or beyond capability)
   - Always pass with skill but fail without? (skill clearly adds value)
   - Always fail with skill but pass without? (skill may be hurting)
   - Highly variable? (flaky expectation or non-deterministic behavior)

3. **Analyze Cross-Eval Patterns**:
   - Are certain eval types consistently harder/easier?
   - Do some evals show high variance while others are stable?
   - Are there surprising results that contradict expectations?

4. **Analyze Metrics Patterns**:
   - Does the skill significantly increase execution time?
   - Is there high variance in resource usage?
   - Are there outlier runs that skew the aggregates?

#### Output Notes Examples

```
[
  "Assertion 'Output is a PDF file' passes 100% in both configurations - may not differentiate skill value",
  "Eval 3 shows high variance (50% ± 40%) - run 2 had an unusual failure",
  "Without-skill runs consistently fail on table extraction expectations",
  "Skill adds 13s average execution time but improves pass rate by 50%"
]
```

#### Guidelines

**DO:**
- Report what you observe in the data
- Be specific about which evals, expectations, or runs you're referring to
- Note patterns that aggregate metrics would hide
- Provide context that helps interpret the numbers

**DO NOT:**
- Suggest improvements to the skill (that's for the improvement step, not benchmarking)
- Make subjective quality judgments ("the output was good/bad")
- Speculate about causes without evidence
- Repeat information already in the run_summary aggregates

---

## JSON Schemas

### evals.json

Defines the evals for a skill. Located at `evals/evals.json` within the skill directory.

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "User's example prompt",
      "expected_output": "Description of expected result",
      "files": ["evals/files/sample1.pdf"],
      "expectations": [
        "The output includes X",
        "The skill used script Y"
      ]
    }
  ]
}
```

**Fields:**
- `skill_name`: Name matching the skill's frontmatter
- `evals[].id`: Unique integer identifier
- `evals[].prompt`: The task to execute
- `evals[].expected_output`: Human-readable description of success
- `evals[].files`: Optional list of input file paths (relative to skill root)
- `evals[].expectations`: List of verifiable statements

### grading.json

Output from the grader agent. Located at `<run-dir>/grading.json`.

```json
{
  "expectations": [
    {
      "text": "The output includes the name 'John Smith'",
      "passed": true,
      "evidence": "Found in transcript Step 3: 'Extracted names: John Smith, Sarah Johnson'"
    }
  ],
  "summary": {
    "passed": 2,
    "failed": 1,
    "total": 3,
    "pass_rate": 0.67
  },
  "execution_metrics": {
    "tool_calls": {"Read": 5, "Write": 2, "Bash": 8},
    "total_tool_calls": 15,
    "total_steps": 6,
    "errors_encountered": 0,
    "output_chars": 12450,
    "transcript_chars": 3200
  },
  "timing": {
    "executor_duration_seconds": 165.0,
    "grader_duration_seconds": 26.0,
    "total_duration_seconds": 191.0
  },
  "claims": [
    {
      "claim": "The form has 12 fillable fields",
      "type": "factual",
      "verified": true,
      "evidence": "Counted 12 fields in field_info.json"
    }
  ],
  "eval_feedback": {
    "suggestions": [
      {
        "assertion": "The output includes the name 'John Smith'",
        "reason": "A hallucinated document that mentions the name would also pass"
      }
    ],
    "overall": "Assertions check presence but not correctness."
  }
}
```

**Important:** The `expectations` array must use the fields `text`, `passed`, and `evidence` (not `name`/`met`/`details` or other variants) — the viewer depends on these exact field names.

### benchmark.json

Output from Benchmark mode. Located at `benchmarks/<timestamp>/benchmark.json`.

```json
{
  "metadata": {
    "skill_name": "pdf",
    "skill_path": "/path/to/pdf",
    "timestamp": "2026-01-15T10:30:00Z",
    "evals_run": [1, 2, 3],
    "runs_per_configuration": 3
  },
  "runs": [
    {
      "eval_id": 1,
      "eval_name": "Ocean",
      "configuration": "with_skill",
      "run_number": 1,
      "result": {
        "pass_rate": 0.85,
        "passed": 6,
        "failed": 1,
        "total": 7,
        "time_seconds": 42.5,
        "tokens": 3800
      }
    }
  ],
  "run_summary": {
    "with_skill": {
      "pass_rate": {"mean": 0.85, "stddev": 0.05, "min": 0.80, "max": 0.90},
      "time_seconds": {"mean": 45.0, "stddev": 12.0, "min": 32.0, "max": 58.0}
    },
    "without_skill": {
      "pass_rate": {"mean": 0.35, "stddev": 0.08, "min": 0.28, "max": 0.45}
    },
    "delta": {
      "pass_rate": "+0.50",
      "time_seconds": "+13.0"
    }
  },
  "notes": [
    "Assertion 'Output is a PDF file' passes 100% in both configurations - may not differentiate skill value"
  ]
}
```

**Critical:** The viewer reads these field names exactly. Using `config` instead of `configuration`, or putting `pass_rate` at the top level of a run instead of nested under `result`, will cause the viewer to show empty/zero values.

---

## Statistical Analysis Methods

### Calculating Statistics

For each metric (pass_rate, time_seconds, tokens), compute:

```python
def calculate_stats(values: list[float]) -> dict:
    if not values:
        return {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0}

    n = len(values)
    mean = sum(values) / n

    if n > 1:
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        stddev = math.sqrt(variance)
    else:
        stddev = 0.0

    return {
        "mean": round(mean, 4),
        "stddev": round(stddev, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4)
    }
```

### Delta Calculation

```python
delta_mean = with_skill_mean - without_skill_mean
delta_str = f"+{delta_mean:.2f}" if delta_mean >= 0 else f"{delta_mean:.2f}"
```

### Identifying Patterns

| Pattern | Description | Action |
|---------|-------------|--------|
| Always pass (both) | 100% pass rate in both configurations | May not differentiate skill value - consider removing |
| Always fail (both) | 0% pass rate in both configurations | May be broken or beyond capability - investigate |
| Skill adds value | High pass with skill, low without | Good discriminative assertion |
| Skill hurts | Low pass with skill, high without | Skill may have bugs - investigate |
| High variance | Large stddev relative to mean | Flaky test or non-deterministic behavior |

---

## Quality Rubrics

### Overall Quality Scoring

| Grade | Score Range | Description |
|-------|------------|-------------|
| A | 90-100 | Comprehensive, current, actionable |
| B | 70-89 | Good coverage, minor gaps |
| C | 50-69 | Basic info, missing key sections |
| D | 30-49 | Sparse or outdated |
| F | 0-29 | Missing or severely outdated |

### Evaluation Criteria

| Criterion | Weight | Check |
|-----------|--------|-------|
| Commands/workflows documented | High | Are build/test/deploy commands present? |
| Architecture clarity | High | Can Claude understand the codebase structure? |
| Non-obvious patterns | Medium | Are gotchas and quirks documented? |
| Conciseness | Medium | No verbose explanations or obvious info? |
| Currency | High | Does it reflect current codebase state? |
| Actionability | High | Are instructions executable, not vague? |

### Skill Quality Checklist

**Structure:**
- [ ] SKILL.md file exists with valid YAML frontmatter
- [ ] Frontmatter has `name` and `description` fields
- [ ] Markdown body is present and substantial
- [ ] Referenced files actually exist

**Description Quality:**
- [ ] Uses third person ("This skill should be used when...")
- [ ] Includes specific trigger phrases users would say
- [ ] Lists concrete scenarios ("create X", "configure Y")
- [ ] Not vague or generic

**Content Quality:**
- [ ] SKILL.md body uses imperative/infinitive form
- [ ] Body is focused and lean (1,500-2,000 words ideal, <5k max)
- [ ] Detailed content moved to references/
- [ ] Examples are complete and working
- [ ] Scripts are executable and documented

**Progressive Disclosure:**
- [ ] Core concepts in SKILL.md
- [ ] Detailed docs in references/
- [ ] Working code in examples/
- [ ] Utilities in scripts/
- [ ] SKILL.md references these resources

---

## Additional Resources

- **`eval-guide.md`** - User-facing guide for running evals
- **`examples/eval-example.json`** - Example eval suite template
- **skill-creator plugin** - Full implementation with scripts and agents
