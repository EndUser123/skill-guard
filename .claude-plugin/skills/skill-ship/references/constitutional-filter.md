# Constitutional Filter for Skill Patterns

> Auto-filter prohibited enterprise patterns during skill creation
> Source: Extracted from `/refactor` skill (lines 712-761)

## Purpose

Prevent anti-patterns from entering the skill ecosystem. Skills should follow solo-dev constitutional constraints and avoid enterprise bloat.

## Prohibited Patterns

Auto-filter these patterns during skill creation:

| Pattern | Filter Because | Alternative |
|---------|---------------|-------------|
| **Service extraction** | Premature microservices | Keep code in same module |
| **Factory patterns** | Enterprise over-engineering | Direct instantiation |
| **Complex abstraction** | YAGNI violation | Simple concrete implementation |
| **Scalability requirements** | Premature optimization | Optimize when needed |
| **Enterprise-grade** | Marketing term, not technical | Use "production-ready" with specifics |
| **Lock ordering** | Complex threading | Use single RLock per object |
| **Continuous monitoring** | Background service prohibited | Use on-demand `/health` |
| **Real-time metrics** | Background service prohibited | Use query-based metrics |

## Implementation

### Filter Function

```python
from enum import Enum
from typing import List, NamedTuple

class ViolationType(Enum):
    SERVICE_EXTRACTION = "Premature service extraction"
    FACTORY_PATTERN = "Factory pattern (enterprise bloat)"
    COMPLEX_ABSTRACTION = "Unnecessary abstraction layer"
    SCALABILITY_REQUIREMENT = "Premature scalability optimization"
    ENTERPRISE_GRADE = "Vague marketing term"
    LOCK_ORDERING = "Complex concurrency pattern"
    CONTINUOUS_MONITORING = "Background service"

class FilterResult(NamedTuple):
    violates_constitution: bool
    violation_type: ViolationType | None
    suggestion: str

def constitutional_filter_check(action: dict) -> FilterResult:
    """Check if a proposed skill change violates solo-dev constitution."""

    # Check for prohibited patterns in description/implementation
    description = action.get("description", "").lower()
    implementation = action.get("implementation", "").lower()
    combined = description + " " + implementation

    # Service extraction
    if any(term in combined for term in ["extract to service", "microservice", "service boundary"]):
        return FilterResult(
            True,
            ViolationType.SERVICE_EXTRACTION,
            "Keep code in same module. Extract only if proven reuse benefit."
        )

    # Factory pattern
    if "factory" in combined:
        return FilterResult(
            True,
            ViolationType.FACTORY_PATTERN,
            "Use direct instantiation or simple builder pattern."
        )

    # Complex abstraction
    if any(term in combined for term in ["abstraction layer", "flexibility", "extensibility"]):
        return FilterResult(
            True,
            ViolationType.COMPLEX_ABSTRACTION,
            "Implement concrete solution first. Abstract only if proven need."
        )

    # Scalability requirements
    if any(term in combined for term in ["scalability", "high availability", "horizontal scale"]):
        return FilterResult(
            True,
            ViolationType.SCALABILITY_REQUIREMENT,
            "Optimize for current needs. Scale when proven necessary."
        )

    # Enterprise-grade
    if "enterprise-grade" in combined:
        return FilterResult(
            True,
            ViolationType.ENTERPRISE_GRADE,
            "Use specific terms: 'handles 10K requests/sec' not 'enterprise-grade'."
        )

    return FilterResult(False, None, "")
```

### Usage in Skill Creation

```python
def validate_skill_proposal(proposal: dict) -> List[FilterResult]:
    """Validate all actions in a skill proposal."""
    violations = []

    for action in proposal.get("actions", []):
        result = constitutional_filter_check(action)
        if result.violates_constitution:
            violations.append(result)

    return violations

def apply_constitutional_filter(proposal: dict) -> dict:
    """Remove constitution-violating actions from proposal."""
    filtered_actions = []
    removed_count = 0

    for action in proposal.get("actions", []):
        result = constitutional_filter_check(action)
        if result.violates_constitution:
            removed_count += 1
            print(f"⚠️ FILTERED: {result.violation_type.value}")
            print(f"   Suggestion: {result.suggestion}")
        else:
            filtered_actions.append(action)

    proposal["actions"] = filtered_actions
    print(f"Constitutional filter: Removed {removed_count} prohibited patterns")

    return proposal
```

## Example Violations

### Service Extraction

```
PROPOSED: "Extract authentication to separate microservice"
FILTERED: True
SUGGESTION: Keep auth in same module. Extract only if multiple independent consumers.
```

### Factory Pattern

```
PROPOSED: "Create DatabaseConnectionFactory for connection pooling"
FILTERED: True
SUGGESTION: Use direct connection initialization or simple context manager.
```

### Scalability Requirements

```
PROPOSED: "Design for horizontal scaling across multiple nodes"
FILTERED: True
SUGGESTION: Optimize for single-node performance. Scale when proven bottleneck.
```

## Integration with /skill-ship

### Phase 2: Creation & Structuring

Add constitutional filter to Phase 2:

```yaml
# Phase 2 workflow_steps:
- phase_2_creation: |
    Create skill structure WITH constitutional filter:
    - Auto-filter prohibited patterns (service extraction, factory patterns)
    - Solo-dev constraints: No enterprise bloat, simple solutions preferred
    - Resources: references/constitutional-filter.md
```

### Quality Gate Table

Add constitutional check to Phase 3:

| Test | Status | Evidence | Fix |
|------|--------|----------|-----|
| Constitutional filter | - | No prohibited patterns found | - |
| YAML completeness | - | - | - |
| Trigger accuracy | - | - | - |

## Why This Matters

Refactoring suggestions are high-risk for enterprise bloat:

| Anti-Pattern | Consequence |
|--------------|-------------|
| "Extract to service" | Unnecessary microservice, added complexity |
| "Add abstraction layer" | Over-engineering, harder debugging |
| "Implement factory pattern" | Enterprise pattern, premature complexity |

By filtering these patterns during skill creation, we maintain:
- **Simplicity**: Skills do one thing well
- **Maintainability**: Direct code is easier to understand
- **Performance**: No unnecessary layers
- **Solo-dev feasible**: One person can understand and modify

## Benefits

| Benefit | Impact |
|---------|--------|
| **Prevent bloat** | Skills remain focused and simple |
| **Faster development** | No time on unnecessary abstractions |
| **Easier onboarding** | New contributors understand quickly |
| **Better performance** | Fewer layers = less overhead |

---

**Source**: `/refactor` skill (Constitutional Compliance)
**Related**: `references/workflow-phases.md` (Phase 2 Creation), `MEMORY.md` (Solo-dev constraints)
