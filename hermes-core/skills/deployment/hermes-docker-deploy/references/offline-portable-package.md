# Offline Portable Package — USB/Flash Drive Deployment

> Creating a self-contained Hermes package for machines without internet.

## What goes in the package (~25G)

```
hermes_portable/
├── deploy-offline-superqwen.sh          ← Single-command launcher
├── start.sh                             ← Management (stop/status/gui)
├── models/
│   └── SuperQwen-APEX-I-Quality-v3.gguf  22G   ← GGUF model (arch-independent)
├── llama.cpp/
│   └── build/bin/llama-server           617M   ← Pre-built ARM64 binary
├── docker/
│   └── hermes-agent-arm64.tar.gz        1.6G   ← Docker image (gzip compressed)
├── gui/
│   └── linux-arm64-unpacked/Hermes      687M   ← Electron GUI binary
├── config/
│   └── config.docker.superqwen.yaml             ← Single-model config
└── scripts/                                     ← Helper scripts
```

## Packaging workflow

### 1. Docker image → tar.gz

```bash
docker save hermes-agent:latest | gzip > /target/docker/hermes-agent-arm64.tar.gz
# 4.65GB image → ~1.6GB compressed
# Load on target: docker load < hermes-agent-arm64.tar.gz
```

### 2. GUI binary

```bash
cp -a ~/.hermes/hermes-agent/apps/desktop/release/linux-arm64-unpacked /target/gui/
# OR from backup: cp -a ~/dev/codemes/gui-backup-v2/electron-app /target/gui/linux-arm64-unpacked
```

### 3. llama.cpp build

```bash
# ARM64 (native):
cp -rL ~/.dev/llama.cpp/build /target/llama.cpp/build

# x64 (cross-compiled from ARM64):
cmake -B /tmp/llama-build-x64 -S ~/dev/llama.cpp \
  -DCMAKE_C_COMPILER=x86_64-linux-gnu-gcc \
  -DCMAKE_CXX_COMPILER=x86_64-linux-gnu-g++ \
  -DCMAKE_SYSTEM_NAME=Linux \
  -DCMAKE_SYSTEM_PROCESSOR=x86_64 \
  -DGGML_NATIVE=OFF -DGGML_CUDA=OFF \
  -DLLAMA_CURL=OFF -DLLAMA_BUILD_UI=OFF \
  -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/llama-build-x64 --target llama-server -j$(nproc)
```

### 4. GGUF model (arch-independent, same file for ARM64 and x64)

```bash
cp ~/models/SuperQwen-APEX-I-Quality-v3.gguf /target/models/
```

## FAT32/exFAT USB drive constraints

Most USB flash drives are formatted as FAT32 or exFAT, which **do not support
symlinks**. The llama.cpp build directory contains symlinks (`libggml.so →
libggml.so.0 → libggml.so.0.15.2`). Copying with `cp -r` fails with
"Operation not permitted" on symlink creation.

**Fix:** Always use `cp -rL` (dereference symlinks — copies the actual file
content instead of the link):

```bash
cp -rL ~/dev/llama.cpp/build /target/llama.cpp/build
# NOT: cp -r ~/dev/llama.cpp/build /target/llama.cpp/build  ← FAILS on FAT32
```

This increases size (no shared .so deduplication) but is the only option on
non-posix filesystems.

## Cross-compilation pitfalls (llama.cpp ARM64 → x64)

### `llama_ui_asset` not defined

When cross-compiling llama.cpp with `-DLLAMA_BUILD_UI=OFF`, `server-http.cpp`
references `llama_ui_asset` which is only defined when `LLAMA_BUILD_UI=ON`.
The type is missing from `tools/ui/ui.h` in recent commits.

**Fix:** Add a stub struct to `ui.h` before cross-compiling:

```cpp
struct llama_ui_asset {
    std::string name;
    std::string data;
    std::string mime_type;
};
inline std::vector<llama_ui_asset> llama_ui_get_assets() { return {}; }
inline const llama_ui_asset * llama_ui_find_asset(const std::string) { return nullptr; }
```

### Stale root-owned CMakeCache

If a previous build was run as root, `CMakeCache.txt` may be root-owned and
block rebuild. Build in `/tmp/` with `-S /path/to/source` to avoid permission
issues:

```bash
cmake -B /tmp/llama-build-x64 -S ~/dev/llama.cpp ...
# NOT: cd ~/dev/llama.cpp && cmake -B build-x64 ...  ← stale root cache
```

### Docker x64 image via QEMU buildx fails

`docker buildx build --platform linux/amd64` fails inside QEMU with apt
signature errors during the `apt-get update` step. This is a known QEMU
emulation limitation — the container's apt can't verify package signatures
through the emulation layer.

**Workaround:** Build the Docker image natively on an x64 machine. There is
no reliable way to cross-build Debian-based Docker images from ARM64 via QEMU.

## deploy-offline-superqwen.sh — what it does

The offline deploy script (9 steps):
1. Checks docker, GUI binary, model file, llama-server
2. Loads Docker image from tar.gz if not already loaded
3. Stops old stack (containers + llama-server + old GUI)
4. Creates data directories (`~/.hermes-portable`, `~/.hermes-portable-dash`)
5. Copies config + generates .env files
6. Launches llama-server with SuperQwen on :8103
7. Launches gateway container on :18649
8. Launches dashboard container on :9123
9. Tests model through gateway
10. Writes connection.json → dashboard :9123
11. Launches GUI with `--disable-gpu --disable-software-rasterizer --no-sandbox`

**Path resolution:** The script uses `$SCRIPT_DIR` (the directory containing
the script itself) as the base for all portable paths, with `$REAL_HOME`
fallbacks for installed-from-source components.

## Validation checklist (before giving to user)

```bash
# Run these checks on the target machine:
[ -f "$SCRIPT_DIR/gui/linux-arm64-unpacked/Hermes" ] && echo "GUI OK"
[ -f "$SCRIPT_DIR/models/SuperQwen-APEX-I-Quality-v3.gguf" ] && echo "Model OK"
[ -f "$SCRIPT_DIR/llama.cpp/build/bin/llama-server" ] && echo "llama OK"
[ -f "$SCRIPT_DIR/docker/hermes-agent-arm64.tar.gz" ] && echo "Docker tar OK"
[ -f "$SCRIPT_DIR/config/config.docker.superqwen.yaml" ] && echo "Config OK"
docker image inspect hermes-agent >/dev/null 2>&1 && echo "Image loaded"
curl -sf http://localhost:9123/api/status >/dev/null && echo "Dashboard alive"
```
