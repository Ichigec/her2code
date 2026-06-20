---
name: hermes-codebase
description: "Navigate and modify the Hermes Agent codebase — architecture, key files, UI extension points."
version: 1.2.0
author: Hermes Agent
license: MIT
---

# Hermes Codebase

Knowledge for navigating and extending the Hermes Agent source code at `~/.hermes/hermes-agent/`.

## Architecture (No Graph)

Hermes does NOT use LangGraph or any DAG framework. The agent is a **simple `while` loop**:

```
run_conversation(agent, user_message):
    messages = [system_prompt, user_msg]
    while budget > 0:
        response = LLM(messages, tools=[...])
        if tool_calls:
            for each: execute tool → append result to messages
            continue
        else:
            return response.text
```

## Key Files

| File | What |
|------|------|
| `run_agent.py` (5307 lines) | `AIAgent` class — state, init, tool dispatch |
| `agent/conversation_loop.py` (4965 lines) | `run_conversation()` — main while-loop + retry/fallback/compression |
| `tools/delegate_tool.py` (2860 lines) | `delegate_task()` — spawns child `AIAgent` in `ThreadPoolExecutor` |
| `tools/registry.py` | Central `registry.register()` for all tools |
| `toolsets.py` | `TOOLSETS` dict — which tools belong to which toolset |
| `agent/agents.py` | Agent preset registry and config loading for `/agent` runtime selection |
| `agent/permissions.py` | Permission-policy engine for `allow` / `ask` / `deny` runtime tool decisions |
| `agent/tool_executor.py` | Runtime tool execution path where permission policies are enforced |
| `agent/runtime_provider.py` | Provider/model resolution and transport selection |
| `hermes_cli/commands.py` | Slash command registry (`/model`, `/agent`, etc.) |
| `cli.py` | Interactive CLI (prompt_toolkit TUI) |

### Desktop App (Electron + React)

| File | What |
|------|------|
| `apps/desktop/src/app/shell/app-shell.tsx` | Outer shell layout |
| `apps/desktop/src/app/chat/sidebar/index.tsx` | Sidebar with nav, sessions, cron |
| `apps/desktop/src/app/shell/model-menu-panel.tsx` | Model switching dropdown |
| `apps/desktop/src/app/command-palette/index.tsx` | Cmd+K palette |
| `apps/desktop/src/app/agents/index.tsx` | Agents view (read-only subagent tree) |
| `apps/desktop/src/store/layout.ts` | Layout state (sidebar open, cron open, etc.) |

### Ink TUI

| File | What |
|------|------|
| `ui-tui/src/components/agentsOverlay.tsx` | Full agents overlay with tree/Gantt/heatmap |
| `ui-tui/src/components/modelPicker.tsx` | Model picker |

## Subagent Lifecycle

```python
# delegate_task() spawns children:
child = _build_child_agent(goal, context, toolsets, model, role, ...)
# Leaf = no delegate_task, orchestrator = can spawn further (bounded by max_spawn_depth)

# Children run in ThreadPoolExecutor:
with ThreadPoolExecutor(max_workers=3) as executor:
    for child in children:
        future = executor.submit(_run_single_child, i, goal, child, parent_agent)

# _run_single_child calls child.run_conversation(goal, system_prompt)
# then extracts summary, registers/unregisters, cleans up
```

Blocked tools for children: `delegate_task`, `clarify`, `memory`, `send_message`, `execute_code`.

For patterns on splitting agent lifecycles across specialised subagents, see
`references/subagent-delegation-pattern.md`. Covers two patterns:
- **3-agent** (General + Executor + Reviewer) — General stays primary, delegates Phase 6 and 7
- **11-agent** (Plan orchestrator + 8 specialist subagents) — Plan is a dedicated orchestrator
  that NEVER does analysis or code; 8 subagents cover every phase; 3 «senior» agents
  (System Analyst, Researcher, Architect) accompany the entire development cycle.
  Agent personas live at `~/.hermes/agents/{plan,requirements-agent,system-analyst,researcher,
  architect-agent,techlead-agent,developer-agent,security-agent,deployment-agent}.md`.
  Use `label: Plan · Name` prefix to group subagents under Plan in the UI selector.

For the plumbing of subagent progress events from Python backend to the desktop Agents view
(how to add new fields like `child_session_id` to the event payload, which call sites to touch,
and the frontend parsing chain), see `references/subagent-progress-events.md`.

For the orchestrator observer checkpoint pattern (feeding phase artifacts to Auditor, Critic,
and Idea Generator after every orchestration phase so they accumulate data for Phase 10),
see `references/orchestrator-observer-checkpoints.md`.

For the Idea Generator checkpoint specifically — phase-adapted methodology, the
critical Phase 2 codebase-cross-referencing technique, output format, pitfalls,
and a verification-file checklist per phase —
see `references/idea-generator-checkpoint-methodology.md`.

## Adding to Desktop Sidebar

The sidebar in `apps/desktop/src/app/chat/sidebar/index.tsx` has this structure:

```
SIDEBAR_NAV (top nav items, line 98-113)
  → new-session, skills, messaging, artifacts

Search field (line 648-658)

Pinned sessions section (line 684-704)

Sessions section (line 706-777)   ← "Agents" recents
  ↓
Agent Presets section (line 793-826)  ← between Sessions and Cron
  ↓
Cron jobs section (line 832-845)
  ↓
Profile rail (line 849-853)
```

To add a section:
1. Add state atom in `store/layout.ts`: `$sidebarYourSectionOpen`
2. Import `SidebarGroup`, `SidebarGroupContent`, `SidebarPanelLabel`
3. Insert between sessions and cron sections, gated on `sidebarOpen && !trimmedQuery`

See `references/desktop-sidebar-agent-presets.md` for the full working Agent Presets implementation with store, component code, preset definitions, and pitfalls.

For the agent persona file format (`~/.hermes/agents/*.md` — YAML frontmatter + system prompt body), field reference, precedence rules, and how system prompts get applied, see `references/agent-persona-file-format.md`.

For auditing and committing cross-cutting runtime changes (agent registry, permission policies, provider routing, toolsets, delegate overrides, and desktop role UI), use `references/runtime-change-review-checklist.md`.

## Gateway Slash-Command Dispatch

Slash commands need handlers in **two places** to work everywhere:

| Layer | File | Purpose |
|-------|------|---------|
| Command definition | `hermes_cli/commands.py` | Registers the command name, aliases, subcommands |
| CLI handler | `cli.py` | `_handle_*_command()` — used by interactive CLI (`hermes`) |
| Gateway handler | `gateway/run.py` | `_handle_*_command()` — used by desktop app, Telegram, Discord, etc. |
| Gateway dispatch | `gateway/run.py` ~line 8200-8440 | Chain of `if canonical == "..."` that routes to handlers |

The desktop app and all messaging platforms go through the gateway, **not** the CLI. A command registered in `commands.py` without a gateway handler will be silently forwarded to the LLM as plain text — the user sees no error, but the command doesn't take effect.

### Adding a gateway handler for a new slash command

1. Add `if canonical == "yourcmd": return await self._handle_yourcmd_command(event)` to the dispatch chain in `gateway/run.py` (insert alphabetically among existing handlers)
2. Implement `async def _handle_yourcmd_command(self, event)` — follow the pattern of existing handlers like `_handle_model_command` or `_handle_reasoning_command`
3. The command will appear in `GATEWAY_KNOWN_COMMANDS` automatically if `cli_only` is not set on its `CommandDef`

## Building External Clients (Mobile, Web, Desktop)

External clients talk to Hermes via the API server adapter
(`gateway/platforms/api_server.py`) — an OpenAI-compatible HTTP API with SSE
streaming, session persistence, capabilities discovery, and approval flows.
OpenCode+ provides its own HTTP API on port 3400 for session-based chat with
model/agent switching.

Full protocol reference, endpoint tables, SSE streaming quirks, Android emulator
gotchas (10.0.2.2), OkHttp patterns, Room/DataStore schemas, and pitfalls:
`references/api-server-protocol.md`.

A complete Android (Kotlin + Jetpack Compose) client implementation lives
at `/home/user/dev/hermes/` — chat with SSE streaming, model/agent switching,
tools/MCP toggle, conversation history via Room, and settings via DataStore.

## Standalone Reproduction: `/home/user/dev/herm2/`

A full standalone reproduction of the Hermes Agent delegation architecture
(~86 K of distilled implementation) lives at `~/.hermes/skills/software-development/hermes-codebase/references/standalone-herm2/`. It mirrors three key source files:

| File | Source Mirror | What it captures |
|------|---------------|-----------------|
| `AIAgent` (`__init__.py`) | `run_agent.py` | Full agent class: init, system prompt, `_call_llm()` abstract, `_dispatch_tool()`, `register_tool()`, `interrupt()` cascade, activity tracking, stats rollup |
| `agent_loop.py` | `agent/conversation_loop.py` | Main `while budget > 0` loop, interrupt checking, grace call, return dict shape |
| `subagent.py` | `tools/delegate_tool.py::_build_child_agent` + `_run_single_child` | Child AIAgent construction, toolset intersection, blocked tools stripping, heartbeat thread, timeout, credential lease, cleanup |
| `delegation.py` | `tools/delegate_tool.py::delegate_task` | Single + batch mode, role (leaf/orchestrator), depth guard, spawn pause, progress callbacks, result aggregation, cost rollup |

**Use this reproduction** when you need to understand delegation mechanics without parsing 8000+ lines of the production code. It's also useful for prototyping new delegation features in isolation.

## Pitfalls

- **Code exploration**: use `read_file` and `search_files` directly. Do NOT use `execute_code` for file reading — it triggers consent prompts that stall and frustrate the user. `execute_code` is for multi-step processing scripts (3+ tool calls with logic between them), not for `grep`/`cat` equivalents.
- **Delivering mobile apps**: when user asks for a mobile app, deliver a PWA (single HTML file served via `python3 -m http.server`) — NOT uncompilable native source code. Building APKs requires Android SDK which isn't on the Hermes host. PWA works immediately in phone browser, installable to home screen. Canonical implementation at `/home/user/dev/hermes/web/index.html`. Quick-start config stub in `templates/pwa-chat.html`. Full API protocol reference in `references/api-server-protocol.md`.
- **API server not running by default**: Hermes gateway must be explicitly started (`hermes gateway run`) with `api_server` platform enabled. Verify with `curl localhost:8642/health`. The API key is in `~/.hermes/.env` as `API_SERVER_KEY`.
- **Bundled skills** (shipped with Hermes, e.g. `hermes-agent`) are protected — cannot be edited via `skill_manage`. Add support files or create new agent-owned skills instead.
- **The main agent loop** is not a graph. Don't look for LangGraph nodes or DAG definitions — there's just `while api_call_count < max_iterations` in `conversation_loop.py`.
- **Gateway vs CLI**: slash commands need handlers in both `cli.py` AND `gateway/run.py`. The desktop app and messaging platforms use the gateway — a command with only a CLI handler silently fails when triggered from the GUI. Always check both layers when a slash command "doesn't work" from the desktop app.
- **`tui_gateway/server.py:_on_tool_progress` silently filters kwargs.** This function (line ~2124) is the Python→frontend gateway for subagent progress events. It builds a `payload` dict from `_kwargs` — but ONLY includes explicitly listed fields (goal, subagent_id, parent_id, depth, model, toolsets, status, summary, etc.). Any new field added to `delegate_tool.py`'s progress callbacks (like `child_session_id` or `parent_session_id`) will be **silently dropped** unless `_on_tool_progress` is updated to extract it. The frontend will never see the field, and no error is raised — it's a silent data loss. **Fix:** add `if _kwargs.get("field_name"): payload["field_name"] = str(_kwargs["field_name"])` in the `_on_tool_progress` function after the existing identity-kwarg extractions. This must be done for EVERY new field added to the progress callback chain.
- **Shadow `hermes_cli` package**: a local directory named `hermes_cli/` in `$HOME` or CWD shadows the real `~/.hermes/hermes-agent/hermes_cli/` in Python's import path. This causes cryptic `ImportError`s like `cannot import name 'SlashCommandCompleter'`, `SlashCommandAutoSuggest`, `__version__`, or `__release_date__`. The slash worker process (`tui_gateway/slash_worker.py`) is especially vulnerable because it imports `cli.py` which does dozens of `from hermes_cli.*` imports. **Fix**: add `sys.path.insert(0, _HERMES_AGENT_ROOT)` to `slash_worker.py` before the `import cli` line, where `_HERMES_AGENT_ROOT` is computed from `__file__`. For simple missing attributes (`__version__`, `__release_date__`), also add them to the shadow `__init__.py` so non-slash-worker processes don't break either.
