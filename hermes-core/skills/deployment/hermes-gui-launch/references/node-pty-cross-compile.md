# node-pty Cross-Compilation: ARM64 → x64

> How to build x64-ready node_modules on an ARM64 host, including the one
> native module (node-pty), so the target x64 machine needs NO network.

## The Problem

`node_modules` from an ARM64 Docker image contains `node_modules/node-pty/build/Release/pty.node`
compiled as an ARM64 ELF. When the x64 target machine runs `npm run build`,
the `stage-native-deps.cjs` script tries to load this `.node` file and crashes
with `wrong ELF class: ELFCLASS64` (ARM64 on x64 mismatch).

Without network, `npm rebuild node-pty` fails (can't download source).

## The Solution: Cross-Compile node-pty Only

JS packages (vite, react, typescript, etc.) are architecture-independent.
Only `pty.node` needs recompiling. Cross-compile it with `x86_64-linux-gnu-g++`.

### Step 1: npm ci on ARM64 (native, fast ~12s)

```bash
# Extract source from Docker image
docker run --rm --entrypoint tar hermes-agent:latest \
    -cf - -C /opt/hermes package.json package-lock.json apps ui-tui web \
    | tar -xf - -C /tmp/hermes-src

cd /tmp/hermes-src
npm ci --prefer-offline --no-audit --no-fund
# → 1325 packages installed
```

### Step 2: Cross-compile node-pty for x64

```bash
cd /tmp/hermes-src/node_modules/node-pty

# Install cross-compiler if not present:
# sudo apt install gcc-x86-64-linux-gnu g++-x86-64-linux-gnu

CC=x86_64-linux-gnu-gcc CXX=x86_64-linux-gnu-g++ \
    npx node-gyp rebuild --target_arch=x64
```

This produces `build/Release/pty.node` as an **x86-64 ELF**.

Verify:
```bash
file build/Release/pty.node
# → ELF 64-bit LSB shared object, x86-64, version 1 (SYSV), dynamically linked
```

### Step 3: Stage for electron-builder

```bash
mkdir -p /tmp/hermes-src/apps/desktop/build/native-deps/node-pty/build/Release/
cp /tmp/hermes-src/node_modules/node-pty/build/Release/pty.node \
   /tmp/hermes-src/apps/desktop/build/native-deps/node-pty/build/Release/
```

### Step 4: Package for USB

```bash
cd /tmp
tar -czf node_modules-x64.tar.gz \
    hermes-src/package.json \
    hermes-src/package-lock.json \
    hermes-src/node_modules \
    hermes-src/apps \
    hermes-src/ui-tui \
    hermes-src/web \
    --transform 's|hermes-src|hermes-agent|g'
# → ~589 MB
```

### Step 5: On x64 target (offline)

```bash
# Extract to /tmp (NOT exFAT USB!)
mkdir -p /tmp/hermes-build
tar -xzf node_modules-x64.tar.gz -C /tmp/hermes-build

# Electron from cache
cp electron-v40.9.3-linux-x64.zip ~/.cache/electron/
export ELECTRON_SKIP_BINARY_DOWNLOAD=1

# Build
cd /tmp/hermes-build/hermes-agent/apps/desktop
export GITHUB_SHA="local-build"
npm run build
npm run pack
# → release/linux-x64-unpacked/Hermes
```

## Why This Works

| Component | Architecture-independent? | Action |
|-----------|:---:|--------|
| JS packages (vite, react, etc.) | Yes | Extract from ARM64 image, use as-is |
| node-pty (`pty.node`) | **No** | Cross-compile with `x86_64-linux-gnu-g++` |
| Electron binary | **No** | Pre-download x64 zip, cache in `~/.cache/electron/` |
| GGUF models | Yes | Same file on both architectures |
| llama-server | **No** | Cross-compile or use pre-built per-arch binary |

## Pitfalls

| Pitfall | Fix |
|---------|-----|
| `assert-root-install.cjs` fails: "Run from repo root" | node_modules must be at `../../node_modules/` relative to `apps/desktop/` |
| Node.js 24 breaks Vite (SIGSEGV) | Install Node.js 22 LTS specifically |
| `write_file` tool corrupts content on exFAT | Write to `/tmp` first, then `cp` to USB |
| `stage-native-deps.cjs` can't find pty.node | Must be in `apps/desktop/build/native-deps/node-pty/build/Release/pty.node` |
| x64 Docker image (QEMU build) lacks node_modules entirely | This is expected — QEMU SIGSEGV on npm. Use the tar.gz approach instead. |

## Alternative: download-deps.sh (machine WITH internet)

If the target machine can briefly access the internet, use `download-deps.sh`
to clone hermes-agent, run `npm ci` natively on x64, and package:

```bash
# On x64 machine WITH internet:
./download-deps.sh
# → downloads-x64/node_modules-x64.tar.gz (native x64, no cross-compile needed)
# → downloads-x64/electron-v40.9.3-linux-x64.zip

# Then on x64 machine WITHOUT internet:
./build-gui-offline.sh
```
