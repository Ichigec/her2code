# Observer Persistence Problem — Deep Analysis

> **Date:** 2026-06-15
> **Source:** codemes_1 distribution packaging cycle
> **Skill:** multi-agent-orchestration (v2.5+)

## The Problem

`delegate_task` creates **stateless leaf agents** that die after returning results.
Observers (Auditor #10, Critic #11, Idea Generator #12) are defined in `plan.md` as
"persistent — they live through the whole cycle" but the Hermes runtime provides
no mechanism for long-lived sub-agents.

## Root Cause: 5 Whys

1. **Why don't observers observe the whole cycle?** → `delegate_task` creates stateless agents that die after returning.
2. **Why doesn't delegate_task support long-lived agents?** → Hermes architecture is request-response: query → process → answer. No background process model.
3. **Why no background process model?** → Hermes was designed as a single-session assistant, not a multi-agent runtime.
4. **Why single-session?** → Early Hermes didn't have 10-phase orchestration cycles with persistent observers.
5. **Root cause: Architectural gap between orchestration layer (prompt) and execution layer (runtime).** `plan.md` describes persistent observers, but Hermes runtime doesn't implement them.

## Impact (measured in codemes_1)

| Loss | Consequence | Example |
|------|-------------|---------|
| Process errors | Observers see final artifacts, not the path | BUG-01 (.env.template missing) found at Phase 8.5, not at Implement |
| Real-time delegation quality | D6 timeout discovered post-hoc | Phase 6 developer interrupted, found only when collecting results |
| Over-engineering prevention | Critic can't stop Phase 4 | 1700 lines of dead library code (yaml_parser.sh, secret_sanitizer.sh, file_copier.sh) |
| Context loss between phases | Auditor can't see incomplete context | Research phase skipped — discovered retrospectively |
| Cross-phase traceability | No history of requirement changes | Only final matrix, no delta tracking |

## Solution: Observer Checkpoint Protocol (immediate fix)

At every quality gate, re-spawn observers with accumulated context:

```
Phase 1: spawn Observer → .observations/checkpoint-01.md
Phase 2: spawn Observer + checkpoint-01.md → checkpoint-02.md
Phase 4: spawn Observer + checkpoint-02.md → checkpoint-04.md
Phase 6: spawn Observer + checkpoint-04.md → checkpoint-06.md
Phase 8.5: spawn Observer + checkpoint-06.md → checkpoint-08.md
Phase 10: spawn Observer + all checkpoints → FINAL.md (triple report)
```

Each checkpoint contains ONLY the delta (new observations), preventing context bloat.
Phase 10 aggregates all checkpoints into the final report.

## Long-Term Solution: Persistent Agent Runtime

Feature Request for `hermes-agent`:
- `delegate_task(persistent=true)` — agent lives until parent session ends
- `notify_on=["phase_complete", "artifact_created"]` — event-driven wake-up
- `heartbeat=300` — timeout for inactivity
- `observer_api` — read artifacts, append observations, escalate to orchestrator

See `docs/deep-analysis/observer-persistence.md` in codemes_1 for the full analysis
with WSM/AHP comparison of 4 alternatives and implementation roadmap.
