# ClarifyBridge — sub-agent → parent question relay

> Implemented 2026-06-15 in `tools/delegate_tool.py`.  
> Enables OpenCode-parity: sub-agents can ask the user questions during execution.

## Architecture

```
sub-agent (ThreadPoolExecutor worker)          parent (orchestrator)
       │                                              │
       ├─ clarify("A or B?", [A, B])                  │
       │   └─ _ClarifyBridge.ask()                     │
       │       ├─ push ClarifyQuestion to queue        │
       │       └─ block on _answers_cv (600s timeout)  │
       │                                              ├─ poll loop: pending_questions()
       │                                              ├─ progress_callback("subagent.clarify", ...)
       │                                              ├─ orchestrator reads question
       │                                              ├─ orchestrator calls clarify(user)
       │                                              ├─ orchestrator calls bridge.answer(qid, response)
       │       └─ unblock ← answer ←─────────────────┘
       ├─ continues execution
```

## Key classes

### `_ClarifyBridge` (thread-safe relay)
- `ask(question, choices)` → blocks sub-agent until answer or timeout
- `answer(question_id, response)` → injects answer from parent
- `pending_questions()` → non-blocking poll (called every 0.5s by poll loop)
- `shutdown()` → signal stop, wake all waiters

### `ClarifyQuestion` (lightweight dataclass)
- `question_id`, `question`, `choices`, `subagent_id`, `task_index`, `goal_preview`, `asked_at`, `timeout`

## Poll loop (in `_run_single_child`)

Replaces the old `future.result(timeout=child_timeout)` blocking call:

1. Every 0.5s: check `future.done()` (short timeout on `.result()`)
2. If not done: check `_clarify_bridge.pending_questions()`
3. If questions pending: emit `subagent.clarify` via `child_progress_cb`
4. Check `_child_deadline` (overall child timeout)
5. After child completes: restore original clarify handler, unregister bridge

## Config

- `_CLARIFY_TIMEOUT = 600` — seconds per question
- `_clarify_poll_interval = 0.5` — seconds between queue checks
- `_question_queue maxsize = 30` — max pending questions

## Prerequisites

1. `clarify` REMOVED from `DELEGATE_BLOCKED_TOOLS` (delegate_tool.py line 44)
2. Orchestrator prompt (`plan.md`) includes `Handling sub-agent clarify requests` section
3. Orchestrator has `clarify` tool in its toolset

## Pitfalls

- **Deadlock risk:** If parent never polls (e.g., gateway without progress_callback), sub-agent hangs for 600s then gets timeout. Mitigation: 600s timeout returns error JSON, sub-agent proceeds with best available info.
- **Thread-safety:** `_clarify_bridges` dict guarded by `_clarify_bridges_lock`. Queue is thread-safe by construction (`queue.Queue`).
- **Handler restoration:** Original clarify handler is saved and restored after child completes. If child crashes, `_unregister_clarify_bridge` calls `shutdown()` which wakes all waiters.
- **Multiple questions:** Up to 15 simultaneous questions supported. Parent processes sequentially (clarify tool is modal).

## Integration with orchestrator

When orchestrator receives `subagent.clarify` progress event:
1. Read `question`, `choices`, `subagent_id`, `task_index`, `goal_preview` from event
2. Call `clarify(question, choices)` immediately — do NOT defer
3. Get user response
4. Import `_get_clarify_bridge` from `tools.delegate_tool` and call `bridge.answer(question_id, response)`
5. Sub-agent resumes automatically

## Why this pattern

Before ClarifyBridge, `clarify` was in `DELEGATE_BLOCKED_TOOLS` — sub-agents could never ask questions. If they hit ambiguity, they either guessed (risk of wrong answer) or failed (cycle stall). This brought the orchestrator closer to OpenCode's pattern where agents can pause for human input mid-execution.
