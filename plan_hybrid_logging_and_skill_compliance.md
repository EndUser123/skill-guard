# Implementation Plan: Hybrid Logging System & Skill Compliance for skill-guard

## Overview

Implement a hybrid logging system for skill-guard's breadcrumb tracking and make Claude Code skills skill-guard compliant through workflow step declarations.

**Primary Goals**:
1. **Hybrid Logging System**: Replace inefficient read-modify-write pattern with append-only logging + in-memory cache + periodic snapshots
2. **Skill Compliance**: Enable all Claude Code skills to participate in breadcrumb tracking by declaring workflow_steps in SKILL.md frontmatter

**Timeline**: 3-4 hours for quick wins, 8-12 hours for full implementation

---

## Context Analysis

### Current Breadcrumb System (skill-guard)

**What exists today**:
- **File location**: `P:/.claude/state/breadcrumbs_{terminal_id}/breadcrumb_{skill_name}.json`
- **Storage pattern**: Single JSON file per skill, rewritten on each breadcrumb update
- **Write pattern**: Read entire JSON → modify in memory → write entire JSON back
- **Problems**:
  - Write amplification (entire file rewritten for each step)
  - No audit trail (can't see historical progression)
  - Performance degrades with workflow complexity
  - Concurrent access issues (multiple terminals)

**Example current state**:
```json
{
  "skill": "package",
  "terminal_id": "term_12345",
  "initialized_at": 1234567890.123,
  "workflow_steps": ["detect", "analyze", "generate", "validate"],
  "completed_steps": ["detect", "analyze"],
  "current_step": "analyze",
  "last_updated": 1234567891.456
}
```

### Hybrid Logging System (Proposed)

**Three-component architecture**:

1. **Append-Only Log** (audit trail)
   - File: `breadcrumb_{skill_name}.log`
   - Format: JSONL (one JSON object per line)
   - Immutable writes (append only, never modify)
   - Example entry: `{"timestamp": 1234567890.123, "event": "step_completed", "step": "analyze"}`

2. **In-Memory Cache** (fast reads)
   - Python dict: `current_state[skill_name] = {...}`
   - Lazy-loaded from log on first access
   - Updated in memory, persisted on checkpoint

3. **Periodic Snapshots** (fast recovery)
   - File: `breadcrumb_{skill_name}.json` (same format as current)
   - Written every N steps or on skill completion
   - Enables fast recovery without replaying entire log

**Benefits**:
- Write efficiency (append vs rewrite)
- Audit trail (can reconstruct history)
- Better concurrency (append-only writes)
- Fast recovery (snapshot + delta log replay)

### Current Skill Compliance

**Skills that COULD track workflow steps** (but don't):
- `/code` - 9 phases (REQUIREMENTS → PRE-FLIGHT → EXPLORE → PLAN → TDD → TEST → AUDIT → TRACE → DONE)
- `/trace` - 3 scenarios (happy path, error path, edge case)
- `/arch` - 3 stages (pre-flight, classification, template execution)
- `/package` - 7 phases (detect, analyze, generate, validate, cleanup, git-ready, recruiter-validation)
- `/tdd` - 4 steps (RED, GREEN, REFACTOR, VERIFY)

**Problem**: None declare `workflow_steps` in SKILL.md frontmatter, so breadcrumb tracking doesn't initialize for them.

---

## Existing Implementation Discovery

### skill-guard Breadcrumb System

**Files**:
- `src/skill_guard/breadcrumb/tracker.py` - Core breadcrumb tracking logic
- `src/skill_guard/skill_execution_state.py` - Skill execution state (related but separate)
- Tests: `tests/test_breadcrumb_tracker.py` (needs verification)

**Key functions**:
- `initialize_breadcrumb_trail(skill_name)` - Creates breadcrumb file from workflow_steps
- `set_breadcrumb(skill_name, step_name)` - Marks step as completed
- `verify_breadcrumb_trail(skill_name)` - Checks if all steps completed
- `cleanup_session_breadcrumbs()` - Removes trails on session end

**Current data flow**:
```
Skill invoked → initialize_breadcrumb_trail()
                    ↓ (reads SKILL.md workflow_steps)
                    → Creates breadcrumb_{skill}.json
                    → Sets all steps to "pending"
Each step → set_breadcrumb(skill, step)
         → Read JSON from file
         → Modify completed_steps list
         → Write JSON back to file
```

### Claude Code Skills Structure

**Frontmatter format** (YAML between `---` markers):
```yaml
---
name: code
version: 2.22.0
description: AI-assisted feature development workflow
category: development
triggers:
  - 'code feature'
  - 'build feature'
---
```

**Missing**: No `workflow_steps` field in any skill frontmatter

---

## Test Discovery

### Existing Tests

**skill-guard tests**:
- `tests/test_tracker.py` - Basic breadcrumb functionality (needs verification if exists)
- `tests/test_tracker_fixes.py` - Tests for security fixes (just created)

**Coverage gaps**:
- No tests for append-only log format
- No tests for in-memory cache invalidation
- No tests for snapshot + log replay
- No tests for concurrent access scenarios
- No integration tests with actual skills

### Required New Tests

**Hybrid Logging System**:
1. `test_append_only_log_format` - Verify JSONL format, line-by-line writes
2. `test_in_memory_cache_initialization` - Lazy load from log on first access
3. `test_snapshot_periodic_writes` - Verify snapshot every N steps
4. `test_log_replay_after_snapshot` - Reconstruct state from snapshot + delta log
5. `test_concurrent_append_writes` - Multiple terminals appending safely
6. `test_log_rotation` - Archive old logs when size exceeds threshold

**Skill Compliance**:
1. `test_workflow_steps_parsing` - Parse workflow_steps from SKILL.md frontmatter
2. `test_breadcrumb_initialization_for_skills` - Verify initialization for compliant skills
3. `test_breadcrumb_verification_pass` - All steps completed → pass
4. `test_breadcrumb_verification_fail` - Missing steps → fail with helpful message

---

## Proposed Solution

### Architecture: Hybrid Logging System

**Component 1: Append-Only Log**

```python
# File: src/skill_guard/breadcrumb/log.py

class AppendOnlyBreadcrumbLog:
    """Append-only log for breadcrumb audit trail."""

    def __init__(self, skill_name: str, terminal_id: str):
        self.log_path = _get_log_file(skill_name, terminal_id)

    def append(self, event: dict) -> None:
        """Append event to log (atomic write)."""
        # JSONL format: one JSON object per line
        line = json.dumps(event)
        with open(self.log_path, 'a') as f:
            f.write(line + '\n')

    def replay(self, from_snapshot: dict | None = None) -> dict:
        """Reconstruct current state from log."""
        # Start from snapshot if available
        state = from_snapshot.copy() if from_snapshot else {
            "completed_steps": [],
            "current_step": None,
            "last_updated": None
        }

        # Apply log entries in order
        with open(self.log_path, 'r') as f:
            for line in f:
                event = json.loads(line)
                if event["event"] == "step_completed":
                    state["completed_steps"].append(event["step"])
                    state["current_step"] = event["step"]
                    state["last_updated"] = event["timestamp"]

        return state
```

**Component 2: In-Memory Cache**

```python
# File: src/skill_guard/breadcrumb/cache.py

class BreadcrumbStateCache:
    """In-memory cache for fast state reads."""

    def __init__(self):
        self._cache: dict[str, dict] = {}
        self._log: AppendOnlyBreadcrumbLog = None
        self._snapshot_interval = 5  # Write snapshot every 5 steps

    def get_state(self, skill_name: str) -> dict:
        """Get current state (lazy load from log)."""
        if skill_name not in self._cache:
            # Lazy load: read snapshot, replay log
            snapshot = self._load_snapshot(skill_name)
            self._cache[skill_name] = self._log.replay(from_snapshot=snapshot)

        return self._cache[skill_name]

    def update_state(self, skill_name: str, step: str) -> None:
        """Update state in memory and append to log."""
        state = self.get_state(skill_name)
        state["completed_steps"].append(step)
        state["current_step"] = step
        state["last_updated"] = time.time()

        # Append to log
        self._log.append({
            "timestamp": state["last_updated"],
            "event": "step_completed",
            "step": step
        })

        # Periodic snapshot
        if len(state["completed_steps"]) % self._snapshot_interval == 0:
            self._write_snapshot(skill_name, state)
```

**Component 3: Backward Compatibility Layer**

```python
# File: src/skill_guard/breadcrumb/tracker.py (modified)

# Keep existing API, delegate to hybrid system internally

def set_breadcrumb(skill_name: str, step_name: str) -> None:
    """Mark a workflow step as completed (backward-compatible API)."""
    # NEW: Use hybrid system internally
    cache.update_state(skill_name, step_name)

    # LEGACY: Also write to old JSON format for compatibility
    # (Remove this in future major version)
    if _use_legacy_format():
        _legacy_set_breadcrumb(skill_name, step_name)
```

### Architecture: Skill Compliance

**Step 1: Add workflow_steps to SKILL.md frontmatter**

Example for `/code` skill:

```yaml
---
name: code
version: 2.22.0
description: AI-assisted feature development workflow
category: development
triggers:
  - 'code feature'
  - 'build feature'
workflow_steps:
  - requirements
  - pre-flight
  - explore
  - plan
  - tdd
  - test
  - audit
  - trace
  - done
---
```

**Step 2: Skill hooks call breadcrumb functions**

```python
# In skill's hook script (e.g., code/hooks/progress.py)

from skill_guard.breadcrumb import set_breadcrumb

def on_phase_complete(phase_name: str):
    """Called when a /code phase completes."""
    set_breadcrumb("code", phase_name)
```

**Step 3: Global hook verifies completion**

```python
# In global PreToolUse or UserPromptSubmit hook

from skill_guard.breadcrumb import verify_breadcrumb_trail

def before_skill_completion(skill_name: str):
    """Verify skill completed all workflow steps."""
    is_complete, message = verify_breadcrumb_trail(skill_name)

    if not is_complete:
        # Block or warn about incomplete workflow
        print(f"WARNING: {message}")
        # Optional: Block completion for strict enforcement
```

---

## Data Flow

### Hybrid Logging Write Path

```
Skill step completes
    ↓
set_breadcrumb(skill, step)
    ↓
cache.update_state(skill, step)
    ├─→ Update in-memory state (dict)
    ├─→ Append to log (JSONL line)
    └─→ Check if snapshot needed (every N steps)
        └─→ Write snapshot to .json file
```

### Hybrid Logging Read Path

```
get_breadcrumb_trail(skill)
    ↓
cache.get_state(skill)
    ├─→ Check cache (hit → return)
    └─→ Cache miss:
        ├─→ Load snapshot from .json (fast start)
        ├─→ Replay log from .log (apply deltas)
        └─→ Store in cache, return
```

### Skill Compliance Flow

```
User invokes skill (e.g., /code feature)
    ↓
UserPromptSubmit hook detects skill invocation
    ↓
initialize_breadcrumb_trail("code")
    ├─→ Read code/SKILL.md
    ├─→ Parse workflow_steps from frontmatter
    └─→ Create breadcrumb log + snapshot
    ↓
Each phase completes → set_breadcrumb("code", "tdd")
    ↓
PreToolUse hook before completion → verify_breadcrumb_trail("code")
    ├─→ All steps complete → Allow completion
    └─→ Missing steps → Block or warn
```

---

## Error Handling

### Hybrid Logging System Errors

**Log write failure** (disk full, permissions):
- **Detection**: IOError on append
- **Fallback**: Keep in-memory state, retry write on next update
- **User impact**: No immediate blocking, logged warning

**Snapshot write failure**:
- **Detection**: IOError on snapshot write
- **Fallback**: Keep log entries, retry snapshot on next periodic write
- **User impact**: Slower recovery (must replay entire log), no data loss

**Log corruption** (invalid JSON, truncated line):
- **Detection**: JSONDecodeError on replay
- **Recovery**: Skip corrupted line, log warning, continue with valid entries
- **User impact**: Some history lost, current state recoverable

**Concurrent write conflict** (two terminals writing same log):
- **Detection**: File lock detected (optional, depends on platform)
- **Prevention**: Append-only writes are naturally lock-free (most filesystems)
- **Fallback**: Retry with exponential backoff

### Skill Compliance Errors

**Missing workflow_steps in SKILL.md**:
- **Detection**: Frontmatter parsing returns empty list
- **Fallback**: Treat as knowledge skill (no breadcrumb tracking)
- **User impact**: Skill works without enforcement

**Invalid step name** (set_breadcrumb called with wrong step):
- **Detection**: Step not in workflow_steps list
- **Response**: Ignore invalid step, log warning
- **User impact**: Step not tracked, but doesn't break skill

**Breadcrumb file missing** (verify called before initialize):
- **Detection**: File not found error
- **Response**: Return "no workflow steps declared" (allow completion)
- **User impact**: Verification passes, skill completes

---

## Test Strategy

### Hybrid Logging System Tests

**Unit Tests** (fast, isolated):
1. `test_append_only_log_format` - Verify JSONL format, newlines
2. `test_log_append_atomicity` - Single write per append, no file corruption
3. `test_cache_lazy_loading` - Cache miss triggers log replay
4. `test_cache_hit` - Subsequent reads use cache
5. `test_snapshot_periodic` - Snapshot every N steps
6. `test_log_replay_from_snapshot` - State = snapshot + delta log
7. `test_concurrent_writes` - Two terminals appending safely

**Integration Tests** (slow, real files):
1. `test_end_to_end_trail` - Initialize → set breadcrumbs → verify
2. `test_recovery_after_crash` - Simulate crash, restart, verify recovery
3. `test_log_rotation` - Large log triggers archival
4. `test_backward_compatibility` - Old JSON files still readable

**Performance Tests**:
1. `test_write_performance` - 100 steps, measure time (hybrid vs old)
2. `test_read_performance` - 1000 reads, measure cache hit rate

### Skill Compliance Tests

**Frontmatter Parsing Tests**:
1. `test_parse_workflow_steps_valid` - Parse correctly formatted frontmatter
2. `test_parse_workflow_steps_missing` - Missing field → empty list
3. `test_parse_workflow_steps_malformed` - Invalid YAML → empty list

**Breadcrumb Initialization Tests**:
1. `test_initialize_with_workflow_steps` - Creates log file
2. `test_initialize_without_workflow_steps` - No file created (knowledge skill)
3. `test_initialize_existing_skill` - code, trace, arch skills work

**Verification Tests**:
1. `test_verify_all_steps_complete` - Pass when all done
2. `test_verify_missing_steps` - Fail with list of missing steps
3. `test_verify_no_workflow_steps` - Pass (knowledge skill)

---

## Standards Compliance

### Python 2025+ Standards (`/code-python`)

**Type hints**: Required for all public functions
```python
def set_breadcrumb(skill_name: str, step_name: str) -> None:
    """Mark a workflow step as completed."""
```

**Error handling**: Explicit exception types, not bare `except:`
```python
try:
    log.append(event)
except IOError as e:
    logger.warning(f"Failed to write log: {e}")
    # Fallback strategy
```

**Async patterns**: Use async I/O for log writes if performance critical
```python
async def append_async(self, event: dict) -> None:
    async with aiofiles.open(self.log_path, 'a') as f:
        await f.write(json.dumps(event) + '\n')
```

### Security Standards

**Path validation**: Already implemented (Issue #2 fix)
- Block `.` and `..` in skill names
- Validate file paths before writing

**Log file permissions**: Restrict to owner-only (if on Unix)
```python
import os
os.chmod(log_path, 0o600)  # Owner read/write only
```

**Log rotation**: Prevent disk exhaustion
```python
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
if log_path.stat().st_size > MAX_LOG_SIZE:
    _rotate_log(log_path)
```

---

## Ramifications

### Breaking Changes

**None for immediate implementation**:
- Backward compatibility layer maintains old API
- Skills without workflow_steps work as before (knowledge skills)

**Future major version (v4.0)**:
- Remove legacy JSON format support
- Require all skills to declare workflow_steps
- Deprecate old tracker.py functions

### Backwards Compatibility

**skill-guard library**:
- Old `set_breadcrumb()` API still works
- Existing breadcrumb files readable
- No changes required for current integrations

**Claude Code skills**:
- Optional: Skills CAN declare workflow_steps
- Not required: Skills without workflow_steps work as before
- Progressive rollout: Add to critical skills first (code, trace, arch)

### Performance Impact

**Write performance**:
- **Current**: O(n) where n = state size (entire JSON rewritten)
- **Hybrid**: O(1) append (single line write)
- **Improvement**: 10-100x faster for complex workflows

**Read performance**:
- **Current**: O(n) file read, JSON parse
- **Hybrid**: O(1) cache hit (after first read)
- **Improvement**: 100-1000x faster for cached reads

**Disk usage**:
- **Current**: Single JSON file (small)
- **Hybrid**: JSONL log (grows) + snapshot (small)
- **Tradeoff**: More disk space for audit trail, mitigated by log rotation

---

## Pre-Mortem Analysis

### Failure Mode 1: Log Performance Degradation

**Scenario**: Log file grows to 100k+ lines, replay becomes slow

**Root cause**: No log rotation, every cold start replays entire log

**Preventive actions**:
1. Implement log rotation (archive logs > 10 MB)
2. Write snapshot more frequently (every 5 steps, configurable)
3. Add cold start optimization (load snapshot only, replay log on demand)

**Detection**: Monitor log replay time, alert if > 100ms

**Recovery**: Force immediate snapshot, archive old log

### Failure Mode 2: Concurrent Access Corruption

**Scenario**: Two terminals append to same log simultaneously, file corruption

**Root cause**: File locking not implemented, race condition on write

**Preventive actions**:
1. Use append-only writes (most filesystems atomic for single-line writes)
2. Add file locking (fcntl on Unix, msvcrt on Windows) if needed
3. Test concurrent access with script

**Detection**: Checksum validation on log read, detect corruption

**Recovery**: Restore from last snapshot, discard corrupted log entries

### Failure Mode 3: Skills Declare Wrong workflow_steps

**Scenario**: /code skill declares 9 steps but actually runs 7, verification always fails

**Root cause**: workflow_steps don't match actual implementation

**Preventive actions**:
1. Document best practices for workflow_steps design
2. Provide example SKILL.md frontmatter for common patterns
3. Add validation: warn if step never called during skill execution

**Detection**: Log breadcrumb initialization vs actual steps called

**Recovery**: Update SKILL.md workflow_steps to match implementation

### Failure Mode 4: In-Memory Cache Invalidation Bug

**Scenario**: Cache shows stale state (old step), log has new state

**Root cause**: Cache not updated when log appended, or cache invalidation logic bug

**Preventive actions**:
1. Single source of truth: cache.update_state() always writes to log
2. Cache always invalidated on set_breadcrumb() call
3. Add cache version number to detect staleness

**Detection**: Compare cache state vs log replay in tests

**Recovery**: Clear cache, reload from log

### Failure Mode 5: Snapshot Write Corruption

**Scenario**: Power fails during snapshot write, JSON file truncated

**Root cause**: No atomic write for snapshot (not append-only)

**Preventive actions**:
1. Write to temporary file, atomic rename on completion
2. Validate JSON before replacing old snapshot
3. Keep previous snapshot as backup

**Detection**: JSON parse error on snapshot load

**Recovery**: Load previous snapshot, replay entire log

---

## Implementation Plan

### Phase 1: Quick Wins (2-3 hours)

**Objective**: Enable immediate skill compliance with minimal risk

**Tasks**:
1. Add `workflow_steps` to critical skills' SKILL.md frontmatter
   - Skills: code, trace, arch, package, tdd
   - Action: Edit frontmatter, add workflow_steps list
   - Verification: `skill_guard.breadcrumb.initialize_breadcrumb_trail()` works

2. Add breadcrumb calls to skill hooks (if hooks exist)
   - Example: `/code` calls set_breadcrumb() after each phase
   - Action: Add import and function calls in hook scripts
   - Verification: Breadcrumb file created when skill invoked

3. Add verification to global hooks
   - Hook: PreToolUse or UserPromptSubmit
   - Action: Call verify_breadcrumb_trail() before skill completion
   - Verification: Warning shown when steps missing

**Acceptance criteria**:
- code, trace, arch skills have workflow_steps in SKILL.md
- Breadcrumb files created when skills invoked
- Verification warns on incomplete workflows

### Phase 2: Hybrid Logging Implementation (6-8 hours)

**Objective**: Replace read-modify-write with append-only log + cache + snapshot

**Tasks**:
1. Create new log module (`src/skill_guard/breadcrumb/log.py`)
   - Class: AppendOnlyBreadcrumbLog
   - Methods: append(), replay()
   - Tests: JSONL format, atomicity, replay correctness

2. Create cache module (`src/skill_guard/breadcrumb/cache.py`)
   - Class: BreadcrumbStateCache
   - Methods: get_state(), update_state()
   - Tests: Lazy loading, cache hit/miss, periodic snapshot

3. Modify tracker.py for backward compatibility
   - Keep existing API: set_breadcrumb(), verify_breadcrumb_trail()
   - Delegate to hybrid system internally
   - Optional: Legacy mode flag to use old format

4. Add log rotation support
   - Function: _rotate_log() when size > threshold
   - Archive old logs with timestamp
   - Tests: Rotation triggers at correct size

5. Performance testing
   - Benchmark: 100 steps, compare hybrid vs old
   - Benchmark: 1000 reads, measure cache hit rate
   - Goal: 10x write improvement, 100x read improvement

**Acceptance criteria**:
- All existing tests pass (backward compatibility)
- New tests for log and cache modules pass
- Performance benchmarks show improvement
- Log rotation works correctly

### Phase 3: Query Interface & Tooling (2-4 hours)

**Objective**: Add tooling to inspect breadcrumb history and debug issues

**Tasks**:
1. Add query interface (`src/skill_guard/breadcrumb/query.py`)
   - Function: get_breadcrumb_history(skill_name) - List all events
   - Function: get_breadcrumb_state_at_time(skill_name, timestamp) - Time travel
   - Tests: History reconstruction, time queries

2. Add CLI command for debugging
   - Command: `python -m skill_guard.breadcrumb inspect <skill_name>`
   - Shows: Current state, recent history, missing steps
   - Tests: CLI output format, error handling

3. Add integration tests with real skills
   - Test: Invoke /code skill, verify breadcrumb trail created
   - Test: Kill mid-execution, verify recovery works
   - Test: Concurrent terminals, verify no corruption

**Acceptance criteria**:
- Query interface returns accurate history
- CLI command useful for debugging
- Integration tests pass with real skills

---

## Next Steps

1. **Review this plan** - Confirm architecture and phased approach
2. **Start with Phase 1** - Add workflow_steps to critical skills
3. **Implement Phase 2** - Hybrid logging system with tests
4. **Add Phase 3** - Query interface and debugging tools
5. **Document migration** - Guide for adding workflow_steps to other skills

**Estimated timeline**:
- Phase 1: 2-3 hours (quick wins, low risk)
- Phase 2: 6-8 hours (core implementation, medium risk)
- Phase 3: 2-4 hours (tooling, low risk)
- **Total**: 10-15 hours across 3 phases

**Risk assessment**:
- **Low risk**: Phase 1 (backward compatible, optional)
- **Medium risk**: Phase 2 (core changes, mitigated by tests)
- **Low risk**: Phase 3 (new features, no breaking changes)
