# Dashboard vs TUI Gateway: Observer Method Gap

**Discovered:** 2026-06-29, session with user reporting "Deep Analyse Now button does nothing."

## The Gap

The Hermes GUI (Electron desktop app) connects to `hermes dashboard` (FastAPI web server on port 9120), NOT to the TUI gateway. Observer mutation methods exist ONLY in `tui_gateway/server.py` — the dashboard's `hermes_cli/web_server.py` only has the read-only `GET /api/observers/recent` endpoint.

## Connection topology

```
Hermes GUI (Electron)
    ↓ WebSocket JSON-RPC
hermes dashboard (port 9120, FastAPI)
    hermes_cli/web_server.py
    ├── GET /api/observers/recent     ✅ read-only
    ├── observer.analyze              ❌ NOT REGISTERED
    ├── observer.toggle               ❌ NOT REGISTERED
    └── observer.status               ❌ NOT REGISTERED
```

vs where these methods actually live:

```
tui_gateway/server.py (separate server, NOT loaded by dashboard)
    ├── @method("observer.analyze")   ✅ line 3444
    ├── @method("observer.toggle")    ✅ line 3417
    └── @method("observer.status")    ✅ line 3433
```

## User-visible symptoms

| Button | Calls | Result |
|--------|-------|--------|
| "Deep Analyse Now" | `requestGateway('observer.analyze', ...)` | Silent failure — method not found on dashboard |
| ON/OFF toggle | `requestGateway('observer.toggle', ...)` | Silent failure — method not found on dashboard |
| Observer status refresh | `requestGateway('observer.status', ...)` | Silent failure — config atom falls back to stale default |

The ObserverPanel code in `apps/desktop/src/app/shell/observer-panel.tsx` catches errors silently (lines 54-58, 100-103), so the user sees nothing happen.

## Why it appears to "sometimes work"

- The toggle works via local state fallback: if the gateway call fails, the `catch` block flips `cfg.enabled` in the atom anyway (line 82).
- The initial config fetch (`useEffect` at line 67-73) reads from `$observerConfig` defaults if `observer.status` fails.
- So the panel UI can toggle and appear functional even though no actual server-side mutation occurs.

## Root cause

The dashboard web server (`hermes_cli/web_server.py`) was built as a FastAPI HTTP server for static file serving + session management. It never registered the JSON-RPC `observer.*` methods because those were added later in `tui_gateway/server.py` (a different server process used by the TUI and gateway CLI).

## Fix options

1. **Port methods to dashboard** — Add `observer.analyze`, `observer.toggle`, `observer.status` as WebSocket message handlers in `hermes_cli/web_server.py`, mirroring the implementations from `tui_gateway/server.py:3417-3495`.

2. **Proxy through dashboard → internal gateway** — Dashboard acts as a proxy, forwarding unknown JSON-RPC methods to the TUI gateway (if running).

3. **Connect GUI to TUI gateway instead** — Change the desktop connection to point at the TUI gateway rather than the dashboard. Breaks the single-process model.

Option 1 is the simplest: the dashboard already has a WebSocket handler; the three methods are self-contained (~50 lines each) and only depend on `ObserverManager` + `delegate_task` — both already importable from the dashboard process.
