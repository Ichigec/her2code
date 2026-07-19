# Docker Dashboard + GUI Launch Recipe (2026-06-21 verified)

## Source
Official Hermes Agent docs: https://hermes-agent.nousresearch.com/docs/user-guide/desktop
Community: https://sudolabs.nz/blog/how-to-connect-the-hermes-desktop-app-to-a-remote-hermes-backend-the-clean-way

## Architecture

Desktop GUI (Electron) → dashboard (:9119) via HTTP/WebSocket → gateway (:18648) via shared volume state.db

## Commands

### 1. Gateway container
```bash
cd her2code
docker compose up -d
for i in $(seq 1 90); do curl -sf localhost:18648/health && break; sleep 2; done
```

### 2. Dashboard container (CRITICAL: --tui --insecure)
```bash
docker run -d --name hermes-dashboard --network host \
  --volumes-from hermes-test \
  -e HERMES_UID=1000 -e HERMES_GID=1000 \
  -e HERMES_DASHBOARD_SESSION_TOKEN=*** \
  hermes-agent dashboard --host 127.0.0.1 --port 9119 \
    --insecure --tui --no-open --skip-build
```

### 3. Copy tui_gateway/ (CRITICAL - missing from Docker image)
```bash
docker cp ~/.hermes/hermes-agent/tui_gateway hermes-dashboard:/opt/hermes/tui_gateway
```
Without this: /api/ws returns HTTP 500 (ModuleNotFoundError)

### 4. Wait for dashboard
```bash
for i in $(seq 1 90); do curl -sf http://127.0.0.1:9119/api/status >/dev/null 2>&1 && break; sleep 2; done
```

### 5. Verify ALL 7 endpoints BEFORE launching GUI
- /api/status → 200 with gateway_running=true
- /api/sessions → 200 with token auth
- /api/logs → 200
- /api/ws → HTTP 101 Switching Protocols
- /health → 200 (HTML, not JSON - normal)
- /api/config → 200
- /api/agents → 404 (not blocking)

### 6. Launch GUI (only after all 7 verified)
```bash
env HERMES_DESKTOP_REMOTE_URL=http://localhost:9119 \
    HERMES_DESKTOP_REMOTE_TOKEN=*** \
    ELECTRON_EXTRA_LAUNCH_ARGS="--no-sandbox" \
    ~/.hermes/hermes-agent/apps/desktop/release/linux-arm64-unpacked/Hermes \
    --user-data-dir=/tmp/hermes-gui-docker
```

## Key Discoveries
1. Dashboard, not gateway - GUI connects to :9119 not :18648
2. --tui flag enables WebSocket for chat
3. --insecure flag enables token auth for remote desktop
4. tui_gateway/ missing from Docker image - must copy from host
5. Proxy (status-proxy.py) unnecessary when using dashboard
6. --user-data-dir does NOT affect connection.json - use env vars for isolation
