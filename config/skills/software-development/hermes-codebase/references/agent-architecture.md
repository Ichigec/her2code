# Hermes Agent Architecture (No Graph)

Hermes does NOT use LangGraph, no DAG, no state machine. The agent is a plain `while` loop.

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
