# LLM Infrastructure Stack — Packaging Inventory (2026-07-06, updated 2026-07-06)

Detailed per-component inventory for the 4-component LLM infrastructure
stack. All source files live under `~/cursor/first/` (Docker stack) and
`~/dev/llama/` (host-side llama.cpp launcher).

## Architecture

```
HOST (DGX Spark, ARM64, CUDA 13, 121GB unified)
  llama-server :8101 (Nex 33G)     ─┐
  llama-server :8102 (Qwen 22G)    ─┤── direct ports, --no-mmap
  llama-server :8103 (World 22G)   ─┘
  LM Studio :1234 (host)           ──┐
  vLLM :8000 (host)                ──┤── alternative backends
  diffusion-server :8646 (host)    ──┘
        │
  DOCKER (llm-stack-net)
        │
  LiteLLM :4000 ─── 35+ model aliases, A2A agent-mesh, audio STT/TTS
    ├── success_callback: arize_phoenix ──► Phoenix :6006 (tracing UI)
    ├── phoenix-db (postgres:16)
    ├── litellm-db (postgres:16)
    ├── openai-stack-relay :8089 (pattern-B hop)
    ├── DeepSeek API (cloud)
    ├── OpenAI API (cloud)
    └── MCP: searchbox (15 search engines)
        
  Neo4j :7474/:7687 ─── 3 graphs: education, claw, codebase
```

## Component 1: Neo4j (Graph DB)

### Files to INCLUDE

| File | Size | Source | Notes |
|------|------|--------|-------|
| `compose.neo4j.yml` | 668B | `~/cursor/first/` or `~/.hermes/` | Docker compose: neo4j:5-community, :7474/:7687, healthcheck. Sanitize: `changeme` → `${NEO4J_PASSWORD:-CHANGEME}` |
| `plugins/claw-neo4j/` | 156K | `~/.hermes/plugins/` | MCP server: mcp-server.mjs, search.js, graph/, queries/, package.json. **MUST exclude node_modules/** (45M → 156K) |
| `neo4j/dumps/neo4j.dump` | ~38M | `neo4j-admin database dump` | Binary graph dump for offline import |

### Files to EXCLUDE

| Item | Reason |
|------|--------|
| Neo4j data volume (`first_neo4j_data`) | Runtime data, recreated from dump |
| Real `.env` with `NEO4J_PASSWORD=changeme` | Secret — use `.env.example` |

### Neo4j Community Edition graph dump (WORKING technique)

**Neo4j Community does NOT support `STOP DATABASE`** — `neo4j-admin database dump` fails with "database is in use" when run inside the running container. The `docker exec` approach from older docs DOES NOT WORK.

Working technique: stop the container, use a temporary container with the volume mounted, dump, then restart:

```bash
# 1. Stop Neo4j container
docker stop neo4j

# 2. Dump via temporary container
mkdir -p ./neo4j/dumps && chmod 777 ./neo4j/dumps
docker run --rm \
  -v first_neo4j_data:/data \
  -v "$(pwd)/neo4j/dumps:/dumps" \
  neo4j:5-community \
  neo4j-admin database dump neo4j --to-path=/dumps --overwrite-destination

# 3. Restart Neo4j
docker start neo4j
```

**Pitfalls:**
- `AccessDeniedException: /dumps` — target dir not writable by neo4j user (uid 7474). Fix: `chmod 777 ./dumps` before running.
- `STOP DATABASE neo4j` → `Unsupported administration command` — Community Edition doesn't support this. Use the stop-container approach above.
- `apoc.export.cypher.all` → `no procedure registered` — APOC not available in vanilla Community. Use `neo4j-admin database dump` instead.
- `docker exec neo4j neo4j-admin database dump` → `database is in use` — even if you try `cypher-shell "STOP DATABASE neo4j"` first, Community Edition rejects it. Must stop the container.

### Import on target machine

```bash
docker stop neo4j
docker run --rm \
  -v neo4j_data:/data \
  -v "$(pwd)/dumps:/dumps" \
  neo4j:5-community \
  neo4j-admin database load neo4j --from-path=/dumps --overwrite-destination
docker start neo4j
```

---

## Component 2: LiteLLM (LLM Gateway)

### Files to INCLUDE

| File | Size | Source | Notes |
|------|------|--------|-------|
| `docker/litellm/config.yaml` | 21K | `~/cursor/first/docker/litellm/` | **KEY FILE.** 510 lines, 35+ model aliases. All keys use `os.environ/` — already safe |
| `compose.phoenix.yml` | 6.4K | `~/cursor/first/` | Phoenix + LiteLLM + 2x PostgreSQL + openai-stack-relay. `mem_limit: 4g` (anti-leak), `MALLOC_ARENA_MAX=2` |
| `.env.example` | 11K | `~/cursor/first/` | 193 lines: all env vars. Keys empty or `CHANGE-ME` |
| `.env.llamacpp.example` | 3.2K | `~/cursor/first/` | llama.cpp launch params: ctx=262144, gpu_layers=41, parallel=4, flash_attn, no-mmap, direct-io |
| `docker/openai-stack-relay/` | 4.3K | `~/cursor/first/docker/` | Dockerfile (python:3.12-alpine) + relay.py |
| `compose.agents-mesh.yml` | ~5K | `~/cursor/first/` | Agent-mesh adapters: clawcode (:8790), openhands (:8791), opencode (:8798) |
| `docker/agent-mesh-common/` | ~10K | `~/cursor/first/docker/` | Shared agent-mesh library |
| `docker/agent-registry/` | ~5K | `~/cursor/first/docker/` | Agent registry |
| `docker/skills-manager/` | ~5K | `~/cursor/first/docker/` | CRUD over .ai/skills/ |
| `docker/clawcode-adapter/` | ~10K | `~/cursor/first/docker/` | Claw Code A2A adapter |
| `docker/openhands-adapter/` | ~10K | `~/cursor/first/docker/` | OpenHands A2A adapter |
| `docker/opencode-adapter/` | ~10K | `~/cursor/first/docker/` | OpenCode A2A adapter (ACP bridge) |

### Files to EXCLUDE

| Item | Reason |
|------|--------|
| Real `.env` (10K) | SECRETS: DEEPSEEK_API_KEY, OPENAI_API_KEY, adapter keys |
| Real `.env.llamacpp` (3.3K) | Real model paths |
| `litellm-pg-volume` | Runtime PostgreSQL data |

---

## Component 3: llama.cpp (Local Model Serving)

### Files to INCLUDE

| File | Size | Source | Notes |
|------|------|--------|-------|
| `dev/llama/start-llama.sh` | 11K | `~/dev/llama/` | 269 lines: 3 llama-server daemon launch, watchdog, UFW rules, garbage token test |
| `docker/llamacpp/Dockerfile` | 1.7K | `~/cursor/first/docker/llamacpp/` | Multi-stage: nvidia/cuda:13.0.0-devel → llama.cpp git clone → cmake (sm_121) |
| `compose.llama.yml` | 1.5K | `~/cursor/first/` | Docker compose: llama-server with GPU |
| `dev/llama/plan3-architecture.md` | 18K | `~/dev/llama/` | Plan3 multi-model orchestrator |
| `dev/llama/roles.md` | 5.9K | `~/dev/llama/` | Role distribution: reasoning→Qwen, coding→Nex, simulation→AgentWorld |
| `dev/llama/APEX-ANALYSIS.md` | 13K | `~/dev/llama/` | Q8_0 on SSM tensors = garbage, --no-mmap fix |

### Model reference table

| Model | Size | Port | Alias | Role |
|-------|------|------|-------|------|
| Huihui-Nex-N2-mini-abliterated-APEX-Quality.gguf | 33G | :8101 | nex-n2-mini | Coding (SWE-Bench 74.4) |
| Qwen3.6-35B-A3B-uncensored-heretic-...-APEX-I-Quality.gguf | 22G | :8102 | qwen3.6-35b | Reasoning (GPQA 86.0) |
| SuperQwen-APEX-I-Quality-v3.gguf | 22G | :8103 | agentworld | Simulation (AgentWorldBench 56.39) |

### Key technical findings

1. **`--no-mmap` MANDATORY for multi-instance** on unified memory. Without it, 2nd+ models produce garbage.
2. **Q8_0 on SSM/DeltaNet tensors = garbage**. Use APEX (Q6_K) instead.
3. **UFW workaround**: Docker→host blocked by firewall. Inject rules via privileged container.
4. **Watchdog**: Separate daemon checks every 30s, restarts dead models.

---

## Component 4: Phoenix (Arize Phoenix — LLM Observability)

### Files to INCLUDE

| File | Size | Source | Notes |
|------|------|--------|-------|
| `compose.phoenix.yml` | 6.4K | `~/cursor/first/` | Shared with LiteLLM |
| `connect-phoenix.sh` | 2.4K | `~/cursor/opencode+/` | Wire host llama → LiteLLM → Phoenix |
| `.env.example` (OTEL section) | — | `~/cursor/first/` | OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_SERVICE_NAME |

### Files to EXCLUDE

| Item | Reason |
|------|--------|
| `phoenix-pg-volume` | Runtime trace history |
| `phoenix-data-volume` | Runtime Phoenix data |

---

## Two-Mode Distribution Pattern (NEW, 2026-07-06)

A distribution can support two installation modes with a single codebase:

### Mode A — Local (llama.cpp + GPU models)
- Requires: NVIDIA GPU, CUDA, 80GB+ disk for models
- LiteLLM config: `config.yaml` with aliases pointing to `http://host.docker.internal:8101-8103/v1`
- Install flow: build llama.cpp → start 3 models → UFW rules → Neo4j → Phoenix+LiteLLM → Hermes

### Mode B — Remote (OpenAI-compatible endpoint)
- Requires: just Docker + an OpenAI-compatible API endpoint
- LiteLLM config: `config.openai.yaml` with single alias → `${OPENAI_API_BASE}` + `${OPENAI_API_KEY}`
- Install flow: configure .env.openai → Neo4j → Phoenix+LiteLLM → Hermes (no GPU needed)

### Implementation
- `config.yaml` — full 35+ alias config (Mode A, points to local llama.cpp :8101-8103)
- `config.openai.yaml` — minimal config (Mode B, single `codewar-default` alias → external endpoint)
- `install.sh --mode A|B` — selects which config to activate
- `.env.example` — for Mode A (Neo4j, LiteLLM, llama.cpp vars)
- `.env.openai.example` — for Mode B (OPENAI_API_BASE, OPENAI_API_KEY, OPENAI_MODEL_NAME)

### Install script structure
```
install/
├── install.sh           ← main entry, selects mode, calls setup scripts
├── setup-llama.sh       ← Mode A only: build + start 3 llama-server models
├── setup-ufw.sh         ← Mode A only: Docker→host firewall rules
├── setup-neo4j.sh       ← both modes: start Neo4j + import graph dump
├── setup-phoenix.sh     ← both modes: Phoenix + LiteLLM stack
├── setup-litellm.sh     ← both modes: activate correct config + smoke test
└── setup-hermes.sh      ← both modes: copy hermes-core to ~/.hermes/
```

---

## Docker Image Offline Export (NEW, 2026-07-06)

For air-gapped or USB-based installation, export all Docker images to .tar files:

```bash
mkdir -p docker-images

# Pre-built images (from Docker Hub / GHCR)
for img in \
    neo4j:5-community \
    arizephoenix/phoenix:latest \
    ghcr.io/berriai/litellm-database:v1.83.7-stable \
    postgres:16-alpine \
    python:3.12-alpine \
    python:3.12-slim \
    alpine:latest; do
    name=$(echo "$img" | tr '/:' '_')
    docker save "$img" -o "docker-images/${name}.tar"
done

# CUDA images (for llama.cpp build, Mode A only)
docker save nvidia/cuda:13.0.0-devel-ubuntu24.04 -o docker-images/cuda-13-devel.tar
docker save nvidia/cuda:13.0.0-runtime-ubuntu24.04 -o docker-images/cuda-13-runtime.tar

# Locally built images
for img in \
    voice-assistant-openai-stack-relay:local \
    voice-assistant-clawcode-adapter:local \
    voice-assistant-openhands-adapter:local \
    voice-assistant-opencode-adapter:local \
    voice-assistant-agent-registry:local \
    voice-assistant-skills-manager:local; do
    name=$(echo "$img" | tr '/:' '_')
    docker save "$img" -o "docker-images/${name}.tar"
done
```

**Load on target machine:**
```bash
for tar in docker-images/*.tar; do
    docker load -i "$tar"
done
```

**Pitfall:** `docker save` can take 10+ minutes for large images (CUDA devel = 6.1G). Run in background with `notify_on_complete=true`.

**Pitfall:** Some image names differ from what compose files reference. Check exact `docker images` output before saving. Example: `python:3.12-slim-bookworm` vs `python:3.12-slim`.

---

## Requirements Files Pattern (NEW, 2026-07-06)

Create `requirements-mode-a.txt` and `requirements-mode-b.txt` in the distribution root, listing EVERYTHING the user needs to download:

### requirements-mode-a.txt (Mode A — local)
- Archive: `codewar-YYYYMMDD.tar.gz` (42 MB)
- Models: 3 GGUF files (77 GB) with exact filenames and HuggingFace search hints
- Docker images: 15 .tar files (~15 GB) with exact `docker save` names
- Hermes Agent: `pip install hermes-agent`
- System packages: `apt install docker.io docker-compose-v2 curl python3 git openssl`
- NVIDIA Container Toolkit (NOT drivers — those are system-specific)
- **Total: ~85 GB**

### requirements-mode-b.txt (Mode B — remote)
- Archive: `codewar-YYYYMMDD.tar.gz` (42 MB)
- Docker images: 12 .tar files (~4.4 GB, no CUDA, no llama.cpp)
- Hermes Agent: `pip install hermes-agent`
- System packages: same
- External endpoint: URL + API key + model name
- **Total: ~4.7 GB**

Both files explicitly state: "Does NOT include NVIDIA GPU drivers or CUDA toolkit — those are system-specific and must be installed separately."

---

## PII Test Script Self-Exclusion (NEW, 2026-07-06)

When writing a PII verification test script, the script itself contains PII patterns (as search strings). It will match itself.

**Fix:** Use grep `--exclude` to skip the test script itself and binary dumps:

```bash
EXCLUDES="--exclude=*.dump --exclude=test-pii.sh --exclude-dir=.git --exclude-dir=__pycache__"
grep -rl $EXCLUDES '/home/user/' "$DIST_DIR/"
```

**Pitfall:** Using `bash -c "$cmd"` inside the check function causes shell quoting issues with `$EXCLUDES` containing quotes. Use direct `eval` or restructure to avoid nested quoting.

**Pitfall:** Binary files (neo4j.dump) will match PII patterns. Always exclude `*.dump`.

---

## Estimated clean dist size

```
hermes-core/     14M    (agents, skills, hooks, scripts, gates, plugins)
llm-stack/       808K   (LiteLLM, Phoenix, llama, compose, docker, docs)
neo4j/           38M    (graph dump)
install/         36K    (7 setup scripts)
tests/           32K    (PII + Docker smoke tests)
docs/            37K    (README + INSTALL + models/README)
─────────────────────
TOTAL:           ~53M   (42M compressed)
```
