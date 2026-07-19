# LiteLLM Native Setup (ARM64 Jetson + Phoenix)

## Problem

LiteLLM Docker container (`ghcr.io/berriai/litellm-database:v1.83.7-stable` and arm64-native tags)
crashes on ARM64 Jetson. Prisma migrations emit:

```
prisma db error: x86_64-binfmt-P: QEMU internal SIGSEGV {code=MAPERR, addr=0x20}
```

Port 4000 never opens. **No Docker tag fixes this** — the Prisma binary itself is the problem.

## Solution: Native venv + Docker Phoenix

Phoenix (pure Python image) works fine in Docker. LiteLLM runs natively.

### 1. Create LiteLLM venv

```bash
python3 -m venv /home/user/litellm_venv
/home/user/litellm_venv/bin/pip install 'litellm[proxy]'
# Required for Phoenix tracing callback (ArizePhoenixLogger imports opentelemetry)
/home/user/litellm_venv/bin/pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
```

### 2. Run `prisma generate` (CRITICAL — fixes "No connected db" fatal error)

```bash
source /home/user/litellm_venv/bin/activate
python3 -m prisma generate \
  --schema=/home/user/litellm_venv/lib/python3.12/site-packages/litellm/proxy/schema.prisma
# Expected: "✔ Generated Prisma Client Python (v0.15.0) to ./litellm_venv/.../prisma in ~400ms"
```

**This WORKS on ARM64** (session 20260714). Previous docs claimed `prisma generate` failed
silently on ARM64 — that was WRONG. The key was using `python3 -m prisma generate` (not the
`prisma` CLI directly) with the `--schema=` flag pointing to LiteLLM's bundled schema.

Without this step, LiteLLM crashes on startup: "Unable to find Prisma binaries. Please run
'prisma generate' first." With it, LiteLLM starts successfully and "No connected db" errors
become non-fatal log warnings (requests still succeed).

### 3. LiteLLM config — `/home/user/dev/llama/litellm-config.yaml`

Routes to 3 llama-servers (:8101-8103) + sends traces to Phoenix:

```yaml
model_list:
  - model_name: "nex-n2-mini"
    litellm_params:
      model: "openai/nex-n2-mini"
      api_base: "http://localhost:8101/v1"
      api_key: "not-needed"

  - model_name: "agents-a1-abliterated"
    litellm_params:
      model: "openai/agents-a1"
      api_base: "http://localhost:8102/v1"
      api_key: "not-needed"

  - model_name: "agentworld"
    litellm_params:
      model: "openai/agentworld"
      api_base: "http://localhost:8103/v1"
      api_key: "not-needed"

  # Cloud models (optional)
  - model_name: "deepseek-v4-pro"
    litellm_params:
      model: "deepseek/deepseek-v4-pro"

litellm_settings:
  success_callback: ["arize_phoenix"]
  failure_callback: ["arize_phoenix"]
  drop_params: false
  request_timeout: 600

environment_variables:
  PHOENIX_COLLECTOR_ENDPOINT: "http://localhost:6006"
  PHOENIX_PROJECT_NAME: "qwen3.6-heretic"

general_settings:
  master_key: "sk-local"
  # NO database_url — Prisma query engine can't connect to Docker Postgres on ARM64
  # After `prisma generate`, "No connected db" errors are NON-FATAL (logged but requests succeed)
  # master_key is REQUIRED for UI — without it, /ui/ doesn't load
```

### 4. Start Phoenix (Docker)

```bash
STACK_DIR="/home/user/cursor/полностью рабочее с openhands, openwebui/first"
docker compose --env-file "$STACK_DIR/.env" -f "$STACK_DIR/compose.phoenix.yml" up -d phoenix phoenix-db
```

### 4. Start LiteLLM (native)

```bash
# Source .env for API keys (DEEPSEEK_API_KEY, etc.)
set -a && source /home/user/.hermes/.env 2>/dev/null && set +a
source /home/user/litellm_venv/bin/activate
cd /home/user/dev/llama  # so litellm_proxy.db (if ever created) lands here
litellm --config /home/user/dev/llama/litellm-config.yaml --port 4000 --host 0.0.0.0
```

**`master_key: "sk-local"` is set in config** — API requests require
`Authorization: Bearer *** header. UI uses this key automatically.

### 5. Verify

```bash
# LiteLLM alive (no auth needed for liveliness check)
curl -s http://localhost:4000/health/liveliness  # → "I'm alive!"

# Models listed (auth required — master_key is set)
curl -s http://localhost:4000/v1/models -H "Authorization: Bearer ***

# Smoke test a model (auth required)
curl -s http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer *** \
  -H "Content-Type: application/json" \
  -d '{"model":"agents-a1-abliterated","messages":[{"role":"user","content":"Say OK"}],"max_tokens":8}'

# UI (requires master_key — loads in browser at http://localhost:4000/ui/)
curl -s -o /dev/null -w "%{http_code}" http://localhost:4000/ui/  # → 200

# Phoenix traces
curl -s http://localhost:6006/v1/projects  # → project "qwen3.6-heretic" appears
```

## Hermes config.yaml integration

Agent files using `provider: custom:local` need BOTH:

1. `custom_providers:` section (YAML list) with `name: local` pointing at `http://localhost:4000/v1`
2. LiteLLM actually running on :4000

```yaml
custom_providers:
- name: local
  api_base: http://localhost:4000/v1
  api_mode: chat_completions
  api_key: sk-local
  models:
  - name: agents-a1-abliterated
    context_length: 262144
  - name: nex-n2-mini
    context_length: 262144
  # ...
```

Without `custom_providers:` section, Hermes silently falls back to `model.default` (e.g. glm-5.2).
See "Agent SILENTLY falls back to cloud default" pitfall in SKILL.md.

**Note on `api_key` in `custom_providers`:** The `api_key: sk-local` field MUST match
the `master_key` in LiteLLM's `general_settings`. LiteLLM enforces auth via `master_key`
(after `prisma generate`, "No connected db" errors are non-fatal). All API requests from
Hermes to LiteLLM must include `Authorization: Bearer ***

## Docker Phoenix compose

The Phoenix+DB compose lives at:
`/home/user/cursor/полностью рабочее с openhands, openwebui/first/compose.phoenix.yml`

It also defines `litellm-db` and `litellm` containers, but the `litellm` container is
dead on ARM64. Only `phoenix`, `phoenix-db`, and `litellm-db` (Postgres, unused by native
LiteLLM but harmless) should be kept running.

## "No connected db" — fix with `prisma generate` + keep `master_key`

**Session 20260714 (corrected).** LiteLLM v1.92 without `database_url` returns:
```json
{"error":{"message":"No connected db.","type":"no_db_connection","code":"400"}}
```

**Two-phase fix (VERIFIED working on ARM64):**

### Phase 1: `prisma generate` (transforms FATAL → NON-FATAL)

```bash
source /home/user/litellm_venv/bin/activate
python3 -m prisma generate \
  --schema=/home/user/litellm_venv/lib/python3.12/site-packages/litellm/proxy/schema.prisma
```

**This WORKS on ARM64.** Previous docs claimed it failed — that was WRONG. The key was
using `python3 -m prisma generate` (not the `prisma` CLI) with `--schema=` pointing to
LiteLLM's bundled `schema.prisma`.

Without this step: LiteLLM crashes on startup ("Unable to find Prisma binaries").
With this step: LiteLLM starts, "No connected db" errors become non-fatal log warnings.

### Phase 2: keep `master_key`, remove `database_url`

```yaml
general_settings:
  master_key: "sk-local"
  # NO database_url — Prisma query engine can't connect to Docker Postgres on ARM64
```

After `prisma generate`, with `master_key` but no `database_url`:
- `/health/liveliness` → `"I'm alive!"` ✅
- `/health` with `Authorization: Bearer *** → 200, healthy endpoints ✅
- `/v1/models` with auth → 200, 13 models ✅
- `/v1/chat/completions` with auth → 200 ✅
- `/ui/` → 200 ✅ (UI REQUIRES `master_key` — without it, UI doesn't load!)
- Logs show "No connected db" warnings — NON-FATAL, requests still succeed

**Why `master_key` is needed:** LiteLLM UI (`/ui/`) requires `master_key` to be set.
Without it, the UI page loads but cannot authenticate to the admin API → blank/broken UI.
Keeping `master_key` without `database_url` is the correct ARM64 configuration.

### Dead-ends (do NOT retry)

| Attempt | Result |
|---------|--------|
| `database_url: "sqlite:///path.db"` | Rejected: "DATABASE_URL uses unsupported scheme 'sqlite'. LiteLLM's database features require PostgreSQL" |
| Connect to Docker `litellm-db` Postgres (172.18.0.2:5432) | Prisma query engine: P1000 "Authentication failed" then ConnectError. Even after `ALTER USER ... PASSWORD` + `pg_hba.conf trust`, the query engine binary cannot reach the Docker internal IP |
| Remove BOTH `master_key` and `database_url` | API works but UI BREAKS — `/ui/` doesn't load without `master_key` |

**Conclusion:** On ARM64, run `prisma generate` once, then keep `master_key: "sk-local"`
without `database_url`. Virtual keys / spend tracking are unavailable (need PostgreSQL +
working Prisma connection), but model routing + Phoenix tracing + UI all work.

## Benchmark script

`scripts/benchmark-models.py` measures tok/s for all local models through LiteLLM:

```bash
python3 ~/.hermes/skills/software-development/hermes-custom-providers/scripts/benchmark-models.py
```

Results (DGX Spark, July 2026, 512-token generation):
- nex-n2-mini: 32.2 tok/s
- agents-a1-abliterated: 33.3 tok/s
- agentworld: 32.8 tok/s

## Notes

- Phoenix container is amd64-only too, but its image runs under QEMU without Prisma — works fine.
- The `drop_params: false` setting is important: passes `chat_template_kwargs` and `extra_body`
  through to llama-server backends (needed for per-request `enable_thinking`).
- **`master_key: "sk-local"` IS set in config** — after running `prisma generate`,
  "No connected db" errors are non-fatal. Auth is enforced via `master_key`.
  UI requires `master_key` to load. If you need virtual keys / spend tracking, you
  MUST set up PostgreSQL + working Prisma connection (query engine can't connect to
  Docker internal IP on ARM64 — P1000 auth error) — so effectively `master_key` without
  `database_url` is the only working ARM64 configuration with auth + UI.
- `opentelemetry-*` packages must be installed in the venv or Phoenix callback
  (`ArizePhoenixLogger`) errors on every request with `ModuleNotFoundError: No module
  named 'opentelemetry'`.
