# Session Source Tagging — Complete Resolution Chain

## The Bug

Observer sessions appeared with `source='cli'` in `state.db` despite `--source observer` flag.

## Root Cause Chain

### 1. `cli.py:5248` — hardcoded `platform="cli"`
```python
self.agent = AIAgent(
    ...
    platform="cli",  # ← HARDCODED, overrides everything
    ...
)
```
Every `hermes chat` invocation gets `platform="cli"`.

### 2. `run_agent.py:509` — platform takes priority over env var
```python
# OLD (broken):
source = self.platform or os.environ.get("HERMES_SESSION_SOURCE", "cli")
# self.platform is "cli" (from #1), so env var is IGNORED
# NEW (fixed):
source = os.environ.get("HERMES_SESSION_SOURCE") or self.platform or "cli"
# Env var checked FIRST, then platform
```

### 3. `observer_worker.py` — `--cli` flag overrode `--source`
The `--cli` flag sets `platform="cli"` which (before fix #2) took priority over `--source observer`.

## Fixes Applied

### Fix 1: `run_agent.py:509` — env var priority
```python
source = os.environ.get("HERMES_SESSION_SOURCE") or self.platform or "cli"
```

### Fix 2: `observer_worker.py` — remove `--cli`, add env var
```python
# OLD: [HERMES_CLI, "chat", "-q", prompt, "--cli", "--yolo", ..., "--source", "observer"]
# NEW: [HERMES_CLI, "chat", "-q", prompt, "--yolo", ..., "--source", "observer"]
# Also: env={..., "HERMES_SESSION_SOURCE": "observer"}
```

### Fix 3: `conversation_loop.py` — `platform="observer"` for deep observer
```python
obs_json = _delegate(
    goal=goal, context=..., toolsets=...,
    parent_agent=agent, role="leaf", max_iterations=4,
    platform="observer",  # ← tags subagent session
)
```

### Fix 4: `delegate_tool.py` — `platform` parameter plumbing
- `delegate_task()`: added `platform: Optional[str] = None` param
- Task dict: `{"goal": goal, ..., "platform": platform}`
- `_build_child_agent()`: added `platform: Optional[str] = None` param
- `AIAgent.__init__()`: `platform=platform or parent_agent.platform`

## Verification

```bash
# Test CLI path
hermes chat -q "echo test" --source observer --yolo -m deepseek-v4-pro --provider deepseek
sqlite3 ~/.hermes/state.db "SELECT source FROM sessions ORDER BY rowid DESC LIMIT 1"
# Should return: observer

# Check all session sources
sqlite3 ~/.hermes/state.db "SELECT source, COUNT(*) FROM sessions GROUP BY source"
# observer: N, tui: 1, cli: 0 (after cleanup)
```

## Desktop Filtering

After source tagging is fixed, the desktop filters observer sessions:
```ts
// desktop-controller.tsx
excludeSources: ['cron', 'observer']
```
Observer sessions still appear in `$observerSessions` atom (fetched separately) and in the ObserverPanel dropdown.
