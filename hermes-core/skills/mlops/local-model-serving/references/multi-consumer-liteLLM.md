# Multi-Consumer LiteLLM Architecture

When multiple consumers (Hermes, OpenCode+, web UIs, cron jobs) need access to the same local models, route everything through a single LiteLLM proxy instead of pointing each consumer directly at llama-server ports.

## Architecture

```
llama-server :8101 (nex)  ─┐
llama-server :8102 (qwen) ─┼── LiteLLM :4000 ──┬── Hermes (providers.local)
llama-server :8103 (world)─┘                    ├── OpenCode+ (litellm provider)
                                                └── any OpenAI-compatible client
```

## Why

- **Single point of model registration** — add a model once to LiteLLM config, all consumers see it
- **Single UFW rule set** — only LiteLLM Docker container needs host access; consumers on host use `localhost:4000`
- **Consistent model names** — short aliases + full quant names coexist, all consumers use same identifiers
- **Phoenix tracing** — all model calls captured in one trace

## Hermes providers.local config (points to LiteLLM)

```yaml
providers:
  local:
    name: DGX Spark (via LiteLLM :4000)
    base_url: http://localhost:4000/v1
    api_key: sk-local
    models:
    - nex-n2-mini
    - qwen3.6-35b
    - agentworld
    - huihui-nex-n2-mini-abliterated-apex-quality
    - qwen3.6-35b-a3b-uncensored-heretic-native-mtp-preserved-apex-i-quality
    - superqwen-apex-i-quality-v3
```

In `providers` v12+ format, `models` is a **list** (not dict like in `custom_providers`). Override Hermes 64K minimum: `hermes config set model.context_length 65536`.

## OpenCode+ provider (points to LiteLLM)

```json
"provider": {
  "litellm": {
    "options": {
      "baseURL": "http://127.0.0.1:4000/v1",
      "apiKey": "sk-local"
    },
    "models": {
      "nex-n2-mini": { "name": "Nex — Coding (DGX)", "limit": {"context": 32768, "output": 16384} },
      "huihui-nex-n2-mini-abliterated-apex-quality": { "name": "Nex APEX-Quality (DGX)", ... }
    }
  }
}
```

Config path: `/home/user/cursor/opencode+/configs/opencode.litellm-dual.json`.
Deployed to: `~/.config/opencode/opencode.json`.

## Plan3 agent preset

Agent files in `~/.hermes/agents/plan3/` use `provider: local` (not `provider: custom:local` — v12+ format drops the `custom:` prefix):

```yaml
# ~/.hermes/agents/plan3/architect-agent.md
---
model: qwen3.6-35b
provider: local
reasoning: high
---
```

Model routing in Plan3:
| Model | Agents |
|-------|--------|
| qwen3.6-35b | Orchestrator, Requirements, SysAnalyst, Researcher, Architect, Auditor, Critic, Ideas, Curator |
| nex-n2-mini | Developer, Security, Deploy, Tester |
| agentworld | SimRL |

## Pitfall: stale inject_hermes_config()

`start-llama.sh` previously had an `inject_hermes_config()` function that appended old-format `custom_providers` (dict, not list) to `~/.hermes/config.yaml`, breaking Hermes with "custom_providers is a dict — it must be a YAML list". Once migrated to `providers` v12+ format, remove the function entirely from `start-llama.sh`. Symptom: `grep -n 'custom_providers' ~/.hermes/config.yaml` returns non-empty after each model restart. Fix: `head -n $((line-1)) config.yaml > tmp && mv tmp config.yaml`.
