# Quality Gate Runner — Implementation Pitfalls

> Extracted from `quality-gate-runner` skill. Keep this reference updated when new pitfalls emerge.

## Import Structure

The gates package lives at `~/.hermes/gates/`. The runner script adds `~/.hermes/` to `sys.path`. All modules inside `gates/` use absolute imports: `from gates.base import GatePlugin`. Do NOT use relative imports (`from .base import`) — they fail when loaded via `spec_from_file_location`.

## Gate Discovery

`registry.py` uses `importlib.util.spec_from_file_location` + `exec_module` to load `.py` files from `gates/gates/`. The `importlib.import_module(module_name, package="...")` approach does NOT work for packages that aren't pip-installed.

## Threshold/Timeout Attributes

These are PLAIN CLASS ATTRIBUTES on `GatePlugin`, not `@property` decorators. `@property` breaks `_apply_config` which does `instance.threshold = value` (no setter). Override in subclass via `threshold = 0.80`.

Example:
```python
class GatePlugin(ABC):
    name: str = ""
    threshold: float = 1.0   # Plain attribute, NOT @property
    timeout: int = 120        # Plain attribute, NOT @property
```

## BA Gate Level 0

The scheduler puts mandatory gates (`mandatory=true`) at their own dedicated Level 0, running BEFORE all other gates. This prevents fast-fail from canceling BA gate's instant result. Without this, BA gate completes in 0ms, fails, and cancels all other gates before they start.

Implementation in `runner.py::_topological_sort()`:
```python
# Mandatory gates run first, alone in their own level
mandatory_names = {g.name for g in gates if g.mandatory}
if mandatory_names:
    mandatory_level = [gate_map[name] for name in mandatory_names if name in gate_map]
    if mandatory_level:
        levels.append(mandatory_level)
        completed.update(mandatory_names)
```

## Fast-Fail Collection

When a gate fails in parallel execution, the scheduler collects results from already-completed futures BEFORE canceling remaining ones. `future.cancel()` on a running future loses its result — collect via `future.result()` on done futures first.

```python
if not result.passed:
    # Collect from already-completed futures FIRST
    for f in list(futures.keys()):
        if f.done() and f != future:
            try:
                r = f.result()
                results.append(r)
            except Exception:
                pass
    # THEN cancel remaining
    for f in futures:
        if not f.done():
            f.cancel()
```

## SecurityGate Tools Config

Mode-specific tool config (e.g., speed mode → only bandit) is injected into `artifacts["security_tools"]` by the scheduler BEFORE running gates. The gate reads from `artifacts`, not from config.yaml directly.

In `runner.py::run_all()`:
```python
mode_config = self.config.get("modes", {}).get(self.mode, {})
if "security-gate" in mode_config:
    tools_override = mode_config["security-gate"].get("tools", {})
    if "security_tools" not in artifacts:
        artifacts["security_tools"] = tools_override
```

## Commit-Msg Hook Blocks --no-verify

Git's `--no-verify` skips pre-commit but NOT commit-msg. The commit-msg hook requires `GatePassport:<cycle_id>:<hmac16>` in the commit message. Merge commits, reverts, and documents-only commits are exempt.

## AcceptanceGate in Speed Mode

Was previously disabled in speed mode. Now mandatory across all modes. Will fail with "no service" diagnostic when no deployment is active → returns `fix_phase=8, fix_agent=deployment` — orchestrator routes to deployment phase. This is intentional signaling, not a bug.

## GatePassport Expiry

30-minute window. Re-run gates before deploy if passport is stale. HMAC secret at `~/.hermes/gates/.gate-secret` (0600, 32 random bytes, auto-generated on first run). Same secret must exist on VPS for deploy verification.
