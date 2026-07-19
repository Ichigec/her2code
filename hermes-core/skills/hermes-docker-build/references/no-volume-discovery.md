# Discovery: Docker works BETTER without volume mount

Date: 2026-06-20
Session: her2code deep analysis + Docker fix

## The finding

After hours of debugging why the Docker Hermes API server wouldn't start,
we discovered that the **container's default config is cleaner** than any
mounted sanitized config.

## Root cause chain

1. Sanitized `config.yaml` (from `~/.hermes-docker/`) contains:
   - Telegram platform config (blocked in Russia → gateway hangs)
   - MCP server paths pointing to `/home/user/...` (don't exist)
   - Old model config (`provider: auto` → unpredictable resolution)
   - TTS command paths pointing to removed scripts

2. When mounted as volume `/opt/data`, Hermes reads this broken config
   and gateway hangs trying to connect to Telegram (geo-blocked in RF).

3. Removing Telegram from config via Python script is fragile — Telegram
   appears in 4+ nested YAML locations (`gateway.platforms.telegram`,
   `platforms.telegram`, `plugins.installed[hermes-telegram]`, top-level
   `telegram:`).

4. `HERMES_DISABLE_MESSAGING=1` helps but doesn't prevent platform init
   from trying Telegram connections.

## The solution

**Don't mount any volume.** The Docker image's internal default config:
- Has NO Telegram
- Has NO broken MCP paths
- Has a clean model config (OpenRouter with `anthropic/claude-opus-4.6`)
- Needs only API keys passed via environment variables

## docker-compose.yml pattern

```yaml
services:
  hermes:
    build: ./hermes-agent
    network_mode: host
    # NO volumes! Default config is clean.
    environment:
      - HERMES_UID=1000
      - HERMES_GID=1000
      - API_SERVER_HOST=0.0.0.0
      - API_SERVER_PORT=18648
      - API_SERVER_KEY          # from .env
      - GATEWAY_ALLOW_ALL_USERS=true
      - HERMES_DISABLE_MESSAGING=1
      - OPENROUTER_API_KEY      # from .env
    command: [gateway, run]
```

## When to mount a volume

Only needed for persistence:
- Skills sync across restarts
- Cron jobs
- Session state (state.db)

For first-run / testing / distribution demo — NO volume is the right choice.

## Verification

Without volume mount, on Jetson ARM64:
- chown: ~120s (inside container filesystem, not on mounted volume)
- Gateway start: ~30s after chown
- Health check: UP at ~170s total
- API server: responds at 18648
