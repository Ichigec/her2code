# Idea Generator — Checklist & Methodology

> Role #12 in the 13-agent orchestration topology. Spawned at every quality gate
> (Phases 1, 2, 4, 5, 6, 8, 8.5). Finds unheard ideas, missing connections,
> information gaps, and pipeline optimizations.

## 4-Question Framework

Every Idea Generator checkpoint answers exactly these 4 questions:

### Q1: Какие идеи не услышаны? (Unheard Ideas)

Look for what the phase artifact **didn't** consider. Signal types:

| Signal | What to look for | Example |
|--------|------------------|---------|
| **Architecture-code gap** | Doc prescribes API that doesn't exist in actual source | `add_system_provider()` in architecture — but `MemoryManager` has no such method |
| **Edge case omission** | Happy-path only; no failure/empty/null handling | Consolidation only on `session_end` — but what about 3-day active sessions? |
| **Missing integration** | Component described in isolation, not connected to existing subsystems | No retrieval path from `memory_consolidations` table |
| **Degraded path** | Assumes full deployment; no feature flag / A/B / canary | No `memory.segtree.enabled: false` config |
| **Silent write-only** | Data is stored but never read back by any path | Consolidation writes summaries — no agent path to read them |
| **Scale assumption** | Works for N=10, fails at N=100K | "Rebuild tree on every start" — 200ms × frequent restarts |
| **Staleness** | Data structure that freezes at init, never refreshed | TF-IDF vocabulary frozen at `initialize()`, new terms invisible |
| **Phantom integration** | Plan implies file X must change but has no task for it | «modify `run_agent.py` if needed» — no ownership, no task |
| **Cross-phase drift** | Phase N-1 critical recommendation silently dropped in Phase N | Phase 4 P0: «integrate with ContextCompressor» → Phase 5: zero mentions |
| **Test stub masquerade** | RED section has `pass`/`...` bodies claiming coverage | 5 test methods, 3 are stubs → 40% real coverage |
| **Speculative refactor** | REFACTOR item is a conditional, not an engineering decision | «Bump SCHEMA_VERSION if version tracking exists» |
| **Dual-writer conflict** | Two components write to same table with different transaction logic | SegTreeMem.consolidate() + ConsolidationManager both INSERT into memory_consolidations |

**Method:** Read the artifact → find the actual source code it references → diff.
The gap between "what the doc says exists" and "what the filesystem actually has"
is the most reliable source of unheard ideas.

### Q2: Кого с кем связать? (Missing Connections)

Find entities that exist in the ecosystem but are NOT linked in the phase artifact.

Category mapping:

| Entity type | Where to find | What to connect to |
|-------------|---------------|-------------------|
| **Prior research artifacts** | Other project dirs in `~/dev/codemes/` | Link research findings → architectural decisions |
| **Knowledge Graph** | Neo4j (`:7474`), `MATCH (ke:KnowledgeEntity) RETURN ke.name` | Verify concepts exist in graph; add missing edges |
| **Actual source code** | `~/.hermes/hermes-agent/` | Map architecture module names → real file paths + line numbers |
| **Existing Hermes subsystems** | `cron/`, `skills/`, `plugins/`, `gateway/` | Show how new components integrate with existing ones |
| **Cross-cycle infrastructure** | `auditor_memory.md`, `audit.db`, `state.db` | Connect new data to existing audit/observation pipelines |
| **AGENTS.md conventions** | `~/dev/codemes/{pid}/AGENTS.md` | Verify architecture doesn't violate project conventions |

**Output format:** Table with columns: What exists | Not connected in artifact | How to connect.

### Q3: Где взять недостающую информацию? (Information Sources)

Identify specific files, APIs, or databases that contain answers to open questions.
Be **precise** — file path + line range, not "somewhere in the codebase."

| Gap | Source | What you'll learn |
|-----|--------|-------------------|
| How existing API works | `path/to/file.py:start-end` | Exact method signature, current behavior |
| Cron scheduler capabilities | `~/.hermes/hermes-agent/cron/` | Format for cron commands |
| Plugin registration pattern | `plugins/memory/*/__init__.py` | How providers register themselves |
| DB schema | `hermes_state.py` → `_init_db()` | Current SCHEMA_VERSION, existing indexes |

**Rule:** Never say "the docs" or "the codebase" — give exact paths. A future agent
with only `read_file` and `search_files` must be able to find the answer.

### Q4: Как оптимизировать пайплайн? (Pipeline Optimizations)

Find concrete performance/throughput/cost improvements.

Categories:

| Category | What to look for | Example |
|----------|-----------------|---------|
| **Merge redundant calls** | Two prefetch calls per turn → one combined call | -50% latency |
| **Cache across restarts** | Rebuild on every init → mmap/pickle cache | 200ms → 10ms |
| **Incremental update** | Full rebuild → delta on `sync_turn()` | Vocabulary stays fresh |
| **Tiered validation** | One pytest run → smoke → integration → perf | Early fail < 10s |
| **Lazy/deferred work** | Eager on `session_end` → queue, process at idle | No blocking |
| **Early cutoff** | Score all candidates → drop `time_decay < 0.1` first | Skip 70% TF-IDF work |
| **Batch writes** | Separate INSERTs → single `executemany()` | 3× faster consolidation |
| **Intent gate** | Always prefetch → skip when no temporal intent | -200ms on 80% queries |

**Filter:** Only list optimizations that save **measurable** resources (time, tokens, RAM).
Don't suggest refactors for "cleanliness" unless they have a concrete cost.

## Codebase-Audit Methodology

The most powerful Idea Generator technique is **comparing architecture proposals
against actual source code**. This catches fabricated APIs, missing methods, and
wrong assumptions before Phase 5 (Plan) bakes them into TDD tasks.

### Audit workflow

```
1. Read architecture doc completely (offset pagination for large files)
2. For each module contract (§Module Contracts):
   a. Find the real source file (resolve ~/.hermes paths to actual files)
   b. search_files(target='content') for the proposed method/class names
   c. read_file the actual implementation
   d. Diff: what the architecture says vs what the code has
3. For each proposed NEW component:
   a. Verify the parent module exists (e.g., does `agent/` directory exist?)
   b. Check if similar patterns exist (e.g., other plugins for registration)
   c. Flag anything that claims "extends existing" but requires new infrastructure
```

### Red flags (architecture lies)

| Claim in architecture | What to verify | Real example |
|----------------------|----------------|-------------|
| "extends existing" | Does the method exist in the current file? | `add_system_provider()` — NO, `MemoryManager` has only `add_provider()` |
| "uses existing model providers" | Is the LLM-calling API accessible from the proposed location? | ConsolidationManager needs access to `model.provider` config |
| "zero code changes for existing plugins" | Do default no-ops in ABC actually compile? | `prefetch_temporal()` default delegates to `prefetch()` |
| "automatic on agent start" | Is the init path actually called? | DB migration in `_init_db()` — verify it runs before first query |
| "background daemon thread" | Does the process survive agent shutdown? | Consolidation daemon thread vs `atexit` handlers |

### What to do with findings

- **Fabricated API** → flag as P0 blocker for Phase 5 (Plan cannot task against nonexistent code)
- **Missing integration path** → suggest concrete addition (e.g., "add retrieval from `memory_consolidations` to `SegTreeMem.prefetch_temporal()`")
- **Wrong assumption** → correct in architecture before Phase 5

## Output Format

Use consistent emoji-section headers and numbered items with **bold captions**:

```markdown
## 🧠 Idea Generator Checkpoint #N — Phase X [Artifact Name]

**Project:** `{pid}`
**Artifact:** `docs/{phase}/{slug}.md` (N lines, N diagrams)
**Codebase audit:** `path/to/real/file.py` (N lines) — [read fully / partially]

---

## 1. Неслышанные идеи 🔕

| # | Идея | Почему не услышана | Где в архитектуре |
|---|------|-------------------|-------------------|
| **I1** | **One-line title** | Why it matters, evidence from code | §section — contract reference |

## 2. Пропущенные связи 🔗

| Что есть | Что НЕ связано в архитектуре | Как связать |
|----------|------------------------------|-------------|
| **Entity name** (source) | Description of gap | Concrete fix |

## 3. Где взять недостающую информацию 📍

| Чего не хватает | Конкретный источник | Что узнаем |
|-----------------|---------------------|------------|
| Gap description | `file:line-range` | Expected learning |

## 4. Оптимизации пайплайна ⚡

| # | Оптимизация | Эффект | Где применить |
|---|-------------|--------|---------------|
| **O1** | **Technique** | Measurable gain | §section — exact location |

---

## Итоговая оценка

**Сильные стороны:** (3-5 bullets)
**Критические пробелы:** (numbered, most important first)
**Главная рекомендация:** (one sentence)
```

## Pitfalls

### Observer not persistent → checkpoint files as workaround

`delegate_task` is synchronous and stateless — sub-agents cannot "live through the
whole cycle." The architecture says "persistent observers" but the runtime can't
support it. **Fix:** Observer Checkpoint Protocol — spawn fresh observer at each
quality gate, pass previous checkpoint as context, append to `.observations/checkpoint-{N}.md`.

### Batch delegation fails with certain models

Kimi K2.7 batch `delegate_task` → ALL children `INTERRUPTED`. **Fix:** Use
DeepSeek V4 Pro for observer spawning. Single-task `delegate_task` may work
with Kimi for leaf subagents.

### Sub-agent fabrication of codebase-audit results

When delegating the codebase audit to a sub-agent, it may claim `add_system_provider()`
exists when it doesn't. **Fix:** Orchestrator verifies with `search_files(target='content')`
for the claimed method name in the actual source file. Trust only your own `read_file`.

## Session History

- **2026-06-15 — hermes-p0-memory Phase 4:** First application of full 4-question
  checklist + codebase-audit methodology. Found 12 unheard ideas (including
  `add_system_provider()` fabrication), 8 missing connections, 8 info sources,
  12 pipeline optimizations.
- **2026-06-15 — hermes-p0-memory Phase 5:** Checkpoint with enhanced Phase 5
  methodology: cross-phase recommendation tracking (6 of 7 Phase 4 critical gaps
  still unaddressed), phantom task detection (3 missing tasks: agent_init.py,
  session_search_tool.py, cron registration), test stub spotting. Found 15 unheard
  ideas including ConsolidationManager↔ContextCompressor collision, FTS5 gap on
  memory_consolidations, thread safety, vocabulary staleness, consolidation-as-data-loss,
  prompt injection vector, and feature flag absence.
