# Hermes Gateway API Setup

## Quick Start

```bash
# Start Hermes Gateway (includes API server on port 8643)
hermes gateway run

# Health check
curl http://localhost:8643/health
# → {"status":"ok"}

# Chat completion
curl -H "Authorization: Bearer $HERMES_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model":"qwen3.6-35b-heretic","messages":[{"role":"user","content":"Hello"}],"stream":false}' \
     http://localhost:8643/v1/chat/completions
```

## Configuration (config.yaml)

```yaml
api_server:
  host: 0.0.0.0
  port: 8643

custom_providers:
- api_key: sk-local           # LiteLLM local key
  base_url: http://localhost:4000/v1
  model: qwen3.6-35b-heretic  # Local Qwen 35B
  name: Local (localhost:4000)

model:
  default: deepseek-v4-pro    # Cloud model
  provider: deepseek
```

## Models

| Model | Source | Latency | Notes |
|-------|--------|---------|-------|
| `qwen3.6-35b-heretic` | Local via LiteLLM | 0.4-0.7s | No rate limit, always available |
| `deepseek-v4-pro` | DeepSeek API | 5-15s | Requires DEEPSEEK_API_KEY in .env, may rate limit |

## API Key

The Hermes API key used by the Android app is configured in `AppSettings.kt`:
```kotlin
const val DEFAULT_API_KEY = "tfpq7h9sUcrCjyFU3VuqAeq-IEpKT6Q6SgnC9iVQ5BPVJrRv"
```

## Why NOT unified proxy / LiteLLM direct / OpenCode+

- **Unified proxy**: Added complexity (socat + Python process + SSH tunnel thread). Processes died, port conflicts, pkill killed terminals.
- **LiteLLM direct**: Just a chat model. No agent tools, no memory, no skills — not Hermes.
- **OpenCode+ API**: Agents generate `step_start` protocol events as text. Not fixable client-side.

**Hermes Gateway API IS the real Hermes.** One process, one port, full agent experience.
