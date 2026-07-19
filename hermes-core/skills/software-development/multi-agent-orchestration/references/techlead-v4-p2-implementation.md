# Tech Lead v4 — P2 Implementation Guide

> Implemented 2026-07-03. P2 = Specification Inference + Enhanced Self-Evolution Metrics.
> Applied to: `~/.hermes/agents/plan3/techlead-agent.md`.

## Overview

| Improvement | Source | Status |
|------------|--------|--------|
| Specification Inference (Step 0.3) | SpecRover (ICSE 2025) | IMPLEMENTED |
| Enhanced Phase 11.1 (Neo4j metrics) | Darwin Godel (ICLR 2026) | ENHANCED |
| §SPEC DELTA plan section | — | ADDED |

## Specification Inference (Step 0.3)

### Problem

Tech Lead creates StandardWork from target architecture without reading existing
code. Developer gets "create parser" when 60% already exists → rework, conflicts,
wasted tokens.

### Solution

Before creating StandardWork, Tech Lead infers the current specification from
existing code and creates a Spec Delta.

### Process

1. **Read existing code** (if file exists):
   - `read_file(path)` — current implementation
   - Neo4j: `MATCH (f:CodeFile)-[:CONTAINS]->(c:CodeClass) WHERE f.name CONTAINS "<module>" RETURN c`
   - Neo4j: `MATCH (f:CodeFile)-[:CALLED_BY]->(caller) WHERE f.name CONTAINS "<module>" RETURN caller.name, caller.line`

2. **Infer current specification:**
   - Methods: names, signatures, return types
   - Exceptions: what it throws
   - Callers: who calls it (file:line)
   - Dependencies: what it imports

3. **Compare with target architecture:**
   - What already exists? → reuse (don't rewrite)
   - What's missing? → new code
   - What conflicts? → refactor
   - Estimate `reuse_potential` (0.0 = full rewrite, 1.0 = everything exists)

4. **Create Spec Delta JSON per file:**

```json
{
  "file": "plugins/foo/parser.py",
  "exists": true,
  "current_spec": {
    "methods": [{"name": "parse", "signature": "parse(input: str) -> dict", "line": 15}],
    "exceptions": ["ValueError"],
    "callers": [{"file": "orchestrator.py", "line": 42}, {"file": "cli.py", "line": 18}]
  },
  "target_spec": {
    "methods": [{"name": "parse", "signature": "parse(input: str) -> ParsedDocument"}],
    "exceptions": ["ParseError"]
  },
  "delta": "refactor: return type dict->ParsedDocument, exception ValueError->ParseError, update 2 callers",
  "reuse_potential": 0.6,
  "action": "refactor"
}
```

5. **Use delta in StandardWork:**
   - `action: "new"` → create from scratch (as before)
   - `action: "refactor"` → modify existing (specify exactly what to change)
   - `action: "reuse"` → possibly merge with another task or simplify

### Graceful degradation

If file doesn't exist → `reuse_potential: 0.0`, `action: "new"`, behavior identical
to previous. No regression on new projects.

### Plan documentation

Spec Delta documented in plan as `§SPEC DELTA` section (between §IMPORT CONTRACTS
and §STREAM TASKS).

### Source

SpecRover (ICSE 2025, arXiv:2408.02232) — +12% success rate with specification
inference before coding.

## Enhanced Phase 11.1: Metrics Collection → Neo4j

### Before (P0)

Phase 11.1 was text-only: "Прочитай финальный dag-state.json. Проанализируй: ..."
— no actual Neo4j storage command.

### After (P2)

Phase 11.1 now includes explicit curl command for CycleMetric node creation:

```bash
curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"CREATE (m:CycleMetric {cycle_id: $pid, sw_id: $sw_id, model: $model, complexity: $complexity, tokens: $tokens, time_s: $time_s, attempts: $attempts, escalation: $escalation, coverage: $coverage, verdict: $verdict, confidence: $confidence, navigator_reuse: $reuse, import_issues: $import_issues, budget_tokens: $budget_tokens, timestamp: timestamp()})"}]}' \
  http://localhost:7474/db/neo4j/tx/commit
```

### CycleMetric fields (15 total)

| Field | Source | Purpose |
|-------|--------|---------|
| `cycle_id` | Plan | Cross-cycle querying |
| `sw_id` | Plan | Per-task identification |
| `model` | Plan | Model effectiveness analysis |
| `complexity` | Plan | L1-L5 routing optimization |
| `tokens` | dag-state.json actual | Cost tracking |
| `time_s` | dag-state.json actual | Latency tracking |
| `attempts` | dag-state.json actual | Difficulty signal |
| `escalation` | dag-state.json actual | Stage reached (Skeptic→Maverick) |
| `coverage` | Jidoka/Review | Quality signal |
| `verdict` | Jidoka | PASS/FAIL |
| `confidence` | Review | Review confidence score |
| `navigator_reuse` | Spec Delta | Reuse potential (0.0-1.0) |
| `import_issues` | Feedback | Import contract failures count |
| `budget_tokens` | Plan | Planned budget (for variance = actual/budget) |
| `timestamp` | Neo4j | Temporal ordering |

### Pattern Mining Queries (11.2 — unchanged from P0)

```cypher
// Which complexity levels consistently overrun?
MATCH (m:CycleMetric) WHERE m.tokens > m.budget_tokens * 1.5
RETURN m.complexity, avg(m.tokens), count(*) AS occurrences
ORDER BY occurrences DESC

// Which models are best for which tasks?
MATCH (m:CycleMetric)
RETURN m.model, m.complexity, avg(m.attempts) AS avg_attempts, avg(m.coverage) AS avg_cov
```

## Self-Evolution Governance (user-gated — CRITICAL design principle)

| Step | What | Automatic? |
|------|------|:----------:|
| 11.1 | Collect metrics → Neo4j CycleMetric nodes | YES |
| 11.2 | Pattern mining → SelfModificationProposal {status: "pending"} | YES |
| 11.3 | Show proposals to user via clarify → apply approved | USER-GATED |
| 11.4 | Template evolution (Kaizen, routing, budgets) | USER-GATED |

**Key principle (user-mandated):** Agents MUST NOT self-modify their own operating
parameters (routing, templates, criteria). They propose; the human disposes.

This contrasts with the Auditor's auto-apply of safe changes (pitfalls, environment
facts) — those are observational corrections, not self-modification of the agent's
own decision parameters.

## Files modified

| File | Changes | Lines added |
|------|---------|:-----------:|
| `~/.hermes/agents/plan3/techlead-agent.md` | Step 0.3 (Spec Inference), enhanced 11.1 (Neo4j curl), §SPEC DELTA in format, role list updated (11 items), frontmatter description | ~78 |
| `~/.hermes/agents/plan3/techlead-agent.md` (review fixes) | BUG: `m.budget`→`m.budget_tokens` in 11.2; GAP: Spec Delta in SW example + Handoff template; GAP: 2 new prohibitions; MINOR: cross-ref to Phase 11 | ~20 |

## Post-implementation review (2026-07-03)

After initial P2 implementation, a systematic review of the full file (611 lines)
found 5 issues — 1 BUG + 4 GAPs. All fixed.

### BUG 1: Neo4j property name mismatch (CRITICAL)

Phase 11.1 CREATE used `budget_tokens` but Phase 11.2 MATCH queried `m.budget`:
```cypher
// 11.1 (correct):
CREATE (m:CycleMetric {... budget_tokens: $budget_tokens ...})
// 11.2 (was WRONG — always returned 0 results):
MATCH (m:CycleMetric) WHERE m.tokens > m.budget * 1.5
// 11.2 (FIXED):
MATCH (m:CycleMetric) WHERE m.tokens > m.budget_tokens * 1.5
```

**Lesson:** When the same property is used in CREATE (write) and MATCH (read)
across different sections of an agent prompt, the names MUST match. A mismatch
silently breaks pattern mining — no error, just empty results.

### GAP 2: StandardWork example missing Spec Delta fields

The SW#3 example (template all agents copy) had no Spec Delta fields. For
`action: "refactor"`, developer needs: current state, target state, delta,
callers to update. **Fixed:** added `Spec Delta action` row to SW header table
+ `#### Spec Delta` section with Current/Target/Delta/Reuse/Callers rows.

### GAP 3: Developer Handoff template missing Spec Delta

Handoff template said "Реализовать Parser класс" (create) but Spec Delta says
`action: "refactor"`. **Fixed:** added Spec Delta block to handoff with
explicit "НЕ переписывай с нуля" instruction and caller update list.

### GAP 4: "Запрещено" section didn't enforce Spec Inference

No prohibition against creating StandardWork without Spec Delta. **Fixed:**
added two prohibitions:
- "Создавать StandardWork без Spec Delta"
- "Писать 'создай с нуля' если файл существует — используй action: 'refactor'"

### MINOR 5: "После успешного деплоя" duplicated Phase 11 without cross-reference

Two sections described post-cycle activities with no link between them. **Fixed:**
added step 4 to "После деплоя": "Выполни Phase 11 (ниже)".

### Review methodology for agent prompt files

The 5-level check that found these issues:

| Level | What to check | How |
|-------|--------------|-----|
| 1. Property consistency | Names in CREATE/MATCH/SET match across sections | grep property names, compare write vs read |
| 2. Example completeness | New features appear in examples/templates, not just instructions | Read every example block, verify it demonstrates the feature |
| 3. Template cross-reference | Handoff templates include new fields that instructions require | Compare StandardWork instruction vs Handoff template |
| 4. Prohibition enforcement | "Запрещено" section covers new mandatory steps | List all mandatory steps, check each has a prohibition |
| 5. Section cross-reference | Related sections reference each other | Check "После деплоя" → Phase 11, format → instructions |

**Key insight:** Agent prompt files are code. They have write/read contracts
(Neo4j CREATE/MATCH), template instantiation (examples become real StandardWork),
and enforcement (Запрещено section). Review them with the same rigor as code.

## What's NOT yet implemented (remaining)

| Priority | Improvement | Status |
|----------|------------|--------|
| P1 | Context Engineering Stack (4-layer, compaction, routing, budgets) | Not started |
| P1 | Interface Compatibility (AST + Protocol + Runtime in Jidoka) | Not started |
| P3 | Cost-Aware Execution Tracking (real-time budget monitoring) | Schema in dag-state.json, no runtime enforcement |
