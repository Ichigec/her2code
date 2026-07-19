# Tech Lead v4 — P0 Implementation Guide

> Implemented 2026-07-03. P0 = Dynamic DAG + Closed-Loop Feedback.
> Applied to 4 files: `plan2/techlead-agent.md`, `plan3/techlead-agent.md`,
> `plan2.md`, `plan3.md`.

## Files modified

| File | Lines before | Lines after | Key changes |
|------|:-----------:|:----------:|-------------|
| `plan2/techlead-agent.md` | 576 | 839 | Dynamic DAG (1a-1d), dag-state.json, §6.5 Feedback Loop (a-d), Phase 6 Report update, Запрещено +4, Phase 11 Self-Evolution (user-gated) |
| `plan3/techlead-agent.md` | 396 | 535 | Dynamic DAG (1a-1d), dag-state.json artifact, DAG Update Protocol for orchestrator, Loop Guards doc, Phase 11 Self-Evolution (user-gated) |
| `plan2.md` | 1216 | 1228 | Phase 6 delegation goal + context, Tech Lead v3 manages (5→7 items), legacy Phase 6 note, context flow ↻, lifecycle contract, artifact validation, pre-phase gate, quality gate, Neo4j schema |
| `plan3.md` | 1228 | 1243 | Phase 6 DAG-driven execution block, context flow ↻, lifecycle contract, artifact validation, pre-phase gate, quality gate, Neo4j schema |

## dag-state.json schema

```json
{
  "cycle_id": "<pid>",
  "version": 1,
  "tasks": [
    {
      "sw_id": "SW#0",
      "status": "pending",         // pending|in_progress|pass|fail|blocked
      "attempts": 0,
      "current_stage": null,        // skeptic|pragmatic|creative|maverick
      "model_assigned": "<from §MODEL ROUTING>",
      "complexity": "L2",           // L1-L5
      "budget": {"tokens": 30000, "time_s": 90, "cost_usd": 0.08},
      "actual": null,               // filled after execution
      "dependencies": [],           // SW IDs this depends on
      "dependents": ["SW#1", "SW#2"],
      "feedback": [],               // filled by 6.5a after each SW
      "dag_updates": []             // filled by DAG Update Protocol
    }
  ],
  "patterns_detected": [],           // filled by 6.5b
  "plan_revisions": [],              // filled by 6.5c
  "cycle_budget": {
    "planned_tokens": 0,
    "actual_tokens": 0,
    "remaining_tasks": 0,
    "projected_total": 0,
    "status": "planned"             // planned|under_budget|over_budget|halted
  }
}
```

## Dynamic DAG

### Update events (5 types)

| Event | Trigger | Action |
|-------|---------|--------|
| New dependency | Developer finds dep not in DAG | Add node + edge, block dependent |
| Interface change | Jidoka FAIL on interface compat | Recalc dependents, update StandardWork |
| Reuse opportunity | Code Navigator: reuse > 0.7 | Reduce scope, downgrade complexity |
| Budget overrun | actual.tokens > budget × 1.3 | Split task or upgrade model |
| Repeated failure | Same failure reason ×3 | Redesign StandardWork from scratch |

### State machine

```
pending ──delegate──▶ in_progress ──PASS──▶ pass
  │                       │
  │ new dep               │ FAIL
  ▼                       ▼
blocked                  fail ──<3 attempts──▶ retry (→in_progress)
                               ──≥3 attempts──▶ redesign (new SW)
                               ──same error 3×──▶ redesign from scratch
```

### Version rule
Every DAG update increments `version` in dag-state.json. Log event in
`tasks[sw_id].dag_updates[]`. If ripple > 3 SWs → escalate to user.

## Feedback Loop Closure (§6.5)

### 6.5a: Feedback Collection (after EVERY SW)

```json
{
  "sw_id": "SW#3",
  "status": "FAIL",
  "developer_stage": "Pragmatic",
  "attempts": 2,
  "tokens_used": 52000,
  "time_seconds": 145,
  "jidoka_verdict": "FAIL",
  "jidoka_failures": ["coverage 78%", "missing edge case: empty input"],
  "review_confidence": 0.65,
  "review_issues": ["Unicode BOM not handled"],
  "navigator_insights": ["Similar impl: utils/parser.py", "reuse: 0.6"],
  "developer_blockers": ["Import contract broken"]
}
```

### 6.5b: Pattern Detection (after every 2nd completed SW)

| Pattern | Condition | Action |
|---------|-----------|--------|
| Import Contract Failure | ≥2 SW with import issues | Add import verification to ALL remaining handoffs |
| Coverage Gap | ≥2 SW with coverage < 80% | Add mandatory Test Designer for L3+ |
| Budget Overrun | ≥2 SW with tokens > budget × 1.3 | Upgrade model for this complexity |
| High Reuse | SW with navigator_reuse > 0.7 | Check merge with dependent SW |
| Repeated Escalation | ≥2 SW reached Pragmatic+ | Recreate StandardWork with different approach |
| Same Error 3× | Same failure reason in 3 SW | Redesign: systemic problem |

### 6.5c: Plan Revision Protocol

On pattern detection → UPDATE (not recreate):
1. Read plan.md + dag-state.json
2. For each pending SW: add kaizen_rules / update model / add Test Designer
3. Write updated files
4. Log revision:
```json
{
  "revision_id": "REV-001",
  "trigger": "import_contract_failure_pattern",
  "sws_affected": ["SW#4", "SW#5", "SW#6"],
  "change": "added import verification to kaizen_rules",
  "timestamp": "2026-07-03T14:32:00Z"
}
```

### 6.5d: Loop Guards

| Guard | Rule | Violation → |
|-------|------|-------------|
| Max iterations per SW | 3 attempts | Force plan revision (redesign SW) |
| Max total retries | 2 × initial_task_count | HALT, escalate to user |
| Max token budget | 150% of planned cycle budget | Switch to cheaper model or simplify |
| Loop detection | Same error reason 3× | Redesign StandardWork from scratch |
| DAG thrashing | >3 DAG updates per cycle | Freeze DAG, finish with current structure |

## Self-Evolution (Phase 11) — User-Gated Governance

**Governance model:** Metrics collection (11.1) and pattern mining + proposal
saving (11.2) are AUTOMATIC. Applying modifications (11.3) and template
evolution (11.4) are ONLY triggered by explicit user request
(«примени self-modifications» / «apply evolution»).

### 11.1: Metrics Collection → Neo4j (AUTOMATIC)

```cypher
CREATE (m:CycleMetric {
  cycle_id: $pid, sw_id: $sw, model: $model, complexity: $cx,
  tokens: $tok, time_s: $t, attempts: $att, escalation: $esc,
  coverage: $cov, verdict: $ver, confidence: $conf,
  navigator_reuse: $reuse, import_issues: $ii, timestamp: timestamp()
})
```

### 11.2: Pattern Mining + Proposal Saving (AUTOMATIC)

```cypher
// Which complexity levels consistently overrun?
MATCH (m:CycleMetric) WHERE m.tokens > m.budget * 1.5
RETURN m.complexity, avg(m.tokens), count(*) AS occurrences
ORDER BY occurrences DESC

// Which models are best for which tasks?
MATCH (m:CycleMetric)
RETURN m.model, m.complexity, avg(m.attempts) AS avg_attempts, avg(m.coverage) AS avg_cov
ORDER BY m.complexity, avg_attempts
```

Proposals saved as `(:SelfModificationProposal)` — NOT applied:

```cypher
CREATE (p:SelfModificationProposal {
  cycle_id: $pid, pattern: $pattern, target: $target,
  change: $change, rationale: $rationale, expected_impact: $impact,
  confidence: $conf, status: "pending", timestamp: timestamp()
})-[:DERIVED_FROM]->(m:CycleMetric {cycle_id: $pid})
```

Neo4j schema (added to both orchestrator files):
```
(:SelfModificationProposal)
  {cycle_id, pattern, target, change, rationale, expected_impact, confidence, status (pending|applied|rejected), timestamp}
  -[:DERIVED_FROM]->(:CycleMetric)
```

Proposal types (all start as `status: "pending"`):

| Pattern (cross-cycle) | Proposal target | Proposed change |
|-----------------------|-----------------|-----------------|
| L3 tasks on kimi → 2+ attempts | model_routing | L3 → deepseek-v4-pro |
| Import contract failures > 30% | handoff_template | add import verification to ALL handoffs |
| Navigator reuse > 0.7 → 1 attempt | standard_work_template | add reuse check as Step 0 |
| Coverage < 80% consistently | jidoka_criteria | add Test Designer mandatory for L3+ |

### 11.3: Apply Self-Modification (ONLY ON USER REQUEST)

When user says «примени self-modifications» / «apply evolution»:

1. Query pending proposals:
```cypher
MATCH (p:SelfModificationProposal {status: "pending"})
RETURN p.pattern, p.target, p.change, p.rationale, p.confidence
ORDER BY p.confidence DESC
```
2. Show list to user via `clarify` (which to apply, which to reject)
3. For approved: apply change to artifact (routing rules, template, criteria) + `SET p.status = "applied", p.applied_at = timestamp()`
4. For rejected: `SET p.status = "rejected"`

### 11.4: Template Evolution (ONLY WITHIN 11.3)

StandardWork template updates only when user approves proposals in 11.3:
- New Kaizen rules from last cycle
- Updated model routing rules (based on actuals)
- Updated budget estimates
- New acceptance criteria patterns

## Lifecycle contract updates

| Phase | ENTRY change | EXIT change |
|-------|-------------|-------------|
| 5 (Plan) | — | +dag-state.json created |
| 6 (Progressive Dev) | +dag-state.json created | +dag-state.json updated + feedback collected + loop guards respected |

### Artifact validation (plan)
Before: `grep "OWNERSHIP"`
After: `grep "OWNERSHIP"` + `test -f <dag-state.json>`

### Pre-phase gate (6: Implementation)
Before: per-dev tools, worktree isolation, capability context injected
After: + dag-state.json exists

### Quality gate (Progressive Dev → Integration)
Before: all code complete; 5 reviewers passed; tests green; circuit breakers stable
After: all code complete; 5 reviewers passed; tests green; dag-state.json updated; feedback collected; loop guards respected

## Context flow (updated)

```
Phase 5.5 PASS → Phase 6 (Progressive Dev Pipeline)
  ↻ Phase 6 internal: SW execute → feedback → pattern detect → plan revision → next SW
Phase 6 output → Phase 6a (DevOps Integration Gate)
```

## Validation methodology (5-level)

After implementing P0 changes, a 5-level validation was run (56/56 tests passed).
This methodology is reusable for future orchestration structural changes.

### Level 1: JSON validation (7 tests)
Extract JSON blocks from agent prompt files, parse with `json.loads()`, verify
required fields. Catches malformed JSON schemas embedded in markdown.

### Level 2: Neo4j Cypher test (7 tests)
Execute CREATE/MATCH/SET statements from Phase 11 against real Neo4j (:7474).
Create test nodes, verify queries work, apply status transitions, then cleanup
with `DETACH DELETE`. Catches Cypher syntax errors and schema mismatches.

### Level 3: Cross-file contract test (20 tests)
Python script that reads all 4 files and checks consistency:
- Path patterns match between orchestrator and techlead
- Variable names match (`dag_state_path` in both)
- Neo4j node labels appear in both schema docs and CREATE statements
- Loop Guards (5/5) and DAG Update Events (5/5) present in both techlead files
- Lifecycle ENTRY/EXIT mentions dag-state.json in both orchestrators
- Self-Evolution guards (АВТОМАТИЧЕСКИ / ТОЛЬКО ПО ЗАПРОСУ) in both techlead files
- Quality gates mention dag-state + feedback + loop guards in both orchestrators

### Level 4: Independent subagent verification (12 tests)
Spawn a `delegate_task` subagent with `toolsets=["file_ro", "search_files"]`
that reads the techlead-agent.md file and checks 12 structural criteria with
quoted line evidence. Catches issues that grep-based tests miss (e.g., section
ordering, semantic correctness).

### Level 5: Pattern injection simulation (10 tests)
Python script that simulates a feedback loop scenario:
- Create mock dag-state.json with 5 SWs (2 with import failures, coverage < 80%)
- Run 6.5b pattern detection logic → verify 2 patterns detected
- Run 6.5c plan revision → verify REV-001 created, version bumped
- Run 6.5d loop guards → verify max iterations (3→redesign), total retries, same-error tracking
- Verify end-to-end trace: feedback → pattern → revision → guards → DAG update

### Key insight
Grep-based structural validation (Level 3) produces false positives when test
patterns are too strict — e.g., checking for a full file path pattern when the
orchestrator correctly uses a variable name (`dag_state_path`) instead. Always
cross-reference with the actual file content before declaring a real failure.

## What's NOT yet implemented (P1-P3)

| Priority | Improvement | Status |
|----------|------------|--------|
| P1 | Context Engineering Stack (4-layer, compaction, routing, budgets) | Not started |
| P1 | Interface Compatibility (AST + Protocol + Runtime in Jidoka) | Not started |
| P2 | Spec Inference (SpecRover pattern) | **IMPLEMENTED (2026-07-03)** in plan3/techlead-agent.md — Step 0.3: read existing code → infer current spec → create Spec Delta JSON (new/refactor/reuse + reuse_potential) → document in §SPEC DELTA. See `techlead-v4-p2-implementation.md`. |
| P2 | Self-Evolution Engine (user-gated) | Phase 11 implemented: 11.1+11.2 auto (metrics→Neo4j CycleMetric, proposals→`(:SelfModificationProposal {status: "pending"})`), 11.3+11.4 user-only (apply on request). **11.1 ENHANCED (2026-07-03):** now includes actual curl command for CycleMetric creation with 15 fields including `budget_tokens` for variance. See `techlead-v4-p2-implementation.md`. |
| P3 | Cost-Aware Execution Tracking (real-time budget monitoring) | Schema in dag-state.json, no runtime enforcement |
