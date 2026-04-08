## Learning Loop for /skill-audit

### Goal

Use raw transcript history as a signal source, then convert recurring failures into durable lessons that improve target skills over time.

### Authority Order

1. Current code / validators / hooks
2. Current skill contracts
3. Current artifacts (plans, ADRs, reports)
4. Prior review artifacts
5. Raw transcript history

Raw transcripts are useful, but they are the least authoritative source.

### What to Mine From Chat History

Good candidate signals:
- repeated user corrections
- repeated “LLM defended stale artifact” behavior
- repeated routing loops between skills
- repeated schema/format mismatches
- repeated stale-data or multi-terminal failures
- repeated hook misuse or unnecessary new hooks

Bad candidate signals:
- one-off frustration with no recurrence
- stale intermediate reasoning later corrected
- complaints contradicted by current code
- pure preference with no workflow impact

### Distillation Rule

Never promote a raw transcript observation directly into a skill change.

First distill it into a lesson record:

```json
{
  "pattern": "routing loop on malformed ADR-derived plan",
  "symptom": "planning escalates schema rewrite issues back to arch",
  "root_cause": "missing ingestion contract between /arch and /planning",
  "recurrence": 3,
  "confidence": "high",
  "best_detector": "planning verifier",
  "best_fix_layer": "validator",
  "owner": "skill-ship"
}
```

### Recommended Fields

| Field | Meaning |
|-------|---------|
| `pattern` | Short reusable failure label |
| `symptom` | What the user/agent experienced |
| `root_cause` | Why it happened |
| `recurrence` | Count or qualitative recurrence level |
| `confidence` | low / medium / high |
| `best_detector` | where this should be detected next time |
| `best_fix_layer` | doc / validator / hook / test / architecture |
| `owner` | source skill / skill-ship / skill-audit |

### Promotion Rule

Promote a lesson only when at least one is true:
- it has repeated in multiple chats or multiple times in one thread
- it caused workflow interruption or unsafe behavior
- it reflects a stable design error rather than a one-off wording issue

### Output Expectation

`/skill-audit` should surface:
- the lesson table in the final audit
- which lessons are approved for implementation
- which should remain prompt-guidance only
