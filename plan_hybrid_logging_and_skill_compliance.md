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

## Multi-Terminal Isolation Architecture

**CRITICAL REQUIREMENT**: The hybrid logging system MUST maintain terminal isolation to prevent context bleed and stale data in multi-terminal environments.

### Terminal-Scoped State Storage

**Directory structure** (same as current system):
```
P:/.claude/state/
├── breadcrumbs_term_abc123/
│   ├── breadcrumb_code.log
│   ├── breadcrumb_code.json
│   ├── breadcrumb_trace.log
│   └── breadcrumb_trace.json
├── breadcrumbs_def456/
│   ├── breadcrumb_code.log
│   └── breadcrumb_code.json
└── breadcrumbs_ghi789/
    └── breadcrumb_package.log
```

**Key principle**: Each terminal has its own isolated breadcrumb directory. No sharing, no cross-terminal reads.

### How Terminal Isolation Works

**1. Terminal Detection** (from `skill_guard.utils.terminal_detection`)
```python
def detect_terminal_id() -> str:
    """Detect terminal ID for state isolation."""
    # Uses terminal_detection.py from utils for consistent ID detection
    # Returns: "term_12345" (unique per terminal session)
    terminal_id = shared_detect()
    return terminal_id
```

**2. Terminal-Scoped File Paths**
```python
def _get_log_file(skill_name: str, terminal_id: str) -> Path:
    """Get log file path for this terminal only."""
    state_subdir = STATE_DIR / f"breadcrumbs_{terminal_id}"
    log_path = state_subdir / f"breadcrumb_{skill_name}.log"
    return log_path
```

**3. No Cross-Terminal Access**
- Terminal A (`term_abc123`) reads/writes `breadcrumbs_term_abc123/breadcrumb_code.log`
- Terminal B (`term_def456`) reads/writes `breadcrumbs_term_def456/breadcrumb_code.log`
- **Never** cross paths between terminals

### Stale Data Prevention

**Problem**: In multi-terminal environments, terminals can see each other's stale state if not isolated.

**Solution**: Terminal-scoped state + validation

**Validation in tracker.py** (already implemented):
```python
def get_breadcrumb_trail(skill_name: str) -> dict[str, Any] | None:
    """Get current breadcrumb trail for a skill.

    Verifies session isolation to prevent cross-terminal contamination.
    """
    trail = json.loads(breadcrumb_file.read_text())

    # Verify session isolation (multi-terminal safety)
    if not verify_session_isolation(trail):
        # Remove stale trail from different session/terminal
        breadcrumb_file.unlink(missing_ok=True)
        return None

    return trail
```

**Session isolation verification**:
```python
def verify_session_isolation(trail: dict[str, Any]) -> bool:
    """Verify that a breadcrumb trail belongs to this terminal.

    CRITICAL: Only checks terminal_id, not session_id.
    Session ID is global across terminals and changes during compaction.

    Returns:
        True if trail belongs to this terminal, False otherwise
    """
    current_terminal_id = detect_terminal_id()
    trail_terminal = trail.get("terminal_id")

    # Only check terminal_id (session_id changes during compaction)
    return trail_terminal == current_terminal_id
```

### Concurrent Access Safety

**Scenario**: Two terminals running same skill simultaneously

**Terminal A**:
```
Invokes /code skill
→ initialize_breadcrumb_trail("code")
→ Creates breadcrumbs_term_abc123/breadcrumb_code.log
→ Appends: {"event": "step_completed", "step": "plan"}
```

**Terminal B** (same time):
```
Invokes /code skill
→ initialize_breadcrumb_trail("code")
→ Creates breadcrumbs_term_def456/breadcrumb_code.log
→ Appends: {"event": "step_completed", "step": "tdd"}
```

**Result**: No conflict, no cross-contamination. Each terminal has its own log file.

### Cleanup Protocol

**Automatic cleanup on SessionEnd**:
```python
def cleanup_session_breadcrumbs() -> int:
    """Clean up all breadcrumb trails for this terminal (SessionEnd hook).

    Called by SessionEnd hook to clean up trails when session terminates.
    This prevents stale breadcrumb trails from littering the filesystem.

    Only cleans up trails from THIS terminal, not other terminals.
    """
    current_terminal_id = detect_terminal_id()
    breadcrumb_dir = _get_breadcrumb_dir()

    for file in breadcrumb_dir.glob("breadcrumb_*.json"):
        trail = json.loads(file.read_text())
        trail_terminal = trail.get("terminal_id")

        # Only clean up trails from this terminal
        if trail_terminal == current_terminal_id:
            file.unlink(missing_ok=True)
```

**Stale trail cleanup on PreCompact**:
```python
def cleanup_stale_breadcrumbs() -> int:
    """Clean up stale breadcrumb trails (PreCompact hook).

    Removes breadcrumb trails that are older than MAX_TRAIL_AGE_SECONDS.
    Also cleans up trails from other terminals (cross-terminal contamination).

    This ensures that stale data from old terminals doesn't accumulate.
    """
    current_terminal_id = detect_terminal_id()

    for file in breadcrumb_dir.glob("breadcrumb_*.json"):
        trail = json.loads(file.read_text())

        # Clean up stale trails (age-based)
        if trail_age > MAX_TRAIL_AGE_SECONDS:
            file.unlink(missing_ok=True)

        # Clean up trails from other terminals
        trail_terminal = trail.get("terminal_id")
        if trail_terminal != current_terminal_id:
            file.unlink(missing_ok=True)
```

---

## Proposed Solution

### Architecture: Hybrid Logging System (Terminal-Scoped + Production-Grade)

**Inspired by production observability research** (see: https://getathenic.com/blog/ai-agent-logging-observability-production)

This hybrid system combines:
- **Event Sourcing pattern** (immutable append-only log) - validated by research as best practice for AI skill state management
- **Terminal-scoped isolation** (multi-terminal safety)
- **Production-grade logging** (structlog, standardized schema)
- **Lightweight query interface** (grep/jq, no custom infrastructure)

**Event Sourcing Pattern Validation** (from research):

The research confirms that Event Sourcing is superior to state files for AI skill tracking:
- **Immutable event log**: Stores sequence of state transitions (not snapshots)
- **Replay capability**: Reconstruct state by replaying events from log
- **Time-travel debugging**: Can see exactly where skill reasoning diverged
- **Audit compliance**: Perfect tamper-proof record of every action
- **Exactly-once semantics**: System knows which side-effects already occurred on resume

Our hybrid logging design (append-only log + in-memory cache + periodic snapshots) aligns with this pattern. The append-only log IS the event source; snapshots are optimization for fast recovery.

**Production-Grade Log Schema** (adapted from OpenTelemetry GenAI conventions):

Research shows that production AI systems require standardized log schemas for observability. We adapt the OpenTelemetry GenAI semantic conventions for local development:

```json
{
  "timestamp": "2026-03-10T12:34:56.789Z",        // ISO 8601 UTC
  "level": "INFO",                                 // DEBUG, INFO, WARN, ERROR
  "service": "skill-guard",                        // System identifier
  "terminal_id": "term_abc123",                    // **CRITICAL**: Multi-terminal isolation
  "session_id": "sess_xyz789",                     // Claude Code session (optional)
  "skill_id": "code",                              // Skill being executed
  "event": "step_completed",                       // Event type
  "message": "Phase TDD completed",                // Human-readable summary
  "trace_id": "abc123def456",                      // Optional: W3C trace ID for distributed tracing
  "span_id": "789xyz012",                          // Optional: Span ID for operation
  "metadata": {                                    // Event-specific data
    "step": "tdd",
    "workflow_steps": ["requirements", "pre-flight", "tdd"],
    "completed_steps": ["requirements", "pre-flight", "tdd"],
    "current_step": "tdd",
    "duration_ms": 1250
  }
}
```

**Key adaptations for local development**:
- **terminal_id**: Added to support multi-terminal isolation (not in OpenTelemetry standard)
- **session_id**: Optional (useful for debugging, but not required for isolation)
- **trace_id/span_id**: Optional (for future distributed tracing integration)
- **metadata**: Flexible dict for skill-specific context

**Implementation with structlog** (from research):

Production systems use structlog for structured logging. We adopt this for consistency:

```python
# File: src/skill_guard/breadcrumb/log.py

import structlog
from pathlib import Path
from typing import Any
import json

class StructlogBreadcrumbLog:
    """Production-grade append-only log using structlog."""

    def __init__(self, skill_name: str, terminal_id: str):
        self.skill_name = skill_name
        self.terminal_id = terminal_id
        self.log_path = _get_log_file(skill_name, terminal_id)

        # Configure structlog for JSON output
        self.logger = structlog.get_logger()
        structlog.configure(
            processors=[
                structlog.processors.JSONRenderer()
            ]
        )

    def append(self, event: str, **kwargs) -> None:
        """Append structured event to log."""
        # Build log entry with standardized schema
        log_entry = {
            "timestamp": time.time(),
            "level": "INFO",
            "service": "skill-guard",
            "terminal_id": self.terminal_id,
            "skill_id": self.skill_name,
            "event": event,
            **kwargs
        }

        # Write to file (JSONL format)
        with open(self.log_path, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
```

**Benefits of structlog**:
- Consistent JSON output (machine-readable)
- Context binding (bind terminal_id once, all logs inherit it)
- Production-ready (used in production systems at scale)
- Easy integration with future log aggregation tools

### Multi-Run Lifecycle: Halted, Resumed, and Multiple Executions

**Critical question**: What happens when a skill is halted mid-execution and run again later?

**Scenario 1: Halted and Resumed in Same Terminal**

```
Day 1, 10:00 AM - Terminal A (term_abc123):
  User invokes /code feature
  → initialize_breadcrumb_trail("code")
  → Creates: breadcrumbs_term_abc123/breadcrumb_code.log
  → Appends: {"event": "step_completed", "step": "requirements"}
  → Appends: {"event": "step_completed", "step": "pre-flight"}
  → User halts execution (Ctrl+C or closes terminal)

Day 1, 2:00 PM - Terminal A (term_abc123):
  User invokes /code feature again
  → initialize_breadcrumb_trail("code")
  → Checks: Does breadcrumbs_term_abc123/breadcrumb_code.log exist? YES
  → Verifies: terminal_id matches (term_abc123 == term_abc123) ✓
  → REPLACES log (starts fresh execution):
      • Archives old log: breadcrumb_code.log.20260310_100000
      • Creates new log: breadcrumb_code.log
      → Appends: {"event": "step_completed", "step": "requirements"}
```

**Behavior**: NEW EXECUTION (not resume). Each skill invocation starts fresh.

**Rationale**: Skills are stateless workflows. If halted, you're starting over, not resuming. The old log is archived for debugging but not used for enforcement.

**Scenario 2: Multiple Runs Over Days (Same Terminal)**

```
Day 1 - Terminal A:
  /code feature → breadcrumb_code.log (run 1)
  /trace code:src/file.py → breadcrumb_trace.log (run 1)

Day 2 - Terminal A (same terminal_id):
  /code feature → breadcrumb_code.log (run 2)
  /arch design API → breadcrumb_arch.log (run 1)

Day 3 - Terminal A (same terminal_id):
  /code feature → breadcrumb_code.log (run 3)
  Logs accumulate: breadcrumb_code.log, breadcrumb_trace.log, breadcrumb_arch.log
```

**Cleanup Process**:
1. **SessionEnd cleanup**: When Claude Code session ends, removes ALL breadcrumb logs for current terminal
   - `cleanup_session_breadcrumbs()` called by SessionEnd hook
   - Deletes: `breadcrumbs_term_abc123/breadcrumb_*.json`
   - Result: Clean slate for next session

2. **PreCompact cleanup**: Every 10 minutes (PreCompact hook), removes stale logs
   - `cleanup_stale_breadcrumbs()` removes logs older than MAX_TRAIL_AGE_SECONDS (2 hours)
   - Also removes logs from OTHER terminals (cross-terminal contamination prevention)
   - Result: No accumulation of stale logs

**Net effect**: Logs don't accumulate indefinitely. SessionEnd cleans current terminal; PreCompact cleans old/stale logs.

**Scenario 3: Concurrent Terminals (Multi-Terminal Isolation)**

```
Terminal A (term_abc123): Runs /code
  → Creates: breadcrumbs_term_abc123/breadcrumb_code.log
  → Appends: {"terminal_id": "term_abc123", "step": "plan"}

Terminal B (term_def456): Runs /code (same time)
  → Creates: breadcrumbs_term_def456/breadcrumb_code.log
  → Appends: {"terminal_id": "term_def456", "step": "tdd"}

Terminal C (term_ghi789): Runs /code (same time)
  → Creates: breadcrumbs_term_ghi789/breadcrumb_code.log
  → Appends: {"terminal_id": "term_ghi789", "step": "audit"}
```

**Behavior**: COMPLETE ISOLATION. No conflicts, no cross-contamination.

**Enforcement Impact**:
- Terminal A's verification only checks Terminal A's breadcrumb
- Terminal B's verification only checks Terminal B's breadcrumb
- Each terminal has independent enforcement state

**Scenario 4: Skill Guard Enforcement on Resumed Execution**

```
Terminal A: User halts /code during TDD phase (step 5 of 9)

Verification check:
  verify_breadcrumb_trail("code")
  → Reads: breadcrumbs_term_abc123/breadcrumb_code.log
  → Parses completed_steps: ["requirements", "pre-flight", "explore", "plan"]
  → Checks workflow_steps: [9 steps total]
  → Result: FAIL - "Missing workflow steps: tdd, test, audit, trace, done"
  → Action: Block or warn about incomplete workflow

Terminal A: User re-runs /code (fresh execution)
  → NEW log created (old log archived)
  → Verification passes only if ALL 9 steps complete in NEW execution
```

**Key principle**: Verification is stateless. It checks the CURRENT log, not historical logs. If halted, you must complete ALL steps in the new execution.

**Log Accumulation Prevention**:

```
SessionEnd (immediate cleanup):
  User closes Claude Code
  → cleanup_session_breadcrumbs()
  → Deletes: breadcrumbs_term_abc123/* (all logs for this terminal)
  → Result: No stale logs left behind

PreCompact (periodic cleanup):
  Runs every ~10 minutes during compaction
  → cleanup_stale_breadcrumbs()
  → Deletes logs older than 2 hours (zombie sessions)
  → Deletes logs from OTHER terminals (cross-terminal contamination)
  → Result: Clean state directory
```

**Summary Table**:

| Scenario | Log Behavior | Enforcement |
|----------|-------------|-------------|
| **Halted mid-execution** | Log archived on next run | New execution starts fresh |
| **Multiple runs same day** | Same log file (overwritten) | Each run independent |
| **Multiple runs over days** | Cleaned by SessionEnd/PreCompact | No accumulation |
| **Concurrent terminals** | Separate logs per terminal | Independent enforcement |
| **Same terminal, next day** | Same terminal_id, same log path | Fresh execution, log replaced |

**Implementation Note**: On `initialize_breadcrumb_trail()`, check if log exists and archive it before creating new log:

```python
def initialize_breadcrumb_trail(skill_name: str) -> None:
    """Initialize breadcrumb trail for a skill."""
    log_path = _get_log_file(skill_name, terminal_id)

    # Archive existing log if present (previous incomplete execution)
    if log_path.exists():
        archive_path = log_path.with_suffix(f".log.{int(time.time())}")
        log_path.rename(archive_path)

    # Create new log for fresh execution
    log_path.touch()
```

This ensures each skill invocation starts with a clean slate.

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

**Multi-Terminal Isolation Tests** (critical for safety):
1. `test_cross_terminal_isolation` - Terminal A cannot read Terminal B's breadcrumbs
2. `test_terminal_scoped_directories` - Each terminal uses separate directory
3. `test_cleanup_only_current_terminal` - SessionEnd only cleans current terminal's trails
4. `test_stale_trail_removal_on_compaction` - PreCompact removes other terminals' stale trails
5. `test_concurrent_terminals_same_skill` - Two terminals running /code simultaneously, no conflicts
6. `test_terminal_id_validation` - Reject breadcrumb trail with different terminal_id

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

### Failure Mode 6: Cross-Terminal Contamination

**Scenario**: Terminal A reads breadcrumb state from Terminal B, causing stale data or incorrect enforcement

**Root cause**: Terminal ID validation missing or bypassed, shared state directory

**Preventive actions**:
1. **Always** include terminal_id in breadcrumb trail initialization
2. **Always** verify terminal_id matches before returning breadcrumb state
3. **Never** read from shared/global breadcrumb directories
4. **Always** use terminal-scoped directory paths: `breadcrumbs_{terminal_id}/`
5. Add assertion in tests: terminal_id in state matches current terminal

**Detection**:
- Test: Create breadcrumbs in terminal A, try to read from terminal B
- Test: Simulate compaction (session_id changes), verify terminal_id still checked
- Test: Verify cleanup only removes current terminal's breadcrumbs

**Recovery**:
- Immediate: Clear stale breadcrumb file, re-initialize for correct terminal
- Long-term: Add terminal_id validation to all breadcrumb read paths

**User impact**:
- **Without isolation**: Terminal A sees Terminal B's incomplete workflow as complete, bypasses enforcement
- **With isolation**: Each terminal has independent breadcrumb state, no cross-contamination

**Example test**:
```python
def test_cross_terminal_isolation():
    """Verify that Terminal A cannot read Terminal B's breadcrumbs."""
    # Terminal A: Initialize and set breadcrumb
    with mock_terminal_id("term_A"):
        initialize_breadcrumb_trail("code")
        set_breadcrumb("code", "plan")

    # Terminal B: Try to read Terminal A's breadcrumb (should fail)
    with mock_terminal_id("term_B"):
        trail = get_breadcrumb_trail("code")
        assert trail is None, "Should not read Terminal A's breadcrumb"

    # Terminal B: Initialize its own breadcrumb (should work)
    with mock_terminal_id("term_B"):
        initialize_breadcrumb_trail("code")
        trail = get_breadcrumb_trail("code")
        assert trail is not None
        assert trail["terminal_id"] == "term_B"
```

---

## Implementation Plan (Updated: Hybrid Enforcement Approach)

**Decision**: Use simplified binary tracking + configurable enforcement levels instead of complex 3-level compliance detection.

**Key Changes from Original Plan**:
- ❌ Removed: 3-level compliance detection (Level 0-3)
- ❌ Removed: Complex compliance detection logic
- ✅ Added: Simple binary tracking (invoked → completed)
- ✅ Added: Configurable enforcement levels (minimal/standard/strict)
- ✅ Added: Auto-inference from tool patterns
- ✅ Added: Zero manual work for most skills

### Phase 1: Core Tracking Implementation (2-3 hours)

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

### Phase 2: Configurable Enforcement System (2-3 hours)

**Objective**: Implement three-tier enforcement levels (minimal/standard/strict)

**Tasks**:
1. Create enforcement level system (`src/skill_guard/breadcrumb/enforcement.py`)
   - Class: `EnforcementLevel` (enum: MINIMAL, STANDARD, STRICT)
   - Function: `get_enforcement_level(skill_name)` - Read from SKILL.md or default to STANDARD
   - Function: `verify_with_enforcement()` - Apply appropriate level checks
   - Tests: All three enforcement levels, default behavior, SKILL.md overrides

2. Update `verify_breadcrumb_trail()` with tiered checks:
   - **MINIMAL**: Duration > 10s + tools_used ≥ 2
   - **STANDARD**: MINIMAL + workflow has ≥2 phases + verification phase required
   - **STRICT**: STANDARD + declared workflow_steps must all be completed
   - Default: STANDARD for all skills (configurable via SKILL.md)

3. Add enforcement level to SKILL.md schema:
   ```yaml
   ---
   name: code
   enforcement_level: strict  # optional: minimal, standard (default), strict
   workflow_steps:
     - requirements
     - design
     - tdd
     - refactor
     - verification
   ---
   ```

4. Update StopHook_breadcrumb_verifier with tiered messages:
   - Show which enforcement level is active
   - Show missing steps for STRICT level
   - Show missing phases for STANDARD level
   - Tests: All three enforcement levels, appropriate messaging

**Acceptance criteria**:
- All existing tests pass (backward compatible)
- New enforcement level tests pass
- Default STANDARD level prevents incomplete workflows
- STRICT level enforces all declared workflow_steps

**Objective**: Replace read-modify-write with append-only log + cache + snapshot

**Tasks**:
1. Create new log module (`src/skill_guard/breadcrumb/log.py`)
   - Class: AppendOnlyBreadcrumbLog
   - Methods: append(), replay()
   - **CRITICAL**: Pass terminal_id to all functions, use terminal-scoped paths
   - Tests: JSONL format, atomicity, replay correctness, **terminal isolation**

2. Create cache module (`src/skill_guard/breadcrumb/cache.py`)
   - Class: BreadcrumbStateCache
   - Methods: get_state(), update_state()
   - **CRITICAL**: Cache key includes terminal_id (e.g., `f"{skill_name}:{terminal_id}"`)
   - Tests: Lazy loading, cache hit/miss, periodic snapshot, **terminal-scoped cache keys**

3. Modify tracker.py for backward compatibility
   - Keep existing API: set_breadcrumb(), verify_breadcrumb_trail()
   - Delegate to hybrid system internally
   - **CRITICAL**: Verify terminal_id validation on all read paths
   - Optional: Legacy mode flag to use old format

4. Add log rotation support
   - Function: _rotate_log() when size > threshold
   - Archive old logs with timestamp
   - Tests: Rotation triggers at correct size

5. **Multi-terminal isolation testing** (CRITICAL for safety)
   - Test: Two terminals create separate logs, no cross-contamination
   - Test: Terminal A cannot read Terminal B's breadcrumb state
   - Test: Cleanup only removes current terminal's trails
   - Test: Concurrent terminals running same skill, no conflicts

6. Performance testing
   - Benchmark: 100 steps, compare hybrid vs old
   - Benchmark: 1000 reads, measure cache hit rate
   - Goal: 10x write improvement, 100x read improvement

**Acceptance criteria**:
- All existing tests pass (backward compatibility)
- New tests for log and cache modules pass
- **Multi-terminal isolation tests pass** (no cross-contamination)
- Performance benchmarks show improvement
- Log rotation works correctly

### Phase 3: Auto-Inference & Tool Tracking (1-2 hours)

**Objective**: Automatically infer workflow steps from tool usage patterns

**Tasks**:
1. Create tool pattern inference system (`src/skill_guard/breadcrumb/inference.py`)
   - Function: `_infer_step_from_tool(tool_name, tool_input)` - Map tools to workflow steps
   - Patterns: WebSearch→research, Read(SKILL.md)→requirements, Edit(test*)→tdd, Bash(pytest)→verification
   - Tests: All major tool types, step mapping accuracy, edge cases

2. Create PostToolUse hook for automatic tracking
   - Hook: `PostToolUse_breadcrumb_tracker.py`
   - Track: Every tool usage with inferred step
   - Build: Unique inferred workflow (preserve order, dedupe)
   - Tests: Tool tracking, inference accuracy, workflow building

3. Update UserPromptSubmit hook for initialization
   - Hook: `UserPromptSubmit_breadcrumb_init.py` (update existing)
   - Detect: Skill invocation via regex (`^/\w+`)
   - Initialize: Simple binary trail (invoked → completed)
   - Set: Active skill in session state
   - Tests: Skill detection, trail initialization, state management

**Acceptance criteria**:
- Tool inference maps major tools to correct steps
- Inferred workflows match actual execution patterns
- PostToolUse tracking doesn't interfere with tool execution
- Integration tests pass with real skill invocations

---

## Next Steps

1. **Implement Phase 1** - Simple binary tracking for all skills
2. **Implement Phase 2** - Configurable enforcement levels (minimal/standard/strict)
3. **Implement Phase 3** - Auto-inference from tool patterns
4. **Test with critical skills** - Add `enforcement_level: strict` to 5-10 skills
5. **Document SKILL.md usage** - Show how to add enforcement_level and workflow_steps

**Estimated timeline**:
- Phase 1: 2-3 hours (core tracking, works for all 234 skills)
- Phase 2: 2-3 hours (enforcement levels, default STANDARD)
- Phase 3: 1-2 hours (auto-inference from tools)
- **Total**: 5-8 hours (vs. 10-15 hours for original complex approach)

**Risk assessment**:
- **Low risk**: Phase 1 (backward compatible, zero manual work)
- **Low risk**: Phase 2 (default STANDARD level prevents most issues)
- **Low risk**: Phase 3 (inference failures don't block tools)
- **Medium risk**: Adding `enforcement_level: strict` to skills (requires testing)

**Key simplification from original plan**:
- ❌ Removed: Complex 3-level compliance detection (Level 0-3)
- ❌ Removed: Manual workflow_steps required for all 234 skills
- ❌ Removed: Compliance detection and feedback system
- ✅ Added: Simple binary tracking (invoked → completed)
- ✅ Added: Auto-inference from tool patterns
- ✅ Added: Configurable enforcement (minimal/standard/strict)
- ✅ Added: Default STANDARD level works for all skills immediately

---

## Architecture Decision Record: Simplified Enforcement

**Date**: 2026-03-10
**Status**: Accepted
**Decision**: Use simple binary tracking + configurable enforcement levels

### Problem Statement

Original plan proposed 3-level compliance detection (Level 0-3) requiring:
- Compliance detection logic for all 234 skills
- Manual workflow_steps addition to each skill
- Complex feedback system about compliance levels
- High implementation cost (10-15 hours)

### Alternative Considered

**Option A: Complex 3-Level Compliance** (Original plan)
- Level 0: Skill not found
- Level 1: Generic tracking (no workflow_steps)
- Level 2: Declared only (workflow_steps exist, no hooks)
- Level 3: Full tracking (workflow_steps + hooks)

**Rejected because**:
- Too complex for the actual problem
- Requires manual work for all 234 skills
- Over-engineering for "prevent false completion claims"

**Option B: Just-in-Time Declaration** (Rejected)
- Prompt user to define workflow_steps on first invocation
- Rejected: Interrupts workflow, inconsistent quality

### Decision: Hybrid Enforcement

**Three enforcement levels** (minimal/standard/strict):

| Level | Duration | Tools | Workflow | workflow_steps | Default |
|-------|----------|-------|----------|----------------|--------|
| **minimal** | ✅ | ✅ | ❌ | ❌ | Opt-in |
| **standard** | ✅ | ✅ | ✅ | ❌ | **✅ Yes** |
| **strict** | ✅ | ✅ | ✅ | ✅ | Opt-in |

**Key features**:
- ✅ **Default STANDARD works for all skills immediately** (zero manual work)
- ✅ **Auto-inference from tool patterns** (no manual step tracking)
- ✅ **Opt-in STRICT for critical skills** (add `enforcement_level: strict` to SKILL.md)
- ✅ **Simple implementation** (5-8 hours vs. 10-15 hours)

### Enforcement Rules

**MINIMAL** (for simple utilities):
```python
if duration < 10 seconds: BLOCK
if tool_count < 2: BLOCK
```

**STANDARD** (default for most skills):
```python
if duration < 10 seconds: BLOCK
if tool_count < 2: BLOCK
if len(inferred_workflow) < 2: BLOCK
if "verification" not in inferred_workflow: BLOCK
```

**STRICT** (for critical skills like /code, /tdd):
```python
if duration < 10 seconds: BLOCK
if tool_count < 2: BLOCK
if len(inferred_workflow) < 2: BLOCK
if "verification" not in inferred_workflow: BLOCK
# PLUS: check declared workflow_steps
if step not in completed_steps: BLOCK
```

### Consequences

**Positive**:
- ✅ All 234 skills get protection immediately (default STANDARD)
- ✅ Zero manual work for most skills
- ✅ Simple implementation (5-8 hours)
- ✅ Can upgrade critical skills to STRICT later

**Negative**:
- ⚠️ STANDARD level doesn't enforce specific step order
- ⚠️ Need to add `enforcement_level: strict` for critical skills

### Migration Path

**Week 1**: Implement with STANDARD default
- All skills protected immediately
- No SKILL.md changes required

**Week 2**: Add STRICT to 5-10 critical skills
```yaml
---
name: code
enforcement_level: strict
workflow_steps:
  - requirements
  - design
  - tdd
  - refactor
  - verification
---
```

**Week 3+**: Expand based on real usage patterns

### References

- User conversation: 2026-03-10
- Architecture discussion: `/arch "do you think it will still accomplish what I want for skill enforcement?"`
- Decision rationale: Prevents false completion claims without over-engineering

---

## Feature Flag Removal Plan

### Overview

Use environment-based feature flags to enable gradual rollout of hybrid logging. This allows:
- Testing in specific terminals without affecting others
- Easy rollback if issues are discovered
- Safe migration path from old breadcrumb system
- Production validation before full deployment

### Phase-by-Phase Migration

#### Phase 1: Implementation (Feature Flag OFF)

**Implementation with feature flag:**
```python
# src/skill_guard/breadcrumb/tracker.py
import os

USE_HYBRID_LOGGING = os.environ.get("SKILL_GUARD_HYBRID_LOGGING", "false") == "true"

def initialize_breadcrumb_trail(skill_name: str) -> None:
    """Initialize breadcrumb trail for a skill."""
    if USE_HYBRID_LOGGING:
        # New system: StructlogBreadcrumbLog
        log = StructlogBreadcrumbLog(skill_name, terminal_id)
        log.append(
            "trail_initialized",
            workflow_steps=workflow_steps,
            current_step="initialize"
        )
    else:
        # Old system: Breadcrumb files
        trail = {
            "skill": skill_lower,
            "terminal_id": detect_terminal_id(),
            "initialized_at": time.time(),
            "workflow_steps": workflow_steps,
            "completed_steps": [],
            "current_step": "initialize",
            "last_updated": time.time()
        }
        breadcrumb_file.write_text(json.dumps(trail, indent=2))
```

**Configuration:**
- Default: `USE_HYBRID_LOGGING = false` (old system active)
- Test: `SKILL_GUARD_HYBRID_LOGGING=true claude` (new system in specific terminal)

#### Phase 2: Testing & Gradual Rollout

**Test in specific terminals:**
```bash
# Terminal 1: Test new system
SKILL_GUARD_HYBRID_LOGGING=true claude

# Terminal 2: Keep using old system
claude  # No environment variable
```

**Run tests with both systems:**
```bash
# Test old system (default)
pytest tests/ -v

# Test new system
SKILL_GUARD_HYBRID_LOGGING=true pytest tests/ -v

# Verify both work correctly
```

**Benefits:**
- Terminal 1 validates new system
- Terminal 2 provides rollback safety
- Compare behavior side-by-side
- Zero risk to production workflow

#### Phase 3: Enable by Default (Reversible)

**Flip the default value:**
```python
# src/skill_guard/breadcrumb/tracker.py
USE_HYBRID_LOGGING = os.environ.get("SKILL_GUARD_HYBRID_LOGGING", "true") == "true"
```

**Migration script for existing breadcrumb files:**
```python
# scripts/migrate_to_hybrid_logging.py
def migrate_existing_breadcrumbs():
    """Convert old breadcrumb files to log format."""
    breadcrumb_dir = Path.home() / ".claude" / "breadcrumbs" / terminal_id

    for old_file in breadcrumb_dir.glob("*.json"):
        try:
            data = json.loads(old_file.read_text())

            # Append to log as historical event
            log_path = _get_log_file(data["skill"], terminal_id)
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    "timestamp": data.get("created_at", time.time()),
                    "level": "INFO",
                    "service": "skill-guard",
                    "terminal_id": data["terminal_id"],
                    "skill_id": data["skill"],
                    "event": "migrated_from_old_system",
                    "message": f"Migrated from breadcrumb file: {old_file.name}",
                    "metadata": data
                }) + '\n')

            # Archive old file (don't delete yet)
            archive_path = old_file.with_suffix(f".json.migrated.{int(time.time())}")
            old_file.rename(archive_path)

        except Exception as e:
            print(f"Failed to migrate {old_file}: {e}")
```

**Verification:**
```bash
# 1. All tests pass
pytest tests/ -v

# 2. No references to old system
grep -r "breadcrumb_file.write_text" src/  # Should return empty

# 3. Hooks work with new system
claude  # Should use hybrid logging by default
```

#### Phase 4: Cleanup (Remove Old Code)

**Step 1: Remove feature flag entirely**
```python
# src/skill_guard/breadcrumb/tracker.py - BEFORE
USE_HYBRID_LOGGING = os.environ.get("SKILL_GUARD_HYBRID_LOGGING", "true") == "true"

def initialize_breadcrumb_trail(skill_name: str) -> None:
    if USE_HYBRID_LOGGING:
        StructlogBreadcrumbLog(skill_name, terminal_id).append(...)
    else:
        # Old breadcrumb file system...

# src/skill_guard/breadcrumb/tracker.py - AFTER
def initialize_breadcrumb_trail(skill_name: str) -> None:
    """Initialize breadcrumb trail for a skill."""
    StructlogBreadcrumbLog(skill_name, terminal_id).append(
        "trail_initialized",
        workflow_steps=workflow_steps,
        current_step="initialize"
    )
```

**Step 2: Remove old breadcrumb file functions**
```python
# DELETE these functions from tracker.py:
# - _read_breadcrumb_file()
# - _write_breadcrumb_file()
# - _update_breadcrumb_file()
# - Any function using read-modify-write pattern
```

**Step 3: Remove old tests**
```bash
# Archive old breadcrumb tests
mkdir tests/legacy_breadcrumb_tests
mv tests/test_breadcrumb_files.py tests/legacy_breadcrumb_tests/

# Keep tests for new system
# tests/test_hybrid_logging.py
# tests/test_structlog_breadcrumb.py
```

**Step 4: Update documentation**
```python
# CLAUDE.md - Remove old documentation
# breadcrumb_files.md → DELETE or ARCHIVE
# hybrid_logging.md → UPDATE (remove "experimental" label)
```

#### Phase 5: Final Cleanup (After 30 days)

```bash
# Remove archived breadcrumb files
find ~/.claude/breadcrumbs_*/ -name "*.json.migrated.*" -mtime +30 -delete

# Remove archived tests
rm -rf tests/legacy_breadcrumb_tests/

# Confirm cleanup
pytest tests/ -v  # All tests should pass
```

### Safety Checks During Migration

**Pre-removal checklist:**
```bash
# 1. Verify all tests pass with new system
pytest tests/ -v

# 2. Verify no references to old functions
grep -r "_read_breadcrumb_file" src/
grep -r "breadcrumb_file.write_text" src/

# 3. Verify no feature flag references
grep -r "USE_HYBRID_LOGGING" src/
grep -r "SKILL_GUARD_HYBRID_LOGGING" src/

# 4. Check hooks don't reference old system
grep -r "breadcrumb_file" .claude/hooks/
```

**If any references found, update or remove them.**

### Rollback Plan

**If issues discovered after removal:**

```bash
# Option 1: Restore from git tag
git checkout hybrid-logging-pre-removal

# Option 2: Cherry-pick the commit
git cherry-pick abc123  # Commit before removal

# Option 3: Re-enable feature flag temporarily
export SKILL_GUARD_HYBRID_LOGGING=false
```

### Timeline Suggestion

- **Week 1**: Implement with flag (default false)
- **Week 2**: Test with flag enabled in 1-2 terminals
- **Week 3**: Enable flag by default (reversible)
- **Week 4**: Monitor for issues
- **Week 5**: Remove feature flag if no issues
- **Week 9**: Final cleanup of archived files (30 days later)

### Key Principle

**Keep old code paths until new system is proven in production.** Feature flags make this easy — just flip the default value. This approach provides:

- ✅ Zero breaking changes during transition
- ✅ Easy rollback if issues discovered
- ✅ Side-by-side testing in production
- ✅ Gradual rollout across terminals
- ✅ Production validation before full commitment

---

## Complete Migration Checklist

### Pre-Migration
- [ ] All existing tests pass
- [ ] Documentation updated with new system
- [ ] Backup of current breadcrumb files created
- [ ] Feature flag implementation reviewed

### Phase 1: Implementation
- [ ] Feature flag added to tracker.py
- [ ] New StructlogBreadcrumbLog class implemented
- [ ] Tests for both old and new paths
- [ ] Documentation updated with flag usage

### Phase 2: Testing
- [ ] Test in specific terminal with flag enabled
- [ ] Run full test suite with both flag values
- [ ] Performance benchmarks compared
- [ ] Multi-terminal isolation verified

### Phase 3: Enable by Default
- [ ] Flip feature flag default to true
- [ ] Migration script created and tested
- [ ] Run migration on existing breadcrumb files
- [ ] Verify production workflows work

### Phase 4: Remove Old Code
- [ ] Remove feature flag entirely
- [ ] Delete old breadcrumb file functions
- [ ] Archive old tests
- [ ] Update all documentation
- [ ] Run safety check checklist

### Phase 5: Final Cleanup
- [ ] Wait 30 days for validation period
- [ ] Remove archived breadcrumb files
- [ ] Remove archived tests
- [ ] Final verification: all tests pass
- [ ] Create git tag for post-migration state
