# Security Policy

## Supported Versions

Currently supported versions:
| Version | Supported |
|---------|-----------|
| 1.0.x   | ✅        |

## Reporting a Vulnerability

If you discover a security vulnerability, please send an email to noreply@csf.nip.

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if known)

**Response Time**: We will acknowledge receipt within 48 hours and provide a fix or workaround within 7 days.

## Security Best Practices

### For Hook Developers
- **Validate all inputs**: Don't trust skill frontmatter without validation
- **Sanitize file paths**: Prevent directory traversal attacks
- **Check file permissions**: Ensure files are readable before parsing
- **Handle exceptions**: Don't let parsing errors crash hooks

### Example
```python
from skill_guard import get_skill_config

# Always handle potential errors
try:
    config = get_skill_config("skill-name")
    if config:
        # Use validated config
        pass
except (ValueError, KeyError) as e:
    # Handle parsing errors safely
    logger.error(f"Invalid skill config: {e}")
```

## Security Considerations

### Filesystem Access
This library reads from:
- `.claude/skills/*/SKILL.md` - User's skill directory
- `.claude/state/skill_execution/` - Session state directory

Both are user-controlled directories within the project workspace.

### External Dependencies
- **PyYAML** - Used for parsing YAML frontmatter
  - Version pinned in pyproject.toml
  - No known security issues in current version

### No Network Access
This library does not make any network requests or external API calls.

## Security Audits

This library has not undergone a formal security audit. We welcome security reviews from the community.

## Vulnerability Disclosure

We will:
- Confirm receipt of the report
- Provide timeline for fix
- Disclose vulnerability publicly after fix is released
- Credit the reporter (unless requested otherwise)

## Minimum Security Standards

Before reporting, please ensure:
- The issue is a security vulnerability (not just a bug)
- You've tested against the latest version
- You can provide reproduction steps
- The issue has real-world security impact

For non-security bugs, please use the GitHub issue tracker.
