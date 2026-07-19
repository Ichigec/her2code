# Cross-Architecture Offline Deployment

> Patterns for deploying Hermes to a machine of a DIFFERENT architecture
> (e.g. ARM64 → x64) with NO internet access. Tested 2026-07-08.

## Architecture-specific components

Not everything is arch-independent. This table determines what needs
per-arch handling:

| Component | Arch-specific? | Size | How to handle |
|-----------|:-:|------|---------------|
| GGUF model | NO | ~22G | Same file works everywhere |
| Docker image | **YES** | 1-2G | Build or save per-arch |
| Electron GUI binary | **YES** | ~195M | Build per-arch or cache zip |
| llama-server binary | **YES** | ~8M | Cross-compile or native build |
| Config YAML | NO | <5K | Same config |
| Python code (in Docker) | NO | — | Runs in container |

## exFAT heredoc pitfall — CRITICAL

USB drives formatted as exFAT silently corrupt bash heredocs. A script
with:
```bash
cat > file <<EOF
line1
line2
EOF
```
will have the heredoc body merged into one line or the EOF marker lost.

**ALWAYS use `printf` instead of heredocs in scripts stored on exFAT:**
```bash
# WRONG (breaks on exFAT):
cat > "$DASH_HOME/.env" <<EOF
HERMES_DASHBOARD_SESSION_TOKEN=$DASH_TOKEN
EOF

# RIGHT (works everywhere):
printf 'HERMES_DASHBOARD_SESSION_TOKEN=%s\n' "$DASH_TOKEN" > "$DASH_HOME/.env"
```

This also applies to multi-line heredocs for connection.json, gateway .env,
and any generated config. The corruption is silent — bash reports a syntax
error only when the script runs.

## Docker image: cross-build via buildx (ARM64 → x64)

Building an x64 Docker image from an ARM64 host requires QEMU binfmt:

```bash
# Register QEMU (if not already):
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes

# Create buildx builder:
docker buildx create --name x64builder --use

# Build with --platform linux/amd64:
cd ~/.hermes/hermes-agent
docker buildx build --platform linux/amd64 -t hermes-agent:x64 -f Dockerfile.x64 --load .
```

### QEMU limitation: Node.js SIGSEGV

QEMU x86_64 emulation **crashes on Node.js** (SIGSEGV in V8). This means
the Dockerfile steps that run `npm install`, `npm run build`, or
`npx playwright install` will fail.

**Workaround:** Patch the Dockerfile to skip all npm steps:
```dockerfile
# Replace:
#   RUN npm install --prefer-offline --no-audit && npx playwright install ...
# With:
RUN true # npm+playwright skipped — QEMU SIGSEGV on x64 cross-build

# Replace:
#   RUN cd web && npm run build && cd ../ui-tui && npm run build
# With:
RUN true # web+ui-tui build skipped — QEMU SIGSEGV

# Fix chown (node_modules doesn't exist after skipping npm):
#   chown -R hermes:hermes ... /opt/hermes/node_modules
# Remove /opt/hermes/node_modules from the chown line
```

The resulting x64 image has **no web UI** (no compiled frontend assets),
but the gateway REST API works. Dashboard starts but serves no web frontend.

Also: `--allow-unauthenticated` needed for apt-get install in QEMU:
```dockerfile
RUN apt-get update && apt-get install -y --allow-unauthenticated --no-install-recommends ...
```

### Save/load Docker images per-arch

```bash
# Save (on build machine):
docker save hermes-agent:latest | gzip > hermes-agent-arm64.tar.gz   # ~1.6G
docker save hermes-agent:x64   | gzip > hermes-agent-x64.tar.gz      # ~810M

# Load (on target machine):
docker load < hermes-agent-x64.tar.gz
```

## Electron GUI binary: offline build from Docker image

When no pre-built Electron binary exists for the target arch, build it
on-site by extracting source from the Docker image + using a cached
Electron zip.

### Prerequisites on target machine

- `node` and `npm` installed (`sudo apt install nodejs npm`)
- Docker image loaded (`docker load < hermes-agent-x64.tar.gz`)

### Pattern (used in `build-gui.sh`)

```bash
# 1. Extract apps/desktop + node_modules from Docker image
docker run --rm -v "$BUILD_DIR/hermes-agent:/out" --entrypoint sh "$IMAGE_TAG" -c '
    cp -a /opt/hermes/apps/desktop /out/apps/desktop &&
    cp -a /opt/hermes/node_modules /out/node_modules &&
    cp -a /opt/hermes/package.json /out/package.json
'

# 2. Install Electron from cached zip (NO network needed)
# Electron zip: electron-v40.9.3-linux-x64.zip (~115M)
mkdir -p ~/.cache/electron
cp electron-v*-linux-x64.zip ~/.cache/electron/
export ELECTRON_SKIP_BINARY_DOWNLOAD=1

# 3. Build
cd hermes-agent/apps/desktop
export GITHUB_SHA="local-offline-build"
npm run build   # tsc + vite
npm run pack    # electron-builder --dir → release/linux-x64-unpacked/Hermes
```

### Electron zip discovery

Electron zips can be found in:
```
~/.cache/electron/electron-v<version>-linux-<arch>.zip
```

The version matches `node_modules/electron/package.json` version field.
Copy these zips from a machine that previously ran `npm ci` for that arch.

## llama-server: cross-compile

Cross-compile llama-server for x64 from ARM64:

```bash
# Install cross-compiler:
sudo apt install gcc-x86-64-linux-gnu g++-x86-64-linux-gnu

# Build in /tmp (avoid stale root-owned CMakeCache):
cmake -B /tmp/llama-build-x64 -S /path/to/llama.cpp \
  -DCMAKE_C_COMPILER=x86_64-linux-gnu-gcc \
  -DCMAKE_CXX_COMPILER=x86_64-linux-gnu-g++ \
  -DCMAKE_SYSTEM_NAME=Linux \
  -DCMAKE_SYSTEM_PROCESSOR=x86_64 \
  -DGGML_NATIVE=OFF \
  -DGGML_CUDA=OFF \
  -DLLAMA_CURL=OFF \
  -DLLAMA_BUILD_UI=OFF \
  -DCMAKE_BUILD_TYPE=Release

cmake --build /tmp/llama-build-x64 --target llama-server -j$(nproc)
```

### Pitfall: `tools/ui/ui.h` missing `llama_ui_asset` struct

llama.cpp HEAD may reference `llama_ui_asset` type without defining it.
When `LLAMA_BUILD_UI=OFF`, add a stub to `tools/ui/ui.h`:

```c
struct llama_ui_asset { std::string name; std::string data; std::string mime_type; };
inline std::vector<llama_ui_asset> llama_ui_get_assets() { return {}; }
inline const llama_ui_asset * llama_ui_find_asset(const std::string n) { return nullptr; }
```

### Pitfall: stale root-owned CMakeCache

If `build-x64/` was previously created by root (e.g. inside Docker),
`rm -rf` fails with permission denied and `cmake` sees a stale cache
referencing `/src/` (Docker build path). Build in `/tmp/` instead.

## docker-compose.yml: platform directive

When deploying to x64, `docker-compose.yml` must specify the platform:

```yaml
services:
  hermes:
    image: ${HERMES_IMAGE:-hermes-agent}
    platform: ${DOCKER_PLATFORM:-linux/amd64}
    ...
```

Without `platform:`, Docker refuses to run the image:
```
The requested image's platform (linux/arm64) does not match
the detected host platform (linux/amd64/v3)
```

The `DOCKER_PLATFORM` variable is set by `start-backend.sh` based on
`uname -m` auto-detection.

## Auto-detection pattern (for portable scripts)

```bash
HOST_ARCH="$(uname -m)"
case "$HOST_ARCH" in
  aarch64|arm64)
    export DOCKER_PLATFORM="linux/arm64"
    IMAGE_TAG="hermes-agent:arm64"
    TARBALL="$SCRIPT_DIR/docker/hermes-agent-arm64.tar.gz"
    ;;
  x86_64|amd64)
    export DOCKER_PLATFORM="linux/amd64"
    IMAGE_TAG="hermes-agent:amd64"
    TARBALL="$SCRIPT_DIR/docker/hermes-agent-x64.tar.gz"
    ;;
esac
```

## Portable launch.sh with auto-rebuild

The `launch.sh` script can detect arch mismatch and offer to rebuild:

```bash
# Check binary matches host arch
BIN_INFO=$(file "$BIN" 2>/dev/null || echo "")
case "$HOST_ARCH" in
  x86_64|amd64)
    echo "$BIN_INFO" | grep -qi 'x86-64' || NEED_REBUILD=true
    ;;
esac

if [ "$NEED_REBUILD" = "true" ]; then
    echo "GUI binary is wrong arch. Rebuild from Docker image? [y/N]"
    read -r ANSWER
    [ "$ANSWER" = "y" ] && build_gui || exit 1
fi
```

The `build_gui()` function extracts source from Docker image, uses cached
Electron zip, runs `npm run build && npm run pack`, and copies the result
to `gui/`. See `scripts/build-gui.sh` for the full implementation.
