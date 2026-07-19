# Clarify Tool GUI Dialog Bug (2026-06-29)

## Symptom

The `clarify()` tool does not display its dialog in the Hermes Desktop GUI. The user sees nothing — no popup, no inline overlay, no choice buttons. The agent session blocks waiting for `clarify.respond` which never arrives.

## Technical Flow

```
Agent calls clarify() 
  → clarify_tool.py sends clarify_callback 
  → gateway _block("clarify.request", sid, {question, choices}) 
  → WS event {type: "clarify.request", payload: {request_id, question, choices}} 
  → GUI use-message-stream.ts:834 catches event 
  → setClarifyRequest({requestId, question, choices, sessionId}) 
  → $clarifyRequest atom updates 
  → ClarifyTool reads $clarifyRequest → renders inline overlay
```

## Where It Breaks

The chain is intact in code. The break is suspected at one of:
1. **Gateway transport** — `_block()` may not deliver the `clarify.request` event through the dashboard's WebSocket (`/api/ws` → `tui_gateway.ws.handle_ws` → `server.dispatch`). The dispatch path exists for JSON-RPC requests, but the event push-back to the WS transport may fail if the session's transport reference is stale.
2. **Session mismatch** — The `_block()` call in `server.py:2230` uses `sid` from the agent session. If the desktop's active session ID doesn't match the agent's session ID, the event is routed to the wrong session and never reaches the GUI.
3. **Timing race** — `clarify.request` may arrive before the GUI's `use-message-stream` hook is fully initialized (the event fires on tool invocation, but the WS listener may not be ready).

## Impact

- Agent cannot use `clarify()` for interactive questions in GUI sessions
- Forces agent to use plain-text questions (no structured choices)
- User frustration: "почему многие вопросы не открываются в окошке?"

## Workaround

Agent should use plain-text questions as fallback when clarify dialog doesn't appear:
```
«Ты имеешь в виду X или Y? Напиши 'X' или 'Y'.»
```

## Fix Candidates

1. **Add `clarify.request` echo-back** — After `_block()`, also send the event through the session's WS transport directly
2. **Add GUI-side watchdog** — If tool.call starts with name='clarify' and no `clarify.request` arrives within 2s, fall back to rendering the question from the tool args
3. **Session ID alignment** — Verify that `sid` in `_block()` matches the session ID the desktop WS is connected to
4. **Add explicit `clarify.request` handling in dashboard** — Currently the dashboard delegates to `tui_gateway.ws.handle_ws` which uses `server.dispatch`. Verify the dispatch path for non-JSON-RPC events.
