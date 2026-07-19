# GUI Connection Architecture, Rebuild, and Multi-Backend Testing

Reference for how the Electron desktop GUI connects to backends, how to rebuild
it from source, and how to run/test against multiple backends.

---

## Connection Architecture (3 layers)

The desktop GUI does NOT connect to the gateway directly. There are three layers:

```
mode: "local" (default):
  Electron GUI ──WS──► Dashboard (:9120, /api/ws + /api/status)
                         ↑ spawned by Electron          │
                         │                               ▼
                         └────────────► Gateway (:8643, /v1/chat/completions + /health)
                                          ↑ spawned by Dashboard / hermes gateway run

mode: "remote":
  Electron GUI ──WS──► Remote Dashboard (:port, must be running separately)
                         │
                         ▼
                         Remote Gateway (:port, must be running separately)
```

### Key distinction: Dashboard ≠ Gateway

| Component | Port | Endpoints | Purpose |
|-----------|------|-----------|---------|
| **Dashboard** | 9120 (auto 9120-9199) | `/api/ws` (WebSocket upgrade), `/api/status`, `/api/sessions`, `/api/agents` | GUI-facing API, session management, plugin hooks |
| **Gateway** (api_server) | 8643 (default 8642) | `/v1/chat/completions`, `/health` | OpenAI-compatible REST API for external clients |

The GUI's WebSocket connects to **Dashboard** (`/api/ws`), NOT to Gateway.
Dashboard internally routes to Gateway for LLM calls.

### Connection config file

`~/.config/Hermes/connection.json`:

```json
// Local mode (default)
{"mode": "local"}

// Remote mode (token auth)
{
  "mode": "remote",
  "remote": {
    "url": "http://127.0.0.1:9121",
    "authMode": "token",
    "token": "<session-token>"
  },
  "profiles": {}
}

// Per-profile remote override
{
  "mode": "local",
  "remote": {},
  "profiles": {
    "codewar": {
      "mode": "remote",
      "url": "http://remote-host:9121",
      "authMode": "token",
      "token": "<token>"
    }
  }
}
```

### Env var override (no file edit needed)

```bash
HERMES_DESKTOP_REMOTE_URL=http://127.0.0.1:9121 \
HERMES_DESKTOP_REMOTE_TOKEN=<token> \
hermes gui --skip-build
```

Resolution precedence (in `main.cjs` `resolveRemoteBackend()`):
1. Per-profile override (`connection.json` `profiles[name]`)
2. Env vars (`HERMES_DESKTOP_REMOTE_URL` + `HERMES_DESKTOP_REMOTE_TOKEN`)
3. Global remote (`connection.json` `mode: 'remote'`)

### Switching back to local

```bash
echo '{"mode": "local"}' > ~/.config/Hermes/connection.json
```

Or via Settings → Gateway → Mode: Local in the GUI.

---

## Rebuild Pipeline

### Prerequisites

- Node.js 20.19+ or 22.12+ (`node --version`)
- npm 10+
- Python 3 + make + g++ (for node-pty compilation on Linux)

### Build steps

```bash
cd ~/.hermes/hermes-agent/apps/desktop

# 1. Type check
npm run type-check          # tsc -b

# 2. Full build (tsc + vite + stage native deps)
npm run build               # ~3s, produces dist/

# 3a. Package Electron app (unpacked, for local use)
npm run pack                # electron-builder --dir

# 3b. OR use hermes CLI (auto-detects stale build)
hermes gui --build-only --force-build

# 4. Launch (after build)
hermes gui --skip-build     # skip rebuild, use existing
```

### What each step does

| Step | Command | Output | Updates running app? |
|------|---------|--------|---------------------|
| Type check | `npm run type-check` | (no files) | No |
| Vite build | `npm run build` | `dist/assets/index-*.js` (22MB) | No (dist only) |
| Electron-builder | `npm run pack` | `release/linux-arm64-unpacked/Hermes` | On next `hermes gui` restart |
| Hermes CLI | `hermes gui --force-build` | Same as above + launches | Yes |

### node-pty (only native dependency)

`node-pty` is the ONLY native module. Prebuilds exist for macOS and Windows;
Linux compiles from source.

| Platform | Arch | Mechanism | Prebuilt? |
|----------|------|-----------|-----------|
| macOS | arm64 | `prebuilds/darwin-arm64/pty.node` | ✅ |
| macOS | x64 | `prebuilds/darwin-x64/pty.node` | ✅ |
| Windows | x64 | `prebuilds/win32-x64/conpty.node` | ✅ |
| Windows | arm64 | `prebuilds/win32-arm64/conpty.node` | ✅ |
| Linux | arm64 | `build/Release/pty.node` (compiled) | ❌ compile |
| Linux | x64 | `build/Release/pty.node` (compiled) | ❌ compile |

`scripts/stage-native-deps.cjs` copies the target arch's prebuilt/compiled
binary into `build/native-deps/` during `npm run build`. Electron-builder
ships it via `extraResources` → `resources/native-deps/`.

### Cross-architecture build (ARM64 → x64)

```bash
# Option A: Docker cross-compile
docker run --rm --platform linux/amd64 \
  -v ~/.hermes/hermes-agent:/repo \
  node:22-bookworm-slim \
  bash -c "cd /repo/apps/desktop && npm install && npm run build && npm run dist:linux"

# Option B: On-target build (if you have x64 machine)
npm run build && npm run dist:linux
```

### Build verification

```bash
# Check build stamp
cat apps/desktop/build/install-stamp.json
# → {"commit": "...", "builtAt": "...", "source": "local"}

# Check native deps staged
find apps/desktop/build/native-deps -name "*.node"

# Check Electron binary
ls -la apps/desktop/release/linux-arm64-unpacked/Hermes
```

### Backup before rebuild

```bash
BACKUP=~/dev/codemes/gui-backup-$(date +%Y%m%d)
mkdir -p "$BACKUP"
cp -r apps/desktop/release/linux-arm64-unpacked "$BACKUP/electron-app"
cp -r apps/desktop/dist "$BACKUP/dist"
cp -r apps/desktop/build "$BACKUP/build"
# Save metadata
cat > "$BACKUP/BACKUP_METADATA.json" << 'EOF'
{"commit": "...", "builtAt": "...", "arch": "linux-arm64"}
EOF
```

### Rollback (frontend only — don't touch backend)

```bash
rm -rf apps/desktop/release/linux-arm64-unpacked
cp -r "$BACKUP/electron-app" apps/desktop/release/linux-arm64-unpacked
cp -r "$BACKUP/dist" apps/desktop/dist
# Backend is untouched — just restart GUI
hermes gui --skip-build
```

---

## Running a Second Backend

To test GUI against a different backend (e.g., `.hermes-docker/`):

### 1. Create separate HERMES_HOME with different port

```bash
mkdir -p /tmp/hermes-backend2
cp ~/.hermes-docker/config.yaml /tmp/hermes-backend2/
cp ~/.hermes-docker/.env /tmp/hermes-backend2/
# Change API_SERVER_PORT to avoid conflict with primary (:8643)
sed -i 's/API_SERVER_PORT=8643/API_SERVER_PORT=18648/' /tmp/hermes-backend2/.env
```

**Pitfall:** `.env` file's `API_SERVER_PORT` OVERRIDES shell env vars.
Setting `API_SERVER_PORT=18648` as a shell var won't work if `.env` also
has `API_SERVER_PORT=8643`. Always edit the `.env` file or use a separate
`HERMES_HOME` with its own `.env`.

### 2. Start gateway for second backend

```bash
HERMES_HOME=/tmp/hermes-backend2 \
  ~/.hermes-docker/hermes-agent/venv/bin/hermes gateway run &
```

Verify: `curl http://127.0.0.1:18648/health` → `{"status":"ok"}`

### 3. Start dashboard for second backend

```bash
HERMES_HOME=/tmp/hermes-backend2 \
  ~/.hermes-docker/hermes-agent/venv/bin/hermes dashboard \
  --port 9121 --host 127.0.0.1 --no-open --skip-build
```

The dashboard provides `/api/ws` and `/api/status` that the GUI needs.

### 4. Connect GUI to second backend

**Via Settings UI:** Settings → Gateway → Remote → URL: `http://127.0.0.1:9121`

**Via connection.json:**
```json
{
  "mode": "remote",
  "remote": {
    "url": "http://127.0.0.1:9121",
    "authMode": "token",
    "token": "<extracted-from-dashboard>"
  }
}
```

### Extracting the dashboard session token

**The token is NOT in `/api/status`.** That endpoint returns config/gateway state
but no token field. The `auth_required: false` in the response means auth is
disabled — but the GUI's remote mode still requires a token in `connection.json`.

The token is an **ephemeral session token** generated at dashboard startup
(`web_server.py:183`):
```python
_SESSION_TOKEN = os.environ.get("HERMES_DASHBOARD_SESSION_TOKEN") or secrets.token_urlsafe(32)
```

It is injected into the SPA HTML at `web_server.py:9080`:
```python
f'<script>window.__HERMES_SESSION_TOKEN__="{_SESSION_TOKEN}";'
```

**Method 1 — Extract from HTML** (after dashboard is running):
```bash
curl -s http://127.0.0.1:9121/ | grep -oP '__HERMES_SESSION_TOKEN__="\K[^"]*'
# → chvbgrOlNuit6l-iNTVE69To4spf6SGZfTmTwd-IC-s
```

**Method 2 — Set your own token at startup** (more reliable):
```bash
HERMES_HOME=/tmp/hermes-backend2 \
HERMES_DASHBOARD_SESSION_TOKEN=my-fixed-token-123 \
  hermes dashboard --port 9121 --host 127.0.0.1 --no-open --skip-build
```
Then use `my-fixed-token-123` as the token in `connection.json`.

**Verify token works:**
```bash
# REST API with token header
curl -s http://127.0.0.1:9121/api/sessions \
  -H "X-Hermes-Session-Token: <token>" | python3 -m json.tool

# WebSocket upgrade with token
# (should return HTTP/1.1 101 Switching Protocols)
node -e "
const net = require('net');
const sock = net.connect(9121, '127.0.0.1', () => {
  sock.write('GET /api/ws?token=<token> HTTP/1.1\r\nHost: 127.0.0.1:9121\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n');
});
sock.on('data', d => { console.log(d.toString().split('\r\n')[0]); sock.destroy(); });
setTimeout(() => process.exit(0), 3000);
"
```

**Pitfall:** The token changes every time the dashboard restarts. If you
extracted it from HTML, it becomes stale on restart. For persistent setups,
use Method 2 (fixed token via env var).

**Via env vars:**
```bash
HERMES_DESKTOP_REMOTE_URL=http://127.0.0.1:9121 \
HERMES_DESKTOP_REMOTE_TOKEN=<token> \
hermes gui --skip-build
```

### 5. Verify LLM works on second backend

```bash
# Get API_SERVER_KEY from .env
KEY=$(grep API_SERVER_KEY /tmp/hermes-backend2/.env | cut -d= -f2)

curl -s -X POST http://127.0.0.1:18648/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $KEY" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"Reply: OK"}],"max_tokens":10}'
```

If LLM calls fail but health check passes → API keys in second backend's
`.env` are stale/commented. Copy working keys from primary `.env`.

---

## Process verification checklist

After any GUI rebuild or backend switch, verify the full chain:

```bash
# 1. All processes alive
ps aux | grep -E "hermes|Hermes|gateway|dashboard" | grep -v grep

# 2. Backend health
curl -s http://127.0.0.1:8643/health    # primary
curl -s http://127.0.0.1:18648/health   # secondary (if running)

# 3. Dashboard status
curl -s http://127.0.0.1:9120/api/status | python3 -m json.tool

# 4. GUI ↔ Dashboard WebSocket active
ss -tnp | grep 9120    # should show ESTAB connections

# 5. Agent log shows activity
tail -5 ~/.hermes/logs/agent.log

# 6. Send a test message IN THE GUI and check response
#    (This is the ONLY real end-to-end test — health checks alone are insufficient)
```

**Critical lesson:** Health check OK ≠ GUI working. A health check only
verifies the gateway process responds. The full chain (GUI → Dashboard WS →
Gateway → LLM → response back) must be exercised by actually sending a
message and receiving a response through the GUI.

---

## hermes_portable architecture gap

The `hermes_portable` package (35 architecture artifacts: C4 L1-L4, 9 D2
diagrams, 10 ADRs, 6 fitness functions) does NOT document the GUI layer at
all. Desktop Electron app, Dashboard, and TUI Gateway are completely absent
from all architecture diagrams. Only backend components (CLI, Gateway,
AIAgent, Tools, Plugins, State Store) are described.

If updating `hermes_portable` architecture docs, add:
- C4 L2: `Desktop Electron App` and `Dashboard` containers
- D2 diagram: `desktop-connection-architecture.d2` showing the 3-layer split
- ADR: connection.json local vs remote mode decision
