# Orchestrator Observer — Variant Architectures

> Research conducted 2026-06-29. Four architectures for an orchestrator-level observer that can spawn subagents. Two families: **Coordination** (spawn observers only, analyze → Neo4j) and **Fix Loop** (spawn developers, close the fix gap). Pavel's explicit constraint (2026-06-29): coordination orchestrator MUST NOT spawn developer — only analyze and write to Neo4j.

## Two Families

| Family | Spawns | Status | Agent file |
|--------|--------|--------|------------|
| **Coordination Orchestrator** | auditor, critic, idea-generator, knowledge-curator | ✅ DEPLOYED v5 | `~/.hermes/agents/observer-orchestrator.md` |
| **Fix-Loop Orchestrator** | developer, security, deployment (via gate) | 📋 Planned | Not yet created |

## Problem

Current observers (Auditor, Critic, Idea Generator, Knowledge Curator) are leaf agents with `toolsets: ["session_search", "terminal"]`. They diagnose and write to Neo4j but CANNOT fix anything. Fix gap: 63 mutations, 0 implementations.

## Technical Base (Already Available)

- `delegate_task(role="orchestrator")` — child gets `delegation` toolset
- `max_spawn_depth: 2` — orchestrator can spawn leaf children
- `orchestrator_enabled: true` — mechanism active
- Orchestrator children retain `delegation` after `_strip_blocked_tools` (line 1005 of delegate_tool.py)

## Variant A: Triage Scheduler (Cron-Driven, Minimal)

```
Every N minutes:
  Observer-Triage (orchestrator)
    ├─ 1. Read Neo4j: MATCH mutations WHERE status IN ['proposed','no_status']
    ├─ 2. Sort by: severity × recurrence × dependency × confidence
    ├─ 3. Pick TOP-1
    ├─ 4. Spawn developer (leaf) to implement
    ├─ 5. Observer verifies (grep/pytest)
    └─ 7. Update Neo4j: SET status = 'implemented' | 'rejected'
```

**Effort:** ~150 lines (`observer_worker_triage.py` + 1 cron job)
**Risk:** Low — one fix per tick, easy rollback
**Time to MVP:** 1 day
**Spawns:** 1 developer per tick

## Variant B: Observer-Gate (Jidoka Pattern, Event-Driven)

```
After each plan2 phase:
  Observer-Gate (orchestrator)
    ├─ 1. Read all unclosed findings for this phase
    ├─ 2. Group by root_cause ([:SAME_ROOT_CAUSE])
    ├─ 3. For blocking groups (CRITICAL/HIGH):
    │     ├─ Spawn developer
    │     └─ Spawn Jidoka (independent verification)
    └─ 4. Update Neo4j, continue cycle
```

**Effort:** ~400 lines + plan.md integration
**Risk:** Medium — blocks phases at CRITICAL
**Time to MVP:** 3 days
**Spawns:** N developers + N jidokas per gate

## Variant C: Autonomous Observer-Agent (Long-Running Orchestrator)

```
Session start → spawn Observer-Agent (orchestrator, lives entire session)
  Own cycle (every 5 min / every N phases):
    ├─ Read Neo4j for new findings
    ├─ Cluster, prioritize
    ├─ Spawn: developer (code), researcher (research), architect (architecture)
    ├─ Track status
    └─ Session end: synthesis report
```

**Effort:** ~800 lines + conversation_loop integration
**Risk:** High — long-running subagent with spawn rights
**Time to MVP:** 1-2 weeks
**Spawns:** Many subagents across session

## Variant D: Hybrid (Recommended)

Two-level architecture combining A + B:

**Level 1 — Observer-Gate (synchronous, in-session):**
- Only BLOCKING findings (CRITICAL + HIGH with dependencies)
- Max 3 fixes per gate
- Jidoka verification on each

**Level 2 — Triage Scheduler (asynchronous, cron):**
- Non-blocking findings (MEDIUM, LOW, ideas)
- 1 fix per tick
- Self-verification

**Effort:** ~550 lines total
**Risk:** Low/Medium
**Time to MVP:** 1 day (Level 2 only) → 4 days (both levels)

## Comparison Table

| Criterion | A: Triage | B: Gate | C: Autonomous | D: Hybrid |
|-----------|-----------|---------|---------------|-----------|
| Complexity | ★☆☆☆☆ | ★★★☆☆ | ★★★★★ | ★★★☆☆ |
| Risk | Low | Medium | High | Low |
| Fix speed | Slow | Medium | Fast | Med/Fast |
| Blocks user | No | Yes (CRITICAL) | No | CRITICAL only |
| plan2 integration | No | Full | Partial | Full |
| SDB contract | Self-verify | Jidoka gate | Self-verify | Jidoka + self |
| Parallelism | No | By group | Full | By group |
| Time to MVP | 1 day | 3 days | 2 weeks | 1→4 days |

## Spawn Decision Logic

**WHO to spawn:**

| Finding type | Spawn target | Toolsets | Role |
|-------------|-------------|----------|------|
| AuditFinding (code) | developer | terminal, file, search | leaf |
| CriticFinding (architecture) | architect | terminal, file, search | leaf |
| Idea (research) | researcher | web, session_search | leaf |
| KnowledgeEntity gap | knowledge-curator | terminal, search | leaf |

**WHEN to spawn:**

| Severity | Mechanism | Timing |
|----------|-----------|--------|
| CRITICAL | Observer-Gate (sync) | Immediately, blocks phase |
| HIGH | Observer-Gate (sync) | Immediately, blocks phase |
| MEDIUM | Triage Scheduler (async) | Next cron tick |
| LOW | Triage Scheduler (async) | Next cron tick |

**WHAT to fix:**

Prioritization formula: `severity_score × confidence × recurrence / (1 + dependency_depth)`

Group by `[:SAME_ROOT_CAUSE]` — fix root, not symptoms. Independent mutations → parallel spawn. Dependent mutations → sequential.

## Key Risks

| Risk | Mitigation |
|------|-----------|
| Developer breaks code | Jidoka verification; `git stash` on failure |
| Observer dies mid-spawn | Triage tracks status; 5-min timeout → mark `stale` |
| Hallucinated fix | Only mutations with `confidence > 0.7`; Jidoka checks finding→fix alignment |
| Spawn cascade | Hard limit: max 3 spawns per gate; max 1 per cron tick |
| Token cost | Triage: ~5K/spawn; Gate: ~15K (3 spawns). Acceptable |

## Implementation Phases

### Phase 1 (MVP, 1 day): Triage Scheduler
1. Create `~/.hermes/scripts/observer_worker_triage.py`
2. Schedule via `hermes cron create --no_agent true --script observer_worker_triage.py`
3. Manual first run to verify safety

### Phase 2 (3-4 days): Observer-Gate in plan2
1. Add `~/.hermes/agents/observer-gate.md` (orchestrator role)
2. Insert Phase 6.6 between Verification Gate (6.5) and Security (7)
3. Integration in `plan.md` phase list

### Phase 3 (future): Autonomous Observer-Agent
Only if Hybrid proves stable. Full ADAS evolutionary loop.
