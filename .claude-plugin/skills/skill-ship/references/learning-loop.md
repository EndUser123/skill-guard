## Learning Loop for /skill-ship

### Goal

Turn approved lessons from `/skill-audit` into concrete improvements at the right layer, without over-automating transient or judgment-heavy behavior.

### Input Contract

`/skill-ship` should prefer structured lessons over raw transcript mining.

Expected lesson shape:

```json
{
  "pattern": "stale review artifact confusion",
  "symptom": "users trust old review summary after verifier changed",
  "root_cause": "review summaries were not invalidated on re-verify",
  "best_fix_layer": "validator",
  "owner": "skill-ship"
}
```

### Fix-Layer Decision

| Best Fix Layer | When to Choose It |
|----------------|-------------------|
| `doc` | behavior should remain flexible and judgment-driven |
| `validator` | failure is repeated and structurally detectable before use |
| `hook` | runtime enforcement is needed at the point of action |
| `test` | regression needs to stay caught forever |
| `architecture` | boundary/ownership is wrong upstream |

### Post-Ship Reflection

After implementing lessons, emit a short reflection:

| Field | Meaning |
|-------|---------|
| `pattern` | failure class addressed |
| `implemented_at` | doc / validator / hook / test / architecture |
| `residual_risk` | what still depends on human judgment |
| `next_promotion` | what should become stronger next if it recurs |

Example:

```json
{
  "pattern": "malformed ADR-derived planning drafts",
  "implemented_at": "validator",
  "residual_risk": "planner can still shallow-copy prose if the handoff packet is missing",
  "next_promotion": "block /arch closure for planning-bound ADRs missing handoff packet"
}
```

### Constraints

- Do not ship changes directly from raw transcript anecdotes.
- Do not add hooks when prompt guidance or validators are enough.
- Do not leave repeated failures at the prose-only layer forever.
