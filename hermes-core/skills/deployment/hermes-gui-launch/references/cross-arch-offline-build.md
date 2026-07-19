# Cross-Architecture Offline GUI Build

> Building x64 Electron GUI on an ARM64 host (or vice versa), WITHOUT internet.

## Problem

Portable USB package contains an ARM64 Electron binary. When plugged into an
x64 machine, the binary cannot run ("exec format error"). No internet to
download x64 Electron. The x64 Docker image was cross-compiled via QEMU but
QEMU SIGSEGV's on `npm install` (Node.js doesn't survive QEMU emulation).

## Method 1 (PREFERRED): Cross-build on Jetson with electron-builder --x64

**Discovery (2026-07-09):** `electron-builder` can cross-build a working x64
ELF binary **directly on the ARM64 Jetson**, with NO QEMU, NO network on the
target, and NO Node.js on the target machine. This is strictly better than
Method 2 (build on target).

### Prerequisites on Jetson (ARM64 build host)
- Node.js 22 LTS (NOT 24 — breaks Vite)
- Pre-built source: `apps/desktop` + `node_modules` with cross-compiled `node-pty`
- Electron x64 zip in cache: `~/.cache/electron/electron-v40.9.3-linux-x64.zip`

### Steps

```bash
# 1. Ensure node-pty is cross-compiled for x64 (see node-pty-cross-compile.md)
#    pty.node must be x86-64 ELF in apps/desktop/build/native-deps/

# 2. Install x64 Electron zip into cache (if not already there)
cp electron-v40.9.3-linux-x64.zip ~/.cache/electron/

# 3. Cross-build x64 binary on ARM64 host
cd /tmp/hermes-build/hermes-agent/apps/desktop
ELECTRON_SKIP_BINARY_DOWNLOAD=1 npx electron-builder --dir --x64

# 4. Verify the output is actually x86-64
file release/linux-x64-unpacked/Hermes
# → ELF 64-bit LSB executable, x86-64, version 1 (SYSV), dynamically linked

# 5. Copy to USB portable package
cp -r release/linux-x64-unpacked "/media/USB/hermes_portable_v2/gui-x64/"
```

### Why this works
- `electron-builder --x64` packages the pre-built web assets (dist/) + the
  cached x64 Electron zip + the x64 node-pty binary into an unpacked dir.
- It does NOT run anything via QEMU — it's a packaging step, not a build step.
- The web assets (HTML/JS/CSS) are arch-independent.
- Only node-pty needs pre-cross-compilation (see `node-pty-cross-compile.md`).

### Key advantage over Method 2
The x64 target machine needs **ZERO build tools** — no Node.js, no npm, no
python3, no build-essential. Just copy the binary and run it.

### Pitfall: build/native-deps must have x64 pty.node
If `apps/desktop/build/native-deps/node-pty/build/Release/pty.node` is ARM64,
the packaged binary will crash on x64 with `wrong ELF class`. Always verify:
```bash
file apps/desktop/build/native-deps/node-pty/build/Release/pty.node
# Must show: ELF 64-bit LSB shared object, x86-64
```

## Method 2 (FALLBACK): Extract + Rebuild from Docker Image on Target

The Docker image contains the full Hermes source tree at `/opt/hermes/`,
including `apps/desktop/`, `ui-tui/`, `web/`, and `package.json`. By
extracting these and running `npm run build && npm run pack` NATIVELY on the
target machine, we get a correct-arch binary without internet.

### Prerequisites on target machine
- Docker (to extract source from image)
- Node.js >= 22 + npm (`sudo apt install nodejs npm`)
- python3, make, g++ (for node-pty compilation)

### Electron Binary Cache

The one piece npm can't install offline is the Electron binary itself (~115MB).
Solution: pre-download the Electron zip for the target arch and ship it on the
USB drive. The zip is at:
```
https://github.com/electron/electron/releases/download/v40.9.3/electron-v40.9.3-linux-x64.zip
```
Place in `gui/electron-v40.9.3-linux-x64.zip`. The build script copies it to
`~/.cache/electron/` and sets `ELECTRON_SKIP_BINARY_DOWNLOAD=1`.

### Build Script Flow (embedded in launch.sh `build_gui()` function)

```
1. Find Docker image: docker images | grep hermes-agent
2. Extract source: docker run --entrypoint tar IMAGE -cf - -C /opt/hermes apps/desktop ... | tar -xf - -C /tmp/build
3. Extract node_modules (if present in image): same tar pipe
4. Install Electron from cache zip -> ~/.cache/electron/
5. cd /tmp/build/apps/desktop
6. npm ci --prefer-offline (if node_modules incomplete)
7. npm run build (tsc + vite)
8. npm run pack (electron-builder --dir)
9. Copy release/linux-x64-unpacked/ -> gui/
```

### Key Pitfalls

| Pitfall | Fix |
|---------|-----|
| QEMU SIGSEGV on npm/node inside Docker x64 cross-build | Build NATIVELY on target machine, not via Docker/QEMU |
| `BUILD_DIR` on exFAT — symlinks in node_modules break | Build in `/tmp/` (ext4), not on USB |
| Docker `cp` loses symlinks | Use `docker run --entrypoint tar -cf - \| tar -xf -` |
| Electron download fails (no network) | Pre-cache zip on USB, set `ELECTRON_SKIP_BINARY_DOWNLOAD=1` |
| x64 Docker image missing node_modules (QEMU skipped npm) | `npm ci --prefer-offline` on target machine (needs network once) |

### Dockerfile.x64 Cross-Build Patch

For building x64 Docker image FROM ARM64 host (gateway-only, no web UI):
```dockerfile
# Skip npm + playwright + web build (QEMU SIGSEGV on Node.js)
RUN true # npm+playwright skipped
RUN true # web+ui-tui build skipped
# Fix chown (node_modules doesn't exist)
RUN chmod -R a+rX /opt/hermes && chown -R hermes:hermes /opt/hermes/.venv /opt/hermes/ui-tui /opt/hermes/gateway
```
Build: `docker buildx build --platform linux/amd64 -t hermes-agent:x64 -f Dockerfile.x64 --load .`

The resulting image runs gateway + dashboard but has NO web UI bundle.
The dashboard will serve but `/` returns no frontend. API endpoints work fine.
