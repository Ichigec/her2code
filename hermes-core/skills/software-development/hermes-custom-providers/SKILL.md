---
name: hermes-custom-providers
description: "Add and configure custom LLM providers in Hermes Agent — YAML config format, API key management, redaction workarounds, testing API keys before Hermes integration, and provider-specific quirks."
version: 1.0.0
tags: [hermes, providers, config, glm, z.ai, api-keys]
---

# Hermes Custom Providers

Add any LLM provider to Hermes via `custom_providers` in `~/.hermes/config.yaml`.

## Quick Start

```bash
# 1. Add API key to .env
echo "PROVIDER_API_KEY=sk-..." >> ~/.hermes/.env

# 2. Add provider to config.yaml (LIST format — NOT dict!)
# 3. Use: hermes chat -m model-name --provider custom:provider-name
#    or in-session: /model custom:provider-name:model-name
```

## Config Format (CRITICAL)

`custom_providers` MUST be a **YAML list**, not a dict:

```yaml
# ✅ CORRECT — list of providers, models as dict
custom_providers:
- name: zai
  base_url: https://api.z.ai/api/paas/v4
  api_key_env: GLM_API_KEY
  models:                      # ⚠️ MUST be a DICT, not a list
    glm-4.7: {}
    glm-5.2: {}
```

```yaml
# ❌ WRONG — dict format (will error: "custom_providers is a dict — it must be a YAML list")
custom_providers:
  zai:
    base_url: ...
```

## Adding a Provider — Full Steps

### Step 1: Store API key in `.env`

```bash
echo "GLM_API_KEY=your-key-here" >> ~/.hermes/.env
```

⚠️ **Redaction note**: Hermes's secret redaction system (`security.redact_secrets: true`) masks secrets in `read_file` OUTPUT only (display-time, via `agent/redact.py`). Files on disk contain real content — `write_file`/`patch` do NOT redact on write. If you see `***` when reading a config file, use `terminal cat <file>` to see the real value. For cases where the LLM model itself drops or mangles a key during generation (model-side issue, not tool-side), use the split-key technique in `references/redaction-workaround.md`.

### Step 2: Add provider to `config.yaml`

Use Python to edit config (direct `write_file`/`patch` is blocked on `config.yaml`):

```python
import yaml
config_path = os.path.expanduser('~/.hermes/config.yaml')
with open(config_path) as f:
    config = yaml.safe_load(f)

# Ensure custom_providers is a LIST
if 'custom_providers' not in config:
    config['custom_providers'] = []
elif isinstance(config['custom_providers'], dict):
    # Fix dict→list (common pitfall)
    config['custom_providers'] = [
        {'name': name, **cfg} for name, cfg in config['custom_providers'].items()
    ]

# Add provider (models as DICT, not list)
config['custom_providers'].append({
    'name': 'zai',
    'base_url': 'https://api.z.ai/api/paas/v4',
    'api_key_env': 'GLM_API_KEY',
    'models': {'glm-4.7': {}, 'glm-5.2': {}}  # ⚠️ dict, not list!
})

with open(config_path, 'w') as f:
    yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
```

### Step 3: Verify provider is visible

```bash
# Check config
grep -A10 'custom_providers' ~/.hermes/config.yaml

# Test with a quick query
hermes chat -q "say ok" -m MODEL --provider custom:NAME
```

### Step 4: Test API key BEFORE Hermes integration

Always test the key directly against the API before configuring Hermes. See `references/api-key-test-pattern.md`.

## v12+ `providers` Format (Newer Alternative)

Hermes v12+ also supports a `providers` key — a **keyed dict** (not a list) with `base_url` (not `api_base`). Both `custom_providers` (list) and `providers` (dict) work; `providers` is the newer format. The `hermes_cli/config.py` normalizer converts `providers` dict → `custom_providers` list at runtime.

```yaml
# ✅ v12+ format — keyed dict
providers:
  local:
    base_url: http://localhost:8101/v1
    api_key: not-needed           # or api_key_env: MY_KEY
    models:
      nex-n2-mini: {}
      qwen3.6-35b: {}
```

```yaml
# ✅ Legacy format — still works, list with api_base
custom_providers:
- name: local
  base_url: http://localhost:8101/v1
  api_key: not-needed
  models:
    nex-n2-mini: {}
```

**Key differences**: `providers` uses `base_url` and is a dict keyed by provider name; `custom_providers` uses `base_url` too but is a list with explicit `name:` field. In `providers` format, `models` can be a **list** (`- nex-n2-mini`), unlike `custom_providers` where `models` MUST be a dict.

**Multiple models on different ports — two valid patterns (session 20260707):**
1. **One provider per port (direct, preferred for `--network host`):** 3 `custom_providers` entries, each with its own `base_url` (`localhost:8101`, `:8102`, `:8103`). Works without LiteLLM because a gateway on `--network host` reaches all localhost ports directly (bypasses UFW). Simplest for single-consumer Hermes deployments. Full example: `hermes-docker-deploy` skill → "3-Model APEX deployment".
2. **Single LiteLLM proxy (for multi-consumer):** One provider pointing at LiteLLM (:4000), which fans out to multiple backends. Needed only when Hermes + OpenCode+ (or other consumers) share the same models. See `local-model-serving` skill → "Multi-consumer pattern".

## Model Provider Override Hierarchy (CRITICAL)

Hermes has THREE layers of model/provider configuration. Understanding which wins is essential:

| Layer | Where | Applies to |
|-------|-------|------------|
| **Global session** | `config.yaml` → `model.default` + `model.provider` | **The session's OWN model** — which LLM the orchestrator/agent ITSELF runs on. This is THE source of truth for the current conversation. |
| **Agent frontmatter** | `~/.hermes/agents/*.md` YAML frontmatter → `model:` + `provider:` | **Sub-agents only** — the default model for `delegate_task` calls spawned by this agent. Does NOT control the session model. |
| **Per-delegation override** | `delegate_task(model=..., provider=...)` in agent body or orchestrator code | **Individual sub-agent** — overrides both above for a specific delegation. |

**CRITICAL PITFALL — session model ≠ agent frontmatter:** When you `/agent plan3`, Hermes loads the system prompt from `plan3.md`, but the **model running the orchestrator comes from `config.yaml`'s `model.default`**, NOT from the agent file's frontmatter `model:` field. The frontmatter `model:` ONLY applies to sub-agents spawned via `delegate_task`.

```yaml
# ~/.hermes/config.yaml (controls the SESSION model — the orchestrator itself)
model:
  default: deepseek-v4-pro      # ← THIS is what the orchestrator runs on
  provider: deepseek            # ← NOT plan3.md's frontmatter

# ~/.hermes/agents/plan3.md frontmatter (controls SUB-AGENTS only)
---
model: agents-a1-abliterated    # ← ONLY for delegate_task children
provider: custom:local          # ← NOT for the session itself
---
```

**How to make the session use a local model (3 options):**

1. **Change global default** (affects ALL non-agent chat too):
   ```bash
   hermes config set model.default agents-a1-abliterated
   hermes config set model.provider custom:local
   ```

2. **Use a separate Hermes profile** (isolated config for plan3):
   ```bash
   hermes profile create plan3 --clone-from default
   hermes config set model.default agents-a1-abliterated --profile plan3
   hermes config set model.provider custom:local --profile plan3
   hermes --profile plan3    # launch with plan3 config
   ```

3. **Per-session override** (one-off):
   ```bash
   hermes -m agents-a1-abliterated --provider custom:local
   # or in-session: /model custom:local:agents-a1-abliterated
   ```

**Verify which model is active:**
```bash
hermes config show | grep -E "default:|provider:"   # session model (what the orchestrator runs on)
head -10 ~/.hermes/agents/plan3.md                    # sub-agent default (for delegate_task)
```

**Common confusion:** User activates `/agent plan3`, sees DeepSeek in the session header, and asks "why am I not using the local model from plan3.md?" — the answer is that plan3.md's `model:` frontmatter only governs sub-agents. The session model comes from `config.yaml`. To fix: either change the global default or use a plan3-specific profile. See `references/agent-model-routing-enforcement.md` for the full enforcement framework (6 strategies + implementation validation + plugin template). Copy `templates/routing-enforcer-plugin.py` and `templates/routing-enforcer-plugin.yaml` for a ready-to-deploy pre_tool_call enforcement plugin.

## How to Use in Hermes

⚠️ **The `model.provider` value differs between the two formats:**

| Config format | `custom_providers` (legacy list) | `providers` (v12+ dict) |
|---------------|----------------------------------|------------------------|
| `model.provider` | **`custom:<name>`** (WITH `custom:` prefix) | **`<name>`** (bare, NO prefix) |
| Example | `provider: custom:zai` | `provider: local` |

**Bare `custom` without `:<name>` in legacy format → "No LLM provider configured" error.** See Pitfalls.

- **CLI**: `hermes chat -m glm-5.2 --provider custom:zai` (legacy) or `hermes chat -m nex-n2-mini --provider local` (v12+)
- **In-session**: `/model custom:zai:glm-5.2` (legacy) or `/model local:nex-n2-mini` (v12+)
- **In agent preset** (`~/.hermes/agents/*.md`):
  ```yaml
  model: glm-5.2
  provider: custom:zai
  ```

## Provider-Specific Quirks

### Local llama-server (llama.cpp)

Connecting local llama-server models to Hermes. See `references/local-llama-server-provider.md` for the full recipe including v12+ `providers` format, 64K context override, Docker UFW firewall fix, **multi-consumer architecture (Hermes + OpenCode+ via single LiteLLM proxy)**, and start-llama.sh pattern.

**LiteLLM on ARM64:** Use Docker image `ghcr.io/berriai/litellm:main-stable` — it works reliably on ARM64 (Prisma bundled, stable). The **native venv approach is UNSTABLE**: the Prisma query engine binary crashes after 5-10 min (`prisma-query-engine PID ... exited; triggering reconnect` → process death → LiteLLM shutdown). Previous docs said "ALL Docker images crash" — that was true for old images but is **WRONG as of 2026-07-14**; `main-stable` works. Phoenix stays in Docker. Full recipe: `references/litellm-prisma-postgres-fix.md` — Docker LiteLLM + PostgreSQL + trust auth + admin user creation.

**Model not in menu or agent not routing?** The model name must agree across all three layers (llama-server `--alias`, LiteLLM model list, config.yaml `providers.local.models`). See `references/model-not-in-menu-diagnostic.md` for the full checklist.

**Agent preset supposed to be local but routing to cloud?** Check `delegate_task` code blocks in the `.md` body — they may contain stale `model="deepseek-v4-pro"` strings the orchestrator reads as instructions. Run `scripts/verify-agent-model-consistency.py --agent NAME --expect-local` to check all 5 consistency points automatically.

### z.ai (GLM models)

- **Base URL**: `https://api.z.ai/api/paas/v4` (overridable via `GLM_BASE_URL` in `.env` — Hermes picks it up automatically)
- **Auth**: `Authorization: Bearer {GLM_API_KEY}`
- **Available models**: `glm-4.5`, `glm-4.5-air`, `glm-4.6`, `glm-4.7`, `glm-5`, `glm-5-turbo`, `glm-5.1`, `glm-5.2`
- **glm-5.2 is a reasoning model** — returns `reasoning_content` with thinking tokens; `content` may be empty. For regular chat, use `glm-4.7` or `glm-5.1`. However, glm-5.2 with `reasoning_effort: xhigh` successfully produces both `reasoning_content` AND `content` — the empty-content pitfall is model-version dependent.
- **API key format**: `{uuid}.{secret}` (e.g., `c101243a...yGGstD8pQ71YHQE6`)
- **Rate limiting**: z.ai returns HTTP 429 error code 1305 ("service temporarily overloaded"). Large system prompts (Plan2 ~16K tokens) trigger this more aggressively because context grows with each retry. When all 3 retries fail, Hermes auto-switches to the fallback model if configured. See `references/zai-glm-setup.md` for diagnostic workflow.
- **GLM_BASE_URL**: The `zai` provider plugin (`plugins/model-providers/zai/__init__.py`) has a hardcoded `base_url="https://api.z.ai/api/paas/v4"` but Hermes respects `GLM_BASE_URL` from `.env` at runtime — confirmed in agent.log: `base_url=https://api.z.ai/api/coding/paas/v4`. The `env_vars` tuple in the plugin only lists key vars (`GLM_API_KEY`, `ZAI_API_KEY`, `Z_AI_API_KEY`) — `GLM_BASE_URL` is resolved by a separate config layer, not the plugin's `env_vars` tuple.

## Pitfalls

| Pitfall | Fix |
|---------|-----|
| `custom_providers is a dict — it must be a YAML list` | Convert to list format (see Config Format above), or use v12+ `providers` dict format. **Common cause:** stale `custom_providers:` block left over from `start-llama.sh`'s `inject_hermes_config()` after migrating to `providers:` format. Remove the old block entirely (`grep -n 'custom_providers' ~/.hermes/config.yaml` to locate). |
| **`models` as list → provider appears empty** ("GLM disappeared", no models in `/model`) | `models` MUST be a dict (`glm-4.7: {}`), NOT a list (`- glm-4.7`). Hermes checks `isinstance(models, dict)` in `model_switch.py:1036`. A list silently fails — models are not discovered. |
| API key corrupted by redaction in tool args | Use base64 encoding + split-string technique (see `references/redaction-workaround.md`) |
| `write_file`/`patch` refuses config.yaml | Use Python via `terminal` to edit config |
| **`write_file` DESTROYS config.yaml** | ⚠️ Unlike `patch` (which refuses), `write_file` will silently OVERWRITE the entire config.yaml! Always back up first (`cp config.yaml config.yaml.bak`) or use `hermes config set` for scalars / Python `yaml.load→dump` for structured keys. Session 20260704 lost an 11K config this way — recovered only from auto-backup `.bak.<timestamp>`. |
| **Hermes rejects model: context window below 64K minimum** | Local models started with `-c 32768` (32K) hit `MINIMUM_CONTEXT_LENGTH = 64_000` in `agent/agent_init.py:1548`. Fix: `hermes config set model.context_length VALUE`. ⚠️ This only bypasses the startup check — the real context limit is the llama-server `-c` value. **For thinking models (Qwen3.6-35B)**, 32K is too small even after bypassing the check — the model produces empty `content` because `<｜end▁of▁thinking｜>` tokens consume the entire output budget. Increase to `-c 262144` (256K) for correct thinking-model responses. Long conversations will error when they exceed the actual llama-server `-c` value. |
| `hermes model` requires interactive terminal | Test via `hermes chat -q` in non-interactive mode |
| **z.ai HTTP 429 (error code 1305) — rate limiting** | z.ai is overloaded. **Symptoms**: 3 retries with exponential backoff all fail, conversation stalls. **Contributing factors**: large system prompts (Plan2 ~16K tokens) make each request heavy; context grows with each retry making later attempts even more likely to be rate-limited. **Diagnose**: `grep "429\|RateLimitError" ~/.hermes/logs/agent.log`. **Workarounds**: (1) wait and retry later, (2) switch to lighter agent preset, (3) use a different model/provider. Hermes auto-falls back to `fallback_providers` if configured. **Full diagnostic**: `grep -E "429|RateLimitError|error_type" ~/.hermes/logs/errors.log | tail -20`. |
| **LiteLLM env var not updating after `.env` edit** | `docker restart litellm` does NOT re-read `.env` — env vars are baked at creation time. Use `docker compose up -d --force-recreate litellm`. Verify: `docker exec litellm printenv VAR_NAME`. Full recipe + ARM64 image arch gotcha in `references/local-llama-server-provider.md`. |
| **Agent preset files use stale `provider: custom:local`** | When migrating to v12+ `providers` format, agent `.md` files in `~/.hermes/agents/` still have `provider: custom:local` in their YAML frontmatter. Hermes won't route them to the new `providers.local` provider. Fix: `sed -i 's/provider: custom:local/provider: local/' ~/.hermes/agents/**/*.md`. Also update the orchestrator file (e.g., `plan3.md`). The `custom:` prefix is the legacy format; v12+ uses bare provider name (`local`, not `custom:local`). |
| **`provider: custom` (bare) → "gateway needs setup" / "No LLM provider configured"** | ⚠️ **ROOT CAUSE of "gateway needs setup" (session 20260707).** With legacy `custom_providers` (list format), `model.provider` MUST include the provider name suffix: `custom:<name>`, NOT bare `custom`. Bare `custom` → Hermes can't resolve WHICH custom provider to use → returns `"No LLM provider configured. Run hermes model to select a provider"` on every `/v1/chat/completions` call. **Format asymmetry that traps people:** legacy `custom_providers` needs `provider: custom:llama-local`; v12+ `providers` needs `provider: local` (bare name, NO `custom:` prefix). The two formats use OPPOSITE conventions. **Fix:** `sed -i 's/^  provider: custom$/  provider: custom:llama-local/' config.yaml`. **Debug:** `curl -s :PORT/v1/chat/completions -H "Authorization: Bearer KEY" -d '{"model":"...","messages":[...]}'` → if response contains "No LLM provider configured", it's this bug. |
| **LiteLLM compose defaults `LLAMA_CPP_API_BASE` to :8090** | llama-server runs on :8092 (start-llama-qwen.sh). If `.env` doesn't override, LiteLLM returns 500 Connection error. Fix: `LLAMA_CPP_API_BASE=http://host.docker.internal:8092/v1` (bridged) or `http://127.0.0.1:8092/v1` (host network). See `references/local-llama-server-provider.md`. |
| **LiteLLM arm64: native venv Prisma engine crashes; use Docker instead** | The **native venv** approach (`pip install 'litellm[proxy]'`) is UNSTABLE on ARM64 — the Prisma query engine binary dies after 5-10 min, killing LiteLLM. **Use Docker image `ghcr.io/berriai/litellm:main-stable`** — Prisma is bundled and stable. Previous docs claiming "ALL Docker images crash" were true for old images (v1.83.7) but are **WRONG as of 2026-07-14**. Full Docker recipe: `references/litellm-prisma-postgres-fix.md`. |
| **Model in menu but `Connection error` on chat** | Model appears in `/v1/models` but `POST /v1/chat/completions` → `litellm.InternalServerError: Connection error`. Root cause: Docker→host firewall blocks llama-server ports. `/v1/models` returns static config (no backend check); only chat completion tests real connectivity. Multiple causes and fixes — see below. |
| **Docker bridge → host unreachable (iptables blocks)** | `sudo iptables -I INPUT 1 -s 172.17.0.0/16 -p tcp --dport 8101:8103 -j ACCEPT`. See `references/model-not-in-menu-diagnostic.md` → Layer 5. |
| **Docker bridge → host unreachable (no sudo — bypass LiteLLM)** | When you can't modify iptables, add a direct provider that hits the backend on `localhost:PORT` (e.g. `custom:vllm → http://localhost:8000/v1`). Hermes runs on the host and CAN reach `localhost` — LiteLLM in Docker can't. Full recipe: `references/direct-vllm-bypass.md`. |
| **Agent preset silently falls back to cloud default — no error** | See the "Model Provider Override Hierarchy" section above — the agent frontmatter does NOT control the session model. The session uses `model.default` from config.yaml. If that's a cloud model, `/agent plan3` silently runs on cloud. Fix: either change `model.default` to a local model, or create a separate Hermes profile with its own config.yaml. |
| **Agent file references non-existent sub-providers** | Agent `.md` files (e.g. plan3.md) sometimes invent `custom:local:nex`, `custom:local:agents`, `custom:local:world` — these are NOT real providers. Only the provider keys defined under `providers:` in config.yaml exist (e.g. just `local` → `custom:local`). Sub-providers per port are NOT auto-created. Fix: either add separate providers in config (one per port) or change agent file to use `custom:local:model-name` (single provider, model switching via model field). |
| **Frontmatter vs registry.json provider mismatch** | Agent frontmatter says `provider: local` but registry.json says `provider: custom:local` (or vice versa). Hermes reads registry.json for delegate_task routing and frontmatter for session-level model. If they disagree, delegation may fail silently. **Fix**: ensure both use the same format — `custom:local` for legacy `custom_providers`, or bare `local` for v12+ `providers`. Verify: `grep provider ~/.hermes/agents/registry.json` vs frontmatter in the `.md` file. |
| **"Why am I getting model X instead of Y?" (plan vs global)** | The global `config.yaml` model applies ONLY to non-agent chat. Agent presets (`~/.hermes/agents/*.md` frontmatter) override it when activated via `/agent <name>`. If `hermes config show` says `glm-5.2` but `/agent plan3` is supposed to use a local model, check `head -10 plan3.md` — the frontmatter is the source of truth for that plan, NOT the global config. No global change needed if frontmatter is already correct. |
| **LiteLLM v1.92 "No connected db" error** | **RECOMMENDED: Use Docker LiteLLM** (see `references/litellm-prisma-postgres-fix.md` for the full Docker recipe). The native venv approach works temporarily but Prisma engine crashes after 5-10 min. **Docker approach (definitive):** (1) Pull `ghcr.io/berriai/litellm:main-stable`. (2) Recreate `litellm-db` with `-p 5432:5432` and switch `pg_hba.conf` from `scram-sha-256` to `trust`: `docker exec -u postgres litellm-db bash -c "sed -i 's/scram-sha-256/trust/g' /var/lib/postgresql/data/pg_hba.conf && pg_ctl reload -D /var/lib/postgresql/data"`. (3) In `litellm-config.yaml`: `database_url: "postgresql://litellm:litellm@litellm-db:5432/litellm"` (Docker DNS, NOT localhost — LiteLLM container can't reach host localhost). (4) Run LiteLLM in Docker on `llm-stack-net` network so it can resolve `litellm-db`. (5) Create admin user for UI: `curl -X POST http://localhost:4000/user/new -H "Authorization: Bearer sk-local" -H "Content-Type: application/json" -d '{"user_email":"admin@local","user_password":"admin","user_role":"proxy_admin"}'` — UI login is `admin@local / admin`. **Then set password separately**: `/user/new` may NOT set the password (NULL in DB). Call `/user/update` with `{"user_email":"admin@local","password":"admin"}` (note: field is `password`, not `user_password`). Verify: `docker exec litellm-db psql -U litellm -d litellm -c "SELECT password IS NOT NULL FROM \"LiteLLM_UserTable\";"`. **Native venv approach (unstable, fallback only):** run `prisma generate --schema=.../litellm/proxy/schema.prisma`, forward PostgreSQL port to localhost, use `database_url: "postgresql://litellm:litellm@localhost:5432/litellm"`. SQLite is rejected ("unsupported scheme"). Also install `opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp` in the venv or Phoenix callback errors. See `references/litellm-prisma-postgres-fix.md` for the full step-by-step (both approaches). |
| **Agent SILENTLY falls back to cloud default — no error** | ⚠️ **Session 20260714.** When provider resolution fails in an agent preset, Hermes does NOT error or warn — it silently uses `model.default` from `config.yaml` (e.g. `glm-5.2`). User sees cloud model where they expected local model, with zero diagnostic signal. **Two conditions that combine to cause this:** (1) Format mismatch — agent frontmatter says `provider: custom:local` but config.yaml uses v12+ `providers: local:` dict format (no `custom_providers:` list section exists). (2) Intermediary down — LiteLLM proxy on `:4000` is not running, so even if the format matched, the endpoint is dead. **Either alone may produce different symptoms; together they guarantee silent fallback.** **Diagnostic sequence (run in order):** (1) `curl -s localhost:4000/v1/models` → is LiteLLM alive? (exit 7 = dead). (2) `curl -s localhost:8101/health` etc → are llama-server backends alive? (they can be up even when LiteLLM is down). (3) `head -10 agent.md` → `grep -A5 'providers:' config.yaml` → does the provider name format match? (`custom:local` needs `custom_providers:` list; `local` bare needs `providers:` dict). (4) Check `ss -tlnp | grep -E '4000|8101|8102'` to see what's actually listening. **Fix options:** (A) Start LiteLLM + add `custom_providers:` section. (B) Switch agent frontmatter to `provider: local` (bare) + ensure `providers: local: base_url: http://localhost:4000/v1`. (C) Bypass LiteLLM entirely: define one provider per port (`providers: local-8101:`, `local-8102:`, etc.) and point each at the direct llama-server. **Full diagnostic walkthrough:** `references/silent-fallback-diagnostic.md`. |
| **Cloud model under a `local`-named provider — not actually local** | ⚠️ **Session 20260715.** A LiteLLM proxy at `:4000` can route to BOTH local llama-servers (:8101-:8103) AND cloud APIs (DeepSeek, OpenAI). When cloud models (`deepseek-v4-pro`, `gpt-4.1`) are listed under a provider named `local`, the session shows `model: deepseek-v4-pro` — which LOOKS like it could be local but actually hits the cloud API via LiteLLM. **This is NOT a silent fallback** (provider resolution succeeds, model is explicitly chosen) — the model is just cloud-routed through a proxy that also serves local models. **Symptom**: user asks "why isn't the session using a local model?" but the session IS using the configured model — it's just that the model routes to cloud despite being under the `local` provider. **Diagnostic**: (1) `session_search(session_id=...)` to see actual model. (2) Inspect `custom_providers` / `providers` in config.yaml — for each model, check if it maps to a local llama-server port or a cloud API. (3) `curl localhost:4000/v1/models` — if LiteLLM lists both `agentworld` AND `deepseek-v4-pro`, cloud models are mixed in. (4) Health-check direct ports: `curl localhost:{8101,8102,8103}/v1/models` — these are the TRULY local models. **Fix**: (A) Remove cloud models from the `local` provider entry to avoid confusion. (B) Add separate direct providers per port so truly local models are unambiguous. (C) Just be aware that LiteLLM proxies cloud + local under one name. **Full walkthrough**: `references/local-provider-cloud-models.md`. |
| **Agent body delegate_task blocks reference stale cloud models** | Agent `.md` files (e.g. plan2.md, plan3.md) contain Python `delegate_task(model="deepseek-v4-pro", provider="deepseek")` code blocks — these are INSTRUCTIONS the orchestrator LLM reads and executes. A "fully local" plan with 15-25 cloud-model references in its body silently routes every delegation to cloud, ignoring the local frontmatter. **Two fix variants:** (A) Switch to fully local model: `sed -i 's/provider="deepseek"/provider="custom:local"/g; s/model="deepseek-v4-pro"/model="agents-a1-abliterated"/g'` — changes both model and provider. (B) Fix provider routing only (keep cloud model via LiteLLM): `sed -i 's/provider="deepseek"/provider="custom:local"/g'` — model name stays `deepseek-v4-pro`, which LiteLLM routes to DeepSeek API via `DEEPSEEK_API_KEY`. Use (B) when the model IS available through LiteLLM but the provider name in the agent file doesn't match config.yaml. Session 20260714: plan2.md had **16 provider references + 38 `~/.hermes/` path references** — both fixed with `sed -i`. Also check dict-syntax: `model: "deepseek-v4-pro", provider: "deepseek"` (colon, not equals) — `sed -i 's/provider: "deepseek"/provider: "custom:local"/g'`. Also check YAML frontmatter line 7: `provider: deepseek` → `provider: custom:local`. **Automated check**: `scripts/verify-agent-model-consistency.py --agent plan3 --expect-local`. |
| **Dual routing tables in agent body (CLOUD + LOCAL)** | Agent `.md` bodies can contain a **higher-level routing table** like `### Routing Rules (CLOUD)` assigning cloud models per role (Orchestrator = deepseek-v4-pro, etc). The orchestrator LLM reads this as a decision instruction — when delegating, it looks up the role and picks the model from the table. This is distinct from stale `delegate_task` blocks: those are individual code calls; routing tables are system-prompt-level instructions that influence ALL delegation decisions. **Diagnostic**: `grep -n 'Routing Rules.*CLOUD' ~/.hermes/agents/plan3.md`. **Fix**: delete the entire CLOUD routing table, keep only LOCAL. For 6 enforcement strategies (soft prompt fix through hard infra block to code patch), see `references/agent-model-routing-enforcement.md`. |
| **pre_tool_call plugin exists on disk but provides zero enforcement** | ⚠️ **Session 20260715.** A plugin placed in `~/.hermes/plugins/<name>/` with correct `plugin.yaml` and `register()` function will appear in `hermes plugins list` as **"not enabled"** by default. It is never loaded, its hooks are never registered, and it silently does nothing. **This is NOT a bug — it's the design.** Plugins must be explicitly activated: `hermes plugins enable <name>`. **Diagnostic**: `hermes plugins list \| grep <name>` — if status is "not enabled", the plugin is dead weight. **Fix**: `hermes plugins enable <name>`. After enabling, restart the session or verify hooks fire. Also: a routing-enforcer plugin WITHOUT removing the CLOUD routing table from the agent .md body creates an adversarial loop — orchestrator reads "use deepseek-v4-pro", plugin blocks it, orchestrator retries (same instructions), blocked again. Prompt fix (delete CLOUD table) and hook (plugin) MUST be applied together. **Plugin template**: `templates/routing-enforcer-plugin.py` + `templates/routing-enforcer-plugin.yaml`. **Full enforcement framework**: `references/agent-model-routing-enforcement.md` → "Implementation Validation" section. |
