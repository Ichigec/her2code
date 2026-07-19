---
name: subagent-delegation-success
description: "How to successfully modify and fix subagent delegation in Hermes Agent: credential pool sync, event payload optimization, provider override flow, verification methodology."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [subagent, delegation, credentials, orchestration, debugging, hermes-agent]
    related_skills: [hermes-agent, hermes-codebase, multi-agent-orchestration, systematic-debugging]
---

# Subagent Delegation Success Pattern

How to successfully modify, fix, and verify subagent delegation in Hermes
Agent. Based on a real bug fix (2026-07-06) where delegation was completely
broken — subagents inherited stale credential pools causing HTTP 400 on
every delegate_task call.

**Core principle:** Delegation involves a chain of credential inheritance
that spans 3 layers (parent agent → child construction → child runtime).
Any break in the chain causes silent failures that look like provider errors.

## When to Use

- delegate_task returns HTTP 400/401/403 on subagent calls
- Subagents use wrong provider/model/base_url despite overrides
- Observer subagents cause OOM or excessive event payload
- After modifying switch_model, credential_pool, or _build_child_agent
- Before enabling observers (they spawn 4+ subagents per session)

## The Delegation Credential Chain

```
Parent Agent (provider=zai, base_url=api.z.ai, pool=zai_pool)
    │
    ├─ switch_model() updates: model, provider, base_url, api_key, client
    │   └─ ⚠️ MUST also update: _credential_pool  ← BUG #1 was here
    │
    ├─ _build_child_agent() creates child with override creds
    │   └─ _resolve_delegation_credentials() resolves provider→pool→creds
    │
    ├─ _run_single_child() initializes child runtime
    │   └─ child._swap_credential(pool.current())  ← BUG #1b was here
    │       ⚠️ MUST guard: pool.provider == child.provider
    │
    └─ Child Agent runs with correct provider/model/base_url
```

### The Three Critical Bugs (and their fixes)

| Bug | Location | Symptom | Fix |
|-----|----------|---------|-----|
| Stale credential pool | `agent_runtime_helpers.py:switch_model` | Pool from old provider persists after switch → `_swap_credential` overwrites base_url | Update `_credential_pool` in `switch_model` |
| Unguarded swap in _run_single_child | `delegate_tool.py:_run_single_child` | `_swap_credential` called even when pool provider ≠ child provider | Guard: skip swap on provider mismatch |
| Event payload bloat | `delegate_tool.py:_identity_kwargs` | Full `goal` text (1200+ bytes) in every subagent event → OOM | Remove `goal` from per-event payload |

## Verification Methodology (TDD + E2E)

### Phase 0: Reproduce (RED)

```python
# tests/agent/test_switch_model_credential_pool.py
def test_switch_model_updates_credential_pool():
    """After switch_model deepseek→zai, _credential_pool must be zai."""
    agent = _make_agent(provider="deepseek")
    agent._credential_pool = deepseek_pool  # stale

    switch_model(agent, new_model="glm-5.2", new_provider="zai", ...)

    assert agent._credential_pool is zai_pool  # FAILS before fix
```

### Phase 1: Fix + Unit Test (GREEN)

**Fix #1a:** In `agent/agent_runtime_helpers.py`, `switch_model()`, after
updating `_primary_runtime`:

```python
# ── Update credential pool to match new provider ──
old_pool = getattr(agent, "_credential_pool", None)
old_pool_provider = (getattr(old_pool, "provider", "") or "").strip().lower()
new_provider_norm = (new_provider or "").strip().lower()
if old_pool and old_pool_provider and old_pool_provider != new_provider_norm:
    try:
        from agent.credential_pool import load_pool
        new_pool = load_pool(new_provider)
        if new_pool is not None and new_pool.has_credentials():
            agent._credential_pool = new_pool
        else:
            agent._credential_pool = None
    except Exception as exc:
        logger.debug("Could not load credential pool: %s", exc)
```

**Fix #1b:** In `tools/delegate_tool.py`, `_run_single_child()`, before
calling `_swap_credential`:

```python
child_provider = (getattr(child, "provider", "") or "").strip().lower()
pool_provider = (getattr(child_pool, "provider", "") or "").strip().lower()
if child_provider and pool_provider and child_provider != pool_provider:
    logger.warning(
        "Skipping credential swap: pool '%s' != child '%s'",
        pool_provider, child_provider,
    )
else:
    # Only swap when providers match
    leased_cred_id = child_pool.acquire_lease()
    ...
```

**Fix #2:** In `tools/delegate_tool.py`, `_identity_kwargs()`:

```python
def _identity_kwargs() -> Dict[str, Any]:
    kw: Dict[str, Any] = {
        "task_index": task_index,
        "task_count": task_count,
        # goal_label REMOVED — was 65% of payload size, caused OOM
        # TUI reconstructs tree from subagent_id, not goal text
    }
```

### Phase 2: E2E Verification

```python
# Live test: delegate_task must complete without HTTP 400
result = delegate_task(
    goal="Reply with exactly one word: pong",
    toolsets=["terminal"]
)
assert result["results"][0]["status"] == "completed"
assert "pong" in result["results"][0]["summary"]
```

### Phase 3: Log Verification

```bash
# After fix: credential_rotation must use correct base_url
grep "credential_rotation" agent.log | grep -o "base_url=[^ ]*" | sort -u
# Expected: base_url=https://api.z.ai/api/paas/v4 (NOT api.deepseek.com)

# After fix: no HTTP 400 from subagents
grep "subagent.*400\|subagent.*BadRequest" agent.log | wc -l
# Expected: 0
```

## How to Diagnose Delegation Failures

### Symptom Matrix

| Symptom | Root Cause | Investigation |
|---------|-----------|---------------|
| HTTP 400 "model not supported" | Stale pool → wrong base_url | `grep credential_rotation agent.log` |
| Subagent inherits parent model despite override | Override not reaching `_build_child_agent` | Check `_resolve_delegation_credentials` return |
| OOM / crash with many subagents | Event payload bloat | `grep '"goal"' desktop.log \| wc -l` |
| Subagent hangs (no API call) | Credential pool empty/exhausted | Check `pool.has_credentials()` |
| Observer cascade (exponential subagents) | Observer detection failing | Check `_is_observer_session()` in observer-hook |

### Diagnostic Commands

```bash
# 1. Check what provider/model/base_url the subagent actually used
grep "subagent\|credential_rotation\|chat_completion" agent.log | tail -20

# 2. Check if credential pool matches agent provider
python3 -c "
from agent.credential_pool import load_pool
for p in ['zai', 'deepseek', 'openrouter']:
    pool = load_pool(p)
    if pool and pool.has_credentials():
        entry = pool.current()
        print(f'{p}: pool.provider={pool.provider}, entry.base_url={entry.base_url}')
"

# 3. Measure event payload size
python3 -c "
from tools.delegate_tool import _build_child_progress_callback, DelegateEvent
from types import SimpleNamespace
from unittest.mock import MagicMock
import json
parent = SimpleNamespace(_delegate_spinner=None, tool_progress_callback=MagicMock())
cb = _build_child_progress_callback(0, 'X'*1200, parent, 1, subagent_id='sa-test')
cb(DelegateEvent.TASK_TOOL_STARTED, tool_name='test', preview='r')
payload = parent.tool_progress_callback.call_args.kwargs
print(f'Payload size: {len(json.dumps(payload))} bytes')
print(f'Has goal: {\"goal\" in payload}')
"
```

## Observer System: How It Connects to Delegation

```
Session End
    ↓
observer-hook plugin (on_session_end)
    ↓  Activity gate: ≥5 msgs OR ≥2 tool calls OR ≥5K tokens
    ↓
_spawn_observer_worker() → observer_worker.py (separate process)
    ↓
delegate_task ×4 (auditor, critic, idea-generator, knowledge-curator)
    ↓  Each is a subagent with session_search toolset
    ↓
THIS IS WHERE DELEGATION BUGS HIT:
  - Stale pool → 4 subagents × HTTP 400 → 4 failures → no observations
  - Payload bloat → 4 subagents × 50 events × 1200 bytes = 240KB → OOM
```

**Observer config (config.yaml):**

```yaml
observer:
  enabled: false      # master switch (was True when OOM happened)
  inline: true        # regex heuristics (~0.1s, no subagent)
  deep: true          # LLM subagent on turns 1,5,10,15,20
  deep_interval: 5
  session_end: true   # 4 LLM subagents at session end
```

**Before enabling observers, verify:**
1. `delegate_task` works (Phase 2 E2E test passes)
2. Event payload < 200 bytes per event (Phase 3 diagnostic)
3. `max_concurrent_children` is reasonable (not 90 — that's too many for observers)

## Key Files in the Delegation Chain

| File | Role | Critical Functions |
|------|------|-------------------|
| `tools/delegate_tool.py` | Spawning + running children | `delegate_task`, `_build_child_agent`, `_run_single_child`, `_resolve_delegation_credentials`, `_build_child_progress_callback` |
| `agent/agent_runtime_helpers.py` | Runtime state management | `switch_model`, `recover_with_credential_pool` |
| `agent/credential_pool.py` | Pool abstraction | `load_pool`, `CredentialPool`, `PooledCredential` |
| `run_agent.py` + `agent/agent_init.py` | Agent class + init | `AIAgent.__init__` (forwarder), `init_agent` (1743 lines of setup), `AIAgent._swap_credential`, `AIAgent._replace_primary_openai_client` |
| `tui_gateway/server.py` | GUI JSON-RPC gateway | `_make_agent()` (call site 2), `session.create`, `prompt.submit` |
| `gateway/platforms/api_server.py` | HTTP API server | `_create_agent()` (call site 3), `_run_agent()`, `/v1/runs` (async runs) |
| `agent/observer_manager.py` | Observer config | `ObserverManager.is_enabled`, `is_deep_enabled` |
| `plugins/observer-hook/__init__.py` | Session-end spawning | `_spawn_observer_worker`, `_is_observer_session` |

**Three AIAgent() call sites** — all in-process, all the same class:
1. `delegate_tool.py:_build_child_agent` — subagents (ThreadPoolExecutor, shared session_db)
2. `tui_gateway/server.py:_make_agent` — GUI sessions (JSON-RPC, per-session agent)
3. `api_server.py:_create_agent` — external HTTP clients (aiohttp, `loop.run_in_executor`)

See `hermes-codebase/references/agent-creation-architecture.md` for the full
parameter comparison table, the TUI Gateway architecture, and the gap analysis
for routing delegation through the API server (HTTP-based delegation like OpenCode).

## Pitfalls

| Pitfall | Fix |
|---------|-----|
| **Mock tests don't set `child.provider`** | Set `child.provider = "deepseek"` and `child._credential_pool.provider = "deepseek"` in mock setup |
| **Fix works in test but not live** | Running process has old code loaded — restart Hermes after applying fixes |
| **Desktop.log shows old payload** | Desktop (Electron) process is separate — restart desktop app to pick up changes |
| **`delegation.provider` empty in config** | When empty, child inherits parent's provider — this is CORRECT behavior, not a bug |
| **`max_concurrent_children: 90`** | Each child consumes API tokens independently — 90 is dangerous for cost. Set to 3-10 for normal use |
| **Observer subagents cascade** | `_is_observer_session()` must detect them — check env var `HERMES_OBSERVER_SUBAGENT=1` is set by worker |

## Verification Checklist

- [ ] Unit test: `switch_model` updates `_credential_pool` (RED→GREEN)
- [ ] Unit test: `_run_single_child` guards provider mismatch (RED→GREEN)
- [ ] Unit test: `_identity_kwargs` excludes `goal` (RED→GREEN)
- [ ] E2E: `delegate_task(goal="Reply: pong")` returns "pong"
- [ ] E2E: batch (3 tasks) all complete
- [ ] Log: `credential_rotation` uses correct `base_url`
- [ ] Log: 0 HTTP 400 from subagents
- [ ] Payload: < 200 bytes per subagent event
- [ ] Regression: `pytest tests/tools/test_delegate*.py tests/agent/test_switch_model*.py` passes
- [ ] Regression: `pytest tests/run_agent/test_fallback_credential_isolation.py` passes
