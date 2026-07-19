# OpenCode HTTP API Reference

OpenCode can be started as an HTTP server: `opencode web --hostname 127.0.0.1 --port 3400`

## Endpoints

### Health Check
```
GET /global/health
Response: {"healthy": true, "version": "1.15.5"}
```

### Providers & Models
```
GET /provider
Response: {
  "all": [{ "id": "openai", "name": "OpenAI", "models": { "gpt-5.5": {...} } }],
  "connected": ["openai", "litellm", "opencode"],
  "default": { "openai": "gpt-5.5", ... }
}
```

Also supports `GET /config` for custom providers.

### Sessions (Subagents)

Sessions are OpenCode's equivalent of "subagents" — isolated conversation instances.

```
POST /session
Body: { "title": "my-agent", "agent": "build", "model": {"providerID": "openai", "modelID": "gpt-5.5"} }
Response: { "id": "ses_...", "title": "my-agent", "agent": "build", "model": {...} }

DELETE /session/:id

POST /session/:id/abort

POST /session/:id/message
Body: { "parts": [{"type": "text", "text": "task text"}] }
Response: {
  "info": { "sessionID": "...", "modelID": "...", "tokens": {...}, "cost": 0.001 },
  "parts": [{"type": "text", "text": "response"}]
}
```

### Event Stream (SSE)

```
GET /event
Headers: Accept: text/event-stream
Response: Stream of `data: {...}` frames

Event types: message.created, message.updated, message.completed, part.updated
Each event contains: type, sessionID, properties
```

## Session vs CLI Comparison

| Feature | CLI (`opencode run`) | HTTP API (sessions) | TUI (`opencode`) |
|---------|---------------------|---------------------|-------------------|
| One-shot | ✅ | ❌ (needs session lifecycle) | ❌ |
| Multi-turn | ❌ | ✅ (message per turn) | ✅ |
| Parallel | ✅ (separate commands) | ✅ (separate sessions) | ❌ (one instance) |
| Real-time | ❌ | ✅ (SSE stream) | ✅ (TUI) |
| Background | ✅ | ✅ | ❌ |
| Model switching mid-session | ❌ | ✅ (specify per message) | ✅ (Ctrl+X M) |
| Programmatic control | ❌ | ✅ | Partial (via stdin) |

## Known Issues

- `POST /session` returns 400 if the model doesn't exist in the specified provider. Verify with `GET /provider` first.
- Model IDs are provider-specific. Always check `GET /provider` for valid IDs. The `connected` array shows which providers are authenticated.
- SSE stream stays open — needs timeout or stop signal.
- Session creation payload requires `"model.providerID"` and `"model.modelID"` as nested objects, not strings.
- Some providers (like `litellm`, `opencode`) have their own model namespace. The `default` map in `/provider` response shows default model per provider but may not all be usable — always verify the model exists in the provider's `models` dict.

## Real-World Connected Providers (from production session 2026-06-07)

Connected: `openai`, `litellm`, `opencode`
- `openai`: 52 models including gpt-5.5, gpt-5.4-pro, o3, o1
- `litellm`: 8 models including qwen3.6-35b-heretic (local LM Studio/llama.cpp)
- `opencode`: 5 models including big-pickle, deepseek-v4-flash-free

Use `GET /provider` to get the live list — this changes as you add/remove API keys.

## Python Client Pattern (Robust)

Use this pattern for creating and managing OpenCode sessions as subagents:

```python
import requests, json

BASE = "http://localhost:3400"

# Step 1: Verify health and get provider list
r = requests.get(f"{BASE}/global/health")
assert r.json()["healthy"]
providers = requests.get(f"{BASE}/provider").json()
connected = providers.get("connected", [])
# Use a connected provider with known models
provider_id = connected[0]
model_id = list(providers["all"][0]["models"].keys())[0]

# Step 2: Create session (subagent)
session = requests.post(f"{BASE}/session", json={
    "title": "agent-name",
    "agent": "build",  # or "plan"
    "model": {"providerID": provider_id, "modelID": model_id}
}).json()

# Step 3: Send message
resp = requests.post(
    f"{BASE}/session/{session['id']}/message",
    json={"parts": [{"type": "text", "text": "your task"}]}
).json()
# Response contains 'info' with tokens/cost and 'parts' with text output

# Step 4: (Optional) Listen to SSE for real-time events
r = requests.get(f"{BASE}/event", headers={"Accept": "text/event-stream"}, stream=True)
for line in r.iter_lines():
    if line.startswith(b"data:"):
        event = json.loads(line[5:])
        if event.get("sessionID") == session["id"]:
            print(f"[{event['type']}] {event.get('properties', {})}")
```
