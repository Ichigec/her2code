# Dashboard Auth Mechanics — How REST & WebSocket Auth Really Work

> Condensed from 2026-06-22 debugging session. Source: `hermes_cli/web_server.py`.

## Two auth paths, one token

Dashboard has a single session token (`_SESSION_TOKEN`) stored in module-level variable,
read from `HERMES_DASHBOARD_SESSION_TOKEN` env var (default: `secrets.token_urlsafe(32)`).

### REST API auth (`auth_middleware`)

```python
# web_server.py lines 228-245
def _has_valid_session_token(request: Request) -> bool:
    # PRIMARY: X-Hermes-Session-Token header (the header desktop GUI uses)
    session_header = request.headers.get("X-Hermes-Session-Token", "")
    if session_header and hmac.compare_digest(
        session_header.encode(), _SESSION_TOKEN.encode()
    ):
        return True
    # LEGACY: Authorization: Bearer <token> (for backward compat)
    auth = request.headers.get("authorization", "")
    expected = f"Bearer {_SESSION_TOKEN}"
    return hmac.compare_digest(auth.encode(), expected.encode())
```

**Key:** Both headers work. Desktop GUI sends `X-Hermes-Session-Token` (see `main.cjs:2339`).
`Authorization: Bearer` is a legacy fallback.

### WebSocket auth (`_ws_auth_reason`)

```python
# web_server.py lines 8342-8423
def _ws_auth_reason(ws: "WebSocket") -> tuple[Optional[str], str]:
    # Loopback / --insecure: legacy ?token=<token> query parameter
    token = ws.query_params.get("token", "")
    if not token:
        return "no_credential", "none"
    if hmac.compare_digest(token.encode(), _SESSION_TOKEN.encode()):
        return None, "token"
    return "token_mismatch", "token"
```

**Key:** WebSocket uses `?token=` query param, NOT headers. No `Authorization`, no `X-Hermes-Session-Token`.

### FastAPI middleware DOES NOT apply to WebSocket routes

This is critical for debugging:

```python
# web_server.py line 8313
# FastAPI HTTP middleware does not run for WebSocket routes, so the
```

`auth_middleware` is registered with `@app.middleware("http")` — HTTP only.
WebSocket auth is handled EXCLUSIVELY by `_ws_auth_ok()` → `_ws_auth_reason()`.
If WebSocket returns 403/401, the problem is in `_ws_auth_reason`, NOT in `auth_middleware`.

## Auth modes

| Mode | Trigger | REST auth | WS auth |
|------|---------|-----------|---------|
| **loopback / `--insecure`** | `auth_required: false` | `X-Hermes-Session-Token` or `Authorization: Bearer` | `?token=` query param |
| **OAuth gated** | `auth_required: true` | Cookie-based (HttpOnly session) | `?ticket=` (single-use, 30s TTL) or `?internal=` (server-spawned) |

## Pitfall: 401 despite correct token

GUI may log 401 errors during boot even with correct `HERMES_DESKTOP_REMOTE_TOKEN`.
Possible causes:

1. **Race condition in `startHermes()`**: `connectionPromise` is cached. If first call to
   `resolveRemoteBackend()` happens before env vars are fully resolved, subsequent calls
   use stale (null/empty) token. Not confirmed but plausible.

2. **`connection.json` pollution**: `readDesktopConnectionConfig()` returns `{"mode":"local"}`
   but env vars should override this (priority 2 of 3 in `resolveRemoteBackend`).

3. **Desktop shell's own connection.json**: When `HERMES_DESKTOP_REMOTE_URL` is set, the
   shell skips `connection.json`. But per-profile overrides in `connection.json` could
   still shadow env vars.

**Workaround (not confirmed):** Delete `~/.config/Hermes/connection.json` before starting
GUI with env vars. Or use per-profile remote in `connection.json` instead of env vars.

## Verification commands

```bash
# REST with X-Hermes-Session-Token (what GUI uses)
curl -H "X-Hermes-Session-Token: *** http://localhost:9119/api/sessions

# REST with Authorization: Bearer (legacy)
curl -H "Authorization: Bearer *** http://localhost:9119/api/sessions

# WebSocket (raw HTTP upgrade)
python3 -c "
import socket, base64, os
s=socket.socket(); s.connect(('127.0.0.1',9119)); s.settimeout(5)
k=base64.b64encode(os.urandom(16)).decode()
s.sendall(f'GET /api/ws?token=sk-local HTTP/1.1\\r\\nHost: localhost:9119\\r\\nUpgrade: websocket\\r\\nConnection: Upgrade\\r\\nSec-WebSocket-Key: {k}\\r\\nSec-WebSocket-Version: 13\\r\\n\\r\\n'.encode())
print('101' if b'101' in s.recv(4096) else 'FAIL')
"
```
