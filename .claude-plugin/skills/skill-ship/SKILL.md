---
name: skill-ship
description: "Implement, repair, and harden skills so the intended design is correctly realized in SKILL.md, code, hooks, tests, and integrations."
version: 1.11.0
status: stable
category: orchestration
effort: medium
triggers:
  - /skill-ship
  - "complete skill"
  - "skill completion"
aliases:
  - /skill-ship
  - /sc
suggest:
  - skill-creator:skill-creator
  - plugin-dev:skill-development
  - /similarity
  - /doc-to-skill
  - /sharing-skills
  - /skill-audit
depends_on_skills: []
enforcement: advisory
workflow_steps:
  - phase_0_context: Lightweight session scan (read recent turns for correction signals, check .claude/hooks/.evidence/gto-state-* for prior GTO outputs — no external /gto invocation)
  - phase_1_discovery: Understand user intent, auto-invoke /similarity for conflict detection with result envelope pattern, extract requirements
  - phase_1_5_knowledge_retrieval:
      description: "Intelligent NotebookLM scan (semantic notebook discovery via describe+match or inverted query routing; functional quality inference (robustness/computational efficiency/token efficiency/safety/observability/concurrency/recoverability/self-improvement); 5-query per notebook: enforcement, agents/sub-agents, triggers, output, gaps), CKS semantic search, existing skills/plugins pattern scan, and memory.md for relevant patterns/lessons before building"
      enforcement: required
      blocks_phase_2: true
      skip_when:
        - simple_skill: "Skill has <5 steps and straightforward execution — user can override by requesting full retrieval"
        - user_declined: "User explicitly declined knowledge retrieval"
        - no_existing_entries: "Domain has no existing CKS/memory/notebook entries (verified via /search)"
      violation_message: "Phase 1.5 skipped without logged reason — Phase 2 blocked until reason is documented"
  - phase_1_7_policy_routing:
      description: "Classify artifact type + blast radius, read config/policy.json, emit required_phases list and risk_level"
      enforcement: required
      blocks_phase_2: true
      output: required_phases (list), risk_level (low/medium/high), matched_artifact_type (string)
  - phase_2_creation: "Create or update skill structure using skill-creator and skill-development guidance WITH constitutional filter (no enterprise patterns), plan-and-review for complex skills (>5 steps). REQUIRES: Phase 1.5 output present in workflow state or conversation — if Phase 1.5 was skipped, its skip reason must be documented before Phase 2 begins."
  - phase_3a_spec_compliance: Verify implementation follows plan with completion evidence (RED/GREEN/REGRESSION/VERIFY) - blocks 3b until SPEC_PASS
  - phase_3b_code_quality: Validate YAML frontmatter, trigger accuracy, quality gates, context bloat prevention, and operational resilience (multi-terminal scope, stale-data immunity, compact resilience, cognitive-hook fit) - blocks 3c until critical issues resolved
  - phase_3c_integration_verification: Test skill invocation and execution paths - blocks Phase 4 until integration passes
  - phase_3_5_evaluation: Run eval suite with skill-creator including benchmarks and variance analysis (skip for simple skills)
  - phase_3e_evaluator:
      description: "Evaluate artifact against implementation/readiness rubric lenses, emit structured JSON findings per lens, and flag strategic defects for /skill-audit"
      enforcement: required
      blocks_phase_3f: true
      output: JSON array of {lens, finding, evidence, proposed_score, severity, owner}
  - phase_3f_judge:
      description: "Apply policy to implementation/readiness findings, return pass/conditional_pass/fail decision, and require /skill-audit for strategic defects"
      enforcement: required
      blocks_phase_4: true
      output: {decision, required_follow_ups, scores}
  - phase_4_optimization: Add hooks for mechanical continuation, validation patterns, cognitive/reasoning support where justified, and standardized formatting via output-style-extractor
  - phase_5_distribution: Package skill for sharing via GitHub PR workflow using sharing-skills
---

# Skill Ship

Implementation and readiness shipper for skills.

## Purpose

Implement, repair, and harden skills and orchestrators once the intended design is clear enough to build. `/skill-ship` owns implementation correctness: creating or updating SKILL.md, code, hooks, tests, validation wiring, optimization, and distribution. It may call `/sqa`, `/arch`, `/rca`, or `/sdlc` for targeted guidance, but it does not own final strategic judgment about whether the skill should exist in this form.

Operationally, `/skill-ship` is also responsible for making shipped skills:
- multi-terminal isolated or explicitly stateless
- immune to stale data through freshness/invalidation rules
- resilient to workflow interruption and compact events
- deliberate about cognitive/reasoning hook usage instead of duplicating or bypassing the existing hook stack

`/skill-ship` should also preserve ACEF-style command discipline where it adds real value:
- input quality gates for vague or underspecified user requests
- single responsibility per skill unless a deliberate scope exception is documented
- explicit enumeration of logical execution and failure paths for branch-heavy skills
- standardized block/error wording so enforcement is distinguishable from crashes

`/skill-ship` should answer questions like:
- Did we implement the intended skill correctly?
- Are the hooks, files, tests, and integrations wired properly?
- Is the artifact ready to rely on?
- Is the shipped skill operationally safe across terminals, stale state, and compaction?
- Are cognitive/reasoning hooks used where helpful and left out where they would be noise?

Creation is not the same as readiness. `/skill-ship` must not call a new or repaired skill "shipped", "ready", or "complete" immediately after Phase 2 creation when policy routing still requires Phase 3 or Phase 3e/3f work. A skill is only ready once the required validation path has run or an explicit policy-backed skip reason has been documented.

`/skill-ship` should not be the primary owner of:
- whether the skill’s strategy is the right one
- whether the skill should be split, merged, or replaced
- whether enforcement belongs in prose, hooks, validators, or another skill
- whether the user-facing outcome is the right outcome model

Those belong to `/skill-audit`.

## Self-Improvement Loop

`/skill-ship` does not mine raw chat history as truth. Instead it consumes structured lessons approved by `/skill-audit` and decides how to realize them:

- docs/prompt clarification when judgment should stay flexible
- validator checks when the failure is repeated and structurally detectable
- hooks when the enforcement must happen at runtime
- tests when the failure is a regression class

After shipping, `/skill-ship` should emit a short post-ship reflection:
- what failure class was prevented
- what still depends on human judgment
- what should be promoted to a stronger enforcement layer next time

## Internal Discovery Modes

`/skill-ship` should use two internal helper passes regularly, and two others selectively:

- `challenge`: adversarial implementation check before calling a nontrivial artifact ready
- `graduate`: promote repeated fixes into validators, hooks, tests, or stronger workflow rules
- `trace`: reconstruct how a requirement or correction evolved when implementation details depend on earlier decisions
- `emerge`: identify latent recurring implementation debt across repeated ship cycles

Default stance:
- for medium/high-risk creation or repair, run `challenge` through the evaluator/judge path
- after repeated similar fixes, run `graduate` to decide what should become durable enforcement
- use `trace` when the current implementation only makes sense in light of prior plan, audit, or user corrections
- use `emerge` sparingly, mainly when repeated ship cycles suggest a broader pattern the current artifact still does not name

These are internal reasoning passes, not user-facing prompts.

Reference: `P:/.claude/skills/__lib/sdlc_internal_modes.md`

## Reasoning Effort Policy

`/skill-ship` should match reasoning depth to implementation risk and ambiguity instead of treating every subtask as equally deep.

Claude Code supports per-skill `effort:`. `/skill-ship` should use that capability deliberately and also guide shipped target skills toward appropriate effort settings where useful.

Default reasoning-depth policy for `/skill-ship`:
- `low` for rote deterministic edits, formatting, and clearly bounded mechanical cleanups
- `medium` for normal skill implementation, repair, and wiring work
- `high` for integration, contract-sensitive enforcement, operational resilience fixes, evaluator/judge preparation, and ambiguous implementation tradeoffs that still belong in shipping
- `max` only when implementation is blocked on unusually hard technical ambiguity but the strategic direction is already settled

When shipping a target skill, prefer:
- deeper reasoning for architecture-preserving implementation choices, safety-critical hooks, and cross-file integration
- lighter reasoning for repetitive or heavily constrained edits
- explicit reasoning-depth guidance in prompts, rubrics, or workflow text when it helps future runs
- set or recommend `effort:` frontmatter only when it materially improves behavior or consistency

## Open-Ended Questions

Open-ended questions are appropriate in `/skill-ship` only when they help narrow toward a robust implementation of an already-settled design.

Good open-ended questions for `/skill-ship`:
- What is the simplest implementation that still preserves the intended design?
- What part of this implementation is most likely to drift?
- What do we need to prove before this is safe to ship?
- Where should enforcement live in code, hooks, tests, or validators?
- What implementation choice gives us the most maintainable path?
- What should fail closed here?
- What is the smallest change that makes the design real?
- What reasoning depth is justified for this implementation step, and what would be wasteful?

Avoid open-ended questions in `/skill-ship` when they reopen settled strategic questions, such as whether the skill should exist at all, whether the outcome model is wrong, or whether the skill should be split or merged. Those belong to `/skill-audit`.

## Missing-Enforcement Prompts

Before declaring a shipped skill ready, `/skill-ship` should ask itself:

- What important behavior do we think is enforced, but have not actually implemented?
- What ambiguity are we still relying on a reviewer to catch manually?
- What regression class will recur unless we add a test or validator now?
- What implementation detail is doing policy work by accident?
- What should fail closed, but currently only fails by convention?
- What is the strongest implementation-side objection to declaring this ready? (`challenge`)
- What repeated fix should now graduate into a validator, hook, or test? (`graduate`)
- What earlier design decision or user correction most changed what "correct implementation" means here? (`trace`)

These prompts are implementation-focused. If answering them reopens scope, outcome model, or enforcement ownership, stop and route to `/skill-audit`.

These are internal self-check prompts. They are not default prompts to ask the user.

## Completion Integrity

Before finalizing a `/skill-ship` run:

- reread the final artifact from disk and summarize the actual final state, not an earlier draft
- do not narrate frontmatter fields that are no longer present
- do not invent optional metadata such as `status:` unless the active local schema or repo conventions require it
- if `required_phases` still include unfinished validation work, describe the artifact as `created` or `drafted`, not `shipped`
- if a new skill or orchestrator is nontrivial, expect the Phase 3e Evaluator and Phase 3f Judge path unless policy routing explicitly bypasses them

Treat "we could reason it out ourselves" as a bad reason to skip critique. For medium/high-risk creation or repair flows, the evaluator/judge subagent path is the default adversarial check, not an optional flourish.

## Operational Resilience Requirements

When `/skill-ship` builds or repairs a skill, it should ensure one of two things is true and documented:

- the skill is explicitly stateless/read-only, so multi-terminal isolation and stale-data risks are structurally absent
- or the skill has a concrete operational contract for:
  - terminal/session scope
  - stale-data invalidation or freshness authority
  - interrupted-workflow / compact recovery

For hook-heavy skills, `/skill-ship` should also decide explicitly whether the design should:
- reuse existing cognitive/reasoning hooks from the hook stack
- add a new cognitive/reasoning hook because there is a real gap
- or avoid hook-based cognition entirely because prompt-level guidance is enough

Do not leave these as implicit assumptions.

## Command Discipline Requirements

When `/skill-ship` builds or repairs a skill, it should also check four ACEF-derived command-discipline concerns:

- **Input quality gate**: if the skill accepts broad or ambiguous requests, define when it should clarify, infer, block, or route instead of guessing
- **Single responsibility**: if the skill is trying to do strategy, implementation, and distribution at once, document the scope guard or route part of the work elsewhere
- **Path enumeration**: for routing-, phase-, or branch-heavy skills, enumerate the meaningful execution and failure paths so validators/tests can cover them
- **Standardized errors**: blocking/enforcement paths should use consistent, operator-readable language so users can tell workflow enforcement from accidental breakage

These are implementation duties. If satisfying them requires changing the skill's fundamental purpose or scope, stop and route to `/skill-audit`.

## Added-Complexity Check

Before adding a new hook, validator, controller, layer, subagent, or helper system, `/skill-ship` should ask:

- What concrete failure or repeated manual burden does this new structure prevent?
- Is there a simpler alternative that reuses an existing mechanism?
- What implementation complexity, maintenance cost, or blast radius does this add?
- If this extra structure is wrong, is it easy to undo?

If those questions cannot be answered clearly, prefer the simpler implementation or route back to `/skill-audit` if the uncertainty is strategic.

## When to Use

| Strength | When This Applies |
|----------|-------------------|
| **MUST BE USED** | "create a skill", "build a new skill", "write a skill from scratch" |
| **Use PROACTIVELY** | "fix my skill", "improve this skill", "optimize a skill", "skill isn't working" |
| **Consider using** | "how do I create skills", "how do I implement this skill design", "finish wiring this skill" |

**Decision:** "create/new/build" → MUST USE | "fix/broken/error" → PROACTIVE | "review/audit/should this skill exist like this?" → prefer `/skill-audit`

## Optimized / Evaluated Skills

### Context Phase
- **gto**: Session gap analysis - detect user corrections, learning signals, broken windows

### Creation Phase
- **skill-creator**: (external plugin) Full iterative development loop with evals, benchmarks, description optimization
- **skill-development**: SKILL.md structure, progressive disclosure, plugin-specific best practices
- **doc-to-skill**: Convert documentation into skills

### Analysis Phase
- **similarity**: Find similar/redundant skills (auto-invoked in Phase 1)
- **av** (internal): Analyze and generate hook files
- **testing-skills** (internal): Quality gate validation

### Validation Phase (Policy-Routed)
- **3e Evaluator** (internal): Produces structured findings about implementation quality, readiness, and rubric compliance — not strategic redesign advice
- **3f Judge** (internal): Applies policy to implementation/readiness findings, returns pass/conditional_pass/fail

> Evaluator and Judge are **subagent-only** — no Python implementations exist. They are activated via subagent prompts (see `references/evaluator-judge-prompts.md`) based on policy.json routing (Phase 1.7 output). For low-risk artifacts (prompt_skill, distribution_update), they may be bypassed. If findings point to wrong strategy, wrong outcome model, wrong trigger/scope, wrong enforcement ownership, or the wrong cognitive-hook ownership boundary, route to `/skill-audit` instead of trying to solve those inside `/skill-ship`.

### Optimization Phase
- **av2** (internal): Mechanical continuation enforcement
- **output-style-extractor**: Extract display formatting patterns

### Distribution Phase
- **sharing-skills**: GitHub PR workflow automation
- **github-public-posting**: Pre-publish checklist

> `/av`, `/av2`, and `/testing-skills` are internal. Users should invoke `/skill-ship` directly.

## References

| Category | Files |
|----------|-------|
| **Core** | `references/workflow-phases.md` (detailed phase instructions), `references/skill-frontmatter-fields.md` (frontmatter reference), `references/config-file-conventions.md` (config template pattern) |
| **Workflow** | `references/agent-tool-usage.md`, `references/knowledge-retrieval.md`, `references/plan-and-review.md`, `references/learning-loop.md` |
| **Quality** | `references/phase3-validation-details.md`, `references/skill-quality-gates.md`, `references/context-bloat-prevention.md` |
| **Evaluation** | `references/eval-guide.md`, `references/eval-complete-reference.md`, `references/description-optimization-guide.md` |
| **Agent Patterns** | `references/subagent-result-envelope.md`, `references/anti-false-done-patterns.md`, `references/agentic-validation-hooks.md`, `references/constitutional-filter.md`, `references/agent-failure-modes.md`, `references/agent-command-templates.md` |
| **Output** | `references/output-format-templates.md` (7 templates), `references/format-compliance-guidance.md`, `references/recommended-next-steps-format.md` |
| **Hooks** | `references/skill-based-hooks.md`, `references/hooks-implementation-guide.md`, `references/hooks-design-patterns.md`, `references/procedure-type-skills-embedded-enforcement.md` |
| **Examples** | `examples/WORKFLOW-EXAMPLES.md` (3 complete workflows), `examples/eval-example.json` (eval suite template) |

**External Docs:** `P:/.claude/hooks/PROTOCOL.md` | `P:/.claude/hooks/ARCHITECTURE.md` | `P:/.claude/hooks/SKILL_AUTHORS_GUIDE.md`

## Workflow Phases Overview

**Detailed instructions:** `references/workflow-phases.md`

| Phase | Goal | Key Skills | Skip When |
|-------|------|------------|-----------|
| **0. Context** | Session awareness, detect patterns | session scan | Fresh sessions |
| **1. Discovery** | Understand user intent, auto-detect conflicts | similarity (auto) | Never |
| **1.5. Knowledge** | Retrieve existing patterns/lessons | notebooklm, cks, memory | Simple skills, user declines |
| **1.7. Policy Routing** | Classify artifact type + blast radius, emit required_phases | policy.json lookup | Trivial intent (e.g., typo fix) |
| **2. Creation** | Build skill structure with progressive disclosure | skill-creator, skill-development | Never |
| **3a. Spec** | Verify implementation follows plan | testing-skills (spec) | Never |
| **3b. Quality** | Validate YAML, triggers, quality gates, operational resilience | av, testing-skills (quality) | Simple skills (<100 lines) |
| **3c. Integration** | Test skill invocation and execution | testing-skills (integration) | Never |
| **3d. Artifact** | Validate solution framing and artifact quality | artifact rubric | Non-artifact skills |
| **3e. Evaluator** | Structured implementation/readiness findings per lens (policy-routed) | implementation rubric | Risk-level bypass |
| **3f. Judge** | Policy-driven pass/conditional_pass/fail decision on implementation readiness | evaluator findings + risk_level | Risk-level bypass |
| **3.5. Evaluation** | Empirical testing with evals/benchmarks | skill-creator (evals) | Simple skills, user declines |
| **4. Optimization** | Add hooks, enforce formatting | av2, output-style-extractor | Single-phase workflows |
| **5. Distribution** | Prepare for sharing/shipping | sharing-skills | Local skills only |

### Phase Summaries

**Phase 0:** Lightweight session scan — read recent turns for correction signals, check gto-state-* files and workflow-state.json for interrupted work. Skip for fresh sessions.

**Phase 1:** Extract user intent. Auto-invoke `/similarity` for conflict detection (>=80% → enhance vs create). **Critical**: Check for possessive repair phrases before assuming new creation ("my skill isn't working" = REPAIR, not CREATE). See `references/workflow-phases.md#phase-1` for intent extraction rules.

**Phase 1.5:** Query NotebookLM, CKS, and memory.md for relevant patterns. See `references/knowledge-retrieval.md` for query patterns. Skip for simple skills (<5 steps).

**Phase 2:** Create SKILL.md with proper frontmatter (including `enforcement` field). Apply progressive disclosure (<500 lines). See `references/workflow-phases.md#phase-2` and `references/skill-frontmatter-fields.md`.

**Phase 3 (Quality):** Three sub-phases run sequentially with fresh subagents (no state sharing between phases). Each spawns a fresh subagent with minimal context to prevent bias. Phase 3 is about implementation correctness and readiness, not strategic redesign.

- **3a Spec:** Did implementation follow the plan? Output: `SPEC_PASS`/`SPEC_FAIL`. Blocks 3c. Never skip.
- **3b Quality:** YAML completeness, trigger accuracy, context bloat prevention, and operational resilience. Confirm the skill is terminal-isolated or explicitly stateless, stale-data-immune, compact-resilient, and deliberate about cognitive/reasoning hooks. Blocks 3c until critical issues resolved. Skip for simple skills (<100 lines) only when those concerns are truly not applicable.
- **3c Integration:** Test skill invocation, execution paths, runtime behavior. Blocks Phase 4. Never skip.
- **3d Artifact (conditional):** Activate when skill emits durable artifacts (plans, reports). See `references/phase3-validation-details.md` for tables, processes, gate criteria.

See `references/phase3-validation-details.md` for complete validation tables, absence claim workflow, and Phase 3d artifact activation criteria.

**Phase 3.5:** Run eval suite with `evals/evals.json`. See `references/eval-guide.md`. Skip for simple skills.

**Phase 4:** Invoke internal av2 for StopHook, output-style-extractor for formatting, and add cognitive/reasoning hooks only when there is a demonstrated gap that prompt-level guidance or existing hooks do not already cover. Pattern synthesis from `P:/memory/skill_optimization_patterns.md`. See `references/workflow-phases.md#phase-4`.

**Phase 5:** Fork, commit with conventional commits, open PR. See `references/workflow-phases.md#phase-5`.

---

## Iteration Escalation Ladder

When iterating on a skill (Phase 4 optimization or improvement cycles), classify the iteration depth:

| Level | Signal | Example |
|-------|--------|---------|
| **Band-Aid** | Patches a specific complaint | Fix a typo, adjust wording, add a missing flag |
| **Local Optimum** | Polishes within current design | Improve frontmatter, add references, restructure sections |
| **Reframe** | Questions the skill's purpose | "Should this be 3 smaller skills?" "Is the trigger wrong?" |
| **Redesign** | Changes fundamental structure | Split procedural into phase-based, merge overlapping skills |

**3-Band-Aid rule**: If 3+ iterations on the same skill are all Band-Aid level, flag: `"ITERATION DEBT: {skill} has {N} surface-level patches. Consider Reframe or Redesign iteration."`

## Multi-Criteria Quality Evaluation

During Phase 3b (Quality) and Phase 3.5 (Evaluation), score skills across weighted dimensions:

| Dimension | Weight | Criteria |
|-----------|--------|----------|
| Completeness | 0.25 | All workflow steps covered, no gaps in execution path |
| Clarity | 0.25 | Unambiguous instructions, examples for complex steps |
| Usability | 0.20 | Correct triggers, suggests bidirectional, progressive disclosure |
| Testability | 0.15 | Verification steps defined, acceptance criteria concrete |
| Robustness | 0.15 | Error handling guidance, edge cases documented |

**Score**: Each dimension 1-5. Weighted sum = quality score (max 5.0).

**Sensitivity check**: If changing any dimension score by ±1 would change the pass/fail outcome, flag as `FRAGILE QUALITY: {dimension} score is decisive — verify carefully.`

---

## Output Formatting

All skill outputs use templates from `references/output-format-templates.md`:

| Template | Use Case |
|----------|----------|
| 1: Strict Analysis | API responses, test results, RCA |
| 2: Executive Summary | Analysis reports, most skills default |
| 3: Hypothesis Testing | Debugging, investigation |
| 4: Comparison | Tool selection, architecture decisions |
| 5: Workflow Progress | Long-running tasks, phase tracking |
| 6: Error Analysis | Bug reports, debug findings |
| 7: Research Findings | Research tasks, doc analysis |

For skills producing gap-based findings (like `/gto`), use the **dynamic RNS format** — see `/gto SKILL.md` "Recommended Next Steps (RNS)" section.

### Enforcing Output Display in Skills

For skills with specific output format requirements (CLI output, config displays, etc.), use the **external template pattern**:

1. **Create** `references/output-template.md` with exact format specification
2. **Reference** it in SKILL.md: `See [references/output-template.md](references/output-template.md) for exact format`
3. **Keep** the template short (<50 lines) with concrete examples

**Why this works:** Inline format instructions are ignored ~50% of the time (GitHub #6450). External template files are read as content, not instructions, achieving much higher compliance.

See `references/format-compliance-guidance.md` for full options (Option A: template files, Option B: hook gates, Option C: both).

---

## Execution Directive

When `/skill-ship` is invoked:

1. **CONTEXT**: Phase 0 — lightweight session scan (no external `/gto`)
2. **DISCOVER**: Phase 1 — understand intent, auto-invoke `/similarity`
3. **CLASSIFY**: Determine skill type, complexity, output format
4. **COORDINATE**: Invoke appropriate specialized skills
5. **FORMAT**: Apply output format templates from `references/output-format-templates.md`
6. **VALIDATE 3a + 3b IN PARALLEL**: Two fresh subagents — 3a for spec compliance (blocks 3c), 3b for YAML/context-bloat (independent)
7. **VALIDATE 3c**: Fresh subagent tests invocation. Blocks Phase 4 until pass.
8. **EVALUATE**: Phase 3.5 evals (skip for simple skills)
9. **OPTIMIZE**: Phase 4 hooks/formatting if workflow warrants
10. **DISTRIBUTE**: Phase 5 sharing if upstreaming

**Quality Gate Protocol**: Each phase spawns FRESH subagents. Previous verdicts are NOT shared.

### Re-Run Mode Selection

When re-running `/skill-ship` on a target that was previously analyzed:

Before proceeding, present re-run mode choice using RNS formatting:

```
🔄 RE-RUN OPTIONS
  [recover/medium] RUN-001 — Full re-run: all phases 3a-3f (safe, slower)
  [recover/medium] RUN-002 — Targeted re-run: skip unaffected phases (faster, human must correctly identify affected phases)
  [recover/medium] RUN-003 — Auto-detect: skill auto-identifies affected phases based on what changed (recommended)
```

**Constraint**: Phases 3e (evaluator) + 3f (judge) MUST run regardless of chosen option — they produce the verdict that gates Phase 4.

**RUN-001 (Full)**: Re-execute ALL phases 0→5 fresh. Appropriate when structural changes were made (enforcement level, triggers, frontmatter fields).

**RUN-002 (Targeted)**: Human selects which phases to re-execute. Appropriate when only specific aspects were modified (e.g., wording in description, added one example). Human must identify affected phases correctly — skipping an affected phase is a compliance failure.

**RUN-003 (Auto-detect)** [default]: Compare `git diff --stat` of target SKILL.md against the prior run's artifact timestamp. If only frontmatter fields changed (version, status, enforcement) → 3b only. If content changed (workflow steps, references, phase descriptions) → full run. Mandatory phases (3e/3f) always run regardless.

**Self-targeting**: `/skill-ship /skill-ship` works without special flags or self-exclusion logic. The skill is treated like any other target. No phase skips itself — self-analysis is a first-class mode.

After user selects a mode (or defaults to RUN-003), execute the appropriate phase subset.

---

## Recommended Next Steps

When analysis is complete, present next steps in structured domain/action format. See `references/recommended-next-steps-format.md` for complete format specification, including machine-parseable format for downstream skill chaining.

---

## Agent Tool Usage

**CRITICAL**: `subagent_type` and `model` are different parameters. `model="haiku"` is correct; `(haiku model)` gets misinterpreted as `subagent_type="haiku"` causing errors.

See `references/agent-tool-usage.md` for complete parameter reference and examples.
