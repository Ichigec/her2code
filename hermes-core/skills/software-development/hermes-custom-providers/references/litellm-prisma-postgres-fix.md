# LiteLLM Prisma + PostgreSQL on ARM64 — Full Fix

> Session 20260714. Resolves the `No connected db` error completely.
> **UPDATED 2026-07-14**: Docker approach is now the RECOMMENDED fix.
> The native venv approach works temporarily but Prisma query engine
> crashes after 5-10 min. Docker `ghcr.io/berriai/litellm:main-stable`
> is stable on ARM64 with Prisma bundled.

## Symptom

```
{"error":{"message":"No connected db.","","type":"no_db_connection","param":null,"code":"400"}}
```

Every API call fails. LiteLLM logs show `ProxyException: No connected db` in
`user_api_key_auth()`. The UI (`/ui/`) may not load at all.

## Root Cause (3 layers)

1. **Prisma client not generated** (native venv only) — `prisma generate` was
   never run, so the Prisma Python client has no binaries.

2. **Prisma query engine can't reach Docker internal IP** (native venv only) —
   The Prisma query engine binary cannot connect to `172.18.0.2:5432` (Docker
   bridge network IP). Error: `P1000: Authentication failed`.

3. **pg_hba.conf uses scram-sha-256** — PostgreSQL defaults to `scram-sha-256`
   auth for remote connections. Prisma query engine doesn't handle scram auth
   correctly on ARM64.

4. **Native venv Prisma engine instability** (NEW) — Even with all 3 fixes
   above, the native venv Prisma query engine binary crashes after 5-10 min
   of operation. LiteLLM logs: `prisma-query-engine PID ... exited; triggering
   reconnect` → `Application startup failed. Exiting.` This makes the native
   approach unreliable for long-running deployments.

---

## Fix A: Docker LiteLLM (RECOMMENDED — stable)

Use `ghcr.io/berriai/litellm:main-stable` — Prisma is bundled and stable.

### Step 1: Recreate litellm-db with port forwarding

```bash
docker stop litellm-db && docker rm litellm-db

docker run -d \
  --name litellm-db \
  --network llm-stack-net \
  -p 5432:5432 \
  -e POSTGRES_USER=litellm \
  -e POSTGRES_PASSWORD=*** \
  -e POSTGRES_DB=litellm \
  -v litellm-pg-volume:/var/lib/postgresql/data \
  postgres:16
```

### Step 2: Switch pg_hba.conf to trust

```bash
docker exec -u postgres litellm-db bash -c \
  "sed -i 's/scram-sha-256/trust/g' /var/lib/postgresql/data/pg_hba.conf && \
   pg_ctl reload -D /var/lib/postgresql/data"
```

### Step 3: Configure litellm-config.yaml

```yaml
general_settings:
  database_url: "postgresql://litellm:***@litellm-db:5432/litellm"
  master_key: "sk-local"
```

**CRITICAL:** Use `litellm-db:5432` (Docker DNS), NOT `localhost:5432`.
When LiteLLM runs inside Docker, `localhost` refers to the LiteLLM container,
not the host. Docker DNS resolves `litellm-db` to the PostgreSQL container's
IP on the `llm-stack-net` network.

### Step 4: Run LiteLLM in Docker

```bash
# Extract API keys from .hermes/.env
DSK=$(grep '^DEEPSEEK_API_KEY=*** ~/.hermes/.env | tail -1 | cut -d= -f2-)
KMK=$(grep '^KIMI_API_KEY=*** ~/.hermes/.env | tail -1 | cut -d= -f2-)

docker run -d \
  --name litellm \
  --network llm-stack-net \
  -p 4000:4000 \
  -v /home/user/dev/llama/litellm-config.yaml:/app/config.yaml \
  -e DEEPSEEK_API_KEY=*** \
  -e KIMI_API_KEY=*** \
  -e PHOENIX_COLLECTOR_ENDPOINT=http://host.docker.internal:6006 \
  -e PHOENIX_PROJECT_NAME=qwen3.6-heretic \
  ghcr.io/berriai/litellm:main-stable \
  --config /app/config.yaml --port 4000 --host 0.0.0.0
```

Wait ~20 seconds for Prisma migration, then verify:

```bash
curl -s http://localhost:4000/health/liveliness           # → "I'm alive!"
curl -s -o /dev/null -w "%{http_code}" http://localhost:4000/ui/  # → 200
```

### Step 5: Create admin user for UI login

LiteLLM UI requires a user account. Create one via API:

```bash
curl -s -X POST http://localhost:4000/user/new \
  -H "Authorization: Bearer *** \
  -H "Content-Type: application/json" \
  -d '{"user_email":"admin@local","user_password":"admin","user_role":"proxy_admin"}'
```

**UI login:** `admin@local` / `admin`
**API key (master):** `sk-local`

### Step 5b: Set password via /user/update (CRITICAL)

In some LiteLLM versions, `/user/new` creates the user but does NOT set the
password — the `password` column in `LiteLLM_UserTable` stays NULL. The UI
returns: `"User has no password set. Please set a password for the user
via /user/update."` when you try to log in.

Fix with a separate `/user/update` call:

```bash
curl -s -X POST http://localhost:4000/user/update \
  -H "Authorization: Bearer sk-local" \
  -H "Content-Type: application/json" \
  -d '{"user_email":"admin@local","password":"admin"}'
```

Verify the password hash is set:

```bash
docker exec litellm-db psql -U litellm -d litellm -c \
  "SELECT user_email, password IS NOT NULL as has_pw FROM \"LiteLLM_UserTable\";"
# admin@local | t  (password hash present)
```

**Note:** The field name is `password` (not `user_password`) in `/user/update`,
even though `/user/new` uses `user_password`. This asymmetry is a LiteLLM API
quirk.

### Verification

```bash
# No DB errors in logs
docker logs litellm 2>&1 | grep -i "connected db" | tail -5  # → empty

# Models accessible
curl -s http://localhost:4000/v1/models \
  -H "Authorization: Bearer *** | python3 -m json.tool | head -5

# UI loads
curl -s http://localhost:4000/ui/ | head -5  # → HTML with "LiteLLM Dashboard"
```

---

## Fix B: Native venv (FALLBACK — unstable, Prisma crashes after 5-10 min)

Only use if Docker is unavailable. Prisma query engine will crash eventually.

### Phase 1: Generate Prisma client

```bash
source /home/user/litellm_venv/bin/activate
python3 -m prisma generate \
  --schema=/home/user/litellm_venv/lib/python3.12/site-packages/litellm/proxy/schema.prisma
```

Also install opentelemetry packages:
```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
```

### Phase 2: Forward PostgreSQL port + trust auth

Same as Docker Fix Steps 1-2.

### Phase 3: Configure with localhost (not Docker DNS)

```yaml
general_settings:
  database_url: "postgresql://litellm:***@localhost:5432/litellm"
  master_key: "sk-local"
```

Native venv can use `localhost:5432` because it runs on the host.

### Launch

```bash
set -a && source /home/user/.hermes/.env 2>/dev/null && set +a
source /home/user/litellm_venv/bin/activate
cd /home/user/dev/llama
litellm --config /home/user/dev/llama/litellm-config.yaml --port 4000 --host 0.0.0.0
```

⚠️ **Known issue:** Prisma query engine will crash after 5-10 min. LiteLLM will
shut down. Use Docker Fix A for production.

---

## What does NOT work

| Approach | Why it fails |
|----------|-------------|
| SQLite (`sqlite:///./litellm.db`) | "LiteLLM's database features require PostgreSQL" |
| Docker Postgres without port forwarding | Prisma query engine can't connect to Docker internal IP |
| Docker Postgres with scram-sha-256 | P1000 auth error — Prisma can't do scram auth on ARM64 |
| No `master_key` | UI (`/ui/`) doesn't load without it |
| No `database_url` (just `master_key`) | API works but `No connected db` errors; UI partially broken |
| Native venv with Prisma (long-running) | Prisma engine crashes after 5-10 min — use Docker instead |
| `database_url: localhost:5432` in Docker LiteLLM | `localhost` = LiteLLM container, not host — use Docker DNS `litellm-db:5432` |

---

## Infrastructure reference

All credentials, start commands, and service URLs are documented at:
`/home/user/dev/infrastructure/README.md`

Includes: LiteLLM, Neo4j, Phoenix, llama-servers, Hermes API, Docker network
topology, one-liner startup, and known issues.
