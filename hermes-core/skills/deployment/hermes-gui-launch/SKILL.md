---
name: hermes-gui-launch
description: "Launch, fix, and diagnose the Hermes Electron Desktop GUI. Covers connection.json, dashboard-vs-gateway endpoint distinction, stale process/scope cleanup, and boot failure recovery."
category: deployment
version: 1.0.0
author: agent
triggers:
  - "запусти gui"
  - "почини gui"
  - "gui не запускается"
  - "launch desktop"
  - "fix electron"
  - "gui упал"
  - "desktop boot failed"
  - "connection.json"
  - "presets not working"
  - "agent presets"
  - "presets from gui"
  - "plan3 not activating"
  - "agents.activate fails"
---

# Hermes GUI Launch & Fix

> Launch and repair the Electron Desktop app. Use when GUI won't start, shows
> a blank screen, or connects to the wrong backend.

## Architecture — the #1 gotcha

GUI **does not connect to the gateway**. Two different servers, two different
endpoints, two different tokens:

```
Electron GUI ──► Dashboard (:9123) ──► Gateway (:18649)
                 has /api/status       has /health + /v1/*
                 has /api/ws (chat)    NO /api/status (returns 404!)
                 token: sk-docker-b    token: API_SERVER_KEY (64-char hex)
```

**connection.json MUST point to the dashboard port (:9123), NOT the gateway
port (:18649).** If it points to the gateway, Electron's `waitForHermes()`
calls `/api/status`, gets 404, and boot fails after 45s timeout with:
`Hermes backend did not become ready: 404: 404: Not Found`.

| What | Dashboard (:9123) | Gateway (:18649) |
|------|-------------------|------------------|
| `/api/status` | **200** ✅ | 404 ❌ |
| `/api/ws` (WebSocket) | **101** ✅ | 404 ❌ |
| `/health` | 200 | **200** ✅ |
| `/v1/chat/completions` | varies | **200** ✅ |
| Token | `sk-docker-b` (DASH_TOKEN) | API_SERVER_KEY (64 hex) |
| Purpose | GUI's real backend | LLM API only |

## Quick launch (when backend is already up)

```bash
# 1. Verify dashboard is alive
curl -sf http://localhost:9123/api/status | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(f'gw={d.get(\"gateway_running\")} v{d.get(\"version\")}')"

# 2. Kill old GUI by PID (NOT pkill — pkill kills your own terminal!)
ps -eo pid,args | grep "release/linux-.*-unpacked/Hermes" | grep -vE "grep|zygote|chrome-sandbox" \
  | awk '{print $1}' | while read pid; do kill "$pid" 2>/dev/null; done

# 3. Clean stale systemd scopes + singleton lock
for s in $(systemctl --user list-units --all 'app-org.chromium.Chromium-*.scope' --no-legend 2>/dev/null | awk '{print $1}'); do
  systemctl --user stop "$s" 2>/dev/null
done
rm -f ~/.config/Hermes/Singleton{Lock,Cookie,Socket} 2>/dev/null

# 4. Write connection.json (DASHBOARD port + DASH_TOKEN)
cat > ~/.config/Hermes/connection.json <<'EOF'
{
  "mode": "remote",
  "remote": {
    "url": "http://localhost:9123",
    "token": { "value": "sk-docker-b" },
    "authMode": "token"
  },
  "profiles": {}
}
EOF

# 5. Launch — on ARM64 (Jetson) MUST use --disable-gpu flags (see below)
ARCH=$(uname -m | sed 's/aarch64/arm64/;s/x86_64/x64/')
# Binary search: portable dir first, then standard install
for BIN in \
  "$(dirname "$0")/gui/linux-${ARCH}-unpacked/Hermes" \
  "$HOME/.hermes/hermes-agent/apps/desktop/release/linux-${ARCH}-unpacked/Hermes"; do
  [ -f "$BIN" ] && break
done
"$BIN" --disable-gpu --disable-software-rasterizer --no-sandbox &
```

## ⚠️ GPU crash on ARM64 (Jetson) — CRITICAL

On NVIDIA Jetson (ARM64, GB10, driver 580.x), Chromium's GPU sandbox
**crashes at startup** — `nvidia-smi` works fine, it's the Electron/Chromium
GPU process sandbox that's broken:

```
[PID:ERROR:content/browser/gpu/gpu_process_host.cc:998] GPU process launch failed: error_code=1002
[PID:ERROR:content/browser/gpu/gpu_process_host.cc:998] GPU process launch failed: error_code=1002
[PID:ERROR:content/browser/gpu/gpu_process_host.cc:998] GPU process launch failed: error_code=1002
[PID:FATAL:content/browser/gpu/gpu_data_manager_impl_private.cc:415] GPU process isn't usable. Goodbye.
```

This is a **FATAL crash** — Electron exits immediately. No window appears.

**Fix:** Always launch with these three flags on ARM64:
```bash
./Hermes --disable-gpu --disable-software-rasterizer --no-sandbox
```

- `--disable-gpu` — bypasses the Chromium GPU sandbox that crashes on ARM64
- `--disable-software-rasterizer` — prevents fallback to SwiftShader (also broken)
- `--no-sandbox` — disables the Chromium sandbox (Electron in dev/test mode)

**Without these flags, GUI will NOT start on Jetson.** This is NOT a
warning — it's a hard FATAL exit.

**For `start.sh gui`:** the script was patched on 2026-07-08 — all three bugs
below are FIXED in the current version. The function now writes `${PORT_DASH}`
(dashboard port), `${DASH_TOKEN}` (sk-docker-b), and launches with all three
GPU flags. The misleading comments at lines 664-666 were also corrected.

**Historical reference — TRIPLE BUG (FIXED 2026-07-08):** Three bugs existed
in `start_gui()` and were all fixed in the same patch:

| Bug | Was (wrong) | Now (correct) |
|-----|-------------|---------------|
| Port | `${PORT_GW}` (gateway :18649) | `${PORT_DASH}` (dashboard :9123) |
| Token | `${gw_api_key}` = API_SERVER_KEY (64-hex) | `${DASH_TOKEN}` = `sk-docker-b` |
| GPU flags | `--no-sandbox` only | `--disable-gpu --disable-software-rasterizer --no-sandbox` |

The comments at lines 664-666 previously **actively lied** (asserted gateway
port and API_SERVER_KEY were correct). They now correctly document dashboard
port and DASH_TOKEN.

If `start.sh gui` still produces boot failures, verify these three lines
haven't reverted (e.g. from a stale copy on USB drive).

## connection.json format — STRICT

```json
{
  "mode": "remote",
  "remote": {
    "url": "http://localhost:9123",
    "token": { "value": "sk-docker-b" },
    "authMode": "token"
  },
  "profiles": {}
}
```

**Pitfalls (each has caused a real boot failure):**
- `url` port MUST be **9123** (dashboard), not 18649 (gateway). Gateway has no `/api/status`.
- `token.value` MUST be the **DASH_TOKEN** (`sk-docker-b`), not the gateway's `API_SERVER_KEY` (64-char hex). Wrong token → `401: {"detail":"Unauthorized"}` on every API call.
- `token` is an **object** `{"value": "..."}`, not a bare string.
- Structure is nested: `{"remote": {"url": ...}}`, NOT flat `{"url": ...}`.
- To switch back to local mode (GUI spawns its own backend): `echo '{"mode":"local"}' > ~/.config/Hermes/connection.json`.

**⚠️ Electron rewrites connection.json to `mode: local` on close.** Every time
the GUI exits, it writes `mode: local` back into the file. This means if you
previously set up a remote connection.json, **you MUST re-write it to remote
mode before each launch** — otherwise GUI falls back to local mode and spawns
its own backend (ignoring your Docker dashboard entirely).

The Quick Launch and Recovery Script below both write connection.json as their
last step before launching, which is why they work reliably. If you only kill
the old GUI and re-launch the binary without re-writing connection.json first,
you'll get local mode.

**Extract DASH_TOKEN programmatically:**
```bash
DASH_TOKEN=$(grep '^HERMES_DASHBOARD_SESSION_TOKEN=' ~/.hermes-portable-dash/.env | cut -d= -f2)
```

## Diagnosis — when GUI won't start

### Step 1: Read the boot log

```bash
tail -40 ~/.hermes/logs/desktop.log
```

This file is the **single source of truth**. Electron's `rememberLog()` writes
here. Look for:

| Message | Meaning | Fix |
|---------|---------|-----|
| `Desktop boot failed: Hermes backend did not become ready: 404` | connection.json points to gateway, not dashboard | Change `url` port to 9123 |
| `Error: 401: {"detail":"Unauthorized"}` | Wrong token in connection.json | Use `sk-docker-b` (DASH_TOKEN) |
| `[boot] Connecting to remote Hermes backend at http://localhost:9123` then `Remote Hermes backend is ready` | Boot OK — if no window, it's a GPU/display issue | See "GPU crash on ARM64" above |
| `FATAL:content/browser/gpu/gpu_data_manager_impl_private.cc:415] GPU process isn't usable. Goodbye.` | **GPU sandbox crash (ARM64/Jetson)** — Chromium GPU process fails to start | Launch with `--disable-gpu --disable-software-rasterizer --no-sandbox` |
| `[boot] Resolving Hermes backend` / `Finding an open local port` / `Starting Hermes backend via existing Hermes CLI` | GUI fell back to LOCAL mode (connection.json missing or mode:local) | Write remote connection.json |
| `electron: Failed to load URL: http://loc/ ... ERR_NAME_NOT_RESOLVED` | Chromium DNS prefetch (cosmetic, NOT fatal) | Ignore |

### Step 2: Check if the process is even alive

```bash
ps -eo pid,lstart,args | grep "linux-.*-unpacked/Hermes" | grep -v grep | head -5
```

- **No processes** → Electron crashed at startup. Check `dmesg | tail` for OOM, check `~/.config/Hermes/Crashpad/` for `.dmp` files.
- **Main + zygote processes alive, but no window** → GPU/display problem or stale singleton lock.
- **Only `--type=utility` orphans (network/audio service)** → Previous instance left zombies. Kill them all and clean scopes.

### Step 3: Check window visibility

```bash
# wmctrl can return EMPTY even when the window exists!
# Always cross-check with xwininfo -root -tree:
xwininfo -root -tree 2>/dev/null | grep -i hermes
```

If empty but process is alive: GPU init failed. On ARM64 Jetson this is a
**FATAL crash**, not a soft failure — the entire Electron process dies with:
```
GPU process launch failed: error_code=1002
GPU process launch failed: error_code=1002   (repeated ~6x)
FATAL:content/browser/gpu/gpu_data_manager_impl_private.cc:415] GPU process isn't usable. Goodbye.
```

Note: `nvidia-smi` works fine (driver 580.142+) — this is Chromium's **GPU
sandbox** failing on ARM64, not a GPU hardware/driver problem.

Launch with fallback flags (ALL THREE required on ARM64 Jetson):
```bash
./Hermes --disable-gpu --disable-software-rasterizer --no-sandbox
```

## Cleanup — the 3 things that block a clean launch

> For the related `start.sh gui` triple bug (wrong port + wrong token +
> missing GPU flags), see `references/start-sh-triple-bug.md`.

### 1. Orphan Electron processes

**Never use `pkill -f Hermes`** — it sends SIGTERM to your own terminal shell
(matches the command line). Kill by specific PID:

```bash
ps -eo pid,args | grep "release/linux-.*-unpacked/Hermes" \
  | grep -vE "grep|zygote|chrome-sandbox" \
  | awk '{print $1}' | while read pid; do kill "$pid" 2>/dev/null; done
sleep 2
```

### 2. Stale systemd scopes

Electron creates `app-org.chromium.Chromium-<PID>.scope` via DBus. If a
previous instance crashed, the scope stays `active` and blocks the new one:

```
ERROR:dbus/object_proxy.cc:573] Failed to call method: ...UnitExists
```

Clean them:
```bash
for s in $(systemctl --user list-units --all 'app-org.chromium.Chromium-*.scope' --no-legend 2>/dev/null | awk '{print $1}'); do
  systemctl --user stop "$s" 2>/dev/null
done
```

### 3. SingletonLock

If Electron crashed hard, `~/.config/Hermes/SingletonLock` may persist and
prevent a new instance from acquiring the single-instance lock:

```bash
rm -f ~/.config/Hermes/Singleton{Lock,Cookie,Socket} 2>/dev/null
```

## Full recovery script

Run this when GUI is completely broken and you need a clean restart:

```bash
#!/bin/bash
# gui-recover.sh — full clean restart of Hermes Desktop GUI

set -e
ARCH=$(uname -m | sed 's/aarch64/arm64/;s/x86_64/x64/')
BIN="$HOME/.hermes/hermes-agent/apps/desktop/release/linux-${ARCH}-unpacked/Hermes"
DASH_TOKEN=$(grep '^HERMES_DASHBOARD_SESSION_TOKEN=' "$HOME/.hermes-portable-dash/.env" | cut -d= -f2)

echo "==> Checking dashboard :9123..."
if ! curl -sf http://localhost:9123/api/status >/dev/null 2>&1; then
  echo "✗ Dashboard not running. Start backend first:"
  echo "  cd ~/dev/hermes_portable && REAL_HOME=$HOME bash ./start.sh full --3models"
  exit 1
fi
echo "  ✅ Dashboard alive"

echo "==> Killing old GUI processes..."
ps -eo pid,args | grep "release/linux-.*-unpacked/Hermes" | grep -vE "grep|zygote|chrome-sandbox" \
  | awk '{print $1}' | while read pid; do kill "$pid" 2>/dev/null; done
sleep 2

echo "==> Cleaning stale scopes..."
for s in $(systemctl --user list-units --all 'app-org.chromium.Chromium-*.scope' --no-legend 2>/dev/null | awk '{print $1}'); do
  systemctl --user stop "$s" 2>/dev/null
done

echo "==> Removing singleton locks..."
rm -f "$HOME/.config/Hermes/SingletonLock" "$HOME/.config/Hermes/SingletonCookie" "$HOME/.config/Hermes/SingletonSocket" 2>/dev/null

echo "==> Writing connection.json → dashboard :9123..."
mkdir -p "$HOME/.config/Hermes"
cat > "$HOME/.config/Hermes/connection.json" <<EOF
{
  "mode": "remote",
  "remote": {
    "url": "http://localhost:9123",
    "token": { "value": "${DASH_TOKEN}" },
    "authMode": "token"
  },
  "profiles": {}
}
EOF

echo "==> Launching Hermes Desktop..."
# ARM64 Jetson: --disable-gpu is REQUIRED, not optional.
# Without it, Chromium GPU sandbox crashes (error_code=1002 → FATAL).
nohup "$BIN" --disable-gpu --disable-software-rasterizer --no-sandbox >/tmp/hermes-gui.log 2>&1 &
GUI_PID=$!
echo "  PID: $GUI_PID"

echo "==> Waiting for window..."
# NOTE: wmctrl -l can return empty even when the window exists.
# Cross-check with: xwininfo -root -tree 2>/dev/null | grep -i hermes
for i in $(seq 1 15); do
  sleep 1
  if xwininfo -root -tree 2>/dev/null | grep -qi '"Hermes"'; then
    echo "  ✅ Window visible after ${i}s"
    exit 0
  fi
done

echo "  ⚠️  No window after 15s. Check ~/.hermes/logs/desktop.log"
exit 1
```

## Building the GUI from source (offline)

When no pre-built binary exists for the target architecture (e.g. x64 machine
with only ARM64 binary on USB), build from source extracted from the Docker image:

1. Extract `apps/desktop` + `node_modules` from Docker image via tar
2. Copy Electron binary from cache (`gui/electron-v*-linux-*.zip`)
3. Build in `/tmp/` (NOT on exFAT — symlinks break)
4. `npm run build && npm run pack`

**Key constraints:**
- Build dir MUST be on ext4 (`/tmp/`), not exFAT — node_modules has symlinks
- Use `tar` pipe (not `cp -a` or Docker volume mount) to extract from image
- Set `ELECTRON_SKIP_BINARY_DOWNLOAD=1` when cache zip is available
- See `hermes-docker-deploy` skill → `references/offline-usb-deployment.md` for full pattern

## Building the GUI from source

When the unpacked binary doesn't exist or source code changed:

```bash
cd ~/.hermes/hermes-agent/apps/desktop

# Type-check only (fast)
npx tsc --noEmit

# Full build (tsc + vite -> dist/)
npm run build

# Package as unpacked app
npm run pack    # -> release/linux-<arch>-unpacked/Hermes

# Or via hermes CLI (builds + launches)
cd ~/.hermes/hermes-agent
./venv/bin/hermes desktop           # build + launch
./venv/bin/hermes desktop --skip-build  # use existing release/
```

Build artifacts: `apps/desktop/dist/` (web assets), `apps/desktop/release/linux-arm64-unpacked/Hermes` (packaged).

**Cross-architecture offline build** (x64 binary from ARM64 Docker image, no internet):
See `references/cross-arch-offline-build.md` — extract source from Docker image,
use cached Electron zip, build natively on target machine.

**node-pty cross-compilation** (build x64-ready node_modules on ARM64 host):
See `references/node-pty-cross-compile.md` — `npm ci` natively on ARM64 (fast),
then cross-compile only `node-pty` with `x86_64-linux-gnu-g++`, package as
`node_modules-x64.tar.gz`. This lets the x64 target build GUI with NO network.

## Cross-architecture: no GUI binary for target arch

**V2 FINAL WORKING PATTERN (2026-07-09) — pre-built dual-arch binaries:**

The definitive solution for portable offline deployment. Ship BOTH pre-built
Electron binaries (ARM64 + x64) on USB. `launch.sh` auto-selects at runtime
via `uname -m`. Target machine needs ZERO build tools — no Node.js, no npm,
no Python, no network.

```
hermes_portable_v2/
├── start-backend.sh     # Auto-arch Docker backend launcher
├── launch.sh            # Auto-arch GUI launcher (see script below)
├── chat.sh              # CLI fallback (python3-based)
├── stop.sh
├── docker/
│   ├── hermes-agent-arm64.tar.gz   (1.6G)
│   └── hermes-agent-x64.tar.gz     (810M, no web UI — QEMU limitation)
├── gui-arm64/Hermes     # Pre-built ARM64 ELF (344M)
└── gui-x64/Hermes       # Pre-built x64 ELF (339M)
```

**x64 binary built on Jetson (ARM64 host):**
```bash
cd ~/.hermes/hermes-agent/apps/desktop
ELECTRON_SKIP_BINARY_DOWNLOAD=1 npx electron-builder --dir --x64
# → release/linux-x64-unpacked/Hermes (ELF 64-bit, x86-64)
```
Requires cross-compiled node-pty: `CC=x86_64-linux-gnu-gcc CXX=x86_64-linux-gnu-g++ npx node-gyp rebuild --target_arch=x64`

**V2 launch.sh (WORKING — verified on x64 Kali 2026-07-09):**
```bash
#!/usr/bin/env bash
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REAL_HOME="${REAL_HOME:-$(getent passwd "$(id -u)" | cut -d: -f6)}"
[ -z "$REAL_HOME" ] && REAL_HOME="$HOME"

PORT_DASH="${PORT_DASH:-9123}"
DASH_TOKEN="${HERMES_DASHBOARD_SESSION_TOKEN:-sk-docker-b}"
HOST_ARCH="$(uname -m)"
case "$HOST_ARCH" in
  aarch64|arm64) ARCH="arm64" ;;
  x86_64|amd64)  ARCH="x64" ;;
  *) echo "ERROR: unsupported: $HOST_ARCH"; exit 1 ;;
esac

GUI_DIR="$SCRIPT_DIR/gui-$ARCH"
BIN="$GUI_DIR/Hermes"

# Check backend
curl -sf "http://localhost:$PORT_DASH/api/status" >/dev/null 2>&1 || {
    echo "ERROR: Dashboard not responding on :$PORT_DASH"
    exit 1
}

# Kill old GUI, clean locks
pgrep -f "gui-.*/Hermes" | xargs kill 2>/dev/null || true
sleep 2
rm -f "$REAL_HOME/.config/Hermes/SingletonLock" \
      "$REAL_HOME/.config/Hermes/SingletonCookie" \
      "$REAL_HOME/.config/Hermes/SingletonSocket" 2>/dev/null || true

# Write connection.json -> DASHBOARD (not gateway!)
CONN_DIR="$REAL_HOME/.config/Hermes"
mkdir -p "$CONN_DIR"
printf '{"mode":"remote","remote":{"url":"http://localhost:%s","token":{"value":"%s"},"authMode":"token"},"profiles":{}}\n' \
    "$PORT_DASH" "$DASH_TOKEN" > "$CONN_DIR/connection.json"

# Launch — GPU flags MANDATORY on ARM64, harmless on x64
"$BIN" --disable-gpu --disable-software-rasterizer --no-sandbox
```

**CRITICAL: This script MUST be written via terminal heredoc to /tmp/ then
`cp` to USB, NOT via `write_file` tool.** exFAT silently merges adjacent lines
(LINE MERGE). `write_file` itself does NOT corrupt files — but exFAT's line
merge is silent and `bash -n` does NOT catch it.

```bash
# On Jetson (ARM64), after npm run build + cross-compiled node-pty:
ELECTRON_SKIP_BINARY_DOWNLOAD=1 npx electron-builder --dir --x64
file release/linux-x64-unpacked/Hermes   # → ELF 64-bit, x86-64
```

Ship both binaries in `gui-arm64/` and `gui-x64/` dirs; `launch.sh` auto-selects.

**FALLBACK OPTIONS** (when no pre-built binary available):

1. **CLI chat fallback** — use a curl-based chat script through the gateway API:
   ```bash
   API_KEY=$(cat .api-key)
   curl -sf http://localhost:18649/v1/chat/completions \
     -H "Authorization: Bearer $API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model":"qwen3.6-35b-heretic","messages":[{"role":"user","content":"hello"}],"max_tokens":100}'
   ```

2. **Build GUI on-site** (requires network for npm):
   ```bash
   sudo apt install nodejs npm
   cd hermes-agent/apps/desktop && npm ci && npm run pack -- --linux
   ```

3. **Cross-build x64 Docker image** — see `references/cross-architecture-offline-deploy.md`
   for the full pattern: Docker buildx with QEMU (Node.js SIGSEGV workaround),
   Electron cache zip for offline install, llama-server cross-compile, and the
   `build-gui.sh` script that extracts source from Docker image + builds on-site.
   Key pitfall: **exFAT breaks bash heredocs** — always use `printf` in scripts
   stored on USB drives.

**Electron binaries are architecture-specific** (195MB each). Unlike GGUF models
or Python code, they cannot be shared between ARM64 and x64 deployments.

## Common failure matrix

| Symptom | Root cause | Fix |
|---------|-----------|-----|
| Process exits immediately with `FATAL: GPU process isn't usable. Goodbye` | **ARM64 GPU sandbox crash** (error_code=1002) | `--disable-gpu --disable-software-rasterizer --no-sandbox` — ALL THREE required |
| Boot fails: `404: Not Found` | connection.json → gateway :18649 | Change url to `:9123` |
| Boot OK, but API calls: `401: Unauthorized` | connection.json → right port, but wrong token (API_SERVER_KEY instead of DASH_TOKEN) | Use `sk-docker-b` (DASH_TOKEN) |
| Boot fails: `Connection error` after 3 retries | Dashboard volume config.yaml stale | `cp ~/.hermes-portable/config.yaml ~/.hermes-portable-dash/config.yaml; docker restart hermes-dashboard` |
| Process dies immediately with `GPU process launch failed: error_code=1002` then `FATAL: ... GPU process isn't usable. Goodbye` | Chromium GPU sandbox crash (ARM64 Jetson) | Launch with `--disable-gpu --disable-software-rasterizer --no-sandbox` |
| Process alive, no window, wmctrl empty | Stale lock OR wmctrl false-negative | Clean SingletonLock; cross-check with `xwininfo -root -tree` |
| `Failed to call method: ...UnitExists` | Stale systemd scope | Clean scopes (see above) |
| `ERR_NAME_NOT_RESOLVED` for `http://loc/` etc | Chromium DNS prefetch (harmless) | Ignore |
| `dri3 extension not supported` | GPU warning (harmless on headless) | Ignore |
| GUI falls back to local mode, spawns own backend | connection.json missing or `mode:local` | Write remote connection.json |
| Window opens but chat doesn't work | Dashboard volume config points to dead port/model | Sync config: see `hermes-docker-deploy` skill → "Dashboard volume config sync" |
| Window opens, agent presets don't work (model doesn't switch) | Docker backend missing agents/, stale config, or unpatched code | See "Agent presets not working" section + `references/docker-backend-preset-sync.md` |
| `start.sh gui` produces broken launch (404 + 401 + GPU crash) | **TRIPLE BUG in start_gui() — FIXED 2026-07-08.** If still broken, you're running a stale copy. Verify lines 672/674/690 have PORT_DASH, DASH_TOKEN, and --disable-gpu | Update start.sh from the patched source or use gui-recover.sh |

## Agent presets not working — Docker backend split-brain

**Symptom:** GUI boots fine, but selecting an agent preset (plan3, plan2, etc.)
in the sidebar does nothing. The model doesn't switch. Or: agent presets show
up but activating one silently fails.

**Root cause #1 — Docker backend has its own code, config, and agent registry.
Local patches to `~/.hermes/hermes-agent/` have ZERO effect on the Docker
dashboard.** The Docker container `hermes-dashboard` uses:
- Code at `/opt/hermes/` (inside container, image-baked)
- Config at `/opt/data/config.yaml` (volume: `~/.hermes-portable-dash/config.yaml`)
- Agents at `/opt/data/agents/` (volume: `~/.hermes-portable-dash/agents/`)
- `HERMES_HOME=/opt/data`

While the local install uses:
- Code at `~/.hermes/hermes-agent/`
- Config at `~/.hermes/config.yaml`
- Agents at `~/.hermes/agents/`
- `HERMES_HOME=~/.hermes`

**Diagnostic chain (5 steps — do ALL before concluding):**

```bash
# Step 1: Which backend does GUI connect to?
cat ~/.config/Hermes/connection.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('remote',{}).get('url','?'))"
# :9123 = Docker dashboard, :9120 = local dashboard

# Step 2: Does Docker volume have agents/?
ls ~/.hermes-portable-dash/agents/*.md 2>/dev/null | wc -l
# 0 = MISSING — copy from local:
#   cp -r ~/.hermes/agents ~/.hermes-portable-dash/agents

# Step 3: Does Docker config point to a LIVE endpoint?
docker exec hermes-dashboard python3 -c "
from hermes_cli.config import load_config
c = load_config()
m = c.get('model', {})
cp = c.get('custom_providers', [{}])[0]
print(f'provider={m.get(\"provider\")} default={m.get(\"default\")}')
print(f'base_url={cp.get(\"base_url\")} api_key={\"set\" if cp.get(\"api_key\") else \"MISSING\"}')"
# If base_url is dead (e.g. localhost:8092 when nothing listens there) → update config

# Step 4: Does Docker code have the provider patch?
docker exec hermes-dashboard grep -c "provider" /opt/hermes/agent/agents.py
# 0 or <5 = UNPATCHED — see references/docker-backend-preset-sync.md

# Step 5: Can Docker reach the LLM backend?
docker exec hermes-dashboard python3 -c "
import urllib.request, json
req = urllib.request.Request('http://localhost:4000/v1/models', headers={'Authorization':'Bearer sk-local'})
d = json.loads(urllib.request.urlopen(req, timeout=3).read())
print(f'{len(d[\"data\"])} models reachable')"
```

**Quick fix (when Docker volume is missing agents + config is stale):**
```bash
# 1. Copy agents to Docker volume
cp -r ~/.hermes/agents ~/.hermes-portable-dash/agents

# 2. Update Docker config.yaml (see references/docker-backend-preset-sync.md for template)

# 3. Apply code patches inside container (5 sed commands — see reference)

# 4. Restart dashboard
docker restart hermes-dashboard
sleep 10

# 5. Verify
docker exec hermes-dashboard python3 -c "
from agent.agents import load_agents
a = load_agents()
p3 = a.get('plan3')
print(f'{len(a)} agents, plan3: model={p3.model}, provider={p3.provider}' if p3 else 'plan3 NOT FOUND')"
```

**Full diagnostic + fix procedure including the 5 Docker code patches:**
See `references/docker-backend-preset-sync.md`.

**Verifying agent activation via WebSocket RPC:**
```python
import json, asyncio, websockets

async def test():
    async with websockets.connect("ws://localhost:9123/api/ws?token=sk-docker-b") as ws:
        await ws.recv()  # gateway.ready event
        await ws.send(json.dumps({"jsonrpc":"2.0","id":1,"method":"agents.list","params":{}}))
        data = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        agents = data.get("result",{}).get("agents",[])
        print(f"{len(agents)} agents")
        plan3 = [a for a in agents if a.get("id") == "plan3"]
        if plan3:
            print(f"plan3: model={plan3[0].get('model')}")

asyncio.run(test())
```

**Key pitfall:** Patches to Docker code via `docker exec sed -i` do NOT survive
container rebuild. For permanent fix, either bake patches into the Dockerfile or
mount the local code directory as a volume. See
`references/docker-backend-preset-sync.md` for the survival strategy.

## Writing scripts for exFAT / USB drives (CRITICAL)

When deploying scripts to exFAT-formatted USB drives (common for portable
deployments), these bash features BREAK silently:

| Feature | Symptom | Fix |
|---------|---------|-----|
| **Line merge (SILENT KILLER)** | Two adjacent lines silently merge into ONE line. Script LOOKS valid but semantically broken. `DASH_TOKEN=...` + `HOST_ARCH=$(uname -m)` become `DASH_TOKEN=... "$(uname -m)"` — bash tries to execute DASH_TOKEN value as command. With `set -u`, `HOST_ARCH` is now unbound → script exits SILENTLY (no error, no output, just dead). **THIS IS THE #1 exFAT FAILURE MODE.** | **MUST verify with `bash -n` AND visual `head -20` after EVERY write to exFAT.** `bash -n` passes because syntax is valid — the bug is semantic, not syntactic. Also: **use `terminal` heredoc to `/tmp/` then `cp` to USB, NOT `write_file` directly to USB.** |
| Heredoc (`<<EOF`) | `cat > file <<EOF` corrupts content, merges lines | Use `printf '...\n' > file` instead |
| UTF-8 chars (em-dash, Cyrillic, emoji) | Bytes mangled → syntax errors | Pure ASCII only in comments + echo |
| `cp -a` (preserve ownership) | `Operation not permitted` | Use `cp -r` or `tar` |
| `cp -a` (preserve symlinks) | `cp: cannot create symbolic link` | Use `cp -rL` (dereference) or `tar` |
| `set -eu` + `read -r` | If stdin closed (pipe/sudo), `read` returns 1 → script dies | Use `set -u` only, or `read -r X \|\| X=""` |
| **`read_file` shows redacted tokens (display-only)** | `read_file` applies `redact_sensitive_text(code_file=True)` on output (`file_tools.py:823`). Values like `sk-docker-b` → `***` in DISPLAY. File on disk has REAL content (verified: `write_file`/`patch` do NOT redact on write). Agent sees `***`, misdiagnoses as file corruption. | Understand `agent/redact.py:_mask_token()` — tokens < 18 chars → fully `***`. Use `terminal('grep ... file')` to see real content without redaction. |

**VERIFICATION PROTOCOL after writing ANY script to exFAT (MANDATORY):**
```bash
# 1. Syntax check (catches gross errors but NOT line merges!)
bash -n script.sh && echo "syntax OK"

# 2. Visual inspection (catches line merges — THIS is what finds the real bug)
head -20 script.sh | cat -n    # check line count matches expected

# 3. Dry run (catches semantic errors)
bash -x script.sh 2>&1 | head -30    # trace execution, verify variables set correctly

# 4. ALWAYS sync after writing to exFAT
sync && echo "synced"
```

**AUTOMATED VERIFICATION** — use `exfat_safe_write.sh` for 3-layer auto-check:
```bash
source ~/.hermes/scripts/exfat_safe_write.sh
exfat_safe_write /tmp/script.sh "/media/pavel/One Touch/hermes_portable_v2/script.sh"
# Auto-checks: line-count comparison + SHA256 hash + bash -n
# Retries up to 3 times if corruption detected
```

**REAL-WORLD EXAMPLE (2026-07-09):** `launch.sh` was written via `write_file` to exFAT USB. Two lines merged:
```
# EXPECTED (two lines):
DASH_TOKEN="${HERMES_DASHBOARD_SESSION_TOKEN:-sk-docker-b}"
HOST_ARCH="$(uname -m)"

# ACTUAL ON DISK (one line — exFAT LINE MERGE, DASH_TOKEN shown as *** by read_file redaction):
DASH_TOKEN=*** "$(uname -m)"

# RESULT: case "$HOST_ARCH" → set -u → "unbound variable" → SILENT EXIT
# USER SYMPTOM: ./launch.sh produces empty output, drops back to $ prompt
```
**Fix:** Re-wrote via `terminal` heredoc to `/tmp/`, then `cp` to USB. Verified with `head -18` and `bash -n`.

**Pattern:** Write script to `/tmp` first, verify with `bash -n`, THEN copy to USB:
```bash
cat > /tmp/script.sh << 'EOF'   # heredoc works on ext4
# script content
EOF
bash -n /tmp/script.sh && cp /tmp/script.sh "/media/USB/script.sh"
```

**Cross-architecture deployment (ARM64 → x64):**
- ARM64 Electron binary CANNOT run on x64 — `exec format error`
- x64 Docker image built via QEMU fails on npm/node (SIGSEGV)
- node_modules ARE arch-independent JS — extract from ARM64 image, rebuild native modules
- Electron x64 zip can be pre-downloaded and cached in `~/.cache/electron/`
- `docker-compose.yml` needs `platform: ${DOCKER_PLATFORM:-linux/amd64}` directive

## "Never do" list

- **Never** trust a script on exFAT without visual `head -N` inspection after writing — `bash -n` passes line-merged files (syntax is valid, semantics are broken). **Line merge is the #1 exFAT script killer.** Write to `/tmp/` first, then `cp` to USB.
- **Never** use `cat <<EOF` heredocs in scripts stored on exFAT (USB drives) — use `printf` instead. exFAT corrupts heredocs silently.
- **Never** put `start.sh stop` in the same script as `start.sh gui` — `stop`
  kills Docker containers seconds after launch, killing the backend the GUI
  just connected to.
- **Never** use `pkill -f Hermes` — it matches and kills your terminal.
- **Never** set connection.json `url` to the gateway port (:18649) — gateway
  doesn't serve `/api/status`.
- **Never** put the gateway's `API_SERVER_KEY` as the connection.json token —
  dashboard auth expects `HERMES_DASHBOARD_SESSION_TOKEN` (`sk-docker-b`).
- **Never** delete `~/.config/Hermes/` wholesale — it contains session state,
  cookies, local storage. Only delete `SingletonLock*`.
- **Never** trust a stale `start.sh` copy on USB — the triple bug (wrong port,
  wrong token, missing GPU flags) was **FIXED 2026-07-08** but old copies still
  circulate. If `start.sh gui` fails with 404/401/GPU crash, verify the file
  has been updated: lines 672/674/690 should have PORT_DASH, DASH_TOKEN,
  and `--disable-gpu --disable-software-rasterizer --no-sandbox`.
- **Never** trust `wmctrl -l` alone — it can return empty when a window exists.
  Cross-check with `xwininfo -root -tree 2>/dev/null | grep -i hermes`.
- **Never** launch without `--disable-gpu` on ARM64 Jetson — the GPU sandbox
  crash is FATAL and kills the entire Electron process.
- **Never** assume connection.json is still in remote mode from a previous
  session — Electron writes `mode: local` back on close. Always re-write it
  to remote mode before each launch.

## ⚠️ GUI hang during response — full recovery

GUI может зависнуть во время ответа (особенно с reasoning моделями на ARM64 —
GLM-5.2, qwen3.6). Симптомы: окно не реагирует, потом закрывается, повторный
запуск не работает.

**Root causes (3 фактора):**

1. **Electron сбрасывает connection.json** → при закрытии пишется `{"mode":"local"}`
2. **SingletonLock остаётся** → блокирует новый инстанс
3. **Stale systemd scopes** → cgroup занята старым процессом

**Полный алгоритм восстановления** (задокументирован в Quick Launch выше, но
подчёркиваю: ВСЕ 5 шагов обязательны, не пропускать ни один):

```bash
# 1. Backend должен быть жив (если Docker контейнеры умерли — перезапусти)
curl -sf http://localhost:9123/api/status || { echo "Backend DOWN"; exit 1; }

# 2. Убить старые процессы
ps -eo pid,args | grep "linux-.*-unpacked/Hermes" | grep -vE "grep|zygote" \
  | awk '{print $1}' | while read pid; do kill "$pid"; done
sleep 2

# 3. Очистить scopes + locks
for s in $(systemctl --user list-units --all 'app-org.chromium.Chromium-*.scope' --no-legend 2>/dev/null | awk '{print $1}'); do
  systemctl --user stop "$s" 2>/dev/null
done
rm -f ~/.config/Hermes/Singleton{Lock,Cookie,Socket}

# 4. Переписать connection.json (Electron сбросил в local!)
cat > ~/.config/Hermes/connection.json << 'EOF'
{"mode":"remote","remote":{"url":"http://localhost:9123","token":{"value":"sk-docker-b"},"authMode":"token"},"profiles":{}}
EOF

# 5. Запустить с GPU флагами
./Hermes --disable-gpu --disable-software-rasterizer --no-sandbox &
```

**Диагностика по desktop.log** — читать `~/.hermes/logs/desktop.log`:

| Сообщение | Причина | Fix |
|-----------|---------|-----|
| `Desktop boot failed: 404: Not Found` | connection.json → gateway порт | Поменять url на :9123 |
| `401: Unauthorized` | Неверный токен | Использовать sk-docker-b |
| `FATAL: GPU process isn't usable` | ARM64 GPU sandbox crash | `--disable-gpu --disable-software-rasterizer --no-sandbox` |
| `Resolving Hermes backend` / `Finding an open local port` | connection.json = local mode | Переписать в remote mode |
| `Remote Hermes backend is ready` + нет окна | GPU/display проблема | Проверить флаги, DISPLAY, xwininfo |

## Environment specifics (Pavel's machine)
- **Never** write scripts with heredocs (`<<EOF`) or UTF-8 characters (emoji,
  Cyrillic, em-dashes) to exFAT USB drives — exFAT corrupts both silently. Use
  `printf` and pure ASCII. See `hermes-docker-deploy` → `references/offline-usb-deployment.md`.

## Environment specifics (Pavel's machine)
## ⚠️ Writing scripts for exFAT USB drives (CRITICAL)

When writing deploy/launch scripts that will live on an exFAT-formatted USB
drive (e.g. `/media/pavel/One Touch/`), the following bash features BREAK:

| Feature | What happens | Fix |
|---------|-------------|-----|
| **Bash heredoc** (`<<EOF`) | exFAT mangles line endings or delimiter -> syntax error | Use `printf 'line1\nline2\n'` |
| **UTF-8 characters** (emoji, Cyrillic, em-dash) | Bytes get corrupted -> syntax error near token | Pure ASCII only — no checkmarks, no Cyrillic in echo |
| **Symlinks** (`cp -a`) | exFAT has no symlink support | Use `cp -rL` (dereference) or `tar` pipe |
| **`set -eu` + `read`** | If stdin is not a TTY, `read` returns 1 -> `set -e` kills script | Use `set -u` (no `-e`) and `read -r X \|\| X=""` |
| **`read_file` redaction** | Secret-like values shown as `***` in display (display-only, NOT file corruption). Use `terminal grep` to see raw file content. | Use `terminal('cat file')` to bypass display redaction |

**Pattern:** Write to `/tmp/` with full UTF-8 + heredocs, then `cp` to USB.
Or write directly in pure ASCII with printf.

**Note:** `scripts/gui-recover.sh` uses heredocs + emoji — it works on ext4
but will BREAK if copied to exFAT USB.

## x64 cross-architecture deployment

When deploying the ARM64-built GUI to an x64 machine (e.g. Kali/Ubuntu laptop):

**Full offline x64 build recipe**: see `references/offline-x64-gui-build.md` —
covers QEMU limitations, pre-packaged node_modules, Electron cache, node-pty
rebuild, and exFAT script-writing pitfalls.

1. **ARM64 binary CANNOT run on x64** — Electron is a native ELF binary. Must rebuild from source.
2. **x64 Docker image via QEMU buildx**: Node.js/npm SIGSEGV under QEMU emulation. Must skip npm steps in Dockerfile (`RUN true # npm skipped — QEMU SIGSEGV`). The x64 image will lack node_modules and web UI, but gateway works.
3. **node-pty is arch-specific**: the native `.node` binary in node_modules is ARM64-only. Must rebuild on target: `npm rebuild node-pty` (requires `build-essential python3`).
4. **Electron binary**: download separately for x64: `https://github.com/electron/electron/releases/download/v40.9.3/electron-v40.9.3-linux-x64.zip`
5. **Node.js 22 LTS required**: Node 24+ breaks Vite/TypeScript (V8 engine changes cause SIGSEGV).
6. **Offline build impossible without network**: if no internet, node_modules must be pre-packaged. JS packages are arch-independent, but native modules (node-pty) are not.

See `scripts/build-gui-offline.sh` for the offline build recipe.

## Writing scripts to exFAT USB drives — CRITICAL

exFAT (and FAT32) filesystems used by external USB drives **corrupt shell scripts**:

| Problem | Cause | Fix |
|---------|-------|-----|
| UTF-8 characters (cyrillic, emoji, em-dash `—`) | exFAT mangles multi-byte sequences | Write scripts in **pure ASCII only** |
| Bash heredocs (`<<EOF`) | exFAT breaks line endings in heredoc blocks | Use `printf` or `echo` instead |
| `cp -a` (preserve ownership) | exFAT has no Unix ownership model | Use `cp -r` (no `-a`) or `tar` |
| Symlinks in node_modules | exFAT doesn't support symlinks | Use `cp -rL` (dereference) or `tar` |
| `write_file` tool to exFAT path | Same encoding issues | Write to `/tmp` first, then `cp` to USB |

**Pattern for writing scripts to USB:** always write via terminal heredoc to `/tmp/`, verify with `bash -n`, then `cp` to USB:
```bash
cat > /tmp/script.sh << 'EOF'
#!/usr/bin/env bash
# Pure ASCII only — no cyrillic, no emoji, no em-dash
...
EOF
bash -n /tmp/script.sh && cp /tmp/script.sh "/media/pavel/One Touch/target/" && chmod +x "/media/pavel/One Touch/target/script.sh"
```

## User communication pattern: error reporting

When the user says "check the file" after an error, they may have **pasted the error text INTO the script file**. Always READ the file first and look for appended error output before writing fixes — otherwise you overwrite their error report.

## Environment specifics (Pavel's machine)

- Binary: `~/.hermes/hermes-agent/apps/desktop/release/linux-arm64-unpacked/Hermes`
- Dashboard: Docker container `hermes-dashboard` on :9123
- Gateway: Docker container `hermes-gateway` on :18649
- DASH_TOKEN: `sk-docker-b` (from `~/.hermes-portable-dash/.env`)
- Portable start script: `~/dev/hermes_portable/start.sh gui`
- Main entry: `apps/desktop/electron/main.cjs` (5762 lines)
- Boot timeout: 45s (`waitForHermes` in main.cjs:2970)
- Desktop log: `~/.hermes/logs/desktop.log` (rotated: `.1`, `.2`, `.3`)
- User data dir: `~/.config/Hermes/`
- start.sh triple bug (PORT_GW, wrong token, missing GPU flags) — **FIXED** lines 672/674/690

## Portable offline deployment (USB drives)

Full pattern for deploying Hermes to offline machines via USB (exFAT):
`references/portable-offline-deployment.md` — exFAT script constraints,
cross-arch Docker/Electron strategy, file layout, sudo/docker permission fix.

**Scripts:**
- `scripts/gui-recover.sh` — full clean restart of GUI (kill + clean + connection.json + launch)
- `scripts/download-deps.sh` — download x64 dependencies on a machine WITH internet
- `scripts/build-gui-offline.sh` — build GUI from pre-downloaded tar.gz, NO internet needed
- Portable USB packages: `/media/pavel/One Touch/hermes_portable_v1` (clean) and `hermes_portable` (full with GGUF+llama-server)

## Portable path resolution (USB deployment)

When running from a USB drive or portable directory, the GUI binary and
llama-server must be found via portable-path-first resolution:

```
Search order:
  1. $PORTABLE_DIR/gui/linux-${arch}-unpacked/Hermes     ← USB
  2. $REAL_HOME/.hermes/.../release/linux-${arch}-unpacked/Hermes  ← standard install
```

**exFAT limitation:** USB drives formatted as exFAT do NOT support SUID.
The `chrome-sandbox` SUID bit is lost on copy. Always use `--no-sandbox`
when launching from exFAT (already in the launch flags).

**start.sh `start_gui()` patched (2026-07-08):** The three original bugs are
now fixed in `start.sh`:
- Line ~672: `PORT_DASH` (was `PORT_GW`) → correct dashboard port
- Line ~674: `DASH_TOKEN` (was `gw_api_key`) → correct dashboard token
- Line ~690: `--disable-gpu --disable-software-rasterizer --no-sandbox` (was `--no-sandbox` only)
- Comments at lines 664-666 rewritten to state the correct behavior
