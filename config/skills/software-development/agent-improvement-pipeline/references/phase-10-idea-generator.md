# Phase 10 — Idea Generator: Methodology & Patterns

The Idea Generator is the final phase of the Agent Improvement Pipeline. Unlike the Auditor (which judges past performance), the Idea Generator is a **forward-looking creative synthesizer** that reads ALL artifacts across ALL phases and produces cross-cutting insights, unsynthesized connections, and prioritized improvement proposals.

## Trigger

- Phase 9 (Post-Deploy) completed
- Orchestrator (or user) invokes: «Idea Generator: финальный отчёт Phase 10»
- All phases 1–9 have produced artifacts in `docs/`

## Core Methodology (4-Axis Analysis)

### Axis 1: Неслышанные идеи (Unheard Ideas)
Identify gaps between design (Phases 2–4) and implementation (Phase 6 reality). Compare:
- Research findings → what was actually built
- Architecture specifications → what code implements
- Acceptance Criteria → test report verdicts
- Security recommendations → actual fixes applied

**Signals to look for:**
- Tool/technology specified in architecture but replaced with simpler alternative in implementation (e.g., tree-sitter → regex)
- Capabilities designed but not implemented (Level 2/3 missing, CALLS=0)
- Performance targets measured in research but missed in implementation
- Security findings unresolved from SAST report

### Axis 2: Связи (Connections)
Find unsynthesized connections between components that coexist but don't interact:
- Cross-graph connections (codebase ↔ claw ↔ education)
- Tool ↔ implementation file mappings (CODED_IN)
- Knowledge entity ↔ code function semantic links
- Session ↔ code file review trails
- Test coverage ↔ risk surface gaps

### Axis 3: Недостающая информация (Missing Information)
Identify measurement gaps — things that were estimated but never measured:
- Benchmarks projected but not run on actual implementation
- RRF quality not A/B tested on real codebase data
- MCP full-stack latency not measured (only Cypher-level)
- Documentation vs reality drift (KnowledgeEntity count: 55→3165→6905)

### Axis 4: Оптимизация пайплайна (Pipeline Optimization)
Find the critical path and propose concrete fixes with quantified impact:
- Bottleneck identification with before/after estimates
- Batch/parallelism opportunities
- Configuration fixes with exact commands
- Missing integration points (MCP registration, systemd units, cron jobs)

## Output Format

The report has 5 sections:

```markdown
# 🔮 Phase 10 — IDEA GENERATOR: Финальный отчёт

**Проект:** <project-id>
**Дата:** <today>
**Артефактов прочитано:** <count> docs + plan + sources + tests

## 1. 🦻 Какие идеи не были услышаны?
- Design→Implementation gaps with evidence from artifacts
- Each idea: what was promised → what was built → what to do

## 2. 🤝 Кого с кем связать?
- Cross-graph/tool connections with data tables (From | Link | To | How)
- Existing entities waiting for integration

## 3. 🔍 Где взять недостающую информацию?
- Unmeasured metrics with exact measurement commands
- Documentation drift discovered

## 4. ⚡ Как оптимизировать пайплайн?
- Before/after performance table for critical path
- Configuration fixes with exact YAML/code snippets

## 5. 💡 Creative Proposals
- 5–8 forward-looking ideas beyond current scope
- Each with concept, mechanism, and implementation sketch

## 📊 Сводная таблица приоритетов
- Prioritized table: #, Proposal, Category, Impact, Effort, Priority (P0–P3)
```

## Execution Pattern

```
1. Read ALL docs/ artifacts:
   - docs/requirements/<slug>.md
   - docs/system-analysis/<slug>.md
   - docs/research/<slug>.md
   - docs/architecture/<slug>.md
   - docs/security/sast-report.md (if exists)
   - docs/tests/<slug>.md (if exists)
   - docs/deployment/<slug>.md (if exists)

2. Read all source files in project directory
3. Read .hermes/plans/<ts>-<slug>.md (the plan)
4. Read structure.md and config files

5. Build a mental map of:
   - What was PROMISED (Requirements ACs)
   - What was DESIGNED (Architecture specs)
   - What was RESEARCHED (benchmarks, findings)
   - What was BUILT (test report actuals)
   - What was VERIFIED (security SAST)
   - What is MISSING (empty docs directories, zero-count nodes/edges)

6. For each gap, formulate a concrete, actionable proposal
7. For each proposal, estimate impact and effort
8. Prioritize: P0 (blocking), P1 (high leverage), P2 (valuable), P3 (future vision)
```

## Key Pattern: Design↔Implementation Gap Detection

This is the most valuable Idea Generator function. The technique:

1. Extract specification from Architecture doc (e.g., "tree-sitter parser, batch_size=32, <30s")
2. Find implementation reality from Test Report (e.g., "regex parser, 94.5s, 0 CALLS edges")
3. Identify root cause: not "performance problem" but "tool substitution"
4. Propose fix: "replace regex with tree-sitter (already benchmarked at <2s, already in dependencies)"

**Common gap types:**
| Design says | Implementation did | Root cause | Fix |
|---|---|---|---|
| tree-sitter AST parser | regex line parser | Faster to prototype, never replaced | Swap parser, already in deps |
| Batch MERGE (50 files/txn) | Per-file MERGE | Simpler to implement first | Group transactions |
| MCP server registered in config | .mjs file exists but unregistered | Deployment phase missed | Add config entry |
| CODED_IN edges populated | 0 edges created | Dev #4 never got to it | Run matching script |
| `.venv` in exclude_patterns | `.venv` not excluded | Segment vs exact match bug | Fix path check logic |

## Pitfalls

- **Do NOT treat the Idea Generator as an Auditor.** The Auditor judges past performance. The Idea Generator synthesizes forward-looking proposals. Confusing the two produces a blame report, not a creative synthesis.
- **Read ALL artifacts before writing.** The value is in cross-phase synthesis. Reading only the test report or only the architecture doc misses the gaps.
- **Quantify proposals.** "Make it faster" is not actionable. "Replace regex with tree-sitter → 94.5s → 25s (3.8×)" is.
- **Include exact commands for fixes.** Every P0/P1 proposal should have a copy-pasteable fix.
- **The Creative Proposals section is not optional.** This is the unique value of the Idea Generator over the Auditor — future-looking imagination, not backward-looking judgment.
