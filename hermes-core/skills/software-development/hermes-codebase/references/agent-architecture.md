# Hermes Agent Architecture (No Graph)

> **Full canonical description:** `/home/user/architecture-knowledge-graph.md` — 20 components, full dependency map, data flow trace, state management inventory, all config/extension points.
> This file is a quick-reference summary.

Hermes does NOT use LangGraph, no DAG, no state machine. The agent is a plain `while` loop.

## Component Map

| Component | File | Lines | Responsibility |
|-----------|------|-------|----------------|
| `AIAgent` | `run_agent.py` + `agent/agent_init.py` | 5307 + 1743 | Central agent class: all runtime state, init, tool dispatch |
| `run_conversation()` | `agent/conversation_loop.py` | 5047 | Main while-loop: LLM calls, tool dispatch, retries, fallbacks, compression |
| `model_tools.py` | `model_tools.py` | 1216 | Tool dispatch bridge: schema generation, handler dispatch, async loop |
| `tools/registry.py` | `tools/registry.py` | 589 | Central tool registry: self-registration, discovery |
| `toolsets.py` | `toolsets.py` | 894 | Named tool groupings, composition |
| `delegate_tool.py` | `tools/delegate_tool.py` | 2860+ | Subagent spawning in ThreadPoolExecutor |
| `system_prompt.py` | `agent/system_prompt.py` | 429 | Three-tier prompt assembly (stable/context/volatile), cached per session |
| `memory_manager.py` | `agent/memory_manager.py` | 877 | Memory provider orchestration: prefetch, inject, sync |
| `permissions.py` | `agent/permissions.py` | 554 | Declarative allow/ask/deny engine |
| `tool_executor.py` | `agent/tool_executor.py` | 1450 | Sequential + concurrent tool dispatch, guardrails |
| `context_compressor.py` | `agent/context_compressor.py` | 2078 | Context window compression via auxiliary LLM |
| `agents.py` | `agent/agents.py` | 754 | Agent preset registry (~/.hermes/agents/*.md) |
| `agent_runtime_helpers.py` | `agent/agent_runtime_helpers.py` | 2508 | Provider switching, credential pool, message repair |
| `config.py` | `hermes_cli/config.py` | 6366 | Config loading: ~/.hermes/config.yaml + DEFAULT_CONFIG |
| `runtime_provider.py` | `hermes_cli/runtime_provider.py` | 1707 | Provider/model credential resolution |
| `plugins.py` | `hermes_cli/plugins.py` | 1975 | Plugin discovery from 4 sources |
| `hermes_state.py` | `hermes_state.py` | 4429 | SQLite state.db: sessions, messages, FTS5 search |
| `observer.py` | `agent/observer.py` | 371 | Auditor + Critic + Idea Generator + Knowledge Curator → Neo4j |
| `gateway/run.py` | `gateway/run.py` | 20272 | Gateway: messaging platforms, session mgmt, slash dispatch |
| `cli.py` | `cli.py` | ~6000+ | prompt_toolkit TUI, CLI slash commands |

## Main Loop

File: `agent/conversation_loop.py`, function: `run_conversation(agent, user_message, ...)`

```
run_conversation:
  messages = [system_prompt, user_msg]
  while budget > 0:
    response = LLM(messages, tools=[...])
    if tool_calls:
      for each: execute -> append result -> continue
    else:
      return response.text
```

Key details:
- System prompt built ONCE per session, cached in `agent._cached_system_prompt`
- Memory injected into user message (not system prompt — preserves cache prefix)
- Tools dispatched via `tools/registry.py`
- Inner retry loop handles auth errors, context overflow, fallback providers
- Preflight compression before loop, summarises old messages near context limit
- `agent._interrupt_requested` flag checked at top of each iteration

## Subagent Lifecycle

File: `tools/delegate_tool.py`, function: `delegate_task()`

1. Guard rails: pause check, depth check
2. Build child AIAgents on main thread (`_build_child_agent`)
3. Execute in ThreadPoolExecutor (single or batch)
4. `_run_single_child` calls `child.run_conversation(goal, system_prompt)`
5. Cleanup: unregister, close terminal/browser/processes, restore parent tool names

## Blocked Tools for Subagents

```python
DELEGATE_BLOCKED_TOOLS = frozenset([
    "delegate_task",   # no recursive delegation (unless role="orchestrator")
    "clarify",          # no user interaction
    "memory",           # no writes to shared MEMORY.md
    "send_message",     # no cross-platform side effects
    "execute_code",     # children reason step-by-step, don't write scripts
])
```

## Config

```yaml
delegation:
  max_concurrent_children: 3
  max_spawn_depth: 1          # 1=flat, 2+=orchestrator nesting
  orchestrator_enabled: true
  child_timeout_seconds: 600
```

## Data Flow: User Message → Response

```
1. ENTRY: CLI/gateway/desktop/cron → AIAgent.run_conversation(user_message)
2. PRE-TURN: safe stdio, db session row, runtime main, retry reset, sanitize
3. SYSTEM PROMPT (cached, built once):
   stable (identity+tool guidance+skills) → context (AGENTS.md) → volatile (memory+USER.md)
4. MEMORY: memory_manager.prefetch_all() injects recalled context into user message
5. PREFLIGHT: context compressor checks token limit, summarizes if needed
6. MAIN LOOP (while budget > 0):
   ├── LLM call → response
   ├── IF tool_calls: permission check → guardrail → execute → append → continue
   └── ELSE: return response.text (with retries for errors, fallbacks, pool rotation)
7. POST-TURN: memory sync, observer analysis (Neo4j), trajectory save, DB update
```

## Key Extension Points

| Extension | How | Location |
|-----------|-----|----------|
| **New tools** | `registry.register(name, schema, handler, toolset, check_fn)` | `tools/` |
| **Plugins** | `plugin.yaml` + `__init__.py` with `register(ctx)` | `~/.hermes/plugins/` |
| **Agent presets** | `.md` file with YAML frontmatter | `~/.hermes/agents/` |
| **Custom providers** | `custom_providers:` block | `config.yaml` |
| **Context engines** | Implement `ContextEngine` ABC | `plugins/context_engine/` |
| **Memory providers** | Implement `MemoryProvider` ABC | Via plugin system |
| **Gateway platforms** | Platform adapter module | `gateway/platforms/` |
| **Slash commands** | Handler in both `cli.py` AND `gateway/run.py` | `hermes_cli/commands.py` |
| **LLM transports** | Implement transport interface | `agent/transports/` |
| **Observer types** | Add analysis function | `agent/observer.py` |

## State Stores

| Store | What | Location |
|-------|------|----------|
| **state.db** (SQLite) | Sessions, messages, FTS5 search | `~/.hermes/state.db` |
| **In-memory** | Model, provider, tools, callbacks, credential pool, retry counters | `AIAgent` instance |
| **Cached prompt** | System prompt string (per-session prefix cache) | `agent._cached_system_prompt` |
| **config.yaml** | All user settings | `~/.hermes/config.yaml` |
| **.env** | API keys, secrets | `~/.hermes/.env` |
| **Agent presets** | YAML frontmatter + markdown body | `~/.hermes/agents/*.md` |
| **Neo4j** | Observer findings, knowledge graph | Docker container port 7474 |
