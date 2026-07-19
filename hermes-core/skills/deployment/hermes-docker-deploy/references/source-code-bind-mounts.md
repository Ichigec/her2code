# Source Code Bind Mounts — Persistent Code Sync (2026-07-11)

## Problem

Docker containers run baked-in code from the image at `/opt/hermes/`. When you
patch local source files in `~/.hermes/hermes-agent/`, the changes are **invisible**
to running containers. Two approaches exist:

| Approach | Persistent? | survives recreate? | effort |
|----------|:-----------:|:------------------:|:------:|
| `docker cp` each file | ❌ no | ❌ no | 30+ commands |
| **bind mount source dirs** | ✅ yes | ✅ yes | one-time compose |

`docker cp` copies files into the container's writable layer. On `docker rm` +
recreate (compose down/up, image update, host reboot), the writable layer is
destroyed and you must re-copy everything.

## Solution: Source Code Bind Mounts

Mount local source directories and `.py` files as **read-write bind volumes**
in docker-compose. Files on host = files in container (same inode). Edits are
instantly live in both gateway and dashboard containers.

### What to mount

**Directories** (contain packages with `__init__.py`):
- `agent/` — agent internals (runtime, providers, memory, observer)
- `hermes_cli/` — CLI subcommands, setup wizard, plugins loader
- `tui_gateway/` — Python JSON-RPC backend for TUI
- `tools/` — tool implementations (auto-discovered via registry.py)
- `gateway/` — messaging gateway (run.py, session.py, platforms/)
- `cron/` — scheduler
- `plugins/` — plugin system
- `acp_adapter/` — ACP server (VS Code / Zed / JetBrains)
- `providers/` — provider adapters
- `skills/` — built-in skills

**Individual .py files** (top-level modules):
`run_agent.py`, `cli.py`, `model_tools.py`, `toolsets.py`, `hermes_state.py`,
`hermes_constants.py`, `hermes_logging.py`, `hermes_time.py`, `batch_runner.py`,
`utils.py`, `trajectory_compressor.py`, `hermes_bootstrap.py`,
`toolset_distributions.py`, `mcp_serve.py`, `mini_swe_runner.py`, `setup.py`

### What NOT to mount

- `.venv/` — Python virtualenv is image-specific (compiled extensions, arch)
- `node_modules/` — same reason
- `ui-tui/` — Ink/React app, compiled at build time
- `tests/` — not needed at runtime
- `docs/`, `website/` — documentation only

### Why NOT :ro (read-only)?

s6-overlay's `stage2-hook.sh` runs `chown -R` on `/opt/hermes/gateway` during
init. On `:ro` bind mounts, this hangs (D-state) indefinitely. Files are owned
by UID 1000 on host = `hermes(1000)` in container, so `chown` is a no-op — but
s6 still needs write permission to attempt it.

## Compose file structure

See `templates/docker-compose-local.yml` for the complete working file.

Key decisions in the compose:
1. **Gateway data** = `~/.hermes-portable:/opt/data` (own config, own state.db)
2. **Dashboard data** = `~/.hermes:/opt/data` (SHARED with local Hermes — same
   state.db, same sessions, same WAL files)
3. **Both services** mount identical source code bind mounts
4. `depends_on: [gateway]` on dashboard (gateway must start first for health URL)

### ⚠️ YAML anchors DON'T work for volume arrays

You cannot use YAML anchors (`&src` / `*src`) to share the volume list between
services. Docker Compose rejects merge-key arrays in `volumes:`:

```
validating docker-compose-local.yml: services.gateway.volumes.1 must be a string
```

**Fix:** Duplicate the volume list explicitly in each service. It's verbose but
reliable. A 30-line YAML anchor saves nothing when compose rejects it.

## Migration from `docker cp` to bind mounts

If containers already have code copied via `docker cp`, migrating is a 3-step
process — but requires container **recreation** (not restart):

```bash
# 1. Stop old containers
docker stop hermes-gateway hermes-dashboard
docker rm hermes-gateway hermes-dashboard

# 2. Start from compose (bind mounts take effect on CREATE, not restart)
cd ~/.hermes-portable-dash
docker compose -p hermes-local -f docker-compose-local.yml up -d

# 3. Wait 3-5 min for s6 chown (ARM64: 2 containers = double time)
```

⚠️ **Container name conflict:** if the old gateway was from a different compose
project (e.g. the USB-based `docker` project), `docker compose up` fails with
`container name "/hermes-gateway" already in use`. Fix: `docker stop` +
`docker rm` the old container before `compose up`.

## Shared state.db (dashboard ↔ local Hermes)

Pointing the dashboard's `/opt/data` at `~/.hermes` instead of a separate
`~/.hermes-portable-dash` makes the local desktop app and Docker dashboard
share the same SQLite database:

- **507 sessions** visible in both interfaces
- New chats created in one appear instantly in the other
- SQLite WAL mode handles concurrent access correctly (same directory = same
  `-shm` / `-wal` files)
- No data migration needed — the larger DB simply wins

⚠️ **Gateway keeps its own data volume** (`~/.hermes-portable`). Sharing state.db
with the gateway would cause the s6-log lock crash-loop documented in the main
skill. Only the DASHBOARD shares with local Hermes.

## Verification checklist

After starting containers with bind mounts:

```bash
# 1. Health
curl -sf http://127.0.0.1:18649/health  # Gateway
curl -sf http://127.0.0.1:9123/         # Dashboard

# 2. Code sync (md5 must match across all 3)
md5sum ~/.hermes/hermes-agent/tools/delegate_tool.py
docker exec hermes-gateway md5sum /opt/hermes/tools/delegate_tool.py
docker exec hermes-dashboard md5sum /opt/hermes/tools/delegate_tool.py

# 3. Shared DB
stat -c '%s' ~/.hermes/state.db
docker exec hermes-dashboard stat -c '%s' /opt/data/state.db
# Must be identical

# 4. Session count
docker exec hermes-dashboard python3 -c \
  "import sqlite3; c=sqlite3.connect('/opt/data/state.db').cursor(); \
   c.execute('SELECT COUNT(*) FROM sessions'); print(c.fetchone()[0])"

# 5. Compose project label
docker inspect hermes-gateway \
  --format='{{index .Config.Labels "com.docker.compose.project"}}'
# Must be 'hermes-local' for both containers
```

## Daily workflow after setup

1. Edit any `.py` file in `~/.hermes/hermes-agent/`
2. File is instantly live in both containers (same inode via bind mount)
3. For Python changes that need process restart:
   `docker restart hermes-gateway hermes-dashboard`
4. No `docker cp` needed — ever
