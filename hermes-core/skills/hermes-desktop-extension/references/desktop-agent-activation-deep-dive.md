# Deep Dive: Auto-activating agents from the Hermes Desktop status bar

## Context

When a statusbar button or dropdown selects a sub-agent (Plan2, Plan3, Claw Orchestrator, etc.), the user expects the agent to become active immediately. In the broken state the button only inserts `/agent <id>` into the composer, so the user must press Enter manually.

## Root cause

The UI used the composer-insert path instead of the agent-activation RPC:

```tsx
// ❌ Broken — text only, no activation
onSelect={() => {
  requestComposerInsert(`/agent ${agentId}`)
  requestComposerFocus()
}}
```

`requestComposerInsert` only writes into the draft. It does not send the message and does not call the backend. The actual agent switch happens later — and only if the user presses Enter.

## Correct mechanism: `agents.activate` RPC

`desktop-controller.tsx` already exposes a `switchAgentPreset` callback that calls:

```tsx
await requestGateway('agents.activate', {
  id: presetId,
  session_id: activeSessionId ?? undefined
})
```

### It works even without an active session

In `tui_gateway/server.py` the handler stores the override under a special key when no session exists:

```python
if session_id is None:
    _agent_overrides['__pending_desktop__'] = agent_obj
    return {'activated': agent_id, 'pending': True}
```

When the next `session.create` runs, the pending override is copied into the new session key and applied by `_make_agent()` / `_apply_agent_override_if_any()`. This means statusbar buttons can switch agents on a fresh/empty draft before any backend session exists.

## Why the chat indicator does not update mid-session

`session.info` events already include `agent_id` in the payload, but `useMessageStream.ts` does not read it. `useSessionActions.applyRuntimeInfo()` handles `info.agent_id` for `session.create`/`session.resume`, so the indicator only updates on session startup, not when the agent is switched later.

Fix in `useMessageStream.ts` inside the `session.info` handler:

```ts
if (typeof payload?.agent_id === 'string' && payload.agent_id) {
  $activeAgentId.set(payload.agent_id)
}
```

(Also guard against empty strings, which previously cleared the indicator.)

## Recommended implementation

1. **Statusbar buttons/dropdowns** — call `switchAgentPreset(agentId)` directly.
2. **Avoid `requestComposerInsert('/agent ...')`** for activation UI.
3. **Add `ActiveAgentIndicator`** in `ChatHeader` or `ChatBar`, subscribed to `$activeAgentId`.
4. **Patch `useMessageStream.ts`** to sync `$activeAgentId` from `session.info.agent_id`.
5. **Ensure `agentPresets`** include all sub-agents (`plan3/*`, `claw-orchestrator`, etc.) via the `rglob('*.md')` registry fix.

## Verification checklist

- [ ] `agents.list` returns `plan3`, `plan3/requirements-agent`, `claw-orchestrator`, etc.
- [ ] Clicking P3 calls `agents.activate` and returns `activated: 'plan3'`.
- [ ] On a fresh draft (no session), clicking P3 sets `$activeAgentId` to `plan3`.
- [ ] Creating a new session after staging applies the pending `plan3` override.
- [ ] `session.info` payload contains `agent_id` and updates the chat indicator.
- [ ] `npm run pack` succeeds and the running app reflects the changes.
