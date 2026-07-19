# Delegation Credential Pool Staleness Bug

## Status: FIXED (2026-07-06, verified — 230 tests passed, E2E confirmed)

## Summary

`switch_model()` in `agent/agent_runtime_helpers.py` updated model, provider,
base_url, api_key, api_mode, and the OpenAI client — but did NOT update
`agent._credential_pool`. When a user switched providers mid-session (e.g.
`/model glm-5.2` on zai after the session started on deepseek), the OLD
provider's credential pool persisted. Subagents spawned via `delegate_task`
inherited this stale pool, and credential rotation replaced the correct
`base_url` with the old provider's endpoint, causing HTTP 400.

## Credential Flow (delegate_task → child agent)

```
delegate_task(goal, model="deepseek-v4-pro", provider="deepseek")
  │
  ├─ cfg = _load_config()                          # delegation.* from config.yaml
  ├─ route_cfg = _build_task_route_config(cfg,     # merges per-call overrides
  │     model_override=model,
  │     provider_override=provider)
  │
  ├─ creds = _resolve_delegation_credentials(      # resolves provider creds
  │     route_cfg, parent_agent)
  │   → {model:"deepseek-v4-pro", provider:"deepseek",
  │      base_url:"https://api.deepseek.com/v1",
  │      api_key:"***", api_mode:"chat_completions"}
  │
  ├─ child = _build_child_agent(
  │     model=creds["model"],                      # "deepseek-v4-pro"
  │     override_provider=creds["provider"],        # "deepseek"
  │     override_base_url=creds["base_url"],        # "https://api.deepseek.com/v1"
  │     override_api_key=creds["api_key"],
  │     override_api_mode=creds["api_mode"],
  │     parent_agent=parent_agent)
  │   │
  │   ├─ effective_model = model or parent_agent.model
  │   ├─ effective_provider = override_provider or parent_agent.provider
  │   ├─ AIAgent(base_url=effective_base_url, ...)
  │   │
  │   └─ child_pool = _resolve_child_credential_pool(  # ← BUG WAS HERE
  │         effective_provider, parent_agent)
  │       │
  │       ├─ parent_provider = parent_agent.provider  # "zai" (after switch_model)
  │       ├─ parent_pool = parent_agent._credential_pool  # DEEPSEEK pool (STALE!)
  │       │
  │       └─ if effective_provider == parent_provider:
  │            return parent_pool  # ← returned STALE DeepSeek pool for zai!
  │          else:
  │            return load_pool(effective_provider)  # correct for different provider
  │
  └─ _run_single_child: child._swap_credential(pool_entry)  # ← OVERWROTE base_url
       │
       └─ _swap_credential (run_agent.py:3847):
            runtime_base = entry.base_url  # "https://api.deepseek.com/v1"
            self.base_url = runtime_base   # ← child's base_url overwritten!
            self._replace_primary_openai_client(reason="credential_rotation")
```

## Why Even Explicit Overrides Failed

Even with `delegate_task(model="deepseek-v4-pro", provider="deepseek")`:

1. `_resolve_delegation_credentials` correctly returned deepseek creds
2. `_build_child_agent` correctly set `effective_provider="deepseek"`
3. `_resolve_child_credential_pool("deepseek", parent_agent)`:
   - `effective_provider="deepseek"` ≠ `parent_provider="zai"` → loaded deepseek pool
   - BUT: `_run_single_child` then called `child._swap_credential(leased_entry)`
   - The pool entry's `base_url` overrode the child's `base_url` at init time
4. Result in logs: `provider=zai base_url=https://api.deepseek.com/v1 model=glm-5.2`

The credential rotation mechanism (triggered at AIAgent init via
`_run_single_child` → `acquire_lease` → `_swap_credential`) used the pool's
`base_url` to rebuild the OpenAI client, overriding the `_build_child_agent` settings.

## Root Cause in switch_model()

`agent/agent_runtime_helpers.py`, function `switch_model()` (lines ~1428-1617):

```python
# ── Swap core runtime fields ──
agent.model = new_model           # ✓ updated
agent.provider = new_provider     # ✓ updated
agent.base_url = base_url         # ✓ updated
agent.api_mode = api_mode         # ✓ updated
agent.api_key = api_key           # ✓ updated

# ... rebuilds client, _client_kwargs, _primary_runtime, _fallback_chain ...

# ✗ WAS MISSING: agent._credential_pool was NOT updated!
# The pool from the OLD provider persisted indefinitely.
```

## Applied Fix #1: switch_model updates _credential_pool

`agent/agent_runtime_helpers.py`, `switch_model()`, after `_primary_runtime`
update (line ~1593), added:

```python
# ── Update credential pool to match new provider ──
# Without this, the pool from the OLD provider persists and credential
# rotation in subagents replaces base_url with the old provider's endpoint,
# causing HTTP 400 ("you passed glm-5.2" to api.deepseek.com).
old_pool = getattr(agent, "_credential_pool", None)
old_pool_provider = (getattr(old_pool, "provider", "") or "").strip().lower() if old_pool else ""
new_provider_norm = (new_provider or "").strip().lower()
if old_pool and old_pool_provider and old_pool_provider != new_provider_norm:
    try:
        from agent.credential_pool import load_pool
        new_pool = load_pool(new_provider)
        if new_pool is not None and new_pool.has_credentials():
            agent._credential_pool = new_pool
            logger.info(
                "Credential pool updated: %s -> %s (provider switch)",
                old_pool_provider, new_provider_norm,
            )
        else:
            agent._credential_pool = None
            logger.info(
                "Credential pool cleared: no pool for provider '%s'",
                new_provider_norm,
            )
    except Exception as exc:
        logger.debug("Could not load credential pool for '%s': %s", new_provider, exc)
```

## Applied Fix #2: _run_single_child defense-in-depth guard

`tools/delegate_tool.py`, `_run_single_child()` (line ~1399), added provider
mismatch guard before `_swap_credential`:

```python
child_pool = getattr(child, "_credential_pool", None)
leased_cred_id = None
if child_pool is not None:
    # Defense-in-depth: skip _swap_credential when pool provider doesn't
    # match child provider. _swap_credential overwrites base_url from the
    # pool entry, so a stale pool from a different provider sends requests
    # to the wrong endpoint (e.g. glm-5.2 → api.deepseek.com → HTTP 400).
    child_provider = (getattr(child, "provider", "") or "").strip().lower()
    pool_provider = (getattr(child_pool, "provider", "") or "").strip().lower()
    if child_provider and pool_provider and child_provider != pool_provider:
        logger.warning(
            "Skipping credential swap: pool provider '%s' != child provider '%s' "
            "(would overwrite base_url to wrong endpoint)",
            pool_provider, child_provider,
        )
    else:
        leased_cred_id = child_pool.acquire_lease()
        if leased_cred_id is not None:
            try:
                leased_entry = child_pool.current()
                if leased_entry is not None and hasattr(child, "_swap_credential"):
                    child._swap_credential(leased_entry)
            except Exception as exc:
                logger.debug("Failed to bind child to leased credential: %s", exc)
```

## Applied Fix #3: Remove goal from per-event payload

`tools/delegate_tool.py`, `_build_child_progress_callback()` →
`_identity_kwargs()` (line ~760), removed `"goal": goal_label` from the
per-event identity payload:

```python
def _identity_kwargs() -> Dict[str, Any]:
    kw: Dict[str, Any] = {
        "task_index": task_index,
        "task_count": task_count,
        # goal_label intentionally omitted from per-event payload — it can
        # be 1200+ bytes for observer subagents, and repeating it in every
        # subagent.tool/thinking/progress event caused 65% payload overhead
        # and contributed to OOM kill of Electron renderer (issue: July 2026).
        # The TUI reconstructs the tree from subagent_id; goal is sent once
        # on subagent.start.
    }
```

## Verification (2026-07-06)

### Unit tests (TDD: RED → GREEN)

| Test file | Tests | Result |
|-----------|-------|--------|
| `tests/agent/test_switch_model_credential_pool.py` | 3 new | ✅ GREEN |
| `tests/tools/test_delegate_event_payload.py` | 3 new | ✅ GREEN |
| `tests/tools/test_delegate.py` | 2 fixed (mock provider attrs) | ✅ GREEN |

### Regression

```
230 passed, 0 failed
```

Test suites run: `test_switch_model_credential_pool.py`,
`test_delegate_event_payload.py`, `test_delegate.py`,
`test_fallback_credential_isolation.py`, `test_credential_pool.py`.

### E2E

| Check | Before fix | After fix |
|-------|-----------|-----------|
| `delegate_task` single | ❌ HTTP 400 | ✅ completed, "pong" |
| `delegate_task` batch (3) | ❌ 3× HTTP 400 | ✅ 3× completed (alpha, beta, gamma) |
| HTTP 400 after fix | — | **0** |
| `credential_rotation` base_url | `api.deepseek.com` (wrong) | `api.z.ai/api/paas/v4` (correct) |
| Payload `goal` in per-event | 1291 bytes | **79 bytes** (94% reduction) |

## Log Evidence

### Before fix (2026-07-06 22:51)

```
# credential_rotation REPLACES base_url with DeepSeek:
OpenAI client created (credential_rotation)
  provider=zai base_url=https://api.deepseek.com/v1 model=glm-5.2  ✗

# API call — 400 from DeepSeek API:
Streaming failed: Error code: 400 -
  'The supported API model names are deepseek-v4-pro or
   deepseek-v4-flash, but you passed glm-5.2.'
```

### After fix (2026-07-06 23:10)

```
# credential_rotation uses CORRECT base_url:
OpenAI client created (credential_rotation)
  provider=zai base_url=https://api.z.ai/api/paas/v4 model=glm-5.2  ✓

# delegate_task completed successfully:
tool delegate_task completed (4.93s, 400 chars)
```

## Related: Observer Event Payload Bloat

A separate but related bug: `_build_child_progress_callback()` in
`delegate_tool.py` (line 763) included the full `goal` text (~1200 bytes)
in EVERY subagent event payload (`subagent.tool`, `subagent.progress`,
`subagent.thinking`, `subagent.start`). With 16+ `session_search` calls per
observer subagent, this created massive event payloads that caused OOM kill
of the Electron renderer (SIGKILL, exitCode=9) on 2026-07-02.

**Fix applied:** `goal` removed from `_identity_kwargs()` — payload reduced
from 1291 bytes to 79 bytes per event (94% reduction). `subagent.start`
still includes goal for initial display; other events use `subagent_id`
for tree reconstruction.
