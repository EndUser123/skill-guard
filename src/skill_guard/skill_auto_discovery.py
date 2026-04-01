"""
Universal Skill Auto-Discovery and Enforcement
==============================================

Automatically discovers and enforces ALL skills without manual registration.

Replaces manual SKILL_EXECUTION_REGISTRY with dynamic discovery from filesystem.
Maintains backwards compatibility for explicit registry entries.

Author: CSF NIP
Version: 1.0.0
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# Knowledge skills that are NOT enforced (reference/documentation only)
KNOWLEDGE_SKILLS = {
    "standards",
    "constraints",
    "techniques",
    "evidence-tiers",
    "constitutional-patterns",
    "cognitive-frameworks",
    "prompt_refiner",
    "library-first",
    "solo-dev-authority",
    "data-safety-vcs",
    "search",
    "cks",
    "analyze",
    "discover",
    "ask",
}


def discover_all_skills(
    skills_dir: str | Path = "P:/.claude/skills",
) -> dict:
    """
    Auto-discover ALL skills from SKILL.md frontmatter.

    Scans .claude/skills/*/SKILL.md files and extracts metadata from frontmatter.

    Args:
        skills_dir: Path to skills directory (default: P:/.claude/skills)

    Returns:
        Dictionary mapping skill names to their configurations:
        {
            "skill_name": {
                "name": "skill_name",
                "category": "development",
                "has_execution": True,
                "allowed_first_tools": ["Bash"],
                "default_tools": ["Bash"],
            }
        }
    """
    skills_path = Path(skills_dir)
    if not skills_path.exists():
        return {}

    discovered = {}

    for skill_dir in skills_path.iterdir():
        if not skill_dir.is_dir():
            continue

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        # Parse frontmatter
        config = _parse_skill_frontmatter(skill_md)
        if config:
            discovered[config["name"]] = config

    return discovered


def _parse_skill_frontmatter(skill_md: Path) -> dict | None:
    """
    Parse SKILL.md frontmatter to extract configuration.

    Args:
        skill_md: Path to SKILL.md file

    Returns:
        Configuration dict or None if parsing fails
    """
    try:
        content = skill_md.read_text(encoding="utf-8")

        # Extract YAML frontmatter between --- markers
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return None

        frontmatter = match.group(1)
        config = {"name": skill_md.parent.name}

        # Parse YAML-like key-value pairs
        for line in frontmatter.split("\n"):
            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            config[key] = value

        # Determine if skill has execution (enforced vs knowledge)
        category = config.get("category", "development")
        config["category"] = category

        # Knowledge skills have no enforcement
        if config["name"] in KNOWLEDGE_SKILLS or category in ("knowledge", "meta"):
            config["has_execution"] = False
            config["allowed_first_tools"] = []
            config["default_tools"] = []
        else:
            config["has_execution"] = True
            # Default to Bash for execution skills
            config["allowed_first_tools"] = ["Bash"]
            config["default_tools"] = ["Bash"]

        return config

    except Exception:
        return None


def get_skill_config(
    skill_name: str,
    explicit_registry: dict | None,
) -> dict:
    """
    Get skill configuration with auto-discovery fallback.

    Priority:
    1. Explicit registry (backwards compatibility)
    2. Frontmatter from SKILL.md
    3. Script pattern detection
    4. Category defaults

    Args:
        skill_name: Name of the skill (without slash)
        explicit_registry: Optional explicit SKILL_EXECUTION_REGISTRY

    Returns:
        Configuration dict:
        {
            "tools": ["Bash"],
            "pattern": "run_heavy.py",
            "hint": "Use /skill via its documented workflow",
            "intent_enabled": False,
            "discovered": True,
        }
    """
    # Priority 1: Explicit registry
    if explicit_registry and skill_name in explicit_registry:
        registry_entry = explicit_registry[skill_name]
        return {
            "tools": registry_entry.get("tools", ["Bash"]),
            "pattern": registry_entry.get("pattern", ""),
            "hint": f"Use /{skill_name} via its documented workflow",
            "intent_enabled": registry_entry.get("intent_enabled", False),
            "discovered": False,
        }

    # Priority 2-4: Auto-discovery
    discovered = discover_all_skills()

    if skill_name not in discovered:
        # Unknown skill - fail open (don't block)
        return {
            "tools": [],
            "pattern": "",
            "hint": f"Skill /{skill_name} not found in registry",
            "intent_enabled": False,
            "discovered": False,
        }

    skill_config = discovered[skill_name]

    # Build config from discovered data
    tools = skill_config.get("allowed_first_tools", [])

    # Detect script patterns
    pattern = _detect_script_pattern(skill_name)

    return {
        "tools": tools,
        "pattern": pattern,
        "hint": f"Use /{skill_name} via its documented workflow",
        "intent_enabled": False,
        "discovered": True,
    }


def discover_hooks(
    skills_dir: str | Path = "P:/.claude/skills",
) -> list[dict]:
    """
    Auto-discover hook declarations from SKILL.md frontmatter.

    Scans .claude/skills/*/SKILL.md files and extracts hooks: declarations.

    Args:
        skills_dir: Path to skills directory (default: P:/.claude/skills)

    Returns:
        List of hook configs:
        [
            {
                "skill": "rca",
                "event": "PostToolUse",
                "name": "rca_posttooluse_init",
                "matcher": "Skill",
                "type": "command",
                "command": "python -m rca.hook_launcher PostToolUse_rca_init.py",
                "timeout": 10,
            },
            ...
        ]
    """
    skills_path = Path(skills_dir)
    if not skills_path.exists():
        return []

    discovered = []

    for skill_dir in skills_path.iterdir():
        if not skill_dir.is_dir():
            continue

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        hooks = _parse_skill_hooks(skill_md, skill_dir.name)
        discovered.extend(hooks)

    return discovered


def _parse_skill_hooks(skill_md: Path, skill_name: str) -> list[dict]:
    """
    Parse SKILL.md frontmatter to extract hook declarations.

    Args:
        skill_md: Path to SKILL.md file
        skill_name: Name of the skill (from directory name)

    Returns:
        List of hook configs for this skill
    """
    try:
        content = skill_md.read_text(encoding="utf-8")

        # Extract YAML frontmatter between --- markers
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return []

        frontmatter = match.group(1)

        # Parse YAML manually (avoiding external yaml dependency)
        hooks_data = _parse_yaml_field(frontmatter, "hooks")
        if not hooks_data:
            return []

        result = []

        # hooks_data is a dict like {"PostToolUse": [...], "SessionEnd": [...]}
        for event, hook_list in hooks_data.items():
            if not isinstance(hook_list, list):
                continue

            for hook_entry in hook_list:
                if not isinstance(hook_entry, dict):
                    continue

                # Each entry has "matcher" and "hooks"
                matcher = hook_entry.get("matcher", ".*")
                hook_items = hook_entry.get("hooks", [])
                if not isinstance(hook_items, list):
                    hook_items = [hook_items]

                for hook_item in hook_items:
                    if not isinstance(hook_item, dict):
                        continue

                    hook_type = hook_item.get("type", "command")
                    command = hook_item.get("command", "")
                    timeout = hook_item.get("timeout", 10)

                    if not command:
                        continue

                    # Generate unique name: {skill}_{event}_{index}
                    idx = len([h for h in result if h["event"] == event])
                    name = f"{skill_name}_{event}_{idx}"

                    result.append({
                        "skill": skill_name,
                        "event": event,
                        "name": name,
                        "matcher": matcher,
                        "type": hook_type,
                        "command": command,
                        "timeout": timeout,
                    })

        return result

    except Exception:
        return []


def _parse_yaml_field(content: str, field: str) -> dict | None:
    """
    Parse a top-level YAML field from SKILL.md frontmatter.

    Handles nested structures like:
        hooks:
          PostToolUse:
            - matcher: "Skill"
              hooks:
                - type: command
                  command: python -m rca.hook_launcher

    Args:
        content: YAML frontmatter content
        field: Field name to extract

    Returns:
        Parsed dict or None if not found
    """
    # Find the field at the start of a line
    pattern = re.compile(rf"^{re.escape(field)}:\s*\n((?:[ \t]+.+\n?)+)", re.MULTILINE)
    match = pattern.search(content)
    if not match:
        return None

    field_content = match.group(1)

    # Parse nested YAML structure
    result = {}
    current_list = None
    current_dict = None
    current_indent = 0

    for line in field_content.split("\n"):
        if not line.strip():
            continue

        # Calculate indentation
        indent = len(line) - len(line.lstrip())

        # Check for list item
        list_match = re.match(r"^-\s+(.+)$", line.strip())
        dict_match = re.match(r"^(\w+):\s*(.*)$", line.strip())

        if list_match and indent <= current_indent:
            # Close previous dict and add to list
            if current_dict is not None and current_list is not None:
                current_list.append(current_dict)
            # Start new list item
            item_content = list_match.group(1)
            current_list = []
            current_dict = {"_list": current_list}

            # Check if this line itself has key-value
            kv_match = re.match(r"(\w+):\s*(.*)", item_content)
            if kv_match:
                key, val = kv_match.groups()
                if val.strip():
                    current_dict[kv_match.group(1)] = _unquote(val.strip())
                else:
                    # Key with no value = start of nested dict
                    pass

        elif dict_match and indent <= current_indent:
            # Close previous dict and add to list
            if current_dict is not None and current_list is not None:
                if "_list" in current_dict:
                    pass  # Already added
                else:
                    current_list.append(current_dict)
            # New key-value
            key, val = dict_match.groups()
            if val.strip():
                current_dict = {key: _unquote(val.strip())}
            else:
                current_dict = {key: None}
            current_indent = indent

        elif dict_match and current_dict is not None:
            # Nested key-value
            key, val = dict_match.groups()
            if current_list is not None and "_list" in current_dict:
                # We're in a list item context
                if "_nested" not in current_dict:
                    current_dict["_nested"] = {}
                if val.strip():
                    current_dict["_nested"][key] = _unquote(val.strip())

    # Close final dict
    if current_dict is not None and current_list is not None:
        if "_nested" in current_dict:
            # Merge nested back
            for k, v in current_dict["_nested"].items():
                current_dict[k] = v
            del current_dict["_nested"]
        current_list.append(current_dict)

    # Convert to proper structure
    if result.get("_current_list"):
        return result.get("_current_list", [])

    return result


def _unquote(s: str) -> str:
    """Strip quotes from YAML string values."""
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s


def _detect_script_pattern(skill_name: str) -> str:
    """
    Detect if skill has a run_heavy.py script for pattern matching.

    Args:
        skill_name: Name of the skill

    Returns:
        Pattern string (e.g., "run_heavy.py") or empty string
    """
    skill_path = Path("P:/.claude/skills") / skill_name

    # Check for run_heavy.py
    if (skill_path / "run_heavy.py").exists():
        return "run_heavy.py"

    # Check for other common scripts
    for script_name in ["run_light.py", "run.py"]:
        if (skill_path / script_name).exists():
            return script_name

    return ""


if __name__ == "__main__":
    # Test auto-discovery
    skills = discover_all_skills()
    print(f"Discovered {len(skills)} skills")

    for name, config in list(skills.items())[:5]:
        print(f"  {name}: {config.get('category', 'unknown')}")
