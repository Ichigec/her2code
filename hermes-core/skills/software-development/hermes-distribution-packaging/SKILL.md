---
name: hermes-distribution-packaging
description: "Package Hermes Agent into a sanitized, installable distribution — manifest-driven packaging with pack.sh/install.sh pipeline, secret sanitization, and first-run onboarding."
version: 1.0.0
author: Hermes Agent + Pavel
license: MIT
metadata:
  hermes:
    tags: [distribution, packaging, deployment, sanitization, onboarding, manifest]
    related_skills: [hermes-agent, orchestration-cycle, multi-agent-orchestration, hermes-migration]
---

# Hermes Distribution Packaging

Package a sanitized Hermes Agent installation into a distributable archive.
Excludes secrets, databases, caches, logs, and development artifacts. Produces
a clean directory tree installable via `install.sh`.

## 🔴 IRON RULES (from <SESSION_ID> session)

1. **NEVER insert real API keys** into distribution files. Only `.env.example` with placeholders (`***`, `<YOUR_KEY>`).
2. **NEVER push to GitHub without full smoke test**: docker compose up -> health -> models -> chat -> down.
3. **`.env` MUST be in `.gitignore`**. User creates it from `.env.example`.
4. **Test BEFORE declaring success**. Pavel rejects claims without verified evidence.
5. **Credentials in code = BLOCKER**. Check Android source, Python scripts, compose files for hardcoded tokens (`<YOUR_HARDCODED_TOKEN>...`, `changeme` defaults).

## When to use

- User asks to "упаковать Hermes в дистрибутив" или "сделать portable версию"
- Preparing Hermes for another developer or machine
- Creating a public/open-source variant of a personal Hermes setup
- Building a `codemes_*` project for distribution
- User asks for "глубокий анализ" or "санитизация" or "выкладывание в GitHub"
- User asks "запустить в Docker" or "развернуть стек" or needs a `docker-compose.yml`
- User asks "как опубликовать Hermes" or "подготовить к open-source"

## ⚠️ Full-stack inclusion (CRITICAL)

Hermes is more than `~/.hermes/`. A complete distribution MUST also include
these components (code only, no data):

| Component | Source | Destination in dist |
|-----------|--------|-------------------|
| **Education Graph MCP** | `~/cursor/first/graph_tool/` | `config/mcp/education-graph/` |
| **Claw Agent** | `~/cursor/opencode+/opencode_claw/` | `config/claw-agent/` |
| **Android Client** | `~/dev/Opencode/` | `opencode-android/` |
| **OpenCode+** | `~/cursor/opencode+/` | `opencode-plus/` |
| **LLM Infrastructure Stack** | `~/cursor/first/` + `~/dev/llama/` | `llm-stack/` |

**Pitfall:** The first sanitization pass typically copies only `~/.hermes/`
and misses `~/cursor/` and `~/dev/` components. The user WILL notice and
ask for a second pass. Do it proactively.

### LLM Infrastructure Stack (CRITICAL, added 2026-07-06)

The LLM infrastructure is a 4-component stack that must be packaged as
config/scripts/templates only — **never** model weights, source repos, or
runtime data. All config lives under `~/cursor/first/` (Docker stack) and
`~/dev/llama/` (host-side llama.cpp launcher).

| Component | Key files to INCLUDE | What to EXCLUDE |
|-----------|---------------------|-----------------|
| **Neo4j** | `compose.neo4j.yml`, `plugins/claw-neo4j/` (without node_modules), graph dump via `neo4j-admin database dump` | Data volumes (runtime), real password in `.env` |
| **LiteLLM** | `docker/litellm/config.yaml` (510 lines, 35+ aliases), `compose.phoenix.yml`, `.env.example`, `.env.llamacpp.example`, `docker/openai-stack-relay/`, `compose.agents-mesh.yml`, `docker/agent-mesh-common/`, `docker/agent-registry/`, `docker/skills-manager/`, `docker/clawcode-adapter/`, `docker/openhands-adapter/`, `docker/opencode-adapter/`, `scripts/litellm-*.sh`, `docs/litellm-clients.md` | Real `.env` (keys), `litellm-pg-volume` (runtime DB) |
| **llama.cpp** | `dev/llama/start-llama.sh`, `docker/llamacpp/Dockerfile`, `compose.llama.yml`, `.env.llamacpp.example`, `docs/llama-cpp-host.md`, `dev/llama/plan3-architecture.md`, `dev/llama/roles.md`, `dev/llama/APEX-ANALYSIS.md` | Model GGUF files (77G!), llama.cpp source repo (1.3G, rebuilt from Dockerfile) |
| **Phoenix** | `compose.phoenix.yml` (shared with LiteLLM), `opencode+/connect-phoenix.sh`, `.env.example` OTEL section | Phoenix data volumes (trace history, not needed for fresh deploy) |

**Sanitization rules for LLM stack:**

| File | Replace | With |
|------|---------|------|
| `start-llama.sh` | `/home/user/dev/llama.cpp`, `${HOME}/models/*.gguf` | `${HOME}/dev/llama.cpp`, `# CHANGEME: path to model GGUF` |
| `.env.llamacpp.example` | `${HOME}/.lmstudio/models/...` | `# CHANGEME: path to model` |
| `compose.llama.yml` | `CCSSNE/tvall43-Qwen3.6...` | `${LLAMA_CPP_MODEL_PATH}` |
| `compose.neo4j.yml` | `${NEO4J_PASSWORD:?Set NEO4J_PASSWORD}` | `${NEO4J_PASSWORD:?Set NEO4J_PASSWORD}` |
| `connect-phoenix.sh` | Hardcoded `${LITE...al}` key | `${LITELLM_API_KEY}` |

**Good news:** `docker/litellm/config.yaml` is ALREADY safe — all API keys
use `os.environ/VAR_NAME` indirection, no hardcoded secrets. The agent-mesh
adapter keys (`CLAWCODE_ADAPTER_API_KEY` etc.) also use `os.environ/`.

**What the distribution does NOT include (by design):**
- Model GGUF files (77G) — documented in `.env.llamacpp.example` with model names/quant levels
- llama.cpp source repo (1.3G) — rebuilt from `docker/llamacpp/Dockerfile`
- Phoenix/Neo4j data volumes — created fresh on `docker compose up`
- Real `.env` — user copies from `.env.example` and fills keys

See `references/llm-infrastructure-inventory.md` for the full per-component
file inventory, architecture diagram, and sanitization checklist.

### Two-Mode Distribution Pattern (added 2026-07-06, codewar session)

When a distribution supports both local GPU inference and remote API
endpoints, provide **two install paths** with shared infrastructure:

| Mode | LLM Source | Requires GPU | LiteLLM config | Install script |
|------|-----------|:---:|----------------|----------------|
| **A (Local)** | llama.cpp + GGUF models | ✅ | `config.yaml` (aliases → `:8101-8103`) | `setup-llama.sh` + `setup-ufw.sh` |
| **B (Remote)** | OpenAI-compatible endpoint | ❌ | `config.openai.yaml` (alias → `${OPENAI_API_BASE}`) | Direct `.env` configuration |

**Architecture:**
```
Clients → Hermes Agent (:8643) → LiteLLM (:4000) → [Mode A: llama-server :8101-8103 | Mode B: external API]
                                          ↓
                                     Phoenix (:6006) ← tracing
                                     Neo4j (:7474)  ← knowledge graphs
```

**Startup order (CRITICAL):**

The LLM stack has dependencies that dictate a strict startup sequence. LiteLLM
depends on Phoenix (for tracing callbacks); Hermes depends on LiteLLM; llama-server
is independent but must be running before LiteLLM can route to it.

```
1. Neo4j          docker compose -f compose.neo4j.yml up -d          :7474/:7687
2. Phoenix        docker compose -f compose.phoenix.yml up -d phoenix :6006/:4317
3. LiteLLM        docker compose -f compose.phoenix.yml up -d litellm :4000  (depends_on: phoenix)
4. llama-server   ./start-llama.sh start                               :8101-8103 (host-side, Mode A only)
5. Hermes Agent   hermes gateway run (or desktop app)                  connects to LiteLLM :4000
```

Phoenix traces flow: LiteLLM `success_callback: ["arize_phoenix"]` → Phoenix :6006.
Hermes → Neo4j via MCP plugin `claw-neo4j`. Hermes → local models via `providers.local` → LiteLLM :4000.

**Key files for two-mode support:**
- `install/install.sh` — main entry, `--mode A` or `--mode B` flag
- `llm-stack/docker/litellm/config.yaml` — Mode A: 35+ aliases to `host.docker.internal:8101-8103`
- `llm-stack/docker/litellm/config.openai.yaml` — Mode B: single alias to `os.environ/OPENAI_API_BASE`
- `llm-stack/env/.env.example` — Mode A env template
- `llm-stack/env/.env.openai.example` — Mode B env template
- `requirements-mode-a.txt` / `requirements-mode-b.txt` — full dependency lists per mode

**Pitfall — `config.openai.yaml` must use `os.environ/` indirection:**
```yaml
# ✅ Correct — env vars resolved at runtime
api_base: "os.environ/OPENAI_API_BASE"
api_key: "os.environ/OPENAI_API_KEY"

# ❌ Wrong — hardcoded in config, leaks into git
api_base: "https://api.openai.com/v1"
api_key: "sk-..."
```

### Docker Image Packaging for Offline Install (added 2026-07-06)

When the target machine may not have internet access, package Docker images
as tar files alongside the distribution:

```bash
# Save all images (pull + locally built)
docker save neo4j:5-community -o docker-images/neo4j-5-community.tar
docker save arizephoenix/phoenix:latest -o docker-images/phoenix-latest.tar
# ... etc for all images

# Load on target machine
for f in docker-images/*.tar; do docker load -i "$f"; done
```

**Must include BOTH:**
1. **Pull images** — `neo4j:5-community`, `arizephoenix/phoenix:latest`, `ghcr.io/berriai/litellm-database:v1.83.7-stable`, `postgres:16-alpine`, `python:3.12-*`, `alpine:latest`, `nvidia/cuda:*`
2. **Locally-built images** — `voice-assistant-openai-stack-relay:local`, `voice-assistant-clawcode-adapter:local`, etc. (these CANNOT be re-pulled, only rebuilt from Dockerfile)

**Pitfall — `docker save` image name must match exactly:**
- `python:3.12-slim-bookworm` → NOT `python:3.12-slim` (tag mismatch → `reference does not exist`)
- Check with `docker images` before saving

**Pitfall — CUDA images may not be present on dev machine:**
CUDA devel/runtime images may need `docker pull` before `docker save`. They're
large (~3.5G devel, ~900M runtime) and may not be cached if llama.cpp was built
on bare metal instead of in Docker.

**Provide `install/load-docker-images.sh` script** that:
1. Finds `docker-images/` directory (relative to dist or configurable)
2. Loops `docker load -i` over all `.tar` files
3. Reports success/failure count
4. Suggests verification command (`docker images | grep ...`)

### Requirements Files Pattern (added 2026-07-06)

Provide `requirements-mode-a.txt` and `requirements-mode-b.txt` in the dist
root, listing ALL external dependencies with sizes:

```
# Format:
# <path or image name>           # <size>  <comment>
codewar-20260706.tar.gz          # 42 MB
~/models/Nex-N2-mini.gguf        # 33 GB   coding model
neo4j:5-community                # 607 MB  Docker image
```

**Must include:**
- Archive itself
- All GGUF model files (Mode A only) with exact filenames and sizes
- All Docker images (pull + locally built) with exact `image:tag` names
- Hermes Agent CLI (`pip install hermes-agent`)
- System packages (`apt install ...`)
- NVIDIA Container Toolkit (NOT drivers — those are system-specific)

**Must NOT include:**
- NVIDIA GPU drivers (system-specific, kernel-dependent)
- CUDA toolkit (installed via Docker images or system packages)
dump technique, two-mode distribution pattern, Docker image offline export,
and PII test script self-exclusion fix.

### Two-mode distribution pattern (Mode A vs Mode B)

A distribution can support two installation paths with a single codebase:

- **Mode A (Local):** llama.cpp + GPU models. Requires NVIDIA GPU, CUDA, 80GB+ disk. LiteLLM `config.yaml` points to `http://host.docker.internal:8101-8103/v1`.
- **Mode B (Remote):** OpenAI-compatible endpoint. No GPU needed. LiteLLM `config.openai.yaml` points to `${OPENAI_API_BASE}` + `${OPENAI_API_KEY}`.

`install.sh --mode A|B` selects the config. Create `requirements-mode-a.txt` and `requirements-mode-b.txt` listing everything the user needs (archive, models, Docker images, system packages). See the reference file for the full pattern.

### Docker image offline export

For air-gapped/USB installs, `docker save` all images to `.tar` files, then `docker load` on the target. CUDA devel image alone is 6.1G — run in background. See reference file for the full script.

### Neo4j Community Edition dump

`docker exec neo4j neo4j-admin database dump` FAILS ("database is in use"). Community Edition does NOT support `STOP DATABASE`. Working technique: `docker stop neo4j` → temporary container with volume → dump → `docker start neo4j`. See reference file for full script and pitfalls.

**What to exclude from each:**
- Education graph: `venv/`, `node_modules/`, trained graph data (Neo4j)
- Claw agent: `.compactor/log.jsonl`, `registry/`, `sessions/`, `summaries/`
- Android: `build/`, `.gradle/`, `*.apk`
- OpenCode+: `.env` files with real keys, `.compactor/` data

### Profile path discovery (CRITICAL, 2026-07-14)

**Problem:** When doing inventory of `~/.hermes/`, agents may look for skills/agents/hooks
under `profiles/` subdirectories and miss them. The actual structure is split:

| What | Where | Notes |
|------|-------|-------|
| Skills, agents, hooks, scripts, gates, plugins | **`~/.hermes/`** (TOP level) | Always here, never under profiles/ |
| Profile-specific config.yaml, .env | `~/.hermes/home/.hermes/profiles/<name>/` | e.g. `profiles/codewar/config.yaml` |
| Profile-specific skills/hooks/plugins | `~/.hermes/home/.hermes/profiles/<name>/` | May have their OWN subset, but main set is at top |

**How to verify the active HERMES_HOME:**
```bash
echo $HERMES_HOME   # usually ~/.hermes
# Skills are at $HERMES_HOME/skills/, NOT $HERMES_HOME/home/.hermes/profiles/X/skills/
```

**Detection:** `find ~/.hermes/ -name 'SKILL.md' -maxdepth 5 | head -3` — if 0 results
at depth 2, skills are NOT where you think. Try `find ~/.hermes/skills/ -name 'SKILL.md'`
directly. The `home/.hermes/profiles/<name>/` subtree is for config/secrets, not skills.

**Previous inventory (July 6) used `profiles/1/` — actual profile name is environment-specific**
(e.g. `codewar`). Never assume the profile directory name; always `ls ~/.hermes/home/.hermes/profiles/`
to discover it.

### Reuse from prior portable build (2026-07-14)

When creating a new portable version (v2 → v3) and the Hermes version hasn't changed,
**copy Docker images and GUI binaries from the prior USB directory** instead of rebuilding:

```bash
# Check if versions match
hermes --version                              # current host version
docker inspect hermes-agent:latest --format '{{.Created}}'  # image build date

# If same version, copy from prior build (saves ~2-3 hours):
cp -r "/media/pavel/One Touch/hermes_portable_v2/docker/"* "/media/pavel/One Touch/hermes_portable_v3/docker/"
cp -r "/media/pavel/One Touch/hermes_portable_v2/gui-arm64" "/media/pavel/One Touch/hermes_portable_v3/"
cp -r "/media/pavel/One Touch/hermes_portable_v2/gui-x64" "/media/pavel/One Touch/hermes_portable_v3/"
```

Only rebuild Docker images or GUI binaries if:
- Hermes version changed (check `hermes --version` vs Docker image `--format '{{.Created}}'`)
- Codebase has significant local commits not in the prior image
- GUI binary for the target architecture is missing from the prior build

### Incomplete `~/.hermes/` coverage (CRITICAL, found 2026-07-06)

**Problem:** The first packaging pass (codemes_1, 2026-06-14) copied only `agents/`, `skills/`, `plugins/`, `cron/`, `templates/` but **MISSED** three critical component directories that live inside `~/.hermes/`:

| Component | Files | codemes_1 | her2code | Live |
|-----------|-------|-----------|----------|------|
| `hooks/` | 8 hooks (enforce-workspace, inject-agents-md, skill-router, observer-hook, preflight-check, post-edit-verify, inject-verify-feedback, curator-session-analysis) | ❌ missing | ❌ missing | ✅ 100K |
| `scripts/` | 30 scripts (agent_registry, capability_gate, claw-audit/discovery/process, curator-daily, embed_skills, knowledge-curator-ingest, observer_daemon, observer_worker, orchestrator_gate, quality_gate_runner, research_*, topology_ingest, launch-docker-gui) | ❌ missing | ❌ missing | ✅ 452K |
| `gates/` | Quality gates system (all_gates.yaml, base.py, config.yaml, registry.py, runner.py, passport.py, history_db.py, deploy/, hooks/) | ❌ missing | ❌ missing | ✅ 536K |

Additionally, **agent coverage was incomplete**: codemes_1 had 12 of 31 live agents (missing 19 newer agents including aflow-orchestrator, auditor, claw-orchestrator, critic, deep-plan-researcher, dev-creative/maverick/pragmatic/skeptic, devops-engineer, enterprise-architect, idea-generator, jidoka-evaluator, knowledge-curator, observer-orchestrator, project-architect, requirements-interviewer, research/*, review/*).

**Fix:** Before packaging, generate a complete inventory of `~/.hermes/` and diff against the manifest's include rules. Any component directory with >5 files that is NOT in the manifest is a likely omission. See `references/packaging-inventory-2026-07.md` for the canonical inventory.

### Public variant leaking personal data (CRITICAL, found 2026-07-06)

**Problem:** codemes_1 was packaged with `variant: public` which claims "no memory files, clean". However, the actual `dist/` contained:
- `memories/MEMORY.md` (16K) — real paths, IPs, Neo4j password, phone ID, Telegram info, VPS details
- `memories/USER.md` (3.4K) — user name, habits, VPS IP, Telegram, device info
- `skills/pavel-environment/` — machine specs, all local paths, OpenCode+ details
- `AGENTS.md` with unsanitized `/home/user/` paths, `changeme` passwords, ADB paths

**Root cause:** The `--variant public` flag in pack.sh did not actually exclude `memories/` or `pavel-environment`. The variant system was declarative but not enforced.

**Fix:** After `pack.sh --variant public`, run mandatory post-build verification:
```bash
# MUST return 0 matches
find dist/ -path '*/memories/*' -type f
find dist/ -path '*/pavel-environment/*' -type f
find dist/ -name '.sudo_pass' -o -name '.env' -o -name 'auth.json'
grep -rP '/home/user/' dist/
grep -rP '64\.188\.64\.52' dist/
```

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

### Docker deployment (for distribution target)

When the sanitized `her2code/` needs to be runnable via `docker compose up`, use
the bundled templates:

| Template | Role |
|----------|------|
| `.env.example` | Docker env vars template (committed to Git) |
| `.gitignore` | Excludes `.env` (real keys) from Git |
| `DOCKER.md` | Quick-start instructions |

**🔴 CRITICAL: NEVER include real API keys in the distribution.** The `.env` file
with real keys is excluded via `.gitignore`. Users copy `.env.example` → `.env`
and fill in their own keys. This is a hard constraint — Pavel explicitly requires
the distribution to be key-free.

```bash
# In her2code/:
cp .env.example .env && nano .env    # add real API keys (OPENROUTER_API_KEY, etc.)
docker compose up -d                        # start stack
curl http://localhost:18648/health          # verify
```

**`.env.example` template:**
```bash
# Copy: cp .env.example .env
# Edit: nano .env
# NEVER commit .env to Git!
OPENROUTER_API_KEY=*** DEEPSEEK_API_KEY=*** API_SERVER_KEY=*** API_SERVER_KEY (generate: openssl rand -hex 32)
GATEWAY_ALLOW_ALL_USERS=true
HERMES_DISABLE_MESSAGING=1
```

**`.gitignore`:**
```
# NEVER commit real keys
.env
```

**⚠️ НИКОГДА не вставлять реальные API-ключи в файлы дистрибутива.** Pavel: дистрибутив должен быть key-free. Только `.env.example` с плейсхолдерами. `.gitignore` исключает `.env`. Пользователь создаёт `.env` сам из `.env.example`.
(`ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie@sha256:...`). This SHA may be
unavailable on the target machine. If `docker compose build` fails, update the
SHA in `hermes-agent/Dockerfile` to the latest from `ghcr.io/astral-sh/uv`.

**Pitfall — Docker image defaults to OpenRouter:** The Docker image's built-in
config uses `model.default: anthropic/claude-opus-4.6` with `provider: auto`
which resolves to `openrouter`. Users MUST set `OPENROUTER_API_KEY` in `.env`,
not just `DEEPSEEK_API_KEY`. Without it: HTTP 401 `Missing Authentication header`.

**Pitfall — `env_file:` требует существования файла:** Docker Compose с `env_file: .env`
упадёт если `.env` не существует (а в git его нет — только `.env.example`).
Использовать `- VAR_NAME` (без `=value`) — docker compose передаст переменную из
окружения хоста, а если её нет — она будет пустой, не вызывая ошибки парсинга.

**Pitfall — `HERMES_DISABLE_MESSAGING` vs Telegram:** Даже с `=1` gateway пытается
подключиться к `api.telegram.org` (логи: `WARNING gateway.platforms.telegram_network`).
API server это не блокирует, но создаёт шум. Для чистого старта — удалить `telegram`
из `config.yaml` через entrypoint перед запуском.

**Pitfall — s6-log lock crash-loop:** Если gateway и dashboard контейнеры шарят один
volume (`/opt/data`), при рестарте gateway падает в crash-loop: `s6-log: fatal: unable
to lock /opt/data/logs/gateways/default/lock: Resource busy` → процесс уходит в
`sleep infinity`. Контейнер показывает `Up`, но не обслуживает запросы.
**Fix:** (1) использовать раздельные volumes для gateway и dashboard, или (2)
добавить `rm -rf /opt/data/logs/gateways/` в entrypoint перед запуском gateway.

**Pitfall — API_SERVER_KEY rejects placeholders:** Hermes explicitly refuses

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

### `.env` with real keys MUST NOT be in distribution (user-enforced)

**Problem (2026-06-20):** During her2code analysis, agent created `.env` with real
API keys from host. Pavel corrected: "Мы делали специально без ключей и перс данных
(что бы никто не мог похитить или взломать)."

**Rule:** The distribution is KEY-FREE by design. `.env` is excluded via `.gitignore`.
Only `.env.example` with placeholders (`***`) is committed. Users copy `.env.example`
→ `.env` and fill in their own keys after cloning.

**Checklist before Git push:**
```bash
# Must return 0 matches
grep -rP 'sk-proj-[A-Za-z0-9_-]{30,}' . 2>/dev/null
grep -rP 'sk-ant-api03-[A-Za-z0-9_-]{30,}' . 2>/dev/null
grep -rP '64\.188\.64\.52|95\.24\.31\.191' . 2>/dev/null
# .env must NOT be staged
git status --short | grep "A.*\.env$"  # should be empty
```

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

### Partially-hidden keys evade regex

**Problem:** Keys written as `Bearer <YOUR_HARDCODED_TOKEN>...` or `Bearer ***` (with ellipsis,
asterisks, or truncation) won't match `[A-Za-z0-9]{20,}` patterns. These appear
in skill reference files and documentation.

**Fix:** Use a broader catch-all BEFORE the strict pattern:
```bash
# Catch partial/truncated tokens first
grep -rPl 'Bearer [A-Za-z0-9+/=_.*-]{5,}' . | xargs sed -i 's|Bearer [^ ]\{5,\}|Bearer <YOUR_API_SERVER_KEY>|g'
# Then apply strict patterns for full tokens
```

### Sanitizer's own files are NOT self-cleaned

**Problem:** `sanitize.py`, `sanitize-config.yaml`, `SANITIZATION_LOG.md`, and
`Makefile` are part of the output but NOT processed by the sanitizer. They can
contain hostnames, paths, and PII values in documentation tables.

**Fix:** After running `sanitize.py`, do a separate `sed` pass on all sanitizer
artifacts:
```bash
sed -i 's|/home/\w+/|/home/user/|g' README.md SANITIZATION_LOG.md sanitize-config.yaml Makefile
sed -i 's|<YOUR_HOSTNAME>|<YOUR_HOSTNAME>|g' sanitize-config.yaml
# Replace ALL PII values in SANITIZATION_LOG.md table
sed -i 's|Bearer <YOUR_HARDCODED_TOKEN>...<YOUR_API_SERVER_KEY>|g' SANITIZATION_LOG.md
```

### SANITIZATION_LOG.md stores original PII by default

**Problem:** The sanitization log is written AFTER the main sanitization pass
and contains the ORIGINAL PII values in its documentation table. It needs a
dedicated cleaning step.

**Fix:** Run the full replacement table against SANITIZATION_LOG.md as the
LAST step before verification. See `references/sanitization-methodology.md`
for the 22-pattern verification checklist.

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

## Security Agent Monitoring (CRITICAL, user-enforced 2026-06-20)

During any distribution/sanitization cycle, spawn **2 security agents IN PARALLEL**
at Phase 0 **before any file modifications**:

| Agent | Role | Monitors |
|-------|------|----------|
| **Security Agent 1 (PII Monitor)** | `write_file`/`patch` audit | API keys, IPs, usernames, passwords, paths |
| **Security Agent 2 (SAST Auditor)** | Code security review | Hardcoded secrets, shell injection, insecure defaults |

**PII Monitor checklist** (runs after EVERY phase):
```bash
# Real API keys (MUST return 0)
grep -rP 'sk-proj-[A-Za-z0-9_-]{30,}' .
grep -rP 'sk-ant-api03-[A-Za-z0-9_-]{30,}' .
# Real IPs (MUST return 0)  
grep -rP '64\.188\.64\.52|95\.24\.31\.191|10\.4\.213\.' .
# Username in code (MUST return 0 in service files, scripts)
grep -rn 'pavel' opencode-plus/ config/ --include='*.service' --include='*.sh'
# Hardcoded passwords beyond changeme (MUST return 0)
grep -rn "'<YOUR_HARDCODED_TOKEN>\|hunter2\|s3cret" .
```

**SAST Auditor checklist** (runs on docker-compose.yml, entrypoint, shell scripts):
- Hardcoded API keys in source code (Android, Python, JS) → replace with `***`
- `network_mode: host` without security comment → document it
- `changeme` used as runtime default (not just docs) → change to `:?` or empty
- Shell injection risks in entrypoint (inline Python) → use `sed` with `set -euo pipefail`
- `env_file:` requires file to exist → use `- VAR_NAME` passthrough instead

**Pavel's rule:** distribution is KEY-FREE by design. If the agent creates `.env`
with real keys or commits real PII, the cycle is BLOCKED and the GitHub repo
must be deleted.

### PII blind spots (second-pass sanitization)

Sanitization tools commonly miss these categories:

| Blind spot | Example | Fix |
|-----------|---------|-----|
| **Systemd service files** | `User=pavel`, `Group=pavel`, `USER=pavel`, `LOGNAME=pavel` | Add `*.service` to sanitize extensions |
| **PlantUML diagrams** | `' PID: <SESSION_ID>` | Add `*.puml` to text_file_extensions |
| **Android source code** | `const val DEFAULT_API_KEY = "<YOUR_HARDCODED_TOKEN>..."` | Manual review of `SettingsDataStore.kt` |
| **Shell scripts** | `sudo -u pavel bash` | Sanitize usernames in `*.sh` |
| **Compose defaults** | `NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:?Set NEO4J_PASSWORD}` | Use `:?` forcing: `${NEO4J_PASSWORD:?Set NEO4J_PASSWORD}` |
| **`.sudo_pass`** (CRITICAL) | `SUDO_PASSWORD=<actual_password>` in `~/.hermes/.sudo_pass` | **ALWAYS exclude.** Not caught by standard secret scanners — it's not an API key format. Add to exclude_global: `.sudo_pass` |
| **`profiles/` directory** | `profiles/1/.env` (real keys), `profiles/1/auth.lock`, `profiles/1/cache/model_catalog.json` | Exclude entire `profiles/` OR sanitize: keep structure, strip `.env` and cache. Profile `.env` files contain real API keys |
| **`cron/output/`** | `cron/output/8d4dd872e4aa/2026-07-06_02-04-59.md` — personal cron results | Include `cron/` job definitions ONLY, **exclude `cron/output/`** (contains personal execution results) |
| **`pavel-environment` skill** | `skills/pavel-environment/SKILL.md` — machine specs (ARM64, 20 cores, 121 GiB RAM), all local paths, OpenCode+ details | **ALWAYS exclude** from distribution. This is user-specific environment documentation, not a reusable skill |
| **`memories/` in public variant** | `memories/MEMORY.md` (16K) + `memories/USER.md` (3.4K) — despite `variant: public` | **codemes_1 LEAKED these.** The `public` variant flag in manifest.yaml did NOT prevent inclusion. Manual verification required after pack |
| **`AGENTS.md` personal paths** | `/home/user/dev/Opencode`, venv paths, Neo4j `pass=<YOUR_NEO4J_PASSWORD>`, ADB paths, voice proxy paths | Sanitize: replace `/home/user/` → `/home/user/`, remove IP addresses, replace `changeme` defaults |
| **`persona.md` (live)** | `agent.default: plan2` + personal workflow preferences | Exclude live version, include sanitized template with `CHANGEME` |
| **`channel_directory.json`** | Telegram `chat_id: <YOUR_TELEGRAM_CHAT_ID>`, bot info | Exclude — contains real Telegram channel mapping |
| **`observer_*` files** | `observer_queue.jsonl`, `observer_state.db`, `.observer_last_check`, `observations/`, `.observations/` | Exclude — personal observer state and observation history |

| **`changeme` — use `:?` forcing, not `:-changeme` defaults**

`changeme` is acceptable in DOCUMENTATION (README, DOCKER.md) but NOT as a runtime default.
In compose files and Python scripts, force the user to set the password:

```yaml
# ❌ Silently defaults to changeme — security risk
NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:?Set NEO4J_PASSWORD}

# ✅ Fails with clear error if not set  
NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:?Set NEO4J_PASSWORD in .env}
```

```python
# ❌ Default password
auth=("neo4j", os.getenv("NEO4J_PASSWORD", "changeme"))

# ✅ Empty default — Neo4j driver will reject empty password
auth=("neo4j", os.getenv("NEO4J_PASSWORD", ""))
```

| **compose.neo4j.yml missing network reference (2026-07-06)** | Neo4j compose file must include `networks: [llm-net]` + `networks: llm-net: external: true, name: llm-stack-net`. Without it, Neo4j runs in default network and LiteLLM (in llm-stack-net) cannot reach it via container DNS. **Fix:** always add network section to every compose file in the stack. |
| **Neo4j Community cannot STOP DATABASE for dump (2026-07-06)** | `cypher-shell "STOP DATABASE neo4j"` returns `Unsupported administration command` on Community edition. `neo4j-admin database dump` fails with "database is in use". **Workaround:** (1) `docker stop neo4j`, (2) `docker run --rm -v <volume>:/data -v <dumps>:/dumps neo4j:5-community neo4j-admin database dump neo4j --to-path=/dumps`, (3) `docker start neo4j`. Must `chmod 777` the dumps directory first (container user is `neo4j` UID 7474). |
| **PII test script self-triggers (2026-07-06)** | `test-pii.sh` contains PII patterns as check strings (`'/home/user/'`, `'changeme'`, `'codemes_1'`). The grep scans find these strings inside the test script itself. **Fix:** add `--exclude=test-pii.sh` to all grep commands, or use `grep ... \| grep -v test-pii.sh`. |
| **Missing config.yaml.template (2026-07-06)** | Without `hermes-core/config.yaml.template`, Hermes creates a default config with `provider: auto` → OpenRouter. User gets 401 without `OPENROUTER_API_KEY`. **Fix:** include a template with `custom_providers` pointing to LiteLLM gateway (`api_base: http://localhost:4000/v1`). |
| **Missing load-docker-images.sh (2026-07-06)** | When packaging Docker images as tar files, users need a script to load them back. Without it, they must manually `docker load -i` 15+ files. **Fix:** include `install/load-docker-images.sh` that loops over `docker-images/*.tar`. |
| **`docker save` image name mismatch (2026-07-06)** | `docker save python:3.12-slim-bookworm` fails with `reference does not exist` if the local image is tagged `python:3.12-slim` (different tag). **Fix:** run `docker images` first to get exact tags, or `docker pull` the exact tag before saving. |
| **s6-log lock crash-loop (2026-07-07)** | gateway + dashboard контейнеры шарят один `/opt/data` volume → `s6-log: fatal: unable to lock /opt/data/logs/gateways/default/lock: Resource busy` → gateway уходит в `sleep infinity`. **Fix:** clean `logs/gateways/` перед стартом: `rm -rf ~/.hermes-docker/logs/gateways/`. В `start.sh` portable — `prepare_home()` делает это автоматически. Альтернатива: separate volumes для gateway и dashboard. |
| **`provider: custom` bare → "gateway needs setup" (2026-07-07)** | Docker config template с `provider: custom` (без суффикса имени) → `"No LLM provider configured"` на каждый запрос. Dashboard пишет "gateway needs setup". **Fix:** `provider: custom:<name>` (с суффиксом) для legacy `custom_providers` list format. v12+ `providers` dict — наоборот bare name. См. `hermes-custom-providers` pitfall table. |
| **ARM64 LiteLLM image tag (2026-07-07)** | On ARM64 targets, `ghcr.io/berriai/litellm-database:v1.83.7-stable` is amd64-only → QEMU emulation → `prisma-migrate` crashes with SIGSEGV. **Fix:** use `main-stable` tag (arm64-native). Always verify with `docker image inspect <tag> --format '{{.Architecture}}'` before `docker save`. This affects both Mode A and Mode B distributions that include LiteLLM. |
| **PORT_DASH three-way mismatch in portable distributions (2026-07-08)** | When a portable distribution has `start.sh`, `docker/.env`, `.env.example`, and `docker-compose.yml`, port defaults can drift across files. Found: `start.sh` comment says `PORT_DASH=9121`, `start.sh` default `:-9123`, `.env` says `9122`, `docker-compose.yml` says `9122`. **Impact:** running `start.sh` without `.env` → dashboard on wrong port, GUI can't connect. **CRITICAL: ports :18649/:9123 are BY DESIGN — intentionally offset from main Hermes (:18648/:9121) for parallel deployment. Do NOT "fix" by aligning to :9122 — that port collides with host daemon auto-restart.** Canonical portable value: `PORT_GW=18649`, `PORT_DASH=9123`. **Fix:** audit ALL port references: `grep -rn 'PORT_DASH\|PORT_GW\|API_SERVER_PORT' start.sh .env* docker/ config/*.yaml`. Align ALL files to :18649/:9123 — comments, defaults, .env, .env.example, docker-compose.yml healthcheck. User correction: "не надо правильных — там специально такие, чтобы не конфликтовать." Lesson: understand WHY values differ before "fixing" them. |
| **Fitness functions hardcode `/home/user` path (2026-07-08)** | All 6 files in `architecture/fitness-functions/*.py` contain `CODEBASE = Path("/home/user/.hermes/hermes-agent")` — hardcoded absolute path. **Impact:** fitness checks silently fail on any other machine. **Fix:** use `pwd.getpwuid(os.getuid()).pw_dir` — NOT `os.path.expanduser("~")` which resolves to `~/.hermes/home/` when Hermes overrides `$HOME`: `import pwd; _real_home = pwd.getpwuid(os.getuid()).pw_dir; CODEBASE = Path(os.environ.get("HERMES_CODEBASE", str(Path(_real_home) / ".hermes" / "hermes-agent")))`. The `HERMES_CODEBASE` env var allows overriding entirely. Also check ALL scripts and hooks for hardcoded `/home/user` references: `grep -rn '/home/user' scripts/ config/ architecture/`. |
| **d2 diagrams use invalid `<style>{}` syntax (2026-07-08)** | AI-generated d2 diagrams commonly use `shape_name: "Label" <style>{ fill: "#..." }` — this is **invalid d2 syntax** (any version). d2 expects `style: { fill: "..." }` as a nested block inside the shape definition. Error: `unexpected text after double quoted string` / `unexpected map termination character }`. **Impact:** ALL d2 diagrams silently fail to render; architecture docs look present but are broken. **Detection:** `grep -rl '<style>' architecture/` or `for f in architecture/**/*.d2; do d2 "$f" /tmp/test.svg 2>&1; done`. **Fix:** rewrite to valid syntax: `shape_name: "Label" { style: { fill: "#e3f2fd" } }`. **Pitfall:** use a temp file/directory for d2 compile testing, NOT `/dev/null` — multi-board diagrams (with `layers:`) attempt `mkdir` on the output path and fail with `mkdir /dev/null: not a directory` false positive. |

## Reuse existing portable artifacts (2026-07-14)

When creating a new portable version (v3 from v2, etc.), check if the
previous version's Docker images and GUI binaries are the **same Hermes
version** before rebuilding. If versions match, just copy the artifacts —
saves 30+ minutes of build time.

```bash
# Check current version
hermes --version  # e.g. v0.16.0

# Check previous portable's image age + GUI binary existence
ls -lh "/media/pavel/One Touch/hermes_portable_v2/docker/"
docker inspect hermes-agent:latest --format '{{.Created}}'

# If same version → copy instead of rebuild
cp "$V2/docker/hermes-agent-arm64.tar.gz" "$V3/docker/"
cp -rL "$V2/gui-arm64" "$V3/gui-arm64"
```

**Always verify architecture after copy:** `file gui-*/Hermes` must show the
correct ELF architecture (ARM aarch64 / x86-64).

See `references/portable-v3-packaging-pattern.md` for the full V3 structure,
automated PII sanitization pipeline, and first-run onboarding flow.

## Pre-GitHub Push Gate (CRITICAL, 2026-06-20)

**НИКОГДА не пушить на GitHub без полного smoke-теста Docker.** Паттерн ошибки:
агент запушил после успешного health check, но chat completion падал с 401 —
Pavel потребовал удалить репозиторий.

**5-шаговый smoke test перед push:**

```bash
# 1. Запустить
docker compose up -d

# 2. Дождаться health (ARM64: ~170s)
for i in $(seq 1 90); do curl -sf localhost:18648/health && break; sleep 2; done

# 3. Models endpoint
curl -s -H "Authorization: Bearer $API_SERVER_KEY" localhost:18648/v1/models | grep hermes-agent

# 4. Chat completion (реальный ключ LLM обязателен!)
curl -s -H "Authorization: Bearer $API_SERVER_KEY" localhost:18648/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"hermes-agent","messages":[{"role":"user","content":"Hello"}]}'

# 5. Остановить
docker compose down
```

**Почему health ≠ работает:**
- Docker-образ по умолчанию использует OpenRouter — нужен `OPENROUTER_API_KEY`
- `API_SERVER_KEY=***` отвергается Hermes (проверка на плейсхолдеры)
- Dockerfile SHA может быть недоступен (не пересобрать)
- Telegram может висеть на реконнектах (РФ), блокируя API server

## First-run onboarding

`llm-bootstrap/hermes_bootstrap.py` detects first run by scanning `config.yaml`
for `CHANGEME` values. On detection, augments the system prompt with a Russian
onboarding block that:

1. Greets the user in Russian
2. Explains what needs to be configured (API keys, Neo4j, OpenCode+)
3. Points to `ИНСТРУКЦИЯ.md`, `НАСТРОЙКА.md`, `.env.template`
4. DOES NOT ask for API keys in chat (security rule)

## Pre-Push Testing Gate (CRITICAL)

**НИКОГДА не пушить на GitHub без полного smoke-теста.** Pavel забраковал push на GitHub сделанный до тестирования.

Минимальный smoke-test перед push:
1. `docker compose up -d`
2. Дождаться health: `for i in $(seq 1 90); do curl -sf localhost:18648/health && break; sleep 2; done`
3. `curl localhost:18648/v1/models -H "Authorization: Bearer $KEY"`
4. `curl -X POST localhost:18648/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d '{"model":"hermes-agent","messages":[{"role":"user","content":"test"}],"max_tokens":10}'`
5. `docker compose down`
6. Только после успеха всех шагов — `git push`

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

## Two-mode distribution pattern (CRITICAL, 2026-07-06)

A distribution should support two installation modes to cover both
GPU-equipped and remote-endpoint users:

| Aspect | Mode A (Local) | Mode B (Remote) |
|--------|----------------|-----------------|
| Requires | NVIDIA GPU, ~80GB disk for models | Just Docker + API key |
| LiteLLM config | `config.yaml` (aliases to `:8101-8103`) | `config.openai.yaml` (alias `codewar-default` → `${OPENAI_API_BASE}`) |
| Install script | `setup-llama.sh` (build + start models) | Inline: read OPENAI_API_BASE, OPENAI_API_KEY, MODEL_NAME |
| UFW rules | Required (Docker→host:8101-8103) | Not needed |

**Mode B config pattern** (`config.openai.yaml`):
```yaml
model_list:
  - model_name: "codewar-default"
    litellm_params:
      model: "openai/${OPENAI_MODEL_NAME}"
      api_base: "os.environ/OPENAI_API_BASE"
      api_key: "os.environ/OPENAI_API_KEY"
```

**Install script pattern** — `install.sh` with `--mode A|B` flag, interactive
fallback if no flag given. Mode B collects endpoint info via `read -sp` (key)
and `read -p` (base URL, model name).

## Neo4j graph dump technique (CRITICAL, 2026-07-06)

Neo4j Community Edition does NOT support `STOP DATABASE` (Enterprise only).
`neo4j-admin database dump` fails with "database is in use" on a running
instance. APOC export procedures may not be installed.

**Working technique — stop container, temp container, dump, restart:**

```bash
# 1. Stop the running Neo4j container
docker stop neo4j
sleep 2

# 2. Run dump via a TEMPORARY container with the volume mounted
#    MUST chmod 777 the output directory first (Neo4j user can't write otherwise)
chmod 777 ./dumps
docker run --rm \
  -v first_neo4j_data:/data \
  -v "$(pwd)/dumps:/dumps" \
  neo4j:5-community \
  neo4j-admin database dump neo4j --to-path=/dumps --overwrite-destination

# 3. Restart Neo4j
docker start neo4j
```

**Import on target machine** — same pattern: stop, load, start:
```bash
docker stop neo4j
docker run --rm \
  -v neo4j_data:/data \
  -v "$(pwd)/dumps:/dumps" \
  neo4j:5-community \
  neo4j-admin database load neo4j --from-path=/dumps --overwrite-destination
docker start neo4j
```

**Pitfall:** `chmod 777` on the dumps directory is MANDATORY — the Neo4j
container user (uid 7474) cannot write to a directory owned by the host user
without it. Error: `AccessDeniedException: /dumps`.

**Pitfall:** Binary `.dump` files contain raw strings that match PII patterns
(e.g. `/home/user/` in stored node properties). PII test scripts MUST exclude
`*.dump` from grep scans: `--exclude=*.dump`.

## PII test script design (CRITICAL, 2026-07-06)

When writing a PII verification test script (`test-pii.sh`):

1. **Self-exclusion**: The test script itself CONTAINS the PII patterns it
   searches for (as string literals in grep commands). MUST exclude itself:
   `--exclude=test-pii.sh` or `--exclude-dir=tests`.

2. **Binary exclusion**: Neo4j `.dump` files, `.db` files, images — all contain
   binary data that can match PII patterns. Exclude with `--exclude=*.dump`.

3. **Avoid `eval` with complex quoting**: Using `eval "$cmd"` where `$cmd`
   contains nested single-quotes (from variable expansion of `$EXCLUDES`)
   causes bash to hang silently. Instead, use `bash -c "$cmd"` or restructure
   to avoid eval entirely:
   ```bash
   # ❌ Hangs — nested quote expansion in eval
   EXCLUDES="--exclude='*.dump' --exclude='test-pii.sh'"
   check "No PII" "grep -rl $EXCLUDES 'pattern' '$DIST_DIR/'"

   # ✅ Works — unquoted globs in EXCLUDES, bash -c for eval
   EXCLUDES="--exclude=*.dump --exclude=test-pii.sh --exclude-dir=.git"
   result=$(bash -c "grep -rl $EXCLUDES 'pattern' '$DIST_DIR/'" 2>/dev/null | head -3)
   ```

4. **Second-pass sanitization for .cypher files**: `.cypher` files are not in
   the default text-file extension list for `find + sed`. They contain
   `changeme` in comments and `/home/user` in paths. Must explicitly include
   `*.cypher` in the sanitization find command.

5. **`sk-xxx...xxxx` in documentation**: Example API keys in documentation
   (`sk-xxx...xxxx`, `sk-...`) match `sk-[a-zA-Z0-9]{3,}` patterns. Use
   `<YOUR_API_KEY>` placeholder instead. Python `re.sub` is more reliable
   than `sed` for these patterns:
   ```python
   content = re.sub(r'sk-[a-zA-Z0-9.]{3,}', '<YOUR_API_KEY>', content)
   ```

## Distribution directory isolation (user preference, 2026-07-06)

**Pavel's rule:** All distribution work MUST happen in a separate directory
(`~/dev/codemes/codewar/`), NEVER in the source `~/.hermes/`. The source
installation must remain untouched. Copy files OUT, sanitize copies, never
modify originals in place.

```
Source (READ-ONLY):     ~/.hermes/              ← agents, skills, hooks, etc.
                        ~/cursor/first/          ← LLM stack configs
                        ~/dev/llama/             ← llama.cpp scripts

Distribution (WRITE):   ~/dev/codemes/codewar/  ← sanitized copies + new files
```

## Rename on distribution (user preference, 2026-07-06)

When creating a new distribution, rename ALL references to the previous
distribution name. `codemes_1` → `codewar` everywhere in text files. Binary
files (`.dump`) cannot be sed'd — document them as exceptions in PII test
output.

## Requirements files — downloadable artifacts manifest (user preference, 2026-07-06)

**Pavel's rule:** A distribution MUST include two requirements files
(`requirements-mode-a.txt` and `requirements-mode-b.txt`) listing ALL
downloadable artifacts the user needs on a bare system — EXCEPT GPU drivers
and CUDA toolkit (those are documented separately as system prerequisites).

Each file lists:
1. **The distribution archive** itself (filename + size)
2. **Docker images** to `docker pull` — exact `repository:tag` + size
3. **Base images** needed for local Docker builds (e.g. `python:3.12-alpine`,
   `nvidia/cuda:13.0.0-devel-ubuntu24.04`)
4. **Model files** (Mode A only) — GGUF filenames, sizes, where to put them
5. **Hermes Agent CLI** — `pip install hermes-agent`
6. **System packages** — `apt install` command
7. **NVIDIA Container Toolkit** (Mode A only) — install + configure commands
8. **Summary totals** — total download size, what's NOT included

Pattern: each entry has a comment with purpose and size. Example:
```
neo4j:5-community                                                    # 607 MB
ghcr.io/berriai/litellm-database:v1.83.7-stable                      # 1.89 GB
```

Mode A total: ~85 GB (77G models + 7.5G Docker images + 200M Hermes).
Mode B total: ~4.7 GB (4.4G Docker images + 200M Hermes, no GPU/models).

Locally-built images (via `docker compose build`) are listed separately
from pull images, with a note that they build from Dockerfiles in the dist.

## exFAT external drive symlink pitfall (CRITICAL, 2026-07-06)

When copying directories with symlinks (e.g. `node_modules/`, llama.cpp `.so`
files) to an **exFAT-formatted** external drive (Seagate, WD, USB sticks),
symlinks are **silently expanded into full file copies**. This inflates size
dramatically:

| Directory | Real size (ext4) | Expanded size (exFAT) | Factor |
|---|---|---|---|
| `node_modules/` (npm) | 45 MB | 847 MB | 19× |
| `llama.cpp/build/bin/` (.so) | 83 MB | 83 MB | 1× (mostly real files) |

**Root cause:** exFAT does not support POSIX symlinks. `cp -r` silently
dereferences them, creating full copies of every symlinked file. npm
`node_modules/.bin/` and package cross-references are heavily symlinked.

**Fix — always use `tar` to preserve symlinks on exFAT:**
```bash
# ✅ Correct — tar preserves symlinks inside the archive
cd /source/dir
tar czf /external/drive/node_modules.tar.gz node_modules/

# Extract on target machine (which has ext4/btrfs/zfs):
tar xzf node_modules.tar.gz -C /target/dir/

# ❌ Wrong — cp -r expands symlinks on exFAT
cp -r /source/node_modules/ /external/drive/node_modules/
```

**Detection:** if `du -sh` on the external drive shows a directory much larger
than the source, check `find /external/path -type l | wc -l` — if 0 symlinks
but source has many, exFAT expanded them.

**Also affected:** FAT32, NTFS (without `sysdm` symlink support on Linux),
CIFS/SMB shares without `mfsymlinks` option.

## Full offline packaging pattern (CRITICAL, 2026-07-06)

Beyond Docker images, a fully offline-installable distribution needs THREE
additional pre-cached artifact bundles:

### 0. Cross-platform pre-building (CRITICAL, 2026-07-06)

**Discovery:** `docker buildx build --platform linux/amd64 --load` works on Jetson
ARM64 via QEMU emulation. `pip download --platform manylinux2014_x86_64` also works.
This means ALL x86_64 artifacts can be pre-built on the ARM64 dev machine
(while it has internet) and shipped to an air-gapped x86_64 target.

```bash
# Prerequisite: QEMU for cross-platform builds
sudo apt install qemu-user-static
docker buildx ls | grep -q linux/amd64 || exit 1

# Pre-build pip wheels for x86_64
pip download --platform manylinux2014_x86_64 --python-version 312 \
  --only-binary=:all: hermes-agent -d dist/pip-packages-x86_64/

# Pre-build Docker images for amd64
for img in neo4j:5-community arizephoenix/phoenix:latest postgres:16-alpine; do
  docker pull --platform linux/amd64 "$img"
  docker save "$img" -o "dist/docker-images-amd64/$(echo $img | tr '/:' '-').tar"
done

# Pre-build local images for amd64 (via QEMU)
# 6 locally-built images (NOT 9 — verify against compose files, not docker images):
for svc in agent-registry clawcode-adapter opencode-adapter \
           openhands-adapter skills-manager openai-stack-relay; do
  docker buildx build --platform linux/amd64 --load \
    -t "voice-assistant-${svc}:local" \
    -f "llm-stack/docker/${svc}/Dockerfile" .
done

# Pre-build llama-server for x86_64 (via Docker buildx + CUDA image)
# ⚠️ llamacpp Dockerfile hardcodes CUDA_ARCH=121 (Blackwell/Jetson).
#    MUST override for x86_64 target GPU (90=Hopper, 89=Ada, 80=Ampere).
cat > /tmp/Dockerfile.llama-x86 << 'EOF'
FROM nvidia/cuda:13.0.0-devel-ubuntu24.04
RUN apt-get update && apt-get install -y git cmake build-essential
RUN git clone --depth 1 https://github.com/ggml-org/llama.cpp /src
RUN cd /src && cmake -B build -DGGML_CUDA=ON \
  -DCMAKE_CUDA_ARCHITECTURES=89 \
  && cmake --build build -j$(nproc) --target llama-server
EOF
docker buildx build --platform linux/amd64 --load \
  -t llama-x86-builder:latest -f /tmp/Dockerfile.llama-x86 .
docker run --rm -v /tmp/out:/out llama-x86-builder:latest \
  cp /src/build/bin/llama-server /out/
```

**Limitations:** QEMU is 5-10× slower than native. CUDA cannot be verified inside QEMU
(no GPU passthrough). Pre-built artifacts must be smoke-tested on the actual target
machine. See `hermes-migration` skill → `references/cross-platform-pre-build.md` for full script.

### 1. pip packages (Hermes Agent CLI + all deps)

```bash
# On online machine — download all wheels (no install):
pip download hermes-agent -d dist/pip-packages/

# On offline target — install from local wheels:
pip install --no-index --find-links dist/pip-packages/ hermes-agent
```

Size: ~40 MB (60 wheels for hermes-agent 0.18.0 + openai, fastapi, pydantic,
uvicorn, httpx, cryptography, jinja2, rich, etc.)

### 2. npm node_modules (for MCP plugins like claw-neo4j)

```bash
# On online machine — install + tar (preserves symlinks):
cd plugins/claw-neo4j/
npm install
tar czf node_modules.tar.gz node_modules/

# On offline target — extract:
tar xzf node_modules.tar.gz -C plugins/claw-neo4j/
```

Size: ~5 MB compressed (45 MB uncompressed, `@modelcontextprotocol/sdk` +
`neo4j-driver` + deps).

**Pitfall:** Do NOT `cp -r node_modules/` to an exFAT drive — symlinks expand
19× (see exFAT pitfall above). Always tar first.

### 3. Pre-built llama-server binary (Mode A, avoids git clone + cmake)

```bash
# On online/build machine — build llama.cpp, then tar the bin/ dir:
cd ~/dev/llama.cpp/build/bin
tar czf llama-server-bin.tar.gz llama-server lib*.so* libmtmd*

# On offline target — extract to ~/dev/llama.cpp/build/bin/:
mkdir -p ~/dev/llama.cpp/build/bin
tar xzf llama-server-bin.tar.gz -C ~/dev/llama.cpp/build/bin/
```

Size: ~49 MB compressed (83 MB uncompressed — includes `libggml-cuda.so` at
61 MB, the CUDA backend).

**Pitfall:** The binary is architecture-specific (ARM64 vs x86_64) and
CUDA-version-specific. Document the target architecture in the archive name
or a README.

### install-offline.sh — ties it all together

The offline installer script should:
1. `docker load` all `.tar` images from `docker-images/`
2. `pip install --no-index --find-links` from `pip-packages/`
3. `tar xzf node_modules.tar.gz` for MCP plugins
4. `tar xzf llama-server-bin.tar.gz` for Mode A
5. Generate `.env` with `openssl rand -hex` for keys
6. `docker network create llm-stack-net`
7. `docker compose up -d` for Neo4j + Phoenix + LiteLLM
8. Import Neo4j graph dump
9. Copy hermes-core to `~/.hermes/`

### Offline completeness matrix

```
                     Mode A (local)     Mode B (remote)
Docker images        ✅ docker load    ✅ docker load
Models GGUF          ✅ file copy      — (not needed)
Neo4j dump           ✅ import         ✅ import
Hermes CLI           ✅ pip --no-index ✅ pip --no-index
MCP plugin npm       ✅ tar extract    ✅ tar extract
llama-server binary  ✅ tar extract    — (not needed)
LLM endpoint         — (local models)  ❌ needs internet (API calls)
```

**Only Mode B's actual LLM API calls require internet** — everything else
can be pre-packaged. See `references/offline-packaging-pattern.md` for
the full `install-offline.sh` script and detailed instructions.

## Testing before archiving (user preference, 2026-07-06)

**Mandatory phase before creating the final archive:**
1. PII verification (grep for all known PII patterns) — use `scripts/test-pii.sh` as a template
2. Docker smoke test (start services, check health endpoints)
3. Functional test (chat completion, Neo4j query, Phoenix traces)
4. **Offline isolation test** — verify zero internet connections (see below)

Archive is created ONLY after all tests pass. See `references/codewar-session-2026-07.md`
for the full test suite structure.

## Offline isolation test (CRITICAL, 2026-07-06)

When a distribution claims to be "fully offline," VERIFY it by blocking all
internet traffic and running the full install. This catches hidden dependencies
(Docker pull attempts, pip downloads, npm fetches, apt-get update inside
Dockerfiles) that would fail on an air-gapped machine.

**Technique — iptables OUTPUT chain blocking + dmesg monitoring:**

1. Create a LOG+DROP chain in iptables
2. Allow localhost, Docker networks (172.16.0.0/12), LAN (192.168.0.0/16, 10.0.0.0/8)
3. Drop everything else with LOG prefix `CODEWAR_BLOCKED:`
4. Monitor `dmesg -w` for blocked entries
5. Run the full install sequence
6. Check blocked connections log — **must be 0 entries**
7. Restore iptables

**Requires root (sudo).** The user runs the script manually:
```bash
sudo bash tests/test-offline-isolation.sh
```

**What the test verifies (7 checks):**
1. `docker load` all 15 images — no `docker pull` attempts
2. `pip install --no-index --find-links` — no PyPI access
3. `tar xzf node_modules.tar.gz` — no `npm install` attempts
4. `tar xzf llama-server-bin.tar.gz` + `--help` — binary works without build
5. `docker compose up` Neo4j — starts from loaded image, no pull
6. `docker compose up` Phoenix — starts from loaded image, no pull
7. **Blocked connections log = 0 lines** — nothing tried to reach the internet

**Pitfall — port conflicts on test machine:** When testing on a machine that
already has services running (e.g. existing `litellm` on :4000), the test
compose files must use different ports (e.g. `14000:4000`) and container names
(`codewar-test-litellm`) to avoid conflicts. This is a test-environment issue,
not an offline issue.

**Pitfall — dmesg permissions:** `dmesg` requires root. The test script must
be run with `sudo`. Non-root alternatives: `unshare --net` for namespace
isolation (limited, doesn't block Docker bridge traffic).

See `scripts/test-offline-isolation.sh` for the full reusable script.

## References

- `references/codemes-distribution-session.md` — full session transcript of the
  codemes_1 packaging cycle (2026-06-14): requirements, system analysis, architecture,
  implementation, security audit, acceptance testing. 9 bugs found and fixed.
- `references/manifest-reference.md` — canonical manifest.yaml with all 14 include
  rules, 13 exclude categories, 8 sanitize patterns, and 7 validate checks.
- `references/sanitization-methodology.md` — PII discovery patterns, replacement table,
  her2code/ target structure, and verification checklist. From the full-stack sanitization
  cycle (`<SESSION_ID>`): 62 PII items across 12 categories, producing an 81MB
  clean distribution.
- `references/pii-blind-spots.md` — **NEW (2026-06-20):** Categories missed by first-pass
  sanitization: systemd service files, PlantUML, Android Kotlin, shell scripts, compose
  defaults. 7 documented blind spots with regex patterns and config fixes.
- `references/v3-packaging-inventory-2026-07-14.md` — **NEW (2026-07-14):** Updated inventory for hermes_portable_v3 (131 skills, 32 agents, 10 hooks). Documents the profile path split (skills at top `~/.hermes/` vs config under `home/.hermes/profiles/codewar/`), V2→V3 reuse pattern for Docker/GUI assets, and grown counts since July 6.
- `references/llm-infrastructure-inventory.md` — **NEW (2026-07-06):** Per-component inventory
  for the LLM Infrastructure Stack (Neo4j, LiteLLM, llama.cpp, Phoenix). Architecture diagram,
  file-by-file include/exclude/sanitize rules, model reference table, and estimated clean dist size (~5.2M).
- `references/codewar-distribution-session.md` — **NEW (2026-07-06):** Full codewar distribution
  session: structure, Seagate bundle layout, 10-point validation methodology, issues found & fixed,
  comparison with codemes_1, and what's NOT included by design.
- `references/codewar-session-2026-07.md` — **NEW (2026-07-06):** Full codewar distribution
  session: two-mode install pattern, Neo4j dump technique, PII test script pitfalls,
  directory isolation, test-before-archive workflow, final dist structure and sizes.
- `references/offline-packaging-pattern.md` — **NEW (2026-07-06):** Full air-gapped
  installation technique: pip download for Hermes CLI, node_modules.tar.gz for MCP
  plugins, pre-built llama-server binary, install-offline.sh script, exFAT symlink
  preservation, Docker image list, and validation checklist.
- `references/portable-v3-packaging-pattern.md` — **NEW (2026-07-14):** V3 portable
  distribution structure with automated PII sanitization pipeline (Python YAML recursive
  sanitizer + sed bulk pass + .env.example generation + iterative grep verification loop).
  Includes "reuse existing portable artifacts" pattern (copy V2 Docker/GUI if same version),
  V3 directory structure, start-backend.sh first-run flow, exclusion checklist, and
  verification protocol.

## Templates

- `templates/docker-compose.yml` — unified Docker Compose for Hermes + Neo4j + Dashboard.
  Copy to `her2code/docker-compose.yml`.
- `templates/.env.docker` — Docker-specific environment variables template. Copy to
  `her2code/.env`, edit with real keys.
- `templates/.env.llm-stack` — **NEW (2026-07-06):** Complete env template for the full LLM
  Infrastructure Stack (Neo4j, LiteLLM, Phoenix, local backends, agent mesh adapters). Covers
  all variables referenced by `compose.neo4j.yml`, `compose.phoenix.yml`, and `start-llama.sh`.
  Copy to `.env`, replace all `CHANGE_ME` values with real credentials.

## Scripts

- `scripts/test-pii.sh` — reusable PII verification script template. Self-excludes
  (avoids matching its own pattern strings), excludes binary `.dump` files, and
  uses `bash -c` instead of `eval` to avoid quoting hangs. Copy to `tests/` in
  any distribution, edit the PII patterns to match your environment.
- `scripts/test-offline-isolation.sh` — **NEW (2026-07-06):** Offline isolation
  test. Run with `sudo bash scripts/test-offline-isolation.sh`. Blocks all
  internet via iptables, runs full install sequence, logs blocked connection
  attempts (must be 0), restores iptables. Verifies: docker load, pip install
  (--no-index), node_modules extraction, llama-server binary, docker compose up.
  Uses non-conflicting ports (14000, 16006, 17474) for testing on machines with
  existing services.
- `scripts/validate-portable-distribution.sh` — **NEW (2026-07-08):** Validate a
  finished portable Hermes distribution directory. Checks bash syntax, Python
  compile, YAML/JSON parse, d2 diagram compilation, port consistency across
  start.sh/.env/docker-compose, hardcoded `/home/` paths, d2 `<style>{}` artifacts,
  and binary artifacts (GUI, GGUF, docker tarball). Usage: `bash scripts/validate-portable-distribution.sh /path/to/hermes_portable`.
