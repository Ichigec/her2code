# Hermes vs OpenCode: Subagent Process Model

## Why This Exists

Users often ask: "Does Hermes spawn a process per subagent?" and "Why does OpenCode seem lighter?" This reference answers both.

## Hermes: Three Independent AIAgent Creation Paths

This is a common source of confusion. Hermes has **three separate code paths**
that create `AIAgent` instances, all in the **same Python process**, and
**none of them calls the others**:

```
Path 1: Delegation (threads)
  tools/delegate_tool.py:_build_child_agent()
    → AIAgent(model=..., provider=..., ...)
    → ThreadPoolExecutor.submit(child.run_conversation)
    → Parent blocks

Path 2: TUI Gateway (JSON-RPC)
  tui_gateway/server.py:_make_agent()
    → AIAgent(model=..., provider=..., ...)
    → Stored in _sessions[sid]["agent"]
    → prompt.submit calls agent.run_conversation()

Path 3: API Server (HTTP)
  gateway/platforms/api_server.py:_create_agent()
    → AIAgent(model=..., provider=..., ...)
    → loop.run_in_executor(None, agent.run_conversation)
    → SSE stream to HTTP client
```

All three call `AIAgent()` directly — no HTTP, no IPC, no subprocess.
Path 3 (API server) could theoretically serve as an HTTP-based delegation
backend (replacing Path 1's in-process threads), but this is NOT wired today.
See "What Hermes Already Has: The API Server Bridge" below for details.

### Key files

```
Parent AIAgent (same Python process, main thread)
    │
    ├─ _build_child_agent() → new AIAgent()  ← Python object, in-process
    │
    ├─ Single task:
    │    _timeout_executor = ThreadPoolExecutor(max_workers=1)
    │    _child_future = _timeout_executor.submit(child.run_conversation, goal)
    │    result = _child_future.result(timeout=...)  ← BLOCKS
    │
    ├─ Batch (N tasks):
    │    with ThreadPoolExecutor(max_workers=N) as executor:
    │        for task: executor.submit(_run_single_child, ...)
    │        while pending:
    │            done, pending = wait(pending, timeout=0.5)  ← BLOCKS
    │
    └─ Each child runs the same `while api_call_count < max_iterations` agent loop
```

### Key files

| File | What it does | Lines of interest |
|------|-------------|-------------------|
| `tools/delegate_tool.py` | `delegate_task()`, `_build_child_agent()`, `_run_single_child()` | 28 (ThreadPoolExecutor import), 1564 (timeout executor), 2185 (batch executor) |
| `run_agent.py` | `AIAgent` class — `run_conversation()` | ~5307 LOC |
| `agent/conversation_loop.py` | Main while-loop | ~4965 LOC |

### Where subprocesses ARE used (and why they're not delegation)

| Feature | Mechanism | Purpose |
|---------|-----------|---------|
| Observer worker | `subprocess.Popen([sys.executable, observer_worker.py, ...])` | Fire-and-forget analytics after session ends |
| `batch_runner.py` | `multiprocessing.Pool` | Offline batch processing (separate tool, not delegation) |

Neither of these is `delegate_task`. Delegation is always in-process threads.

## OpenCode: Async HTTP Sessions

### What happens during subagent creation

```
Opencode HTTP Server (single Node.js process, event loop)
    │
    ├─ POST /session                              → creates session object
    ├─ POST /session/:id/message                  → sends message, waits for response
    ├─ POST /session/:id/prompt_async             → "start if needed, return immediately"
    ├─ GET  /session/:id/children                 → tree of sessions
    ├─ GET  /session/:id/abort                    → interrupt
    ├─ GET  /session/:id/status / /session/:id/diff / /session/:id/summarize
    └─ GET  /event                                → SSE stream of all events
```

### The async advantage

When an OpenCode subagent waits for an LLM response, the Node.js event loop registers a callback and switches to other work. No thread is blocked — it's async I/O.

When a Hermes subagent waits for an LLM response, the entire Python thread blocks on `http_client.send()`. ThreadPoolExecutor keeps that thread alive even though it's doing nothing but waiting.

### Resource Comparison

| Resource | Hermes (Python thread) | OpenCode (Node.js async) |
|----------|------------------------|--------------------------|
| Per subagent overhead | ~8MB stack + TLS + thread metadata | ~0 extra threads — just heap objects |
| Context switching | OS-level (`clone()` syscall) | User-level (event loop tick) |
| Blocked on LLM I/O | Entire thread blocked | Coroutine parked, event loop continues |
| 10 concurrent subagents | 10 threads (~80MB+ overhead) | 1 event loop thread, 10 session objects |
| Shared state | Direct heap sharing (careful locking) | Per-session data in server memory |

### Why Hermes doesn't use this model

Hermes is Python. The agent loop (`conversation_loop.py`) is a synchronous `while`:
```python
while api_call_count < max_iterations:
    response = client.chat.completions.create(...)  # blocking
    if response.tool_calls:
        for tool_call in response.tool_calls:
            result = handle_function_call(tool_call.name, tool_call.args)
```

Converting this to async would require rewriting the entire loop as `async def` + `await`. The current `ThreadPoolExecutor` approach was a pragmatic choice:
- Threads share memory with parent (credentials, callbacks, file state)
- Interrupt propagation works via shared `_interrupt_requested` flag
- No serialization needed (no pickle across process boundaries)
- No `asyncio` dependency in the core loop

### When it matters

| Scenario | Impact |
|----------|--------|
| 1-3 subagents | Neither model is stressed |
| 10+ subagents | Hermes hits OS thread limits; OpenCode scales naturally |
| Many short-lived subagents | Thread creation overhead in Hermes; session creation overhead in OpenCode |
| Resource-constrained host | OpenCode wins (no N×8MB thread stacks) |
| Cross-host subagents | OpenCode's HTTP API naturally supports this; Hermes would need the API server |

## Summary Table

| Aspect | Hermes | OpenCode |
|--------|--------|----------|
| Process model | Single process + threads | Single process + event loop |
| Subagent = | AIAgent Python object in ThreadPoolExecutor | HTTP session object in Node.js server |
| Concurrency | OS threads (preemptive) | Async/await (cooperative) |
| Blocking? | Parent blocks until all children finish | Async available via `prompt_async` |
| I/O wait cost | 1 blocked thread per child | 1 parked coroutine per child |
| Interrupt mechanism | Shared `_interrupt_requested` flag | `POST /session/:id/abort` |
| Cross-host support | Via API server adapter (separate setup) | Native — HTTP API is the primary interface |

## What Hermes Already Has: The API Server Bridge

The Hermes gateway at `gateway/platforms/api_server.py` already provides an
**HTTP-based agent lifecycle** that mirrors OpenCode's session model — but
`delegate_task` does NOT use it. Subagents are still created in-process via
direct `AIAgent()` calls in `_build_child_agent()`.

### The existing infrastructure

| What | Where | What it does |
|------|-------|-------------|
| `_create_agent()` | `api_server.py:969` | Creates `AIAgent` with full config (model, toolsets, session_id, agent_id, callbacks, reasoning, fallback chain) |
| `_run_agent()` | `api_server.py:3582` | `loop.run_in_executor(None, _run)` — runs agent in executor, returns `(result, usage)` |
| `POST /v1/chat/completions` | `api_server.py:1819` | OpenAI-compatible endpoint: parses messages, calls `_run_agent()`, streams via SSE |
| `POST /v1/runs` | `api_server.py:3646+` | Async runs with pollable status and approval queue |
| SSE streaming | `api_server.py:2148` | `_write_sse_chat_completion` — streams tool_calls, thinking, final response |
| `_make_agent()` | `tui_gateway/server.py` | Parallel agent-construction path for the TUI/desktop gateway |

### How it could work

Instead of spawning child `AIAgent` instances in `ThreadPoolExecutor` threads
inside `delegate_tool.py`, the delegation path could call the already-running
gateway's HTTP API:

```python
# Current (delegate_tool.py):
child = AIAgent(model=..., provider=..., ...)
future = ThreadPoolExecutor.submit(child.run_conversation)
result = future.result(timeout=...)

# Potential (HTTP delegation via existing api_server):
resp = requests.post(
    "http://localhost:8642/v1/chat/completions",
    headers={"Authorization": f"Bearer {API_SERVER_KEY}"},
    json={
        "model": model_override,
        "messages": [{"role": "user", "content": goal}],
        "stream": True,
    },
)
# SSE reader → collects agent progress and final response
```

Or, for non-blocking delegation with pollable status:

```python
# Create a run:
run = requests.post(
    "http://localhost:8642/v1/runs",
    headers={...},
    json={"goal": goal, "model": model, "toolsets": ["terminal", "file"]},
)
run_id = run.json()["run_id"]

# Poll for completion:
while True:
    status = requests.get(f"http://localhost:8642/v1/runs/{run_id}/status")
    if status.json()["status"] == "completed":
        break
    time.sleep(1)

# Or abort:
requests.post(f"http://localhost:8642/v1/runs/{run_id}/abort")
```

### What blocks it today

| Gap | Why | Fix needed |
|-----|-----|------------|
| **Credential bridge** | `delegate_task` resolves credentials (API key, base_url) internally. The API server uses gateway-level config. Need to pass child credentials through the HTTP request. | Add `X-Hermes-Credentials` header or extend `/v1/runs` payload with `provider`, `api_key`, `base_url`. |
| **Progress relay** | Current delegation sends progress callbacks to the parent's TUI/desktop. HTTP delegation would receive SSE events that need parsing + relaying. | Build an SSE reader in `delegate_tool.py` that maps API server events back to `child_progress_cb`. |
| **Async client** | `delegate_task` runs synchronously. HTTP calls to localhost could be sync too, but to match OpenCode's `prompt_async`, would need `asyncio` in the delegation path. | Either keep sync (single blocking HTTP call) or switch to `asyncio` (requires upstream conversation loop to be async). |
| **Gateway dependency** | Hermes CLI works without the gateway running. HTTP delegation would require `hermes gateway run`. | Optional path: fall back to in-process threads when the gateway isn't running. |
| **Interrupt propagation** | Currently `child.interrupt()` sets a shared flag. HTTP delegation would need `POST /v1/runs/:id/abort`. | Implement abort endpoint handling in delegate_tool.py. |

### Why it's valuable

| Benefit | Current (in-process) | HTTP delegation |
|---------|---------------------|-----------------|
| **No per-child threads** | 1 thread per subagent (~8MB) | 0 extra threads |
| **Cross-host subagents** | Impossible | Trivial (change localhost:8642 to other host) |
| **Isolation** | Shares GIL and heap | Separate `AIAgent` in gateway's executor |
| **Non-blocking parent** | Parent blocks | Parent could poll or receive SSE |
| **Observability** | Console logs only | HTTP-level tracing, existing `/v1/runs` status |

The irony is that Hermes already has all the pieces OpenCode uses for its
lighter-weight session model — they just aren't wired to `delegate_task`.
A bridge from `delegate_tool.py` to `api_server.py` would give Hermes
the same async, isolated, cross-host subagent capabilities as OpenCode,
without rewriting the agent loop.
