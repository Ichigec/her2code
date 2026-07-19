# tui_gateway ModuleNotFoundError — Root Cause of 95% Hang

> Discovered 2026-06-22. Previously attributed to WebSocket 400/403, missing
> API endpoints, or proxy issues. The real cause is simpler and dumber.

## Symptom

GUI gets stuck at 95% during boot. The boot sequence shows:
- 24% → passes (`/api/status` OK)
- 95% → stuck forever (`gateway.connect()` never completes)

Dashboard logs show:

```
File "/opt/hermes/hermes_cli/web_server.py", line 8749, in gateway_ws
    from tui_gateway.ws import handle_ws
ModuleNotFoundError: No module named 'tui_gateway'
```

WebSocket `/api/ws?token=...` returns HTTP 500 (or 403/closed without explanation in older versions).

## Root Cause

`docker cp ~/.hermes/hermes-agent/tui_gateway hermes-dashboard:/opt/hermes/tui_gateway`
copies files to disk but Python's import system can't find them.

The dashboard's `web_server.py` does `from tui_gateway.ws import handle_ws`.
Python searches `sys.path` for a `tui_gateway/` directory — `/opt/hermes/tui_gateway/`
is NOT on `sys.path` by default.

## Fix (Two Steps)

### Step 1: Copy to persistent volume (survives container restarts)

```bash
tar -C ~/.hermes/hermes-agent -c tui_gateway/ | \
  docker exec -i hermes-dashboard tar -C /opt/data -x
```

### Step 2: Add PYTHONPATH to docker run

```bash
docker run ... -e PYTHONPATH=/opt/data ...
```

Now Python can `import tui_gateway` because `/opt/data/tui_gateway/` is found via `sys.path`.

## Verification

```bash
# Inside container
docker exec hermes-dashboard python3 -c "from tui_gateway.ws import handle_ws; print('OK')"

# WebSocket test from host
python3 -c "
import socket, base64, os
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('127.0.0.1', 9119))
key = base64.b64encode(os.urandom(16)).decode()
req = 'GET /api/ws?token=sk-local HTTP/1.1\r\nHost: localhost:9119\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: ' + key + '\r\nSec-WebSocket-Version: 13\r\n\r\n'
sock.sendall(req.encode())
resp = sock.recv(4096)
print('WS:', '101' if b'101' in resp else resp.decode()[:200])
sock.close()
"
```

Expected: `WS: 101`

## Why `docker cp` to `/opt/hermes/tui_gateway` Doesn't Work

The container's working directory (`/opt/hermes`) is not automatically on `sys.path`.
Python imports search:
1. Current directory (of the running process, not where files live)
2. `PYTHONPATH` entries
3. Standard library
4. site-packages

`/opt/hermes` is none of these. The fix puts `tui_gateway` under `/opt/data` (on `PYTHONPATH`).

## Why This Is Persistent

`/opt/data` is a Docker volume (`--volumes-from hermes-test` or `-v` mount).
Files there survive container `stop`/`rm`/`restart`.

The `PYTHONPATH=/opt/data` env var needs to be set on EVERY `docker run`,
but that's a trivial one-liner in the startup command.

## Failed Approaches

| Approach | Why Failed |
|----------|-----------|
| `docker cp` to `/opt/hermes/tui_gateway` | Not on Python path |
| Symlink from site-packages | Lost on container restart |
| `docker cp` to site-packages directly | Works but lost on restart (site-packages in container FS) |
| Rebuilding Docker image with tui_gateway | Requires internet (blocked in Russia) |
| Proxy workaround (status-proxy.py) | Symptom treatment, doesn't fix real issue |

## Related: FastAPI Middleware Doesn't Apply to WebSocket

FastAPI's `@app.middleware("http")` (including `auth_middleware`) only applies to
HTTP routes. WebSocket routes use `@app.websocket("/api/ws")` which has its own
auth via `_ws_auth_ok()` checking `?token=` query parameter.

This is why:
- REST API: needs `X-Hermes-Session-Token: sk-local` header (OR `Authorization: Bearer sk-local` — both accepted by `_has_valid_session_token()`)
- WebSocket: needs `?token=sk-local` query param (no header needed)

The dual-header check in `_has_valid_session_token()`:
```python
session_header = request.headers.get("X-Hermes-Session-Token", "")  # primary
if session_header and hmac.compare_digest(session_header, _SESSION_TOKEN):
    return True
auth = request.headers.get("authorization", "")  # legacy fallback
expected = f"Bearer {_SESSION_TOKEN}"
return hmac.compare_digest(auth.encode(), expected.encode())
```

Electron main process uses `X-Hermes-Session-Token` (see `main.cjs:2339`), so
the GUI works with `--insecure` + simple token without `Authorization` header.
