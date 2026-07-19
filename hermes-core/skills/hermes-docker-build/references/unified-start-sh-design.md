# Unified start.sh — Design Document

> Created 2026-07-07. Replaces 8 separate scripts with one entry point.

## Two Variants

| Variant | Command | Mechanism | Use Case |
|---------|---------|-----------|----------|
| A (compose) | `./start.sh compose` | `docker compose -f docker/docker-compose.yml up -d` | Simple dev/test, healthcheck + depends_on |
| B (full) | `./start.sh full` | `docker run` gateway + `docker run` dashboard | Production, custom ports, local model |
| B (minimal) | `./start.sh minimal` | `docker run` gateway only | Headless, no GUI needed |

## Commands

```
./start.sh compose         # Variant A: docker-compose
./start.sh full [--model M.gguf]  # Variant B: full stack
./start.sh minimal          # Variant B: gateway only
./start.sh gui              # Launch Desktop GUI
./start.sh build            # Build Docker image
./start.sh stop             # Stop all containers
./start.sh status           # Show status
./start.sh logs [service]   # Logs: gateway, dashboard, neo4j, litellm
```

## Key Design Decisions

### 1. `$HOME` detection via `getent passwd`

Hermes overrides `$HOME` to `~/.hermes/home/`. start.sh uses:

```bash
REAL_HOME=$(getent passwd "$(id -u)" | cut -d: -f6)
HERMES_HOME="${HERMES_DOCKER_HOME:-$REAL_HOME/.hermes-docker}"
```

This ensures data directories go to `/home/user/.hermes-docker/`, not `/home/user/.hermes/home/.hermes-docker/`.

### 2. Shared dashboard container function

Both variants call `start_dashboard_container()` — same docker run command:
- `--network host` (for localhost access to gateway)
- `-v $HERMES_HOME:/opt/data` (persistent volume)
- `-e PYTHONPATH=/opt/data` (tui_gateway import fix)
- `--insecure --tui --no-open --skip-build`

### 3. tui_gateway on persistent volume

`prepare_home()` copies `tui_gateway/` from `~/.hermes/hermes-agent/tui_gateway` to `$HERMES_HOME/tui_gateway` before dashboard starts. Without this, WebSocket `/api/ws` fails with `ModuleNotFoundError`.

### 4. Port override via env vars

```bash
PORT_GW=18649 PORT_DASH=9122 ./start.sh full
```

Default ports: 18648 (gateway), 9121 (dashboard). Override when local Hermes occupies these.

### 5. Compose uses `depends_on: service_healthy`

```yaml
dashboard:
  depends_on:
    hermes:
      condition: service_healthy
```

Gateway has `healthcheck` with `start_period: 180s` (ARM64 chown time). Dashboard waits for gateway to be healthy before starting.

## Replaced Scripts

| Old Script | Replaced By |
|------------|-------------|
| `quick-start.sh` | `start.sh compose` |
| `docker-quick-start.sh` | `start.sh build && start.sh compose` |
| `deploy-full.sh` | `start.sh full` |
| `deploy-minimal.sh` | `start.sh minimal` |
| `status-proxy.py` | Obsolete (dashboard provides `/api/status`) |
| `launch-docker-gui.sh` | `start.sh gui` |
| `desktop.sh` | `start.sh gui` (for Docker mode) |

## Verified Endpoints (2026-07-07)

Both variants pass this smoke test:

| Endpoint | Expected | Result |
|----------|----------|--------|
| `GET /health` (gateway) | `{"status":"ok"}` | ✅ |
| `GET /api/status` (dashboard) | `{"version":"0.16.0","gateway_running":true}` | ✅ |
| `GET /api/sessions` (auth) | `{"sessions":[],"total":0}` | ✅ |
| `GET /api/logs?file=gui` | `{"file":"gui","lines":[...]}` | ✅ |
| `GET /v1/models` (auth) | `{"data":[{"id":"hermes-agent"}]}` | ✅ |
| `GET /api/ws?token=...` | HTTP 400 (WS handler active) | ✅ |
