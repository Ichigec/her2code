# Observer REST API Endpoint

`GET /api/observers/recent?limit=N&session_id=SID`

Serves observer findings from Neo4j to the desktop GUI ObserverPanel.

## Location

`hermes_cli/web_server.py` — FastAPI endpoint added after `get_profiles_sessions`.

## Queries

Fetches from Neo4j:
- `(:AuditFinding)` nodes — ordered by `timestamp DESC`
- `(:CriticFinding)` nodes — ordered by `timestamp DESC`
- `(:Session)` status counts — `pending_observer_review`, `observer_reviewed`, `skipped_observer`

When `session_id` is provided, filters both queries to that session.

## Auth Bypass

**CRITICAL**: The endpoint must be in `dashboard_auth/public_paths.py`:
```python
PUBLIC_API_PATHS: frozenset[str] = frozenset({
    "/api/status",
    "/api/config/defaults",
    "/api/config/schema",
    "/api/model/info",
    "/api/dashboard/themes",
    "/api/dashboard/plugins",
    "/api/observers/recent",  # ← ADD THIS
})
```

Without this, the endpoint returns **401 Unauthorized** for all requests. The `window.hermesDesktop.api()` in Electron sends auth headers, but loopback requests with `Host: localhost` bypass auth for public paths only.

## CORS Issue with `fetch()`

**DO NOT use `fetch()` from the Electron renderer** to call this endpoint. The dashboard returns:
```
access-control-allow-origin: http://localhost:5174
```
which only matches the Vite dev server, NOT the Electron app origin. `fetch()` calls are blocked by CORS.

**USE `window.hermesDesktop.api()` instead** — it proxies through the Electron main process via IPC, avoiding CORS entirely:
```ts
window.hermesDesktop.api<ObserverData>({
  path: `/api/observers/recent?limit=20&session_id=${encodeURIComponent(sessionId)}`,
  timeoutMs: 10000
})
```

If `window.hermesDesktop.api` is unavailable (race condition on mount), retry after 300ms. Maximum 2 retries before showing error.

## Response format

```json
{
  "findings": [
    {
      "session_id": "20260627_202849_0a0c69",
      "finding": "state.db grew to 805MB with 538 sessions...",
      "severity": "MEDIUM",
      "timestamp": "2026-06-27T21:30:00Z",
      "preset": "unknown",
      "type": "audit"
    }
  ],
  "total_findings": 5,
  "status_counts": {
    "active": 1,
    "observer_reviewed": 70,
    "pending_observer_review": 85,
    "skipped_observer": 7
  }
}
```

## Testing

```bash
# Without auth (must work if public_paths is set)
curl -s "http://127.0.0.1:9120/api/observers/recent?limit=3&session_id=SID"

# Should return findings, not {"detail":"Unauthorized"}
```
