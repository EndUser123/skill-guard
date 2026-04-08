---
type: core
load_when: optimization
priority: mandatory
estimated_lines: 80
---

# Recommended Next Steps Format Specification

Format specification for the "Recommended Next Steps" section output by skill-ship. See SKILL.md for when to use this format.

## Human-Readable Format

```markdown
**Recommended Next Steps**

1 - Analyze intent and detect conflicts
- 1a: Similarity analysis → Use `/similarity <target>` - Find redundant/similar skills
- 1b: Intent clarification → Manual interview - Understand user requirements

2 - Build skill structure with proper formatting
- 2a: Create skill draft → Use `/skill-creator` - Full iterative development with evals
- 2b: Structure guidance → Use `/skill-development` - SKILL.md patterns and progressive disclosure
- 2c: Convert docs → Use `/doc-to-skill` - Transform documentation into skills

3 - Validate specification, code quality, and integration
- 3a: Spec compliance → Internal testing-skills (spec mode) - Verify implementation follows plan
- 3b: Code quality → Internal av, testing-skills (quality mode) - YAML, triggers, context bloat
- 3c: Integration test → Internal testing-skills (integration mode) - Test skill invocation

4 - Empirical testing and performance analysis (optional for simple skills)
- 4a: Run eval suite → Use `/skill-creator` - Evals, benchmarks, variance analysis
- 4b: Optimize description → Use `/skill-creator` - Improve triggering accuracy

5 - Add hooks and enforce formatting
- 5a: Mechanical continuation → Use `/av2` - StopHook for multi-phase workflows
- 5b: Standardize output → Use `/output-style-extractor` - Enforce formatting templates

6 - Prepare for sharing and upstreaming
- 6a: Share via GitHub → Use `/sharing-skills` - Automated PR workflow
- 6b: Pre-publish checklist → Use `/github-public-posting` - Final quality checks

0 - Do ALL Recommended Next Steps
```

## Conditional Format (when no next steps needed)

```markdown
**Recommended Next Steps**

No next steps required - skill analysis complete.

0 - Nothing left to do
```

## Format Requirements

- Line 1: `1 - description` format (no parenthetical domain labels)
- Lines 2+: `- 1a: Action → Use /skill OR manual - context` format (dash prefix required)
- Skill recommendations: Use arrow syntax `→ Use /skill-name` (Claude executes this)
- Manual actions: Use `→ Manual check` or `→ No skill applies` (User does this themselves)
- End with: `0 - Do ALL Recommended Next Steps` OR `0 - Nothing left to do`
- Domains numbered 1, 2, 3...; Actions lettered a, b, c...
- Practical limit: ~20 total actions (3-6 domains x 2-4 items) for cognitive load
- **Critical**: Actions within a domain must NOT conflict. If selecting "0" or the domain number would create contradictory outcomes (e.g., "test" AND "skip testing"), split into separate domains

## Machine-Parseable Format (optional)

For downstream skill chaining via /ship or /handoff. Add `format: machine` to SKILL.md YAML frontmatter, or append `<!-- format: machine -->` to the output. When active, render RNS as pipe-delimited lines:

```
RNS|D|1|domain-label
RNS|A|1a|/skill-name|action-description
RNS|A|1b|manual|action-description
RNS|Z|0|ALL
```

Where: `RNS` = record type, `D` = domain header, `A` = action, `Z` = terminator, fields are `domain-num|action-num|skill-or-manual|description`. Terminate with `RNS|Z|0|NONE` if nothing left to do.

Human-readable format remains the default. Machine format is opt-in only.
