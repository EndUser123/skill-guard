# Config File Conventions

**Principle:** Config files that driveskill-runner scripts must be treated as **templates** (stored in `references/`), while **actual runtime configs** must live in a staging or temp directory.

---

## Why

- **Templates in `references/`** are part of the skill's canonical structure — version-controlled, reviewed, shipped with the skill.
- **Runtime configs in `/tmp/` or a staging dir** are per-session or per-run — transient, user-specific, not shipped.
- Mixing them leads to configs being accidentally committed, or being overwritten during skill updates.

---

## Pattern

```
skill/
  references/
    config-template.yaml      # ← TEMPLATE: copy to /tmp/ before use
  scripts/
    runner.py                 # reads --config from CLI
```

**For skills that use config files:**

1. **Store the template** in `references/config-<purpose>-template.yaml`
2. **Document the pattern** in the SKILL.md Usage section:

   ```bash
   # 1. Copy template to staging
   cp references/config-template.yaml /tmp/my-config.yaml

   # 2. Edit the staging copy
   vim /tmp/my-config.yaml

   # 3. Run with staging config
   python scripts/runner.py --config /tmp/my-config.yaml
   ```

3. **Runner script** accepts `--config` as a required argument pointing to the staging copy
4. **Never hardcode** a default config path inside the skill directory

---

## Exceptions

| Situation | Config Location | Rationale |
|-----------|---------------|-----------|
| Skill ships with a **default config** that must exist | Store in skill dir (e.g., `config/defaults.yaml`) | Part of skill structure, not user-provided |
| **Secrets/API keys** | Always via env vars or `settings.json`, never in skill dir | Security |
| **证据/evidence files** | Always in `~/.claude/.evidence/` or staging | Never in skill directory |

---

## Anti-Pattern

```
❌ skill/
     config/
       repos.yaml        # ← actual user config committed to repo
```

```
✅ skill/
     references/
       repos-template.yaml  # ← template
```

**The anti-pattern:** User runs skill → config modified in-place → modified config gets committed → stale/bad configs ship with the skill.
