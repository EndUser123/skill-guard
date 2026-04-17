"""
Universal Skill Auto-Discovery and Enforcement
==============================================

Automatically discovers and enforces ALL skills without manual registration.

Uses skill frontmatter and filesystem discovery as the source of truth.
Any explicit overrides are treated as legacy compatibility, not the primary path.

Author: CSF NIP
Version: 1.0.0
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


_VALID_CONTRACT_TYPES = {"workflow", "output", "hybrid", "analysis"}


def _normalize_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _infer_contract_type(frontmatter: dict, category: str, skill_name: str) -> str:
    explicit = str(frontmatter.get("contract_type", "") or "").strip().lower()
    if explicit in _VALID_CONTRACT_TYPES:
        return explicit

    workflow_signals = bool(
        _normalize_list(frontmatter.get("workflow_steps", []))
        or _normalize_list(frontmatter.get("required_phase_artifacts", []))
        or str(frontmatter.get("workflow_binding", "") or "").strip().lower()
        in {"exclusive", "hard"}
        or str(frontmatter.get("workflow_enforcement", "") or "").strip().lower()
        in {"hard", "strict"}
    )
    output_signals = bool(
        frontmatter.get("layer1_enforcement")
        or _normalize_list(frontmatter.get("required_markers", []))
        or _normalize_list(frontmatter.get("required_sections", []))
        or str(frontmatter.get("final_output_schema", "") or "").strip()
        or str(frontmatter.get("output_enforcement", "") or "").strip().lower()
        in {"hard", "strict", "warn", "advisory"}
    )

    if workflow_signals and output_signals:
        return "hybrid"
    if workflow_signals:
        return "workflow"
    if output_signals:
        return "output"
    if category in {"knowledge", "meta"}:
        return "analysis"

    # Default to analysis for skills that have no explicit contract signals.
    # This prevents the old "every non-knowledge skill is Bash-first" assumption.
    logger.debug("Inferring analysis contract for /%s with no explicit signals", skill_name)
    return "analysis"


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

        if yaml is not None:
            parsed = yaml.safe_load(frontmatter) or {}
            if isinstance(parsed, dict):
                config.update(parsed)
        else:
            # Fallback parser for environments without PyYAML. It handles only
            # simple scalar frontmatter, which is enough for the legacy config
            # fields but not nested lists.
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
        contract_type = _infer_contract_type(config, category, skill_md.parent.name)
        config["contract_type"] = contract_type
        config["workflow_steps"] = _normalize_list(config.get("workflow_steps", []))
        config["required_phase_artifacts"] = _normalize_list(
            config.get("required_phase_artifacts", [])
        )
        config["required_markers"] = _normalize_list(config.get("required_markers", []))
        config["required_sections"] = _normalize_list(config.get("required_sections", []))
        config["usage_markers"] = _normalize_list(config.get("usage_markers", []))

        # Knowledge skills have no enforcement
        if config["name"] in KNOWLEDGE_SKILLS or category in ("knowledge", "meta"):
            config["has_execution"] = False
            config["allowed_first_tools"] = []
            config["default_tools"] = []
        else:
            config["has_execution"] = True
            workflow_like = contract_type in {"workflow", "hybrid"} or bool(
                config["workflow_steps"]
                or config["required_phase_artifacts"]
                or str(config.get("workflow_binding", "") or "").strip().lower()
                in {"exclusive", "hard"}
                or str(config.get("workflow_enforcement", "") or "").strip().lower()
                in {"hard", "strict"}
            )
            explicit_tools = _normalize_list(config.get("allowed_first_tools", []))
            if workflow_like:
                # Workflow-bound skills should stay executable from Bash-first
                # unless they explicitly declare a different first tool set.
                config["allowed_first_tools"] = explicit_tools or ["Bash"]
                config["default_tools"] = config["allowed_first_tools"]
            else:
                # Output/analysis skills are not Bash-first by default.
                config["allowed_first_tools"] = explicit_tools
                config["default_tools"] = explicit_tools

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
    1. Frontmatter from SKILL.md
    2. Script pattern detection
    3. Category defaults

    Args:
        skill_name: Name of the skill (without slash)
        explicit_registry: Optional legacy override mapping

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
    # Legacy override for callers that still provide it
    if explicit_registry and skill_name in explicit_registry:
        registry_entry = explicit_registry[skill_name]
        return {
            "tools": registry_entry.get("tools", ["Bash"]),
            "pattern": registry_entry.get("pattern", ""),
            "hint": f"Use /{skill_name} via its documented workflow",
            "intent_enabled": registry_entry.get("intent_enabled", False),
            "discovered": False,
        }

    # Auto-discovery from the filesystem and skill frontmatter
    discovered = discover_all_skills()

    if skill_name not in discovered:
        # Unknown skill - fail open (don't block)
        return {
            "tools": [],
            "pattern": "",
            "hint": f"Skill /{skill_name} not found in skill files",
            "intent_enabled": False,
            "discovered": False,
        }

    skill_config = discovered[skill_name]

    # Build config from discovered data
    tools = skill_config.get("allowed_first_tools", [])
    contract_type = skill_config.get("contract_type", "analysis")

    if not tools and contract_type in {"workflow", "hybrid"}:
        tools = ["Bash"]

    # Detect script patterns
    pattern = _detect_script_pattern(skill_name)

    return {
        "tools": tools,
        "pattern": pattern,
        "hint": f"Use /{skill_name} via its documented contract",
        "intent_enabled": False,
        "discovered": True,
        "contract_type": contract_type,
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
        import yaml

        content = skill_md.read_text(encoding="utf-8")

        # Extract YAML frontmatter between --- markers
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return []

        frontmatter = match.group(1)
        data = yaml.safe_load(frontmatter)
        if not isinstance(data, dict):
            return []

        hooks_data = data.get("hooks")
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

    except Exception as e:
        logger.warning(f"Failed to parse hooks from {skill_name} SKILL.md: {e}")
        return []


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
