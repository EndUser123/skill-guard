---
type: quality
load_when: quality
priority: mandatory
estimated_lines: 120
---

# Phase 3: Quality & Validation (Detailed Specifications)

Detailed tables, processes, and gate criteria for Phase 3 sub-phases. See SKILL.md for overview and phase summaries.

## Quality Gate Execution Protocol

Each sub-phase spawns a FRESH subagent with minimal context to prevent state contamination. Previous stage verdicts are NOT shared to avoid bias.

---

### Phase 3a: Specification Compliance
**Question:** "Did the implementation follow the plan?"

**Focus:** RED/GREEN/REGRESSION/VERIFY completion evidence

**Process:**
1. Spawn FRESH subagent with: plan.md (if exists) + draft SKILL.md
2. Review ONLY: Does implementation match stated requirements?
3. Do NOT review code quality (that's Phase 3b)
4. Do NOT share previous verdicts or quality scores

**Output:** `SPEC_PASS` or `SPEC_FAIL` with gap list

| Requirement | Status | Evidence | Gap |
|-------------|--------|----------|-----|
| Stated user intent addressed | - | - | - |
| Required sections present | - | - | - |
| Completion evidence provided | - | - | - |
| Reference integrity (files exist) | - | - | - |

**Gate:** Block Phase 3c until `SPEC_PASS` (Phase 3b runs in parallel -- its YAML/context-bloat checks are independent of spec compliance)

**Skip:** Never - spec compliance is mandatory

---

### Phase 3b: Code Quality
**Question:** "Is this well-structured, secure skill code?"

**Focus:** YAML completeness, trigger accuracy, quality gates, context bloat prevention

**Process:**
1. Spawn FRESH subagent with: SKILL.md + `SPEC_PASS` verdict (not spec rationale)
2. Review: Code quality, security, maintainability, best practices
3. **CRITICAL**: Context bloat prevention checks
   - SKILL.md size validation (warn if >300 lines, block if >500 lines)
   - Duplicate content detection (SKILL.md vs memory/ system)
   - Reference integrity check (all referenced files exist)
   - Memory system integration (reference memory/ files instead of duplicating)

**Output:** Quality scores + improvement suggestions

| Check | Status | Severity | Fix |
|-------|--------|----------|-----|
| YAML frontmatter completeness | - | critical/warning/info | - |
| Required frontmatter fields (`suggest`, `workflow_steps`, etc.) | - | critical/warning/info | - |
| Enforcement tier field (required) | - | critical/warning/info | - |
| Trigger accuracy (third person) | - | critical/warning/info | - |
| Description length (<1024 chars) | - | critical/warning/info | - |
| Progressive disclosure (<500 lines) | - | warning/info | - |
| Quality Commitments (from Phase 1.5) | - | critical/warning | - |
| Hook analysis (if applicable) | - | info | - |
| Skill hook path resolution (if hooks) | - | critical/warning | - |
| Absence claim verification | - | critical/warning | - |
| GTO skill coverage (if applicable) | - | critical/warning | - |

**Absence Claim Verification Workflow:**
Before claiming a component is missing, verify absence with tool evidence:
1. **Grep before claim**: Search codebase for the component name/pattern
2. **Read before missing**: Check referenced files exist before stating they're absent
3. **Glob before none**: Verify no matches with glob patterns before claiming "no files"
4. Document negative findings with explicit search terms used

**Gate:** Block Phase 3c until critical issues resolved

For new skills and orchestrators, Phase 3b must verify the local SKILL.md schema rather than assuming Phase 2 created a valid frontmatter block. Missing required fields are readiness blockers, not cosmetic issues.

**GTO Skill Coverage Check (if applicable):**
When a skill emits GTO-trackable findings (verification, critique, gap analysis), the reviewer checks:
1. **Activation warranted?** — Does this skill category (quality, orchestration, analysis) produce findings GTO should track?
2. **Import correct?** — Uses `from gto.lib.skill_coverage_detector import _append_skill_coverage` with `P:/.claude/skills` in `sys.path`
3. **Call signature correct?** — Only `target_key`, `skill`, `terminal_id`, `git_sha` params (no `project_root`)
4. **Best-effort wrapper** — Call wrapped in `try/except` so failures don't crash the skill
5. **Reference doc** — Skill author consulted `references/gto-skill-coverage.md`

See `references/gto-skill-coverage.md` for full API documentation.

**Skip:** Simple skills (<100 lines) can skip to 3c after basic YAML check

---

### Phase 3c: Integration Verification
**Question:** "Does the skill work when invoked?"

**Focus:** Actual skill invocation test, execution paths, runtime behavior

**Process:**
1. Spawn FRESH subagent with: installed skill + test prompts (blind to spec/quality)
2. Invoke skill with sample prompts
3. Verify: Skill triggers correctly, executes without errors, produces expected output
4. Test orchestrated skills: Verify coordinated skill execution

**Output:** Test execution transcript + pass/fail

| Test | Status | Evidence | Fix |
|------|--------|----------|-----|
| Skill loads without errors | - | - | - |
| Triggers on expected queries | - | - | - |
| Executes workflow correctly | - | - | - |
| Orchestrated skills work | - | - | - |
| Multi-terminal safe (if applicable) | - | - | - |
| Absence claims verified before asserting | - | - | - |

**Gate:** Block Phase 4 until integration passes

Do not describe the artifact as "shipped" or "ready" until the required Phase 3 path has completed. Phase 2 creation alone only proves that a draft artifact exists.

**Skip:** Never - integration verification is mandatory

---

### Phase 3d: Artifact Quality Validation (conditional)
**Activate when**: Target skill emits durable artifacts (plans, reports, configs consumed by other agents). Check ALL of the following:

1. **Explicit flag**: `produces_artifact: true` in SKILL.md frontmatter, OR
2. **Description signal**: Description contains "produces" or "artifact" keywords (e.g., "Produces plan artifacts", "emits reports"), OR
3. **Workflow signal**: Workflow steps reference file outputs with artifact names (e.g., `plan.md`, `review.findings.json`, `*.report.md`), OR
4. **Known categories**: Skill category is `planning`, `reporting`, or `analysis` (emit durable artifacts)

**Reference:** `references/artifact-rubric.md` -- 5-criterion quality bar

**Gate:** Block Phase 4 until `ARTIFACT_PASS` (all P0/P1 criteria met) when target skill produces artifacts

**Skip:** Utility skills with transient output (formatters, calculators, validators whose output is NOT consumed by other agents)
