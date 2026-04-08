# /skill-audit — Sample Audits

## Example 1: /rca (hypothetical audit)

```
| Lens                        | Gap                                          | Priority |
|-----------------------------|----------------------------------------------|----------|
| REFERENCE_INTEGRITY         | missing reference: evals.md                  | HIGH     |
| PROCESS_ENFORCEMENT          | unbacked promise: 'av2'                      | MEDIUM   |
| NON_GOALS_CLARITY           | Non-Goals section missing                     | LOW      |
```

**Improvement Plan**
1. **REFERENCE_INTEGRITY** (HIGH): Add `evals.md` to references/ directory
2. **PROCESS_ENFORCEMENT** (MEDIUM): Verify av2 import exists in routing.py

---

## Example 2: /arch (hypothetical audit)

```
| Lens                        | Gap                                          | Priority |
|-----------------------------|----------------------------------------------|----------|
| CONTRACT_COMPLETENESS       | SDLC primitive not used: handoff_store      | MEDIUM   |
| MODEL_VARIANCE              | vague directive: 'optimize for clarity'      | MEDIUM   |
```

**Improvement Plan**
1. **CONTRACT_COMPLETENESS** (MEDIUM): Add handoff_store usage for cross-session state
2. **MODEL_VARIANCE** (MEDIUM): Replace "optimize for clarity" with explicit criteria

---

## Example 3: /gto (hypothetical audit)

```
| Lens                        | Gap                                          | Priority |
|-----------------------------|----------------------------------------------|----------|
| REFERENCE_INTEGRITY         | missing references: gap_skill_mapper.md     | HIGH     |
| PROCESS_ENFORCEMENT          | unbacked promise: 'Layer 2 subagent'         | MEDIUM   |
| NON_GOALS_CLARITY           | Non-Goals section present and clear           | —        |
```

**Improvement Plan**
1. **REFERENCE_INTEGRITY** (HIGH): Add gap_skill_mapper.md to references/
2. **PROCESS_ENFORCEMENT** (MEDIUM): Verify Layer 2 subagent invocation exists in code

---

## Example 4: Transfer / Reuse Analysis for /adf

User question:

`Does /adf have value for /skill-audit, /skill-ship, or any other skill?`

Correct framing:

- This is **not** mainly a target-quality audit.
- This is **Transfer / Reuse Analysis**.
- The useful answer is about reusable principles, placement, and ROI.
- Discovery alone is not enough; the top candidates still need semantic judgment.

Useful output shape:

```
Outcome Summary
- verdict: TRANSFER VALUE EXISTS
- rationale: /adf is mostly a prose decision framework, so its main value is reusable structural-justification logic rather than shipping mechanics.
- next moves:
  - migrate ADF delegation from /arch into native /arch scope-check logic
  - copy structural-justification principles into /skill-audit
  - copy a lighter anti-complexity checkpoint into /skill-ship
  - consider a lighter subset for /arch and /planning
  - do not copy ADF branding, full ritual, or CKS-specific scaffolding

Direct migration targets
- /arch
  - direct reason: it explicitly delegates extraction/justification questions to /adf
  - migrate: scope check, concrete-failure test, simpler-alternative check, complexity brake

Indirect beneficiaries
- /skill-audit
  - absorb structural-justification principles as an audit lens
- /skill-ship
  - absorb only a lighter anti-complexity checkpoint
- /planning
  - use a smaller subset when plans propose new hooks, layers, or validators

Copy to /skill-audit
- scope check
- concrete failure/prevention check
- simpler-alternative check
- complexity tradeoff
- durability/reversibility check

Copy a lighter subset to /skill-ship
- what failure does this added structure prevent?
- is there a simpler implementation?
- what complexity does this add?
- is it easy to undo?

Other skills that may benefit
- /arch
- /planning
- /rca

Do not copy
- framework branding
- mandatory ritualized decision tree
- context-blind clarifying-question behavior
```

Why this is the right pattern:

- A docs-only skill can have high **transfer value** even if it has little direct shipping value.
- The audit should optimize for the user's decision, not for the nearest literal rubric.
- Deterministic discovery should generate the candidate set; semantic/LLM judgment should decide what actually gets reused.

---

## Example 5: Creation Request Misrouted Into /skill-audit

User question:

`Can you assemble a best version of /ai-gemini from these notebook findings?`

Wrong behavior:

- self-audit `/skill-audit`
- emit a rewritten `/skill-audit` SKILL.md
- treat "the skill" as meaning the currently running skill

Correct framing:

- This is **not** a target-quality audit.
- This is **skill synthesis / creation** with audit constraints as input.
- `/skill-audit` may extract reusable principles and constraints, but it should route the actual build work to `/skill-ship` or the skill-creation workflow.

Useful output shape:

```
Request Type
- Skill Synthesis / Creation

Target Skill
- /ai-gemini

Reusable Constraints / Principles
- use deterministic hard links for tool/integration claims
- use semantic/LLM judgment only for bounded indirect discovery
- keep direct CLI execution paths explicit and non-brittle
- define allowed tools, failure behavior, and stale-data boundaries clearly

Recommended Next Skill
- /skill-ship

Build Handoff
- create a docs-first Gemini integration skill
- support explicit invocation phrases like "ask gemini" / "analyze with gemini"
- keep the execution path narrow and explicit
- decide whether this should be a slash command, a skill, or both
- if both, document trigger distinctions so the two entry points do not overlap confusingly
```

Why this is the right pattern:

- The user asked for a **new artifact**, not a verdict on `/skill-audit`.
- Audit can constrain the build, but it should not substitute for the build.
- Ambiguous shorthand like "the skill" should anchor to the most recent explicit external target (`/ai-gemini`), not to `/skill-audit` itself.
