# Hermes API Server — External Client Protocol

How to build external clients (mobile, web, desktop) that talk to Hermes Agent
and OpenCode+ over HTTP. Captured from building a full PWA + Android client against
both backends.

## Starting the API Server

The Hermes API server is NOT running by default. It must be started explicitly:

```bash
# Check if api_server is in platforms config
grep -A5 'api_server' ~/.hermes/config.yaml

# The API key is in .env
grep 'API_SERVER' ~/.hermes/.env

# Start the gateway (API server runs inside it)
hermes gateway run   # foreground, or use nohup for background
```

Verify: `curl http://localhost:8642/health` → `{"status":"ok"}`.

The gateway must stay running. For persistence across reboots:
`hermes gateway install` + `hermes gateway start` (systemd user service).

## Hermes API Server (`gateway/platforms/api_server.py`)

Default: `http://127.0.0.1:8642`. Must be enabled in gateway config
(`api_server` platform). Auth: `Authorization: Bearer <API_SERVER_KEY>`
from `.env`.

### Core Endpoints

| Method | Path | Purpose | Client use |
|--------|------|---------|------------|
| `GET` | `/health` | Liveness check | Connection indicator |
| `GET` | `/v1/models` | List available models | Model picker population |
| `GET` | `/v1/capabilities` | Tools, MCP servers, models, agents | Tools/MCP toggle + model list |
| `POST` | `/v1/chat/completions` | OpenAI-compatible chat with SSE streaming | Primary chat interface |
| `GET` | `/api/sessions` | List sessions | Conversation history |
| `GET` | `/api/sessions/:id/messages` | Message history for a session | Load past conversation |
| `POST` | `/v1/runs` | Async runs with approval flow | Code execution with approval gate |
| `POST` | `/v1/runs/:id/approval` | Resolve pending approval | User approves/denies code exec |

### SSE Streaming (`/v1/chat/completions`)

- Request: standard OpenAI Chat Completions body with `"stream": true`
- Response: `text/event-stream` with `data: {...}` frames
- Terminal frame: `data: [DONE]`
- Each frame is a `ChatCompletionChunk` with `choices[0].delta.content` (text) or `choices[0].delta.tool_calls` (tool invocations)
- `finish_reason` signals end of turn (null during streaming, "stop"/"tool_calls" at end)
- Tool calls arrive incrementally across multiple frames (index-based merging needed)
- Test with: `curl -s -N http://localhost:8642/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d '{"model":"hermes-agent","messages":[{"role":"user","content":"hi"}],"stream":true}'`

### Capabilities (`/v1/capabilities`)

Returns `{"tools": [...], "mcp_servers": [...], "models": [...], "agents": [...]}`.
Use this to populate tool/MCP toggle UI and discover available models.

### Models (`/v1/models`)

Returns `{"data": [{"id": "model-name", "owned_by": "hermes-agent"}]}`.
Standard OpenAI format — any OpenAI-compatible client library works.

## OpenCode+ HTTP API

Default: `http://127.0.0.1:3400` (from `opencode web`). No auth required
for local use.

### Core Endpoints

| Method | Path | Purpose | Client use |
|--------|------|---------|------------|
| `GET` | `/global/health` | Liveness + version | Connection indicator |
| `GET` | `/provider` | All providers, connected list, default map | Model picker — iterate `all[].models` keys |
| `GET` | `/config` | Full config including agent definitions | Agent picker — read `agent` keys |
| `POST` | `/session` | Create session (title, agent, model) | Start new conversation |
| `POST` | `/session/:id/message` | Send message, get response | Chat turns |
| `DELETE` | `/session/:id` | Delete session | Cleanup |
| `POST` | `/session/:id/abort` | Abort running generation | Stop button |

### Session Creation

```json
{
  "title": "session-name",
  "agent": "build",
  "model": {"providerID": "litellm", "modelID": "deepseek-v4-pro"}
}
```
Returns a session object with `id`. Keep the `id` for subsequent messages.

### Message Sending

```json
{
  "parts": [{"type": "text", "text": "user message"}],
  "model": {"providerID": "...", "modelID": "..."}  // optional per-message override
}
```
Returns `{"info": {"tokens": {...}, "cost": ...}, "parts": [{"type": "text", "text": "..."}]}`.

**Key difference from Hermes:** OpenCode+ messages are synchronous request-response
(no SSE streaming in the current API). The response includes the full answer.
Session expiry: if a session returns 4xx, the session ID is stale — recreate.

### Model/Agent Discovery

- Models: `GET /provider` → each provider has a `models` dict; keys are model IDs.
  Format for display: `"providerID/modelID"`.
- Agents: `GET /config` → `agent` keys are agent names. Each has `mode`, `model`, `description`.
- Connected providers: `GET /provider` → `connected` array shows authenticated ones.

### Model/Agent Switching

To switch models or agents mid-session: create a new session with the new
model/agent, or pass a model override in the message payload. Sessions are
independent — there's no global conversation state.

## PWA (Progressive Web App) — Preferred Mobile Delivery

When the user asks for a mobile app, the PWA pattern is the go-to deliverable:

- **Single HTML file** with inline CSS/JS — no compilation, no SDK, immediately usable.
- **SSE streaming** via `fetch()` + `ReadableStream` reader — no OkHttp needed.
- **localStorage** for conversation persistence — no Room/DataStore dependency.
- **Service Worker** (`sw.js`) + **Web Manifest** (`manifest.json`) for "Add to Home Screen" install.
- **Mobile-optimized**: `viewport-fit=cover`, `safe-area-inset-bottom`, `user-scalable=no`.
- **Served via** `python3 -m http.server 8080 --bind 0.0.0.0` — phone accesses on LAN IP.
- **No auth client-side**: API keys are pre-configured in the HTML (local dev) or fetched from settings panel.

Full working PWA at `/home/user/dev/hermes/web/` — chat with both backends,
model/agent switching, tools/MCP toggle, settings, conversation persistence.

### Required PWA Features (from user feedback)

Building just a chat UI is insufficient. Users need these for production use:

**Connection monitoring (mandatory):**
- Header badges showing real-time connection status for EACH backend (green dot = connected, red = down).
- Log panel (📋 button) with timestamped entries: successful connections, HTTP errors, streaming starts/completions, token counts.
- Auto-reconnect: poll health endpoints every 15–30 seconds. Show reconnect count. Don't spam — exponential backoff on persistent failures.

**Error visibility:**
- Display ALL HTTP errors inline in the chat (not just console.log). User sees "Error: HTTP 502" as a red system message.
- Surface connection failures BEFORE the user types a message — proactive health checks, not reactive on-send failures.
- Differentiate backend-down vs network-down vs auth-failure in error messages.

**Log panel design:**
- Monospace font, 200-entry ring buffer, newest-first.
- Color-coded: success (green), error (red), warning (yellow), info (dim white).
- Each entry: `[HH:MM:SS] message`. No verbose stack traces — just actionable messages.
- Persistent across page reloads (optional — `localStorage` or just in-memory ring buffer).

**Offline resilience:**
- Service Worker caches the app shell (HTML, CSS, JS) so the UI loads even when the backend is down.
- When backend is unreachable, show last-known messages from localStorage.
- Don't clear the message list on connection loss — only on explicit "New Chat" action.

### Physical Device Access

Android emulator uses `10.0.2.2` → host localhost. Physical phones need the
host's LAN IP (e.g., `192.168.0.48`). Find it: `hostname -I | awk '{print $1}'`.
Phone must be on the same WiFi network. Tell the user to open `http://<IP>:8080`
in their phone browser.

## Android-Specific Patterns

### Emulator → Host

Android emulator uses `10.0.2.2` to reach host `localhost`. Default URLs in
the app use this address so it works out of the box on emulators:

```
Hermes:   http://10.0.2.2:8642
OpenCode: http://10.0.2.2:3400
```

For physical devices, use the host's LAN IP (e.g., `192.168.1.100`).

### SSE Streaming with OkHttp

OkHttp's SSE support (`okhttp-sse` artifact) provides `EventSource` and
`EventSourceListener`. The listener callbacks (`onEvent`, `onFailure`) run
on OkHttp's background thread — UI updates must be posted to the main thread
(via `MutableStateFlow` which Compose observes on the main thread, or explicit
`withContext(Dispatchers.Main)`).

Since SSE callbacks are not suspending, use `runBlocking` to read DataStore
flows for URL and API key at call site. This is acceptable because the blocking
call reads a local preference (sub-millisecond) and only happens once per stream
setup.

### Room for Conversation Persistence

Schema: `conversations` table (id, backend, title, model, agent, session_id,
created_at, updated_at) + `messages` table (id, conversation_id, role, content,
tool_calls_json, timestamp). Foreign key with CASCADE delete so removing a
conversation removes its messages.

### DataStore for Settings

Use `preferencesDataStore` with string keys for URLs, API keys, model names,
agent names, and enabled tools/MCP sets (comma-joined strings for sets).

## Pitfalls

- **Hermes API server is NOT running by default**: must explicitly start the
  gateway (`hermes gateway run`) with `api_server` platform in config. The API
  key lives in `~/.hermes/.env` as `API_SERVER_KEY`. Verify with
  `curl localhost:8642/health`.
- **Don't deliver uncompilable source code as a mobile app**: building an
  Android APK requires Android SDK + Gradle, which typically aren't on the
  Hermes host. When the user asks for a mobile app, deliver a PWA — it works
  immediately in the phone browser, can be installed to the home screen, and
  requires zero toolchain. The user's ask is a working deliverable, not a source
  tree. Only write native code if the user explicitly requests a native app AND
  has the SDK available.
- **OpenCode+ sessions expire**: if `POST /session/:id/message` returns 4xx,
  the session is stale. Recreate with `POST /session` and retry. Don't keep
  retrying a dead session ID.
- **`POST /session` 400 on OpenCode+**: model doesn't exist in the provider.
  Always `GET /provider` first and use a model ID from the provider's `models` dict.
- **SSE stream stays open**: the agent may stream tool calls + multiple turns
  before the final `[DONE]`. Client must handle long-lived connections.
  Set read timeout to 300s.
- **Tool calls arrive across multiple SSE frames**: an indexed `tool_calls` array
  in the delta needs client-side merging — frame N may have `tool_calls[0].function.name`
  and frame N+1 has `tool_calls[0].function.arguments`. Merge by index.
- **`usesCleartextTraffic="true"`**: required in AndroidManifest for HTTP
  (non-TLS) connections to local servers. Remove for production with HTTPS.
- **API key in Authorization header**: Hermes expects `Authorization: Bearer <key>`.
  OpenCode+ (local) needs no auth header.
