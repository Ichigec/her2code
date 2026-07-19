# GUI + Docker: Root Cause Analysis (2026-06-21)

## Key Discovery: `HERMES_DISABLE_MESSAGING=1` is a GHOST VARIABLE

System Analyst searched the entire Hermes codebase — **0 references**. This env var was invented during the Docker setup and never verified. It has no effect. Telegram is NOT disabled by it.

## Why GUI Doesn't Work With Docker

**Architecture mismatch**: 
- Docker runs `hermes gateway run` → provides REST API (health, models, chat via REST)
- Desktop GUI requires `hermes dashboard` → provides WebSocket (`/api/ws`) and `/api/status`
- Without dashboard, GUI hangs at 24% (no `/api/status`) and 95% (no WebSocket)

**Proxy approach was unnecessary**: Desktop `main.cjs` already uses `/health` (was patched). The API server natively has `/health`, `/api/sessions`, `/v1/chat/completions`. The `status-proxy.py` was a symptom treatment — it added stubs that masked the real issue (missing dashboard).

**Dashboard launch**: Dashboard can be launched as a separate container sharing volumes with gateway:
```bash
docker run -d --name hermes-dashboard --network host \
  --volumes-from hermes-test \
  -e HERMES_UID=1000 -e HERMES_GID=1000 \
  -e HERMES_DASHBOARD_SESSION_TOKEN=*** \
  hermes-agent dashboard --host 127.0.0.1 --port 9119 --no-open
```

**WebSocket limitation (2026-06-21)**: Dashboard on port 9119 returns HTTP 400 on WebSocket upgrade requests. GUI requires WebSocket for chat functionality. This is a known limitation — without fixing the WebSocket handshake in the dashboard, GUI+Docker can only do REST API chat, not full GUI interaction.

## Dashboard Endpoint Test Results

| Endpoint | Status | Notes |
|----------|:------:|-------|
| `/api/status` | 200 OK | Full status JSON with gateway_running=true |
| `/api/sessions` | 200 OK | Returns session list (with auth token) |
| `/api/logs` | 200 OK | Returns GUI logs |
| `/api/agents` | 404 | Not available |
| `/api/ws` | 400 | WebSocket upgrade fails |
| `/health` | 200 | Returns HTML page (React SPA), not JSON |

## Testing-First Methodology

Pavel's requirement: NEVER ask user to launch GUI without first testing all endpoints via curl. Test sequence:
1. Verify Docker health: `curl localhost:18648/health`
2. Verify proxy health: `curl localhost:18649/api/status`
3. Verify chat via REST: `curl -X POST localhost:18648/v1/chat/completions`
4. Verify dashboard (if used): `curl localhost:9119/api/status`
5. Only THEN give user the GUI launch command
