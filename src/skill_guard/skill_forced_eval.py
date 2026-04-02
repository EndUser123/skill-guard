"""Skill Forced-Eval Hook.

When user types /skill-name anywhere in prompt:
1. Enumerate ALL available skills with YES/NO/reasoning
2. Mark the invoked skill as YES (forced by / detection)
3. Check if OTHER skills are also relevant to the full prompt context
4. Invoke ALL YES-marked skills before implementation
5. Log the full decision matrix

Multi-terminal isolation: State files scoped by terminal_id
Stale data immunity: TTL-based cleanup
Compact immunity: Re-triggers fresh on post-compaction turn via handoff chain
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # yaml optional - will skip frontmatter parsing

from __lib.hook_base import get_terminal_id
from UserPromptSubmit_modules.base import HookContext, HookResult
from UserPromptSubmit_modules.registry import register_hook

# Paths to skills directories (home, plugins, project)
SKILLS_DIRS = [
    Path.home() / ".claude" / "skills",  # ~/.claude/skills
    Path("P:/.claude/skills"),  # project-level skills
]

# Pattern to detect slash commands - must be at word boundary with /
# Only matches actual slash commands like /gto, /code, not /r within words
_SLASH_COMMAND_RE = re.compile(r"(?:^|(?<=\s))\/([a-z][a-z0-9-]*)(?=\s|$|\?)", re.IGNORECASE)

# State directory for skill forced-eval
_HOOKS_DIR = Path(__file__).resolve().parent.parent
_STATE_DIR = _HOOKS_DIR / "state" / "skill_forced_eval"
_FALLBACK_STATE_DIR = Path.home() / ".claude" / "hooks" / "state" / "skill_forced_eval"

# TTL for state files (5 minutes - matches skill pattern gate TTL)
_STATE_TTL_SECONDS = 300


def _get_state_dir() -> Path:
    """Get state directory, creating it if needed."""
    for base in (_STATE_DIR, _FALLBACK_STATE_DIR):
        try:
            base.mkdir(parents=True, exist_ok=True)
            return base
        except Exception:
            continue
    return _FALLBACK_STATE_DIR


def _get_terminal_id(context: HookContext) -> str:
    """Get terminal ID from hook context."""
    data = context.data or {} if context.data else {}
    return get_terminal_id(data)


def _safe_id(value: str) -> str:
    """Sanitize ID for use in filenames."""
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value)


def _discover_registered_skills() -> list[str]:
    """Discover all registered skill names from all skills directories."""
    skills = []
    seen = set()

    for skills_dir in SKILLS_DIRS:
        if not skills_dir.exists():
            continue

        # Add plugin skills directories (only from plugins/ subdirectory)
        plugins_dir = skills_dir.parent / "plugins"
        if plugins_dir.exists():
            for plugin_dir in plugins_dir.iterdir():
                if plugin_dir.is_dir() and (plugin_dir / "skills").exists():
                    plugin_skills = plugin_dir / "skills"
                    for item in plugin_skills.iterdir():
                        if item.is_dir() and (item / "SKILL.md").exists():
                            skill_name = item.name.lower()
                            if skill_name not in seen and not skill_name.startswith("_"):
                                seen.add(skill_name)
                                skills.append(skill_name)

        # Add main skills directory
        for item in skills_dir.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                skill_name = item.name.lower()
                if skill_name not in seen and not skill_name.startswith("_"):
                    seen.add(skill_name)
                    skills.append(skill_name)

    return sorted(skills)


def _get_skill_frontmatter(skill_name: str) -> dict:
    """Read SKILL.md frontmatter for a skill, returning allowed-tools if present.

    Returns:
        dict with 'allowed_tools' key (list of strings) and other frontmatter fields
    """
    result = {"allowed_tools": []}

    for skills_dir in SKILLS_DIRS:
        if not skills_dir.exists():
            continue

        # Check plugin skills
        plugins_dir = skills_dir.parent / "plugins"
        if plugins_dir.exists():
            for plugin_dir in plugins_dir.iterdir():
                if plugin_dir.is_dir() and (plugin_dir / "skills").exists():
                    skill_path = plugin_dir / "skills" / skill_name / "SKILL.md"
                    if skill_path.exists():
                        data = _parse_frontmatter(skill_path)
                        if data:
                            return data

        # Check main skills directory
        skill_path = skills_dir / skill_name / "SKILL.md"
        if skill_path.exists():
            data = _parse_frontmatter(skill_path)
            if data:
                return data

    return result


def _parse_frontmatter(skill_path: Path) -> dict:
    """Parse YAML frontmatter from SKILL.md file.

    Handles both YAML list format and space-delimited string format for allowed-tools.
    """
    result = {"allowed_tools": []}

    if yaml is None:
        return result

    try:
        content = skill_path.read_text(encoding="utf-8")
    except Exception:
        return result

    # Extract frontmatter block
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return result

    try:
        data = yaml.safe_load(match.group(1))
        if not isinstance(data, dict):
            return result

        # Handle allowed-tools field
        allowed = data.get("allowed-tools", [])
        if isinstance(allowed, str):
            # Space-delimited string format
            result["allowed_tools"] = allowed.split()
        elif isinstance(allowed, list):
            # YAML list format
            result["allowed_tools"] = [str(x) for x in allowed]
        elif allowed is None:
            result["allowed_tools"] = []

        # Extract other useful fields
        for field in ("name", "description", "enforcement", "version"):
            if field in data:
                result[field] = data[field]

    except Exception:
        pass

    return result


def _get_all_skill_metadata() -> dict[str, dict]:
    """Get metadata including allowed-tools for all skills."""
    skills = _discover_registered_skills()
    metadata = {}
    for skill in skills:
        metadata[skill] = _get_skill_frontmatter(skill)
    return metadata


# Cache registered skills and metadata to avoid repeated filesystem scans
_registered_skills: list[str] | None = None
_skill_metadata: dict[str, dict] | None = None


def _get_registered_skills() -> list[str]:
    """Get cached list of registered skills."""
    global _registered_skills
    if _registered_skills is None:
        _registered_skills = _discover_registered_skills()
    return _registered_skills


def _get_skill_metadata() -> dict[str, dict]:
    """Get cached skill metadata including allowed-tools."""
    global _skill_metadata
    if _skill_metadata is None:
        _skill_metadata = _get_all_skill_metadata()
    return _skill_metadata


def _clear_caches() -> None:
    """Clear skill caches - call after TTL expiry or state restore."""
    global _registered_skills, _skill_metadata
    _registered_skills = None
    _skill_metadata = None


def _extract_slash_commands(prompt: str) -> list[str]:
    """Extract all slash commands from prompt."""
    matches = _SLASH_COMMAND_RE.findall(prompt)
    return [m.lower() for m in matches if m]


def _get_matching_skills(prompt: str) -> list[str]:
    """Get slash commands in prompt that match registered skills."""
    slash_commands = _extract_slash_commands(prompt)
    registered = set(_get_registered_skills())
    return [cmd for cmd in slash_commands if cmd in registered]


def _format_skill_list(skills: list[str], metadata: dict[str, dict]) -> str:
    """Format skill list with allowed-tools for the evaluation template."""
    if not skills:
        return "  (No skills found)"

    lines = []
    for name in skills:
        tools = metadata.get(name, {}).get("allowed_tools", [])
        tools_str = f" [tools: {', '.join(tools)}]" if tools else ""
        lines.append(f"  - {name}{tools_str}")
    return "\n".join(lines)


def _detect_tool_conflicts(metadata: dict[str, dict], skills: list[str]) -> list[tuple[str, str]]:
    """Detect tool conflicts between skills.

    Returns list of (skill1, skill2) tuples where tools conflict.
    A conflict occurs when one skill requires Bash and another requires only read-only tools.
    """
    conflicts = []
    skill_tools = {}

    for skill in skills:
        tools = set(metadata.get(skill, {}).get("allowed_tools", []))
        skill_tools[skill] = tools

    # Check for Bash vs read-only conflicts
    bash_skills = {s for s, tools in skill_tools.items() if "Bash" in tools}
    readonly_skills = {s for s, tools in skill_tools.items() if tools and tools.issubset({"Read", "Edit", "Write", "Glob", "Grep"})}

    for bash_skill in bash_skills:
        for readonly_skill in readonly_skills:
            if bash_skill != readonly_skill:
                conflicts.append((bash_skill, readonly_skill))

    return conflicts


def _format_conflict_report(conflicts: list[tuple[str, str]]) -> str:
    """Format tool conflict report for instruction."""
    if not conflicts:
        return "No tool conflicts detected between selected skills."

    lines = ["## Tool Conflicts Detected"]
    lines.append("")
    lines.append("The following skill pairs have conflicting tool requirements:")
    for skill1, skill2 in conflicts:
        lines.append(f"  - {skill1} ↔ {skill2} (requires serial execution)")
    lines.append("")
    lines.append("**Resolution**: Execute conflicting skills SERIALLY (one completes before next starts).")
    lines.append("Non-conflicting skills MAY be executed in PARALLEL.")

    return "\n".join(lines)


def _save_eval_state(context: HookContext, invoked_skills: list[str], metadata: dict[str, dict]) -> None:
    """Save evaluation state to terminal-scoped file for compact immunity."""
    terminal_id = _get_terminal_id(context)
    if not terminal_id:
        return

    safe_terminal = _safe_id(terminal_id)
    state_data = {
        "invoked_skills": invoked_skills,
        "metadata": metadata,
        "all_skills": _get_registered_skills(),
        "timestamp": datetime.now().isoformat(),
        "created_at": time.time(),
        "terminal_id": terminal_id,
    }

    content = json.dumps(state_data)

    try:
        state_dir = _get_state_dir()
        state_file = state_dir / f"eval_state_{safe_terminal}.json"
        tmp = state_file.with_suffix(".tmp")

        for attempt in range(2):
            try:
                tmp.write_text(content, encoding="utf-8")
                tmp.replace(state_file)
                break
            except OSError:
                if attempt == 1:
                    raise
                time.sleep(0.05)

    except Exception:
        pass  # Best-effort - state capture failure should not block hook


def _load_eval_state(context: HookContext) -> dict | None:
    """Load evaluation state from terminal-scoped file if not stale."""
    terminal_id = _get_terminal_id(context)
    if not terminal_id:
        return None

    safe_terminal = _safe_id(terminal_id)

    for state_dir in (_STATE_DIR, _FALLBACK_STATE_DIR):
        if not state_dir.exists():
            continue

        state_file = state_dir / f"eval_state_{safe_terminal}.json"
        if not state_file.exists():
            continue

        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))

            # Check TTL using filesystem mtime (NOT attacker-controlled JSON created_at)
            # SEC-FE-001 fix: state_file mtime is not user-controlled
            mtime = state_file.stat().st_mtime
            if time.time() - mtime > _STATE_TTL_SECONDS:
                # Stale - clear and return None
                state_file.unlink(missing_ok=True)
                _clear_caches()
                return None

            # Verify terminal_id matches
            if data.get("terminal_id") != terminal_id:
                return None

            return data

        except Exception:
            continue

    return None


def _clear_eval_state(context: HookContext) -> None:
    """Clear evaluation state file."""
    terminal_id = _get_terminal_id(context)
    if not terminal_id:
        return

    safe_terminal = _safe_id(terminal_id)

    for state_dir in (_STATE_DIR, _FALLBACK_STATE_DIR):
        try:
            state_file = state_dir / f"eval_state_{safe_terminal}.json"
            state_file.unlink(missing_ok=True)
        except Exception:
            continue


def _cleanup_stale_state_files() -> int:
    """Remove stale state files older than TTL. Returns count of removed files."""
    removed = 0
    now = time.time()

    for state_dir in (_STATE_DIR, _FALLBACK_STATE_DIR):
        if not state_dir.exists():
            continue

        for state_file in state_dir.glob("eval_state_*.json"):
            try:
                # Use filesystem mtime for TTL check (not JSON created_at - SEC-FE-001 fix)
                mtime = state_file.stat().st_mtime
                if now - mtime > _STATE_TTL_SECONDS:
                    state_file.unlink(missing_ok=True)
                    removed += 1
            except Exception:
                continue

    if removed > 0:
        _clear_caches()

    return removed


@register_hook("skill_forced_eval", priority=0.5)
def skill_forced_eval_hook(context: HookContext) -> HookResult:
    """Enumerate all skills with YES/NO when slash command detected in prompt.

    This hook runs at priority 0.5 (before skill_enforcer at 1.0).

    Multi-terminal isolation: State files scoped by terminal_id
    Stale data immunity: TTL-based cleanup on each invocation
    Compact immunity: Re-triggers fresh on post-compaction turn via handoff chain
    """
    # Cleanup stale files on each invocation
    _cleanup_stale_state_files()

    prompt = context.prompt or ""

    # Only trigger if slash command(s) detected
    invoked_skills = _get_matching_skills(prompt)
    if not invoked_skills:
        _clear_eval_state(context)
        return HookResult.empty()

    # Get all registered skills and metadata
    all_skills = _get_registered_skills()
    if not all_skills:
        return HookResult.empty()

    metadata = _get_skill_metadata()

    # Save state for compact immunity
    _save_eval_state(context, invoked_skills, metadata)

    # Format the skill list with allowed-tools
    skill_list = _format_skill_list(all_skills, metadata)

    # Detect tool conflicts
    conflicts = _detect_tool_conflicts(metadata, invoked_skills)
    conflict_report = _format_conflict_report(conflicts)

    # Build the forced-eval instruction
    if len(invoked_skills) == 1:
        forced_skill = invoked_skills[0]
        forced_tools = metadata.get(forced_skill, {}).get("allowed_tools", [])
        tools_note = f" (requires: {', '.join(forced_tools)})" if forced_tools else ""
        instruction = f"""\
SKILL EVALUATION REQUIRED

You referenced /{forced_skill}{tools_note} in your request. This skill is YES (forced by explicit invocation).

Before processing, you MUST enumerate ALL available skills and make an explicit YES/NO decision.

## Available Skills
{skill_list}

## Your Task Context
{prompt}

## Evaluation Rules
For EACH skill above, output:
  [skill_name]: YES or NO
  Reason: One sentence explaining why this skill is or isn't relevant (≥1% relevance = YES)

Note: /{forced_skill} is YES — it was explicitly invoked. But ALSO check if other skills
are relevant to your full task context.

## Mandatory Invocation
For every skill marked YES:
  1. Immediately call Skill("[skill_name]") — BEFORE any implementation
  2. Do NOT proceed to task implementation until all YES skills are evaluated

## Tool Information
{conflict_report}

## Why This Works
- Explicit YES/NO per-skill prevents rationalizing away secondary skills
- Forces discovery of skills you didn't explicitly invoke
- Decision log is auditable — you can verify which skills were considered
- Tool conflict detection ensures correct serial/parallel execution

Do NOT use Bash, Read, Glob, or any other tool before completing skill evaluation.
"""
    else:
        # Multiple skills invoked
        forced_list = ", ".join(f"/{s}" for s in invoked_skills)
        tools_parts = []
        for s in invoked_skills:
            t = metadata.get(s, {}).get("allowed_tools", [])
            if t:
                tools_parts.append(f"/{s} requires: {', '.join(t)}")
        tools_note = "\n".join(tools_parts)
        if tools_note:
            tools_note = f"\n### Invoked Skills Tool Requirements\n{tools_note}\n"

        instruction = f"""\
SKILL EVALUATION REQUIRED

You referenced {forced_list} in your request. These skills are YES (forced by explicit invocation).

Before processing, you MUST enumerate ALL available skills and make an explicit YES/NO decision.

## Available Skills
{skill_list}

## Your Task Context
{prompt}

## Evaluation Rules
For EACH skill above, output:
  [skill_name]: YES or NO
  Reason: One sentence explaining why this skill is or isn't relevant (≥1% relevance = YES)

Note: {forced_list} are YES — they were explicitly invoked. But ALSO check if OTHER skills
are relevant to your full task context.

## Mandatory Invocation
For every skill marked YES:
  1. Immediately call Skill("[skill_name]") — BEFORE any implementation
  2. Do NOT proceed to task implementation until all YES skills are evaluated

## Tool Information
{conflict_report}
{tools_note}

## Why This Works
- Explicit YES/NO per-skill prevents rationalizing away secondary skills
- Forces discovery of skills you didn't explicitly invoke
- Decision log is auditable — you can verify which skills were considered
- Tool conflict detection ensures correct serial/parallel execution

Do NOT use Bash, Read, Glob, or any other tool before completing skill evaluation.
"""

    # Estimate tokens (~4 chars per token)
    token_count = len(instruction) // 4

    return HookResult(context=instruction, tokens=token_count, priority=0.5)
