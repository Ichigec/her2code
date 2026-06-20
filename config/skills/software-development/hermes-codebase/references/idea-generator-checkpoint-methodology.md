# Idea Generator Checkpoint — Methodology per Phase

How to execute an Idea Generator checkpoint for each orchestration phase, with
phase-specific techniques that go beyond the general pattern in
`orchestrator-observer-checkpoints.md`.

## General Output Format (all phases)

Every Idea Generator checkpoint produces a report with these **four mandatory
sections**, regardless of phase:

1. **Неслышанные идеи / упущенные связи** — ideas the artifact missed,
   connections between components/systems it didn't draw
2. **Оптимизации пайплайна** — structural pipeline improvements (ordering,
   parallelism, reuse, deduplication)
3. **Связи (кого с кем связать)** — concrete cross-references the artifact
   omitted
4. **Источники (где взять недостающую информацию)** — files, APIs, docs the
   artifact should reference but doesn't

Phase-specific focus refines what each section looks for.

---

## Phase 2 (System Analysis) — Enhanced Methodology

**Toolsets:** `file_ro`, `search_files` (mandatory), plus `session_search` for
prior art.

### Step 1: Read the artifact in full
Read the entire Phase 2 artifact. Understand its SMART goal decomposition,
5 Whys, goal tree, alternatives matrix (WSM/AHP), developer tasks, and
architectural decisions.

### Step 2: Read all upstream documents
Read requirements (Phase 1), any research doc, structure.md, AGENTS.md.
Understand what the artifact inherits and what constraints it operates under.

### Step 3: Cross-reference architectural decisions against real code
**This is the critical Phase 2 step.** For every architectural decision (D1–D8
in a typical SysAnalysis artifact), verify the claim against the actual
implementation:

- If the artifact says «system provider — всегда активен», check
  `MemoryManager.add_provider()` for the `_has_external` guard. Does a bypass
  mechanism exist?
- If the artifact says «все 8 плагинов без изменений», count the actual plugin
  directories and verify their ABC compliance.
- If the artifact says «on_session_end триггер», check `run_agent.py` — is
  `on_session_end` already called? Where? With what arguments?
- If the artifact proposes a new manager/engine, check whether an existing
  system already does that work (e.g. `conversation_compression.py` already
  does LLM summarization with session lifecycle hooks).

**Key files to check for Phase 2:**
| Artifact claim area | Real code to verify |
|---------------------|---------------------|
| MemoryProvider ABC | `agent/memory_provider.py` |
| Provider registration | `agent/memory_manager.py` (add_provider, lifecycle hooks) |
| Session lifecycle | `run_agent.py` (finalize_session, commit_memory_session) |
| Existing compression | `agent/conversation_compression.py` |
| DB schema | `hermes_state.py` (_init_db, search_messages) |
| Tool schemas | `tools/session_search_tool.py` |
| Plugin discovery | `plugins/memory/__init__.py` |

### Step 4: Look for hidden connections
Every Phase 2 artifact lives in a system with:
- **Agent Improvement Pipeline** (Auditor) — does the artifact connect to it?
- **Neo4j knowledge graphs** — does it leverage graph recall?
- **Voice/audio pipeline** — do transcripts interact with the new feature?
- **Batch runner** — is there isolation from batch trajectories?
- **Gateway multi-platform** — does the feature work across CLI/Telegram/etc?

### Step 5: Identify missing sources
- Arxiv paper citations in the artifact — are they real? (Phase 3 should verify)
- Schema references — does the artifact cite the actual `_init_db()` code or
  just assume a schema from requirements?
- Upstream plugin docs — does the artifact reference
  `plugins/memory/__init__.py` discovery mechanism?
- Existing patterns in the codebase — does the artifact know about
  `conversation_compression.py` as prior art?

### Step 6: Pipeline optimizations
Look for:
- **Overconstraining** — sequential task order when tasks are independent
- **Duplication** — new module that duplicates existing capability
- **Bypass opportunities** — fast paths the artifact didn't consider
  (e.g. recent-tier skipping segment tree)
- **Guardrail conflicts** — artifact decisions that conflict with code
  invariants (e.g. _has_external blocking system providers)

---

## Phase 4 (Architecture) — Adapted Focus

For Architecture artifacts, the codebase-cross-referencing step shifts from
"verify SysAnalysis claims" to "verify module contracts exist in code":

- Do proposed interfaces match existing ABC method signatures?
- Are hook names already registered in the plugin system?
- Does the deployment model match actual profile/hermes_home resolution?

---

## Phase 5 (Plan) — Enhanced Methodology

Phase 5 is the **last quality gate before implementation**. Errors here become TDD
tasks that developers spend hours on. Be thorough.

### Step 1: Cross-phase recommendation tracking 🆕

**Every Phase 5 checkpoint MUST start by loading the previous Idea Generator checkpoint**
(Phase 4 report). Count how many Phase 4 critical recommendations were addressed
vs. silently dropped by the plan.

```
1. Read Phase 4 checkpoint report
2. Extract all P0/P1 recommendations (R1-R7 etc.)
3. Search the Phase 5 plan for matching task text
4. Produce: Recommendation | Addressed in Plan? | Evidence/Task#
5. Flag every DROPPED recommendation with its original priority
```

**Pitfall:** Plans routinely address the most visible gap from Phase 4 while
silently ignoring harder ones (integration with existing subsystems, thread
safety, feature flags). Dropped P0 items are the #1 source of unheard ideas
for Phase 5.

### Step 2: Phantom task detection 🆕

Plans say «modify `run_agent.py` if needed» or imply changes without explicit
tasks. **Phantom integrations** are files the plan assumes will be modified but
has no task for. They will never be connected.

**Common phantom victims:**
- `agent/agent_init.py` — loading system providers (plan adds `add_system_provider()` to MemoryManager but never calls it on startup)
- `tools/session_search_tool.py` — wrapping new API parameters (plan extends `search_messages()` but the tool wrapper remains unchanged)
- `cron/jobs.py` — registering cron jobs (plan describes `consolidate_daily()` but has no cron registration task)
- `run_agent.py` — where MemoryManager/ConsolidationManager are wired together (plan says «modify if needed»)

**Rule:** Any file mentioned in a task description but absent from the OWNERSHIP
table → flag as phantom.

### Step 3: Test stub spotting 🆕

Scan every RED section for `pass`, `...`, or empty method bodies. A task claiming
5 test methods with 3 marked `pass` has only 40% real coverage. Flag tasks where
>30% of test methods are stubs. These will pass trivially (empty test = green)
but provide zero protection.

### Step 4: Standard Phase 5 checks

- Task file paths — do they exist on disk?
- Test commands — are they runnable verbatim?
- File count — does 1 task = 1 file hold?
- Dependencies — can tasks actually execute in the claimed sequence?
- Speculative refactor items — items like «Bump SCHEMA_VERSION if version tracking exists» are not engineering plans; flag them

---

## Pitfalls

- **Don't stop at reading the artifact.** The artifact is a model's synthesis —
  it can be internally consistent but factually wrong about the codebase.
- **Don't trust arxiv IDs without verification.** Phase 2 artifacts often cite
  papers by ID; Phase 3 Research should validate them.
- **Don't assume 1:1 mapping between artifact "plugins" count and reality.**
  Count the actual directories.
- **Don't skip the `add_provider()` gate.** This is the single most common
  architectural decision that Phase 2 gets wrong — claiming a new provider won't
  conflict when the `_has_external` guard says it will.
