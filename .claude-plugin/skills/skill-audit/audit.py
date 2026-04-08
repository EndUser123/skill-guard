"""
audit.py — /skill-audit router and lens executor.

Single-pass skill architecture auditor.
Reads target SKILL.md, inventories files, runs 13 lenses, outputs outcome summary + gap table + improvement plan.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple


class Finding(NamedTuple):
    lens: str
    gap: str
    evidence: str
    priority: str  # HIGH | MEDIUM | LOW
    owner: str = "source skill"


@dataclass(frozen=True)
class ParsedSkill:
    skill_path: Path
    raw_text: str
    frontmatter: dict[str, str]
    body: str
    footer_version: str | None
    sections: dict[str, str]


@dataclass(frozen=True)
class TransferTarget:
    skill_name: str
    relation: str
    score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class TransferJudgmentPacket:
    source_name: str
    principle_families: tuple[str, ...]
    direct_targets: tuple[TransferTarget, ...]
    reference_targets: tuple[TransferTarget, ...]
    indirect_candidates: tuple[TransferTarget, ...]


SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
SEMANTIC_SEARCH_RESEARCH_DIR = WORKSPACE_ROOT / "packages" / "search-research"

_PRIORITY_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
_STRATEGIC_LENSES = {
    "COMMAND_DISCIPLINE",
    "STRUCTURAL_JUSTIFICATION",
    "SKILL_CONTRACT_CONSISTENCY",
    "CONTRACT_COMPLETENESS",
    "QUESTION_STRATEGY",
    "OPERATIONAL_RESILIENCE",
    "NON_GOALS_CLARITY",
}
_LENS_ACTION_TEMPLATES = {
    "REFERENCE_INTEGRITY": "remove or repair broken promised references before trusting the skill docs",
    "PROCESS_ENFORCEMENT": "align claimed workflow steps with the real execution model, or stop implying automation that does not exist",
    "COMMAND_DISCIPLINE": "tighten input gates, branch coverage, and scope discipline so the skill stops relying on implicit operator judgment",
    "STRUCTURAL_JUSTIFICATION": "justify added structure with a concrete failure, a simpler-alternative check, and an explicit complexity tradeoff",
    "TEMPLATE_SYSTEM": "standardize the template/rendering mechanism so the skill stops depending on ad hoc composition",
    "MODEL_VARIANCE": "replace vague directives with explicit thresholds or decision criteria",
    "CONTRACT_COMPLETENESS": "name and enforce the governing contract primitive instead of leaving the boundary implicit",
    "SKILL_CONTRACT_CONSISTENCY": "repair contradictions between frontmatter, body, and footer so the contract has one truth source",
    "MECHANISM_LEAKAGE": "remove brittle implementation details from policy text unless they are truly normative",
    "QUESTION_STRATEGY": "tighten the skill's internal reasoning prompts so it asks the right questions for its role",
    "OPERATIONAL_RESILIENCE": "make runtime behavior explicit for stale data, multi-terminal, follow-up context, or nested-workflow recovery",
    "ASSURANCE_STRATEGY": "add the cheapest real smoke proof or critique policy that would catch this class of failure early",
    "NON_GOALS_CLARITY": "define what the skill will not do so users stop inferring unsupported behavior",
}
_PRINCIPLE_FAMILY_PATTERNS = {
    "structural_justification": [
        r"\bboundar(?:y|ies)\b",
        r"\babstraction\b",
        r"\bextract(?:ion)?\b",
        r"\bsplit\b",
        r"\bcomplexity\b",
        r"\bsimpler alternative\b",
        r"\bover-engineering\b",
        r"\breversib",
        r"\bscope check\b",
    ],
    "assurance_evidence": [
        r"\bevidence\b",
        r"\btier\b",
        r"\bproof\b",
        r"\bverify\b",
        r"\bvalidation\b",
        r"\bsmoke test\b",
    ],
    "workflow_orchestration": [
        r"\bworkflow\b",
        r"\broute\b",
        r"\bdelegate\b",
        r"\bhandoff\b",
        r"\bphase\b",
        r"\bresume\b",
    ],
    "contract_enforcement": [
        r"\bcontract\b",
        r"\bvalidator\b",
        r"\bhook\b",
        r"\bgate\b",
        r"\benforcement\b",
        r"\bpolicy\b",
    ],
    "learning_improvement": [
        r"\blesson\b",
        r"\bretro\b",
        r"\breflect\b",
        r"\blearn\b",
        r"\bimprov",
    ],
}
_TRANSFER_CATEGORY_AFFINITY = {
    "structural_justification": {"architecture", "planning", "analysis", "strategy", "development"},
    "assurance_evidence": {"analysis", "development", "execution", "planning", "testing"},
    "workflow_orchestration": {"orchestration", "planning", "architecture", "analysis"},
    "contract_enforcement": {"architecture", "planning", "analysis", "development", "execution"},
    "learning_improvement": {"learning", "analysis", "session"},
}
_TRANSFER_STOPWORDS = {
    "skill", "skills", "workflow", "workflows", "analysis", "advisor", "advice",
    "system", "systems", "design", "quality", "right", "wrong", "using", "use",
    "used", "when", "with", "from", "that", "this", "there", "into", "does",
    "have", "value", "other", "should", "could", "would", "their", "about",
    "through", "across", "before", "after", "more", "than", "very", "real",
    "high", "medium", "low", "good", "best", "user", "users", "guide",
}


def audit(target: str) -> list[Finding]:
    """Run all 13 lenses against target skill. Returns list of findings."""
    skill_path = _resolve_skill(target)
    if not skill_path:
        return [Finding("SETUP", "Skill not found", f"'{target}' does not exist in {SKILLS_DIR}", "HIGH", "skill-audit")]

    skill_md = _read_skill_md(skill_path)
    if not skill_md:
        return [Finding("SETUP", "SKILL.md missing", f"No SKILL.md in {skill_path}", "HIGH", "source skill")]

    parsed = _parse_skill(skill_path, skill_md)
    py_files = list(skill_path.glob("**/*.py"))

    findings: list[Finding] = []
    findings.extend(_lens_reference_integrity(parsed))
    findings.extend(_lens_process_enforcement(parsed, py_files))
    findings.extend(_lens_command_discipline(parsed))
    findings.extend(_lens_structural_justification(parsed))
    findings.extend(_lens_template_system(py_files))
    findings.extend(_lens_model_variance(parsed.body))
    findings.extend(_lens_contract_completeness(parsed, py_files))
    findings.extend(_lens_skill_contract_consistency(parsed))
    findings.extend(_lens_mechanism_leakage(parsed))
    findings.extend(_lens_question_strategy(parsed))
    findings.extend(_lens_operational_resilience(parsed))
    findings.extend(_lens_assurance_strategy(parsed))
    findings.extend(_lens_non_goals_clarity(parsed.body))

    return findings


def _priority_score(finding: Finding) -> int:
    return _PRIORITY_RANK.get(finding.priority, 0)


def _derive_verdict(findings: list[Finding]) -> tuple[str, str]:
    """Return a short verdict and reason oriented around outcomes."""
    if not findings:
        return ("HEALTHY", "Lenses executed cleanly against available evidence. Maintenance only.")

    strategic_high = [f for f in findings if f.lens in _STRATEGIC_LENSES and _priority_score(f) >= 3]
    any_high = [f for f in findings if _priority_score(f) >= 3]

    if strategic_high:
        return (
            "RIGHT IDEA, WRONG CONTRACT",
            "The skill likely serves a real need, but its strategy/contract layer is drifting enough that users cannot rely on it consistently.",
        )
    if any_high:
        return (
            "KEEP THE SKILL, HARDEN EXECUTION",
            "The skill shape is probably fine, but concrete broken promises or missing verification make the outcome unreliable.",
        )
    return (
        "TARGETED CLEANUP",
        "The skill is broadly sound. A few medium-priority corrections should be enough to make it trustworthy.",
    )


def _derive_outcomes(findings: list[Finding]) -> list[tuple[str, str, str]]:
    """Collapse findings into a concrete set of outcome moves.

    Returns tuples of (action, owner, priority), deduplicated by action and ordered by priority.
    """
    best_by_lens: dict[str, Finding] = {}
    for finding in findings:
        existing = best_by_lens.get(finding.lens)
        if existing is None or _priority_score(finding) > _priority_score(existing):
            best_by_lens[finding.lens] = finding

    ordered = sorted(
        best_by_lens.values(),
        key=lambda f: (_priority_score(f), f.lens),
        reverse=True,
    )

    outcomes: list[tuple[str, str, str]] = []
    seen_actions: set[str] = set()
    for finding in ordered:
        action = _LENS_ACTION_TEMPLATES.get(finding.lens, finding.gap)
        if action in seen_actions:
            continue
        seen_actions.add(action)
        outcomes.append((action, finding.owner, finding.priority))
    return outcomes


def _derive_handoff_offer(findings: list[Finding]) -> tuple[str, str, list[tuple[str, str]]] | None:
    """Return an explicit next-skill handoff when the next owner is not the source skill."""
    outcomes = _derive_outcomes(findings)
    owned_outcomes = [outcome for outcome in outcomes if outcome[1] != "source skill"]
    if not owned_outcomes:
        return None

    owner_scores: dict[str, tuple[int, int]] = {}
    for action, owner, priority in owned_outcomes:
        priority_score = _PRIORITY_RANK.get(priority, 0)
        current = owner_scores.get(owner, (0, 0))
        owner_scores[owner] = (
            max(current[0], priority_score),
            current[1] + 1,
        )

    owner = sorted(
        owner_scores.items(),
        key=lambda item: (item[1][0], item[1][1], item[0]),
        reverse=True,
    )[0][0]
    owner_actions = [(priority, action) for action, action_owner, priority in owned_outcomes if action_owner == owner]

    if owner == "skill-ship":
        rationale = "The blocking work is implementation or correctness hardening, so `/skill-ship` should own the next pass."
    elif owner == "skill-audit":
        rationale = "The blocking work is still strategic or audit-owned, so `/skill-audit` should keep control for the next pass."
    else:
        rationale = f"The blocking work is owned by `{owner}`, so hand off there instead of leaving ownership implicit."
    return owner, rationale, owner_actions


def _resolve_skill(target: str) -> Path | None:
    """Resolve a skill name to its directory path."""
    name = target.lstrip("/")
    skill_path = SKILLS_DIR / name
    if skill_path.exists():
        return skill_path
    for child in SKILLS_DIR.iterdir():
        if child.name.lower() == name.lower():
            return child
    return None


def _read_skill_md(skill_path: Path) -> str | None:
    """Read SKILL.md from skill directory."""
    f = skill_path / "SKILL.md"
    return f.read_text() if f.exists() else None


def _parse_frontmatter(skill_md: str) -> dict[str, str]:
    """Extract simple YAML frontmatter key/value pairs."""
    match = re.match(r"^---\n(.*?)\n---\n", skill_md, re.DOTALL)
    if not match:
        return {}

    frontmatter: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = value.strip().strip('"').strip("'")
    return frontmatter


def _body_without_frontmatter(skill_md: str) -> str:
    """Return the body portion after YAML frontmatter."""
    match = re.match(r"^---\n.*?\n---\n(.*)$", skill_md, re.DOTALL)
    return match.group(1) if match else skill_md


def _parse_sections(body: str) -> dict[str, str]:
    """Extract markdown sections keyed by heading text."""
    matches = list(re.finditer(r"^##\s+(.+)$", body, re.MULTILINE))
    sections: dict[str, str] = {}
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        sections[match.group(1).strip()] = body[start:end].strip()
    return sections


def _parse_skill(skill_path: Path, skill_md: str) -> ParsedSkill:
    """Parse SKILL.md into frontmatter/body/footer metadata."""
    frontmatter = _parse_frontmatter(skill_md)
    body = _body_without_frontmatter(skill_md)
    footer_version_match = re.search(r"\*\*Version:\*\*\s*([^\s|]+)", body)
    return ParsedSkill(
        skill_path=skill_path,
        raw_text=skill_md,
        frontmatter=frontmatter,
        body=body,
        footer_version=footer_version_match.group(1) if footer_version_match else None,
        sections=_parse_sections(body),
    )


def _operational_reference_text(parsed: ParsedSkill) -> str:
    """Return text suitable for dependency/reuse-link scanning.

    This strips example-only contexts like fenced code blocks and "Typical questions"
    lists so quoted sample prompts do not masquerade as real workflow dependencies.
    """
    text = parsed.body
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    lines = text.splitlines()
    kept: list[str] = []
    in_typical_questions = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"^\d+\.\s+\*\*.+\*\*$", stripped):
            in_typical_questions = False
        if stripped.lower() == "typical questions:":
            in_typical_questions = True
            continue
        if in_typical_questions:
            if stripped.startswith("- "):
                continue
            if not stripped:
                continue
            in_typical_questions = False
        kept.append(line)
    return "\n".join(kept).lower()


def _principle_families_for_text(text: str) -> set[str]:
    """Infer reusable principle families from prose without hardcoding source skills."""
    lowered = text.lower()
    families: set[str] = set()
    for family, patterns in _PRINCIPLE_FAMILY_PATTERNS.items():
        if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in patterns):
            families.add(family)
    return families


def _salient_terms(text: str) -> set[str]:
    """Extract coarse lexical concepts for transfer-mode semantic expansion."""
    tokens = re.findall(r"[a-z][a-z0-9\-]{3,}", text.lower())
    return {
        token
        for token in tokens
        if token not in _TRANSFER_STOPWORDS and not token.isdigit()
    }


def _semantic_transfer_reasons(source: ParsedSkill, candidate: ParsedSkill) -> list[str]:
    """Return coarse semantic-overlap reasons for indirect transfer candidates."""
    source_terms = _salient_terms(_operational_reference_text(source))
    candidate_terms = _salient_terms(_operational_reference_text(candidate))
    overlaps = sorted(source_terms & candidate_terms)
    if len(overlaps) >= 3:
        return ["salient concept overlap: " + ", ".join(overlaps[:5])]
    if len(overlaps) >= 2:
        return ["light concept overlap: " + ", ".join(overlaps[:4])]
    return []


def _transfer_embedding_text(parsed: ParsedSkill) -> str:
    """Build a stable semantic text representation for transfer-mode ranking."""
    parts = [
        parsed.frontmatter.get("name", parsed.skill_path.name),
        parsed.frontmatter.get("category", ""),
        parsed.frontmatter.get("description", ""),
        " ".join(sorted(_principle_families_for_text(parsed.raw_text))),
        _operational_reference_text(parsed),
    ]
    return "\n".join(part for part in parts if part).strip()[:8000]


def _load_embed_client():
    """Best-effort loader for the semantic embedding client.

    Prefers the shared search-research embed client because it already wraps the
    Windows-pipe daemon with a direct SentenceTransformer fallback.
    """
    if not SEMANTIC_SEARCH_RESEARCH_DIR.exists():
        return None
    package_dir = str(SEMANTIC_SEARCH_RESEARCH_DIR)
    if package_dir not in sys.path:
        sys.path.insert(0, package_dir)
    try:
        from core.chs.embeddings import get_embed_client  # type: ignore
    except Exception:
        return None
    try:
        return get_embed_client()
    except Exception:
        return None


def _semantic_transfer_bonus_map(
    source: ParsedSkill,
    candidates: list[ParsedSkill],
) -> dict[str, tuple[int, str]]:
    """Return embedding-backed score bonuses for indirect transfer candidates.

    The daemon is optional. When unavailable or unhealthy, callers fall back to the
    existing coarse lexical/principle-family logic without failing the audit.
    """
    if not candidates:
        return {}

    try:
        import numpy as np
    except Exception:
        return {}

    client = _load_embed_client()
    if client is None:
        return {}

    try:
        texts = [_transfer_embedding_text(source)] + [
            _transfer_embedding_text(candidate) for candidate in candidates
        ]
        raw_embeddings = client.embed_texts(texts)
        if len(raw_embeddings) != len(texts):
            return {}

        source_vec = np.frombuffer(raw_embeddings[0], dtype=np.float32)
        if source_vec.size == 0:
            return {}

        similarity_rows: list[tuple[ParsedSkill, float]] = []
        source_norm = float(np.linalg.norm(source_vec))
        if source_norm <= 0 or not np.isfinite(source_norm):
            return {}

        for candidate, raw_embedding in zip(candidates, raw_embeddings[1:]):
            candidate_vec = np.frombuffer(raw_embedding, dtype=np.float32)
            if candidate_vec.size != source_vec.size:
                continue
            candidate_norm = float(np.linalg.norm(candidate_vec))
            if candidate_norm <= 0 or not np.isfinite(candidate_norm):
                continue
            similarity = float(np.dot(source_vec, candidate_vec) / (source_norm * candidate_norm))
            if not np.isfinite(similarity):
                continue
            similarity_rows.append((candidate, similarity))

        similarity_rows.sort(key=lambda row: row[1], reverse=True)
        bonuses: dict[str, tuple[int, str]] = {}
        for rank, (candidate, similarity) in enumerate(similarity_rows):
            bonus = 0
            if similarity >= 0.72:
                bonus = 3
            elif similarity >= 0.62:
                bonus = 2
            elif similarity >= 0.52 and rank < 6:
                bonus = 1
            if bonus:
                candidate_name = candidate.frontmatter.get("name", candidate.skill_path.name).lower()
                bonuses[candidate_name] = (
                    bonus,
                    f"semantic daemon similarity={similarity:.2f}",
                )
        return bonuses
    except Exception:
        return {}


def discover_transfer_targets(target: str) -> tuple[ParsedSkill, set[str], list[TransferTarget]]:
    """Discover direct and indirect reuse targets for a skill.

    Direct references rank highest. Indirect targets are inferred from overlapping
    principle families and category affinity so the result can adapt to skills that
    should benefit even without explicit references.
    """
    skill_path = _resolve_skill(target)
    if not skill_path:
        raise ValueError(f"Skill not found: {target}")

    skill_md = _read_skill_md(skill_path)
    if not skill_md:
        raise ValueError(f"SKILL.md missing for: {target}")

    source = _parse_skill(skill_path, skill_md)
    source_name = source.frontmatter.get("name", source.skill_path.name).lower()
    source_families = _principle_families_for_text(source.raw_text)

    targets: list[TransferTarget] = []
    candidate_map: dict[str, ParsedSkill] = {}
    for candidate_dir in SKILLS_DIR.iterdir():
        if not candidate_dir.is_dir() or candidate_dir == skill_path:
            continue
        candidate_md = _read_skill_md(candidate_dir)
        if not candidate_md:
            continue

        candidate = _parse_skill(candidate_dir, candidate_md)
        candidate_name = candidate.frontmatter.get("name", candidate.skill_path.name).lower()
        candidate_text = candidate.raw_text.lower()
        operational_text = _operational_reference_text(candidate)
        candidate_category = candidate.frontmatter.get("category", "").lower()
        candidate_families = _principle_families_for_text(candidate.raw_text)

        score = 0
        reasons: list[str] = []
        relation = "indirect_candidate"

        consumer_patterns = [
            rf"\broute to `?/{re.escape(source_name)}`?",
            rf"\bdelegate to `?/{re.escape(source_name)}`?",
            rf"\binvoke `?/{re.escape(source_name)}`?",
            rf"\bcall `?/{re.escape(source_name)}`?",
        ]
        reference_patterns = [
            rf"`?/{re.escape(source_name)}`?",
            rf"\bsuggest:\s.*{re.escape(source_name)}",
        ]
        if any(re.search(pattern, operational_text, re.IGNORECASE) for pattern in consumer_patterns):
            score += 12
            relation = "direct_consumer"
            reasons.append(f"explicitly delegates or routes to /{source_name}")
        elif any(re.search(pattern, operational_text, re.IGNORECASE) for pattern in reference_patterns):
            score += 6
            relation = "direct_reference"
            reasons.append(f"explicitly mentions /{source_name}")

        shared_families = sorted(source_families & candidate_families)
        if shared_families:
            score += len(shared_families)
            reasons.append("shared principle families: " + ", ".join(shared_families))

        semantic_reasons = _semantic_transfer_reasons(source, candidate)
        if semantic_reasons:
            score += 1
            reasons.extend(semantic_reasons)

        affinity_reasons: list[str] = []
        for family in source_families:
            if candidate_category in _TRANSFER_CATEGORY_AFFINITY.get(family, set()):
                affinity_reasons.append(family)
        if affinity_reasons:
            score += 1
            reasons.append(
                f"{candidate_category or 'uncategorized'} role fits "
                + ", ".join(sorted(dict.fromkeys(affinity_reasons)))
            )

        is_core_sdlc = candidate_name in {"arch", "planning", "skill-audit", "skill-ship"}
        if is_core_sdlc and source_families:
            score += 1
            reasons.append("core SDLC skill likely to absorb reusable principles")

        if relation.startswith("direct_") or score >= 5 or (is_core_sdlc and shared_families and score >= 4):
            candidate_map[candidate_name] = candidate
            targets.append(TransferTarget(
                skill_name=candidate_name,
                relation=relation,
                score=score,
                reasons=tuple(dict.fromkeys(reasons)),
            ))

    indirect_candidates = [
        candidate_map[target_item.skill_name]
        for target_item in targets
        if target_item.relation == "indirect_candidate" and target_item.skill_name in candidate_map
    ]
    semantic_bonuses = _semantic_transfer_bonus_map(source, indirect_candidates)
    if semantic_bonuses:
        enriched_targets: list[TransferTarget] = []
        for target_item in targets:
            if target_item.relation != "indirect_candidate":
                enriched_targets.append(target_item)
                continue
            bonus = semantic_bonuses.get(target_item.skill_name)
            if bonus is None:
                enriched_targets.append(target_item)
                continue
            bonus_score, bonus_reason = bonus
            enriched_targets.append(TransferTarget(
                skill_name=target_item.skill_name,
                relation=target_item.relation,
                score=target_item.score + bonus_score,
                reasons=tuple(dict.fromkeys(target_item.reasons + (bonus_reason,))),
            ))
        targets = enriched_targets

    relation_rank = {"direct_consumer": 3, "direct_reference": 2, "indirect_candidate": 1}
    targets.sort(key=lambda item: (relation_rank.get(item.relation, 0), item.score, item.skill_name), reverse=True)
    return source, source_families, targets


def build_transfer_judgment_packet(target: str, max_indirect: int = 12) -> TransferJudgmentPacket:
    """Build a bounded packet for LLM judgment after deterministic discovery.

    This keeps all explicit direct relationships, but narrows indirect candidates
    to a manageable queue for semantic judgment instead of pretending scores alone
    are the final answer.
    """
    source, source_families, targets = discover_transfer_targets(target)
    direct_targets = tuple(item for item in targets if item.relation == "direct_consumer")
    reference_targets = tuple(item for item in targets if item.relation == "direct_reference")
    indirect_candidates = tuple(
        item for item in targets if item.relation == "indirect_candidate"
    )[:max_indirect]
    return TransferJudgmentPacket(
        source_name=source.frontmatter.get("name", source.skill_path.name),
        principle_families=tuple(sorted(source_families)),
        direct_targets=direct_targets,
        reference_targets=reference_targets,
        indirect_candidates=indirect_candidates,
    )


def _resolve_reference(skill_path: Path, ref: str) -> bool:
    """Resolve a referenced path relative to the skill root and known content dirs."""
    if not ref or "{" in ref or "}" in ref:
        return True

    cleaned = ref.strip().strip("`").rstrip("/").replace("\\", "/")
    if not cleaned or cleaned.endswith(":"):
        return True

    ref_path = Path(cleaned.lstrip("./"))
    candidates = [
        skill_path / ref_path,
        skill_path / "references" / ref_path.name,
        skill_path / "resources" / ref_path.name,
        skill_path / "templates" / ref_path.name,
    ]
    return any(candidate.exists() for candidate in candidates)


def _lens_reference_integrity(parsed: ParsedSkill) -> list[Finding]:
    """Check if promised references actually exist."""
    findings: list[Finding] = []
    promised_refs: set[str] = set()
    for ref in re.findall(r"`([^`\n]*\.(?:md|json|yaml))`", parsed.raw_text):
        normalized = ref.strip()
        if normalized.startswith("~/"):
            continue
        if normalized.endswith(".md"):
            promised_refs.add(normalized)
            continue
        if "/" in normalized or "\\" in normalized:
            promised_refs.add(normalized)
    promised_refs.update(re.findall(r"((?:\.?/)?(?:references|resources|templates)/[^\s`]+)", parsed.raw_text))

    for ref in promised_refs:
        if not _resolve_reference(parsed.skill_path, ref):
            findings.append(Finding(
                "REFERENCE_INTEGRITY",
                f"missing reference: {ref}",
                f"SKILL.md mentions '{ref}' but it was not found relative to {parsed.skill_path}",
                "HIGH",
                "source skill",
            ))
    return findings


def _lens_process_enforcement(parsed: ParsedSkill, py_files: list[Path]) -> list[Finding]:
    """Check if prose workflow promises have Python backing."""
    findings: list[Finding] = []
    phase_claims = re.findall(r"(?:Phase|phase|Step|step)\s+\d+(?:\.\d+)?\s+(?:invokes|calls|runs)\s+([/\w\-]+)", parsed.raw_text)

    for claim in phase_claims:
        tool = claim.lstrip("/")
        found = any(
            tool.lower() in pf.name.lower() or tool.lower() in pf.read_text().lower()
            for pf in py_files
        )
        if not found:
            findings.append(Finding(
                "PROCESS_ENFORCEMENT",
                f"unbacked promise: '{claim}'",
                "SKILL.md claims this is invoked but no Python file references it",
                "MEDIUM",
                "source skill",
            ))
    return findings


def _lens_command_discipline(parsed: ParsedSkill) -> list[Finding]:
    """Check ACEF-style command discipline: input gates, path coverage, and scope."""
    findings: list[Finding] = []
    body_lower = parsed.body.lower()
    role_text = " ".join([
        parsed.frontmatter.get("name", "").lower(),
        parsed.frontmatter.get("description", "").lower(),
        parsed.frontmatter.get("category", "").lower(),
        body_lower,
    ])

    quality_gate_markers = [
        "quality gate",
        "vague input",
        "clarifying question",
        "ask one clarifying question",
        "input validation",
        "when input is vague",
        "clarity gate",
    ]
    path_enumeration_markers = [
        "all logical paths",
        "enumerate all paths",
        "routing table",
        "decision table",
        "failure path",
        "failure paths",
        "execution paths",
        "branch matrix",
    ]
    standardized_error_markers = [
        "standardized error",
        "predictable error",
        "violation message",
        "error format",
        "block reason",
    ]

    broad_user_facing = any(
        token in role_text
        for token in ["workflow", "advisor", "router", "planning", "architecture", "review", "orchestrat", "analysis"]
    )
    branch_heavy = any(token in body_lower for token in ["route", "routing", "classify", "branch", "if ", "elif", "else"])

    if broad_user_facing and not any(marker in body_lower for marker in quality_gate_markers):
        findings.append(Finding(
            "COMMAND_DISCIPLINE",
            "skill lacks explicit vague-input quality gate",
            "ACEF-style command discipline expects a clear rule for handling underspecified requests before execution proceeds",
            "MEDIUM",
            "source skill",
        ))

    if branch_heavy and not any(marker in body_lower for marker in path_enumeration_markers):
        findings.append(Finding(
            "COMMAND_DISCIPLINE",
            "branch-heavy skill does not enumerate its logical paths clearly",
            "The skill routes or branches, but does not clearly enumerate the meaningful execution and failure paths",
            "MEDIUM",
            "source skill",
        ))

    responsibility_clusters = {
        "strategy": ["audit", "strategy", "should exist", "outcome model", "scope boundary"],
        "implementation": ["implement", "repair", "wire", "hook", "validator", "test"],
        "distribution": ["publish", "github", "distribution", "share", "package skill"],
    }
    active_clusters = {
        cluster
        for cluster, patterns in responsibility_clusters.items()
        if any(pattern in role_text for pattern in patterns)
    }
    if len(active_clusters) >= 3 and "single responsibility" not in body_lower:
        findings.append(Finding(
            "COMMAND_DISCIPLINE",
            "skill shows single-responsibility drift",
            "The skill appears to combine strategic judgment, implementation work, and distribution concerns without an explicit scope guard",
            "MEDIUM",
            "source skill",
        ))

    if broad_user_facing and not any(marker in body_lower for marker in standardized_error_markers):
        findings.append(Finding(
            "COMMAND_DISCIPLINE",
            "skill lacks standardized error/blocking guidance",
            "ACEF-style command discipline expects predictable blocking or error language so enforcement does not look like accidental failure",
            "LOW",
            "source skill",
        ))

    return findings


def _lens_structural_justification(parsed: ParsedSkill) -> list[Finding]:
    """Check whether added structure is justified by concrete failures and tradeoffs.

    This is intentionally principle-based rather than ADF-branded so it can adapt to
    new classes of structure (hooks, validators, controllers, agents, layers) without
    requiring exact framework wording.
    """
    findings: list[Finding] = []
    body_lower = parsed.body.lower()
    role_text = " ".join([
        parsed.frontmatter.get("name", "").lower(),
        parsed.frontmatter.get("description", "").lower(),
        parsed.frontmatter.get("category", "").lower(),
        body_lower,
    ])

    structure_addition_markers = [
        "new boundary",
        "new abstraction",
        "abstraction layer",
        "new hook",
        "new validator",
        "new controller",
        "new agent",
        "new subagent",
        "split into",
        "extract into",
        "delegate to",
        "router",
        "gate",
        "phase",
        "workflow layer",
    ]
    activates = any(marker in role_text for marker in structure_addition_markers) or any(
        token in role_text for token in ["over-engineering", "complexity tax", "boundary stability", "simpler alternative"]
    )
    if not activates:
        return findings

    concrete_failure_markers = [
        "concrete failure",
        "failure this prevents",
        "problem check",
        "what failure",
        "evidence-based",
        "demonstrate failures",
        "real incident",
        "prevents",
    ]
    simpler_alternative_markers = [
        "simpler alternative",
        "existing code solve",
        "share existing",
        "reuse existing",
        "simplify",
        "least complex",
    ]
    complexity_tradeoff_markers = [
        "complexity tax",
        "overhead",
        "blast radius",
        "tradeoff",
        "cost of",
        "complexity score",
    ]
    durability_markers = [
        "boundary stability",
        "6-12 months",
        "long-term",
        "durable",
        "reversibility",
        "survive",
    ]

    has_concrete_failure = any(marker in body_lower for marker in concrete_failure_markers)
    has_simpler_alt = any(marker in body_lower for marker in simpler_alternative_markers)
    has_complexity_tradeoff = any(marker in body_lower for marker in complexity_tradeoff_markers)
    has_durability_check = any(marker in body_lower for marker in durability_markers)

    if not has_concrete_failure:
        findings.append(Finding(
            "STRUCTURAL_JUSTIFICATION",
            "added structure is not tied to a concrete failure or prevention case",
            "The skill discusses new boundaries/layers/mechanisms but does not clearly ask what concrete failure or recurring cost the added structure prevents",
            "HIGH",
            "source skill",
        ))

    if not has_simpler_alt:
        findings.append(Finding(
            "STRUCTURAL_JUSTIFICATION",
            "skill adds structure without a simpler-alternative check",
            "The skill can recommend new structure but does not explicitly ask whether reusing or simplifying existing mechanisms would solve the same problem",
            "MEDIUM",
            "source skill",
        ))

    if not has_complexity_tradeoff:
        findings.append(Finding(
            "STRUCTURAL_JUSTIFICATION",
            "skill adds structure without an explicit complexity tradeoff",
            "The skill discusses added machinery but does not ask what complexity overhead, blast radius, or maintenance cost it is introducing",
            "MEDIUM",
            "source skill",
        ))

    if not has_durability_check:
        findings.append(Finding(
            "STRUCTURAL_JUSTIFICATION",
            "skill adds structure without checking durability or reversibility",
            "The skill does not explicitly ask whether the proposed boundary or mechanism is likely to remain useful over time or be cheap to undo",
            "LOW",
            "source skill",
        ))

    return findings


def _lens_template_system(py_files: list[Path]) -> list[Finding]:
    """Check how templates are composed."""
    findings: list[Finding] = []
    has_jinja = False
    has_prose = False

    for pf in py_files:
        content = pf.read_text()
        if "jinja2" in content.lower() or "from jinja2" in content:
            has_jinja = True
        if 'f"' in content and ("template" in content.lower() or "output" in content.lower()):
            has_prose = True

    if has_prose and not has_jinja:
        findings.append(Finding(
            "TEMPLATE_SYSTEM",
            "prose template composition",
            "Templates built via f-string concatenation — consider Jinja2 for maintainability",
            "LOW",
            "skill-ship",
        ))
    return findings


def _lens_model_variance(skill_md_body: str) -> list[Finding]:
    """Check for model-dependent vagueness."""
    findings: list[Finding] = []
    vague_terms = ["briefly", "appropriately", "as needed", "as necessary", "optimize for", "consider doing"]
    for term in vague_terms:
        if term.lower() in skill_md_body.lower():
            findings.append(Finding(
                "MODEL_VARIANCE",
                f"vague directive: '{term}'",
                f"'{term}' has no concrete metric — different LLMs could interpret differently",
                "MEDIUM",
                "source skill",
            ))
    return findings


def _lens_contract_completeness(parsed: ParsedSkill, py_files: list[Path]) -> list[Finding]:
    """Check SDLC primitive usage across docs-first and code-backed skills."""
    findings: list[Finding] = []
    primitive_patterns = {
        "handoff_store": ["handoff_store", "handoff store"],
        "session_chain": ["session_chain", "session chain"],
        "evidence_store": ["evidence_store", "evidence store"],
        "contract_authority": ["contract authority packet", "contract_authority", "cap"],
        "planning_handoff_packet": ["planning handoff packet"],
    }

    sources = [parsed.raw_text.lower()]
    sources.extend(pf.read_text().lower() for pf in py_files)
    combined = "\n".join(sources)

    referenced_primitives = [
        primitive
        for primitive, patterns in primitive_patterns.items()
        if any(pattern in combined for pattern in patterns)
    ]
    if referenced_primitives:
        return findings

    raw_io_markers = [".write_text(", ".write_bytes(", "json.dump(", "open("]
    uses_raw_io = any(marker in combined for marker in raw_io_markers)
    contract_relevant_language = any(token in combined for token in ["contract", "handoff", "evidence", "session", "packet"])
    if uses_raw_io and contract_relevant_language:
        findings.append(Finding(
            "CONTRACT_COMPLETENESS",
            "raw file/state handling lacks named SDLC primitive",
            "Skill discusses contract/state concerns and uses raw file I/O but does not name the governing SDLC primitive",
            "MEDIUM",
            "source skill",
        ))
    return findings


def _lens_skill_contract_consistency(parsed: ParsedSkill) -> list[Finding]:
    """Check for contradictions between frontmatter, footer metadata, and body rules."""
    findings: list[Finding] = []

    enforcement = parsed.frontmatter.get("enforcement", "").lower()
    blocking_markers = [
        r"\bmay not\b",
        r"\bmust reject\b",
        r"\bmust repair\b",
        r"\bblocking behavior\b",
        r"\bblock(?:ed|ing)?\b",
        r"\breject(?:ed|ion)?\b",
    ]
    if enforcement == "advisory" and any(re.search(pattern, parsed.body, re.IGNORECASE) for pattern in blocking_markers):
        findings.append(Finding(
            "SKILL_CONTRACT_CONSISTENCY",
            "frontmatter enforcement understates blocking body behavior",
            "Frontmatter says enforcement=advisory but the body contains blocking/mandatory rules",
            "HIGH",
            "source skill",
        ))

    frontmatter_version = parsed.frontmatter.get("version")
    if frontmatter_version and parsed.footer_version and frontmatter_version != parsed.footer_version:
        findings.append(Finding(
            "SKILL_CONTRACT_CONSISTENCY",
            "frontmatter/footer version drift",
            f"Frontmatter version is {frontmatter_version} but footer version is {parsed.footer_version}",
            "MEDIUM",
            "skill-ship",
        ))

    return findings


def _lens_mechanism_leakage(parsed: ParsedSkill) -> list[Finding]:
    """Check if policy text hardcodes brittle runtime mechanics."""
    findings: list[Finding] = []
    leakage_markers = [
        ("hardcoded Agent invocation", r"Agent\("),
        ("fixed model selection", r'model\s*=\s*["\'][^"\']+["\']'),
        ("absolute path in policy text", r"[A-Z]:[\\/][^\s`\"']+"),
        ("fixed output path", r"Output:\s*[A-Z]:[\\/][^\s`\"']+"),
    ]

    hits = [label for label, pattern in leakage_markers if re.search(pattern, parsed.body)]
    if hits:
        findings.append(Finding(
            "MECHANISM_LEAKAGE",
            "skill contract hardcodes runtime mechanism details",
            "Policy text includes: " + ", ".join(hits),
            "MEDIUM",
            "source skill",
        ))

    return findings


def _extract_open_ended_questions(parsed: ParsedSkill) -> list[str]:
    """Extract open-ended questions from the dedicated section or full body."""
    source = parsed.sections.get("Open-Ended Questions", parsed.body)
    return [match.group(1).strip() for match in re.finditer(r"(?m)^[\-\*\d\.\s]*([^\n]*\?)\s*$", source)]


def _expected_question_prompt_contract(parsed: ParsedSkill) -> tuple[str, str, list[str], list[str]] | None:
    """Return expected role-specific internal prompt contract when warranted."""
    skill_name = (parsed.frontmatter.get("name", "") or parsed.skill_path.name).lower()
    description = parsed.frontmatter.get("description", "").lower()
    category = parsed.frontmatter.get("category", "").lower()
    body = parsed.body.lower()

    role_text = " ".join([skill_name, description, category, body])

    if skill_name == "tdd" or "test-driven" in role_text or "write failing test" in role_text:
        return (
            "Test-Truth Prompts",
            "TDD/testing skill lacks explicit test-truth self-check prompts",
            [
                r"\btest\b.*\bprov",
                r"\bpass while\b",
                r"\buser-visible behavior\b",
                r"\bnaive implementation\b",
                r"\bcontract\b",
                r"\bfail\b",
            ],
            [
                "what contract or behavior is this test actually proving?",
                "could this test pass while the real bug still exists?",
            ],
        )

    if skill_name == "rns" or "extract action items" in role_text or "turn this into actions" in role_text:
        return (
            "Action-Extraction Prompts",
            "Action-extraction skill lacks explicit action-extraction self-check prompts",
            [
                r"\bactionable\b",
                r"\bduplicate",
                r"\bownership\b",
                r"\bstale\b",
                r"\brevers",
                r"\bdependency\b",
            ],
            [
                "what item here is still a finding rather than an actionable next step?",
                "what action would become unsafe or misleading if the transcript or artifact is stale?",
            ],
        )

    if skill_name == "pre-mortem" or "adversarial critique" in role_text or "blinded consumer" in role_text:
        return (
            "Failure-Mode Prompts",
            "Adversarial/pre-mortem skill lacks explicit failure-mode self-check prompts",
            [
                r"\bhappy path\b",
                r"\bconsumer\b",
                r"\bhidden assumption\b",
                r"\blow-reversibility|\brevers",
                r"\bblind spot\b",
                r"\bnew one elsewhere\b|\belsewhere\b",
            ],
            [
                "what is the most plausible way this target still fails even if the happy path passes?",
                "what recommendation becomes dangerous if it is low-reversibility or applied out of order?",
            ],
        )

    if skill_name == "gto" or "what to do next" in role_text or "strategic next-step advisor" in role_text:
        return (
            "Next-Step Integrity Prompts",
            "Next-step advisory skill lacks explicit next-step integrity self-check prompts",
            [
                r"\bstale\b",
                r"\bduplicate",
                r"\bownership\b",
                r"\bmis-sequenc",
                r"\bhighest-value\b",
                r"\bcurrent evidence\b",
            ],
            [
                "what recommendation is being driven by stale artifacts rather than current evidence?",
                "what recommendation is being suggested because the skill is nearby, rather than because it truly owns the gap?",
            ],
        )

    if skill_name == "recap" or "session catch-up" in role_text or "terminal-wide session catch-up" in role_text:
        return (
            "Catch-Up Integrity Prompts",
            "Session catch-up skill lacks explicit catch-up integrity self-check prompts",
            [
                r"\btranscript\b",
                r"\bstale\b|\bincomplete\b|\bcontradicted\b",
                r"\bresume risk\b|\bcontract gap\b",
                r"\bturning point\b",
                r"\bglobally wrong\b|\bsession chain\b",
            ],
            [
                "what part of this recap is being inferred from condensed transcript fragments rather than strong evidence?",
                "what would make this recap locally coherent but globally wrong across the full session chain?",
            ],
        )

    if skill_name == "learn" or "lesson capture" in role_text or "novelty detection" in role_text:
        return (
            "Lesson-Quality Prompts",
            "Lesson-capture skill lacks explicit lesson-quality self-check prompts",
            [
                r"\breusable lesson\b|\bdurable\b",
                r"\bnovel\b|\bobvious\b|\bone-off\b",
                r"\bcausal claim\b",
                r"\bmerge\b",
                r"\bwrong habit\b",
            ],
            [
                "what candidate here is merely an event or routine operation rather than a reusable lesson?",
                "what would make this stored lesson teach the wrong habit next time?",
            ],
        )

    if skill_name == "retro" or "self-contrast" in role_text or "retrospective" in role_text:
        return (
            "Retrospective-Integrity Prompts",
            "Retrospective skill lacks explicit retrospective-integrity self-check prompts",
            [
                r"\bsuboptimal\b|\bprocess win\b",
                r"\bduplicat",
                r"\bscore\b",
                r"\bmis-sequenc",
                r"\bwrong lesson\b|\btradeoff\b|\bunresolved tension\b",
            ],
            [
                "what did we treat as a process win even though the outcome was suboptimal?",
                "what would make this retro feel complete while still teaching the wrong lesson?",
            ],
        )

    if skill_name == "reflect" or "self-improving skills" in role_text or "conversation transcripts" in role_text:
        return (
            "Reflection-Upgrade Prompts",
            "Reflection skill lacks explicit reflection-upgrade self-check prompts",
            [
                r"\bone-off\b|\bdurable\b",
                r"\bstale\b|\boverturned\b",
                r"\bvalidator\b|\bhook\b|\btest\b",
                r"\boverfit\b",
                r"\bownership\b|\bwrong habit\b",
            ],
            [
                "what correction or preference here is a one-off local preference rather than a durable skill improvement?",
                "what lesson should be pushed into a validator, hook, or test instead of staying as prose?",
            ],
        )

    if skill_name == "planning" or category == "planning":
        return None

    if skill_name == "arch" or category == "architecture":
        return None

    if skill_name == "code" or "feature development workflow" in role_text:
        return (
            "Implementation-Risk Prompts",
            "Implementation skill lacks explicit implementation-risk self-check prompts",
            [
                r"\bguess\b",
                r"\bcontract\b",
                r"\bassum",
                r"\bfail closed\b",
                r"\bregression\b",
                r"\bsystemically wrong\b",
            ],
            [
                "what requirement or contract am i about to guess instead of read?",
                "what regression would recur unless i add or update a test now?",
            ],
        )

    if skill_name == "rca" or category == "analysis" and any(token in role_text for token in ["root cause", "diagnosis", "hypothesis"]):
        return (
            "Competing-Cause Prompts",
            "RCA-heavy skill lacks explicit competing-cause self-check prompts",
            [
                r"\bfalsif",
                r"\bcompeting\b",
                r"\broot cause\b",
                r"\bsymptom\b",
                r"\brecur\b",
                r"\binvariant\b",
            ],
            [
                "what is the strongest competing root-cause explanation?",
                "what evidence would falsify the current hypothesis?",
            ],
        )

    return None


def _expected_internal_mode_contracts(parsed: ParsedSkill) -> list[tuple[str, str, list[str], list[str]]]:
    """Return expected internal reasoning-mode contracts by role.

    These are concept-level checks for shared SDLC helper modes (`trace`,
    `challenge`, `emerge`, `graduate`), not literal slash-command parity checks.
    """
    skill_name = (parsed.frontmatter.get("name", "") or parsed.skill_path.name).lower()
    category = parsed.frontmatter.get("category", "").lower()
    role_text = " ".join([
        skill_name,
        parsed.frontmatter.get("description", "").lower(),
        category,
        parsed.body.lower(),
    ])

    # Only apply these expectations to fuller skill contracts. Minimal unit-test stubs
    # that only contain an isolated prompt section should not be forced to include the
    # whole internal-mode contract as well.
    if "Purpose" not in parsed.sections:
        return []

    expectations: list[tuple[str, str, list[str], list[str]]] = []

    def add_modes(skill_label: str, modes: list[str]) -> None:
        markers: list[str] = [rf"\b{mode}\b" for mode in modes]
        examples: list[str] = [
            f"use `{mode}` as an internal helper mode when it materially improves the skill's judgment"
            for mode in modes
        ]
        expectations.append((
            "Internal Discovery Modes",
            f"{skill_label} lacks appropriate internal-mode support ({', '.join(modes)})",
            markers,
            examples,
        ))

    if skill_name == "skill-audit":
        add_modes("Audit skill", ["trace", "challenge", "emerge", "graduate"])
    elif skill_name == "skill-ship":
        add_modes("Ship skill", ["challenge", "graduate"])
    elif skill_name == "arch" or category == "architecture":
        add_modes("Architecture skill", ["trace", "challenge"])
    elif skill_name == "planning" or category == "planning":
        add_modes("Planning skill", ["trace", "challenge", "graduate"])
    elif skill_name == "rca" or (category == "analysis" and any(token in role_text for token in ["root cause", "diagnosis", "hypothesis"])):
        add_modes("RCA-heavy skill", ["trace", "challenge"])
    elif skill_name == "learn" or "lesson capture" in role_text or "novelty detection" in role_text:
        add_modes("Lesson-capture skill", ["emerge", "graduate"])
    elif skill_name == "retro" or "self-contrast" in role_text or "retrospective" in role_text:
        add_modes("Retrospective skill", ["trace", "emerge", "graduate"])
    elif skill_name == "reflect" or "self-improving skills" in role_text or "conversation transcripts" in role_text:
        add_modes("Reflection skill", ["emerge", "graduate", "trace"])

    return expectations


def _lens_question_strategy(parsed: ParsedSkill) -> list[Finding]:
    """Check whether open-ended questions align with the skill's role."""
    findings: list[Finding] = []
    skill_name = (
        parsed.frontmatter.get("name", "")
        or parsed.skill_path.name
    ).lower()
    questions = _extract_open_ended_questions(parsed)
    strategic_patterns = [
        r"\bshould this skill exist\b",
        r"\bwhat problem is this skill actually trying to solve\b",
        r"\bwhat would a better outcome look like\b",
        r"\bwhat would we build instead\b",
        r"\bshould this be split\b",
        r"\bshould this be merged\b",
        r"\bis the enforcement model\b",
    ]
    implementation_trivia_patterns = [
        r"\bhelper\b",
        r"\bhook file(?:name)?\b",
        r"\bfile split\b",
        r"\bfilename\b",
        r"\bfunction name\b",
        r"\bmodule name\b",
        r"\bpath\b",
    ]

    strategic_hits = [
        question for question in questions
        if any(re.search(pattern, question, re.IGNORECASE) for pattern in strategic_patterns)
    ]
    implementation_hits = [
        question for question in questions
        if any(re.search(pattern, question, re.IGNORECASE) for pattern in implementation_trivia_patterns)
    ]

    if "skill-ship" in skill_name and strategic_hits:
        findings.append(Finding(
            "QUESTION_STRATEGY",
            "skill-ship reopens strategic design questions",
            "Open-ended questions should narrow toward implementation, but found: "
            + "; ".join(strategic_hits[:3]),
            "MEDIUM",
            "source skill",
        ))

    if "skill-audit" in skill_name and implementation_hits:
        findings.append(Finding(
            "QUESTION_STRATEGY",
            "skill-audit collapses into implementation-trivia questions",
            "Open-ended questions should challenge strategy and outcomes, but found: "
            + "; ".join(implementation_hits[:3]),
            "MEDIUM",
            "source skill",
        ))

    prompt_contract = _expected_question_prompt_contract(parsed)
    if prompt_contract:
        section_name, gap, required_patterns, examples = prompt_contract
        section_body = parsed.sections.get(section_name, "")
        if not section_body:
            findings.append(Finding(
                "QUESTION_STRATEGY",
                gap,
                f"Expected an internal self-check section like '{section_name}' with prompts such as: "
                + "; ".join(examples),
                "MEDIUM",
                "source skill",
            ))
        else:
            normalized = section_body.lower()
            if not any(re.search(pattern, normalized, re.IGNORECASE) for pattern in required_patterns):
                findings.append(Finding(
                    "QUESTION_STRATEGY",
                    f"{section_name} exists but does not contain role-appropriate self-check prompts",
                    f"The section should contain prompts like: {'; '.join(examples)}",
                    "LOW",
                    "source skill",
                ))

    for section_name, gap, required_patterns, examples in _expected_internal_mode_contracts(parsed):
        section_body = parsed.sections.get(section_name, "")
        body_lower = parsed.body.lower()
        haystack = " ".join(filter(None, [section_body.lower(), body_lower]))
        if not section_body and "sdlc_internal_modes.md" not in body_lower:
            findings.append(Finding(
                "QUESTION_STRATEGY",
                gap,
                f"Expected internal-mode guidance such as: {'; '.join(examples)}",
                "LOW",
                "source skill",
            ))
            continue
        if not all(re.search(pattern, haystack, re.IGNORECASE) for pattern in required_patterns):
            findings.append(Finding(
                "QUESTION_STRATEGY",
                gap,
                f"Expected internal-mode guidance such as: {'; '.join(examples)}",
                "LOW",
                "source skill",
            ))

    return findings


def _lens_operational_resilience(parsed: ParsedSkill) -> list[Finding]:
    """Check multi-terminal safety, stale-data immunity, compact resilience, and cognitive-hook fit."""
    findings: list[Finding] = []
    body_lower = parsed.body.lower()
    raw_lower = parsed.raw_text.lower()
    category = parsed.frontmatter.get("category", "").lower()

    stateful_or_orchestrated = (
        category in {"orchestration", "analysis"}
        or any(token in body_lower for token in [
            "workflow",
            "phase",
            "state",
            "session",
            "terminal",
            "resume",
            "compact",
            "interrupt",
            "hook",
            "subagent",
        ])
    )
    hook_oriented = any(token in body_lower for token in ["hook", "pretooluse", "posttooluse", "stop hook", "usersubmit"])

    multi_terminal_markers = [
        "multi-terminal",
        "terminal-private",
        "terminal-scoped",
        "session-scoped",
        "stateless",
    ]
    stale_data_markers = [
        "stale data",
        "stale-data",
        "fresh read",
        "fresh reads",
        "ttl",
        "invalidation",
        "invalidate",
        "current-session",
    ]
    compact_markers = [
        "compact-resilient",
        "compaction resilience",
        "workflow interruption",
        "resume",
        "resuming",
        "interrupted workflow",
    ]
    cognitive_hook_markers = [
        "cognitive hook",
        "cognitive hooks",
        "reasoning hook",
        "reasoning hooks",
        "cognitive steering framework",
        "csf",
        "protocol.md",
        "architecture.md",
        "skill_authors_guide",
    ]
    nested_workflow_markers = [
        "invoke `/",
        "call skill(",
        "recommended_skill",
        "route to `/",
        "auto-invoke `/",
        "invoke /",
    ]
    resume_contract_markers = [
        "nested subworkflow",
        "return to caller",
        "resume automatically",
        "automatic return",
        "user re-entry is not required",
        "do not ask the user to rerun",
    ]
    context_inference_markers = [
        "context inference is mandatory",
        "follow-up grace",
        "follow-up query",
        "retrieve_context_hint",
        "infer subject",
        "prior context",
        "preceding turn",
        "recent substantive work",
    ]
    redundant_clarification_guard_markers = [
        "asking the user to restate",
        "workflow error",
        "do not ask one clarifying question",
        "do not ask a clarifying question",
        "inherit the most recent substantive subject",
        "rewrite the query to be self-contained",
        "retrieve prior turn content",
        "retrieval signal",
    ]

    if stateful_or_orchestrated:
        missing_resilience: list[str] = []
        if not any(marker in body_lower for marker in multi_terminal_markers):
            missing_resilience.append("multi-terminal isolation or explicit statelessness")
        if not any(marker in body_lower for marker in stale_data_markers):
            missing_resilience.append("stale-data immunity / freshness guidance")
        if not any(marker in body_lower for marker in compact_markers):
            missing_resilience.append("compaction resilience / interrupted-workflow recovery")

        if missing_resilience:
            findings.append(Finding(
                "OPERATIONAL_RESILIENCE",
                "skill lacks explicit operational resilience contract",
                "Missing guidance for: " + ", ".join(missing_resilience),
                "HIGH",
                "source skill",
            ))

    if hook_oriented and not any(marker in body_lower for marker in cognitive_hook_markers):
        findings.append(Finding(
            "OPERATIONAL_RESILIENCE",
            "hook-oriented skill lacks cognitive/reasoning hook fit guidance",
            "Skill discusses hooks or hook-heavy workflow but does not explain whether cognitive/reasoning hooks are required, reused, or intentionally out of scope",
            "MEDIUM",
            "source skill",
        ))

    is_orchestration_skill = category in {"orchestration", "planning", "architecture"} or any(
        token in body_lower for token in ["workflow", "routing behavior", "invoke `/", "call skill(", "route to `/"]
    )
    invokes_other_skills = any(marker in body_lower for marker in nested_workflow_markers)
    if is_orchestration_skill and invokes_other_skills and not any(marker in body_lower for marker in resume_contract_markers):
        findings.append(Finding(
            "OPERATIONAL_RESILIENCE",
            "orchestration skill lacks nested-workflow resume contract",
            "Skill invokes downstream skills but does not state whether control returns automatically to the caller or requires user re-entry",
            "MEDIUM",
            "source skill",
        ))

    claims_context_reuse = any(marker in body_lower for marker in context_inference_markers)
    has_followup_handling = any(token in raw_lower for token in ["follow-up", "follow up", "clarity gate", "context"])
    if (
        is_orchestration_skill
        and has_followup_handling
        and claims_context_reuse
        and not any(marker in body_lower for marker in redundant_clarification_guard_markers)
    ):
        findings.append(Finding(
            "OPERATIONAL_RESILIENCE",
            "context-reuse contract allows redundant clarification despite prior session context",
            "Skill promises follow-up/context inference but does not explicitly forbid asking the user to restate a subject that recent session context already establishes",
            "MEDIUM",
            "source skill",
        ))

    return findings


def _lens_assurance_strategy(parsed: ParsedSkill) -> list[Finding]:
    """Check critique-agent and smoke-test expectations for SDLC-heavy skills."""
    findings: list[Finding] = []
    skill_name = (parsed.frontmatter.get("name", "") or parsed.skill_path.name).lower()
    description = parsed.frontmatter.get("description", "").lower()
    category = parsed.frontmatter.get("category", "").lower()
    body = parsed.body.lower()
    role_text = " ".join([skill_name, description, category, body])

    def _require_section(section_name: str, gap: str, evidence: str, priority: str = "MEDIUM") -> None:
        if section_name not in parsed.sections:
            findings.append(Finding("ASSURANCE_STRATEGY", gap, evidence, priority, "source skill"))

    if skill_name == "code" or "feature development workflow" in role_text:
        _require_section(
            "Smoke Validation",
            "implementation workflow lacks explicit smoke validation contract",
            "Expected a 'Smoke Validation' section describing the cheapest real execution that falsifies risky implementation changes.",
        )
        _require_section(
            "Critique-Agent Triggers",
            "implementation workflow lacks explicit critique-agent trigger policy",
            "Expected a 'Critique-Agent Triggers' section for high-risk integration, contract, hook, or state changes.",
        )

    if skill_name == "tdd" or "test-driven" in role_text or "write failing tests" in role_text:
        _require_section(
            "Behavior Smoke Proof",
            "tdd workflow lacks explicit behavior smoke proof contract",
            "Expected a 'Behavior Smoke Proof' section describing minimal real executions that prove tests attach to real behavior.",
        )
        _require_section(
            "Critique-Agent Triggers",
            "tdd workflow lacks explicit critique-agent trigger policy",
            "Expected a 'Critique-Agent Triggers' section for high-risk test design, contract, state, or integration cases.",
        )

    if skill_name == "planning" or category == "planning":
        _require_section(
            "Critique-Agent Review Policy",
            "planning workflow lacks explicit critique-agent review policy",
            "Expected a 'Critique-Agent Review Policy' section covering stateful, contract-sensitive, layered, or overlapping-workflow plans.",
        )

    if skill_name == "arch" or category == "architecture":
        _require_section(
            "Critique-Agent Review Policy",
            "architecture workflow lacks explicit critique-agent review policy",
            "Expected a 'Critique-Agent Review Policy' section covering contract-sensitive, stateful, router, or packet-emitting designs.",
        )

    return findings


def _lens_non_goals_clarity(skill_md_body: str) -> list[Finding]:
    """Check for explicit Non-Goals section."""
    if "## Non-Goals" not in skill_md_body:
        return [Finding(
            "NON_GOALS_CLARITY",
            "Non-Goals section missing",
            "SKILL.md has no Non-Goals section — scope boundary is undefined",
            "LOW",
            "source skill",
        )]
    return []


def print_audit_table(findings: list[Finding]) -> None:
    """Print gap table."""
    print("\n## Skill Audit — Gap Table\n")
    print(f"| {'Lens':<28} | {'Gap':<40} | {'Owner':<16} | {'Priority':<8} |")
    print(f"|{'-'*28}|{'-'*40}|{'-'*16}|{'-'*8}|")
    for f in findings:
        print(f"| {f.lens:<26} | {f.gap:<40} | {f.owner:<16} | {f.priority:<8} |")


def print_outcome_summary(findings: list[Finding]) -> None:
    """Print a short decision-oriented summary before the detailed tables."""
    verdict, rationale = _derive_verdict(findings)
    outcomes = _derive_outcomes(findings)
    handoff = _derive_handoff_offer(findings)

    print("\n## Outcome Summary\n")
    print(f"- Verdict: **{verdict}**")
    print(f"- Why: {rationale}")
    if not outcomes:
        print("- Next move: No major action needed beyond routine maintenance.")
        return

    print("- Next moves (priority-ordered, deduplicated):")
    for action, owner, priority in outcomes:
        print(f"  - {priority}: {action} (owner: {owner})")

    if handoff:
        owner, handoff_rationale, owner_actions = handoff
        print("\n## Recommended Handoff\n")
        print(f"- Recommended next skill: `/{owner}`")
        print(f"- Why: {handoff_rationale}")
        print("- Offer this handoff with scope:")
        for priority, action in owner_actions:
            print(f"  - {priority}: {action}")


def print_improvement_plan(findings: list[Finding]) -> None:
    """Print 1-page improvement plan, sorted by priority."""
    high = [f for f in findings if f.priority == "HIGH"]
    med = [f for f in findings if f.priority == "MEDIUM"]

    print("\n## 1-Page Improvement Plan\n")
    for i, f in enumerate(high, 1):
        print(f"{i}. **{f.lens}** ({f.priority}, owner: {f.owner}): {f.gap}")
        print(f"   Evidence: {f.evidence}\n")
    for f in med:
        print(f"   - {f.lens} ({f.owner}): {f.gap}")
    if not high and not med:
        print("  No HIGH or MEDIUM gaps found.")


def print_transfer_analysis(target: str) -> None:
    """Print hybrid transfer/reuse target discovery for a source skill."""
    source, source_families, targets = discover_transfer_targets(target)
    packet = build_transfer_judgment_packet(target)
    print(f"# Transfer / Reuse Analysis: /{source.frontmatter.get('name', source.skill_path.name)}\n")
    print("## Principle Families\n")
    if source_families:
        print("- " + ", ".join(sorted(source_families)))
    else:
        print("- No strong reusable principle family detected from the source text.")

    print("\n## Reuse Targets\n")
    if not targets:
        print("- No clear transfer targets discovered.")
        return

    groups = {
        "direct_consumer": "### Direct Migration Targets",
        "direct_reference": "### Direct References",
        "indirect_candidate": "### Indirect Beneficiaries",
    }
    for relation in ("direct_consumer", "direct_reference", "indirect_candidate"):
        grouped = [item for item in targets if item.relation == relation]
        if not grouped:
            continue
        print(groups[relation] + "\n")
        for target_item in grouped:
            reason_text = "; ".join(target_item.reasons)
            print(
                f"- /{target_item.skill_name} "
                f"(score={target_item.score}): {reason_text}"
            )
        print()

    print("## Judgment Queue\n")
    print("Use deterministic discovery as the candidate set, then apply semantic/LLM judgment to the bounded indirect queue.")
    print("- When available, semantic daemon embeddings may already refine indirect candidate order. Treat that as a ranking aid, not an authority override.")
    print("- Explicit direct consumers must be either kept or rejected with an explicit reason.")
    print("- Example-only mentions must not be upgraded into real dependencies.")
    print("- Judge indirect candidates as one of: migrate, lighter subset, indirect beneficiary, or do not copy.")
    if packet.indirect_candidates:
        print("- Bounded indirect queue:")
        for item in packet.indirect_candidates:
            print(f"  - /{item.skill_name} (score={item.score})")
    else:
        print("- No indirect queue needed.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 2 and sys.argv[1] == "--transfer":
        print_transfer_analysis(sys.argv[2])
    else:
        target = sys.argv[1] if len(sys.argv) > 1 else "/rca"
        findings = audit(target)
        print(f"# Skill Audit: {target}\n")
        print_outcome_summary(findings)
        print_audit_table(findings)
        print_improvement_plan(findings)
