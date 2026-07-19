# No-Volume Docker Start — Discovery (2026-06-21)

## Discovery

Docker Hermes image ships with a **built-in default config** at `/opt/data/config.yaml`.
This config:
- Has NO `telegram` platform configured → no hang on blocked api.telegram.org
- Has NO `mcp_servers` → no Node.js errors
- Has NO broken `/home/user/` paths
- Uses `model.default: anthropic/claude-opus-4.6` with `provider: auto`

**Without any volume mount, Docker starts clean and fast** — API server is up in ~170s
(Jetson ARM64 chown) with no Telegram connection hangs.

## Problem with Volume Mounts

When `~/.hermes-docker/` (or any host Hermes config) is mounted to `/opt/data`:
1. Telegram platform is configured → gateway hangs on `api.telegram.org` (blocked in Russia)
2. `HERMES_DISABLE_MESSAGING=1` does NOT prevent Telegram platform initialization
3. Gateway retries Telegram connection indefinitely, never starting the API server
4. Config may contain broken `/home/user/` paths from sanitization

## Solution: Two-Pronged Approach

### For distribution (clean start)
```yaml
# docker-compose.yml — NO volume mount
services:
  hermes:
    network_mode: host
    # No volumes — use built-in clean config
    environment:
      - API_SERVER_PORT=18648
      - API_SERVER_KEY=${API_SERVER_KEY:-sk-local}
```

### For custom model (llama.cpp, etc.)
Use `docker cp` to inject config into running container AFTER health check:

```bash
# Wait for health
for i in $(seq 1 90); do curl -sf localhost:18648/health && break; sleep 2; done

# Inject custom config with llama provider
docker cp /tmp/minimal-config.yaml hermes-test:/opt/data/config.yaml

# Restart gateway process via s6
docker exec hermes-test s6-svc -r /run/service/main-hermes
```

Or mount a **minimal** config directory containing ONLY `config.yaml`:

```yaml
volumes:
  - /tmp/hermes-minimal-config:/opt/data
```

Where `/tmp/hermes-minimal-config/config.yaml` contains only:
```yaml
_config_version: 28
model:
  default: qwen3.6-35b-heretic
  provider: llama
  context_length: 65536
custom_providers:
  - name: llama
    base_url: http://localhost:8092/v1
    api_key: noauth
    models:
      - qwen3.6-35b-heretic
api_server:
  host: 0.0.0.0
  port: 18648
```

**Key principle:** The Docker image's built-in config is cleaner than any mounted host config. Start without volume first, then inject only what's needed.
