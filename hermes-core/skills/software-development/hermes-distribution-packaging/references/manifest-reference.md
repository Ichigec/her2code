# Canonical manifest.yaml Reference

> From codemes_1 distribution (2026-06-14). This is the authoritative
> declarative specification for what goes into a Hermes distribution.
> Any file not explicitly included WILL NOT be packaged.

```yaml
version: "2026.06.14"
variant: public  # public | pers

# === INCLUDE RULES (14 entries) ===
# Each rule: source path, destination path, glob filter, and options.
# Files matching these rules are the ONLY files copied into dist/.
include:
  # Core agents
  - source: ~/.hermes/agents/
    dest: hermes-core/agents/
    glob: "*.md"

  # Skills (largest component — recursive, sanitized)
  - source: ~/.hermes/skills/
    dest: hermes-core/skills/
    recursive: true
    sanitize: secrets
    exclude: "telegram-proxies.md,hermes-gateway-api-setup.md,opencode-plus-claw-neo4j.md"

  # Hooks
  - source: ~/.hermes/hooks/
    dest: hermes-core/hooks/
    glob: "*.py"

  # Scripts
  - source: ~/.hermes/scripts/
    dest: hermes-core/scripts/
    glob: "*"

  # Cron jobs
  - source: ~/.hermes/cron/
    dest: hermes-core/cron/
    glob: "*"

  # Skill bundles
  - source: ~/.hermes/skill-bundles/
    dest: hermes-core/skill-bundles/
    recursive: true

  # Config template
  - source: ~/.hermes/config.yaml
    dest: hermes-core/config.yaml.template
    sanitize: secrets

  # SOUL template
  - source: ~/.hermes/SOUL.md
    dest: hermes-core/SOUL.md.template

  # Core AGENTS.md
  - source: ~/.hermes/AGENTS.md
    dest: hermes-core/AGENTS.md

  # Profiles (without duplicating skills)
  - source: ~/.hermes/profiles/
    dest: profiles/
    recursive: true
    exclude: "skills/"

  # Plugins (without node_modules)
  - source: ~/.hermes/plugins/claw-neo4j/
    dest: plugins/claw-neo4j/
    recursive: true
    exclude: "node_modules/"

  - source: ~/.hermes/plugins/hermes-opencode/
    dest: plugins/hermes-opencode/
    recursive: true
    exclude: "node_modules/"

  # Memories (pers variant only — excluded in public)
  - source: ~/.hermes/memories/
    dest: hermes-core/memories/
    recursive: true
    variant: pers

  # Hermes Agent core (optional — if not using pip install)
  # - source: ~/.hermes/hermes-agent/
  #   dest: hermes-agent/
  #   recursive: true
  #   exclude: "__pycache__/,*.pyc,venv/,node_modules/,.git/"

# === GLOBAL EXCLUDES (13 categories) ===
# These patterns are applied to ALL include rules.
exclude_global:
  # Databases
  - "*.db"
  - "*.db-shm"
  - "*.db-wal"

  # Secrets and auth
  - ".env"
  - "auth.json"
  - "auth.lock"
  - ".sudo_pass"

  # Caches
  - "cache/"
  - "models_dev_cache.json"
  - "ollama_cloud_models_cache.json"
  - "provider_models_cache.json"
  - ".skills_prompt_snapshot.json"
  - "audio_cache/"
  - "image_cache/"

  # Logs
  - "logs/"
  - "*.log"

  # Sessions
  - "sessions/"
  - "state-snapshots/"
  - "state.db"
  - "audit.db"
  - "kanban.db"
  - "metrics.db"
  - "response_store.db"

  # Sandboxes
  - "sandboxes/"

  # Pairing and LSP
  - "pairing/"
  - "lsp/"

  # Runtime state
  - "desktop.pid"
  - "gateway_state.json"
  - "processes.json"
  - "channel_directory.json"
  - ".clean_shutdown"
  - ".update_check"
  - ".install_method"
  - "desktop-build-stamp.json"

  # Backups
  - "*.bak.*"
  - "agents.backup*/"

  # Development artifacts
  - "reports/critique-*.md"
  - "plans/*.md"

  # Bytecode
  - "__pycache__/"
  - "*.pyc"
  - "*.pyo"

  # Dependencies
  - "node_modules/"
  - "venv/"
  - ".git/"

# === SANITIZE RULES (8 patterns) ===
# Applied to files marked with sanitize: secrets
sanitize:
  - pattern: "api_key: .+"
    replace: "api_key: CHANGEME"
  
  - pattern: "base_url: .+"
    replace: "base_url: CHANGEME"
  
  - pattern: "password: .+"
    replace: "password: CHANGEME"
  
  - pattern: "token: .+"
    replace: "token: CHANGEME"
  
  - pattern: "secret: .+"
    replace: "secret: CHANGEME"
  
  - pattern: "\\$\\{[A-Z_]+\\}"
    replace: "CHANGEME"
  
  - pattern: "sk-[a-zA-Z0-9]{20,}"
    replace: "CHANGEME"
  
  - pattern: "AIza[A-Za-z0-9_-]{30,}"
    replace: "CHANGEME"

# === VALIDATE RULES (7 checks) ===
# Run after copying. Any failure → exit 1.
validate:
  - type: gitleaks
    description: "No secret leaks in distribution"
    command: 'gitleaks detect --source {dist_dir} --no-git -v'
    expect: "no leaks found"
    exit_code: 0

  - type: find_db_files
    description: "No database files"
    command: 'find {dist_dir} -name "*.db" -o -name "*.db-shm" -o -name "*.db-wal"'
    stdout_empty: true

  - type: find_env_secrets
    description: "No real API keys in templates"
    command: 'grep -rP "(sk-or-|sk-ant-|AIza|ya29\\.|ghp_|gho_|github_pat_)" {dist_dir} --include="*.yaml" --include="*.template" --include="*.env" -l'
    stdout_empty: true

  - type: size_limit
    description: "Distribution size < 200 MB"
    command: 'du -sm {dist_dir} | cut -f1'
    stdout_lt: 200

  - type: agent_count
    description: "At least 12 agent files present"
    command: 'ls {dist_dir}/hermes-core/agents/*.md 2>/dev/null | wc -l'
    stdout_ge: 12

  - type: skill_categories
    description: "At least 22 skill categories present"
    command: 'ls -d {dist_dir}/hermes-core/skills/*/ 2>/dev/null | wc -l'
    stdout_ge: 22

  - type: manifest_internal
    description: "No unexpected files in hermes-core/"
    command: 'find {dist_dir}/hermes-core -type f ! -name *.md ! -name *.py ! -name *.json ! -name *.template ! -name *.yaml ! -name .manifest_hash ! -name .codemes_version ! -name VERSION'
    stdout_empty: true
```

## Usage

```bash
# Build public distribution
./pack.sh --variant public --target ./dist

# Build personal distribution
./pack.sh --variant pers --target ./dist

# Install on target machine
./install.sh --source ./dist --target ~/.hermes

# Dry-run (see what would happen)
./install.sh --source ./dist --target ~/.hermes --dry-run

# Upgrade existing installation
./install.sh --source ./dist --target ~/.hermes --upgrade
```
