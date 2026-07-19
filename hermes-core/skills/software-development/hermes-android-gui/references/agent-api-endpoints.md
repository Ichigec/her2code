# Agent API Endpoints (api_server.py)

Added 2026-06-29. Three endpoints for agent preset discovery and activation in the REST API server.

## Endpoints

### GET /v1/agents
List all available agent presets from the shared registry (`agent/agents.py`).

Response:
```json
{
  "object": "list",
  "data": [
    {
      "id": "build",
      "label": "Build",
      "description": "Full dev access",
      "mode": "primary",
      "emoji": "🔨",
      "model": null,
      "reasoning": "high",
      "toolsets": ["terminal", "file", "web", "browser", "delegation"]
    }
  ]
}
```

### POST /v1/agents/activate
Activate an agent preset with optional session-key persistence.

Request:
```json
{"id": "build", "session_key": "optional-stable-key"}
```

Response:
```json
{
  "activated": "build",
  "label": "Build",
  "emoji": "🔨",
  "toolsets": ["terminal", "file", "web", "browser", "delegation"],
  "reasoning": "high",
  "model": null
}
```

Persistence: stored in `self._agent_overrides[session_key]`. Subsequent
`/v1/chat/completions` with matching `X-Hermes-Session-Key` header
auto-resolve the override.

### agent_id in POST /v1/chat/completions
Pass `agent_id` in the request body to apply the preset before running:

```json
{
  "model": "hermes-agent",
  "agent_id": "plan",
  "messages": [{"role": "user", "content": "..."}]
}
```

Resolution priority: 1. `body.agent_id`  2. `_agent_overrides[session_key]`  3. None (use default)

## Server-side changes (`gateway/platforms/api_server.py`)

1. `__init__`: added `_agent_overrides: Dict[str, str] = {}` field
2. `_handle_agents()` — GET /v1/agents handler
3. `_handle_agents_activate()` — POST /v1/agents/activate handler
4. `_resolve_agent_override(session_key)` — lookup helper
5. `_create_agent(agent_id=...)` — new parameter, calls `apply_agent(agent, agent_def)`
6. `_run_agent(agent_id=...)` — new parameter, passes through to `_create_agent`
7. `_handle_chat_completions` — extracts `agent_id` from body and session_key override
8. Session chat handlers (`_handle_session_chat`, `_handle_session_chat_stream`) — same agent_id support
9. Route registrations in `_start_http_server()`
10. Capabilities updated: `agents_api: true`, endpoint listings

## What `apply_agent()` changes (agent/agents.py:653)

```python
agent_obj.enabled_toolsets = agent_def.toolsets          # e.g. build → [terminal, file, web, browser, delegation]
agent_obj.tools = get_tool_definitions(...)               # resolved tool schemas
agent_obj.reasoning_effort = agent_def.reasoning          # e.g. "high"
agent_obj.switch_model(new_model=agent_def.model)         # optional model override
agent_obj.ephemeral_system_prompt = agent_def.system_prompt  # full prompt from ~/.hermes/agents/<id>.md
agent_obj._permission_policy = build_permission_policy(agent_def)  # e.g. plan → readonly
```

## Android client changes

| File | Change |
|------|--------|
| `ChatRequest.kt` | + `@Json(name = "agent_id") val agentId: String?` |
| `AgentDto.kt` | NEW — `AgentsResponse`, `AgentDto`, `AgentActivateRequest`, `AgentActivateResponse` |
| `HermesApi.kt` | + `getAgents()`, `activateAgent()` |
| `ChatRepository.kt` | + `getAgents()`, `activateAgent()`; `sendMessage/streamMessage` pass `agentId` |
| `ChatViewModel.kt` | + `activateAgent()`; **removed** hardcoded agent prompts |
| `NavGraph.kt` | + 🤖 agent button in BottomToolbar + `AgentSelector` dialog integration |

## Verification

```bash
# Check agents list (34 presets)
curl -s http://localhost:8643/v1/agents | python3 -c "import sys,json; print(len(json.load(sys.stdin)['data']))"

# Activate build agent
curl -s -X POST http://localhost:8643/v1/agents/activate \
  -H "Content-Type: application/json" \
  -d '{"id":"build"}'

# Send message with agent_id
curl -s -X POST http://localhost:8643/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $KEY" \
  -d '{"model":"hermes-agent","agent_id":"plan","messages":[{"role":"user","content":"Say hello in 3 words."}],"stream":false}'
```
