# GUI + Docker Testing Methodology

> Session: <SESSION_ID> (her2code Docker+GUI deep analysis)
> Date: 2026-06-21
> Key finding: GUI+Hermes in Docker IS possible but requires dashboard container + tui_gateway fix

## Test-First Protocol (MANDATORY)

**Pavel requires testing BEFORE asking him to run GUI.** The agent must:

1. Verify Docker gateway is healthy: `curl localhost:18648/health`
2. Verify llama.cpp (or any model): `curl localhost:8092/v1/models`
3. Launch dashboard container with `--volumes-from`
4. Test ALL endpoints the GUI needs: status, sessions, logs, agents, WebSocket
5. Only after 100% pass: give the user the GUI launch command

**Never say "try this and see if it works" without prior endpoint verification.**

## Architecture

```
GUI (Electron) -> dashboard (:9119) -> gateway (:18648) -> llama.cpp (:8092)
                   WebSocket + REST    REST API            inference
```

### Why dashboard is needed:
- GUI requires WebSocket (`/api/ws`) for chat -- only dashboard provides this
- GUI requires `/api/status` -- dashboard provides this natively
- Gateway alone (`hermes gateway run`) only provides REST API
- `status-proxy.py` approach is DEAD CODE -- dashboard has native endpoints

## Dashboard Launch (tested working)

```bash
# Dashboard shares gateway's data volume for sessions/config
docker run -d --name hermes-dashboard --network host \
  --volumes-from hermes-test \
  -e HERMES_UID=1000 -e HERMES_GID=1000 \
  -e HERMES_DASHBOARD_SESSION_TOKEN=*** \
  hermes-agent dashboard --host 127.0.0.1 --port 9119 --no-open

# Wait for chown (~170s ARM64)
for i in $(seq 1 90); do curl -sf localhost:9119/api/status && break; sleep 2; done
```

## WebSocket Fix (CRITICAL)

The Docker image is MISSING `tui_gateway/` at `/opt/hermes/tui_gateway/`.
WebSocket handler imports `from tui_gateway.ws import handle_ws` -> ModuleNotFoundError -> HTTP 500.

**Fix (non-persistent):**
```bash
docker cp ~/.hermes/hermes-agent/tui_gateway hermes-dashboard:/opt/hermes/tui_gateway
# Restart dashboard service
docker exec hermes-dashboard s6-svc -r /run/service/main-hermes
```

**Permanent fix:** Rebuild Docker image with `tui_gateway/` included (check .dockerignore).

## Endpoint Verification Checklist

After starting dashboard + applying tui_gateway fix, test ALL of these:

| Endpoint | Expected | GUI Stage |
|----------|----------|-----------|
| `/api/status` | 200 with version info | 24% |
| `/api/sessions` | 200 with sessions list | 95% |
| `/api/logs?file=gui&lines=12` | 200 with log lines | 95% |
| `/api/config` | 200 with config | 95% |
| `/api/ws?token=KEY` | 101 WebSocket upgrade | 95% |
| `/v1/models` (via dashboard proxy) | 200 with model list | post-boot |

Test script template at `scripts/test-dashboard.py`.

## GUI Isolation from Host Hermes

**Critical for not damaging the user's working Hermes:**

```bash
# Use ONLY env vars (NOT connection.json) for isolation:
env HERMES_DESKTOP_REMOTE_URL=http://localhost:9119 \
    HERMES_DESKTOP_REMOTE_TOKEN=*** \
    ELECTRON_EXTRA_LAUNCH_ARGS="--no-sandbox" \
    ~/.hermes/hermes-agent/apps/desktop/release/linux-arm64-unpacked/Hermes \
    --user-data-dir=/tmp/hermes-gui-docker
```

**Pitfall:** `--user-data-dir` isolates cache/sessions but NOT `connection.json`.
GUI always reads `~/.config/Hermes/connection.json` for remote connection config.
Use `HERMES_DESKTOP_REMOTE_URL` + `HERMES_DESKTOP_REMOTE_TOKEN` env vars -- they have
priority over connection.json.

**NEVER modify `~/.config/Hermes/connection.json`** for Docker testing -- it would
break the user's main Hermes GUI.

## Known Limitations (2026-06-21)

1. **WebSocket fix is NOT persistent** -- `docker cp` lost on container restart
2. **Dashboard+Gateway via `docker-compose` causes s6-log conflict** -- use separate `docker run`
3. **`/api/agents` returns 404** on dashboard -- doesn't block GUI boot
4. **GUI requires display** -- can't test from agent background processes
5. **ARM64 chown is 170s per container start** -- unavoidable, just wait
