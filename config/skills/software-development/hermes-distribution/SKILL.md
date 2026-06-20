---
name: hermes-distribution
description: "Package Hermes Agent as a distributable project: manifest.yaml + pack.sh + install.sh + templates + first-run LLM onboarding."
version: 1.0.0
author: Hermes Agent + User
license: MIT
metadata:
  hermes:
    tags: [distribution, packaging, manifest, install, onboarding, codemes]
    related_skills: [multi-agent-orchestration, orchestration-cycle]
---

# Hermes Distribution Packaging

Use this skill when packaging Hermes Agent (or any codemes project) as a
distributable: manifest-driven selective file copying, secret sanitization,
validation gate, Russian-first-run onboarding with LLM.

Full case study: codemes_1 (2026-06-14) — 14/14 acceptance criteria passed,
647 files, 9.1 MB distribution, 7/7 validations, gitleaks clean.

## Architecture

```
manifest.yaml          ← single source of truth (include/exclude/sanitize/validate)
pack.sh                ← builder: parse→copy→sanitize→symlinks→validate→hash
install.sh             ← installer: precheck→backup→merge→templates→plugins→report
lib/*.sh               ← modular bash libraries (validator, hash_manager, etc.)
templates/             ← .env.template, ИНСТРУКЦИЯ.md, НАСТРОЙКА.md (Russian)
llm_bootstrap/         ← Python: detect CHANGEME → inject onboarding prompt
```

## manifest.yaml — Source of Truth

Declarative specification of what goes into the distribution. Any file NOT listed
in `include` will NOT be packaged.

Sections:
- `include[]` — source/dest/glob/recursive/sanitize rules
- `exclude_global[]` — patterns to exclude from ALL copies
- `sanitize{}` — sed replacement rules (secrets → CHANGEME)
- `validate[]` — post-build checks (gitleaks, size, agent count, etc.)

## Critical Pitfalls

### Dotfiles NOT copied by `cp -r dir/*`

`cp -r "$templates_src"/* "$TARGET/"` silently skips `.env.template` and other
dotfiles because `*` glob excludes them by default.

**Fix:**
```bash
shopt -s dotglob
cp -r "$templates_src"/* "$TARGET/templates/" 2>/dev/null || true
shopt -u dotglob
```

This cost 1 full rework cycle in codemes_1 (BUG-01 in acceptance testing).

### Template comments trigger API key detection

Validators like `grep -rP '(sk-or-|sk-ant-|AIza...)' dist/` match COMMENT lines
that DESCRIBE key formats. Example: `# Формат: sk-ant-api03-...` triggers `sk-ant-`.

**Fix:** Use `CHANGEME` in format description comments, never real key prefixes:
```
# Формат: CHANGEME (начинается с sk-ant префикс)
```

### manifest.yaml vs pack.sh disconnect

The most common architectural drift: `manifest.yaml` claims to be "single source
of truth", but `pack.sh` hardcodes include rules instead of parsing the manifest.
Result: two parallel sources of truth that diverge.

**Fix:** Either parse manifest.yaml in pack.sh (via `lib/yaml_parser.sh`), OR
acknowledge manifest.yaml as declarative documentation and keep pack.sh as the
executable source of truth. Don't maintain both as active.

### Exclude aggressive file lists

Categories that MUST be excluded:
- `.db`, `.db-shm`, `.db-wal` — database files
- `.env`, `auth.json`, `*.bak` — secrets and backups
- `cache/`, `logs/`, `sessions/` — runtime state
- `node_modules/`, `__pycache__/` — dependencies
- `plans/`, `reports/critique-*.md` — development artifacts
- `agents.backup/` — stale backups

## Two Variants: Public vs Personal

```
pack.sh --variant public   → codemes_1 (no memory files, clean)
pack.sh --variant pers     → codemes_1_pers (includes User's memory)
```

## First-Run LLM Onboarding

`llm_bootstrap/hermes_bootstrap.py`:
1. Detects `CHANGEME` in config.yaml
2. Injects Russian onboarding system prompt
3. Guides user through setup (API keys, Neo4j, OpenCode+)
4. References `ИНСТРУКЦИЯ.md` and `НАСТРОЙКА.md` templates

## README Style (lego-claw reference)

From https://github.com/<YOUR_GITHUB_USER>/lego-claw:
- ASCII-art banner header
- Emoji section markers
- Quick start in 3 commands
- Detailed structure tree
- Russian language throughout
- Badges where applicable
- LICENSE: MIT, versioning: date-based (YYYY.MM.DD)

## Validation Gate

7 checks run by `lib/validator.sh` after build:
1. `gitleaks` — no secret leaks (graceful degradation if gitleaks not installed)
2. `find_db_files` — no .db/.db-shm/.db-wal
3. `find_env_secrets` — no real API keys in templates
4. `size_limit` — distribution < 200 MB
5. `agent_count` — ≥ 12 agent .md files
6. `skill_categories` — ≥ 22 skill directories
7. `manifest_internal` — only known file types in hermes-core/

## References

- `references/codemes1-case-study.md` — full acceptance report, bugs found, fixes applied
- Full architecture: codemes_1/docs/architecture/codemes-distribution.md (1622 lines)
- Observer persistence problem: multi-agent-orchestration skill, references/observer-persistence-problem.md
