# GUI Isolation Launch — Docker Hermes

> How to launch a separate Desktop GUI instance connected to Docker Hermes
> without conflicting with the host's main Hermes GUI.

## Problem

The host already has a Hermes Desktop GUI running (connected to host Hermes on port 8643).
Launching a second GUI instance connected to Docker (port 18648) requires isolation.

## Key discovery: connection.json location

GUI ALWAYS reads `connection.json` from `~/.config/Hermes/connection.json`
(or per-profile override). `--user-data-dir` does NOT affect where connection.json
is read — it only isolates cache, sessions, settings.

DO NOT overwrite `~/.config/Hermes/connection.json` — it will break the host GUI.

## Solution: env vars (higher priority than connection.json)

Priority chain (from source code):
1. Per-profile override
2. `HERMES_DESKTOP_REMOTE_URL` + `HERMES_DESKTOP_REMOTE_TOKEN` env vars
3. `connection.json`

Use env vars to override for Docker without touching connection.json.

## Launch command

```bash
BIN=~/.hermes/hermes-agent/apps/desktop/release/linux-arm64-unpacked/Hermes
DATA=/tmp/hermes-gui-docker
mkdir -p "$DATA"

env HERMES_DESKTOP_REMOTE_URL=http://localhost:18649 \
    HERMES_DESKTOP_REMOTE_TOKEN=... \
    ELECTRON_EXTRA_LAUNCH_ARGS="--no-sandbox" \
    "$BIN" --user-data-dir="$DATA"
```

## Why proxy on :18649, not direct :18648

Direct connection to Docker :18648 fails at 24% — GUI waits for `/api/status`,
Docker gateway only has `/health`. Proxy adds `/api/status` stub.

See `scripts/status-proxy.py` for the full proxy with all needed stubs.

## Pitfalls

- GPU crash from background: `GPU process isn't usable` — Electron needs `$DISPLAY`.
  Can only launch from interactive terminal, not from `terminal(background=true)`.
- `connection.json` in `--user-data-dir` is NOT read for connection config.
- `HERMES_DESKTOP_REMOTE_URL` (not `HERMES_API_URL`) — wrong env var silently ignored.
