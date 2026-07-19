# Clarify System Architecture (Desktop GUI)

How the `clarify()` tool renders interactive dialogs in Hermes Desktop.

## Pipeline

```
clarity() tool call
  → tools/clarify_tool.py (MAX_CHOICES=8, validates question + choices)
  → tui_gateway/server.py:_block("clarify.request", sid, {question, choices})
  → Gateway WebSocket → GUI receives "clarify.request" event
  → use-message-stream.ts handler → setClarifyRequest(request) pushes to queue
  → $clarifyRequests store (Record<string, ClarifyRequest[]>, FIFO per session)
  → $clarifyRequest computed (head of active session's queue)
  → ClarifyTool component renders inline dialog with choices + "Other" option
  → User clicks choice or types free-form → gateway.request('clarify.respond', ...)
  → tui_gateway/server.py receives answer → unblocks agent → tool returns answer
  → clearClarifyRequest() pops head → next queued question appears
```

## Key Files

| File | Role |
|------|------|
| `tools/clarify_tool.py` | Tool implementation, MAX_CHOICES=8, callback pattern |
| `tui_gateway/server.py` | `clarify.request` event sender, `clarify.respond` receiver, `_block()` |
| `tui_gateway/ws.py` | WebSocket transport, reuses `server.dispatch` |
| `apps/desktop/src/store/clarify.ts` | Nano stores: `$clarifyRequests` queue, `$clarifyRequest` head, `$clarifyQueueLength` |
| `apps/desktop/src/app/session/hooks/use-message-stream.ts` | Event handler: `clarify.request` → `setClarifyRequest()` |
| `apps/desktop/src/components/assistant-ui/clarify-tool.tsx` | React component: renders question, choices, free-form input |

## Queue Behavior (implemented 2026-06-29)

- **FIFO per session**: multiple `clarify()` calls from the agent stack in order
- **Head display**: `$clarifyRequest` computed returns `requests[sessionId][0]` — first question only
- **Queue badge**: `ClarifyTool` shows badge with `queueLen` when >1 question pending
- **Pop on answer**: `clearClarifyRequest(requestId, sessionId)` removes head, next question auto-displays
- **Mid-queue removal**: clearing by `requestId` removes specific request, preserving order
- **Cross-session scan**: `clearClarifyRequest(requestId)` without sessionId scans ALL sessions

## MAX_CHOICES

Backend: 8 predefined choices (was 4). A "Other (type your answer)" option is always available.
