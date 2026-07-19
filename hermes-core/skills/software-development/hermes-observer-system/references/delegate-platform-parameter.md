# Delegate Platform Parameter — Root Cause & Fix

**Session:** 2026-06-27, observer session spam investigation
**Problem:** Deep observer subagent sessions appearing as `source='cli'` instead of `source='observer'`
**Root cause:** `delegate_tool.py:1157` hardcodes `platform=parent_agent.platform` when building child `AIAgent`, making env-var overrides impossible.

## Why the env-var approach failed

In `run_agent.py:509`:
```python
source = self.platform or os.environ.get("HERMES_SESSION_SOURCE", "cli")
```

Since `_build_child_agent()` passes `platform=parent_agent.platform`, the child's `self.platform` is always truthy (inherited from parent — 'tui' for desktop sessions). The `or` short-circuits to `self.platform`, never reaching the env var.

Setting `HERMES_SESSION_SOURCE=observer` before calling `delegate_task()` had no effect because the child agent's platform was already 'tui'.

## The fix: parameter plumbing

Three files modified:

### 1. `tools/delegate_tool.py` — `delegate_task()` signature
```python
def delegate_task(
    ...
    platform: Optional[str] = None,  # NEW
    parent_agent=None,
) -> str:
```

### 2. `tools/delegate_tool.py` — single-task dict
```python
task_list = [
    {
        "goal": goal,
        "context": context,
        ...
        "platform": platform,  # NEW
    }
]
```

### 3. `tools/delegate_tool.py` — `_build_child_agent()` signature
```python
def _build_child_agent(
    ...
    platform: Optional[str] = None,  # NEW
):
```

### 4. `tools/delegate_tool.py` — `AIAgent` construction (line 1157)
```python
# Before:
platform=parent_agent.platform,
# After:
platform=platform or parent_agent.platform,
```

### 5. `agent/conversation_loop.py` — caller
```python
obs_json = _delegate(
    goal=goal,
    ...
    platform="observer",  # NEW
)
```

## Verification

Check `state.db` for observer-tagged sessions:
```sql
SELECT id, source FROM sessions WHERE source='observer' ORDER BY started_at DESC LIMIT 5;
```

Properly tagged sessions should appear with `source='observer'` instead of `source='cli'` or `source='tui'`.
