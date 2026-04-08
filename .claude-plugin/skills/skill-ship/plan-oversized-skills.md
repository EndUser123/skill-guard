# Plan: Reduce Oversized Skills to <500 Lines

## RALPH_STATUS

- EXIT_SIGNAL: false
- completion_indicators: 0
- current_task: TASK-001

## Acceptance Criteria

- All skills currently >500 lines have SKILL.md reduced to <500 lines
- Extracted content moved to `references/` files within each skill directory
- SKILL.md files link to extracted references using relative paths
- No execution instructions or trigger content removed — only reference/educational content extracted
- WARN skills (300-500) are addressed if time permits

## Strategy

For each skill:
1. Read SKILL.md, identify sections that are reference material (examples, templates, detailed guides, verbose tables, API docs)
2. Extract those sections to `references/<descriptive-name>.md`
3. Replace in SKILL.md with a brief summary + link to the reference file
4. Verify target line count <500 achieved

## Tasks

- [ ] TASK-001 Extract context from `p` (2667→<500) — largest skill
- [ ] TASK-002 Extract context from `code` (2621→<500)
- [ ] TASK-003 Extract context from `github-ready` (2506→<500)
- [ ] TASK-004 Extract context from `debugRCA` (2190→<500)
- [ ] TASK-005 Extract context from `gitready` (1928→<500)
- [ ] TASK-006 Extract context from `arch` (1709→<500)
- [ ] TASK-007 Extract context from `usm` (1200→<500)
- [ ] TASK-008 Extract context from `refactor` (1056→<500)
- [ ] TASK-009 Extract context from `tdd` (988→<500)
- [ ] TASK-010 Extract context from `search` (912→<500)
- [ ] TASK-011 Extract context from `ai-openrouter` (900→<500)
- [ ] TASK-012 Extract context from `av` (892→<500)
- [ ] TASK-013 Extract context from `verify` (890→<500)
- [ ] TASK-014 Extract context from `team` (750→<500)
- [ ] TASK-015 Extract context from `r` (747→<500)
- [ ] TASK-016 Extract context from `all` (716→<500)
- [ ] TASK-017 Extract context from `nlm` (702→<500)
- [ ] TASK-018 Extract context from `subagent-driven-development` (689→<500)
- [ ] TASK-019 Extract context from `csf-nip-integration` (664→<500)
- [ ] TASK-020 Extract context from `planning` (660→<500)
- [ ] TASK-021 Extract context from `trace` (605→<500)
- [ ] TASK-022 Extract context from `loop-code` (578→<500)
- [ ] TASK-023 Extract context from `main` (551→<500)
- [ ] TASK-024 Extract context from `s` (537→<500)
- [ ] TASK-025 Extract context from `skill-ship` (536→<500)
- [ ] TASK-026 Extract context from `ai-chutes` (532→<500)
- [ ] TASK-027 Extract context from `t` (516→<500)
