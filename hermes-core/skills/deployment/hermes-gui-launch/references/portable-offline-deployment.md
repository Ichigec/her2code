# Portable Offline Deployment — Full Pattern

## Scenario

Deploy Hermes + local LLM to a machine via USB drive, completely offline.
Source machine: ARM64 (Jetson). Target machine: may be x64 (Kali/Ubuntu).

## exFAT Constraints (THE #1 source of bugs)

exFAT-formatted USB drives break these bash features:

1. **Heredocs** (`cat > file <<EOF`) — content corrupts, lines merge
2. **UTF-8** (Cyrillic, em-dash, emoji) — bytes mangle → syntax errors
3. **cp -a** (preserve ownership) — "Operation not permitted"
4. **cp -a** (preserve symlinks) — "cannot create symbolic link"
5. **set -eu + read** — if stdin closed, read returns 1 → script dies

### Writing scripts for exFAT

```bash
# WRONG (heredoc breaks on exFAT):
cat > "$FILE" <<EOF
content
EOF

# RIGHT (printf works):
printf 'line1\nline2\n' > "$FILE"

# WRONG (UTF-8 breaks on exFAT):
echo "Запуск GUI…"

# RIGHT (ASCII only):
echo "Launching GUI..."

# WRONG (set -eu kills on read failure):
set -eu
read -r ANSWER

# RIGHT (set -u only, read with fallback):
set -u
read -r ANSWER || ANSWER=""
```

### Pattern: write to /tmp, verify, copy

```bash
cat > /tmp/script.sh << 'INNEREOF'    # heredoc works on ext4 (/tmp)
#!/usr/bin/env bash
# Pure ASCII content
INNEREOF
bash -n /tmp/script.sh && cp /tmp/script.sh "/media/USB/script.sh"
chmod +x "/media/USB/script.sh"
```

## Architecture Detection

```bash
HOST_ARCH="$(uname -m)"
case "$HOST_ARCH" in
  aarch64|arm64) ARCH="arm64"; DOCKER_PLATFORM="linux/arm64" ;;
  x86_64|amd64)  ARCH="x64";   DOCKER_PLATFORM="linux/amd64" ;;
esac
```

## Docker Image Strategy

| Component | ARM64 | x64 | Notes |
|-----------|-------|-----|-------|
| Docker image | `docker save \| gzip` | QEMU cross-build (limited) | x64 build skips npm (SIGSEGV) |
| node_modules | In ARM64 image | Extract from ARM64 (arch-independent JS) | Native modules (node-pty) need rebuild |
| Electron GUI | Pre-built binary | Pre-download zip to `~/.cache/electron/` | `ELECTRON_SKIP_BINARY_DOWNLOAD=1` |
| llama-server | Native build | Cross-compile: `x86_64-linux-gnu-g++` | CPU-only for x64 cross-compile |
| GGUF model | Same file | Same file | Architecture-independent |

## docker-compose.yml platform directive

```yaml
services:
  hermes:
    image: ${HERMES_IMAGE:-hermes-agent}
    platform: ${DOCKER_PLATFORM:-linux/amd64}
    ...
  dashboard:
    image: ${HERMES_IMAGE:-hermes-agent}
    platform: ${DOCKER_PLATFORM:-linux/amd64}
    ...
```

## sudo / docker permissions

`sudo ./launch.sh` → `REAL_HOME=/root` → connection.json in wrong directory.

Fix (one-time): `sudo usermod -aG docker $USER` → relogin → docker without sudo.

## GUI build from Docker image (cross-arch)

```bash
# Extract source + node_modules from ANY hermes-agent image
docker run --rm --entrypoint tar "$IMAGE" \
    -cf - -C /opt/hermes apps/desktop ui-tui web package.json \
    | tar -xf - -C /tmp/build

# node_modules (arch-independent JS)
docker run --rm --entrypoint tar "$IMAGE" \
    -cf - -C /opt/hermes node_modules \
    | tar -xf - -C /tmp/build

# Build in /tmp (NOT on exFAT USB!)
cd /tmp/build/apps/desktop
export GITHUB_SHA="local-build"
npm run build && npm run pack
```

## File layout on USB

```
hermes_portable_v1/
├── start-backend.sh     # Auto-arch detection, docker load
├── launch.sh            # GUI launcher (arch check + build prompt)
├── build-gui.sh         # Cross-arch GUI build from Docker image
├── chat.sh              # CLI fallback (curl-based, any arch)
├── stop.sh              # Stop containers + GUI
├── docker/
│   ├── hermes-agent-arm64.tar.gz
│   ├── hermes-agent-x64.tar.gz
│   └── docker-compose.yml   # Has platform: directive
├── gui/                 # Electron binary (ARM64 or built x64)
├── config/
│   └── config.docker.yaml
└── electron-v*.zip      # Pre-cached Electron for offline build
```
