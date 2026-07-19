# Hermes Gateway API Setup — Pitfalls & Solutions

## Port Configuration (dual-key trap)

Hermes Gateway API server reads port from `platforms.api_server.port`, NOT from `api_server.port`. Both must be set:

```bash
hermes config set api_server.port 8648
hermes config set platforms.api_server.port 8648
```

Verify:
```bash
grep "port: 864" ~/.hermes/config.yaml
# Должно быть два вхождения: оба 8648
```

## Gateway won't start — port already in use

**Symptom:** `grep api_server ~/.hermes/logs/gateway.log` shows:
```
ERROR gateway.platforms.api_server: [Api_Server] Port 8643 already in use.
```

**Root cause:** Another process (unified_proxy, socat, stale sshd-session) holds the port.

**Fix:**
```bash
# Kill ALL processes on the port
fuser -k 8643/tcp
sleep 2
# Kill any stale gateway processes
kill $(pgrep -f "hermes gateway") 2>/dev/null
sleep 1
# Start gateway
hermes gateway run
```

## Watchdog interference

A watchdog loop (`while true; do curl health; restart if dead; done`) can restart unified_proxy on port 8643 BEFORE the gateway binds. This creates a race: gateway tries 8648 (or 8643) → fails → watchdog restarts proxy on 8643 → gateway retries → fails again.

**Fix:** Kill the watchdog BEFORE starting gateway:
```bash
pkill -f "while true.*8643.*health"  # in background terminal!
```

## Gateway API verification

```bash
# Health (Docker Gateway on 18649)
curl http://localhost:18649/health

# Models (requires auth — key from Docker .env)
GATEWAY_KEY=$(docker exec hermes-gateway env | grep API_SERVER_KEY | cut -d= -f2)
curl -H "Authorization: Bearer *** http://localhost:18649/v1/models

# Chat completion (deepseek-chat через LiteLLM)
curl -X POST http://localhost:18649/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer *** \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"Who are you"}],"stream":false}'
```

Expected response: непустой content (DeepSeek отвечает "Hello! How can I help you today?").

**Питфол:** Пустой ответ (`completion_tokens: 0`) = Gateway не достучался до model backend. Проверить `docker logs hermes-gateway --tail 50` на `APIConnectionError`. См. `references/docker-gateway-litellm-routing.md`.

## Architecture: no proxy needed

When Hermes Gateway API is running directly on the SSH-forwarded port:
```
Phone → VPS:8643 → SSH → Jetson:8643 → Hermes Gateway API
```

No unified_proxy needed. No socat. No routing. Hermes Gateway handles everything.

## Gateway persistence

Gateway dies when terminal session ends. Use background + watchdog:
```bash
# Start in background
nohup hermes gateway run > /tmp/hermes_gateway.log 2>&1 &

# Watchdog (checks every 60s)
while true; do
  if ! curl -s --max-time 3 http://localhost:8648/health | grep -q ok; then
    fuser -k 8648/tcp 2>/dev/null
    sleep 2
    hermes gateway run &
  fi
  sleep 60
done
```
