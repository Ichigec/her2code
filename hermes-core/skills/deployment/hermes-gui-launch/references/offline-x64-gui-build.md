# Offline x64 GUI Build — Complete Recipe

## Problem

ARM64 Electron binary cannot run on x64. Cross-compilation via QEMU fails
(Node.js SIGSEGV). Must build x64 GUI on target or from pre-packaged deps.

## Prerequisites (on target x64 machine)

```bash
sudo apt install docker.io build-essential python3
# Node.js 22 LTS (NOT v24+ — breaks Vite)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
```

## Option A: Build with network (simplest)

```bash
# Extract source from Docker image
mkdir -p /tmp/hermes-build
docker run --rm --entrypoint tar hermes-agent:amd64 \
    -cf - -C /opt/hermes . | tar -xf - -C /tmp/hermes-build

cd /tmp/hermes-build
npm ci                    # downloads all deps for x64
cd apps/desktop
npm run build             # tsc + vite
npm run pack              # electron-builder --dir
# Result: release/linux-x64-unpacked/Hermes
```

## Option B: Build offline from pre-packaged node_modules

### Prepare on machine WITH internet:
```bash
git clone https://github.com/NousResearch/hermes-agent.git
cd hermes-agent && npm ci
cd ..
tar -czf node_modules-x64.tar.gz \
    hermes-agent/package.json \
    hermes-agent/package-lock.json \
    hermes-agent/node_modules \
    hermes-agent/apps \
    hermes-agent/ui-tui \
    hermes-agent/web

curl -L -o electron-v40.9.3-linux-x64.zip \
    https://github.com/electron/electron/releases/download/v40.9.3/electron-v40.9.3-linux-x64.zip
```

### Build on target WITHOUT internet:
```bash
# Extract pre-packaged deps
tar -xzf node_modules-x64.tar.gz -C /tmp/hermes-build

# Electron cache (prevents download)
mkdir -p ~/.cache/electron
cp electron-v40.9.3-linux-x64.zip ~/.cache/electron/
export ELECTRON_SKIP_BINARY_DOWNLOAD=1

# Rebuild native module for x64 (node-pty)
cd /tmp/hermes-build/hermes-agent
npm rebuild node-pty

# Build
cd apps/desktop
GITHUB_SHA=local-build npm run build
GITHUB_SHA=local-build npm run pack
```

## Common failures

| Error | Cause | Fix |
|-------|-------|-----|
| `QEMU internal SIGSEGV` | Running Node under QEMU x86_64 | Build on real x64 hardware, not via buildx |
| `wrong ELF class` / `cannot execute binary file` | ARM64 binary on x64 host | Rebuild from source on x64 |
| `node:internal/main/run_main_module` crash | Node.js v24+ V8 incompatibility | Install Node.js 22 LTS |
| `EAI_AGAIN registry.npmjs.org` | No network for npm ci | Use pre-packaged node_modules-x64.tar.gz |
| `assert-root-install.cjs` fails | Not in monorepo root | Ensure package.json + node_modules at `../../` from apps/desktop |
| `cp: failed to preserve ownership` | exFAT filesystem | Use `cp -r` not `cp -a`, or build in /tmp |

## exFAT script writing

When writing bash scripts to USB (exFAT), UTF-8 characters get corrupted.
Always write via terminal heredoc to /tmp, verify, then cp:
```bash
cat > /tmp/script.sh << 'EOF'
#!/usr/bin/env bash
# Pure ASCII only
EOF
bash -n /tmp/script.sh && cp /tmp/script.sh /media/USB/
```
