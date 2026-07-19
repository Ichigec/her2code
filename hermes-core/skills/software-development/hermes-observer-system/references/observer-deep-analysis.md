# Observer Deep Analysis: Why Observers Were Empty

**Date:** 2026-06-26
**Source:** Plan2 orchestrator session analysis

## Six Root Causes

| # | Root Cause | Detail | Fix |
|---|-----------|--------|-----|
| 1 | No agent files | Auditor/Critic/Idea Generator had no `.md` files — only inline goal strings in plan2.md | Created `auditor.md`, `critic.md`, `idea-generator.md` |
| 2 | Stateless context | Subagent context is volatile between phases. "Accumulate in context" impossible | Observers write to Neo4j on EVERY checkpoint |
| 3 | Fire-and-forget checkpoints | Orchestrator didn't wait for results — even if observer wrote something, it was lost | Wait for Neo4j writes (30s timeout) |
| 4 | Read-only toolsets | `[file_ro, search_files, session_search]` — only READING, no writing | Added `terminal` for curl to Neo4j |
| 5 | Knowledge Curator without terminal | Had agent file but no `terminal` in toolsets — couldn't curl to Neo4j | Added to toolsets |
| 6 | No writer for auditor_memory.md | File existed with correct format but no agent had instruction to append | Auditor appends from Neo4j data |

## SDB Gap

```
Current flow:                    SDB-correct flow:
PROPOSER: observer reads         PROPOSER: observer reads
  → analysis in context            → analysis
                                 VERIFIER: validates output
VERIFIER: ❌ ABSENT              COMMIT: writes to Neo4j
COMMIT: ❌ ABSENT                REJECT: typed error if validation fails
REJECT: ❌ ABSENT
```

71% of production agent failures localize at the SDB. Here, 100% of failures were at the missing COMMIT step.

## Fix Strategy

1. Create dedicated agent files for all 4 observers
2. SDB contract in every agent file: PROPOSER → VERIFIER → COMMIT → REJECT
3. Toolsets: remove `file`, keep `terminal` (Neo4j-only persistence)
4. Checkpoint protocol: write to Neo4j immediately, not accumulate in context
5. Hook-based activation: plugin (TUI/CLI) + gateway hook (messaging)
6. Worker process: reads pending sessions, spawns 4 observer subagents

## Observer Files Created

| File | Path | Purpose |
|------|------|---------|
| Auditor agent | `~/.hermes/agents/auditor.md` | Process quality, context completeness |
| Critic agent | `~/.hermes/agents/critic.md` | Waste, over-engineering detection |
| Idea Generator agent | `~/.hermes/agents/idea-generator.md` | Unheard ideas, ADAS mutations |
| Knowledge Curator agent | `~/.hermes/agents/knowledge-curator.md` | Entity extraction, Neo4j graph maintenance |
| AFlow Orchestrator | `~/.hermes/agents/aflow-orchestrator.md` | MCTS workflow search (parallel) |
