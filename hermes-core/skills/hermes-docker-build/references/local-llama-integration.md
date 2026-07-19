# Local llama.cpp Integration with Docker Hermes

> **Date:** 2026-06-21 | **Model:** qwen3.6-35b-heretic | **Provider:** llama.cpp :8092

Configuring Docker Hermes to use a locally running llama.cpp instance on the host.

## Prerequisites

- llama.cpp running on host, accessible via `http://localhost:8092/v1`
- Docker Hermes with `network_mode: host` (to access host's localhost)
- Model must have an OpenAI-compatible chat completions endpoint

## Config

```yaml
model:
  default: qwen3.6-35b-heretic
  provider: llama
  context_length: 65536          # REQUIRED: Hermes minimum is 64K. Override even for 32K models.

custom_providers:                # MUST be YAML LIST, not dict!
  - name: llama
    base_url: http://localhost:8092/v1
    api_key: noauth              # llama.cpp doesn't require auth
    models:
      - qwen3.6-35b-heretic
```

## Critical Pitfalls

| Pitfall | Fix |
|---------|-----|
| `custom_providers` as dict → `[ERROR] custom_providers is a dict — it must be a YAML list` | Use `- name:` list syntax, not `name: {base_url: ...}` |
| `context_length: 32768` → `ValueError: ... below minimum 64,000` | Set `model.context_length: 65536`. Hermes truncates to actual limit at runtime. |
| Config overwritten on restart | Hermes stage2-hook seeds default config. After `docker compose down && up`, rewrite custom_providers block in mounted config. |
| `docker compose restart` doesn't re-read config | Must use full `down && up` to pick up volume config changes. |
| `CUSTOM_PROVIDER_*` env vars don't work | Environment variables alone are insufficient — need `custom_providers` YAML block in config.yaml. |
| Volume mount r/w → Hermes overwrites config | Mount config read-only (`:ro`) with separate writable dir for state, or rewrite config after each `docker compose up`. |

## Verification

```bash
# 1. Check llama.cpp is alive
curl -s http://localhost:8092/v1/models | python3 -c "import sys,json; print(json.load(sys.stdin)['models'][0]['name'])"

# 2. Test chat via Docker
curl -s http://localhost:18648/v1/chat/completions \
  -H "Authorization: Bearer *** \
  -H "Content-Type: application/json" \
  -d '{"model":"llama:qwen3.6-35b-heretic","messages":[{"role":"user","content":"Hi"}],"max_tokens":10}'
# Expected: {"choices":[{"message":{"content":"..."}}]}
```

## Provider Format Reference

Hermes `custom_providers` schema:
```yaml
custom_providers:
  - name: <provider_name>       # Used as "provider" in model config
    base_url: <url>             # OpenAI-compatible API endpoint
    api_key: <key>              # "noauth" for local servers
    models:                     # Whitelist of model names
      - <model1>
      - <model2>
```
