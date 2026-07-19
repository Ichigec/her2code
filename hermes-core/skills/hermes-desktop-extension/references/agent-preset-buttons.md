# Agent Preset Lifecycle — Architecture & Pitfalls

The agent preset system spans three layers. Understanding how state
flows between them is essential for debugging "preset turned off by
itself" or "indicator shows active but agent uses defaults" bugs.

## Layer overview

| Layer | State store | Lifespan |
|-------|-----------|---------|
| **Frontend** (`$activeAgentPresetId` atom) | `localStorage` (`hermes.desktop.active-preset-id`) | Survives page reload, app restart |
| **TUI gateway** (`_agent_overrides` dict) | `~/.hermes/agent_overrides.json` | Survives gateway restart (persisted) |
| **AIAgent runtime** (`ephemeral_system_prompt`, `enabled_toolsets`, `reasoning_config`) | In-memory on the Python `AIAgent` instance | Per agent instance; re-applied on rebuild |

## How a preset switch works (current flow)

1. **User clicks a preset** (RolePanel dropdown or quick-access button)
2. `switchAgentPreset(id)` calls `requestGateway('agents.activate', { id })`
3. **`agents.activate` RPC** (in `tui_gateway/server.py`):
   - Stores `_agent_overrides[session_key] = agent_id`
   - Persists to `~/.hermes/agent_overrides.json`
   - Applies `apply_agent(agent_obj, agent_def)` to the running agent
   - Emits `session.info` with `agent_id`
4. **Frontend** receives the RPC response → `$activeAgentPresetId.set(id)`
5. **Statusbar** reads `$activeAgentPresetId` and shows `{emoji} {label}`

## State recovery paths

### Gateway restart (`$activeAgentPresetId` survives)

When the TUI gateway restarts, `_agent_overrides` reloads from disk
(`_load_agent_overrides()` at first access). BUT the frontend also
pushes its stored preset back → in `desktop-controller.tsx`:

```tsx
useEffect(() => {
  if (gatewayState !== 'open') return
  const presetId = $activeAgentPresetId.get()
  if (!presetId) return
  void requestGateway('agents.activate', { id: presetId }).catch(() => undefined)
}, [gatewayState, requestGateway])
```

### Agent rebuild (model switch, cache eviction, session resume)

`_make_agent()` calls `_apply_agent_override_if_any(agent, session_key)`.
It reads `_agent_overrides[session_key]`, resolves the `AgentDef`, and calls
`apply_agent()` to re-set toolsets, reasoning, model, and system prompt.

### New session (`/new`)

`session.create` transfers `__pending_desktop__` → real session key.
`_agent_overrides` is NOT cleared — the override persists across sessions.

## Key code locations (current)

| File | What |
|------|------|
| `store/session.ts:104` | `$activeAgentPresetId` atom + localStorage persistence |
| `desktop-controller.tsx:254-272` | `switchAgentPreset(id)` — calls `agents.activate` RPC |
| `desktop-controller.tsx:820-854` | `agentPresetsItem` — statusbar button (reads `$activeAgentPresetId`) |
| `desktop-controller.tsx:785-796` | Auto-reapply effect on gateway connect |
| `tui_gateway/server.py:202` | `_agent_overrides` dict + `_load/save_agent_overrides()` |
| `tui_gateway/server.py:3241-3256` | `_apply_agent_override_if_any` — re-applies on agent rebuild |
| `tui_gateway/server.py:3262-3320` | `agents.activate` RPC handler |
| `tui_gateway/server.py:1854-1857` | `_session_info` — only includes `agent_id` when non-empty |
| `agent/agents.py:653-748` | `apply_agent()` — mutates AIAgent in place |

## Critical pitfalls

### `$activeAgentPresetId` was cleared by empty `agent_id` from session.info

**Root cause:** `_session_info()` always included `"agent_id": ...` even
when no override existed (value `""`). The frontend in `use-message-stream.ts`
did `$activeAgentPresetId.set(payload.agent_id)` for ANY string, including
empty.

**Fix (July 2026):**
1. **Backend:** `_session_info()` omits `agent_id` entirely when empty
2. **Frontend:** `use-message-stream.ts` guards with `&& payload.agent_id`
3. **Persistence:** `_agent_overrides` saved to `~/.hermes/agent_overrides.json`
4. **Auto-reapply:** `desktop-controller.tsx` pushes stored preset on connect

### UI shows active preset but agent uses defaults

This happens when the backend `_agent_overrides` dict is empty (fresh gateway
start) but the frontend's `$activeAgentPresetId` still shows a value from
localStorage. The auto-reapply effect (desktop-controller.tsx:785-796) fixes
this by pushing the stored id via `agents.activate` on every gateway connect.

### Model switch does NOT clear the preset

`switch_model()` in `agent_runtime_helpers.py` does NOT touch `ephemeral_system_prompt`,
`enabled_toolsets`, or `reasoning_config`. After a model switch + agent rebuild,
`_apply_agent_override_if_any` re-applies the preset. The preset's model override
(if any) wins over the user-chosen model — this is intentional: the preset
definition is authoritative.

### There is no "deselect preset" button

The only way to change the active preset is to pick a different one. There is
no "clear" or "none" option. The `RolePanel` only lists concrete presets.
This means the preset should NEVER go blank unless the user explicitly picks
a different one — any blanking is a bug.
