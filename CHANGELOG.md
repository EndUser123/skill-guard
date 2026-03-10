# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-09

### Added
- Initial release of skill-guard Python library
- Universal skill auto-discovery from `.claude/skills/*/SKILL.md` frontmatter
- Script pattern detection for skill gate enforcement
- Knowledge skill exemption (distinguishes execution vs reference skills)
- Backwards compatibility with explicit `SKILL_EXECUTION_REGISTRY`
- Terminal ID detection and multi-terminal safety
- Breadcrumb trail verification system
- Skill execution state management
- Test suite with 10 passing tests (67% coverage)
- Complete pyproject.toml configuration with dev dependencies
- README with installation and usage examples
- MIT License

### Features
- **Zero-Maintenance Auto-Discovery**: Automatically scans all skill frontmatter
- **Dual-Layer Enforcement**: UserPromptSubmit + PreToolUse hook cooperation
- **Fast Performance**: Discovers 184+ skills in milliseconds
- **Terminal Isolation**: Multi-terminal safety with terminal_id detection
- **Breadcrumb Verification**: Complete breadcrumb trail verification system
- **Backwards Compatible**: Explicit registry takes precedence over auto-discovery

[1.0.0]: https://github.com/yourusername/skill-guard/releases/tag/v1.0.0
