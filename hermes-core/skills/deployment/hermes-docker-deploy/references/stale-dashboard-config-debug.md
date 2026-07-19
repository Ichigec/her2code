# Debugging "API call failed after 3 retries: Connection error"

> Session: 2026-07-07 — Docker portable deployment with 3 APEX models.
> User reported GUI chat failure when connecting to qwen3.6-35b-heretic.

## Environment

- Gateway container: `hermes-gateway` on `:18649` (`--network host`), volume `~/.hermes-portable`
- Dashboard container: `hermes-dashboard` on `:9123` (`--network host`), volume `~/.hermes-portable-dash`
- 3 llama-server instances: `:8101` (nex), `:8102` (qwen), `:8103` (world)
- Desktop Electron app reads `~/.config/Hermes/connection.json`

## Root cause chain

```
User sees: "API call failed after 3 retries: Connection error"
           ↓
connection.json had: mode="local" (no host gateway running)
           + url="http://localhost:9123" (dashboard, wrong endpoint for REST)
           + token="sk-docker-b" (wrong API key)
           ↓
Dashboard container's embedded gateway read ~/.hermes-portable-dash/config.yaml
           ↓
That config had STALE model name: qwen3.6-35b-heretic → localhost:8092 (DEAD)
           ↓
3 retries to :8092 → all timeout → "Connection error"
```

## Dashboard log evidence

```
🔌 Provider: custom  Model: qwen3.6-35b-heretic
🌐 Endpoint: http://localhost:8092/v1
📝 Error: Connection error.
⏱️  Elapsed: 16.65s  Context: 2 msgs, ~3,884 tokens
⏳ Retrying in 4.8s (attempt 2/3)...
❌ API failed after 3 retries — Connection error.
```

Note: the model name (`qwen3.6-35b-heretic`) and endpoint (`:8092`) come from the
**dashboard's** config, not the gateway's. The gateway container had the correct
3-model config pointing to `:8102`.

## Fixes applied (in order)

### 1. Sync dashboard config with gateway config

```bash
cp ~/.hermes-portable/config.yaml ~/.hermes-portable-dash/config.yaml
docker restart hermes-dashboard
# Verify:
docker exec hermes-dashboard cat /opt/data/config.yaml | grep base_url
```

### 2. Fix connection.json — point to gateway with correct API key

```bash
# Get the real API key from gateway's .env:
API_KEY=*** '^API_SERVER_KEY=' ~/.hermes-portable/.env | cut -d= -f2)

cat > ~/.config/Hermes/connection.json << 'EOF'
{
  "mode": "remote",
  "remote": {
    "url": "http://localhost:18649",
    "authMode": "token",
    "token": {
      "value": "REPLACE_WITH_API_KEY"
    }
  },
  "profiles": {}
}
EOF
```

### 3. Restart Electron app

The desktop app caches connection.json. Must restart to pick up changes.

## Key insight: 4 places config.yaml must be correct

In a Docker portable deployment with dashboard, there are up to 4 config files
that influence model routing:

| Location | Read by | Effect when stale |
|----------|---------|-------------------|
| `~/.hermes/config.yaml` | Host Hermes daemon | Local mode chat fails |
| `~/.hermes-portable/config.yaml` | Gateway container | Gateway API calls fail |
| `~/.hermes-portable-dash/config.yaml` | Dashboard container's gateway | Dashboard-routed chat fails |
| `~/.config/Hermes/connection.json` | Electron desktop app | Wrong endpoint / auth failure |

When debugging, check ALL relevant configs. The gateway working does NOT mean
the dashboard will work — they have separate volumes.
