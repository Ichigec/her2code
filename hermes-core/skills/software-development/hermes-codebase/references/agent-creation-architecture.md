# Agent Creation Architecture: Three Call Sites & API Delegation

> How AIAgent() is constructed across the three entry points, and what it would
> take to route subagent delegation through the API server instead of in-process
> threads. Captured from a deep code exploration session (July 2026).

## The Three AIAgent() Call Sites

All three call `AIAgent(...)` — the same class in `run_agent.py:320` — but with
different parameter combinations. All are **in-process**: no HTTP between them.

```
┌──────────────────────────────────────────────────────────────────┐
│                    ONE Python process                            │
│                                                                  │
│  tools/delegate_tool.py          tui_gateway/server.py           │
│    _build_child_agent()            _make_agent()                 │
│      ↓                              ↓                            │
│  AIAgent(model=...)              AIAgent(model=...)              │
│  (for subagents)                (for GUI session)                │
│                                                                  │
│  gateway/platforms/api_server.py                                 │
│    _create_agent()                                               │
│      ↓                                                           │
│  AIAgent(model=...)                                              │
│  (for external HTTP clients)                                     │
└──────────────────────────────────────────────────────────────────┘
```

### Call Site 1: Subagent (`delegate_tool.py:1149`)

```python
child = AIAgent(
    model=effective_model,           # override from delegation config
    provider=effective_provider,     # override
    base_url=effective_base_url,     # override
    api_key=effective_api_key,       # override
    api_mode=effective_api_mode,     # auto-derived from provider
    max_iterations=max_iterations,   # from delegation.max_iterations
    enabled_toolsets=child_toolsets, # intersected with parent's
    quiet_mode=True,
    ephemeral_system_prompt=child_prompt,  # goal-specific
    skip_context_files=True,         # no AGENTS.md
    skip_memory=True,                # no MEMORY
    clarify_callback=None,           # no user interaction
    session_db=parent._session_db,   # SHARED with parent
    parent_session_id=parent.session_id,  # lineage link
    fallback_model=parent_fallback,  # parent's fallback chain
    reasoning_config=child_reasoning,
    iteration_budget=None,           # fresh budget per subagent
    log_prefix=f"[subagent-{task_index}]",
    platform=platform or parent_agent.platform,
    # session_id NOT passed → auto-generated in init_agent
)
# Post-init overrides:
child._delegate_depth = child_depth
child._subagent_id = subagent_id
child._credential_pool = child_pool  # resolved from parent or provider
```

### Call Site 2: GUI Session (`tui_gateway/server.py:2698`)

```python
agent = AIAgent(
    model=model,                      # from config or session override
    provider=runtime.get("provider"),
    base_url=runtime.get("base_url"),
    api_key=runtime.get("api_key"),
    api_mode=runtime.get("api_mode"),
    acp_command=runtime.get("command"),
    acp_args=runtime.get("args"),
    credential_pool=runtime.get("credential_pool"),
    max_iterations=_cfg_max_turns(cfg, 90),
    quiet_mode=True,
    verbose_logging=False,
    reasoning_config=_load_reasoning_config(),
    service_tier=_load_service_tier(),
    enabled_toolsets=_load_enabled_toolsets(),
    platform="tui",
    session_id=session_id or key,     # EXPLICIT session_id
    session_db=session_db,            # own DB (or profile DB)
    ephemeral_system_prompt=system_prompt,
    checkpoints_enabled=...,
    **_agent_cbs(sid),                # stream_delta, tool_progress, etc.
)
```

### Call Site 3: API Server (`api_server.py:1016`)

```python
agent = AIAgent(
    model=model,                      # from gateway config
    **runtime_kwargs,                 # provider, base_url, api_key, etc.
    max_iterations=int(os.getenv("HERMES_MAX_ITERATIONS", "90")),
    quiet_mode=True,
    verbose_logging=False,
    ephemeral_system_prompt=ephemeral_system_prompt,
    enabled_toolsets=enabled_toolsets,  # platform_toolsets.api_server
    session_id=session_id,
    platform="api_server",
    stream_delta_callback=stream_delta_callback,
    tool_progress_callback=tool_progress_callback,
    session_db=self._ensure_session_db(),
    fallback_model=fallback_model,
    reasoning_config=reasoning_config,
    gateway_session_key=gateway_session_key,
)
# Agent preset applied post-init if agent_id was specified
```

### Parameter Comparison Table

| Parameter | Subagent | GUI (tui) | API Server |
|-----------|----------|-----------|------------|
| `session_id` | Auto-generated | Explicit | From request or auto |
| `session_db` | Parent's | Own | Own (gateway) |
| `parent_session_id` | parent.session_id | None | None |
| `quiet_mode` | True | True | True |
| `skip_context_files` | True | False | False |
| `skip_memory` | True | False | False |
| `stream_delta_callback` | None | Yes (→UI) | Yes (→SSE) |
| `clarify_callback` | None | Yes | Yes |
| `credential_pool` | Parent's | From config | From config |
| `enabled_toolsets` | Intersected | From config | platform_toolsets |
| `fallback_model` | Parent's chain | From config | From config |
| `reasoning_config` | Parent or override | From config | From config |
| `_delegate_depth` | Set post-init | 0 (default) | 0 (default) |

## TUI Gateway Architecture

The desktop app communicates with the backend via **JSON-RPC** (not HTTP),
through `tui_gateway/server.py`. The gateway runs as a subprocess.

### Key RPC Methods

| Method | Purpose |
|--------|---------|
| `session.create` | Create a lightweight session (agent built deferred) |
| `prompt.submit` | Send user message → runs `agent.run_conversation()` |
| `agents.activate` | Switch agent preset |
| `agents.list` | List available agent presets |
| `session.list` / `session.resume` | Session management |
| `cli.exec` | Run `hermes_cli.main` subprocess (non-interactive) |

### Session Creation Flow

```
1. Desktop sends session.create → gateway creates _sessions[sid] dict
   with agent=None, agent_ready=threading.Event()
2. Gateway responds immediately (UI paints composer)
3. _start_agent_build() runs in background thread:
   → _make_agent(sid, key) → AIAgent(...)
   → session["agent"] = agent
   → ready.set()
4. User sends prompt.submit → _wait_agent(ready) → _run_prompt_submit()
   → agent.run_conversation(text, stream_callback=_stream)
   → Blocks the RPC thread for the entire conversation
```

### Long Handler Thread Pool

Slow RPC methods (`cli.exec`, `session.resume`, `slash.exec`, etc.) are routed
to a `ThreadPoolExecutor(max_workers=4)` so they don't block the dispatcher:

```python
_LONG_HANDLERS = frozenset({
    "browser.manage", "cli.exec", "session.branch",
    "session.compress", "session.resume", "shell.exec",
    "skills.manage", "slash.exec",
})
```

## API Server Architecture

`gateway/platforms/api_server.py` — an `aiohttp` HTTP server on port 8642.

### Key Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v1/chat/completions` | OpenAI-compatible chat (SSE streaming) |
| `POST` | `/v1/runs` | **Async** agent run — returns run_id immediately |
| `GET` | `/v1/runs/{id}` | Poll run status |
| `GET` | `/v1/runs/{id}/events` | SSE stream of run events |
| `POST` | `/v1/runs/{id}/approval` | Resolve pending approval |
| `DELETE` | `/v1/runs/{id}` | Abort a run |
| `POST` | `/v1/agents/activate` | Switch agent preset |
| `GET` | `/api/sessions` | List sessions |

### `/v1/runs` — Async Run (Already Exists!)

The `/v1/runs` endpoint already provides the infrastructure for non-blocking
agent execution:

```python
# POST /v1/runs → returns run_id immediately
# Agent runs in loop.run_in_executor(None, _run)
# Events stream via asyncio.Queue → SSE
# Max 10 concurrent runs (_MAX_CONCURRENT_RUNS)
# Status: queued → running → waiting_for_approval → completed/failed
```

**This is the key insight:** `/v1/runs` already does what OpenCode's
`POST /session/:id/prompt_async` does — start an agent run and return
immediately. It's just not wired to `delegate_task`.

### `_run_agent()` — How the API Server Runs Agents

```python
async def _run_agent(self, user_message, conversation_history, ...):
    loop = asyncio.get_running_loop()

    def _run():
        agent = self._create_agent(...)      # fresh AIAgent
        result = agent.run_conversation(...)  # blocks this thread
        return result, usage

    return await loop.run_in_executor(None, _run)  # async wrapper
```

## API Delegation: Gap Analysis

What's missing to route `delegate_task` through the API server instead of
in-process threads.

### What's Already Ready

| Component | Status | Location |
|-----------|--------|----------|
| `_create_agent()` | ✅ Ready | `api_server.py:969` |
| `_run_agent()` with `run_in_executor` | ✅ Ready | `api_server.py:3582` |
| SSE streaming | ✅ Ready | `_write_sse_chat_completion` |
| Async runs (`/v1/runs`) | ✅ Ready | `api_server.py:3715` |
| Session isolation | ✅ Ready | per-session `session_id` |
| Agent preset support | ✅ Ready | `agent_id` param in `_create_agent` |
| Abort | ✅ Ready | `DELETE /v1/runs/{id}` |

### What's Missing (4 Problems)

#### Problem 1: `credential_pool` — can't serialize

`credential_pool` is an in-memory `CredentialPool` object with API keys,
rotation logic, lease tracking. Can't be sent over HTTP.

**Fix:** API server already has `_resolve_runtime_agent_kwargs()` which loads
credentials from config. Pass the **provider name** (string) and let the server
resolve keys. The `model` and `provider` fields in the request body already
work this way.

#### Problem 2: Callbacks — Python callables

`tool_progress_callback`, `thinking_callback`, `stream_delta_callback` are
Python functions that build TUI events.

**Fix:** API server already streams events via SSE (`/v1/runs/{id}/events`).
Parent parses SSE and translates into its own callbacks:

```python
async for event in sse_stream(f"/v1/runs/{run_id}/events"):
    if event["event"] == "tool.started":
        child_progress_cb("subagent.tool", tool_name=event["tool"])
    elif event["event"] == "message.delta":
        child_progress_cb("_thinking", event["delta"])
```

#### Problem 3: `session_db` — SQLite connection

`session_db` is an open SQLite connection object.

**Fix:** Pass the **path** to `state.db` (string). API server opens its own
`SessionDB(db_path)`. SQLite WAL mode supports concurrent access from
multiple processes.

#### Problem 4: `_delegate_depth` — recursion guard

Currently checked in-memory: `child_depth < max_spawn_depth`.

**Fix:** Pass depth in request header or body. Server validates:

```python
depth = int(request.headers.get("X-Hermes-Delegate-Depth", "0"))
if depth >= max_spawn_depth:
    return web.json_response({"error": "max spawn depth exceeded"}, status=403)
```

### Parameters to Add to `_create_agent()`

```python
def _create_agent(
    self,
    # ── EXISTING ──
    ephemeral_system_prompt=None,
    session_id=None,
    stream_delta_callback=None,
    tool_progress_callback=None,
    tool_start_callback=None,
    tool_complete_callback=None,
    gateway_session_key=None,
    agent_id=None,
    # ── NEW for delegation ──
    parent_session_id=None,           # lineage link
    session_db_path=None,             # path instead of object
    model_override=None,              # subagent's model
    provider_override=None,           # subagent's provider
    base_url_override=None,
    api_key_override=None,
    toolsets_override=None,           # restricted toolsets
    skip_context_files=True,          # subagent behavior
    skip_memory=True,
    fallback_model=None,              # parent's chain
    reasoning_config=None,
    max_iterations=None,
    delegate_depth=0,
    subagent_id=None,
) -> Any:
```

### Proposed HTTP Interface

**Via `/v1/runs` (async, non-blocking):**

```
POST /v1/runs
Headers:
    Authorization: Bearer <API_SERVER_KEY>
    X-Hermes-Parent-Session-Id: 20260707_142301_a1b2
    X-Hermes-Delegate-Depth: 1
    X-Hermes-Subagent-Id: sa-0-abc123
Body:
{
    "input": "Refactor auth module",
    "instructions": "You are a subagent...",
    "model": "deepseek-v4-pro",
    "agent_id": "developer-agent",
    "toolsets": ["terminal", "file", "web"],
    "skip_context_files": true,
    "skip_memory": true,
    "parent_session_id": "20260707_142301_a1b2"
}

→ Returns: {"run_id": "run_abc123", "status": "queued"}

GET /v1/runs/run_abc123/events  → SSE stream
DELETE /v1/runs/run_abc123       → abort
```

## Comparison: Hermes vs OpenCode

| Aspect | Hermes (current) | OpenCode |
|--------|-----------------|----------|
| Subagent execution | ThreadPoolExecutor (threads, shared GIL) | HTTP sessions (event loop, async I/O) |
| Parent blocks? | ✅ Yes — `future.result(timeout)` | ❌ No — `prompt_async` returns immediately |
| Resources per subagent | ~8MB stack per thread | ~0 (event loop handles it) |
| Isolation | Shared memory (credential pool, file state) | Full (separate session objects) |
| Interrupt | `child.interrupt()` (can hang on blocking I/O) | `POST /session/:id/abort` (clean) |
| Network delegation | ❌ Impossible | ✅ Can run on another host |
| OOM safety | One crash kills all | One crash kills only that session |

**Key insight:** For LLM agents, 95% of time is I/O (HTTP to API). GIL is
released during I/O, so in-process threads already provide I/O parallelism.
True multiprocessing (separate processes) only helps for CPU-bound work
(compilation, data processing). The main win of API delegation is **non-blocking
parent** + **crash isolation**, not raw parallelism.
