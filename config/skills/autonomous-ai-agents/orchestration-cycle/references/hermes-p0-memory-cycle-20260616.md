# P0 Memory Scaffolding — Full Cycle Case Study (2026-06-16)

> Condensed lessons from `hermes-p0-memory_20260615_232649`: a complete 10-phase
> orchestration cycle implementing temporal retrieval + consolidation pipeline.

## Project Stats

| Metric | Value |
|--------|-------|
| Phases | 0–10 (all) |
| Production files | 7 (~1,900 LOC) |
| Test files | 7 (323 tests) |
| Documentation | ~4,000 lines markdown (9 artifacts) |
| Duration | ~1 session (2026-06-15 evening) |
| ACs met | 6/6 |
| NFRs met | 5/8 (1 failed, 2 deferred) |
| Key metric | NFR1: 252ms < 500ms ✅ |

## Artifacts Created

| Phase | File | Lines |
|-------|------|-------|
| 1 | `docs/requirements/hermes-p0-memory.md` | 282 |
| 2 | `docs/system-analysis/hermes-p0-memory.md` | 537 |
| 3 | `docs/research/hermes-p0-memory-codebase-audit.md` + `memory-scaffolding.md` | 391+348 |
| 4 | `docs/architecture/hermes-p0-memory.md` | 1330 |
| 5 | `.hermes/plans/2026-06-15-hermes-p0-memory.md` | 1986 |
| 7 | `docs/security/hermes-p0-memory.md` | 340 |
| 8 | `docs/deployment/hermes-p0-memory.md` | ~200 |
| 8.5 | `docs/tests/hermes-p0-memory.md` | 500 |
| 9 | `docs/research-post/hermes-p0-memory.md` | 457 |

## Production Code (7 files)

| File | Purpose |
|------|---------|
| `agent/memory_provider.py` | +`prefetch_temporal()`, +`consolidate()`, +`is_system_provider` |
| `plugins/memory/segtree/__init__.py` | SegTreeMem system provider (323 lines) |
| `plugins/memory/segtree/segment_tree.py` | In-memory binary segment tree (193 lines) |
| `plugins/memory/segtree/temporal_scorer.py` | TF-IDF × exponential time decay (157 lines) |
| `agent/consolidation_manager.py` | TiMem 4-tier consolidation pipeline (535 lines) |
| `agent/memory_manager.py` | +`add_system_provider()`, +`prefetch_temporal_all()`, +`on_session_end` consolidation trigger |
| `hermes_state.py` | +`memory_consolidations` table, +`after_ts`/`before_ts` in `search_messages()` |

## Key Pitfalls Discovered

### 1. Methodology-driven over-engineering (2:1 doc-to-code ratio)

Agents fill ALL template sections mandated by AGENTS.md even when there's nothing
meaningful to say. Result: AHP matrices for obvious choices, C4 Level 1 diagrams
showing 4 boxes for 7 files, deployment health checks for undeployed features.

**Lesson:** Instruct agents to skip redundant sections. WSM sufficient when gap >3 points.
One C4 diagram enough for <10 modules.

### 2. LLM-dependency trap

ConsolidationManager was fully built (535 lines, HMAC, atomic transactions) but always
returns placeholders because `MemoryManager._call_consolidation_llm` hook doesn't exist.
HMAC protects strings containing "(No LLM available)".

**Lesson:** When any design depends on an external integration point, the Plan MUST
include a task to verify that integration point EXISTS before building dependent features.

### 3. NFRs that can't be measured become noise

NFR2 (10K→daily <5s) and NFR6 (compression ≤10%) were declared but deferred because
they can't be measured without a live LLM. Status: "design-verified" — a euphemism for
"we can't test this."

**Lesson:** Only declare NFRs that CAN BE MEASURED with available tools.

### 4. Phase 9 is NOT optional

Post-deploy research was initially skipped. When finally run, it discovered that
consolidation was never triggered in production (0 entries in `memory_consolidations`).
This finding came too late — the project was already marked "complete."

**Lesson:** Phase 9 MUST run before Phase 10. It's the reality check.

### 5. Codebase audit as critical research phase

The Researcher conducted a codebase audit with 5 RQs (file:line references) and
discovered that `is_system_provider` did not exist in the codebase. Without this
finding, SegTreeMem would have conflicted with external providers.

**Lesson:** For features extending existing subsystems, always include a codebase
audit RQ: "What is the ACTUAL state of the target files?"

## Observer Chain

All 4 observer checkpoints ran: Auditor (delegation quality, coverage gaps), Critic
(over-engineering detection, 42% of architecture doc flagged), Idea Generator
(missed connections, pipeline optimizations), Knowledge Curator (Neo4j ingestion).

Critic's veredict: **7/10 over-engineering** — methodology-driven bloat, LLM-dependency
trap, NFRs that can't be measured, segment tree reinventing SQLite B-tree.

## Success Patterns

1. **Phase 6.5 Verification Gate** — System Analyst caught NFR7 before deployment
2. **Autonomous Tester** — 847 memory tests, zero user intervention, real terminal output
3. **System provider bypass** — `add_system_provider()` pattern cleanly separated from
   external provider limit
4. **Default no-op backward compatibility** — all 8 existing plugins untouched (AC-6)
5. **Evidence-based NFR measurement** — NFR1 measured 3× with `time python3 -c "..."`
