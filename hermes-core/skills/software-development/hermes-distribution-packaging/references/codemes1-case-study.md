# codemes_1 — Distribution Packaging Case Study

> **Date:** 2026-06-14
> **Cycle:** Full 10-phase orchestration
> **Result:** 14/14 AC passed, dist/ = 647 files, 9.1 MB

## Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Distribution size | < 200 MB | 9.1 MB |
| Install time | < 60 sec | < 10 sec |
| Acceptance criteria | 14/14 | 14/14 |
| gitleaks findings | 0 | 0 |
| .db files in dist | 0 | 0 |
| Agent .md files | ≥ 12 | 12 |
| Skill categories | ≥ 22 | 22 |
| Principles (KISS+DRY+YAGNI+SOLID) | 32 | 31/32 |
| Tests | — | ~174 |

## Bugs Found and Fixed

| Bug | Severity | Root Cause | Fix |
|-----|----------|-----------|-----|
| BUG-01: .env.template missing from dist | 🔴 HIGH | `cp -r dir/*` doesn't copy dotfiles | `shopt -s dotglob` before copy |
| BUG-02: API key format comments trigger validator | 🟡 MEDIUM | `# Формат: ***...` matches `sk-ant-` pattern | Replace format comments with `CHANGEME` descriptions |
| BUG-03: .manifest_hash not in whitelist | 🟢 LOW | Validator didn't account for auto-generated file | Add `.manifest_hash` to manifest_internal whitelist |

## Architecture Drift (Critic Finding)

manifest.yaml claims "single source of truth" but pack.sh (~800 lines) hardcodes
include rules instead of parsing the manifest. `lib/yaml_parser.sh` (324 lines)
was written and tested but NEVER USED by pack.sh.

Result: 1700+ lines of library code (yaml_parser.sh, secret_sanitizer.sh,
file_copier.sh) exist as parallel implementations to pack.sh's inline logic.

Lesson: Design docs must match implementation. If manifest.yaml is "source of truth",
it must actually drive pack.sh. Otherwise, acknowledge pack.sh as the executable
truth and demote manifest.yaml to declarative documentation.

## Production Files (25+)

```
codemes_1/
├── pack.sh              ← builder (6 phases)
├── install.sh           ← installer (merge/upgrade)
├── manifest.yaml        ← declarative specification
├── README.md            ← lego-claw style
├── CHANGELOG.md         ← date-based versioning
├── LICENSE (MIT)
├── VERSION (2026.06.14)
├── .gitignore
├── lib/                 ← 12 bash libraries
│   ├── yaml_parser.sh
│   ├── file_copier.sh
│   ├── secret_sanitizer.sh
│   ├── symlink_manager.sh
│   ├── validator.sh
│   ├── hash_manager.sh
│   ├── preflight.sh
│   ├── backup_manager.sh
│   ├── file_merger.sh
│   ├── template_installer.sh
│   ├── plugin_installer.sh
│   └── report_generator.sh
├── llm_bootstrap/       ← first-run onboarding
├── templates/           ← Russian templates
└── tests/               ← ~174 tests
```
