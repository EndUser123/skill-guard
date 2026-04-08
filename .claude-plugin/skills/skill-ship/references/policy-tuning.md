# Policy Tuning Guide

Lightweight workflow for tuning artifact type mappings in `config/policy.json` over time.

## Why Tune?

Artifact type classifications are initially conservative guesses. Over time, real runs reveal:
- Some low-risk types never fail — could relax validation
- Some medium-risk types consistently fail at specific phases — could tighten routing
- New artifact types emerge that don't fit existing categories

## What to Log

Per-run, record in a session log (e.g., `P:/.claude/.evidence/skill-ship/policy-tuning-log.jsonl`):

```json
{
  "timestamp": "2026-04-05T16:00:00Z",
  "artifact_type": "new_skill",
  "risk_level": "medium",
  "phases_run": ["3a", "3b", "3c", "3e", "3f"],
  "final_decision": "pass",
  "override_rationale": null,
  "notes": "simple 3-step skill, no evaluator findings"
}
```

## Tuning Triggers

| Signal | Action |
|--------|--------|
| Same type + same outcome 5x in a row | Consider adjusting risk_level or phases |
| Type frequently triggers unexpected failures | Upgrade risk_level or add phases |
| Type never fails and has high volume | Consider relaxing to bypass_3e_3f |
| New user intent pattern emerges | Add or rename artifact type |

## Review Cadence

Monthly sampling of the last ~20 runs is sufficient for solo dev. Look for:
1. Clustering of outcomes by artifact type
2. Override patterns (when orchestrator chose different type than default)
3. Phase-level failures (which phase fails most often for which type)

## How to Adjust

Edit `config/policy.json`:
- Change `risk_level` for a type → affects Rule 3 (conditional_pass threshold)
- Change `phases` list → changes what gets run
- Add `bypass_3e_3f: true` → only if type consistently passes without evaluator/judge

## Verification

After any tuning change, run the test suite:
```bash
cd P:/.claude/skills/skill-ship
pytest tests/test_policy_routing.py -v
```

If tests fail, revert the change and investigate before re-tuning.