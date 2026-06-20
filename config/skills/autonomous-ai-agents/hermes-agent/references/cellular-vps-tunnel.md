# Cellular Connectivity via VPS Tunnel

Connecting Android/remote clients to Hermes over cellular networks through a VPS SSH reverse tunnel.

## Architecture (Two Backends)

```
📱 (cellular) → VPS:8643 → SSH -R → Jetson:8643 → unified_proxy
                                                    ├─ Chat models → Hermes API (8648) or LiteLLM (4000)
                                                    └─ Agent models → OpenCode+ (8646)
```

### Hermes Gateway API (preferred for H mode)

```bash
# Configure port — MUST use platforms.api_server.port, NOT api_server.port
hermes config set platforms.api_server.port 8648
# hermes config set api_server.port 8648  ← LOOKS like it works, but gateway ignores it

# Start gateway (includes API server)
hermes gateway run --replace   # --replace if stale PID file exists
```

The gateway provides OpenAI-compatible `/v1/chat/completions` served by the REAL Hermes agent — with tools, memory, skills, and personalities. Use model `qwen3.6-35b-heretic` (local via LiteLLM custom provider) or any configured model.

**Pitfall: `platforms.api_server.port` vs `api_server.port`.** `hermes config set api_server.port 8648` writes to top-level `api_server.port`. But `hermes gateway run` reads from `platforms.api_server.port`. The top-level key exists but is NOT used by the gateway. Error: "Port 8643 already in use. Set a different port in config.yaml: platforms.api_server.port". Always use `hermes config set platforms.api_server.port <port>`.

**Pitfall: gateway PID file.** If gateway process is killed but PID file remains, `hermes gateway run` refuses to start ("Gateway already running"). Use `--replace` flag or `rm -f /tmp/hermes-gateway.pid`.

### LiteLLM (alternative chat backend)

LiteLLM on port 4000 proxies to local LLM:
- Key: `sk-local`
- Default model: `qwen3.6-35b-heretic` (local, no rate limit)
- **Model name MUST include `openai/` prefix for LiteLLM:** `openai/qwen3.6-35b-heretic`
- Avoid `deepseek-chat` — rate-limited on external API
- Hermes Gateway API expects model WITHOUT prefix: `qwen3.6-35b-heretic`

**Pitfall: model name difference.** Unified proxy sends model name AS-IS from the client. If the Android app sends `openai/qwen3.6-35b-heretic` to Hermes Gateway API, it won't match the custom provider. If it sends `hermes-agent` to LiteLLM, LiteLLM returns 400. The proxy's routing logic (checking AGENT_MODELS) handles agent routing, but chat model name must match the target backend.

## SSH Reverse Tunnel

```bash
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=5 \
    -o TCPKeepAlive=yes -o ExitOnForwardFailure=yes \
    -fN -R 0.0.0.0:8643:localhost:8643 root@VPS_IP
```

### Pitfall: pkill kills terminal
On Jetson (ARM64), `pkill -f "pattern"` from a foreground terminal kills the terminal itself. Use `fuser -k PORT/tcp` on the VPS instead, or use background processes.

### Pitfall: stale sshd-sessions on VPS
When SSH tunnel dies, the VPS sshd-session keeps the port locked. Clean with:
```bash
ssh root@VPS "fuser -k 8643/tcp 2>/dev/null; sleep 2"
```

### Pitfall: background processes silently die
`terminal(background=true)` processes can die without notification when the parent shell exits. Use `nohup` for persistence:
```bash
nohup command > /tmp/log.log 2>&1 &
# Note: & is inside the terminal command, which Hermes terminal blocks.
# Use terminal(background=true) with the nohup prefix instead.
```
Keep a watchdog checking health and restarting via `nohup ... &`. The watchdog itself must also use `nohup`:
```bash
while true; do
    if ! curl -s --max-time 3 http://localhost:8643/health | grep -q ok; then
        nohup /path/to/proxy > /tmp/log 2>&1 &
    fi
    sleep 30
done
```

### Pitfall: multiple tunnel processes conflict
Multiple watchdogs/scripts starting SSH tunnels simultaneously create competing sshd-sessions on VPS. Use ONE keeper process with health-check loop. Clean stale sessions before starting new tunnel.

### Wait after fuser -k
After killing stale VPS sessions, wait at least 4 seconds before starting new tunnel:
- `fuser -k 8643/tcp; sleep 2` (remote) + `sleep 2` (local) + `ssh -R` (takes time)

## Unified Proxy Pattern

Single Python process on port 8643:
1. Routes chat models → Hermes API or LiteLLM
2. Routes agent models (hermes-agent, general, build...) → OpenCode+ API
3. Runs built-in SSH tunnel keeper thread

```python
AGENT_MODELS = {'hermes-agent', 'general', 'build', 'plan', 'review', 'safe',
                'explore', 'scout', 'deep-explore', 'claw', 'composter'}

# Chat → LiteLLM (with sk-local key)
# Agent → OpenCode+ (passes through client's Authorization header)
```

### Tunnel keeper thread (built into proxy)
- Health check every 30s: `ssh root@VPS "curl 127.0.0.1:8643/health"`
- On failure: `fuser -k 8643/tcp` on VPS → wait 4s → new `ssh -R` → wait 10s
- Never uses `pkill` — kills the proxy itself on Jetson
- Never kills existing SSH processes — just starts new one

## OpenCode+ step_start Protocol

OpenCode+ agents output `{"type":"step_start",...}` as response text. This is protocol, not chat content.

### Client-side workaround (Android):
```kotlin
// ChatViewModel.kt — if response is ONLY protocol JSON, show friendly message
if (responseText.startsWith("{\"type\":\"step_start\"") &&
    !responseText.contains("\"content\":")) {
    displayText = "Агент не ответил. Попробуйте ещё раз."
}
```

Root cause: OpenCode+ agent generates protocol events as text. Server-side fix needed; client-side filter is a workaround. Hermes Gateway API doesn't have this problem — use it for H mode.

## Android App Gotchas

### SharedPreferences persist old values
Changing default in `AppSettings` doesn't override stored values. Use `pm clear` to reset:
```bash
adb shell pm clear com.hermes.gui.debug
```

### Model mismatch after backend toggle
When `toggleBackend()` changes backend but SharedPreferences still has old model, old model persists. Fix: in `ensureConversation()`, detect mismatch and correct.

### Compose UI not clickable via input tap
`adb shell input tap X Y` doesn't work for Compose elements. Use `uiautomator dump` to find coordinates, but Compose may not process synthetic events. Use direct API calls for testing.

### Honor phone hilogd suppresses Log.d()
Use `Log.i()` instead of `Log.d()` for debugging on Honor devices.

## HealthCheckManager (Android)

- Checks `/health` every 30s
- 3 consecutive failures → switch to fallback URL
- 2 consecutive successes → return to primary
- ConnectionMode enum: WIFI/Tailscale/OFFLINE
- Cellular-through-VPS is labeled as WIFI (no separate CELLULAR mode)

## Common Failure Patterns

| Symptom | Cause | Fix |
|---------|-------|-----|
| Connection reset every 2nd msg | OkHttp connection pool reuses stale connections | `retryOnConnectionFailure(true)` |
| 502 from VPS (Python 3.11) | socat down or proxy dead | Restart proxy with `nohup` |
| 401 from LiteLLM | Wrong key or model routing broken | Verify `sk-local`, check `/tmp/proxy.log` |
| Tunnel keeps restarting | Health check fails before tunnel established | Add delay: 2s after fuser-k + 10s after new tunnel |
| Port 8643 occupied on VPS | Stale sshd-session | `fuser -k 8643/tcp` |
| Hermes gateway "already running" | Stale PID file after kill -9 | Use `--replace` flag |
| Android model not changing | SharedPreferences retains old value | `pm clear` or auto-correct in `ensureConversation()` |

## Simplified Architecture (Final Lesson)

After extensive debugging, the simplest reliable architecture is:

```
📱 → VPS:8643 → SSH → Jetson:8643 → Hermes Gateway API (direct!)
```

**Key insight: unified proxy is unnecessary.** Hermes Gateway API IS an OpenAI-compatible API server with tools, memory, and skills. No routing, no proxy, no socat — just one process on one port.

### Why this is better
- One process instead of proxy + socat + tunnel_keeper
- No port conflicts (8643 is Hermes, full stop)
- No model routing needed
- Hermes handles all providers internally

### Migration from proxy-based setup
1. `fuser -k 8643/tcp` — kill proxy
2. `hermes config set platforms.api_server.port 8643`
3. `hermes gateway run` — Hermes takes port 8643
4. Done. No proxy, no socat, no unified_proxy.py.

## 5-Layer Memory Architecture for Agent Development

From audit of cellular session — most time was lost re-discovering known facts:

| Layer | Storage | Pre-load | Impact |
|-------|---------|----------|--------|
| Context | AGENTS.md | Pre_llm_call hook | 100% sessions see conventions |
| Procedural | Skills | skill-router + HERMES_SKILL_ROUTER=1 | 70%+ skills auto-loaded |
| Relational | Neo4j | Vector search on :Skill embeddings | <1s retrieval |
| Session | state.db | session_search | Cross-session recall |
| Pre-flight | Hooks | Neo4j health + memory staleness | Warns before work starts |
