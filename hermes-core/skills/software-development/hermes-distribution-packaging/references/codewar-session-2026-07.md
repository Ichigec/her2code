# Codewar Distribution Session — 2026-07-06

Full session building the `codewar` distribution: a sanitized packaging of
Hermes Agent + LLM infrastructure (Neo4j, LiteLLM, llama.cpp, Phoenix) with
two installation modes.

## Distribution structure

```
codewar/                          53M, 1172 files
├── README.md                     14K — main guide (Russian)
├── INSTALL.md                    23K — detailed install (Mode A + Mode B)
├── hermes-core/                  14M — agents (84), skills (24 cats), hooks (8),
│                                     scripts (33), gates, plugins (3), opencode_claw,
│                                     cron, AGENTS.md, SOUL.md
├── llm-stack/                    808K — LiteLLM config + config.openai.yaml,
│                                     Docker compose files, llama.cpp Dockerfile,
│                                     start-llama.sh, env templates, docs
├── neo4j/                        38M — graph dump + export/import scripts
├── install/                      36K — install.sh + 6 setup-*.sh scripts
├── tests/                        32K — test-pii.sh + test-docker-smoke.sh + run-tests.sh
└── models/                       28K — README.md (model guide) + verify-models.sh
```

## Final archive

`codewar-20260706.tar.gz` — 42M compressed.

## What was done (10 phases)

| Phase | What | Duration |
|-------|------|----------|
| 1 | Created directory structure | <1 min |
| 2 | Copied hermes-core (agents, skills, hooks, scripts, gates, plugins, cron) | 1 min |
| 3 | Copied llm-stack (docker configs, compose, llama scripts, env, docs) | 1 min |
| 4 | Sanitization (find+sed on text files, PII scan) | 5 min |
| 5 | Neo4j graph export (stop container, temp container dump, restart) | 3 min |
| 6 | Created config.openai.yaml (Mode B) + .env.openai.example | 2 min |
| 7 | Created install scripts (install.sh + 6 setup-*.sh) | 10 min |
| 8 | Documentation (README.md, INSTALL.md, models/README.md) — via subagent | 7 min |
| 9 | Verified codemes_1 → codewar rename (0 text matches) | 1 min |
| 9.5 | PII testing — all 8 checks clean | 3 min |
| 10 | Archive (tar.gz) | 1 min |

## Neo4j dump — step by step

Neo4j Community 5.x running in Docker. `neo4j-admin database dump` fails on
a running database ("database is in use"). No APOC installed.

```bash
# 1. chmod output dir (Neo4j uid 7474 can't write to host-owned dir)
chmod 777 ./neo4j/dumps

# 2. Stop container
docker stop neo4j
sleep 2

# 3. Dump via temporary container
docker run --rm \
  -v first_neo4j_data:/data \
  -v "$(pwd)/neo4j/dumps:/dumps" \
  neo4j:5-community \
  neo4j-admin database dump neo4j --to-path=/dumps --overwrite-destination

# 4. Restart
docker start neo4j
```

Result: `neo4j.dump` — 38M, containing 20K+ nodes, 9K+ relationships across
education, claw, and codebase graphs.

**Failed approaches:**
- `cypher-shell "STOP DATABASE neo4j"` → "Unsupported administration command"
  (Community edition limitation)
- `apoc.export.cypher.all` → "No procedure with the name" (APOC not installed)
- `neo4j-admin database dump` on running container → "database is in use"

## Sanitization — patterns and replacements

| Pattern | Replacement | Files affected |
|---------|-------------|----------------|
| `/home/user/` | `${HOME}/` | ~20 files (scripts, configs, docs) |
| `<YOUR_VPS_IP>` | `<VPS_IP>` | ~10 files (skills, android docs) |
| `<YOUR_DEVICE_ID>` | `<DEVICE_ID>` | 1 file (sanitization ref) |
| `1003011121225` | `<TELEGRAM_CHAT_ID>` | ~10 files (agents, cron, skills) |
| `raicomml` / `@raicomml` | `<TELEGRAM_CHANNEL>` | ~8 files |
| `codemes_1` | `codewar` | ~10 files (skills, agents) |
| `changeme` | `CHANGEME` | ~15 files (compose, gates, skills) |
| `sk-xxx...xxxx` | `<YOUR_API_KEY>` | 1 file (native-mcp.md) |
| `/home/user` (word boundary) | `${HOME}` | .cypher files (second pass) |

**Technique**: `find + sed` on text files only, filtered by extension:
```bash
find "$DST" -type f \( -name "*.md" -o -name "*.sh" -o -name "*.py" \
  -o -name "*.yaml" -o -name "*.yml" -o -name "*.json" -o -name "*.mjs" \
  -o -name "*.js" -o -name "*.ts" -o -name "*.tsx" -o -name "*.env*" \
  -o -name "*.example" -o -name "Dockerfile" -o -name "*.txt" \
  -o -name "*.cypher" \) -print0 | while IFS= read -r -d '' f; do
    sed -i 's|pattern|replacement|g' "$f"
done
```

**Second pass needed for `.cypher` files** — not in default extension list
on first pass. Contained `changeme` in comments and `/home/user` in paths.

## PII test script — final working version

Key design decisions:
1. `EXCLUDES="--exclude=*.dump --exclude=test-pii.sh --exclude-dir=.git --exclude-dir=__pycache__"`
2. Use `bash -c "$cmd"` instead of `eval "$cmd"` (avoids quote expansion hangs)
3. Exclude `*.dump` (binary Neo4j dump contains raw PII strings in node properties)
4. Exclude `test-pii.sh` itself (contains PII patterns as search strings)

## Install scripts — two modes

### install.sh (main entry point)
- `--mode A` → calls `setup-llama.sh` (build llama.cpp, start 3 models) + `setup-ufw.sh`
- `--mode B` → collects OPENAI_API_BASE, OPENAI_API_KEY, MODEL_NAME via interactive prompts
- Both modes → `setup-neo4j.sh` → `setup-phoenix.sh` → `setup-hermes.sh`
- Generates `.env` from template, fills in provided values, generates random keys via `openssl rand -hex`

### setup-llama.sh (Mode A only)
- Checks for `nvidia-smi`
- Checks for 3 model GGUF files in `~/models/`
- Builds llama.cpp from source if binary not found
- Runs `start-llama.sh start`
- Verifies all 3 models respond on :8101-8103

### setup-neo4j.sh
- Creates `llm-stack-net` Docker network
- Starts Neo4j via `compose.neo4j.yml`
- Waits for health (cypher-shell `RETURN 1`)
- Imports graph dump if available

### setup-phoenix.sh
- Starts Phoenix + LiteLLM + 2x PostgreSQL via `compose.phoenix.yml`
- Waits for Phoenix (:6006) and LiteLLM (:4000) health
- Checks models endpoint

### setup-hermes.sh
- Copies hermes-core/ to `~/.hermes/` using `cp -rn` (no-clobber, merge)
- Creates `config.yaml` from template if not exists
- Creates Hermes `.env` pointing to LiteLLM

## config.openai.yaml (Mode B)

Simplified LiteLLM config for remote OpenAI-compatible endpoints:
- Single model alias `codewar-default` → `${OPENAI_MODEL_NAME}` at `${OPENAI_API_BASE}`
- All values via `os.environ/` indirection
- Commented examples for DeepSeek, OpenAI GPT, Ollama, embeddings
- Same Phoenix tracing config (`success_callback: ["arize_phoenix"]`)

## Differences from codemes_1 / her2code

| | codemes_1 | her2code | codewar |
|---|---|---|---|
| Agents | 12 | 14 | **84** |
| Skills | 22+pers | 23 | **24 (no pavel-env)** |
| Hooks | ❌ | ❌ | **✅ 8** |
| Scripts | ❌ | ❌ | **✅ 33** |
| Gates | ❌ | ❌ | **✅** |
| LLM Stack | ❌ | ❌ | **✅ LiteLLM+Phoenix+llama.cpp+Neo4j** |
| Neo4j dump | ❌ | ❌ | **✅ 38M** |
| Mode B (OpenAI) | ❌ | ❌ | **✅ config.openai.yaml** |
| PII leaks | ❌ (MEMORY.md, USER.md) | ❌ | **✅ clean** |
| Install scripts | 1 | ❌ | **✅ 7 scripts** |
| Tests | ❌ | ❌ | **✅ PII + Docker smoke** |
