# Codewar Distribution Session (2026-07-06)

## Context

User requested a full distribution packaging of Hermes Agent + LLM infrastructure
into `codewar/` — replacing both `codemes_1` (proof-of-concept) and `her2code`
(production attempt). Key requirements from user:

1. **Two installation modes**: Mode A (local llama.cpp + GPU models) and Mode B
   (OpenAI-compatible remote endpoint)
2. **SH scripts in two variants** — one for llama.cpp, one for OpenAI endpoint
3. **Requirements files** listing ALL dependencies including models and Docker images
4. **Rename codemes_1 → codewar** everywhere
5. **Prepare files for sanitization**
6. **Test in virtual environment** before archiving (from prior experience)
7. **Copy to Seagate external drive** with models and Docker images included

## Distribution Structure

```
codewar/                           # 42 MB, 1176 files
├── hermes-core/                   # 14 MB — agents (84), skills (24 cats), hooks (10), 
│   │                                scripts (30), gates (24), plugins (3), opencode_claw, cron
│   ├── config.yaml.template       # NEW: custom_providers → LiteLLM gateway
│   ├── AGENTS.md                  # sanitized: ${HOME} instead of /home/user/
│   └── SOUL.md
├── llm-stack/                     # 808 KB
│   ├── docker/litellm/
│   │   ├── config.yaml            # Mode A: 35+ aliases → host.docker.internal:8101-8103
│   │   └── config.openai.yaml     # Mode B: single alias → os.environ/OPENAI_API_BASE
│   ├── docker/llamacpp/Dockerfile # Multi-stage build: nvidia/cuda:13.0.0-devel → llama-server
│   ├── docker/openai-stack-relay/ # Python micro-proxy
│   ├── docker/{clawcode,openhands,opencode}-adapter/  # Agent-mesh A2A adapters
│   ├── docker/agent-registry/     # Single tool-server fronting all adapters
│   ├── docker/skills-manager/     # CRUD over .ai/skills/
│   ├── compose/
│   │   ├── compose.neo4j.yml      # Neo4j 5-community (FIX: added llm-stack-net network)
│   │   ├── compose.phoenix.yml    # Phoenix + LiteLLM + 2× Postgres + relay
│   │   ├── compose.llama.yml      # llama-server in Docker (optional, for Docker mode)
│   │   └── compose.agents-mesh.yml
│   ├── llama/
│   │   ├── start-llama.sh         # 3 models as daemons + watchdog + UFW injection
│   │   ├── plan3-architecture.md  # Multi-model orchestrator design
│   │   ├── roles.md               # 29 roles → 3 models routing
│   │   └── APEX-ANALYSIS.md       # Q8_0 on SSM tensors = garbage, --no-mmap fix
│   └── env/
│       ├── .env.example           # Mode A: all LLM stack variables
│       ├── .env.llamacpp.example  # llama.cpp launch parameters
│       └── .env.openai.example    # Mode B: OpenAI endpoint variables
├── neo4j/
│   ├── dumps/neo4j.dump           # 38 MB — 20K+ nodes, 9K+ relationships
│   ├── export-graphs.sh           # Stop container → temp container dump → restart
│   └── import-graphs.sh           # Stop container → temp container load → restart → verify
├── install/
│   ├── install.sh                 # Main: --mode A or --mode B
│   ├── setup-llama.sh             # Mode A: build llama.cpp, start 3 models, verify
│   ├── setup-ufw.sh               # UFW rules for Docker→host:8101-8103
│   ├── setup-neo4j.sh             # Start Neo4j, import graph dump
│   ├── setup-phoenix.sh           # Start Phoenix + LiteLLM, verify health
│   ├── setup-litellm.sh           # Configure LiteLLM (Mode A or B), smoke test
│   ├── setup-hermes.sh            # Copy hermes-core to ~/.hermes/, create config
│   └── load-docker-images.sh      # NEW: docker load all tar files
├── tests/
│   ├── run-tests.sh               # Main test runner
│   ├── test-pii.sh                # 14 PII checks (exclude self!)
││   └── test-docker-smoke.sh      # Docker compose up + health checks + API tests
├── models/
│   ├── README.md                  # Model download guide (3 GGUF, 77 GB)
│   └── verify-models.sh           # Check models exist and match expected sizes
├── requirements-mode-a.txt        # Full deps: archive + models (77G) + Docker (15G) + Hermes CLI
├── requirements-mode-b.txt        # Full deps: archive + Docker (4.4G) + Hermes CLI (no GPU/models)
├── README.md                      # Main instruction (Russian, architecture diagram, quick start)
└── INSTALL.md                     # Detailed install guide (both modes, troubleshooting)
```

## Seagate Bundle

External drive `/media/pavel/One Touch/hermes/` (97 GB total):

```
hermes/
├── codewar/                       # 231 MB — full dist
├── codewar-20260706.tar.gz        # 42 MB — archive
├── models/                        # 76 GB — 4 GGUF files
│   ├── Huihui-Nex-N2-mini-abliterated-APEX-Quality.gguf          # 33G (:8101 coding)
│   ├── Qwen3.6-35B-A3B-uncensored-heretic-...-APEX-I-Quality.gguf # 22G (:8102 reasoning)
│   ├── SuperQwen-APEX-I-Quality-v3.gguf                           # 22G (:8103 simulation)
│   └── SuperQwen-imatrix-v3.gguf                                  # 184M
└── docker-images/                 # 15 GB — 15 tar files
    ├── neo4j-5-community.tar      ├── cuda-13-devel.tar (6.1G)
    ├── phoenix-latest.tar         ├── cuda-13-runtime.tar (2.4G)
    ├── litellm-v1.83.7.tar (1.9G) ├── openai-stack-relay.tar
    ├── postgres-16-alpine.tar     ├── clawcode-adapter.tar
    ├── python-3.12-alpine.tar     ├── openhands-adapter.tar
    ├── python-3.12-slim.tar       ├── opencode-adapter.tar
    ├── alpine-latest.tar          ├── agent-registry.tar
    └── skills-manager.tar
```

## Validation Methodology (10-point checklist)

| # | Check | Method | Result |
|---|-------|--------|--------|
| 1 | Distribution integrity | All directories and key files present | ✅ 1176 files |
| 2 | Model files | Size comparison source vs Seagate | ✅ 4/4 match |
| 3 | Docker images | `tar tf` validity + manifest.json | ✅ 15/15 valid |
| 4 | Requirements vs reality | Cross-check all listed items exist | ✅ All present |
| 5 | Install scripts | All paths reference existing files | ✅ 20/20 paths valid |
| 6 | Compose files | Images, ports, volumes, networks | ✅ All consistent |
| 7 | Hermes core | Agent/skill/hook/gate counts | ✅ 84 agents, 24 skills |
| 8 | .env templates | No real keys, all placeholders | ✅ 0 real keys |
| 9 | PII verification | 14 grep/find checks | ✅ 14/14 clean |
| 10 | Gaps analysis | What's missing for bare-metal install | ✅ 3 gaps found & fixed |

## Issues Found & Fixed During Validation

1. **compose.neo4j.yml missing network** → added `networks: [llm-net]` + external network
2. **No load-docker-images.sh** → created script that loops `docker load -i` over tar files
3. **No config.yaml.template** → created with `custom_providers` pointing to LiteLLM gateway

## What's NOT in the Distribution (by design)

- NVIDIA GPU drivers (system-specific, kernel-dependent)
- CUDA toolkit (delivered via Docker images)
- Docker Engine + Compose (system package)
- Hermes Agent CLI (`pip install hermes-agent`)
- python3, git, curl, openssl, bash (system packages)
- state.db, logs, sessions, caches (runtime state)
- memories/, pavel-environment/ (personal data)

## Key Differences from codemes_1

| | codemes_1 (2026-06-14) | codewar (2026-07-06) |
|---|---|---|
| Agents | 12 | 84 |
| Skills | 22 + pavel-env (leaked!) | 24 (no pavel-env) |
| Hooks/Scripts/Gates | ❌ all missing | ✅ 10/30/24 |
| LLM Stack | ❌ | ✅ LiteLLM + Phoenix + llama.cpp + Neo4j |
| Mode B (OpenAI) | ❌ | ✅ config.openai.yaml |
| PII leaks | ❌ (MEMORY.md, USER.md) | ✅ 14/14 clean |
| Install scripts | 1 (install.sh) | 8 (install + setup-*.sh) |
| Tests | ❌ | ✅ PII + Docker smoke |
| Docker images | ❌ | ✅ 15 tar files (15 GB) |
| Models | ❌ | ✅ 4 GGUF (76 GB) on Seagate |
| Requirements files | ❌ | ✅ Mode A + Mode B |
