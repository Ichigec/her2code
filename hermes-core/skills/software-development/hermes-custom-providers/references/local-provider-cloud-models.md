# Local Provider with Cloud Models — Diagnostic

Session 20260715: user asked why session `20260715_214516_ac7b76` used
`deepseek-v4-pro` instead of a local model. The model WAS explicitly set —
no silent fallback occurred. The confusion was that `deepseek-v4-pro` is
listed under a provider literally named `local`, but routes to the cloud
DeepSeek API through LiteLLM.

## Symptom

- Session shows `model: deepseek-v4-pro`
- User expected a local model (agents-a1, agentworld, nex-n2-mini)
- No error, no fallback — the model works fine, it's just cloud-routed

## Root Cause: LiteLLM mixes local + cloud under one provider

```yaml
# config.yaml — the `local` provider has BOTH local and cloud models
custom_providers:
- name: local
  api_base: http://localhost:4000/v1   # LiteLLM proxy
  models:
    # TRULY LOCAL (llama-server direct):
    - nex-n2-mini              # → :8101
    - agents-a1-abliterated    # → :8102
    - agentworld               # → :8103

    # CLOUD (LiteLLM → external API):
    - deepseek-v4-pro          # → DeepSeek API (needs DEEPSEEK_API_KEY)
    - deepseek-v4-flash        # → DeepSeek API
    - gpt-4.1                  # → OpenAI API
    - gpt-4.1-mini             # → OpenAI API
```

LiteLLM at `:4000` fans out: local models hit `localhost:8101-8103`, cloud
models hit external APIs. All appear under the single `local` provider name
in Hermes. A model from `provider: local` can therefore be either.

## Diagnostic Sequence

```bash
# 1. What model did the session actually use?
#    Use session_search(session_id="...") in Hermes — session_meta shows model

# 2. Is LiteLLM running?
curl -sf http://localhost:4000/v1/models | python3 -c \
  "import sys,json; [print(m['id']) for m in json.load(sys.stdin).get('data',[])]"
# Lists ALL models (local + cloud mixed together)

# 3. Which backends are TRULY local? (direct llama-server ports)
for p in 8101 8102 8103; do
  echo -n ":$p → "
  curl -sf http://localhost:$p/v1/models 2>/dev/null | \
    python3 -c "import sys,json; print([m['id'] for m in json.load(sys.stdin).get('data',[])])" 2>/dev/null \
    || echo "DOWN"
done
# :8101 → ['nex-n2-mini']
# :8102 → ['agents-a1']
# :8103 → ['agentworld']

# 4. Check config.yaml: which models are under the `local` provider?
grep -A30 'name: local' ~/.hermes/config.yaml
```

**Decision rule**: if a model appears in `curl :4000/v1/models` but NOT in
any `curl :810{1,2,3}/v1/models`, it's cloud-routed through LiteLLM.

## Fix Options

### A) Separate cloud models into their own provider (recommended)

```yaml
custom_providers:
- name: local              # ONLY truly local models
  api_base: http://localhost:4000/v1
  models:
  - name: nex-n2-mini
  - name: agents-a1-abliterated
  - name: agentworld

- name: cloud-proxy        # cloud models through LiteLLM
  api_base: http://localhost:4000/v1
  models:
  - name: deepseek-v4-pro
  - name: gpt-4.1
```

Now `local:*` is unambiguous — everything under it is truly local.

### B) Direct per-port providers (no LiteLLM dependency)

```yaml
custom_providers:
- name: llama-8103
  api_base: http://localhost:8103/v1
  api_key: not-needed
  models:
  - name: agentworld
    context_length: 262144
```

Bypasses LiteLLM entirely. Hermes connects directly to llama-server.
Use `/model custom:llama-8103:agentworld` — guaranteed local.

### C) Just document the mapping (no config change)

If the setup is intentional (LiteLLM serves both), add a comment block in
config.yaml marking which models are local vs cloud. The diagnostic above
resolves the question when asked.

## Key Insight

The `local` provider name is a Hermes-level label, NOT a statement about
where inference happens. LiteLLM is a universal proxy — it routes to both
local backends and cloud APIs. Always verify actual inference location by
checking which port/backend serves a given model.
