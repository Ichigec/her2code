# AIAgent Constructor & Session Creation

How `AIAgent()` works internally, what the three call sites pass differently,
and how sessions are created in `state.db`.

## AIAgent: One Class, Forwarder Pattern

`AIAgent` is a **single class** in `run_agent.py:320`. Its `__init__` is just a
forwarder — all initialization logic lives in `agent/agent_init.py:init_agent()`
(1743 lines):

```python
class AIAgent:
    def __init__(self, base_url=None, api_key=None, provider=None,
                 api_mode=None, model="", max_iterations=90,
                 session_id=None, session_db=None, parent_session_id=None,
                 # ... ~60 more parameters ...
                 credential_pool=None, ...):
        """Forwarder — see agent.agent_init.init_agent."""
        from agent.agent_init import init_agent
        init_agent(self, base_url=base_url, ...)  # ← all logic here
```

### What init_agent() sets up (major blocks)

| Block | Lines (approx) | What it does |
|-------|----------------|--------------|
| Provider resolution | 310-346 | Auto-detects `api_mode`: `chat_completions`, `anthropic_messages`, `bedrock_converse`, `codex_responses` |
| Client construction | 619-820 | Anthropic SDK / OpenAI SDK / Bedrock boto3 / Copilot ACP — different paths per provider |
| Callbacks | 415-428 | `stream_delta_callback`, `tool_progress_callback`, `thinking_callback`, `clarify_callback`, etc. |
| Session | 1009-1076 | `session_id` (auto-gen if None), `_session_db`, `_parent_session_id` |
| Delegation state | 464-467 | `_delegate_depth=0`, `_active_children=[]`, `_active_children_lock` |
| Interrupt | 438-462 | `_interrupt_requested`, `_client_lock`, `_tool_worker_threads` |
| Prompt caching | 496-512 | Anthropic cache: `5m`/`1h` TTL, breakpoints |
| Activity tracking | 523-543 | `_last_activity_ts`, `_api_call_count`, rate limit / credits state |

## Three Call Sites: Parameter Comparison

All three call `AIAgent(...)` directly. The differences in parameters control
behavior isolation, session linking, and UI integration.

| Parameter | GUI (tui_gateway) | Subagent (delegate_tool) | API Server |
|-----------|-------------------|--------------------------|------------|
| `session_id` | Explicit (from `session.create`) | **Not passed** → auto-generated | From request or auto-generated |
| `session_db` | Own DB instance | **Parent's `_session_db`** (shared) | Own DB instance (gateway) |
| `parent_session_id` | None | **`parent.session_id`** (links tree) | None |
| `quiet_mode` | False | True | True |
| `skip_context_files` | False | **True** (no AGENTS.md) | False |
| `skip_memory` | False | **True** (no MEMORY.md) | False |
| `ephemeral_system_prompt` | From config / agent preset | **Goal-specific child prompt** | From request system message |
| `stream_delta_callback` | Yes (→ `message.delta` UI events) | None | Yes (→ SSE stream) |
| `tool_progress_callback` | Yes (→ UI tool panel) | **Child progress callback** (→ parent TUI) | Yes (→ SSE tool events) |
| `clarify_callback` | Yes (→ UI question dialog) | **None** (subagents can't ask user) | Yes (→ approval flow) |
| `credential_pool` | From config / runtime provider | **Parent's pool** (shared, with guard) | From config |
| `enabled_toolsets` | From config / `platform_toolsets.tui` | **Intersected with parent** + blocked tools stripped | From config / `platform_toolsets.api_server` |
| `iteration_budget` | Fresh `IterationBudget(max_iterations)` | **None** → fresh budget per subagent | Fresh |
| `log_prefix` | None | `"[subagent-{index}]"` | None |
| `platform` | `"tui"` | `parent.platform` or override | `"api_server"` |

### Code locations

```python
# 1. GUI — tui_gateway/server.py:2698
AIAgent(
    model=model,
    provider=runtime.get("provider"),
    session_id=session_id or key,      # ← EXPLICIT session_id
    session_db=session_db,             # ← own DB
    platform="tui",
    stream_delta_callback=...,         # ← streaming to UI
    reasoning_config=...,
    enabled_toolsets=...,
)

# 2. Subagent — tools/delegate_tool.py:1149
AIAgent(
    model=effective_model,
    provider=effective_provider,
    # session_id= NOT PASSED → auto-generated in init_agent
    session_db=parent._session_db,             # ← SHARED with parent
    parent_session_id=parent.session_id,        # ← links to parent in state.db
    quiet_mode=True,
    skip_context_files=True,
    skip_memory=True,
    ephemeral_system_prompt=child_prompt,       # ← goal-specific
    log_prefix=f"[subagent-{task_index}]",
    iteration_budget=None,                      # ← fresh budget
)

# 3. API Server — gateway/platforms/api_server.py:1016
AIAgent(
    model=model,
    quiet_mode=True,
    session_id=session_id,             # ← from request or auto-gen
    platform="api_server",
    stream_delta_callback=...,         # ← SSE streaming
    enabled_toolsets=...,
    fallback_model=...,
)
```

## Session Creation in state.db

### Auto-generation

When `session_id` is not passed (subagent case), `init_agent` auto-generates:

```python
# agent/agent_init.py:1010-1017
if session_id:
    agent.session_id = session_id
else:
    timestamp_str = agent.session_start.strftime("%Y%m%d_%H%M%S")
    short_uuid = uuid.uuid4().hex[:6]
    agent.session_id = f"{timestamp_str}_{short_uuid}"
```

### Lazy DB row creation

The `state.db` row is NOT created at construction time. It's created lazily
on the first `run_conversation()` call:

```python
# run_agent.py:505-527
def _ensure_db_session(self) -> None:
    if self._session_db_created or not self._session_db:
        return
    source = os.environ.get("HERMES_SESSION_SOURCE") or self.platform or "cli"
    self._session_db.create_session(
        session_id=self.session_id,
        source=source,
        model=self.model,
        parent_session_id=self._parent_session_id,  # ← links to parent
    )
    self._session_db_created = True
```

### Resulting session tree in state.db

```
state.db (one SQLite DB, shared across the process)
┌─────────────────────────────────────────────────────────┐
│ sessions table                                          │
├──────────────────────┬────────────────┬─────────────────┤
│ session_id           │ parent_session │ model           │
├──────────────────────┼────────────────┼─────────────────┤
│ 20260707_142301_a1b2 │ NULL           │ deepseek-v4     │ ← GUI session
│ 20260707_142305_c3d4 │ a1b2 (parent)  │ deepseek-v4     │ ← subagent 1
│ 20260707_142305_e5f6 │ a1b2 (parent)  │ zai/glm-5.2     │ ← subagent 2
│ 20260707_142310_g7h8 │ c3d4 (parent)  │ deepseek-v4     │ ← sub-subagent
└──────────────────────┴────────────────┴─────────────────┘
```

Each `AIAgent()` call → new `session_id` → new row in `state.db` (lazy, on
first `run_conversation()`). The `parent_session_id` column links the tree.

### What subagents share with the parent (despite separate sessions)

| Shared (in-process heap) | NOT shared (per-agent) |
|--------------------------|------------------------|
| `_session_db` (SQLite connection) | `session_id` (unique) |
| `_credential_pool` (API key rotation) | `_cached_system_prompt` |
| `_active_children` list (interrupt propagation) | `messages` / conversation history |
| File state (task_id-scoped) | `max_iterations` budget (fresh per subagent) |
| Tool registry (global) | `_interrupt_requested` flag (per-agent) |

## Key Insight for Future Work

The three call sites are **independent and duplicative**. If you need to change
how agents are constructed (e.g., add a new parameter, change provider routing),
you must update **all three**:

1. `tui_gateway/server.py:_make_agent()` — for GUI sessions
2. `tools/delegate_tool.py:_build_child_agent()` — for subagents
3. `gateway/platforms/api_server.py:_create_agent()` — for HTTP clients

There is no shared factory function. Each call site assembles its own parameter
dict from different sources (config, parent agent, HTTP request) and passes it
to `AIAgent()`.
