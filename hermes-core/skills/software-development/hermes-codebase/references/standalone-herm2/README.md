# Standalone Hermes Agent Reproduction (`/home/user/dev/herm2/`)

Created: 2026-06-09. Full reproduction of Hermes Agent delegation architecture — distilled from 8000+ lines of production code.

## Structure

```
herm2/
├── __init__.py          # AIAgent class + built-in tools (terminal, file, delegate_task)
├── agent_loop.py        # run_conversation() — main while-loop
├── subagent.py          # Child AIAgent, ChildThreadPool, _run_single_child
├── delegation.py        # delegate_task() — single + batch, role, depth, pause
├── architecture.md      # 6 ASCII architecture diagrams
└── sequence_diagrams.md # 7 sequence diagrams (current + original)
```

## What it captures from production

- `run_agent.py::AIAgent` — full agent class with interrupt cascade, credential pool, activity tracking
- `agent/conversation_loop.py` — `while budget > 0` loop, grace call, return dict shape
- `tools/delegate_tool.py` — `delegate_task()` (2860 lines → distilled to ~300)
- Blocked tools enforcement (delegate_task, clarify, memory, send_message, execute_code)
- Role system (leaf vs orchestrator)
- Depth limiting (max_spawn_depth)
- Credential rotation + heartbeat/stale detection
- Progress callbacks with tree view
- Cost rollup from children to parent

## Key design decisions

1. **No external deps** — pure Python, no OpenAI SDK, no LangGraph
2. **Abstract `_call_llm()`** — subclass to connect to real models
3. **Built-in tools** — terminal (subprocess), file (read/write/search), delegate_task
4. **ThreadPoolExecutor for children** — single-thread mode when only 1 child
5. **Poll-based wait** (not `as_completed`) — enables parent interrupt propagation
6. **Daemon heartbeat thread** — prevents gateway "no activity" timeout
7. **Stale detection** — separate thresholds for idle vs in-tool children

## How to extend

1. Subclass `AIAgent` and implement `_call_llm()` to connect to a real provider
2. Add tools via `agent.register_tool(name, handler, description, schema)`
3. Modify `delegation._MAX_SPAWN_DEPTH`, `_MAX_CONCURRENT` for different limits
4. Override `AIAgent._call_llm()` response format to match your provider's API

## Production mapping

| Standalone file | Production file | Function |
|-----------------|----------------|----------|
| `__init__.py::AIAgent` | `run_agent.py::AIAgent` | Core agent class |
| `agent_loop.py::run_conversation` | `agent/conversation_loop.py` | Main loop |
| `subagent.py::build_child_agent` | `delegate_tool.py::_build_child_agent` | Child construction |
| `subagent.py::ChildThreadPool` | `delegate_tool.py` (ThreadPoolExecutor usage) | Parallel execution |
| `subagent.py::run_single_child` | `delegate_tool.py::_run_single_child` | Child execution |
| `delegation.py::delegate_task` | `delegate_tool.py::delegate_task` | Top-level delegation |
