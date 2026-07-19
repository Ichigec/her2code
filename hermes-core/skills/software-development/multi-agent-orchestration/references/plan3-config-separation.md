# Plan3 Config Separation & Model Routing Enforcement

## The Core Problem

plan3 is designed as a "Fully Local" orchestrator — 3 specialized local models
(reasoning/coding/simulation) replace a single cloud model. But Hermes has a
fundamental architectural gap: **agent file frontmatter `model:` does NOT control
the session model — it only applies to sub-agents.** The session model comes
from `config.yaml` → `model.default`.

This creates a 5-point vulnerability chain:

| # | What breaks | Why | Where |
|---|------------|-----|-------|
| 1 | Session model | `model.default` in config.yaml ≠ plan3.md frontmatter | `config.yaml:2` |
| 2 | Sub-agents ignore routing | Orchestrator LLM can "forget" model/provider in delegate_task | Runtime |
| 3 | Frontmatter drift | 18 plan3/*.md files — any can be edited without validation | `~/.hermes/agents/plan3/*.md` |
| 4 | registry.json drift | Stale cloud entries survive migration | `registry.json` |
| 5 | LLM fabrication | Orchestrator invents non-existent model names | Runtime |

## Solution Matrix

### Layer 1: Profile-Based Isolation (fixes #1)

```bash
hermes profile create plan3 --clone-from default
hermes config set model.default agents-a1-abliterated --profile plan3
hermes config set model.provider custom:local --profile plan3
hermes --profile plan3    # session now uses local model
```

**What it fixes:** The session (orchestrator) itself runs on a local model.
**What it doesn't fix:** Sub-agent routing — delegate_task can still use wrong models.

### Layer 2: Pre-Delegation Validation Script (fixes #2)

Add to plan3.md system prompt:

```
Before EVERY delegate_task, run:
  python3 ~/.hermes/scripts/validate-plan3-models.py --quick
Exit 0 = models healthy, Exit 1 = DO NOT DELEGATE.
```

Or use `verify-agent-model-consistency.py` (already in hermes-custom-providers/scripts/).

### Layer 3: Pre-Flight Gate (fixes #3, #4)

`orchestrator_gate.py` already has 7 checks before Phase 6. Add an 8th:

```python
def check_model_routing(self):
    """Verify plan3 sub-agents use correct model/provider."""
    result = subprocess.run(
        ["python3", f"{HERMES_HOME}/skills/.../validate-plan3-models.py", "--json"],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    self._add("model_routing", data["passed"],
              f"Frontmatter: {len(data['frontmatter'])} agents, "
              f"Registry cloud: {data['registry_cloud_count']}")
```

**What it fixes:** Catches drift before implementation starts.
**What it doesn't fix:** Runtime routing errors in Phases 1-5.

### Layer 4: Capability Gate (fixes #1-#4 at bootstrap)

In `capability_gate.py`, add `plan3-model-routing` as a BLOCKER capability:

```python
CapabilityRecord(
    name="plan3-model-routing",
    available=False,
    severity=Severity.BLOCKER,
    detection_method=GapDetectionMethod.LIVE_PROBE,
    check_command="python3 ~/.hermes/skills/.../validate-plan3-models.py --json"
)
```

**What it fixes:** Cycle BLOCKED at Phase 0 if models are misconfigured.
**What it doesn't fix:** Mid-cycle drift.

### Layer 5: Hermes Plugin/Hook (fixes ALL — future)

A hook on `delegate_task` that validates model/provider against routing table:

```python
# ~/.hermes/hooks/plan3_routing_enforcer.py
def on_delegate_task(task):
    role = classify_role(task.goal)
    expected = ROUTING[role]
    if (task.model, task.provider) != expected:
        raise RoutingError(f"BLOCKED: got ({task.model}, {task.provider}), "
                          f"expected {expected}")
```

**Status:** Requires Hermes hook system extension for delegate_task interception (not yet available).

## Recommended Stack (today)

For immediate protection, deploy Layers 1+2+3:

1. **Profile `plan3`** — session model = local
2. **Pre-delegation script check** — embedded in plan3.md system prompt
3. **Pre-flight gate 8th check** — catches drift at Phase 5.5

## Validation Script

`scripts/validate-plan3-models.py` (in multi-agent-orchestration skill) runs
5 checks:
1. Sub-agent frontmatter (18 files) model/provider consistency
2. registry.json cloud providers
3. Physical llama-server health (:8101/:8102/:8103)
4. start-llama.sh operational health (PID files + process count)
5. LiteLLM :4000 connectivity for all 3 models

Exit 0 = fully local confirmed. Use `--fix` to auto-correct frontmatter drift.
