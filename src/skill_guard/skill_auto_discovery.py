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
