# Portable Deployment Package — Concrete Example

> Built for Hermes Agent (v0.16.0), July 2026
> Source: `/home/user/dev/hermes_portable/` (70 files, 580 KB)

This is a real-world example of the 3-pillar portable deployment framework. Use as a template for any architecture-as-code project that needs to deploy on clean machines (ARM64 or x86_64, online or air-gapped).

## Package Structure

```
project/
├── README.md                  ← Complete deployment guide with checklists
│
├── config/                    ← PILLAR 1: CONFIG
│   ├── config.template.yaml   ← ${VAR} markers for every config value
│   ├── env.template           ← All env vars with defaults
│   ├── persona.template.md    ← Portable persona (no hardcoded infra)
│   └── env-var-resolver.py    ← Resolves ${VAR} in config files
│
├── docker/                    ← PILLAR 3: INFRA (multi-arch)
│   ├── docker-compose.yml     ← Default (arm64 assumed)
│   ├── docker-compose.neo4j.yml
│   ├── docker-compose.litellm.yml
│   ├── docker-compose.voice.yml
│   ├── docker-compose.offline.yml  ← Override for air-gapped
│   ├── docker-compose.x86.yml      ← Override for amd64
│   └── .env.docker
│
├── scripts/                   ← PILLAR 2+3: STATE + INFRA
│   ├── deploy.sh              ← Full orchestrator (--arch, --mode, --offline, --yes)
│   ├── deploy-offline.sh      ← Air-gapped deploy
│   ├── deploy-verify.sh       ← GATE 3: post-deploy
│   ├── check-hardware.sh      ← Detects arch/GPU/disk/RAM/Python/Docker
│   ├── path-rewrite.py        ← Fixes /home/olduser → ${HERMES_HOME}
│   ├── env-var-resolver.py    ← Resolves ${VAR}
│   ├── state-export.sh        ← Docker volumes → tar.gz
│   ├── state-import.sh        ← tar.gz → Docker volumes
│   ├── migrate-state.py       ← Rewrite paths in SQLite state DBs
│   ├── setup-firewall.sh      ← UFW rules for Docker→host ports
│   ├── setup-cron.sh          ← Restore cron jobs
│   ├── skills-migrate.sh      ← Copy + remap skills
│   ├── knowledge-graph-rebuild.py ← Rebuild Neo4j from portable KG
│   └── litellm-config-generator.py ← Generate LiteLLM config from .env
│
├── architecture/              ← C4 + D2 + ADRs + fitness functions
│   ├── c4-level1-context.d2   ← System Context
│   ├── c4-level2-container.d2 ← Containers
│   ├── c4-level3-component.d2 ← Components
│   ├── c4-level4-code.d2      ← Code-level
│   ├── d2-diagrams/           ← 9 supplementary diagrams
│   ├── adr/                   ← 11 ADRs
│   ├── drift-report.md
│   ├── fitness-functions/     ← 6 automated checks
│   └── import-linter/         ← Layering contracts
│
├── models/
│   ├── README.md              ← Model setup guide
│   ├── model-config.template.yaml ← LiteLLM routing config
│   └── start-llama.sh         ← Portable llama.cpp server
│
├── offline/                   ← Air-gapped assets
│   ├── README.md
│   ├── requirements.frozen.txt
│   ├── check-offline.sh       ← GATE 1: pre-deploy check (34 tests)
│   ├── pip-packages/          ← Pre-built wheels (populate before deploy)
│   └── docker-images/         ← Pre-saved images (populate before deploy)
│
└── verify/
    ├── test-offline.sh        ← iptables-based offline isolation test
    ├── test-deployment.sh     ← End-to-end smoke test
    └── test-config.sh         ← Config/YAML/Docker compose validation
```

## Key Script Patterns

### deploy.sh — Full Orchestrator (301 lines)

```bash
# Entry point. Accepts:
./deploy.sh --arch arm64|x86_64 --mode A|B --offline --yes

# Flow:
#   1. Source .env
#   2. Run check-hardware.sh matching --arch
#   3. Create ~/.hermes/ directory structure
#   4. Resolve config.template.yaml → config.yaml via env-var-resolver
#   5. Start Docker containers (appropriate compose files)
#   6. Run setup-firewall.sh
#   7. Run skills-migrate.sh
#   8. Run setup-cron.sh
#   9. Run deploy-verify.sh
```

### check-offline.sh — Pre-Deploy Gate (34 checks)

```bash
# Runs 34 tests grouped by category:
#   Package Structure   (7 checks)
#   Config Files        (3 checks)
#   Docker Files        (5 checks)
#   Scripts             (14 checks)
#   Verify Scripts      (3 checks)
#   Architecture Docs   (1 check)
#   Offline Assets      (2 warnings)
#
# Output: X passed, Y failed, Z warnings
# Exit code: 0 = all pass, 1 = any fail
```

### path-rewrite.py — Hardcoded Path Fixer (298 lines)

```python
# Takes --old-prefix, --new-template or --env-var
# Scans recursively, respects .gitignore, detects binary files
# Dry-run mode (default): report only
# Rewrite mode (--rewrite): apply changes
```

### migrate-state.py — SQLite Path Migration (253 lines)

```python
# Scans TEXT columns in SQLite databases
# Finds /home/olduser patterns, rewrites with new prefix
# Handles WAL checkpoint before and after
# Supports: --db-path, --table, --column, --dry-run
```

## Deployment Flow (One Command)

```bash
./scripts/deploy.sh --arch arm64 --mode B --yes
# └→ check-hardware.sh         (arch, GPU, disk, RAM, Python, Docker)
# └→ env-var-resolver.py       (resolve ${VAR} in config.yaml)
# └→ docker compose up -d      (main + arch override)
# └→ setup-firewall.sh         (ports 8642,8643,8647,4000,7474,7687)
# └→ skills-migrate.sh         (copy + path-rewrite skills)
# └→ setup-cron.sh             (restore cron jobs)
# └→ deploy-verify.sh          (endpoints, containers, skills, delegation)
# └→ Output: PASS/FAIL report
```

## Verification Suite (3 Gates)

| Gate | Script | When | What |
|------|--------|------|------|
| Pre-deploy | `offline/check-offline.sh` | Before deploy | File existence, YAML validity, Python syntax, Docker compose, all assets |
| In-deploy | Embedded in `deploy.sh` | During deploy | Prerequisites match, config parses, containers start, volumes created |
| Post-deploy | `scripts/deploy-verify.sh` | After deploy | Endpoint health, docker ps, skill loading, delegation test, firewall |

## Offline Deployment

For machines with zero internet access:

```bash
# On a connected machine, prepare offline assets:
pip download -r requirements.txt -d offline/pip-packages-arm64/
docker pull ghcr.io/berriai/litellm:latest
docker save ghcr.io/berriai/litellm:latest | gzip > offline/docker-images/litellm.tar.gz
# ... repeat for all images

# Transfer the full package directory via USB

# On target machine:
./scripts/deploy-offline.sh
# Loads images from tar.gz, installs pip from local wheels,
# starts llama-server from pre-built binary.
```

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| docker-compose overrides > separate files | Avoids duplicating 27 service definitions for each arch |
| env-var template > hardcoded config | Single config.yaml works on any machine after env-var resolution |
| Python for path/state tools > bash | SQLite interaction, regex, argparse — Python is more reliable |
| 3-gate verification > single check | Catches failures at earliest possible point |
| D2 > Mermaid for architecture | Layout engines, layering, cleaner DSL for complex diagrams |
| All scripts idempotent | Safe to rerun; deploy is "converge to desired state" |
