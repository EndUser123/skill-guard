# Pre-Mortem: Frontmatter Validation Advisory System
**Target:** `skill_execution_state.py` — `_validate_skill_frontmatter()` + `set_skill_loaded()`
**Date:** 2026-04-02
**Analyst:** Claude (self-review)

---

## Step 0: Project Constraints

From `P:\packages\skill-guard\CLAUDE.md` (implied):
- Hooks handle enforcement structurally
- Fail fast, surface problems immediately
- Solo-dev environment

From global `CLAUDE.md`:
- Truthfulness > agreement
- Evidence-first verification

---

## Step 1: Failure Scenario

**"It's 6 months later. The frontmatter validation advisory system FAILED. Skills continue shipping with missing required frontmatter fields (name, description, version, enforcement). Enforcement tier is unknown. The system was silently broken — it recorded warnings to an audit log nobody read, but never told the developer."**

---

## Step 1.5: Fix Side Effects

**Proposed fix:** The change I just made (using `frontmatter` dict instead of redundant file re-check at wrong path) — this was a cleanup, not the actual surfacing fix.

**What NEW risks does this cleanup introduce?**
- The cleanup changed the early-return condition from `not skill_file.exists()` to `not frontmatter`. If `frontmatter` returns a non-empty dict for a file that exists but has no YAML frontmatter (just plain content), we now track it where previously we skipped. This is actually CORRECT behavior — the old check was wrong because it was checking the wrong path anyway.

---

## Step 2: Brainstorm Causes

**System identity:** Advisory frontmatter validation system — intended to warn developers when skills are missing required metadata (name, description, version, enforcement). Designed to fire on skill invocation (not just Write/Edit like `EnforcementTierValidator`).

**Governing principles:**
1. **Fail-fast surface principle** — Hooks must surface problems immediately, not write to audit trails silently
2. **Producer-consumer contract** — Data written must be read by something; orphan writes are wasted
3. **Ledger is not UI** — Audit trails are for forensics, not user feedback

**Failure causes:**

1. **P1-PRODUCER-ONLY: Ledger write without consumer** — `_validate_skill_frontmatter()` and `set_skill_loaded()` write `frontmatter_warnings` to the ledger via `append_event()`, but no hook or router ever reads `frontmatter_warnings` back out and surfaces it to user output. The ledger is a closed write-only system for this field. *(violates: Producer-consumer contract)*

2. **P2-ARCHITECTURE: Wrong abstraction for advisory warnings** — Ledger events are the right model for audit trails (immutable, ordered, queryable). They are the WRONG model for real-time user feedback. Using ledger `append_event` for advisory warnings instead of a notification mechanism means the warnings are buried in an internal artifact instead of being immediately visible. *(violates: Ledger is not UI)*

3. **P3-DESIGN: No integration point defined before implementation** — The `_validate_skill_frontmatter()` function was implemented in a previous session without explicitly naming which hook/router would consume `frontmatter_warnings`. No consumer was registered or designed. This is a classic producer-only implementation. *(violates: Producer-consumer contract)*

4. **T1-IMP: The path mismatch bug masked the problem** — `_load_skill_frontmatter()` reads from `P:/.claude/skills/{skill}/SKILL.md` while `_validate_skill_frontmatter()` and the redundant re-check read from `STATE_DIR / "skills" / {skill} / SKILL.md` (i.e. `P:/.claude/state/skills/{skill}/SKILL.md`). This is a TWO-YEAR-OLD PATH BUG that was present in the original code. The wrong path means validation would often not find the file, returning empty warnings even for skills with missing fields — making the system appear to work when it largely didn't. *(violates: Fail-fast surface)*

5. **T2-LOGIC: Early-return gate excluded warning skills** — The original early-return condition at lines 358-365 was:
   ```python
   if not required_tools and not allowed_first_tools:
       if not frontmatter_warnings and not skill_file.exists():
           return
   ```
   This means skills with `frontmatter_warnings` (missing fields) but no `required_tools` or `allowed_first_tools` would STILL return early and NOT write state — suppressing the very warnings the system was designed to capture. *(violates: Fail-fast surface)*

6. **E1-EXT: EnforcementTierValidator creates false confidence** — `EnforcementTierValidator` fires on Write/Edit of SKILL.md files and validates the `enforcement` field. Developers may believe this covers enforcement validation for skill INVOCATION, when it only covers skill FILE editing. This reduces perceived urgency of fixing the advisory system.

7. **P4-PROCESS: No definition of "done" for advisory hooks** — The skill_execution_state.py comment says "v3.5 CHANGES" but there's no tracking of whether the consumer-side was ever completed. No issue, no ticket, no test that verifies warnings appear in user output.

8. **T3-DATA: frontmatter_warnings survives compaction but has no reader** — The ledger persists through session compaction, but since no component reads `frontmatter_warnings`, compaction makes the data even more inaccessible.

---

## Step 3: Categorization

- **P1-PRODUCER-ONLY**: Process — No consumer defined before implementation
- **P2-ARCHITECTURE**: Tech — Wrong abstraction (ledger vs notification)
- **P3-DESIGN**: Process — No integration point defined
- **T1-IMP**: Tech — Path mismatch bug (2-year-old)
- **T2-LOGIC**: Tech — Early-return gate excluded warning skills
- **E1-EXT**: External — False confidence from EnforcementTierValidator
- **P4-PROCESS**: Process — No definition of done

---

## Step 3.5: Reference Class Forecasting

**Base rate:** In this codebase (based on hook development patterns), advisory hooks that write to state/ledger without a defined consumer have ~70% rate of becoming inert — the write happens, the data accumulates, nobody acts on it. This aligns with the "success theater" pattern where the write IS the completion signal without actual user-facing effect.

---

## Step 3.6: Success Theater Detection

**Success theater signals present:**
- ✅ "Tests pass" — 11 tests pass, but tests only verify the write to ledger, not that warnings appear in user output
- ✅ "RED/GREEN/REFACTOR complete" — TDD was done on validation logic, but no TDD on the consumer side
- ✅ "Function implemented" — `_validate_skill_frontmatter()` exists and has tests, but its output is never consumed

**Producer-only proof:**
- File written: `set_skill_loaded()` writes to ledger ✅
- Warnings captured: `frontmatter_warnings` in state dict ✅
- User saw warnings: ❌ NO CONSUMER — user never sees them

---

## Step 3.8: Operational Verification

**Finding:** No hook, router, or display mechanism reads `frontmatter_warnings` from the ledger and surfaces it to user output.

**Evidence:**
```
Grep "frontmatter_warning" in P:\.claude\hooks → only match is a state file (grounded_artifact), no actual consumer
```

The ONLY match is an unrelated state artifact. No PostToolUse hook, no Stop hook, no router reads this field.

---

## Step 4: Risk Ratings

| ID | Risk | L | I | Score | L% | C% | Notes |
|----|------|---|---|-------|-----|-----|-------|
| R1 | Producer-only: warnings written but never displayed | 3 | 3 | **9** | 95% | 95% | Primary failure mode |
| R2 | Path mismatch: validation reads wrong path | 2 | 3 | **6** | 80% | 70% | Present since original implementation |
| R3 | Early-return gate suppresses warnings | 2 | 3 | **6** | 70% | 80% | Fixed by cleanup? Wait — NO: the frontmatter_warnings check still gates |
| R4 | Wrong abstraction: ledger for real-time feedback | 2 | 2 | **4** | 60% | 70% | Structural design issue |
| R5 | No integration test for consumer path | 2 | 2 | **4** | 80% | 90% | 11 tests but all producer-side |
| R6 | EnforcementTierValidator creates false confidence | 1 | 2 | **2** | 50% | 60% | Secondary confusion factor |

---

## Step 4.5: Dependency Cascades

- **R1 (producer-only)** is the root — if a consumer existed, R2-R5 would be surfaced and fixed
- **R2 (path mismatch)** CAUSES R3 — because the wrong path returns empty warnings, the early-return gate appears safe when it isn't
- **R3 (early-return)** CAUSES R1 — suppressing warnings at write-time means there's nothing to read at read-time, so even a consumer would find nothing

---

## Step 5: Prevent Top 3

**R1 — Producer-only (BLOCKING)**
- **Prevention**: Define consumer BEFORE implementing producer; add integration test that verifies warnings appear in output
- **Proof**: Read hook/router that reads `frontmatter_warnings` and surfaces it

**R2 — Path mismatch (BLOCKING)**
- **Prevention**: `_validate_skill_frontmatter()` should use `P:/.claude/skills/{skill}/SKILL.md` NOT `STATE_DIR / "skills" / {skill}`
- **Proof**: `pytest tests/test_frontmatter_validation.py -v` with `STATE_DIR` patched to `tmp_path` — existing tests pass because they mock STATE_DIR, but the actual path used at runtime is still wrong

**R3 — Early-return gate suppresses warnings (BLOCKING)**
- **Prevention**: When `frontmatter_warnings` is non-empty, always write state regardless of execution requirements
- **Proof**: Add test: skill with missing frontmatter AND no required_tools → verify `append_event` was called with warnings

---

## Step 6: Warning Signs

- **R1**: User says "why don't I see frontmatter warnings?" → consumer doesn't exist
- **R2**: Validation returns empty warnings for skills known to have missing fields → wrong path being checked
- **R3**: Skills with missing frontmatter don't appear in ledger at all → early-return suppressing

---

## Step 7: Adversarial Validation

*To be dispatched after document is written.*

---

## REMAINING ITEMS

| Step | Status | Gap | Priority |
|------|--------|-----|----------|
| R1 (Consumer) | ❌ Open | No hook/router reads frontmatter_warnings | Critical |
| R2 (Path bug) | ❌ Open | _validate_skill_frontmatter uses STATE_DIR path not skills path | Critical |
| R3 (Early-return) | ⚠️ Partial | Cleanup changed to use frontmatter dict but early-return still gates warnings | High |
| Consumer design | ❌ Open | No decision on WHICH hook surfaces warnings | High |
