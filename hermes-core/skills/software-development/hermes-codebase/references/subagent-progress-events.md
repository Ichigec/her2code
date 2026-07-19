# Subagent Progress Event Plumbing

How `child_session_id` (and any other per-field data) travels from Python backend
to the desktop Agents view. Use this as a template when adding new fields to the
subagent progress payload.

## Architecture

```
_build_child_progress_callback()            ← creates _callback closure
  └─ _identity_kwargs()                     ← base payload for every event
  └─ _relay(event, **kwargs)                ← merges identity + call-site kwargs
       └─ parent_cb(event, tool, preview, args, **payload)  → gateway → desktop
            └─ SubagentPayload              ← raw dict received by frontend
                 └─ toProgress(payload)     ← parses into SubagentProgress
```

## Adding a field known at callback creation time

Fields like `parent_session_id`, `subagent_id`, `depth`, `model`, `toolsets`
are known when `_build_child_progress_callback()` is called. Add them to
`_identity_kwargs()` — they'll appear in every emitted event automatically.

```python
# In _identity_kwargs() inside _build_child_progress_callback:
parent_session_id = getattr(parent_agent, "session_id", None)
if parent_session_id is not None:
    kw["parent_session_id"] = parent_session_id
```

## Adding a field known only AFTER callback creation

Fields like `child_session_id` are only known after `child = AIAgent(...)` is
constructed — which happens AFTER `_build_child_progress_callback()` returns.
Pass them as kwargs at the call site — they flow through `_relay` →
`payload.update(kwargs)` → `parent_cb(**payload)`.

There are 4 call sites that emit lifecycle events:

| Event | Location | Child available? |
|-------|----------|:----------------:|
| `subagent.spawn_requested` | `spawn_subagent()`, ~line 1216 | ✅ (just constructed) |
| `subagent.start` | `_run_single_child()`, ~line 1535 | ✅ |
| `subagent.complete` (timeout) | `_run_single_child()`, ~line 1632 | ✅ |
| `subagent.complete` (normal) | `_run_single_child()`, ~line 1881 | ✅ |

Example for `subagent.start`:

```python
child_progress_cb(
    "subagent.start",
    preview=goal,
    child_session_id=getattr(child, "session_id", None),
)
```

## Frontend side

### 1. Add field to `SubagentProgress` interface (`store/subagents.ts`)

```typescript
export interface SubagentProgress {
  // ... existing fields ...
  subagentSessionId?: null | string
}
```

### 2. Parse in `toProgress()`

```typescript
subagentSessionId: str(payload.child_session_id) || prev?.subagentSessionId || null,
```

The `prev?.subagentSessionId || null` fallback ensures the value persists across
partial updates — once any event carries it, it sticks.

### 3. Use in UI

The field is now available on `SubagentNode` (which extends `SubagentProgress`).
Access as `node.subagentSessionId`.

## Pitfalls

- **Duplicate fields in `_identity_kwargs()`**: the function body is long and it's
  easy to accidentally add the same field twice (e.g., `parent_id` appears at
  lines 767 and 776). Always check for duplicates after editing. The fields are:
  `task_index`, `task_count`, `goal`, `subagent_id`, `parent_id`, `depth`, `model`,
  `toolsets`, `tool_count`, `parent_session_id`.

- **Not all events carry the field**: `_identity_kwargs()` fields go to every event.
  Call-site kwargs only go to the specific event being fired. If you add a field
  at the `subagent.start` call site, it won't be in `subagent.spawn_requested`
  unless you add it there too. The frontend's `|| prev?.fieldName` fallback
  handles this — first event wins, later merges can fill gaps.

- **i18n keys**: if the new field enables a UI element with user-visible text,
  add the translation key to:
  1. `types.ts` — type definition
  2. `en.ts` — English (mandatory)
  3. `ja.ts`, `zh.ts`, `zh-hant.ts` — other locales
  4. Run `npx tsc -b` in `apps/desktop/` to verify all locales satisfy the type

- **TypeScript compilation path**: always run from `apps/desktop/` directory:
  ```bash
  cd apps/desktop && npx tsc -b
  ```
  Running from repo root with the wrong tsconfig will fail.
