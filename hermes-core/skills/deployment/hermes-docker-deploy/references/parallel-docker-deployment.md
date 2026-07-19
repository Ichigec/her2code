# Parallel Docker Deployment — Second Hermes Instance

Run a Docker-based Hermes instance **alongside** the main host-based Hermes,
sharing the same LLM infrastructure (llama-server, LiteLLM). Verified working
2026-07-07.

## Architecture

```
MAIN HERMES (host process)              PORTABLE HERMES (Docker)
┌──────────────────────────┐            ┌──────────────────────────────┐
│ Gateway    :18648        │            │ Gateway      :18649          │
│ Dashboard  :9121         │            │ Dashboard    :9123           │
│ z.ai GLM-5.2 (cloud)     │            │ qwen3.6-35b-heretic (local)  │
└───────────┬──────────────┘            └───────────┬──────────────────┘
            │                                       │
            └────────► llama-server :8092 ◄─────────┘
            └────────► LiteLLM :4000       ◄─────────┘
```

## Port allocation (no conflicts)

| Service       | Main   | Portable |
|---------------|--------|----------|
| Gateway API   | :18648 | :18649   |
| Dashboard     | :9121  | :9123    |
| llama-server  | :8092  | (shared) |
| LiteLLM       | :4000  | (shared) |

**⚠️ Portable dashboard is :9123, NOT :9122!** Main Hermes auto-restarts its
dashboard on :9122. Portable must use :9123 to avoid collision.

## Volume layout (separate volumes!)

```
~/.hermes-portable/         ← gateway volume
  ├── config.yaml           (provider: custom:llama-local)
  ├── .env                  (API_SERVER_KEY, API_SERVER_PORT=18649)
  ├── state.db
  ├── logs/
  └── sessions/

~/.hermes-portable-dash/    ← dashboard volume (SEPARATE!)
  ├── config.yaml           (copy of gateway config)
  ├── .env                  (NO API_SERVER_* vars! only DASHBOARD_SESSION_TOKEN)
  ├── tui_gateway/          (copied from hermes-agent source)
  └── logs/
```

**CRITICAL:** Dashboard `.env` must NOT contain `API_SERVER_ENABLED`,
`API_SERVER_PORT`, or `API_SERVER_KEY`. Otherwise the dashboard tries to start
its own api_server on the gateway's port → `Port already in use` crash-loop.
See SKILL.md → "Shared volume pitfalls" → Root cause 2.

## Docker run commands

```bash
# ── Gateway ──
docker run -d --name hermes-gateway --restart unless-stopped \
  --network host \
  -v ~/.hermes-portable:/opt/data \
  -e HERMES_UID=$(id -u) \
  -e HERMES_GID=$(id -g) \
  -e API_SERVER_PORT=18649 \
  -e "API_SERVER_KEY=$(grep '^API_SERVER_KEY=' ~/.hermes-portable/.env | cut -d= -f2)" \
  -e LLAMA_CPP_API_KEY=llama-cpp \
  -e HERMES_DISABLE_MESSAGING=1 \
  -e GATEWAY_ALLOW_ALL_USERS=true \
  hermes-agent gateway run

# ── Dashboard (separate volume!) ──
docker run -d --name hermes-dashboard --restart unless-stopped \
  --network host \
  -v ~/.hermes-portable-dash:/opt/data \
  -e HERMES_UID=$(id -u) \
  -e HERMES_GID=$(id -g) \
  -e HERMES_DASHBOARD_SESSION_TOKEN=sk-docker-b \
  -e PYTHONPATH=/opt/data \
  -e GATEWAY_HEALTH_URL=http://127.0.0.1:18649/health \
  hermes-agent dashboard --host 127.0.0.1 --port 9123 \
    --insecure --tui --no-open --skip-build
```

## Verification (8-point checklist)

```bash
# 1. Main gateway still works
curl -sf http://127.0.0.1:18648/health

# 2. Portable gateway health
curl -sf http://127.0.0.1:18649/health

# 3. Portable dashboard
curl -sf http://127.0.0.1:9123/api/status | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'v{d[\\\"version\\\"]} gw={d[\\\"gateway_running\\\"]}')"

# 4. Chat works (extract key from .env, test with timeout=120 for reasoning models)
API_KEY=$(grep '^API_SERVER_KEY=' ~/.hermes-portable/.env | cut -d= -f2)
curl -sf -m 120 http://127.0.0.1:18649/v1/chat/completions \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3.6-35b-heretic","messages":[{"role":"user","content":"Say OK"}],"max_tokens":20}'

# 5. NO port conflicts in dashboard logs
docker logs hermes-dashboard 2>&1 | grep -c "Port.*already in use"  # must be 0

# 6. Volumes owned by host user
stat -c '%U:%G' ~/.hermes-portable ~/.hermes-portable-dash  # both pavel:pavel

# 7. Shared LLM infra healthy
curl -sf http://127.0.0.1:8092/v1/models | python3 -c "import sys,json; print(json.load(sys.stdin)['data'][0]['id'])"
curl -sf http://127.0.0.1:4000/health/readiness | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])"

# 8. Both gateways respond independently
diff <(curl -sf http://127.0.0.1:18648/health) <(curl -sf http://127.0.0.1:18649/health)
```

## GUI switching

```bash
# Connect GUI to portable dashboard
cat > ~/.config/Hermes/connection.json << 'EOF'
{"mode":"remote","remote":{"url":"http://localhost:9123","token":{"value":"sk-docker-b"},"authMode":"token"},"profiles":{}}
EOF

# Return to main Hermes
echo '{"mode":"local"}' > ~/.config/Hermes/connection.json
```

## Startup script

`~/dev/hermes_portable/start.sh` handles all of this:
```bash
cd ~/dev/hermes_portable
REAL_HOME=/home/user bash ./start.sh full       # gateway + dashboard
REAL_HOME=/home/user bash ./start.sh gui        # connect GUI
REAL_HOME=/home/user bash ./start.sh status     # check all
REAL_HOME=/home/user bash ./start.sh stop       # stop portable (main untouched)
```

**Note:** `REAL_HOME` must be set explicitly when running inside Hermes Agent,
because Hermes overrides `$HOME` to `~/.hermes/home`. The script uses
`getent passwd $(id -u)` to detect the real home, but `REAL_HOME=/home/user`
bypasses any edge cases.

## Common issues

| Issue | Fix |
|-------|-----|
| Dashboard crash-loop: `Port already in use` | Dashboard reads gateway `.env` → use separate volume for dashboard |
| Volume files owned by UID 10000 | Add `-e HERMES_UID=$(id -u) -e HERMES_GID=$(id -g)` |
| `/v1/chat/completions` times out | Reasoning model (xhigh) needs 120s timeout; check `max_tokens ≥ 20` |
| `Invalid API key` (401) | Extract real key: `grep API_SERVER_KEY ~/.hermes-portable/.env` |
| Dashboard startup takes 90+ seconds | First run builds web UI; subsequent runs use `--skip-build` cache |
| `unknown shorthand flag: 'd' in -d` | Docker compose V1 vs V2 — auto-detect `docker compose` vs `docker-compose` |
| Containers stuck on `Fixing ownership` | s6-overlay `chown -R` on 4.65GB ARM64 image — normal, takes 5+ min |
| `HERMES_HOME` points to `~/.hermes` | Parent Hermes exports it — `unset HERMES_HOME` at script start |
| `--env-file` unknown flag | Old Docker — remove flag, export vars before compose call |
| GUI won't start after hang | Rewrite connection.json, clean SingletonLock + systemd scopes |
