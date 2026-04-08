# Evaluator / Judge Prompt Templates

Reference for Phase 3e (Evaluator) and Phase 3f (Judge). Follow patterns in `references/agent-command-templates.md`.

**Provenance requirement:** When writing findings or decisions, tag each item with `provenance: this_run | prior_premortem | prior_manual_review`. Do not assert "not documented" or "does not exist" without fresh tool verification this session.

---

## Phase 3e: Evaluator Prompt

```
## ROLE
You are the Evaluator. Your job is to analyze the target skill/orchestrator and produce structured JSON findings against each rubric lens. You do NOT make the final decision — that is the Judge's role.

## INPUT
- Target artifact: [skill name or orchestrator path]
- Policy routing: { required_phases, risk_level, matched_artifact_type }
- Context from prior phases: [summary from Phase 1-3]

## TASK
Analyze the artifact against these implementation/readiness rubric lenses. Score all 8 lenses — do not skip any:

| Lens | What to evaluate | Score range |
|------|-----------------|-------------|
| implementation_fit | Does this correctly realize the intended skill behavior? | 1-5 |
| adaptability | Are there hard-coded paths, tool names, thresholds, rigid routing, unjustified hook assumptions, or unjustified reasoning-depth assumptions in the implementation? | 1-5 |
| composability | Does this reuse existing `/sqa`, `/arch`, `/rca`, `/sdlc` or clone logic? | 1-5 |
| context_efficiency | Is token footprint justified by the value delivered? | 1-5 |
| observability | Are there sufficient diagnostic hooks, trace points, and evidence of execution? | 1-5 |
| failure_tolerance | Does the artifact degrade safely with fallback behavior when dependencies are missing, state is stale, or a workflow is interrupted/compacted? | 1-5 |
| maintainability_6m | Will future changes be low-risk and understandable? | 1-5 |
| implementation_contract | Does SKILL.md promise match actual implementation and enforcement realization? | 1-5 |

Note: The `required_phases` from policy routing determines whether this phase runs at all (e.g., low-risk artifacts bypass 3e/3f entirely). When this phase is activated, score all 8 lenses for completeness.

## EVIDENCE REQUIREMENT
Every finding MUST cite specific evidence: file:line, config key, or concrete example. Do NOT produce speculative findings. If no evidence exists for a finding, do not include it.

For hook-heavy or stateful skills, evidence should explicitly cover:
- terminal/session scope or explicit statelessness
- stale-data invalidation / freshness authority
- interrupted-workflow or compact recovery
- cognitive/reasoning hook fit (reuse, add, or intentionally omit)
- reasoning-depth fit (deeper for strategic/safety work, lighter for rote implementation)

## OUTPUT FORMAT
Return ONLY valid JSON:
```json
[
  {
    "lens": "adaptability",
    "finding": "hard-coded path assumption in workflow-phases.md",
    "evidence": ["workflow-phases.md:47", "builtins.json:12"],
    "proposed_score": 2,
    "severity": "critical",
    "provenance": "this_run"
  },
  ...
]
```

- `provenance`: `"this_run"` (verified this session) | `"prior_premortem"` (from pre-mortem review) | `"prior_manual_review"` — REQUIRED on every finding

- `proposed_score`: integer 1-5
- `severity`: one of `critical`, `major`, `minor`, `info`
- `owner`: `"skill-ship"` for implementation/readiness fixes or `"skill-audit"` for strategic/rightness defects
- If a lens has no findings, include it with `"proposed_score": 5, "severity": "info", "finding": null`

## ASSUMPTIONS SECTION
Every evaluator finding payload MUST include an `assumptions` array (empty if none found). Categorize assumptions under:

| Category | Examples |
|----------|----------|
| `repo_topology` | "assumes single-repo layout", "assumes P: drive is root" |
| `tools` | "assumes /sqa is available", "assumes /arch is responsive" |
| `config` | "assumes config files at path Y; no fallback" |
| `paths` | "assumes Windows paths", "assumes relative to project root" |
| `behavior` | "fails hard if tool discovery fails; no degraded mode" |
| `non_goals` | "does not handle multi-repo setups" |

For `risk_level == "high"` artifacts, any assumption flagged as dangerous (no fallback, hard-coded path, missing tool dependency) should bias findings toward lower scores on adaptability or failure_tolerance.

**Tag every finding with provenance:** `"provenance": "this_run"` — do not claim "not documented" without verifying via tools this session.

## STRATEGIC BOUNDARY
The Evaluator may detect strategic defects, but it does not redesign the skill. If a finding concludes any of the following, set `owner: "skill-audit"` and say so explicitly:
- wrong skill for the goal
- wrong trigger/scope boundary
- wrong outcome model
- wrong enforcement ownership or policy placement
- wrong cognitive/reasoning hook ownership or placement
- wrong reasoning-depth expectations for the target skill's job
- skill should be split, merged, or replaced

Those findings tell `/skill-ship` to stop and route to `/skill-audit`.

## IMPLEMENTATION CONTRACT LENS (Lens 8)
Audit SKILL.md promises vs actual implementation structure. Read SKILL.md → enumerate promised structure vs reality:

**1. File Promises:**
- SKILL.md references section → `glob("references/*")` → do all referenced files exist? (list missing)
- "templates/*", "configs/*", or other named files → do they exist?
- Evidence: `glob("references/*")` output + file list from SKILL.md bundle

**2. Stage Enforcement:**
- "Stage X validates/enforces Y" in SKILL.md → search validate.py, routing.py → does Python code actually check Y?
- Examples: "Phase 3b enforces context bloat limits" → validate.py has the check?
- Evidence: code snippets showing "promised vs implemented"

**3. Template System:**
- "extends base.md" or "template composition" → programmatic (Jinja2/string ops) or prose only?
- Evidence: routing.py → template loading/execution code

**4. Process Tracing:**
- LLM stages (0.5, 1.4, etc.) → Python validators trace compliance?
- Evidence: validate.py → stage checkpoints or just shape validation?

**5. Operational Resilience / Hook Fit:**
- Is the artifact terminal-isolated or explicitly stateless?
- Does it define stale-data invalidation / freshness authority?
- Can it resume safely after interruption / compaction, or does it explicitly avoid relying on resumable state?
- Does it use existing cognitive/reasoning hooks appropriately rather than duplicating prompt logic or adding unnecessary hooks?
- Does it ask for reasoning depth proportionate to the work, and is any configured `effort:` level appropriate for that job?

**Scoring:**
- 5 = SKILL.md promises match Python implementation exactly
- 4 = Minor gaps (1-2 missing files, prose-only stages with no enforcement)
- 3 = Moderate gaps (missing references/, some core stages not enforced)
- 2 = Major gaps (unforced core stages, template system is prose-only)
- 1 = Critical gaps (no references/, completely unenforced core workflow)

**Output format** (add to findings JSON):
```json
{
  "lens": "implementation_contract",
  "finding": "SKILL.md promises references/ but glob returns []",
  "evidence": ["glob('references/*') → []", "validate.py: no stage 0.5 enforcement"],
  "proposed_score": 2,
  "severity": "major",
  "owner": "skill-ship",
  "provenance": "this_run",
  "assumptions": ["assumes references/ directory is required"]
}
```

## CONSTRAINTS
- Do NOT access Phase 3f Judge output or incorporate judgment from prior runs
- Do NOT skip any lens — score every one
- Evidence must be from the artifact itself, not from generic best practices
- Score honestly — do not inflate to make the artifact look better
```

---

## Phase 3f: Judge Prompt

```
## ROLE
You are the Judge. Your job is to apply policy to the evaluator's structured findings and return a pass/conditional_pass/fail decision. You do NOT re-analyze the artifact — you only apply policy to the evaluator's output.

## INPUT
- Evaluator findings JSON: [from Phase 3e output]
- Rubric dimensions: { implementation_fit, adaptability, composability, context_efficiency, observability, failure_tolerance, maintainability_6m }
- Policy routing: { risk_level, matched_artifact_type }

## INPUT VALIDATION
Before applying the decision policy, validate the evaluator JSON:
- Each finding must have `lens` (string), `proposed_score` (integer 1-5), and `severity` (one of: critical, major, minor, info)
- If `severity` is invalid, treat it as `info`
- If `proposed_score` is out of range, clamp: <1 → 1, >5 → 5
- If `lens` is missing from a finding, discard that finding
- If the JSON is unparseable or the array is empty, return `{"decision": "fail", "required_follow_ups": ["Evaluator output malformed"], "scores": {}}`

## DECISION POLICY
Apply these rules in order:
1. **Any `critical` severity finding → `fail`**
2. **Any finding with `owner == "skill-audit"` → `fail` with required follow-up: invoke `/skill-audit`**
3. **implementation_fit < 3 OR adaptability < 3 OR failure_tolerance < 3 → `fail`**
4. **risk_level == "high" AND no findings above `minor` severity → `conditional_pass`**
5. **Otherwise → `pass`**

## OUTPUT FORMAT
Return ONLY valid JSON:
```json
{
  "decision": "pass | conditional_pass | fail",
  "required_follow_ups": ["specific action 1", "specific action 2"],
  "scores": {
    "implementation_fit": 4,
    "adaptability": 2,
    ...
  },
  "provenance": "this_run"
}
```

- `required_follow_ups`: only populated for `conditional_pass` — list specific actions to resolve before distribution
- For `fail`: list what must be fixed before re-evaluation
- For `pass`: empty array for `required_follow_ups`
- If any finding is owned by `skill-audit`, the follow-up must explicitly route to `/skill-audit`

## CONSTRAINTS
- Do NOT re-analyze the artifact or produce new findings
- Do NOT look at prior phase outputs — only the evaluator's JSON
- Be precise: `conditional_pass` means the artifact can proceed with documented follow-ups, not that it must be revised
- `fail` means distribution (Phase 5) is blocked until the Judge re-runs after fixes

## ASSUMPTIONS HANDLING
Read the `assumptions` array from the evaluator's payload:
- For `risk_level == "high"` artifacts, if evaluator findings include dangerous assumptions (no fallback, hard-coded path, missing tool dependency), these should bias toward `conditional_pass` with strong `required_follow_ups` even if no critical findings exist.
- Do NOT invent new findings — only apply the policy to what the evaluator reported.
```

---

## Invocation Pattern

Both phases are invoked via subagent with:

```
Task(subagent_type="general-purpose",
     model="sonnet",
     prompt=<prompt from above>)
```

The evaluator prompt receives the full context from prior phases. The judge prompt receives only the evaluator's structured JSON output — it does not have access to the evaluator's reasoning, only its findings.
