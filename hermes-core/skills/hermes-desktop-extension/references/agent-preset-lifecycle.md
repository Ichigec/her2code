# Agent Preset Lifecycle

End-to-end flow of agent preset selection, persistence, and re-application.

## Flow

```
Desktop GUI                    TUI Gateway                   AIAgent
──────────                     ────────────                  ───────
User clicks "General" ──────→  agents.activate(id=general)
                                │
                                ├─ _agent_overrides[key]=general
                                ├─ apply_agent(agent_obj, def)
                                ├─ emit session.info{agent_id: "general"}
                                │
$activeAgentPresetId ←─────────┘  (set to "general")
```

## Persistence Layers

| Layer | Location | Survives |
|-------|----------|----------|
| Frontend atom | `localStorage` key `hermes.desktop.active-preset-id` | Page reload, browser restart |
| Backend override | `_agent_overrides` dict (module-level, in-memory) | **Nothing** — lost on TUI gateway restart |
| Agent state | `agent_obj.ephemeral_system_prompt`, `enabled_toolsets`, etc. | Current session only |

## Re-application on Agent Rebuild

When the cached AIAgent is evicted (model switch, idle timeout, /new), a
fresh agent is built. `_apply_agent_override_if_any()` (line 3201) reads
`_agent_overrides[session_key]` and calls `apply_agent()` on the new
instance. This preserves toolsets, reasoning, model, and system prompt.

## Known Pitfalls

1. **TUI gateway restart loses all overrides.** `_agent_overrides` is an
   in-memory Python dict. After restart, `session.info` reports no active
   agent. The frontend fix (skip empty `agent_id`) prevents the indicator
   from clearing, but the agent itself runs with default settings until the
   user re-clicks a preset.

2. **Pending override race.** When clicking a preset before a session
   exists, `agents.activate` stores under `"__pending_desktop__"`.
   `session.create` transfers it to the real session key. If `session.create`
   is called concurrently (e.g., first message auto-creates), the pending
   key may not exist yet if `agents.activate` hasn't returned. The desktop's
   `switchAgentPreset` calls `$activeAgentPresetId.set()` in `.then()`, so
   the frontend indicator updates even if the pending transfer fails.

3. **Empty agent_id in session.info.** The backend's `_session_info()`
   unconditionally included `agent_id` (even `""`). The frontend handler
   set `$activeAgentPresetId` to the empty string, visibly clearing the
   statusbar. Fixed Jul 2026: backend now omits the key when empty, and
   frontend guards with `&& payload.agent_id`.
