# Silent Cloud Fallback Diagnostic

Session 20260714: plan3 agent used `glm-5.2` (zai cloud) instead of local
`agents-a1-abliterated`. Zero error messages — silent fallback.

## Symptom

- `/agent plan3` activated with `model: agents-a1-abliterated, provider: custom:local`
- But the session clearly runs on `glm-5.2` (zai, cloud)
- No errors in logs, no warnings, no provider resolution failure message

## Root Cause (two-layer)

1. **Format mismatch**: `plan3.md` frontmatter says `provider: custom:local`.
   Config.yaml uses v12+ `providers: local:` (dict format). There is NO
   `custom_providers:` list section in config.yaml. `custom:local` looks for
   a `custom_providers:` entry named `local` — not found → resolution fails.

2. **Intermediary dead**: LiteLLM proxy on `:4000` is not running. Even if
   the format matched, `providers.local.base_url = http://localhost:4000/v1`
   points to a dead port.

Both conditions together → Hermes silently falls back to `model.default`
(`zai/glm-5.2`) from config.yaml. No error because it IS a valid fallback
target.

## Diagnostic Sequence (ordered)

```bash
# 1. Is LiteLLM (:4000) alive?
curl -s --max-time 3 http://localhost:4000/v1/models | head -5
# Exit 7 = "Connection refused" → LiteLLM is DOWN

# 2. Are llama-server backends alive? (direct ports, no LiteLLM needed)
curl -s --max-time 2 http://localhost:8101/health; echo " :8101"
curl -s --max-time 2 http://localhost:8102/health; echo " :8102"
curl -s --max-time 2 http://localhost:8103/health; echo " :8103"
# {"status":"ok"} = backend is up

# 3. What's actually listening?
ss -tlnp | grep -E '4000|8101|8102|8103'
# Shows: 8101/8102/8103 listening (llama-server), 4000 absent

# 4. Does the provider name format match?
head -10 ~/.hermes/agents/plan3.md          # → provider: custom:local
grep -A5 'providers:' ~/.hermes/config.yaml  # → providers: local: (dict key)
# custom:local ≠ local → MISMATCH

# 5. Is there a custom_providers section at all?
grep 'custom_providers' ~/.hermes/config.yaml
# No output → there isn't one → custom:local can NEVER resolve
```

## Fix Options

### A) Start LiteLLM + add custom_providers (recommended for multi-model routing)

```yaml
# Add to config.yaml
custom_providers:
- name: local
  base_url: http://localhost:4000/v1
  api_key: sk-local
  models:
    agents-a1-abliterated: {}
    nex-n2-mini: {}
    agentworld: {}
```

Then start LiteLLM with model mappings to :8101/:8102/:8103.

### B) Switch agent frontmatter to bare `local` (quickest fix)

```bash
# In each agent .md file, change:
#   provider: custom:local
# to:
#   provider: local
# This matches the v12+ providers: dict key in config.yaml
```

Still requires LiteLLM on :4000 (since providers.local.base_url = :4000).

### C) Bypass LiteLLM — one provider per port

```yaml
providers:
  local-8101:
    base_url: http://localhost:8101/v1
    api_key: sk-local
    models:
      nex-n2-mini: {}
  local-8102:
    base_url: http://localhost:8102/v1
    api_key: sk-local
    models:
      agents-a1-abliterated: {}
  local-8103:
    base_url: http://localhost:8103/v1
    api_key: sk-local
    models:
      agentworld: {}
```

Then agent frontmatter: `provider: local-8102` (no LiteLLM needed).

## Key Insight

The fallback is SILENT because `model.default` is a valid model. Hermes
treats provider resolution failure as "use the default" rather than "error".
This means an agent can silently run on cloud when local is expected, with
the only signal being slower responses or different model behavior.

Always verify with: `grep "OpenAI client created" ~/.hermes/logs/agent.log | tail -3`
to see which base_url Hermes actually connected to.
