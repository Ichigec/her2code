# .gitignore Templates for Snapshot Cleanup

Ready-to-use `.gitignore` files for common project types. Copy when a repo
was committed without `.gitignore` and build artifacts need untracking.

## Android / Gradle

```
# Gradle
.gradle/
build/

# Android
*.apk
*.aab
*.ap_
*.dex
*.class

# Build outputs
app/build/
build/

# Local config
local.properties

# IDE
.idea/
*.iml
.vscode/

# OS
.DS_Store
Thumbs.db

# Logs
*.log

# Keystore
*.jks
*.keystore

# NDK
.cxx/
```

## Node.js / Electron / React

```
# Dependencies
node_modules/

# Build outputs
dist/
build/
out/
.next/
.nuxt/

# Electron
release/

# Local config
.env
.env.local
.env.*.local

# IDE
.idea/
*.iml
.vscode/

# OS
.DS_Store
Thumbs.db

# Logs
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Cache
.cache/
.parcel-cache/
.eslintcache
```

## Python

```
# Bytecode
__pycache__/
*.py[cod]
*$py.class

# Virtual envs
.venv/
venv/
env/

# Distribution
build/
dist/
*.egg-info/
*.egg

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# IDE
.idea/
.vscode/

# OS
.DS_Store

# Local config
.env
```

## Session Example: 2026-07-03 Multi-Component Snapshot

Snapshot of Hermes Agent + Android app + config files.

### Components and states (before)

| Component | Path | Repo | Uncommitted | .gitignore | Build artifacts tracked |
|-----------|------|------|-------------|------------|------------------------|
| Hermes Agent | `~/.hermes/hermes-agent/` | git, main | 13 files | yes | no |
| Android App | `~/dev/Opencode/` | git, master | 703 files | **NO** | **2808 files** (.gradle/, app/build/) |
| Config | `~/.hermes/config.yaml` + `.env` | n/a | n/a | n/a | n/a |

### Actions taken

1. **Android**: Created `.gitignore` (Android template above) →
   `git rm -r --cached .gradle/ app/build/` (2808 files untracked) →
   `git add -A` → 17 source files staged, 2808 deletions staged →
   `git commit` → `git tag -a stable-2026-07-03`

2. **Hermes Agent**: `git add -A` (13 files: consolidation_manager, segtree
   memory plugin, observer-hook, codebase_read_tool, desktop UI updates) →
   `git commit` → `git tag -a stable-2026-07-03`

3. **Config**: `cp config.yaml` + `.env` to `~/.hermes/backups/` with
   `.stable-2026-07-03` suffix. chmod 600.

4. **Dev branches**: `git branch dev` in both repos.

### Result

```
main / master  ← stable-2026-07-03 tag, clean working tree
     ↑
   dev         ← future experimental work
```

Recovery: `git checkout stable-2026-07-03` + restore config backups.
