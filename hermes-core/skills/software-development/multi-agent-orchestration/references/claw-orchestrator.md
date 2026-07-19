# Claw Graph Orchestrator

Minimal 5-phase maintenance orchestrator for the claw graph (Tool, Evidence, Session nodes in Neo4j). Unlike the codebase orchestrator (10 phases, 20 roles), claw is a **maintenance** cycle — it discovers existing infrastructure, detects compaction candidates, and proposes optimizations. It does NOT build new features.

## Key difference from codebase orchestrator

| Aspect | Codebase Orchestrator | Claw Orchestrator |
|--------|---------------------|-------------------|
| Domain | Building new systems | Maintaining existing infrastructure |
| Phases | 10 (Requirements → Audit) | 5 (Discover → Audit) |
| Roles | 20 | 3 (Claw + Auditor + Orchestrator) |
| Frequency | Event-driven (on demand) | Cron (daily) |
| Output | Code + tests + docs | Draft proposals + Neo4j updates |
| Human role | Approves requirements/architecture | Approves merge/prune proposals |

## 5 Phases

| # | Phase | Agent | What happens |
|---|-------|-------|-------------|
| 1 | Discover | Claw | 9 scanners → registry snapshot |
| 2 | Process | Classifier → Detector | 5 axes compaction detection |
| 3 | Draft+Log | Claw | Proposals + log.jsonl |
| 4 | Neo4j Sync | Claw | Graph update + CODED_IN links |
| 5 | Audit | Auditor | Metrics, health, escalation |

## YAGNI roles (for claw)

Requirements Analyst, System Analyst, Researcher, Architect, Tech Lead, Developer, Security Agent, Tester, Deployment Agent — ALL `YAGNI`. Claw doesn't build, it maintains.

## Integration with codebase graph

Both orchestrators share one Neo4j database. Claw fills `CODED_IN` links (Tool→CodeFile). Codebase reads them for impact analysis.

## Agent file

`~/.hermes/agents/claw-orchestrator.md` — full agent persona with entry/exit conditions, escalation paths, and cron setup.
