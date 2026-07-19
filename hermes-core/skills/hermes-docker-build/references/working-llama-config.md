# Working Docker Hermes config with local llama.cpp

Minimal config that works on Pavel's Jetson ARM64:

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
gateway:
  media_delivery_allow_dirs: []
  platforms:
    api_server: {}
mcp_servers: {}
agent:
  max_turns: 500
```

Key learnings:
- `custom_providers` MUST be YAML list (items prefixed with `- name:`), NOT a dict
- `context_length: 65536` bypasses Hermes's 64K minimum context check
- `gateway.platforms.api_server: {}` is required for API server auto-start
- Telegram removed from all levels (gateway.platforms, top-level platforms, top-level key)
