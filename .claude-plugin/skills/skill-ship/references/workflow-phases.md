---
type: core
load_when: discovery
priority: mandatory
estimated_lines: 350
---

# Skill Complete - Detailed Workflow Phases

This document contains the detailed phase-by-phase instructions for the skill-ship workflow. See SKILL.md for overview and quick reference.

## Phase 0: Context Awareness

**Goal**: Detect session patterns, user corrections, and learning signals before starting skill work — lightweight, no external tools

**Questions to answer**:
1. Were there user corrections or broken-windows signals in this session related to skills?
2. Are there any active hooks or state that would affect skill execution?
3. Did recent conversation show any recurring patterns about skill quality?
4. Is there terminal-scoped or session-scoped prior state that is safe to reuse, or should this run start fresh to avoid stale data?
5. What reasoning depth is justified for this run: low, medium, high, or max?

**Actions**:
1. **Scan recent conversation turns** (last 5-10 turns) for correction signals:
   - User said "no, not X" or "stop doing X" → flag as broken window
   - User said "yes exactly" or "perfect" → flag as validated pattern
   - User corrected trigger/output/format → note as quality requirement
2. **Read session state files**:
   - `.claude/hooks/.evidence/gto-state-*/` — GTO outputs from earlier session activity
   - `.evidence/skill-ship-state-{cwd_hash}/workflow-state.json` — **skill-ship's own terminal-scoped evidence** (if exists and fresh, read to detect interrupted workflow)
     - Contains: `target_skill`, `current_phase`, `quality_dimensions`, `workflow_started`
     - Only use if last_updated < 24 hours (stale state is worse than no state)
     - If interrupted workflow detected → surface as "resuming workflow for {target_skill}" before Phase 1
   - Prefer terminal/session-scoped evidence over shared global state; stale or cross-terminal state is worse than no state
3. **Extract signals** — Map detected patterns to specific skill quality concerns:
   - User corrected trigger accuracy → increase trigger validation rigor in Phase 3b
   - User flagged a missing feature → note as design requirement in Phase 2
   - User corrected output format → enforce template in Phase 4
   - User reported failure mode → add to Phase 3d artifact validation checks
4. **Operational resilience stance**:
   - If the target skill is stateful or hook-heavy, record whether it must be multi-terminal isolated, stale-data-immune, and compact-resilient
   - If the target skill appears stateless/read-only, record that explicitly so later phases do not add unnecessary state machinery
5. **Reasoning-depth stance**:
   - Choose the minimum reasoning depth that still protects quality:
     - `low` for rote deterministic edits
     - `medium` for normal implementation and repair
     - `high` for integration, operational resilience, contract-sensitive work, or evaluator/judge preparation
     - `max` only for unusually ambiguous implementation problems that still belong to shipping
   - For shipped skills, add or adjust `effort:` frontmatter when a stable reasoning-depth default will improve consistency

**Output Format**: Embedded in Phase 1 output

```markdown
### Session Correction Signals

| Signal | Location | Skill Quality Concern | Routed To |
|--------|----------|---------------------|-----------|
| [pattern] | turn N | [specific concern] | [phase] |

### Resumed from Evidence (if applicable)
If `.evidence/skill-ship-state-{cwd_hash}/workflow-state.json` was found and fresh (< 24h):
- **Resuming workflow for**: `{target_skill}`
- **Last completed phase**: `{current_phase}`
- **Quality dimensions**: `{quality_dimensions}`
- Surface this as: `→ Resuming skill-ship for {target_skill} — last completed: {current_phase}`

**Skip this phase when**: Fresh session with no prior skill work in the chat

---

## Phase 1: Discovery & Intent

**Goal**: Understand what the user wants to accomplish

**Questions to answer**:
1. What should this skill enable Claude to do?
2. When should this skill trigger? (user phrases/contexts)
3. What's the expected output format?
4. Is this a new skill or improvement to existing?
5. Should we set up test cases for verification?

**Intent Extraction Rules (Critical)**:

**Possessive Repair Phrase Trap:**
When the user says "my skill isn't working" or "this skill is broken", the phrase "my skill" or "this skill" may be incorrectly extracted as a NEW skill name to create. **This is wrong.**

**Correct interpretation:**
- "my skill isn't working right" → REPAIR intent for an EXISTING skill (user wants help fixing a skill they already have)
- "this skill keeps failing" → REPAIR intent (possessive "this" refers to existing skill)
- "create a skill called my-skill" → NEW creation intent (explicit "create a skill called X")

**Rule:** Possessive adjectives ("my", "this") + broken/error/not-working keywords = REPAIR intent. Do NOT treat possessive phrases as skill names to create.

**If no specific skill is named in a repair phrase:** Ask the user "Which skill do you want me to help fix?" before proceeding.

**Python Skill Repair Diagnostic (run before Phase 2 when REPAIR intent + Python skill detected):**

When a Python skill has a `lib/` directory, two failure modes account for most "wrong output / empty results" bugs:

**Failure Mode 1 — Missing `lib/__init__.py` export**

```bash
python "P:/.claude/skills/<SKILL_NAME>/<main_script>.py" --help
```
- If `ImportError: cannot import name 'X' from 'lib'` → find the function: `grep -rn "^def X\|^class X" P:/.claude/skills/<SKILL_NAME>/lib/`
- If found in a `.py` file but absent from `lib/__init__.py` → add `X` to both `__all__` and the import statements
- Re-run `--help` to confirm fix

**Failure Mode 2 — SKILL.md routing to a degraded fallback script**

Read the `## EXECUTE` section of `SKILL.md`. If it lists two scripts (a primary and a "fallback for monorepo/subdirectories"), check the fallback script for disabled detectors (comment blocks with "Re-enable by uncommenting below"). If detectors are commented out:
- Update SKILL.md to remove the fallback routing — use the primary script for all targets
- Mark the fallback script as deprecated in a comment or SKILL.md note

**Verification**: Run the primary script with `--format markdown --no-subagents` on a real target. Confirm health score has dimension breakdown and gap count > 0 (not "Total Gaps: 0" from a script with disabled detectors).

**Actions**:
1. **Extract intent** from conversation if available
2. **CRITICAL**: Before assuming new creation, check for possessive repair phrases (see above)
3. **Boundary check before build**:
   - If the unresolved question is strategic, stop shipping and route to `/skill-audit`
   - Strategic questions include:
     - should this skill exist in this form?
     - should it be split, merged, or replaced?
     - is the trigger/scope boundary wrong?
     - is the enforcement model in the wrong place?
     - is the desired outcome model wrong?
3. **AUTOMATED CONFLICT DETECTION** (enforced):
   - Invoke `/similarity` skill automatically with skill description/intent
   - If similarity score ≥ 80%:
     - Display conflict table: | Existing Skill | Similarity | Overlapping Features |
     - Ask user: "Continue creating new skill OR enhance existing [skill-name]?"
     - If enhance: **Output feed-forward block** (see below), then route to `/skill-ship` with improvement intent for existing skill
     - If continue: Document overlap rationale and proceed with creation

**Enhance Existing — Feed-Forward Block**:
When user chooses "enhance existing", emit this structured block immediately after the decision:

```markdown
<!-- SKILL-SHIP FEED-FORWARD -->
<!-- TARGET_SKILL: [skill-name] -->
<!-- TARGET_PATH: [absolute path to SKILL.md] -->
<!-- INTENT: enhance -->
<!-- OVERLAP_FEATURES: [comma-separated list of overlapping features from similarity analysis] -->
<!-- USER_CORRECTIONS: [any corrections flagged by user during conflict review] -->
<!-- GTO_SIGNALS: [any Phase 0 signals relevant to this skill] -->
<!-- END FEED-FORWARD -->
```

Phase 2 reads this block as context instead of re-parsing the conversation. Do NOT proceed to Phase 2 creation without first incorporating the feed-forward context from this block.
3. Clarify output format requirements
4. Determine if objective verification is needed

**Output Format**: Use Template 2 (Executive Summary Format)

```markdown
# Discovery Summary

## Intent
[What the skill should do]

## Context
- Triggering phrases: [list]
- Output format: [description]
- Conflict detection: [similarity score / conflicts found / none]
- Test coverage: [yes/no with rationale]

## Similarity Analysis
[If conflicts detected:]
| Existing Skill | Similarity | Overlapping Features | Action |
|----------------|------------|---------------------|---------|
| [skill-name] | [score%] | [features] | [Enhance/Continue/New]

## Recommendation
[Proposed approach with skill type classification]
[If conflicts: Document decision rationale for creating new vs enhancing existing]
```

---

## Phase 1.5: Knowledge Retrieval

**Goal**: Retrieve relevant patterns, lessons, and research before building — with active NotebookLM enhancement scanning

**Questions to answer**:
1. What related patterns exist in CKS?
2. What enforcement mechanisms, hooks, agents, sub-agents, trigger strategies, output formats, and failure modes exist in NotebookLM that could strengthen this skill?
3. What relevant lessons are in memory.md?
4. What do existing skills/plugins teach about the inferred quality dimensions?

**Infer functional quality dimensions FIRST** — Before querying any knowledge source, read the skill description and infer which of these are relevant. These dimensions apply to ALL knowledge sources (CKS, NotebookLM, skills/plugins), not just NotebookLM:

  | Dimension | Trigger signals | What to look for |
  |-----------|----------------|------------------|
  | Robustness | Error handling, edge cases, race conditions mentioned | Failure modes, circuit breakers, retry logic |
  | Computational Efficiency | Large data, loops, repeated operations | N+1 patterns, caching, batch operations |
  | Token Efficiency | Sub-agents, large context, verbose outputs, repeated summaries | File-passing IPC, progressive disclosure, condensed formats (machine RNS), lazy context loading |
  | Safety | State mutations, file operations, shared data | Atomicity, locking, corruption prevention |
  | Observability | Diagnostics, debugging, health monitoring | Logging patterns, trace hooks, metrics |
  | Concurrency | Multi-terminal, shared state, parallel work | Terminal isolation, file locking, race conditions |
  | Recoverability | Undo, rollback, cleanup on failure | Transaction patterns, cleanup hooks, backup |
  | Self-Improvement | Repeated use, feedback signals, evolving requirements, lessons learned | Feedback loops, self-correction hooks, lesson capture to memory/CKS, adaptive thresholds |

**Flagged dimensions become Quality Commitments** — These are explicitly listed in the Phase 2 output and validated in Phase 3b.

**Actions**:
1. **Query CKS** for relevant patterns:
   - Extract key terms from skill intent/description
   - Run `/cks search "<domain>" "<keywords>"` for semantic search
   - Run `/cks search "<pattern_type>"` for hook/pattern/anti-pattern queries
   - **Also query CKS for each flagged quality dimension**: `/cks search "<dimension-name>" "<skill-domain>"` (e.g., `/cks search "concurrent safety" "terminal isolation"`)

2. **Query NotebookLM** (if available) — Intelligent Notebook Discovery:
   - Check `nlm auth status`
   - List notebooks: `nlm notebook list`
   - **Smart relevance selection** (use approach A or B):
     - **Approach A (describe + semantic match)** — Get topic depth:
       1. `nlm notebook describe <id>` on each candidate to get AI-generated topic summary
       2. Score by semantic relevance to skill intent (not just keyword overlap)
       3. Select top 2-3 by intent match, not title substring
     - **Approach B (inverted query — let NotebookLM route)** — Most elegant:
       1. Ask the most broadly-relevant notebook (e.g., "skills & patterns"): `nlm notebook query <id> "I need to build a skill that [skill description]. Which of my other notebooks would be most relevant and why?"`
       2. Use that response to identify 2-3 target notebooks
       3. This leverages NotebookLM's semantic retrieval instead of manual keyword matching
   - Run 5 targeted queries per selected notebook using `nlm notebook query <id> "<question>"`:

     | Query | Purpose | Example Question Template |
     |-------|---------|---------------------------|
     | Q1: Enforcement | Find hooks, quality gates, StopHook patterns | "What enforcement mechanisms or hooks appear in this corpus that could strengthen a skill that [skill description]?" |
     | Q2: Agents/Sub-Agents | Find agent patterns, subagent coordination, capability delegation | "What agent or subagent patterns are described here — e.g. specialized agents, tool orchestration, capability delegation — that could enhance a skill for [skill description]?" |
     | Q3: Triggers | Find trigger phrases, activation contexts, user intent signals | "What trigger phrases or user intents are described that might improve how a skill for [skill description] gets activated?" |
     | Q4: Output/Format | Find templates, formatting patterns, presentation strategies | "What output formats, templates, or presentation patterns appear here that could improve a skill's usability?" |
     | Q5: Gaps/Failure | Find edge cases, failure modes, missing features | "What failure modes, edge cases, or missing features are discussed that a skill for [skill description] should handle?" |

   - Synthesize findings: deduplicate across notebooks, rank by relevance to target skill
   - If a notebook has no relevant results for a query, note "no findings" rather than omitting the row

3. **Scan existing skills/plugins** for reusable patterns:
   - Use `/similarity <target-skill-name>` to find related skills by domain
   - Also scan directly: Glob `skills/*/SKILL.md` and `hooks/**/SKILL.md` for frontmatter `description` matching target domain
   - For each related skill found, read its implementation files (not just SKILL.md — look at `__lib/`, `scripts/`, `references/`)
   - Extract reusable patterns: interesting hooks, CLI patterns, data structures, phase designs
   - Deduplicate against what's already in CKS or NotebookLM findings
   - Rank by specificity and reuse feasibility

4. **Query memory.md**:
   - Read MEMORY.md topic index
   - Read relevant topic files based on keywords
   - Priority files: working_principles.md, discovery_patterns.md, skill_optimization_patterns.md

5. **Run dynamic agent ecosystem scan** (NEW — for agent creation opportunities):
   - Execute: `python scripts/list_agents.py --json` to discover all available agents at runtime
   - Use `--filter <domain>` to probe specific categories for white space
   - Compare discovered agents against the target skill's needed capabilities
   - **Gap analysis dimensions** (check each with `--filter`):
     - Token efficiency: agents that reduce context overhead (none found = opportunity)
     - Skill/workflow selection: agents that route/classify/match tasks to skills (none = opportunity)
     - Documentation: agents for README, API docs, code-to-doc sync (none = opportunity)
     - Onboarding: agents for new-developer orientation, codebase tour (none = opportunity)
     - API/database patterns: agents for REST design, schema, migrations (none = opportunity)
   - **Output a "Suggested New Agent Types" subsection** in the Knowledge Retrieval Summary identifying the highest-value agent gaps for this specific skill

6. **Query external discovery skills** (NEW):
   a. **Invoke `/search`** for CKS/NotebookLM patterns relevant to the target skill domain:
      - `/search "Claude Code subagent patterns skill automation"` — find related agent patterns
      - `/search "hooks best practices multi-agent orchestration"` — find hook/agent coordination patterns
   b. **Invoke `/usm`** for ecosystem discovery:
      - Use `/usm` to search SkillsMP, ClawHub, SkillHub, and skills.sh for skills matching the target domain
      - Also use `/usm` to discover plugins from marketplace and GitHub that have agent-type capabilities
      - Scan installed plugin agents via: `python scripts/list_agents.py --source plugin --json`
      - Report any found agent-type skills/plugins as "External Agent Opportunities"

**Output Format**: Use Template 2 (Executive Summary Format)

```markdown
## Knowledge Retrieval Summary

### CKS Results
[Relevant patterns found in CKS]

### NotebookLM Enhancement Scan

**Notebooks analyzed:** [list of notebook names/aliases]

| Enhancement Vector | Source Notebook | Finding | Applicable Phase |
|--------------------|-----------------|---------|------------------|
| Enforcement pattern | notebook-name | description | phase_3b hooks |
| Agents/Sub-Agents | notebook-name | description | phase_2 design, phase_3c |
| Trigger phrase | notebook-name | description | phase_1 triggers |
| Output format | notebook-name | description | phase_4 formatting |
| Gap/Edge case | notebook-name | description | phase_2 design |
| [new row for each finding] | | | |

**Notebooks with no relevant findings:** [list any notebooks where all 5 queries returned "no findings"]

### Existing Skills/Plugins Patterns
[Reusable patterns extracted from related skills/plugins, including hook patterns, CLI structures, data models, phase designs]

| Source Skill | Pattern | Reuse Feasibility | Applicable Phase |
|-------------|---------|-------------------|-----------------|
| skill-name | description | high/medium/low | phase_2 design |

### Memory.md Results
[Relevant topic files and lessons]

### Agent Ecosystem Scan
**Total agents discovered:** [from list_agents.py --json count]
**By source:** [user_p_drive, user_home, plugin_p_drive, plugin_home, builtin counts]

| Capability Area | Agents Found | White Space? | Opportunity |
|-----------------|-------------|--------------|-------------|
| [e.g. Token Efficiency] | [existing agents or "none"] | yes/no | [description if gap] |

**Suggested New Agent Types:** [Bullet list of specific agent types that would add most value for this skill — name, focus, and why it would help]

### External Discovery (Search + USM)
**`/search` findings:** [relevant agent/skill patterns from CKS/NotebookLM via /search]

**`/usm` findings:** [relevant skills or plugins discovered from SkillsMP/ClawHub/SkillHub/skills.sh and GitHub]

### Recommendations
[What patterns/lessons should be incorporated into the skill — include agents/sub-agents recommendations here]
```

**NotebookLM Query Guidelines**:
- Always substitute `[skill description]` with a concrete 1-2 sentence summary of what the skill does
- If a notebook contains no relevant findings, still include it in the table with "no findings" rather than omitting
- Deduplicate findings that appear across multiple notebooks — combine into a single row listing all source notebooks
- Rank recommendations by: (1) specificity to the skill domain, (2) evidence strength in source, (3) feasibility of implementation

**Skip this phase when**:
- Simple skills (<5 steps, straightforward execution)
- User explicitly declines knowledge retrieval
- Domain has no existing CKS/memory entries

<!--STATE_SAVE: After Phase 1.5 completes (or skips), write to `.evidence/skill-ship-state-{cwd_hash}/workflow-state.json`:
{"target_skill": "<skill_path>", "quality_dimensions": [<dim1>, ...], "current_phase": "1.5_complete", "skip_reason": null | "simple_skill" | "user_declined" | "no_existing_entries", "workflow_started": "<ISO_timestamp>", "last_updated": "<ISO_timestamp>"}
This enables compaction resilience — if session is compacted during Phase 2+, resume from this state.
CRITICAL: skip_reason MUST be set if Phase 1.5 was not executed. Phase 2 gate checks this field.-->

---

## Phase 1.7: Policy Routing

**Goal**: Classify artifact type and blast radius, emit explicit required_phases from policy config

**Input**: artifact metadata, user intent classification, skill type

**Action**:
1. Read `config/policy.json`
2. Match artifact type to `artifact_types` keys:
   - `prompt_skill`: user is tweaking trigger phrasing, output format, or description — minimal validation
   - `new_skill`: user is creating a net-new skill — full pipeline recommended
   - `orchestrator`: skill delegates to subagents, dispatches tasks, or coordinates other skills — high risk, adversarial review warranted
   - `contract_change`: skill changes a protocol, contract primitive, or hook interface — highest risk
   - `distribution_update`: user is only updating docs, metadata, or sharing config — lightweight
3. **If key found**: emit `required_phases` and `risk_level` from that entry
4. **If key NOT found**: emit `default.phases` and `default.risk_level` (no error — unknown types use default gracefully)

**Output**:
```json
{
  "required_phases": ["3a", "3b", "3c", "3e", "3f"],
  "risk_level": "medium",
  "matched_artifact_type": "new_skill"
}
```

**Note**: Phase 1.7 output is stored in workflow state and read by subsequent phases to determine which validation gates to enforce. The evaluator (3e) and judge (3f) phases are **subagent-only** — no Python implementations exist. Classification is performed by the orchestrator reading `config/policy.json` and routing accordingly.

**Provenance requirement**: Every finding or claim in Phase 1.7 output must be tagged with `provenance: "this_run" | "prior_premortem" | "prior_manual_review"`. Do not assert "not documented" or "does not exist" without fresh tool verification this session. See `references/evaluator-judge-prompts.md` for provenance field specification.

**Policy tuning**: To tune artifact type mappings over time, log per-run: artifact type, risk_level, phases run, final decision, and any override rationale. Periodic sampling (e.g., monthly) lets you tighten high-risk mappings for frequently-seen patterns or relax low-risk mappings that never fail. See `references/policy-tuning.md` for the lightweight tuning workflow.

**Skip this phase when**: Artifact type is trivially determined (e.g., user says "just fix a typo in my skill" — skip routing, use `prompt_skill` defaults directly).

**Goal**: Create or update the skill structure

**⚠️ Phase 1.5 Gate — MUST SATISFY BEFORE PROCEEDING:**

Before beginning Phase 2, verify ONE of the following:
1. **Phase 1.5 output present** — Knowledge Retrieval Summary appears in conversation or workflow state with CKS results, NotebookLM Enhancement Scan table, and Memory.md results
2. **Phase 1.5 skipped with logged reason** — Check workflow state for skip reason matching one of the defined `skip_when` conditions:
   - `simple_skill`: Skill has <5 steps and straightforward execution
   - `user_declined`: User explicitly declined knowledge retrieval
   - `no_existing_entries`: Verified via `/search` that domain has no CKS/memory/notebook entries

**If neither condition is met** — Phase 1.5 was silently skipped. DO NOT proceed to Phase 2. Execute Phase 1.5 now or document the skip reason in workflow state.

**Enforcement rationale**: Phase 1.5 is the knowledge-retrieval safety net — skipping it means building without access to lessons, patterns, and enforcement mechanisms already documented in CKS/NotebookLM. The violation cost is paid in repeated mistakes across skill iterations.

**Skill Coordination**:
- Invoke **skill-creator** for draft creation and test prompt generation
- Invoke **skill-development** for SKILL.md structure and best practices
- Use **display_templates.md** for output formatting guidance

**Actions**:
1. Create SKILL.md with proper YAML frontmatter
2. **Set Degrees of Freedom** (NEW):
   - Add `freedom: high|medium|low` field to YAML frontmatter
   - **High freedom** (text-based instructions): Multiple approaches valid, decisions depend on context
   - **Medium freedom** (pseudocode/scripts with parameters): Preferred pattern exists, some variation acceptable
   - **Low freedom** (specific scripts, few parameters): Operations fragile, consistency critical
3. Apply progressive disclosure pattern (keep under 500 lines)
4. Choose appropriate output format template from display_templates.md:
   - Template 1: Strict Analysis Format (API-like)
   - Template 2: Executive Summary Format (flexible)
   - Template 3: Hypothesis Testing Format
   - Template 4: Comparison Format
   - Template 5: Workflow Progress Format
   - Template 6: Error Analysis Format
   - Template 7: Research Findings Format

**Output Format**: Use Template 1 (Strict Analysis Format)

```markdown
## Skill Structure Analysis

**Confidence:** [Score]% (Tier [1-4])

### Skill Classification
**Type:** [EXECUTION/KNOWLEDGE/PROCEDURE]
**Freedom Level:** [high/medium/low]
**Complexity Score:** [calculated score]
**Hook Recommendation:** [yes/no with rationale]

### Structure
- YAML frontmatter: ✓
- Description quality: [assessment]
- Progressive disclosure: [assessment]
- Output format template: [Template #]

### Evidence
| Aspect | Status | Notes |
|--------|--------|-------|
| Triggers | [status] | [details] |
| Workflow | [status] | [details] |
| Output | [status] | [details] |
| Tests | [status] | [details] |

### Quality Commitments
[List of flagged dimensions from Phase 1.5 that the skill must address — each dimension listed with how the design addresses it]

| Dimension | Commitment | Validation |
|-----------|-----------|-----------|
| [e.g., Token Efficiency] | [e.g., File-passing IPC instead of content passing] | Phase 3b checks for IPC patterns |
```

**Design Adequacy Check** (before finalizing Phase 2 output):

Before passing to Phase 3a, apply these reflective questions to the drafted skill:
1. **"Is this the best design for the stated goal, or the first design that seemed to work?"** — If the answer is "first plausible," iterate on the structure before proceeding
2. **"Would a user find this genuinely useful, or just technically functional?"** — Technically functional is the floor, not the target
3. **"What would I cut if this had to be half as long?"** — If nothing, the skill is too thin. If everything, the skill is too broad

If the draft fails any of these checks: revise before Phase 3a. Do not pass inadequate designs to validation — fix them at creation.

**ACEF Command Discipline Check** (before leaving Phase 2):

- if inputs can be vague, define the quality gate
- if the skill branches or routes, enumerate the execution and failure paths
- if block/error paths exist, standardize their wording
- if the skill appears to span multiple responsibilities, either narrow it or document the scope guard
- if the draft adds new hooks, validators, controllers, layers, or helper systems, justify the added complexity with:
  - a concrete failure/prevention case
  - a simpler-alternative check
  - an explicit complexity cost
  - a reversibility check

---

## Phase 3: Quality & Validation

**Goal**: Ensure skill meets quality standards

**Boundary rule**: Phase 3 evaluates implementation correctness and readiness. If any finding concludes the strategy, trigger/scope, enforcement placement, or outcome model is wrong, emit that as a strategic defect and route to `/skill-audit` instead of continuing redesign inside `/skill-ship`.

**Skill Coordination**:
- Invoke **testing-skills** for trigger and execution path validation
- Invoke **av** for hook generation and improvement analysis
- Run test prompts if configured

**Quality Validation Integration**:

1. **Skill Validation** (recommended):
   - Invoke `/testing-skills` with skill path for validation
   - Testing-skills will verify: YAML completeness, trigger accuracy, constitution links
   - Review validation report and address critical issues before proceeding

2. **Manual Verification Checks** (always performed):
   - **YAML frontmatter**: Verify name, description, triggers, category present
   - **Description quality**: Check ≤100 characters (registry constraint)
   - **Trigger phrases**: Test that phrases actually invoke the skill
   - **Constitution links**: Ensure skill declares which PARTs it extends
   - **Execution paths**: Walk through workflow steps to verify they complete
   - **`execution_hint` alignment** (NEW - catches aspirational tool declarations):
     - Parse `execution_hint` for explicit tool declarations (e.g., `Agent tool:`, `Bash tool:`, `Skill tool:`)
     - If `execution_hint` declares a tool, verify the execution flow actually contains that tool's invocation syntax (e.g., `Agent(...)`, `Bash(...)`, `Skill(...)`)
     - Precedent: Integration Verifier catches `suggest:` pointing to non-existent skills — same philosophy applies to tool declarations
     - Failure mode: `execution_hint: "Agent tool:..."` but no `Agent(...)` call in execution flow → gitbatch-style failure where orchestrator waits for instruction instead of executing

3. **Integration Check** (for orchestrated skills):
   - Verify all skills in `suggest:` field actually exist
   - Use `/similarity` to check for redundant/conflicting skills
   - Document any gaps or overlaps

4. **Progressive Disclosure** (enforced for >300 lines):
   - If SKILL.md exceeds 300 lines, move detailed content to references/
   - Keep main workflow in SKILL.md, advanced guides in references/

5. **Isolation Testing** (NEW - critical safety check):
   - Spawn sub-agent with ONLY the test skill
   - Run 2-3 representative tasks in isolated context
   - Verify: No environment mutations, no side effects
   - Check: Skill executes without affecting user's environment

**Actions**:
1. **Skill validation** (recommended):
   - Invoke `/testing-skills` with skill path
   - Review validation report for critical issues
   - Address FAILED checks before proceeding

2. **`execution_hint` alignment check** (NEW - catches aspirational tool declarations):
   - If `execution_hint` contains `Agent tool:`, `Bash tool:`, or `Skill tool:` → verify the execution flow has the corresponding `Agent(...)`, `Bash(...)`, or `Skill(...)` invocation syntax
   - Precedent: Integration Verifier for `suggest:` field
   - Failure mode: gitbatch — `execution_hint: "Agent tool:..."` but Step 3 only prose-described agent spawning without `Agent(...)` call

2. **Integration verification** (if orchestrated):
   - Check all skills in `suggest:` field exist
   - Use `/similarity` to detect redundancy/conflicts
   - Document any integration gaps

3. **Absence claim verification** (if claims present):
   - Use Read/Grep tools to verify absence claims
   - Require Tier 1 or Tier 2 evidence before accepting
   - Flag unverified claims for user correction

4. **Test trigger phrases** (MANDATORY — no caveats):
   - For each trigger in the target's `triggers:` field, verify it matches at least one positive example from user utterances
   - Run `/similarity` with the trigger phrase to confirm it is semantically reachable by users
   - Also test negative cases: verify known non-matching phrases do NOT activate the skill
   - If triggering fails: optimize description and re-test before declaring Phase 3c complete
   - This step is NOT conditional — all skills have triggers, all triggers must be tested

5. **Check progressive disclosure** (if SKILL.md >300 lines):
   - Verify main content in SKILL.md, details in references/
   - If not compliant: Move content to references/ and restructure

6. **Isolation testing** (NEW - critical safety check):
   - Spawn sub-agent with ONLY the test skill
   - Run 2-3 representative tasks
   - Verify: No environment mutations, no side effects
   - Check: Skill executes in isolated context

7. **Generate hooks** (if complexity score ≥ 1):
   - Invoke **av** for hook generation
   - Apply StopHook for multi-phase workflows
   - Apply PreToolUse hooks for execution requirements

8. **Suggest/refer integrity check** (MANDATORY):
   - Check all skills in `suggest:` and `depends_on_skills:` fields exist in the skills registry
   - For each skill found in any `suggest:` field, verify the reciprocal: does that skill also list the current skill in ITS `suggest:`? If not, add it
   - Grep all skills: `grep -r "^\s*- /{skill_name}:" skills/*/SKILL.md` to find candidates for reciprocation
   - This prevents orphaned skills where Skill A mentions Skill B but Skill B doesn't mention Skill A
   - Document gaps: list skills with missing reciprocations as integration findings

**Output Format**: Use Template 3 (Hypothesis Testing Format)

```markdown
## Quality Validation

| Test | Status | Evidence | Fix |
|------|--------|----------|-----|
| YAML completeness | ✓/✗ | [details] | [action if needed] |
| Trigger accuracy | ✓/✗ | [details] | [action if needed] |
| Output consistency | ✓/✗ | [details] | [action if needed] |
| Execution flow | ✓/✗ | [details] | [action if needed] |
| Quality Commitments | ✓/✗ | [details] | [action if needed] |
| Absence claim verification | ✓/✗ | [details] | [action if needed] |
| Isolation testing | ✓/✗ | [details] | [action if needed] |
| Test coverage | ✓/✗ | [details] | [action if needed] |

### Selected Issues
**Priority:** [High/Medium/Low]
**Issue:** [Description]
**Fix:** [Specific action]

### Validation Plan
1. [Validation step 1]
2. [Validation step 2]
3. [Validation step 3]
```

---

## Phase 3d: Artifact Quality Validation (Conditional)

**Goal**: Validate downstream artifact quality when target skill emits durable artifacts

**Activation Check** — Activate Phase 3d if ANY of the following are true (skip if none):

- [ ] `produces_artifact: true` in SKILL.md frontmatter
- [ ] Description contains "produces" or "artifact" keywords (e.g., "Produces plan artifacts", "emits reports")
- [ ] Workflow steps reference file outputs with artifact names (e.g., `plan.md`, `review.findings.json`, `*.report.md`)
- [ ] Skill category is `planning`, `reporting`, or `analysis`

**If none apply → Skip Phase 3d** UNLESS:
- Skill touches state mutations (file writes, shared data, terminal state) even if output is transient — in that case, apply Safety + Concurrency dimension checks from Quality Commitments
- In that case: run only the relevant rubric criteria (Safety, Concurrency), skip the rest

**Actions**:
1. **Load artifact-rubric.md** — the 5-criterion quality bar for artifact-emitting skills
2. **Locate the artifact** — Find the primary output file(s) the skill produces
3. **Apply the 5 checks**:
   - Single-purpose: artifact addresses one goal, not multiple
   - No raw findings: audit logs/review output synthesized, not pasted verbatim
   - No placeholder residue: no `{{TODO}}`, `[UNRESOLVED]`, unresolved markers
   - Contradiction-free: status is internally consistent (e.g., "ACCEPTED" = no P0 blockers)
   - Decision-complete: all P0/P1 findings incorporated or explicitly deferred with rationale
4. **Synthesize findings** — Do not append raw check output; summarize by criterion

**Blocking gate**: Phase 4 is blocked until `ARTIFACT_PASS` (all P0/P1 criteria met).

**Output Format**:
```markdown
## Artifact Quality Validation

| Criterion | Result | Details |
|-----------|--------|---------|
| Single-purpose | ✓/✗ | [details] |
| No raw findings | ✓/✗ | [details] |
| No placeholder residue | ✓/✗ | [details] |
| Contradiction-free | ✓/✗ | [details] |
| Decision-complete | ✓/✗ | [details] |

### Verdict
**ARTIFACT_PASS** or **ARTIFACT_FAIL** — [list failures if any]
```

---

## Phase 3.5: Evaluation & Iteration

**Goal**: Validate skill performance through empirical testing and iteration

**Choose Evaluation Mode** (NEW):

**Trial Mode** (before installing):
- Test-drive skill with 2-3 representative tasks
- Evaluate: Does it help? Clear instructions?
- Decision: keep, pass, or try another
- Use case: "Try before commit" - quick informal testing

**Evaluation Mode** (before publishing):
- Spawn specialized reviewers for structure/safety/usefulness
- Comprehensive quality audit with formal test suite
- Generate recommendations for improvements
- Use case: "Evaluate before publish" - formal quality gate

**Prerequisites**:
- Requires **skill-creator** plugin (from `~/.claude/plugins/cache/claude-plugins-official/skill-creator/`)
- Eval suite structure: Create `evals/evals.json` in skill directory with test prompts
- Eval viewer: Uses `eval-viewer/generate_review.py` for performance reports (skill-creator feature)

**📖 Detailed Guide**: See `references/eval-guide.md` for complete eval suite creation, test categories, performance interpretation, and description optimization.

**Skill Coordination**:
- Invoke **skill-creator** to run eval suite with `evals/evals.json`
- Use eval-viewer to generate performance reports via `eval-viewer/generate_review.py`
- Apply description optimization script if triggering issues detected
- Iterate until satisfaction threshold met

**Actions**:
1. **Choose mode**: Ask user "Trial mode (test-drive) or Evaluation mode (quality audit)?"
2. Create test prompts (2-3 realistic user queries)
3. Save to `evals/evals.json` format
4. Run evaluation suite with skill-creator
5. Generate performance report with variance analysis
6. Review results with user using eval-viewer
7. Apply description optimization if triggering accuracy < 80%
8. Rewrite skill based on empirical feedback
9. Repeat until performance threshold met

**Output Format**: Use Template 1 (Strict Analysis Format)

```markdown
## Evaluation Results

**Confidence:** [Score]% (Tier [1-4])

### Performance Metrics
| Metric | Score | Target | Status |
|--------|-------|--------|--------|
| Trigger accuracy | [%] | ≥80% | ✓/✗ |
| Output consistency | [%] | ≥90% | ✓/✗ |
| Execution success | [%] | ≥95% | ✓/✗ |
| Variance analysis | [score] | Low variance | ✓/✗ |

### Test Results
| Test Prompt | Expected | Actual | Pass/Fail | Notes |
|-------------|----------|--------|-----------|-------|
| [prompt 1] | [expectation] | [result] | ✓/✗ | [notes] |
| [prompt 2] | [expectation] | [result] | ✓/✗ | [notes] |

### Iteration Plan
1. [Issue identified] → [Fix applied]
2. [Issue identified] → [Fix applied]
3. Re-run eval suite after fixes

### Evidence
| Aspect | Evidence Source |
|--------|-----------------|
| Test output | eval-viewer/generate_review.py |
| Performance | evals/evals.json results |
| Variance | Benchmark comparison |
```

**When to skip this phase**:
- Simple skills with objectively verifiable outputs (file transforms, data extraction)
- User explicitly declines evaluation ("just vibe with me")
- Skills with subjective outputs (writing style, art)

---

## Phase 3e: Evaluator

**Role**: Structured evaluation against rubric lenses — NO final judgment, NO decision field

**Lenses**: 8 lenses total. Lens 8: Implementation Contract audits SKILL.md promises vs implementation/enforcement realization (file promises, stage enforcement, template system, process tracing). Strategic rightness remains `/skill-audit` territory.

**Separation from Phase 3f**: The evaluator produces findings; the judge applies policy. The evaluator never returns a `decision` field — that is the judge's exclusive responsibility. This separation prevents conflation of "what was found" with "what should be done about it."

**Default stance**: For `new_skill`, `orchestrator`, and `contract_change` routes, Phase 3e is the required critique pass unless policy routing explicitly bypasses it. Do not skip it just because the main model believes the artifact is already good enough.

**Input**: artifact + context + policy routing decision (required_phases, risk_level, matched_artifact_type)

**Output**: JSON array of structured findings per lens:
```json
[
  {
    "lens": "adaptability",
    "finding": "hard-coded path assumption in phase 3b",
    "evidence": ["workflow-phases.md:47", "builtins.json:12"],
    "proposed_score": 2,
    "severity": "critical",
    "provenance": "this_run",
    "assumptions": []
  }
]
```

**Provenance field** (required on every finding): `"provenance": "this_run" | "prior_premortem" | "prior_manual_review"`. Tag each finding with its source. Do not assert "not documented" or "does not exist" without fresh tool verification this session — use `"provenance": "this_run"` for new findings, `"prior_premortem"` for findings from a pre-mortem session, or `"prior_manual_review"` for findings from human review.

**Assumptions field** (required): Every evaluator output MUST include an `assumptions` array (empty if none found). Categorize under:
| Category | Examples |
|----------|----------|
| `repo_topology` | "assumes single-repo layout", "assumes P: drive is root" |
| `tools` | "assumes /sqa is available", "assumes /arch is responsive" |
| `config` | "assumes config files at path Y; no fallback" |
| `paths` | "assumes Windows paths", "assumes relative to project root" |
| `behavior` | "fails hard if tool discovery fails; no degraded mode" |
| `non_goals` | "does not handle multi-repo setups" |

For `risk_level == "high"` artifacts, dangerous assumptions (no fallback, hard-coded path, missing tool dependency) bias findings toward lower scores on adaptability or failure_tolerance.

**Lenses** (score ALL 7 — do not skip any):
| Lens | Measures | Score threshold |
|------|----------|----------------|
| implementation_fit | Correctly realizes the intended skill behavior | ≥3 |
| adaptability | Tolerates ecosystem change (no hard-coded paths/tools/thresholds) | ≥3 |
| composability | Reuses `/sqa`, `/arch`, `/rca`, `/sdlc` vs cloning logic | ≥3 |
| context_efficiency | Token footprint justified by value delivered | ≥3 |
| observability | Sufficient diagnostic hooks and trace points | ≥3 |
| failure_tolerance | Degrades safely with fallback behavior | ≥3 |
| maintainability_6m | Future changes are low-risk and understandable | ≥3 |

**Scoring**: `proposed_score` is integer 1-5 (1=critical failure, 5=excellent). `severity` is one of: `critical`, `major`, `minor`, `info`.

**Evidence requirement**: Every finding must cite specific file:line or config key. Speculative findings are flagged and excluded.

**SKILL.md Integration**: The evaluator uses the same rubric dimensions already defined in SKILL.md:159-174 (Completeness, Clarity, Usability, Testability, Robustness), mapped to evaluator lenses per the Rubric Dimension Mapping table in the plan.

**Quality Gate Protocol exception**: Phase 3e spawns a FRESH subagent with the evaluator prompt. Its output (structured JSON) is passed to Phase 3f — this is the only exception to the "Previous verdicts are NOT shared" rule, and it is specific to the evaluator/judge separation design.

---

## Phase 3f: Judge

**Role**: Apply policy to evaluator findings — returns pass/conditional_pass/fail decision

**Separation from Phase 3e**: The judge applies policy rules to the evaluator's findings. It does NOT re-analyze the artifact or produce new findings. If the evaluator's output is malformed, the judge returns `fail` with a specific error — it does not attempt to repair or interpret incomplete data.

**Default stance**: For the same medium/high-risk routes, Phase 3f is the required decision pass. A new skill should not be called shipped or ready without this pass unless policy routing documents a legitimate bypass.

**Input**: evaluator findings JSON + rubric dimensions + policy.json risk_level + matched_artifact_type

**Output**:
```json
{
  "decision": "pass | conditional_pass | fail",
  "required_follow_ups": ["Add assumptions register", "Fix hard-coded path"],
  "scores": {"implementation_fit": 4, "adaptability": 2, ...},
  "provenance": "this_run"
}
```

**Provenance field** (required): `"provenance": "this_run"` — the judge runs fresh in this session and applies policy to the evaluator's output.

**Decision policy** (apply in order):
1. Any `critical` severity finding → `fail`
2. Any finding owned by `skill-audit` → `fail` with required follow-up: invoke `/skill-audit`
3. `implementation_fit` OR `adaptability` OR `failure_tolerance` < 3 → `fail`
4. `risk_level == "high"` AND no findings above `minor` severity → `conditional_pass`
5. Otherwise → `pass`

**Assumptions handling**: Read the `assumptions` array from the evaluator's payload. For `risk_level == "high"` artifacts, dangerous assumptions (no fallback, hard-coded path, missing tool dependency) bias toward `conditional_pass` with strong `required_follow_ups` even if no critical findings exist. Do NOT invent new findings — only apply policy to what the evaluator reported.

**Input validation**:
- Invalid severity → treat as `info`
- Out-of-range score → clamp (<1→1, >5→5)
- Missing lens field → discard that finding
- Unparseable JSON or empty array → return `{"decision": "fail", "required_follow_ups": ["Evaluator output malformed"], "scores": {}}`

**Conditional pass**: Judge must list specific required follow-ups. Phase 4 is blocked until conditional items are resolved.

**Fail**: Distribution (Phase 5) is blocked until Judge re-runs and returns pass/conditional_pass.

---

## Phase 4: Optimization & Enhancement

**Goal**: Improve skill performance and reliability

**Skill Coordination**:
- Invoke **av2** for mechanical continuation enforcement (if multi-phase workflow)
- Invoke **output-style-extractor** to ensure consistent formatting
- Reuse existing cognitive/reasoning hooks when they solve a proven gap; do not add new hook-based cognition by default
- Review display_templates.md for format improvements
- **Route to /simplify + /refactor** (see Routing Checks below)

**Actions**:
1. Analyze workflow for phase enforcement needs
2. Add StopHook if multi-phase workflow detected
3. Optimize description for triggering accuracy (if Phase 3.5 showed issues)
4. Ensure output format matches chosen template
5. Add progressive disclosure if skill > 300 lines
6. Confirm operational resilience remains explicit after optimization:
   - terminal/session scope or explicit statelessness
   - stale-data invalidation / freshness authority
   - compact / interrupted-workflow recovery
   - cognitive/reasoning hook fit
7. **Consistency verification** (flaky test detection):
   - Run skill 3x with identical prompts
   - Measure output variance across runs
   - Flag non-deterministic behavior
   - High variance = requires fixing before deployment

8. **IMPL Pattern Extraction** (do this properly — thoroughness pass):
   - Read `P:/memory/skill_optimization_patterns.md`
   - Read `P:/.claude/.evidence/critique/IMPROVEMENTS.md`
   - If IMPROVEMENTS.md has entries not yet generalized into skill_optimization_patterns.md:
     - Extract the broader principle from each unimplemented IMPL entry
     - Append generalized principle to `skill_optimization_patterns.md` with a one-line changelog entry:
       `- [date]: [principle summary] — from IMPL entry: [original entry name]`
     - Flag remaining IMPL entries that still need generalization as **pending tasks**
   - If no unimplemented IMPL entries exist: note "IMPL entries fully generalized" in output

**Output Format**: Use Template 6 (Error Analysis Format)

### Routing Checks: /simplify and /refactor

After all validation phases complete, run these checks before rendering RNS. Each is a separate conditional block — evaluate all that apply.

**A. Complexity Check** (gates `/refactor`)
Try to run `lizard -f json <target_dir>` (or fall back to `radon cc -a <target_dir>`). Thresholds:

| Signal | Threshold | Action |
|--------|-----------|--------|
| `max_cc > 15` | Max cyclomatic complexity | **STRONG** `/refactor` candidate |
| `avg_cc > 8` | Average CC | `/refactor` candidate |
| `SKILL.md > 500 lines` | Skill length | `/refactor` candidate (structure burden) |

If neither `lizard` nor `radon` is available: use `SKILL.md > 500 lines` as sole heuristic.

**B. Implementation Check** (gates `/simplify`)
```bash
has_python=$(find <target_dir> -name "*.py" -not -name "__pycache__" | wc -l)
```
- `has_python >= 1` → `/simplify` candidate (any Python implementation benefit from code review)
- `has_python >= 3` → **STRONG** `/simplify` candidate (multiple files = compounding complexity)

**C. RNS Emission**
Append results to RNS output before the "Recommended Next Steps" section renders:

```
🔄 QUALITY ROUTING
  [recover/medium] SIMPLIFY-001 — Run /simplify on {target} ({reason})
  [recover/high] REFACTOR-001 — Run /refactor on {target} ({reason})
```

Only emit items with satisfied conditions. If no conditions satisfied for a skill, emit neither. If both are satisfied, emit both — do not deduplicate.

**Threshold sourcing**: Cite the actual measured value (e.g., `max_cc=23`) in the reason, not just the threshold name.

```markdown
## Optimization Analysis

### Summary
**Skill:** [skill-name]
**Location:** [file:line or component]
**Optimization Type:** [Continuation/Format/Performance]

### Issues Identified
| Issue | Impact | Fix |
|-------|--------|-----|
| [Issue 1] | [High/Med/Low] | [Solution] |
| [Issue 2] | [High/Med/Low] | [Solution] |

### Resolution
**Continuation Enforcement:** [StopHook added/updated/skipped]
**Format Standardization:** [Template # applied]
**Performance:** [optimizations applied]

### Prevention
[How to prevent future issues]
```

---

## Phase 5: Distribution & Documentation

**Goal**: Prepare skill for sharing or deployment

**Skill Coordination**:
- Invoke **sharing-skills** for GitHub PR workflow
- Invoke **github-public-posting** for pre-publish checklist
- Document output format in skill if not present

**Actions**:
1. Create fork if needed
2. Create feature branch
3. Commit changes with conventional commits
4. Open PR with proper description
5. Ensure output format documented in SKILL.md

**Output Format**: Use Template 5 (Workflow Progress Format)

```markdown
## Distribution Progress

### Phase 1: Preparation
- [x] Skill validated
- [x] Output format documented
- [x ] PR description written

### Phase 2: Git Workflow
- [ ] Fork repository
- [ ] Create feature branch
- [ ] Commit changes
- [ ] Push to remote

### Phase 3: PR Creation
- [ ] Open pull request
- [ ] Add reviewers
- [ ] Link to issues

### Current Status
**Phase:** [Current phase]
**Blockers:** [Any blockers or "None"]
**Next action:** [Specific next step]
```

<!--STATE_CLEAR: On workflow completion (Phase 5 done or user exits early): delete `.evidence/skill-ship-state-{cwd_hash}/workflow-state.json` — workflow is complete, no need to resume. Use Write tool to delete the file. This prevents stale state from confusing future runs.-->

---

## When to Skip Phases

**Skip Phase 3.5 (Evaluation) when:**
- Simple skills with objectively verifiable outputs
- User explicitly declines evaluation
- Skills with subjective outputs (writing style, art)

**Skip Phase 5 (Distribution) when:**
- Local skill improvements
- Plugin skills (use plugin distribution workflow)
- Skills not intended for sharing

## Quick Reference Table

| Phase | Goal | Key Skills | Output Template | Skip When |
|-------|------|------------|-----------------|-----------|
| Phase 1 | Discovery & Intent | similarity | Template 2 | Never |
| Phase 1.5 | Knowledge Retrieval | notebooklm, cks, memory | Template 2 | Simple skills, user declines |
| Phase 2 | Creation & Structuring | skill-creator, skill-development | Template 1 | Never |
| Phase 3 | Quality & Validation | testing-skills, av | Template 3 | Never |
| Phase 3.5 | Evaluation & Iteration | skill-creator (evals) | Template 1 | Simple skills, user declines, subjective outputs |
| Phase 4 | Optimization & Enhancement | av2, output-style-extractor | Template 6 | Multi-phase workflows only |
| Phase 5 | Distribution & Documentation | sharing-skills | Template 5 | Local skills, plugins, not sharing |
