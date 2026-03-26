# Pre-Mortem: T002 Breadcrumb Integration Test Fixes

## Analysis Target
T002 breadcrumb integration test suite (`tests/test_t002_breadcrumb_integration.py`) and its
`clean_breadcrumb_log_files` fixture (`tests/conftest.py`), after session-compaction recovery.

## Step 0: Project Constraints
Solo dev, Windows 11, pytest-based test isolation with `autouse=True` fixtures affecting all package tests.
Two independent breadcrumb storage subdirectories: `breadcrumb_logs_{terminal_id}/` (`.jsonl`) and
`breadcrumbs_{terminal_id}/` (`.json` state files).

## Step 0.7: Kill Criteria
- If `.jsonl` files accumulate after running tests → fixture cleanup is broken
- If tests fail after clean run → stale state pollution confirmed
- If real Claude Code state gets deleted → fixture needs mocking

## Step 1: Failure Scenario
"It's 6 months later and T002 tests pass but `.jsonl` log files accumulate in
`breadcrumb_logs_{terminal_id}/` because the cleanup glob `breadcrumb_*.jsonl` never matches
the actual `{skill}.jsonl` filenames. Meanwhile, `.json` state files correctly cleaned but
logs silently grow unbounded."

## Step 1.5: Fix Side Effects
- Changing `breadcrumb_*.jsonl` → `*.jsonl`: Safe — `breadcrumb_logs_*/` only contains `.jsonl` files
- Changing to also clean `breadcrumbs_*/`: Safe — `breadcrumb_dir` now cleaned in same fixture

## Step 2: Failure Modes (from adversarial agents)
See individual finding files in `.evidence/`.

## Step 4: Risk Ratings

## 🔴 WHAT'S ACTUALLY BROKEN

**Critical failures (must fix before further use)**

• COMP-001 | `.jsonl` cleanup glob pattern never matched actual files (Risk 8)
  [causes: COMP-001a, COMP-001b]
  - conftest.py:125 `glob("breadcrumb_*.jsonl")` does NOT match actual `{skill}.jsonl` files
  - log.py:77 confirms actual naming: `f"{skill_lower}.jsonl"`
  - FIX APPLIED: changed to `glob("*.jsonl")`

• COMP-001a | Stale `.jsonl` files accumulate in `breadcrumb_logs_{terminal_id}/` (Risk 7)
  [caused-by: COMP-001]
  - Old `code.jsonl`, `tdd.jsonl` entries never cleaned between test runs
  - Test isolation degraded — entries from one test bleed into another

• COMP-001b | Fixture claims to clean all breadcrumb files but silently leaves `.jsonl` (Risk 7)
  [caused-by: COMP-001]
  - Docstring says "Cleans ALL breadcrumb log files" — false guarantee

## 🟠 HIGH-RISK BEHAVIOR

• LOGIC-001 | `detect_terminal_id()` returns real terminal in pytest, risking real session data deletion (Risk 6)
  - Independent risk (no dependencies)
  - conftest.py:96 — fixture has no mocking; real `P:/.claude/state/breadcrumbs_*/` files targeted
  - If pytest inherits Claude Code terminal env vars, `detect_terminal_id()` returns real session ID

• LOGIC-002 | `test_verify_breadcrumb_trail_function` silently skips assertions when trail file absent (Risk 6)
  - Independent risk
  - test_t002_breadcrumb_integration.py:221 — `if trail_file.exists():` guards all assertions
  - False pass if initialization fails for any reason

• TEST-001 | `test_verify_breadcrumb_trail_function` bypasses `set_breadcrumb` API entirely (Risk 5)
  - Independent risk
  - Constructs complete trail directly in file + cache, never exercises `set_breadcrumb` → `verify` flow

• TEST-002 | No test verifies the cleanup fixture actually removes files (Risk 5)
  - Independent risk
  - `clean_breadcrumb_log_files` has zero test coverage

• PERF-001 | Triple `gc.collect()` loop adds 3x overhead per test (Risk 4)
  - Independent risk
  - conftest.py:119 — single call sufficient; triple loop on every test (200+ tests) is waste

• QUAL-002 | Fixture named `clean_breadcrumb_log_files` but cleans both `.jsonl` AND `.json` (Risk 3)
  - Independent risk
  - Misleading name — suggests only log files cleaned

## 🧠 BLIND SPOTS & CONTRADICTIONS

• adversarial-critic agent could not locate T002 test files — analyzed wrong topic
  - Source: .evidence/adversarial-critic/a04d04607c62bab19.txt
  - Indicates the critic agent's path resolution was misconfigured

• QA-002: Case-insensitive skill name matching may not work for all edge cases
  - Source: .evidence/adversarial-qa/a950a166f2b15031d.txt

## 🧪 TESTING & WATCHLIST (OPERATIONAL CHECKLIST)

**Per run**
- [ ] Run full skill-guard test suite and check for test isolation failures
- [ ] Verify no `code.jsonl`, `tdd.jsonl` files accumulate in `breadcrumb_logs_*/`

**Cadence**
- [ ] Weekly: Check `breadcrumb_logs_*/` for growth in number/size of `.jsonl` files

## 📂 EVIDENCE ARTIFACTS

- COMP-001 finding: log.py:77 confirms actual file naming as `{skill_lower}.jsonl`
- Adversarial findings stored in `.evidence/` subdirectory

## ✅ RECOMMENDED NEXT STEPS

**Evidence-Based Format (v5.0)**

1 (TEST) - Verify fixture cleanup actually works
  1a: Action → Manual - Evidence (COMP-001a: log.py:77)
  1b: Add integration test that creates log files, runs cleanup, asserts files gone

2 (QUAL) - Rename fixture to reflect dual-cleanup responsibility
  2a: Action → Edit conftest.py - Evidence (QUAL-002: conftest.py:96)
  2b: Rename `clean_breadcrumb_log_files` → `clean_breadcrumb_state_and_logs`

3 (LOGIC) - Mock `detect_terminal_id()` in fixture to isolate pytest from real session
  3a: Action → Edit conftest.py - Evidence (LOGIC-001: conftest.py:96)
  3b: Use `unittest.mock.patch` for `detect_terminal_id` returning a test-only terminal ID

4 (PERF) - Reduce gc.collect() from triple to single loop
  4a: Action → Edit conftest.py - Evidence (PERF-001: conftest.py:119)
  4b: Single `gc.collect()` is sufficient per cleanup phase (before + after)

5 (TEST) - Add test exercising `set_breadcrumb` → `verify_breadcrumb_trail` flow end-to-end
  5a: Action → Edit test_t002_breadcrumb_integration.py - Evidence (TEST-001: test_t002_breadcrumb_integration.py)
  5b: Create trail via `set_breadcrumb` API, then call `verify_breadcrumb_trail`, assert expected result

6 (LOGIC) - Add assertion before `if trail_file.exists()` to fail fast if init fails
  6a: Action → Edit test_t002_breadcrumb_integration.py - Evidence (LOGIC-002: test_t002_breadcrumb_integration.py:221)
  6b: Assert `trail_file.exists()` before the conditional, making test fail fast

7 - Capture lessons and patterns
  7a: Extract lessons → Use `/learn` - Capture dual-directory breadcrumb storage pattern to CKS
  7b: Reflect on corrections → Use `/reflect` - If user provided feedback

0 - Do ALL Recommended Next Steps
