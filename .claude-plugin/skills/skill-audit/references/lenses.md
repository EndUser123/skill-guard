# 13 Lenses for /skill-audit

## Lens 1: Reference Integrity

**Question**: Does what SKILL.md promises to exist actually exist?

**Checks**:
- Parse references structurally from `SKILL.md`, not just raw substring scans
- `references/X.md` in SKILL.md → glob `<skill-dir>/references/X.md` → file exists?
- `templates/Y` in SKILL.md → glob `<skill-dir>/templates/Y` → file exists?
- `./resources/Z.md` in SKILL.md → resolve relative to skill root
- Template placeholders like `{template}` are placeholders, not missing-file findings
- `evals/evals.json` mentioned → glob → exists?
- `lib/` imports in Python code → each file exists?
- `workflow_steps` referenced files → each file exists?

**Evidence format**:
```json
{"lens": "REFERENCE_INTEGRITY", "promise": "references/evals.md", "status": "MISSING", "evidence": "SKILL.md line 45 mentions 'evals/evals.json' but glob returns no file"}
```

---

## Lens 2: Process Enforcement

**Question**: Are workflow step promises backed by actual Python code?

**Checks**:
- SKILL.md prose: "Phase X validates Y" or "Stage N performs Z"
  → extract the claim → search `<skill-dir>/**/*.py` for the mechanism
- For docs-first skills, distinguish "missing Python backing" from "policy intentionally lives in SKILL.md"
- "runs `/foo`" → verify the skill exists in registry
- "calls `lib.foo()`" → verify the function exists in the imported module
- "appends to state file" → verify the write logic exists
- routing table entries → verify each branch has code

**Evidence format**:
```json
{"lens": "PROCESS_ENFORCEMENT", "promise": "Phase 2 invokes av2", "status": "MISSING", "evidence": "workflow-phases.md line 312 says av2 is called but no av2 import in any .py file"}
```

---

## Lens 3: Command Discipline

**Question**: Does the skill follow ACEF-style command discipline where it matters?

**Checks**:
- Broad user-facing skills should define a vague-input quality gate instead of free-running on underspecified requests
- Branch-heavy/routing-heavy skills should enumerate their logical execution and failure paths clearly
- Multi-role skills should guard against single-responsibility drift
- User-facing workflow skills should use predictable error/block reasons so enforcement does not look like random failure

**Evidence format**:
```json
{"lens": "COMMAND_DISCIPLINE", "status": "MISSING_GATE", "evidence": "Skill accepts broad user prompts but has no clarity/input-quality gate before execution"}
```

---

## Lens 4: Structural Justification

**Question**: When the skill adds structure, is that structure actually justified?

**Checks**:
- If the skill proposes new boundaries, abstractions, hooks, validators, controllers, layers, or helper systems, require:
  - a concrete failure/prevention case
  - a simpler-alternative check
  - an explicit complexity tradeoff
  - a durability or reversibility check
- Keep this principle-based, not framework-branded; the issue is unjustified added structure, not failure to mention ADF by name

**Evidence format**:
```json
{"lens": "STRUCTURAL_JUSTIFICATION", "status": "MISSING_TRADEOFF", "evidence": "Skill recommends adding a new validator/controller layer but never asks what concrete failure it prevents or what complexity it adds"}
```

---

## Lens 5: Template System

**Question**: How are templates composed — prose or programmatic?

**Checks**:
- `render(template.md)` or `TEMPLATE_DIR` constants in code?
- Jinja2/Templar imports → template files loaded programmatically
- String concatenation for templates → prose composition
- `output-format-templates.md` reference → uses external template files?
- `references/output-template.md` exists → custom format?

**Evidence format**:
```json
{"lens": "TEMPLATE_SYSTEM", "method": "PROSE", "evidence": "Templates built via f-string concatenation in formatter.py:34-67"}
```

---

## Lens 6: Model Variance Risk

**Question**: Would different LLMs execute differently on the same skill?

**Checks**:
- Vague prose in workflow steps ("briefly", "appropriately", "as needed") → model-dependent
- No exact thresholds ("~5min", "> 10 items") → variance
- Conditional branching without explicit criteria → LLM judgment dependent
- Skill relies on conversation context rather than structured state
- Ambiguous trigger phrasing ("consider doing X") not enforced

**Evidence format**:
```json
{"lens": "MODEL_VARIANCE", "risk": "HIGH", "evidence": "workflow-phases.md step 3: 'optimize for clarity' — no concrete metric, GLM-5.1 and M2.7 could interpret differently"}
```

---

## Lens 7: Contract Completeness

**Question**: Are SDLC contract primitives fully and correctly used?

**Checks**:
- Treat `SKILL.md` as a first-class contract artifact, not just Python files
- Uses `Contract Authority Packet` for handoffs? (search doc + code)
- Uses session chain for cross-session state? (search doc + code)
- Uses `handoff_store` for file-based state? (search doc + code)
- Uses `evidence_store` for artifact persistence? (search doc + code)
- SDLC primitives vs raw file I/O — which is used and when?

**Evidence format**:
```json
{"lens": "CONTRACT_COMPLETENESS", "primitive": "NONE", "evidence": "No imports of handoff_store, session_chain, or evidence_store found in any .py file — skill uses raw JSON writes"}
```

---

## Lens 8: Skill Contract Consistency

**Question**: Does the skill specification contradict itself?

**Checks**:
- Frontmatter `enforcement` vs blocking/mandatory body rules
- Frontmatter `version` vs footer `**Version:**`
- Frontmatter status/metadata vs body behavior
- Contradictory authority statements across sections

**Evidence format**:
```json
{"lens": "SKILL_CONTRACT_CONSISTENCY", "status": "DRIFT", "evidence": "Frontmatter says enforcement=advisory but body says '/arch must repair HIGH severity defects before saving'"}
```

---

## Lens 9: Mechanism Leakage

**Question**: Does the policy text hardcode brittle runtime mechanics?

**Checks**:
- Hardcoded `Agent(...)` or equivalent tool-call pseudocode in policy sections
- Fixed model names in `SKILL.md`
- Absolute file paths as required mechanism rather than example/reference
- Fixed output file/state file locations in policy sections
- Implementation-specific orchestration details where behavior-level policy would suffice

**Ownership guidance**:
- Usually `source skill` for over-specified policy text
- `skill-ship` only when the architecture decision is already settled and this is a pure mechanical cleanup

**Evidence format**:
```json
{"lens": "MECHANISM_LEAKAGE", "status": "HARD_CODED", "evidence": "SKILL.md requires Agent(model=\"haiku\") and writes output to P:/.claude/state/foo.json"}
```

---

## Lens 10: Question Strategy

**Question**: Do the target skill's open-ended questions fit the skill's role?

**Checks**:
- Extract open-ended questions from `## Open-Ended Questions` when present, otherwise from the body
- For audit-oriented skills, flag implementation-trivia questions about exact helper names, hook filenames, file splits, module names, or paths
- For ship-oriented skills, flag strategic questions that reopen whether the skill should exist, be split/merged, or use a different enforcement model
- For strategy-heavy skills, consider whether the skill is missing internal blind-spot prompts that would surface hidden ambiguity, unstated guarantees, or reviewer-dependent interpretation
- For RCA-heavy skills, require internal competing-cause prompts that challenge symptom-vs-root-cause confusion, falsifiability, stale authority, and recurrence risk
- For RCA-heavy and architecture-heavy skills, expect `trace`-style internal prompts when the reasoning depends on how evidence or design evolved over time
- For architecture-heavy, planning-heavy, and audit-heavy skills, expect `challenge`-style internal prompts or critique passes that pressure-test the current recommendation against simpler alternatives, contradictions, or downstream ambiguity
- For lesson-capture, reflective, and audit-heavy skills, expect `emerge`-style internal prompts when repeated findings may imply a latent unnamed pattern
- For ship-heavy, planning-heavy, learn-heavy, and reflective skills, expect `graduate`-style internal prompts when repeated issues should be promoted into durable validators, hooks, tests, or workflow rules
- For implementation-heavy skills such as `/code`, require implementation-risk prompts that challenge guessed contracts, stale assumptions, fail-closed behavior, and regression exposure
- For TDD/testing-heavy skills, require test-truth prompts that challenge whether tests prove the real contract, reject naive implementations, and cover failure paths
- For action-extraction/advisory skills such as `/rns`, require action-extraction prompts that challenge vague findings, duplicate actions, stale transcript/artifact inputs, ownership drift, and unsafe "do all" bundling
- For adversarial/pre-mortem skills, require failure-mode prompts that challenge happy-path bias, producer-only proofs, hidden assumptions, low-reversibility recommendations, and shared blind spots across specialists
- For next-step advisory skills such as `/gto`, require next-step integrity prompts that challenge stale artifacts, duplicate gaps, weak ownership mapping, mis-sequencing, and generic low-value recommendations
- For session catch-up skills such as `/recap`, require catch-up integrity prompts that challenge weak transcript evidence, stale or contradicted session summaries, missed turning points, and recap-level overconfidence
- For lesson-capture skills such as `/learn`, require lesson-quality prompts that challenge novelty inflation, one-off events, weak causal claims, over-promotion, and bad future teaching
- For retrospective orchestrators such as `/retro`, require retrospective-integrity prompts that challenge score inflation, duplicated gaps, weak synthesis across chained skills, and "wrong lesson" conclusions
- For reflection/self-improvement skills such as `/reflect`, require reflection-upgrade prompts that challenge one-off preferences, stale correction signals, overfitting, wrong ownership, and prose-only fixes that should become enforcement
- Do not require open-ended questions for every skill; only judge alignment when they are present

**Evidence format**:
```json
{"lens": "QUESTION_STRATEGY", "status": "MISALIGNED", "evidence": "skill-ship asks 'Should this skill exist in this form at all?' which reopens strategy instead of narrowing toward implementation"}
```

---

## Lens 11: Operational Resilience

**Question**: Is the target skill explicit about multi-terminal isolation, stale-data immunity, compact resilience, cognitive-hook fit, and reasoning-depth fit where those concerns apply?

**Checks**:
- For orchestration, analysis, stateful, or hook-oriented skills, require an explicit stance on:
  - multi-terminal isolation or deliberate statelessness
  - stale-data immunity / freshness / invalidation behavior
  - compaction resilience / interrupted-workflow recovery
- If the skill uses or recommends hooks, require guidance on whether cognitive/reasoning hooks should be used, reused from the existing hook stack, or intentionally excluded
- For orchestration/routing skills that invoke other skills, require a nested-workflow resume contract that says whether control returns automatically to the caller or requires explicit user re-entry
- For orchestration/routing skills that promise follow-up handling or context inference, require an explicit guard against redundant clarification when recent session context already establishes the subject
- Check whether the target skill asks for reasoning depth proportionate to the work:
  - deeper reasoning for architecture, RCA, routing, safety, and policy decisions
  - lighter reasoning for rote deterministic edits
  - if `effort:` is present, verify that the configured level is proportionate to the work
  - if `effort:` is absent on high-judgment skills, consider whether adding it would reduce variance
- Distinguish docs-only low-risk skills from stateful/hook-heavy skills; do not require every trivial skill to discuss all four topics

**Evidence format**:
```json
{"lens": "OPERATIONAL_RESILIENCE", "status": "MISSING_CONTRACT", "evidence": "Hook-oriented skill defines workflow state and hooks but says nothing about terminal scope, stale-data invalidation, or cognitive hook ownership"}
```

---

## Lens 12: Assurance Strategy

**Question**: Does the skill use the right critique-agent and smoke-test contracts for its role?

**Checks**:
- For implementation-heavy skills such as `/code`, require:
  - an explicit smoke-validation contract
  - explicit critique-agent triggers for high-risk integration, hook, state, or contract changes
- For TDD/testing-heavy skills such as `/tdd`, require:
  - an explicit behavior-smoke-proof contract
  - explicit critique-agent triggers for false-confidence or contract-proof risks
- For planning-heavy skills such as `/planning`, require:
  - an explicit critique-agent review policy for stateful, contract-sensitive, layered, or overlapping-workflow plans
- For architecture-heavy skills such as `/arch`, require:
  - an explicit critique-agent review policy for contract-sensitive, stateful, router/gate, or packet-emitting designs
- For audit-heavy skills such as `/skill-audit`, require:
  - an explicit critique-agent policy for high-ambiguity strategic audits, transfer/reuse analyses, and other high-blast-radius recommendation work
- For ship-heavy skills such as `/skill-ship`, require:
  - explicit subagent evaluator/judge or critique-agent use for nontrivial new skills unless policy routing documents a real bypass
- Do not require smoke or critique-agent sections for every trivial skill; apply this lens by role and risk

**Evidence format**:
```json
{"lens": "ASSURANCE_STRATEGY", "status": "MISSING_CONTRACT", "evidence": "Implementation-heavy skill has no Smoke Validation section and no critique-agent trigger policy for high-risk changes"}
```

---

## Lens 13: Non-Goals Clarity

**Question**: Is scope explicitly defined — what the skill will NOT do?

**Checks**:
- `## Non-Goals` section exists in SKILL.md?
- Content is specific (named exclusions) vs vague ("doesn't do X")
- Exclusions match actual behavior (skill doesn't claim to do X but does)
- Missing anti-patterns mentioned? (e.g., "does NOT handle concurrent terminals")

**Evidence format**:
```json
{"lens": "NON_GOALS_CLARITY", "status": "MISSING", "evidence": "SKILL.md has no Non-Goals section — scope boundary undefined"}
```
