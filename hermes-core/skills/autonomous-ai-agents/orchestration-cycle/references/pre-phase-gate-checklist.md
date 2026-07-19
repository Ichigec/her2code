# Pre-Phase Gate Checklist — all 15 phases

> Reference for `orchestration-cycle` skill. 145 checks across 15 plan2 phases/sub-phases.
> Sources: CI/CD patterns (Jenkins, SonarQube, OPA, Stage-Gate), BA frameworks (BACCM, SPIN, 5 Whys, MoSCoW).

## Gate Architecture

Each phase has a pre-hook gate following the PEP/PDP pattern (RFC 2753):
- **PEP** (Policy Enforcement Point) intercepts phase transition
- **PDP** (Policy Decision Point) evaluates gate rules → Go/Kill/Hold/Recycle

Gates use deny-by-default (OPA pattern): phase blocked unless explicitly allowed.

## Severity Taxonomy

| Severity | Code | Gate Behavior |
|----------|------|---------------|
| BLOCKER | B | Phase CANNOT start. Hard fail. threshold=1.0 |
| CRITICAL | C | Phase starts degraded. Max 20% tolerated. threshold=0.8 |
| HIGH | H | Phase proceeds with warning. Fix before downstream. threshold=0.6 |
| MEDIUM | M | Advisory. Captured in observers. Non-blocking. |

## Per-Phase Check Summary

| Phase | Gate | Checks | BLOCKER | Key BLOCKER Examples |
|-------|------|:------:|:-------:|---------------------|
| 0: Bootstrap | `gate:bootstrap` | 12 | 5 | FS writable, AGENTS.md exists, registry valid, capability inventory loaded |
| 1: Requirements | `gate:requirements` | 9 | 2 | BACCM dimensions covered, ACs verifiable |
| 2: System Analysis | `gate:system-analysis` | 8 | 2 | Alternatives feasible, goal tree reachable |
| 3: Research | `gate:research` | 19 | 11 | Searchbox accessible, sources diverse ≥3 types |
| 4: Architecture | `gate:architecture` | 10 | 3 | Module contracts feasible, no port conflicts |
| 5: Plan | `gate:plan` | 9 | 2 | Tasks executable, OWNERSHIP complete, fabrication scan |
| 5.5: Pre-Flight | `gate:preflight` | 14 | 8 | Services healthy, capability report exists, dev tools |
| 6: Implementation | `gate:implementation` | 10 | 2 | Per-dev tools, worktree isolation, capability context |
| 6a: Integration | `gate:integration` | 5 | 1 | No orphan modules, integration tests green |
| 6.5: Verification | `gate:verification` | 7 | 2 | GAP propagation, spec conformance, goal tree |
| 7: Security | `gate:security` | 9 | 2 | SAST tools available, pip-audit, gitleaks |
| 8: Deployment | `gate:deployment` | 10 | 4 | Target reachable, permissions, Docker |
| 8.5: Acceptance | `gate:acceptance` | 8 | 3 | Tests executable, traceability, autonomous testing |
| 9: Post-Deploy | `gate:postdeploy` | 6 | 2 | Monitoring accessible, logs available |
| 10: Iterate | `gate:iterate` | 9 | 3 | Reports generatable, Neo4j accessible |
| **TOTAL** | | **145** | **52** | |

## Stage-Gate Semantics (Cooper, 1990)

| Verdict | When | Action |
|---------|------|--------|
| **Go** | All BLOCKER = PASS | Proceed to next phase |
| **Kill** | BLOCKER = FAIL, no resolution | Halt cycle, escalate to user |
| **Hold** | BLOCKER = FAIL, resolution exists | Pause, execute resolution, retry gate |
| **Recycle** | Downstream GAP found | Return to previous phase with specific GAP |

## CI/CD Pattern Mappings

| CI/CD Pattern | plan2 Application |
|---------------|------------------|
| Jenkins `when` directive | Declarative phase entry conditions |
| SonarQube Quality Gate | Metric threshold gates (≥80% checks PASS) |
| OPA admission controllers | Default-deny phase transition policy |
| Git hooks (pre-commit) | `pre-phase-N` gate scripts |
| Stage-Gate (Cooper) | Go/Kill/Hold/Recycle decisions |
| Feature flags | Circuit breakers per capability |
| K8s ValidatingWebhook | Externalizable gate webhooks |

## GAP Propagation Tracking (Phase 6.5 new check #5)

System Analyst verifies:
1. All GAPs from `capability_report.json` reflected in code?
2. Each GAP has workaround or delegate_to_user?
3. No new GAPs introduced during implementation?
4. All UNTESTABLE ACs have resolution?
