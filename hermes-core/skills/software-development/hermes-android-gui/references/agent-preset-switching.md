# Agent Preset Switching — Cross-Surface Architecture

> How agent preset changes propagate across Desktop, TUI, CLI, Gateway, REST API, and Android.
> Created 2026-06-29 after deep analysis of the switching gap.

## The core mechanism: `apply_agent()`

```python
# agent/agents.py:653
def apply_agent(agent_obj, agent_def):
    # 1. Toolsets — e.g. build: [terminal, file, web, browser, delegation]
    agent_obj.enabled_toolsets = agent_def.toolsets
    agent_obj.tools = get_tool_definitions(enabled_toolsets=toolsets)
    
    # 2. Reasoning effort — e.g. build: "high"
    agent_obj.reasoning_effort = agent_def.reasoning
    
    # 3. Model — if specified in agent definition
    if agent_def.model:
        agent_obj.switch_model(new_model=agent_def.model)
    
    # 4. Ephemeral system prompt — full text from ~/.hermes/agents/<id>.md
    agent_obj.ephemeral_system_prompt = agent_def.system_prompt
    
    # 5. Permission policy — e.g. plan: readonly (edit: deny, bash: deny)
    agent_obj._permission_policy = build_permission_policy(agent_def)
```

## How each surface switches presets

### 1. Desktop GUI (Electron) — WORKS
```
User clicks preset button
  → switchAgentPreset(id) // desktop-controller.tsx:253
    → requestComposerInsert(`/agent ${id}`)  // inserts text into input
    → $activeAgentPresetId.set(id)           // updates nano-store
  → User sends message
    → TUI Gateway processes `/agent` slash command
      → apply_agent(agent_obj, agent_def)
      → _agent_overrides[key] = agent_id  // persistent for future sessions
```

### 2. TUI Gateway RPC — WORKS (unused by desktop currently)
```
agents.activate RPC (WebSocket)
  → apply_agent(agent_obj, agent_def)
  → _agent_overrides[key] = agent_id
  → _emit("session.info", ...)  → desktop updates icon
```

### 3. CLI — WORKS
```
/agent <id>
  → _handle_agent_command() // cli.py:10442
    → self.enabled_toolsets = agent_def.toolsets
    → self.reasoning_effort = agent_def.reasoning
    → apply_agent(self.agent, agent_def)
```

### 4. Gateway (Telegram/Discord) — WORKS
```
/agent <id> via message
  → _handle_agent_command() // gateway/run.py:12904
    → apply_agent(agent_obj, agent_def)
    → self._session_agent_overrides[session_key] = agent_id  // persistent
    → _apply_session_agent_override() re-applies on each turn
```

### 5. REST API (/v1/chat/completions) — BROKEN ❌
```
POST /v1/chat/completions
  → _handle_chat_completions() // api_server.py:1683
    → _run_agent()
      → _create_agent()  // NO agent_id parameter
        → AIAgent()  // default toolsets, no agent override
```

**NO mechanism exists:**
- No `agent_id` body parameter
- No `X-Hermes-Agent` header support
- Slash commands are NOT processed (bypasses gateway message pipeline)
- No `/v1/agents/activate` REST endpoint

### 6. Android App — SEVERELY INCOMPLETE ❌
```
settings.selectedAgent = "build"
  → ChatViewModel sends:
    system message "You are the Build agent..."  // ONE LINE, not full prompt
    // Toolsets UNCHANGED
    // Reasoning UNCHANGED
    // Permissions UNCHANGED
    // Model UNCHANGED
```

## Where agent definitions come from

```python
# agent/agents.py — load_agents() merges three layers:
# 1. _BUILTIN_AGENTS (10 presets): general, build, plan, explore, scout, 
#    claw, composter, deep-explore, review, safe
# 2. ~/.hermes/agents/*.md — user overrides (YAML frontmatter + markdown body)
# 3. config.yaml → agents: block — highest precedence
```

## Built-in agent presets

| id | Label | Toolsets | Mode | Key trait |
|----|-------|----------|------|-----------|
| general | 🤖 General | all | primary | Full lifecycle agent |
| build | 🔨 Build | terminal, file, web, browser, delegation | primary | Full dev access |
| plan | 🧠 Plan | web, search, browser, file_ro | primary | Read-only research |
| explore | 🧭 Explore | file, search | subagent | Read-only codebase |
| scout | 🔭 Scout | web, search, browser | subagent | Read-only web |
| claw | 🐾 Claw | file, terminal, search, lsp, mcp | primary | Skill/MCP compactor |
| composter | 🍂 Composter | file_ro, search, mcp | primary | Read-only audit reader |
| deep-explore | 🔬 Deep Explore | file_ro, search, lsp | subagent | Multi-pass code explore |

Plus two that exist in Android Constants but NOT in `_BUILTIN_AGENTS`:
- `review` — not in built-in registry (may be from older config)
- `safe` — not in built-in registry (may be from older config)

## Android Constants discrepancy

`Constants.kt` hardcodes 10 agents with one-line prompts. The server has rich multi-thousand-line prompts loaded from `~/.hermes/agents/*.md`. The Android one-liners are a pale shadow — e.g. `general.md` is 1034 lines of research methodology, but the app sends "You are the General agent — the default Hermes assistant with access to all tools."

## Recommended fix path for Android

Add `POST /v1/agents/activate` REST endpoint to api_server.py:
```python
async def _handle_agent_activate(self, request):
    body = await request.json()
    agent_id = body.get("id")
    from agent.agents import get_agent, apply_agent
    agent_def = get_agent(agent_id)
    if agent_def:
        # Apply to current agent (if any) + store override
        ...
    return web.json_response({"activated": agent_id, ...})
```

Then Android calls this before sending messages, and the agent is properly switched server-side.
