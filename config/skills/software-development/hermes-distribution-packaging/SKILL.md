---
name: hermes-distribution-packaging
description: "Package Hermes Agent into a sanitized, installable distribution — manifest-driven packaging with pack.sh/install.sh pipeline, secret sanitization, and first-run onboarding."
version: 1.0.0
author: Hermes Agent + User
license: MIT
metadata:
  hermes:
    tags: [distribution, packaging, deployment, sanitization, onboarding, manifest]
    related_skills: [hermes-agent, orchestration-cycle, multi-agent-orchestration]
---

# Hermes Distribution Packaging

Package a sanitized Hermes Agent installation into a distributable archive.
Excludes secrets, databases, caches, logs, and development artifacts. Produces
a clean directory tree installable via `install.sh`.

## When to use

- User asks to "упаковать Hermes в дистрибутив" or "сделать portable версию"
- Preparing Hermes for another developer or machine
- Creating a public/open-source variant of a personal Hermes setup
- Building a `codemes_*` project for distribution

## Architecture

The distribution pipeline has 4 stages:

```
~/.hermes/ (6717 files, 500MB raw)
    │
    ▼
manifest.yaml — declarative include/exclude/sanitize/validate rules
    │
    ▼
pack.sh — 6 phases: parse → copy → sanitize → symlinks → validate → hash
    │
    ▼
dist/ (647 files, ~9MB clean)
    │
    ▼
install.sh — merge strategy (6 scenarios) → ~/.hermes/ on target machine
```

## Key files

| File | Role |
|------|------|
| `manifest.yaml` | Single source of truth — 14 include, 13 exclude_global, 8 sanitize, 7 validate rules |
| `pack.sh` | Build script — reads manifest, copies with filters, sanitizes secrets, runs validations |
| `install.sh` | Install script — preflight checks, merge logic, template installation, plugins |
| `lib/` | 12 bash libraries (yaml_parser, file_copier, secret_sanitizer, symlink_manager, validator, hash_manager, preflight, backup_manager, file_merger, template_installer, plugin_installer, report_generator) |
| `llm-bootstrap/hermes_bootstrap.py` | First-run detection (CHANGEME) → onboarding system prompt injection |
| `templates/` | ИНСТРУКЦИЯ.md, НАСТРОЙКА.md, `.env.template` — Russian onboarding |
| `VERSION` | Date-based version (2026.06.14) — upgrade path key |

## pack.sh — 6 phases

1. **Parse** — CLI args + manifest.yaml validation (python3 YAML)
2. **Prepare** — clean/create target directory
3. **Copy** — glob filters, local + global excludes, sanitize-on-copy
4. **Static** — templates (dotglob!), symlinks (profiles/1/skills → ../../hermes-core/skills), VERSION file
5. **Validate** — 7 checks (gitleaks, find_db_files, find_env_secrets, size_limit, agent_count, skill_categories, manifest_internal)
6. **Report** — SHA256 `.manifest_hash` + summary

Exit codes: 0=success, 1=validation failed, 2=source error, 3=manifest error.

## install.sh — merge strategy

6 scenarios for each file:

| # | Condition | Action |
|---|-----------|--------|
| 1 | Target absent | COPY |
| 2 | Exists, identical | SKIP |
| 3 | Exists, different, `--force` | OVERWRITE |
| 4 | Exists, different, no `--force` | WARN + skip |
| 5 | `--upgrade`, user didn't modify | UPDATE (hash-based) |
| 6 | `--upgrade`, user modified | WARN + skip |

Special files (`.codemes_version`, `.manifest_hash`, `VERSION`) always overwrite.
User `.env` NEVER touched.

## `.env.template` pitfalls

### API key format comments trigger validators

**Problem:** Comment lines like `# Формат: sk-ant-api03-...` contain substrings
(`sk-ant-`) that match `grep -rP 'sk-ant-'` validator patterns. The validator
flags `.env.template` as containing real API keys.

**Fix:** Use descriptive format comments WITHOUT actual API key prefixes:

```bash
# ❌ Triggers validator
# Формат: sk-ant-api03-...
# Формат: sk-...

# ✅ Safe
# Формат: CHANGEME (начинается с sk-ant префикс)
# Формат: CHANGEME (начинается с sk-префикс)
```

The space after `sk-ant` breaks the regex match while preserving the instruction.

### Dotfiles not copied by `cp -r dir/*`

**Problem:** `cp -r "$templates_src"/* "$TARGET/templates/"` skips dotfiles
(`.env.template`). Bash glob `*` excludes hidden files.

**Fix:** Enable dotglob before copy:

```bash
shopt -s dotglob
cp -r "$templates_src"/* "$TARGET/templates/" 2>/dev/null || true
shopt -u dotglob
```

### Secret sanitizer leaves partial matches

**Problem:** Sanitizer replaces `api03` → `***` in `sk-ant-api03-...`, producing
`sk-ant-***...`. The `sk-ant-` prefix remains and matches API key detectors.

**Fix:** Sanitize the ENTIRE key, not components. Match `sk-ant-` prefix pattern
explicitly in sanitizer rules, replacing the whole value with `CHANGEME`.

## Phase 0 heredoc pitfall

When generating `structure.md` via bash heredoc, **single-quoted delimiters**
(`<< 'EOF'`) prevent shell expansion. `$(tree ...)` remains as literal text.

```bash
# ❌ Variables NOT expanded
cat > file << 'EOF'
$(tree /dir)
EOF

# ✅ Variables expanded
cat > file << EOF
$(tree /dir)
EOF
```

**Post-creation verification:**
```bash
grep -c '\$(' structure.md   # must return 0
```

## Variants: public vs pers

Two distribution variants via `--variant` flag:

| Variant | Includes | Excludes |
|---------|----------|----------|
| `public` | agents, skills, plugins, hooks, cron, scripts, templates, profiles | memories/, personal configs, telegram-proxies.md, hermes-gateway-api-setup.md |
| `pers` | Everything in public + memories/, full config | Same exclusions as public |

## First-run onboarding

`llm-bootstrap/hermes_bootstrap.py` detects first run by scanning `config.yaml`
for `CHANGEME` values. On detection, augments the system prompt with a Russian
onboarding block that:

1. Greets the user in Russian
2. Explains what needs to be configured (API keys, Neo4j, OpenCode+)
3. Points to `ИНСТРУКЦИЯ.md`, `НАСТРОЙКА.md`, `.env.template`
4. DOES NOT ask for API keys in chat (security rule)

## Upgrade path

`install.sh --upgrade` flow:
1. Compare `VERSION` files (old vs new)
2. Compare `.manifest_hash` files (SHA256 sum)
3. Diff the manifests → [added], [removed], [changed] files
4. Copy only added + unchanged files (user-modified files preserved)

## manifest.yaml quick-start

```yaml
version: "2026.06.14"
variant: public

include:
  - source: ~/.hermes/agents/
    dest: hermes-core/agents/
    glob: "*.md"
  - source: ~/.hermes/skills/
    dest: hermes-core/skills/
    recursive: true
    sanitize: secrets
    exclude: "telegram-proxies.md,hermes-gateway-api-setup.md"

exclude_global:
  - "*.db"
  - "*.db-shm"
  - "*.db-wal"
  - ".env"
  - "auth.json"
  - "cache/"
  - "logs/"
  - "sessions/"
  - "sandboxes/"
  - "models_dev_cache.json"

sanitize:
  - pattern: "sk-[a-zA-Z0-9]{20,}"
    replace: "CHANGEME"
  - pattern: "api_key: .+"
    replace: "api_key: CHANGEME"

validate:
  - type: gitleaks
    command: "gitleaks detect --source {dist_dir} --no-git -v"
    expect: "no leaks found"
  - type: find_db_files
    command: "find {dist_dir} -name '*.db' -o -name '*.db-shm' -o -name '*.db-wal'"
    stdout_empty: true
```

## References

- `references/codemes-distribution-session.md` — full session transcript of the
  codemes_1 packaging cycle (2026-06-14): requirements, system analysis, architecture,
  implementation, security audit, acceptance testing. 9 bugs found and fixed.
- `references/manifest-reference.md` — canonical manifest.yaml with all 14 include
  rules, 13 exclude categories, 8 sanitize patterns, and 7 validate checks.
