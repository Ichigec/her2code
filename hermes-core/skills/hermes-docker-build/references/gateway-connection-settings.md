# Gateway Connection Settings — Quick Reference

> Manual gateway/dashboard connection settings for GUI remote mode, testing, and debugging.

## Backend A (Local — primary Hermes)

| Setting | Value |
|---------|-------|
| Gateway URL | `http://127.0.0.1:8643` |
| Dashboard URL | `http://127.0.0.1:9120` |
| HERMES_HOME | `/home/user/.hermes` |
| API_SERVER_KEY | `<YOUR_HARDCODED_TOKEN>` |
| Dashboard flags | (none — spawned by GUI in local mode) |
| connection.json mode | `"local"` |

## Backend B (Docker — second Hermes)

| Setting | Value |
|---------|-------|
| Gateway URL | `http://127.0.0.1:18648` |
| Dashboard URL | `http://127.0.0.1:9121` |
| HERMES_HOME | `/tmp/hermes-backend2` |
| API_SERVER_KEY | `<YOUR_HARDCODED_TOKEN>` |
| Dashboard Session Token | `sk-docker-b` |
| Dashboard flags | `--insecure` (REQUIRED for token auth) |
| connection.json mode | `"remote"` |

## connection.json Formats

File: `~/.config/Hermes/connection.json`

### Local mode (GUI spawns dashboard + gateway)

```json
{"mode": "local"}
```

### Remote mode (GUI connects to external dashboard)

```json
{
  "mode": "remote",
  "remote": {
    "url": "http://127.0.0.1:9121",
    "token": {"value": "sk-docker-b"},
    "authMode": "token"
  },
  "profiles": {}
}
```

**Critical format rules:**
- `token` must be an **object** `{"value": "..."}`, NOT a string. String → `decryptDesktopSecret()` returns `""` → 401 on all REST.
- `remote` must be a **nested object**, NOT flat. Flat structure → `config.remote = {}` → undefined URL.
- `url` points to **Dashboard** (not Gateway). Dashboard provides `/api/ws` and `/api/status`; Gateway only has `/health`.

## One-liner Switch Commands

```bash
# → Local
python3 -c "import json; p='/home/user/.config/Hermes/connection.json'; json.dump({'mode':'local'}, open(p,'w'))"

# → Docker (Backend B)
python3 -c "import json; p='/home/user/.config/Hermes/connection.json'; json.dump({'mode':'remote','remote':{'url':'http://127.0.0.1:9121','token':{'value':'sk-docker-b'},'authMode':'token'},'profiles':{}}, open(p,'w'), indent=2)"
```

After switching: restart GUI (`hermes gui --skip-build` or kill+relaunch Electron).

## Starting Backend B + Dashboard B

```bash
# 1. Gateway (Backend B)
HERMES_HOME=/tmp/hermes-backend2 \
  /home/user/.hermes-docker/hermes-agent/venv/bin/hermes gateway run &

# 2. Dashboard B (MUST use --insecure for token auth)
cd ~/.hermes/hermes-agent && \
HERMES_HOME=/tmp/hermes-backend2 \
HERMES_DASHBOARD_SESSION_TOKEN=sk-docker-b \
  /home/user/.hermes-docker/hermes-agent/venv/bin/hermes dashboard \
    --port 9121 --host 127.0.0.1 --no-open --insecure &
```

**Why `--insecure`:** Without it, `/api/sessions`, `/api/agents`, etc. return 401 even with correct `X-Hermes-Session-Token` header. `--insecure` enables simple token auth for remote desktop clients.

**Why `HERMES_DASHBOARD_SESSION_TOKEN`:** Sets the expected token value. GUI sends this as `X-Hermes-Session-Token` header and `?token=` query param for WebSocket.

## Verifying Backend B

```bash
# Gateway health
curl -s http://127.0.0.1:18648/health
# → {"status": "ok", "platform": "hermes-agent"}

# Dashboard status
curl -s http://127.0.0.1:9121/api/status
# → {"auth_required": false, "gateway_state": "running", ...}

# REST API with token
curl -s -H 'X-Hermes-Session-Token: sk-docker-b' http://127.0.0.1:9121/api/sessions
# → {"sessions": []}

# LLM test
KEY=$(grep '^API_SERVER_KEY=' /tmp/hermes-backend2/.env | cut -d= -f2)
curl -s --max-time 10 -X POST http://127.0.0.1:18648/v1/chat/completions \
  -H "Authorization: Bearer $KEY" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'
```

## Pitfalls

### `--skip-build` fails after GUI rebuild

After `build-gui.sh` rebuilds the desktop app, `hermes dashboard --skip-build` fails:
```
✗ --skip-build was passed but no web dist found at:
  .../release/linux-arm64-unpacked/resources/app.asar/dist
```

**Fix:** Run `npm run build -w web` first, or omit `--skip-build` (dashboard will build web dist itself, ~30s extra).

### Dashboard B started without `--insecure` → 401 on REST

```
curl -s -H 'X-Hermes-Session-Token: sk-docker-b' http://127.0.0.1:9121/api/sessions
→ {"detail": "Unauthorized"}
```

**Fix:** Kill dashboard, restart with `--insecure` and `HERMES_DASHBOARD_SESSION_TOKEN=sk-docker-b`.

### `.env` overrides `API_SERVER_PORT` env var

Setting `API_SERVER_PORT=18648` on the command line does NOT work if `.env` contains `API_SERVER_PORT=8643`. The `.env` is loaded by python-dotenv AFTER command-line env vars, overriding them.

**Fix:** Create a separate HERMES_HOME with its own `.env` (e.g., `/tmp/hermes-backend2/.env` with `API_SERVER_PORT=18648`).
