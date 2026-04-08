---
type: infrastructure
load_when: creation, quality
priority: recommended
estimated_lines: 60
---

# GTO Skill Coverage Logging

Skills that emit GTO-trackable findings (verification results, gap analyses, quality reports) should log their execution to the GTO skill coverage log so GTO knows they were run and can suppress redundant suggestions.

## Shared Library

```
from gto.lib.skill_coverage_detector import _append_skill_coverage
```

**Requires** `P:/.claude/skills` in `sys.path`.

## Call Signature

```python
_append_skill_coverage(
    target_key: str,    # e.g. "hooks/my_hook" or "skills/my-skill"
    skill: str,          # e.g. "/verify", "/critique"
    terminal_id: str,     # Terminal identifier for this session
    git_sha: str | None = None,
) -> bool
```

Returns `True` if appended successfully, `False` otherwise. **Best-effort** — always succeeds silently; never raises.

## Output Location

`~/.evidence/skill_coverage/{sanitized_target_key}.jsonl`

Where `~/.evidence` = `Path.home() / ".evidence"` = e.g. `C:\Users\<user>\.evidence\`

Format (one JSON object per line):
```json
{"skill": "/verify", "target": "hooks/Stop_skill_question_marker", "terminal_id": "console_abc123", "timestamp": "2026-03-30T...", "git_sha": null}
```

## When to Use

**Use it** when your skill produces findings that GTO should track — so GTO won't suggest running your skill again if nothing has changed since the last run.

Examples:
- `/verify` — logs when verification was run on a target
- `/critique` — logs when quality review was run
- Gap analysis skills — logs when gaps were detected

**Don't use it** for:
- Utility skills (formatters, calculators) with transient output
- Skills that are purely informational with no actionable output
- Skills whose findings are fully captured by other skills' coverage logs

## How GTO Uses It

1. GTO reads `skill_coverage` log entries when `gaps == 0`
2. Checks git state to detect staleness (if files changed since last run, coverage is stale)
3. Suppresses suggestions for skills that have fresh coverage on the target
4. Surfaces `SKILL-CHANGE-/verify` findings when no fresh coverage exists for a target that changed

## Activation Signals

Your skill should log coverage when ALL of:
1. Skill produces durable findings or verification results
2. Findings could inform future sessions (not just this session's transient output)
3. Re-running the skill would have different value than noting "already ran here"

## Sys.path Setup

In the module that calls `_append_skill_coverage`:

```python
from pathlib import Path
import sys

_gto_lib = Path("P:/.claude/skills")
if str(_gto_lib) not in sys.path:
    sys.path.insert(0, str(_gto_lib))
from gto.lib.skill_coverage_detector import _append_skill_coverage
```

## Integration with Phase 3b

Phase 3b quality gate checks for GTO coverage logging correctness when applicable. The reviewer checks:

1. **Activation signal met?** — Does this skill type warrant GTO coverage logging?
2. **Import correct?** — Uses `from gto.lib.skill_coverage_detector import _append_skill_coverage` with proper `sys.path` setup
3. **Call signature correct?** — Uses only `target_key`, `skill`, `terminal_id`, `git_sha` (no `project_root`)
4. **Best-effort wrapper** — Call is wrapped in `try/except` so failures don't crash the skill

See `references/phase3-validation-details.md#phase-3b` for the full checklist.
