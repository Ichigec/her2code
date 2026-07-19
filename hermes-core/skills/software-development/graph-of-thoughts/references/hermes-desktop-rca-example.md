# GoT Example — Hermes Desktop agent activation root cause

## User request

«Проведи глубокий анализ и найди причину. Предложи план решения» after a summary stating that Plan3 subagent dropdowns work but still require pressing Enter to activate the agent.

## Clarification

The request was ambiguous across three layers (Hermes Agent backend, Android app, Desktop GUI). `clarify()` was used; the context compaction then pointed to the Desktop GUI layer as the active task.

## Graph of Thoughts

```
ROOT: Why do Plan3 / Claw statusbar buttons require manual Enter and show no active-agent indicator in the chat?
├── Branch A — Composer-insert path (the broken current behavior)
│   ├── A1: Buttons call requestComposerInsert('/agent plan3')
│   ├── A2: requestComposerInsert only writes text into the composer draft
│   ├── A3: No message is sent; agent is not activated
│   └── A4: User must press Enter to submit the /agent command
├── Branch B — RPC activation path (the correct fix)
│   ├── B1: desktop-controller.tsx already has switchAgentPreset()
│   ├── B2: switchAgentPreset calls requestGateway('agents.activate', { id, session_id })
│   ├── B3: Backend supports staging without session via __pending_desktop__
│   └── B4: Buttons should call switchAgentPreset(agentId) directly
└── Branch C — Chat indicator gap
    ├── C1: session.info events already carry agent_id
    ├── C2: useMessageStream ignores agent_id
    ├── C3: useSessionActions.applyRuntimeInfo handles it only on session create/resume
    └── C4: Fix: handle payload.agent_id in useMessageStream.ts
```

## Synthesis

| Branch | Verdict | Action |
|--------|---------|--------|
| A | Rejected | Remove composer-insert behavior from activation buttons |
| B | Adopted | Wire P2/P3/Claw buttons to `switchAgentPreset` |
| C | Rejected as-is | Patch `useMessageStream.ts` to sync active agent indicator |

## Output delivered

1. Root cause: buttons used `requestComposerInsert` instead of `agents.activate` RPC.
2. Plan: switch buttons to `switchAgentPreset`, patch `useMessageStream` for `agent_id`, add `ActiveAgentIndicator`, build and restart GUI.
3. Pitfalls captured: `__pending_desktop__` staging, empty-string `agent_id` clearing the indicator, and the fact that `/agent` is not a desktop slash command.

## IMPORTANT: This GoT was built on FALSE premises

A follow-up session (2026-07-02) verified the actual code via `read_file` and found that **all three "problems" above were already fixed**:

- `switchAgentPreset()` (desktop-controller.tsx:253-285) already calls `agents.activate` RPC — no `requestComposerInsert`
- `useMessageStream` (use-message-stream.ts:685-687) already handles `payload.agent_id`
- `agents.activate` (server.py:3266-3325) already supports `__pending_desktop__` staging

The agent that produced this GoT trusted a context-compression summary instead of reading the code. The GoT structure is correct (Branch A/B/C decomposition), but Node A1 contained false claims that propagated into the entire plan. This is the canonical example of the **summary-as-truth trap** (see Step 2.5 in the SKILL.md).

**Lesson:** Always verify Node A1 claims against actual code before building Node A3 (plan). The GoT is only as good as its input data.

Full post-mortem: → `references/summary-trust-failure.md`
Verified code state: → `hermes-cross-stack/references/desktop-agent-activation-vertical.md`
