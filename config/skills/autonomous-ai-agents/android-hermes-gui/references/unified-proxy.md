# Unified Proxy — Architecture & Implementation

The unified proxy (`/home/user/unified_proxy.py`) is the SINGLE entry point for all Android app requests. It replaces the previous multi-component chain (SSH tunnel + socat + proxy + watchdog) with ONE Python process.

## Why One Process

The original architecture had 4+ components:
- SSH reverse tunnel (managed by shell script)
- socat (8643→8647)
- HTTP proxy (Python, port 8647)
- Watchdog (bash loop)

Each component could die independently. pkill from foreground killed the terminal. Background processes died silently. Multiple watchdogs conflicted. The unified proxy eliminates all these failure modes.

## Routing Logic

```
Request → unified_proxy:8643
              │
              ├─ model in AGENT_MODELS? → OpenCode+:8646 (with client's auth)
              └─ otherwise → LiteLLM:4000 (with sk-local key)
```

**AGENT_MODELS:** `hermes-agent`, `general`, `build`, `plan`, `review`, `safe`, `explore`, `scout`, `deep-explore`, `claw`, `composter`

**Chat models:** Everything else — `qwen3.6-35b-heretic`, `deepseek-chat`, `gpt-4o`, etc. → LiteLLM with `Bearer sk-local`.

**Alternative: route chat models to Hermes Gateway API instead of LiteLLM:**
```python
HERMES_API = 'http://127.0.0.1:8648/v1/chat/completions'
# Use this instead of LITELLM to get real Hermes agent capabilities
```

## SSH Tunnel Thread

Built-in `tunnel_thread()` runs as a daemon thread inside the proxy process:
- Checks health every 30s: `ssh root@VPS "curl localhost:8643/health"`
- On failure: `fuser -k 8643/tcp` on VPS (clean stale sessions), then `ssh -fN -R`
- Uses `subprocess.run()` for health checks, `subprocess.Popen()` for tunnel
- **Critical:** add `time.sleep(2)` between `fuser -k` and new `ssh` — stale sessions need time to release

## Why No socat

The proxy listens on port 8643 DIRECTLY. No intermediate TCP forwarder needed. Eliminates one failure point.

## Health Check

`GET /health` → `{"status":"ok"}` — used by:
- Android HealthCheckManager (every 30s)
- Tunnel thread (every 30s)
- VPS watchdog cron

## Logging

Writes to `/tmp/proxy.log` with format: `[HH:MM:SS] → model → OC+/Hermes msgs=N` / `← STATUS`

## Startup

```bash
# Via Hermes terminal (background=true)
/home/user/.hermes/hermes-agent/venv/bin/python3 -u /home/user/unified_proxy.py 8643

# With nohup for persistence
nohup /home/user/.hermes/hermes-agent/venv/bin/python3 -u /home/user/unified_proxy.py 8643 > /tmp/proxy_stdout.log 2>&1 &
```

## Pitfalls

1. **Port conflict with Hermes Gateway API.** If Hermes gateway is configured on 8643, the proxy can't bind. Solution: move Hermes to 8648 (`platforms.api_server.port`), keep proxy on 8643.
2. **Model name mismatch.** LiteLLM expects `openai/qwen3.6-35b-heretic` but Hermes config expects `qwen3.6-35b-heretic` (custom provider match). The proxy sends the model name AS-IS from the client.
3. **SSE streaming.** The proxy reads backend response in 8KB chunks and flushes immediately — supports real-time SSE streaming.
4. **nohup zombie.** If the proxy dies, the nohup process stays as zombie. Watchdog (`while true; curl health; restart`) handles this.
