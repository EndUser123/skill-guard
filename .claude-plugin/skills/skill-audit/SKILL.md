---
name: skill-audit
description: "Audit skill strategy, scope, contracts, and outcome quality before or after implementation."
version: 0.1.0
status: experimental
category: analysis
effort: high
enforcement: advisory
triggers:
  - /skill-audit
  - "audit skill"
  - "analyze skill design"
suggest:
  - /skill-ship
  - /rca
depends_on_skills: []
---

# /skill-audit — Skill Strategy and Outcome Auditor

Audits whether a skill is the right skill in the right shape for the goal. Single-pass, no phases — just audit and report.

## Purpose

`/skill-ship` validates whether a chosen skill design was implemented and wired correctly. `/skill-audit` complements it by auditing whether the design itself is the right one:

- skill purpose, scope, and trigger fit
- skill-to-goal fit and outcome quality
- enforcement ownership and policy placement
- SKILL.md contract integrity and internal consistency
- mechanism leakage in policy text
- multi-terminal isolation, stale-data immunity, and compact resilience
- cognitive/reasoning hook fit and ownership
- process enforcement model (prompt, hook, code, or hybrid)
- ACEF-style command discipline (input gates, path enumeration, standardized errors, single responsibility)
- structural justification for added hooks, boundaries, abstractions, validators, or layers
- template system composition
- model variance risk
- contract primitive completeness
- Internal skill-contract consistency
- Out-of-scope clarity

`/skill-audit` should answer questions like:
- Should this skill exist in this form at all?
- Is the trigger/scope boundary correct?
- Is the enforcement model in the right place?
- Is the skill over-specified, under-specified, or split incorrectly?
- Does the resulting user outcome match the intended goal?

It should not stop at "here are the findings." It should make the next decision easier:
- Is the skill basically right, or is the contract wrong enough to redesign?
- What are the concrete next moves, in priority order?
- Who should act next: the source skill, `/skill-ship`, or `/skill-audit`?

`/skill-audit` should not be the primary owner of:
- writing hooks/scripts/tests
- wiring runtime integrations
- packaging or distribution
- proving that the chosen design was implemented correctly

## Reasoning Effort Policy

Use full LLM reasoning where it improves strategic judgment, and set the skill's configured effort to match that work.

Claude Code supports per-skill `effort:`. `/skill-audit` should use that capability deliberately rather than leaving reasoning depth implicit.

Default reasoning-depth policy for `/skill-audit`:
- `high` for primary audits, RCA, cross-skill boundary questions, enforcement ownership, and architecture-quality review
- `medium` for narrow follow-up audits, regression checks, and low-blast-radius reviews
- `max` only for unusually ambiguous, high-stakes, multi-boundary audits where shallow reasoning would likely miss the root cause
- avoid `low` for strategic work; it is usually too shallow for `/skill-audit`'s core job

When auditing a target skill, `/skill-audit` should also judge whether that target uses reasoning depth appropriately:
- deeper reasoning for RCA, architecture, routing, policy, or safety decisions
- lighter reasoning for rote transforms, formatting, or deterministic edits
- if the target skill uses `effort:`, check that the configured level matches the job it performs

If helpful, include a recommended reasoning depth (`low`/`medium`/`high`/`max`) in the Improvement Plan and call out whether the target skill should encode it in frontmatter.

## Critique-Agent Policy

`/skill-audit` should usually work directly, but it should use a bounded critique subagent when the audit depends on adversarial review rather than simple file inspection.

Trigger a critique subagent when the target or request is:
- architecture-heavy, routing-heavy, or policy-heavy
- a transfer/reuse or merge/remove/migrate analysis with multiple plausible targets
- high-blast-radius, stateful, hook-heavy, or contract-sensitive
- likely to benefit from an explicit "strongest objection" pass before final recommendations

When used, the critique subagent should be narrowly scoped:
- challenge the main audit's assumptions
- identify omitted direct consumers, simpler alternatives, or hidden failure modes
- not replace the main audit's final synthesis

Do not skip critique just because the current model could theoretically reason it out. The point is to create a deliberate second-pass adversarial check when the cost of a wrong recommendation is meaningful.

## Self-Improvement Loop

`/skill-audit` should make skills more correct over time by converting noisy experience into durable strategy changes.

The loop is:
1. Mine recent chat/transcript history for candidate failure signals.
2. Distill those signals into structured lesson artifacts.
3. Audit which lessons are real, recurring, and worth codifying.
4. Hand approved lessons to `/skill-ship` with a recommended fix layer:
   - prompt/doc only
   - validator
   - hook
   - test
   - architecture change

Raw chat history is a discovery source, not a source of truth. `/skill-audit` should prefer:
- repeated user corrections
- repeated loop/escalation patterns
- repeated stale-artifact confusion
- repeated schema/format mismatches
- repeated hook/cognitive-hook misuse

over one-off complaints or stale intermediate reasoning.

## Internal Discovery Modes

`/skill-audit` benefits from four internal helper modes when the audit is strategy-heavy or pattern-heavy:

- `trace`: reconstruct how a contract, recommendation, or failure pattern evolved across prior turns, artifacts, and corrections
- `challenge`: run a bounded adversarial pass against the current recommendation or reuse judgment
- `emerge`: identify latent recurring patterns that are visible across findings but not yet named explicitly
- `graduate`: promote repeated lessons into durable improvement artifacts for `/skill-ship`, validators, hooks, or tests

Use them selectively:
- prefer `challenge` for high-blast-radius audits, transfer/reuse analysis, and merge/remove decisions
- prefer `emerge` when multiple findings point to the same hidden failure class
- prefer `graduate` when the same gap keeps recurring and should become durable enforcement
- use `trace` when the skill's current shape only makes sense in light of prior decisions or corrections

These are internal reasoning passes, not user-facing workflow steps.

Reference: `P:/.claude/skills/__lib/sdlc_internal_modes.md`

## How to Use

```
/skill-audit <target>    # Audit a skill by name
/skill-audit /arch       # Audit /arch
/skill-audit /rca        # Audit /rca
```

## Audit Modes

Before applying the lenses, `/skill-audit` should classify what decision the user actually needs. Do not default to "audit the target as a shipping unit" if the request is really about reuse, migration, or removal.

Primary modes:

1. **Target-Quality Audit**
   Use when the user is asking whether the target skill itself is healthy, trustworthy, or correctly shaped.
   Typical questions:
   - "please review /gitready"
   - "audit /arch"
   - "is this skill over-specified?"

2. **Transfer / Reuse Analysis**
   Use when the user is asking what parts of one skill should be reused in others.
   Typical questions:
   - "does `/adf` have value for `/skill-audit`, `/skill-ship`, or any other skill?"
   - "what parts of this skill should be copied elsewhere?"
   - "what principles should survive if we remove this skill?"

   In this mode, the central question is not "is the target itself shippable?" It is:
   - what principles, checks, prompts, or contracts are reusable?
   - where should they go?
   - what should not be copied?
   - what is the ROI of copying them?

   A docs-only or prose-heavy skill can have high transfer value even if it has little shipping value.

   Required target-discovery workflow:
   1. Find **direct consumers or explicit references** first.
      - search other skills for `/<source-skill>` mentions, delegation rules, route targets, and suggest links
      - these targets should be listed before any abstract reuse ideas
   2. Extract **principle families** from the source skill.
      - examples: structural justification, assurance/evidence, workflow orchestration, contract enforcement, learning/improvement
   3. Find **indirect candidates** even when they do not reference the source skill.
      - look for skills whose role, category, or contracts would benefit from those principle families
      - do not require a direct consumer link
   4. Separate **principles** from **presentation/framework baggage**.
      - copy principles, not branding, rituals, or brittle scaffolding
   5. Rank outputs in this order:
      - direct migration targets
      - indirect beneficiaries
      - do not copy

   If a direct consumer exists, failing to name it is an audit miss.

   Required judgment workflow after discovery:
   1. Treat deterministic discovery as the **candidate set**, not the final decision.
  2. Apply semantic/LLM judgment to the bounded indirect queue:
      - which skills are true migration targets?
      - which only deserve a lighter subset?
      - which are merely related but not worth changing?
      - when available, prefer embedding-backed daemon ranking as an input to this step, not as a replacement for judgment
      - for high-ambiguity or high-ROI transfer questions, run a bounded critique subagent over the shortlisted candidates before final ranking
   3. Keep all explicit direct consumers visible unless you explicitly reject them with a reason.
   4. Do not let raw lexical overlap or score order become the final answer without judgment.
   5. Direct consumers and direct references remain authoritative hard links. Embedding or semantic ranking may refine indirect candidates, but it must not override explicit dependencies.

3. **Merge / Remove / Migrate Analysis**
   Use when the user is deciding whether a skill should be removed, absorbed into another skill, or split apart.
   Typical questions:
   - "I'd like to remove `/adf`, what should move into `/arch`?"
   - "should these two skills merge?"
   - "what should be kept vs deleted?"

4. **Implementation-Readiness Audit**
   Use when the design is mostly accepted and the user needs to know what still blocks reliable implementation or rollout.

### Out-Of-Scope Request Types

`/skill-audit` should not pretend a creation or synthesis request is an audit just because a skill name is mentioned.

If the user is asking to:
- create a new skill
- assemble the "best version" of a skill from source material
- synthesize a new skill spec from notebooks, references, or examples
- scaffold or implement the resulting skill

then `/skill-audit` should **not** self-audit or emit a rewritten SKILL.md as if that were an audit result.

Instead:
1. briefly say this is a **skill synthesis / creation** request, not a pure audit
2. if useful, extract a short list of audit constraints or reusable principles
3. route the build work to `/skill-ship` or the skill-creation workflow

Creation/synthesis is allowed to use audit findings as input, but the output should be:
- a design brief
- a build handoff
- or a route to the implementation skill

not a self-audit of `/skill-audit` unless the user explicitly asked to audit `/skill-audit`.

### Target Anchoring Rule

When the user says "the skill", "this skill", "best version", or similar shorthand:
- anchor to the most recent explicit **non-`/skill-audit` target** in the conversation
- do not silently reinterpret the target as `/skill-audit` just because `/skill-audit` is the current running skill

If the anchor is still genuinely ambiguous after that rule, ask one short clarifying question.

If the request mixes modes, say so briefly and prioritize the mode that makes the user's next decision easiest.

## Lenses

See `references/lenses.md` for full lens definitions. Thirteen lenses:

1. **Reference Integrity** — does what SKILL.md promises to exist actually exist?
2. **Process Enforcement** — are workflow steps backed by actual Python code?
3. **Command Discipline** — does the skill use input gates, path enumeration, predictable errors, and single-responsibility scope?
4. **Structural Justification** — are added boundaries, hooks, abstractions, or layers justified by concrete failures and explicit tradeoffs?
5. **Template System** — prose vs programmatic template composition
6. **Model Variance Risk** — would different LLMs execute differently?
7. **Contract Completeness** — are SDLC primitives fully used?
8. **Skill Contract Consistency** — do frontmatter, footer, and body agree?
9. **Mechanism Leakage** — does policy text hardcode brittle runtime mechanics?
10. **Question Strategy** — do open-ended questions fit the skill's role?
11. **Operational Resilience** — is the skill multi-terminal safe, stale-data-aware, compact-resilient, and deliberate about cognitive hooks?
12. **Assurance Strategy** — does the skill use the right critique-agent and smoke-test contracts for its job?
13. **Non-Goals Clarity** — is scope explicitly defined?

## Boundary With /skill-ship

Use `/skill-audit` when the hard question is **rightness**:
- Is this the right skill?
- Is the strategy sound?
- Are the contracts and enforcement model correct?
- Is the outcome likely to satisfy the goal?

Use `/skill-ship` when the hard question is **correctness**:
- Did we build the intended skill properly?
- Are the files, hooks, tests, and integrations implemented correctly?
- Is the shipped artifact ready to rely on?

## Open-Ended Questions

Open-ended questions are appropriate in `/skill-audit` when they help test or improve the design space.

Good open-ended questions for `/skill-audit`:
- What problem is this skill actually trying to solve?
- What would a better outcome look like for the user?
- If this skill did not exist, what would we build instead?
- What assumptions are we making about scope, triggers, or enforcement?
- Where is the design fighting the workflow instead of fitting it?
- What responsibilities here should belong to another skill, hook, or validator?
- What would make this skill unnecessary?
- What failure would be most embarrassing six months from now?
- What breaks under multi-terminal concurrency, stale-data exposure, or stale state?
- Which cognitive or reasoning hooks belong here, and which should stay out?
- Is the reasoning depth too shallow or too heavy for the kind of decisions this skill makes?

Avoid open-ended questions in `/skill-audit` when they collapse into local implementation trivia, such as exact helper names, file splits, or hook filenames. Those belong to `/skill-ship`.

## Blind-Spot Prompts

Before finalizing an audit on a strategy-heavy target, `/skill-audit` should ask itself a short set of internal blind-spot questions:

- What important failure mode is still being left to reviewer interpretation?
- What would a weaker or faster model most likely misunderstand here?
- Which decisions are still implicit but materially affect downstream execution?
- What does this skill claim to guarantee that it does not yet enforce?
- What part of this skill would still drift if the docs stayed right but the validator stayed unchanged?
- Am I evaluating the target itself, or evaluating what should be learned from it?
- Is this really a target-quality audit, or is it transfer/reuse analysis in disguise?
- Am I dismissing reusable principles just because the source skill is docs-first or prose-only?
- What prior decision or correction most changed the shape of this recommendation? (`trace`)
- What is the strongest objection or counterexample to my current recommendation? (`challenge`)
- What repeated pattern is visible across these findings that I still have not named cleanly? (`emerge`)
- What repeated lesson should leave this audit as a durable validator, hook, test, or workflow rule? (`graduate`)

When auditing another skill, `/skill-audit` should also judge whether that target has an equivalent internal self-check mechanism where one is warranted. Strategy-heavy, routing-heavy, or architecture-heavy skills should not rely entirely on unstated judgment.

Role-specific prompt expectations:
- RCA-heavy skills should carry internal competing-cause prompts.
- Implementation-heavy skills such as `/code` should carry internal implementation-risk prompts.
- TDD/testing-heavy skills should carry internal test-truth prompts.
- Action-extraction/advisory skills such as `/rns` should carry internal action-extraction prompts.
- Adversarial/pre-mortem skills should carry internal failure-mode prompts.
- Next-step advisory skills such as `/gto` should carry internal next-step integrity prompts.
- Session catch-up skills such as `/recap` should carry internal catch-up integrity prompts.
- Lesson-capture skills such as `/learn` should carry internal lesson-quality prompts.
- Retrospective orchestrators such as `/retro` should carry internal retrospective-integrity prompts.
- Reflection/self-improvement skills such as `/reflect` should carry internal reflection-upgrade prompts.

These are internal self-check prompts. They are not default user-facing questions and should not be turned into user interrogations unless the skill is truly blocked and cannot proceed safely without clarification.

## Output

The exact framing of the output should match the chosen audit mode. Do not force every result into a target-health verdict if the user really asked for reuse or migration guidance.

Common outputs after a single audit pass:

**Outcome Summary** — always first, short and decision-oriented:

- verdict (`HEALTHY`, `TARGETED CLEANUP`, `KEEP THE SKILL, HARDEN EXECUTION`, or `RIGHT IDEA, WRONG CONTRACT`)
- one-sentence rationale
- all distinct next moves, priority-ordered, with owner

If `/skill-audit` cannot tell the operator what to do next, the audit is incomplete even if the lenses are correct.

When the highest-priority actionable owner is not `source skill`, `/skill-audit` must also emit:
- `Recommended Handoff`
- `Recommended Next Skill`
- one-sentence `Why`
- a short scoped handoff list containing only the actions that target skill should own next

If the next owner is `/skill-ship`, make that handoff explicit instead of leaving `/skill-ship` buried in the owner column.

For creation/synthesis requests that were misrouted into `/skill-audit`, do not emit a fake audit verdict. Instead emit:
- `Request Type: Skill Synthesis / Creation`
- `Target Skill: ...`
- `Reusable Constraints / Principles`
- `Recommended Next Skill`
- `Build Handoff`

**Gap Table** — one row per lens finding:

| Lens | Gap | Evidence | Owner | Priority |
|------|-----|----------|-------|----------|
| REFERENCE | missing refs/evals.md | file not found | source skill | HIGH |

**1-Page Improvement Plan** — concrete next actions per lens, prioritized, with ownership guidance (`source skill`, `skill-ship`, or `skill-audit`).

When in **Transfer / Reuse Analysis** or **Merge / Remove / Migrate Analysis**, add an explicit reuse/migration section:

- **Direct migration targets**
- **Indirect beneficiaries**
- **Copy to X**
- **Copy a lighter subset to Y**
- **Do not copy**
- **Keep only in source skill**

For transfer/reuse questions, the workflow is two-stage:
- **Stage A — deterministic discovery**: find explicit links and plausible indirect candidates
- **Stage B — semantic judgment**: judge the discovered candidates and decide what should actually be reused

Those sections should be principle-level unless the user explicitly asks for file-by-file implementation edits.

**Improvement Signals** — durable lessons that should survive the current chat:

| Pattern | Symptom | Root Cause | Recurrence | Best Fix Layer | Owner |
|---------|---------|------------|------------|----------------|-------|
| [pattern] | [what keeps happening] | [why] | [count/qualitative] | [doc/validator/hook/test/arch] | [owner] |

When useful, emit a structured lesson artifact using the schema in `references/learning-loop.md`.

## Implementation

- **No phases** — single pass through all 13 lenses
- **No policy routing** — always runs all 13 lenses
  - **Bounded critique subagents when warranted** — default to direct file glob/read/search, but use a narrowly scoped critique pass for strategic, routing, transfer, or high-blast-radius audits
- **Structured spec parsing** — parse frontmatter/body/footer before applying lenses
- **Docs-first aware** — treat `SKILL.md` as a first-class contract artifact, not just Python backing
- **Compact-resilient** — completes within one response window
- **Operationally opinionated** — flags missing multi-terminal/stale-data/compact-resilience contracts for stateful or hook-oriented skills
- **Learning-oriented** — mines transcripts for candidate lessons, but only promotes repeated, verified patterns into durable artifacts

## Files

```
skill-audit/
├── SKILL.md              # This file
├── audit.py             # Router + glob/read/search + LLM synthesis
├── validate.py          # Basic shape validation (pre-audit check)
├── references/
│   ├── lenses.md        # 11 lenses verbatim
│   ├── learning-loop.md # Transcript mining + lesson artifact schema
│   └── examples.md     # Sample audits
└── tests/
    └── test_audit.py    # Regression coverage for all lens classes
```
