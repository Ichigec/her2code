# Delegation Route Preflight

Use this reference when a workflow assigns specific models/providers to subagent roles, or when observer/reviewer subagents must be trusted as independent evidence.

## Problem pattern

A workflow may require a route such as `provider/model` for a role (for example an auditor or critic). The active delegation boundary may still be able to run a default subagent while failing, ignoring, or being unable to prove the intended route. If the orchestrator treats default spawn success as route proof, it can falsely claim that observers reviewed the work.

## Capability report shape

Record separate fields rather than one boolean:

```python
@dataclass(frozen=True)
class DelegationCapabilityReport:
    status: Literal["ready", "degraded", "blocked"]
    can_spawn_observers: bool
    model_provider_overrides_supported: bool
    explicit_model_route_available: bool
    default_route_usable: bool | None
    intended_route_proven: bool
    proven_model: str | None
    proven_provider: str | None
    issues: list[str]
    actions: list[str]
```

Represent the probe route kind explicitly:

```python
@dataclass(frozen=True)
class DelegationProbeResult:
    ok: bool
    model: str | None = None
    provider: str | None = None
    summary: str = ""
    error: str | None = None
    route_kind: Literal["default", "config", "explicit"] = "explicit"
```

## Decision table

| Schema / probe | Meaning | Status | Observer trust |
|---|---|---:|---:|
| No explicit model/provider and no probe | Cannot prove routing | `BLOCKED` | no |
| Probe failed for intended route | Intended route unavailable | `DEGRADED` | no |
| Default probe succeeded but wrong/unknown route | Spawn health only | `DEGRADED` | no |
| Config-routed probe proves required route | Intended route proven without schema overrides | `READY` | yes |
| Explicit probe proves required route | Intended route proven via per-call overrides | `READY` | yes |
| Probe succeeds on a different model/provider | Route drift | `DEGRADED` | no |

## TDD checklist

1. Write RED tests for each row that matters: missing schema, failing intended probe, default-only success, config-routed success, explicit success, wrong-route drift.
2. Implement the smallest preflight evaluator that makes those tests pass.
3. Keep live-routing issues open in the ledger unless a real intended-route smoke probe succeeds.
4. Verify with targeted tests, full tests, compile/syntax check, and git diff/status.

## Safety boundary

Do not mutate live Hermes config/core as a side effect of project implementation. If a workflow needs config-routed proof, either ask for explicit approval to change the live config or keep the project in degraded mode and use local evidence instead of subagent claims.
