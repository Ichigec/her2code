# Observer SDB Persistence Fix (2026-06-26)

## Problem Summary

Observers spawned at Phase 0 were told to "accumulate findings in context and synthesize at Phase 10."
This is impossible: subagent context is STATELESS — it evaporates between checkpoints.

**Evidence:** 0 observer outputs ever persisted across multiple cycles:
- `auditor_memory.md`: "Cycles observed: 0, Mutations proposed: 0"
- `.observations/` directory: did not exist
- `.hermes/reports/` directory: did not exist
- Neo4j: 0 observer-created nodes

## Root Causes (6)

1. No dedicated agent files (inline goals only — no persistence instructions)
2. No write toolsets (`file_ro` only — can't write to disk or curl Neo4j)
3. Fire-and-forget with no durability guarantee
4. `auditor_memory.md` existed but nothing was instructed to append to it
5. Knowledge Curator lacked `terminal` (can't curl to Neo4j)
6. "Accumulate in context" impossible for stateless subagents

## SDB Fix

Applied Srinivasan's Stochastic-Deterministic Boundary (arXiv:2605.20173) to observer checkpoints:

```
PROPOSER → observer reads artifact, analyzes
VERIFIER → observer checks own output (format correct? data valid?)
COMMIT   → observer WRITES to .observations/cycle-{pid}/observer-phase-{N}.md + Neo4j
REJECT   → if verification fails → typed error to errors.log
```

## Files Created/Updated

| File | Action | Key Change |
|------|--------|-----------|
| `~/.hermes/agents/auditor.md` | CREATED (7.1 KB) | SDB contract, persistence to `.observations/`, Neo4j curl templates |
| `~/.hermes/agents/critic.md` | CREATED (5.4 KB) | 3 questions → checkpoint file, over-engineering scoring |
| `~/.hermes/agents/idea-generator.md` | CREATED (7.1 KB) | ADAS-inspired, `(:Mutation)` Neo4j nodes, evolutionary loop |
| `~/.hermes/agents/knowledge-curator.md` | UPDATED | +`file` +`terminal` in toolsets, SDB contract, Neo4j curl templates |
| `~/.hermes/agents/aflow-orchestrator.md` | CREATED (9.4 KB) | MCTS over plan2 phases-as-Operators, parallel variant search |
| `~/.hermes/agents/plan2.md` | UPDATED | Observer spawning → Phase 0, +AFlow, persistence architecture, Phase 10 comparison |
| `~/.hermes/agents/registry.json` | UPDATED | +4 agents, updated toolsets |

## Persistence Architecture

```
.hermes/
├── .observations/cycle-{pid}/
│   ├── auditor-phase-{N}.md
│   ├── critic-phase-{N}.md
│   ├── idea-gen-phase-{N}.md
│   ├── curator-checkpoint-{N}.md
│   └── errors.log
├── reports/
│   ├── auditor-report-{pid}.md
│   ├── critic-report-{pid}.md
│   ├── idea-gen-report-{pid}.md
│   └── curator-report-{pid}.md
├── aflow-variants/
│   └── {pid}-variant.md
└── auditor_memory.md
```

## AFlow Orchestrator

New agent runs in PARALLEL with plan2 from Phase 0:
- MCTS over plan2 phases as AFlow Operators
- Heuristic evaluation via auditor_memory + Neo4j + session_search
- Returns alternative workflow → `.hermes/aflow-variants/{pid}-variant.md`
- Compared to main plan2 in Phase 10

## Verification Checklist

After first cycle with new observers, verify:
- [ ] `.observations/cycle-{pid}/` directory exists with checkpoint files
- [ ] Each checkpoint file ≥500 bytes (not empty stubs)
- [ ] `auditor_memory.md` updated with cycle summary
- [ ] Neo4j has new `(:AuditFinding)`, `(:CriticFinding)`, `(:Idea)`, `(:Mutation)` nodes
- [ ] `.hermes/aflow-variants/{pid}-variant.md` exists
- [ ] `.hermes/reports/` has all 4 final reports
