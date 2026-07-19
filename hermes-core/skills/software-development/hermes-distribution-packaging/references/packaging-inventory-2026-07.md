# Complete Packaging Inventory — July 2026

Full audit of `~/.hermes/` (1.1 GB total) conducted 2026-07-06.
Breaks down every component into: **INCLUDE** (valuable, sanitized), **EXCLUDE** (personal/secret), **EXCLUDE** (runtime state).

## Tier 1 — Core agents & infrastructure (MUST include)

| Component | Live size | Contents | Notes |
|-----------|-----------|----------|-------|
| `agents/` | 1.2M | 31 files: general, build, plan, plan2, plan3, architect, developer, techlead, tester, security, deployment, system-analyst, researcher, requirements-agent + 19 newer: aflow-orchestrator, auditor, claw-orchestrator, critic, deep-plan-researcher, dev-creative/dev-maverick/dev-pragmatic/dev-skeptic, devops-engineer, enterprise-architect, idea-generator, jidoka-evaluator, knowledge-curator, observer-orchestrator, project-architect, requirements-interviewer, research/*, review/* | codemes_1 had only 12; her2code had only 14 |
| `skills/` | 14M | 24 categories (EXCLUDING `pavel-environment`!): analytics, apple, autonomous-ai-agents, creative, data-science, deployment, devops, dogfood, email, github, hermes-desktop-extension, hermes-docker-build, media, messaging-debugging, mlops, note-taking, productivity, red-teaming, research, security, smart-home, social-media, software-development, yuanbao | `pavel-environment` is PERSONAL — exclude always |
| `hooks/` | 100K | 8 hooks: enforce-workspace.py, inject-agents-md.py, skill-router.py, observer-hook/, preflight-check.py, post-edit-verify.py, inject-verify-feedback.py, curator_session_analysis.py | Was COMPLETELY MISSING from codemes_1 |
| `scripts/` | 452K | 30 scripts: agent_registry.py, capability_gate.py, claw-audit/discovery/process.py, curator-daily.sh, embed_skills.py, knowledge-curator-ingest*.py, observer_daemon.py, observer_worker*.py, orchestrator_gate.py, quality_gate_runner.py, research_*.py, topology_ingest.py, launch-docker-gui.sh | Was COMPLETELY MISSING from codemes_1 |
| `gates/` | 536K | Quality gates system: all_gates.yaml, base.py, config.yaml, registry.py, runner.py, passport.py, history_db.py, deploy/, hooks/ | Was COMPLETELY MISSING from codemes_1 |

## Tier 2 — Plugins & auxiliary infrastructure (MUST include, sanitized)

| Component | Live size | Notes |
|-----------|-----------|-------|
| `plugins/claw-neo4j/` | 156K (without node_modules!) | **MUST exclude `node_modules/`** — 45M → 156K. Keep: mcp-server.mjs, search.js, graph/, queries/, package.json |
| `plugins/hermes-opencode/` | 32K | OpenCode+ integration |
| `plugins/clarify-gate/` | 28K | Clarify gate plugin |
| `opencode_claw/` | 972K | Claw agent config: diagrams, schemas. **Exclude:** .compactor/log.jsonl, registry/, sessions/ |
| `skill-bundles/` | 12K | build.yaml, security.yaml |
| `schemas/` | 16K | research-output-v1.json |
| `cron/` | — | **Job definitions ONLY.** `cron/output/` is personal data — EXCLUDE |
| `AGENTS.md` | 15K | **MUST sanitize:** remove /home/user/, IP <YOUR_VPS_IP>, changeme, ADB paths, voice proxy paths |
| `SOUL.md` | 537B | Neutral persona template, OK as-is |
| `shell-hooks-allowlist.json` | 1.3K | Command allowlist |
| `compose.neo4j.yml` | 668B | Docker compose for Neo4j |

## Tier 3 — Templates (sanitized, CHANGEME placeholders)

| Component | Rule |
|-----------|------|
| `config.yaml.template` | All `api_key: "CHANGEME"`, remove /home/user/ paths |
| `.env.template` | Variable names only with `***`: DEEPSEEK_API_KEY=***, OPENAI_API_KEY=***, etc. |
| `persona.md` (template) | Remove `agent.default: plan2` → `CHANGEME`. Remove personal details. |

## EXCLUDE — Secrets (key-free by design)

| File | Size | What |
|------|------|------|
| `.env` | 28K | REAL KEYS: DEEPSEEK_API_KEY, KIMI_API_KEY, OPENAI_API_KEY, API_SERVER_KEY |
| `.sudo_pass` | 4K | **ACTUAL SUDO PASSWORD!!!** Critical blind spot |
| `auth.json` | 4K | Auth tokens |
| `config.yaml` | 12K | Config with real settings → only .template |
| `profiles/1/.env` | — | Keys in profile! |
| `profiles/1/auth.lock` | — | |
| `profiles/1/cache/` | — | Model catalog cache |
| `gateway_state.json` | — | Runtime state |

## EXCLUDE — Personal data ("персухи")

| File/Dir | What |
|----------|------|
| `memories/MEMORY.md` | Personal memory: paths, IPs, keys, phone ID, Telegram, VPS |
| `memories/USER.md` | User profile: name, habits, VPS IP, Telegram, device info |
| `skills/pavel-environment/` | Machine specs: ARM64, RAM, paths, OpenCode+ details |
| `persona.md` (live) | agent.default: plan2 + personal details |
| `auditor_memory.md` | Auditor memory |
| `observer_queue.jsonl` | Observer state |
| `observer_state.db` | Observer DB |
| `observations/`, `.observations/` | Observations |
| `plans/` | Personal plans |
| `reports/` | Reports |
| `paper_queue/` | Research papers |
| `channel_directory.json` | Telegram chat_id |
| `pairing/` | Pairing data |
| `cron/output/` | Cron execution results |
| `.observer_last_check` | Observer timestamp |

## EXCLUDE — Runtime state (garbage)

| File | Size | Reason |
|------|------|--------|
| `state.db` | 323M | Sessions DB |
| `state.db.bak.*` | 860M | Backups |
| `state.db-shm`, `state.db-wal` | — | SQLite WAL |
| `audit.db`, `metrics.db`, `kanban.db`, `response_store.db` | — | Runtime DBs |
| `sessions/` | 14 files | Session files |
| `logs/` | 38M | Logs |
| `cache/` | 1.9M | Cache |
| `backups/`, `sandboxes/` | — | Backups/sandboxes |
| `image_cache/`, `audio_cache/` | — | Media cache |
| `models_dev_cache.json` | 2.9M | Model cache |
| `provider_models_cache.json` | — | Cache |
| `ollama_cloud_models_cache.json` | — | Cache |
| `config.yaml.bak.*`, `.env.bak-*` | — | Config backups |
| `agents.backup-*/` | — | Stale backup |
| `desktop.pid`, `processes.json` | — | PID files |
| `.skills_prompt_snapshot.json` | — | Snapshot |
| `state-snapshots/` | — | Snapshots |
| `platforms/` | — | May contain tokens |
| `home/` | — | Nested home (another profile) |
| `hermes-agent/` | — | Installation itself → submodule in her2code |
| `bin/`, `lsp/`, `.local/`, `skins/`, `workspace/` | — | Local data |

## Estimated clean dist size

```
Tier 1+2+3:  ~17.5M  (agents 1.2M + skills 14M + hooks 100K + scripts 452K + gates 536K + plugins 216K + opencode_claw 972K + misc ~50K)
Excluded:    ~1.2GB  (state.db + backups + logs + cache + secrets + personal)
```

## codemes_1 vs live — gap analysis (2026-07-06)

| Component | codemes_1 | Live | Gap |
|-----------|-----------|------|-----|
| agents/ | 12 | 31 | **19 missing** |
| hooks/ | 0 | 8 | **all missing** |
| scripts/ | 0 | 30 | **all missing** |
| gates/ | 0 | full system | **all missing** |
| memories/ | INCLUDED (leak!) | should be excluded | **personal data leaked** |
| pavel-environment | INCLUDED (leak!) | should be excluded | **personal data leaked** |
| AGENTS.md | INCLUDED with paths | should be sanitized | **paths/IPs leaked** |
