# Offline Packaging Pattern — Full Air-Gapped Installation

Complete technique for making a Hermes Agent + LLM infrastructure distribution
installable on a machine with NO internet access. Developed during the codewar
session (2026-07-06) when the user asked to put everything on a Seagate
external drive.

## What needs internet in a normal install

| Component | Internet dependency | Can pre-package? |
|---|---|---|
| Docker images (pull) | `docker pull` from Docker Hub / ghcr.io | ✅ `docker save` → `.tar` |
| Docker images (built) | `docker build` → `apt-get`, `pip install`, `git clone` | ✅ `docker save` after build |
| Hermes Agent CLI | `pip install hermes-agent` from PyPI | ✅ `pip download` → wheels |
| MCP plugins (npm) | `npm install` from npm registry | ✅ `npm install` + `tar` |
| llama.cpp binary | `git clone` + `cmake` + `apt-get` | ✅ pre-build + `tar` |
| Neo4j graph data | N/A (in volume) | ✅ `neo4j-admin database dump` |
| Model weights | HuggingFace download | ✅ file copy (large) |
| LLM API endpoint (Mode B) | API calls to external service | ❌ requires internet by design |

## Seagate bundle layout

```
/media/pavel/One Touch/hermes/          ~97 GB total
├── codewar/                            324 MB  ← dist + offline bundles
│   ├── pip-packages/                   40 MB   ← 60 wheels (hermes-agent + deps)
│   ├── hermes-core/plugins/claw-neo4j/
│   │   └── node_modules.tar.gz          5 MB   ← npm deps (symlink-preserved)
│   ├── llm-stack/llama/
│   │   └── llama-server-bin.tar.gz     49 MB   ← pre-built ARM64+CUDA binary
│   ├── install/
│   │   ├── install.sh                          ← online installer
│   │   ├── install-offline.sh                  ← offline installer
│   │   └── load-docker-images.sh               ← docker load helper
│   └── ... (hermes-core, llm-stack, neo4j, tests, docs)
├── codewar-20260706.tar.gz             129 MB  ← archive (with offline bundles)
├── models/                             76 GB   ← 4 GGUF files
└── docker-images/                      21 GB   ← 15 Docker image .tar files
```

## install-offline.sh — key sections

### 1. Load Docker images

```bash
IMAGES_DIR="${IMAGES_DIR:-$(cd "$PROJECT_ROOT/../docker-images" 2>/dev/null && pwd)}"
for tar in "$IMAGES_DIR"/*.tar; do
    [ -f "$tar" ] || continue
    docker load -i "$tar" &>/dev/null && echo "✅ $(basename $tar)" || echo "❌"
done
```

### 2. Install Hermes Agent (offline pip)

```bash
PIP_DIR="$PROJECT_ROOT/pip-packages"
if command -v hermes &>/dev/null; then
    echo "✅ Hermes already installed"
else
    pip3 install --no-index --find-links "$PIP_DIR" hermes-agent
fi
```

### 3. Extract MCP plugin node_modules

```bash
NM_TAR="$PROJECT_ROOT/hermes-core/plugins/claw-neo4j/node_modules.tar.gz"
tar xzf "$NM_TAR" -C "$PROJECT_ROOT/hermes-core/plugins/claw-neo4j/"
```

### 4. Extract pre-built llama-server (Mode A only)

```bash
LLAMA_TAR="$PROJECT_ROOT/llm-stack/llama/llama-server-bin.tar.gz"
LLAMA_DIR="${HOME}/dev/llama.cpp/build/bin"
mkdir -p "$LLAMA_DIR"
tar xzf "$LLAMA_TAR" -C "$LLAMA_DIR/"
```

### 5. Start services (same as online)

```bash
docker network create llm-stack-net 2>/dev/null || true
docker compose -f compose.neo4j.yml up -d
docker compose -f compose.phoenix.yml up -d
# Wait for health...
```

## exFAT symlink preservation

External drives (Seagate, WD Passport) are often factory-formatted as exFAT.
exFAT does NOT support POSIX symlinks. `cp -r` silently dereferences them,
inflating `node_modules/` from 45 MB to 847 MB.

**Always use tar for symlink-heavy directories:**
```bash
# On source machine:
cd /source/plugins/claw-neo4j
tar czf /external/drive/node_modules.tar.gz node_modules/

# On target machine:
tar xzf node_modules.tar.gz -C /target/plugins/claw-neo4j/
```

**Detection:** `du -sh` on external drive >> source size → check for expanded
symlinks: `find /external/path -type l | wc -l` (0 = expanded).

## Docker image list for codewar (15 images)

| Tar filename | Docker image | Size | Type |
|---|---|---|---|
| neo4j-5-community.tar | `neo4j:5-community` | 584 MB | pull |
| phoenix-latest.tar | `arizephoenix/phoenix:latest` | 809 MB | pull |
| litellm-v1.83.7.tar | `ghcr.io/berriai/litellm-database:v1.83.7-stable` | 1.9 GB | pull |
| postgres-16-alpine.tar | `postgres:16-alpine` | 262 MB | pull |
| python-3.12-alpine.tar | `python:3.12-alpine` | 53 MB | pull (base for relay) |
| python-3.12-slim.tar | `python:3.12-slim` | 142 MB | pull (base for adapters) |
| alpine-latest.tar | `alpine:latest` | 9 MB | pull (UFW rules) |
| cuda-13-devel.tar | `nvidia/cuda:13.0.0-devel-ubuntu24.04` | 6.1 GB | pull (llama.cpp build) |
| cuda-13-runtime.tar | `nvidia/cuda:13.0.0-runtime-ubuntu24.04` | 2.4 GB | pull (llama.cpp runtime) |
| openai-stack-relay.tar | `voice-assistant-openai-stack-relay:local` | 54 MB | built |
| clawcode-adapter.tar | `voice-assistant-clawcode-adapter:local` | 301 MB | built |
| openhands-adapter.tar | `voice-assistant-openhands-adapter:local` | 989 MB | built |
| opencode-adapter.tar | `voice-assistant-opencode-adapter:local` | 301 MB | built |
| agent-registry.tar | `voice-assistant-agent-registry:local` | 193 MB | built |
| skills-manager.tar | `voice-assistant-skills-manager:local` | 193 MB | built |

**Total: 15 images, ~15 GB**

## Validation checklist for offline bundle

- [ ] `docker-images/*.tar` — all 15 images present, `tar tf` valid, `manifest.json` inside
- [ ] `pip-packages/*.whl` — `hermes_agent-*.whl` + all deps (check with `pip install --dry-run --no-index --find-links`)
- [ ] `node_modules.tar.gz` — `tar tzf` shows `node_modules/` tree with symlinks
- [ ] `llama-server-bin.tar.gz` — `tar tzf` shows `llama-server` + `lib*.so*` with symlinks
- [ ] `neo4j/dumps/neo4j.dump` — binary, 38 MB, importable
- [ ] `models/*.gguf` — file sizes match source (use `stat -c%s`, not md5 for 22G+ files)
- [ ] PII test passes (14/14 checks, excluding `.dump` and `test-pii.sh` from scans)
- [ ] `install-offline.sh` executable and references correct relative paths
