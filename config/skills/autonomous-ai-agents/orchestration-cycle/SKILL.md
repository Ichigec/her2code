---
name: orchestration-cycle
description: "Force full orchestration lifecycle on /agent plan activation. Preload to guarantee Phase 1→10 auto-start."
version: 2.4.0
author: Hermes Agent + User
license: MIT
metadata:
  hermes:
    tags: [orchestration, multi-agent, plan, auto-cycle, lifecycle, tester, auditor]
    related_skills: [multi-agent-orchestration]
---

# Orchestration Cycle — Full Lifecycle Enforcer

Load this skill alongside the `plan` agent to **guarantee** the full
orchestration lifecycle runs automatically on every activation.

**v2.2 adds 4th observer (Knowledge Curator #13), Quadruple report, Researcher routing, and Developer temperature differentiation.** v2.1 added Research-first variant and separate-file rule.

**v2.3 (2026-06-15) switches default to DeepSeek V4 Pro for ALL roles — management, code, review, testing. Kimi K2.7 was removed as default due to delegation failures (observer spawning with Kimi → interrupted). DeepSeek V4 Pro demonstrated successful Auditor and Critic runs (direct delegation, 120s+ duration, quality reports).**

**v2.4 (2026-06-16) adds methodology-driven over-engineering mitigation, LLM-dependency trap detection, NFR measurability gate, Phase 9 mandatory enforcement, and codebase audit as research phase pattern. Lessons from full hermes-p0-memory cycle (10 phases, 7 files, 323 tests, 6/6 AC).**

Previous addition: v1.8 active error-ledger/backlog protocol for multi-phase runtime work — record defects first, continue safely, and keep summary/detail sections synchronized.

## When to use

- Preload with `hermes -s orchestration-cycle` before `/agent plan`
- Load mid-session: `/skill orchestration-cycle` then `/agent plan`
- Set as a pinned skill for the orchestrator profile

## Agent persistence (KEY DISCOVERY)

**One `/agent plan` = entire session under orchestrator.** `apply_agent()`
sets `ephemeral_system_prompt` on the `AIAgent` object — it persists across
ALL turns until you switch agents again. No need to re-type `/agent plan`
every message. No `/reset` needed after agent file changes (agents are read
from disk on activation).

**Runtime boundary:** this is prompt-driven orchestration, not a hardcoded workflow runner. `/agent plan` applies the `plan.md` preset to the live parent agent. `delegate_task` creates isolated children, but currently does not accept `agent_id`; pass subagent role/persona explicitly in `goal`/`context` plus `toolsets`/`model`/`provider`. See `multi-agent-orchestration` → `references/agent-runtime-contract.md`.

```
Turn 1: /agent plan          → plan.md loaded as ephemeral_system_prompt
Turn 2: «Создай API»         → plan.md STILL active
Turn 3: «Добавь фичу»        → plan.md STILL active
Turn N: /agent general        → switches back to general
```

To verify: after `/agent plan`, the status bar shows the agent emoji and label.

## Toolsets pitfall (v1.2)

**`toolsets: []` in agent frontmatter = ALL tools, not "none".**

Python: `agent_def.toolsets or None` — empty list `[]` is falsy → becomes
`None` (all tools enabled). The orchestrator prompt says «your tools:
delegate_task, todo, clarify, read_file, search_files» but the agent
actually has 25+ tools available. This creates dangerous confusion — the
model may try to use tools it wasn't instructed about, or worse, start
writing code directly instead of delegating.

**Fix:** Always use an explicit list:
```yaml
toolsets: [delegation, todo, file, session_search, skills, clarify]
```

## Model selection for orchestrator (v2.3)

The orchestrator is a **manager**, not a coder. Model choice matters.

### The model field trap

**`plan.md` has no `model:` field** → inherits `agent.default` from config.yaml.
If that's `deepseek-v4-pro`, the orchestrator runs on DeepSeek V4 Pro.

**Fix:** Always add to plan.md frontmatter:
```yaml
model: deepseek-v4-pro
provider: deepseek
```

Without this field, `/agent plan` uses whatever `hermes config` default is — which
may be a model not suited for long-context orchestration.

### Verified model comparisons

| Model | Fit | Verified fact | Source |
|-------|:---:|---------------|--------|
| **DeepSeek V4 Pro** | 🟢 Default | 1M context, cheap. Proven in: Auditor 120s+ deep analysis, Critic 71s artifact review, Researcher 705s deep search (8 iterations, 61 API calls). Default for ALL roles. $0.28/1M in — cheapest of all. | 2026-06-15 direct test (this session) |
| **Kimi K2.7** | 🟡 Fallback | 262K context. $0.60/1M in. Observer spawning with Kimi via batch delegation → INTERRUPTED (parent timed out). Still good for leaf subagents. | 2026-06-15 delegation failure |
| **Qwen 3.6 35B (thinking)** | 🟡 Free | Free, unlimited, 262K context. TOO SLOW on Jetson CPU for orchestrator (5+ min/turn). | Local test |
| ~~GPT-5.5~~ | ❌ REMOVED | Quota exceeded. $10/1M output. Removed 2026-06-15 per quota exhaustion. | — |
| ~~GPT-4.1-mini~~ | ❌ EXCLUDED | Removed per user direction 2026-06-15. | — |

### ⚠️ MoE hallucination pitfall (v1.3)

**Qwen 3.5 122B-A10B Q4_K_M (71 GB) hallucinates at 32K tokens.** User tested this.
The model looks great on paper (IFEval 93.4%, 122B total params) but the Q4
quantization degrades long-context coherence. MoE models route tokens through
different experts — at low quants, expert routing noise compounds over 32K+ tokens.

**Do NOT use Qwen 122B Q4 for orchestration.** It might work at Q5 (85 GB) or
Q6 (101 GB) but those barely fit in 128 GB and are untested.

For detailed model data (exact GGUF sizes from HuggingFace, architecture notes,
DGX Spark memory budget), see `references/model-selection-guide.md`.

### Recommended setup

```yaml
# plan.md frontmatter
model: deepseek-v4-pro
provider: deepseek

# config.yaml — delegation default for sub-agents
delegation:
  model: deepseek-v4-pro
  provider: deepseek
```

**⚠️ DeepSeek V4 Pro is default for ALL roles** since 2026-06-15: management, code, review, testing. Kimi K2.7 is fallback for leaf subagents only — batch delegation with Kimi was observed to cause INTERRUPTED children (parent timed out).

## Auto-cycle rules

When the orchestrator (plan agent) is activated with this skill loaded:

1. **Phase 0 FIRST** — create `/home/user/dev/codemes/{pid}/`, copy AGENTS.md, generate structure.md
2. **The user's message IS the task input** — immediately begin Phase 1 after Phase 0
3. **Full cycle only** — all 10+1 phases, no shortcuts
4. **Observer Checkpoint Protocol (v2.2)** — spawn Auditor #10, Critic #11, Idea Generator #12, and Knowledge Curator #13 at EVERY quality gate (phases 1, 2, 4, 5, 6, 8, 8.5), not just Phase 1 and Phase 10. Each observer reads previous checkpoint + new artifacts → appends to `.observations/checkpoint-{N}.md`. Knowledge Curator extracts entities from every artifact into Neo4j Knowledge Graph, building cross-cycle connections. See `multi-agent-orchestration` skill §Observer Persistence.
5. **Todo tracking** — use the `todo` tool with all 11 phases as items, marking each complete as you go
6. **Inject isolation paths** — every `delegate_task` context includes:
   `Project ID: {pid}`, `Structure: /home/user/dev/codemes/{pid}/structure.md`
7. **Phase artifacts are SEPARATE files** — each phase produces its own artifact (e.g. `docs/requirements/<slug>.md`, `docs/system-analysis/<slug>.md`). Never merge multiple phases into one file. The user rejected combined artifacts («не надо экономить — запусти полный цикл»). One phase = one file = one delegate_task.

### Research-first variant (v2.1)

When the user says «сначала deep research», «поменяй фазы местами», «research first», «сначала анализ — потом требования», or any phrase indicating they want research before scoping:

1. **Swap Phase 3 before Phase 1.** Run Research (Phase 3) immediately after Phase 0.
2. **Inject research findings into Requirements.** When spawning Phase 1, pass the completed research artifact path + key findings summary in the context field.
3. **Order becomes: 0 → 3 → 1 → 2 → 4 → 5 → 6 → 6.5 → 7 → 8 → 8.5 → 9 → 10.**
4. **Rationale:** Valid when the domain is unfamiliar — research-first prevents requirements from being written in ignorance. User prefers deep analysis before scoping.
5. **Do NOT apply unless explicitly requested.** Default is requirements-first (0 → 1 → 2 → 3 → ...). The user's phrase must clearly indicate reordering intent.

## Exception protocol

Only pause the cycle if:
- The user says "interactive", "manual", "step by step", "стоп"
- A sub-agent returns a question that MUST be answered by the user
- A quality gate fails and escalation paths are exhausted
- **Batch delegation fails** — if 3+ tasks in a batch return "interrupted", re-launch individually on verified models (v1.7)
- **Provider/model delegation is blocked or unproven** — before launching model-routed observer/developer batches, run a delegation capability preflight (schema inspection + one-child smoke) as described in `multi-agent-orchestration` → `references/delegation-capability-preflight.md`. If blocked but user explicitly ordered continuation, enter degraded orchestration mode: write a `.observations/` deviation note, keep phase artifacts separated, replace missing subagent review with real pytest/SAST/acceptance evidence, and state DEGRADED in Phase 10. Full protocol lives in `multi-agent-orchestration` → `references/degraded-orchestration-mode.md`.

## Depth mode selection

Auto-detect from the user's message:
- Short/simple task (bug fix, one file) → **speed** mode (1 dev, skip research, smoke test only)
- Medium feature → **balanced** mode (3 devs, 6 research iterations, smoke + acceptance tests) [DEFAULT]
- Large system design → **quality** mode (7 devs, 25 research iterations, full test suite)

If unsure, ask a single clarifying question: "speed / balanced / quality?"

## Error ledger / backlog protocol (v1.8)

For long orchestration sessions, especially when a user says «зафиксируем ошибки и продолжим», create or update a **canonical error ledger** before continuing implementation.

Recommended artifact:

```text
docs/backlog/known-issues-<slug>.md
```

Each issue should have a stable ID and both a compact summary row and a detailed section:

```markdown
| ID | Severity | Status | Area | Symptom | Next action |
|----|---------:|--------|------|---------|-------------|
| MAR-ERR-009 | S3 | OPEN | Runtime Observability | Missing QualityGateRunner | Implement RuntimeEvent + gate runner |

### MAR-ERR-009 — Missing QualityGateRunner
- **Severity:** S3
- **Status:** OPEN
- **Evidence:** file/path.md:line-range or command output
- **Root cause / hypothesis:** ...
- **Fix plan:** ...
- **Acceptance test:** ...
```

Rules:

1. **Record first, then continue.** Do not hold all discovered defects in chat context; write them to `docs/backlog/` so later agents and compressed sessions can recover them.
2. **Separate blocker vs deferred debt.** Use statuses like `OPEN`, `DEFERRED`, `RESOLVED`, `ACCEPTED`. OPEN issues only block the target slice if they affect that slice.
3. **Keep summary and details synchronized.** When resolving an issue, update both the table row and the detailed section, including evidence (`pytest`, `py_compile`, SAST, etc.).
4. **After context compression, trust disk over stale todos.** Re-read the ledger, relevant files, and run/inspect a real verification before continuing. If the preserved todo says an old slice is still in progress but ledger/tests show it is done, close the todo and move to the next slice.
5. **Use the ledger as next-slice input.** Add a bottom section that says what to do next and what not to mix into the slice. Example: `Provider/plugin integration must not be mixed with env/pip maintenance`.
6. **Do not bury environment mutation in feature work.** Env changes (`pip`, provider config, git initialization, credentials) need explicit side-effect boundaries and, when user policy requires it, explicit user approval.

This protocol turns Phase 10/Auditor findings into executable backlog, rather than losing them during compression or mixing unrelated debt into the next implementation slice.

## VCS baseline + canonical plan preflight (v1.9)

For long-running orchestration projects, especially after context compaction or when resuming from an error ledger, run a **VCS/plan readiness gate** before starting the next slice. This prevents two recurring failures: working without rollback/diff review, and continuing from chat/todos when the canonical disk plan is missing or stale.

Recommended artifact/module shape:

```text
.hermes/plans/<timestamp>-<slug>.md       # canonical plan
src/<runtime>/orchestrator/vcs_plan_preflight.py
 tests/test_vcs_plan_preflight.py
```

The preflight should classify readiness:

| Status | Meaning | Action |
|--------|---------|--------|
| `READY` | Git works, working tree/diff can be inspected, canonical plan exists and has required sections | Continue implementation slice |
| `DEGRADED` | Git exists but plan is missing/incomplete, or plan exists but git is unavailable | Create/repair the missing baseline/plan before feature work |
| `BLOCKED` | Neither git nor canonical plan is available | Stop feature work; establish baseline first |

Minimum canonical plan sections:

```markdown
## OWNERSHIP
## Bite-sized TDD Tasks
## Principles Checklist
## Verification Commands
```

TDD pattern:

1. RED: test `no git + no plan => BLOCKED`, `git + no plan => DEGRADED`, `git + valid plan => READY`.
2. GREEN: implement the smallest `VcsPlanPreflight`/`CanonicalPlanReport` that shells out to `git status --short` and `git diff --stat`, locates `.hermes/plans/*.md`, and validates required sections.
3. VERIFY: run targeted pytest, full regression, then record the exact output in `docs/tests/<slice>.md`.
4. BASELINE: if this is the first safe point, make a local baseline commit only inside the project root after user/standing policy allows repository mutation.
5. LEDGER: mark the corresponding issue IDs resolved in both the summary table and detail sections.

Rules:

- Disk evidence beats preserved todos after context compaction. Re-read/verify the repo state before closing or reopening a slice.
- Do not mix VCS/plan repair with provider/plugin/env work. Baseline first, feature slice second.
- Treat git initialization, commits, provider config, dependency installs, and credential changes as explicit side-effect boundaries; follow the user's permission policy for the session.
- A clean baseline is not success by itself: success requires `pytest`, preflight `READY`, and a clean `git status`/known commit hash.

See `references/vcs-plan-baseline-preflight.md` for a compact case study and acceptance checklist.

## Tester (#8) — autonomous acceptance testing (Phase 8.5)

After deployment, the Tester verifies the system against ALL requirement sources:
1. Requirements doc (`docs/requirements/<slug>.md`)
2. System Analysis doc (`docs/system-analysis/<slug>.md`)
3. User acceptance criteria

**Critical rule:** Tester tests autonomously — NEVER tells user «проверь сам».
Uses `terminal` (curl, adb, ping), `browser`, `read_file` (logs, configs).
Produces `docs/tests/<slug>.md` with traceability matrix.

Test failures → System Analyst (#2) decides: fix (→ Phase 6) or accept deviation.

## Orchestrator = manager (v1.1)

The orchestrator is NOT just a conductor — it's accountable for team output.
At every quality gate, run 7 cross-phase checks. See
`references/managerial-oversight-checklist.md` for the full table.

| Check | Red flag |
|-------|----------|
| Requirement propagation | «User wanted tests» — but `docs/tests/` doesn't have them |
| Root cause resolution | Fixed symptom, root cause remains |
| Goal tree completion | Sub-goal has no implementation or test |
| Context completeness | Agent asks about something already in Requirements doc |
| Agent accountability | Artifact empty, or agent claimed «done» without evidence |
| Tester autonomy | Test report contains «проверь сам» or uses `clarify` |
| Reality check | «Server running» but `curl` returns nothing |

**Red flag → don't pass the gate.** Return agent: «Requirement X from [source]
is missing in your output. Re-do.»

## v1.6 — All 10 improvements complete (2026-06-13)

The full 10-point code agent improvement framework has been implemented across
3 sessions. Design docs live in `/home/user/dev/global_changes/`. When creating
new orchestrator profiles or auditing existing ones, verify ALL 10 are present.

| # | Improvement | Design doc | Session | Status |
|---|------------|-----------|---------|:------:|
| 1 | **AGENTS.md migration** | `hermes-md-migration.md` | `20260613_201921` | ✅ |
| 2 | **Repository Map + Project Isolation (Phase 0)** | `repository.md` | Current | ✅ |
| 3 | **Edit→Lint→Test cycle** | `edit-lint-test-cycle.md` | Current | ✅ |
| 4 | **Git safety net** | `git-safety-net.md` | `20260613_201921` | ✅ |
| 5 | **Self-correction 3 attempts** | `self-correction-loops.md` | Current | ✅ |
| 6 | **Reality check** | `orchestrator-reality-check.md` | Current | ✅ |
| 7 | **Architect/Editor contracts** | `architect-editor-contracts.md` | Current | ✅ |
| 8 | **Artifact validation** | `artifact-validation.md` | Current | ✅ |
| 9 | **READ/WRITE-ONLY split** | `stateless-stateful-separation.md` | Current | ✅ |
| 10 | **Curated skills catalog** | `curated-skills.md` | Current | ✅ |

### #1 AGENTS.md — single source of truth for project conventions

`~/.hermes/AGENTS.md` is the ONE file for project-level knowledge: build commands,
code conventions, environment facts, pitfalls, documentation conventions, lifecycle,
testing conventions, security gate, architecture patterns.

Orchestrator loads it at Phase 0. Auditor auto-applies safe changes (pitfalls ≥2 cycles,
environment facts, verified build commands). Agent files now contain ONLY role-specific
instructions — no more duplication across 10+ files.

Backup at `~/.hermes/agents.backup-20260613_210841/`.

### #2 Repository Map — Phase 0 Project Bootstrap

Orchestrator now creates `/home/user/dev/codemes/{pid}/` before Phase 1:
- `AGENTS.md` — copied from `~/.hermes/AGENTS.md`
- `structure.md` — auto-generated tree + symbols + stats

All sub-agents receive isolation paths in context and MUST read `structure.md`
before any file operation. Developers work in isolated worktrees under
`/home/user/dev/codemes/{pid}/worktrees/{my_id}/`.

### #4 Git safety net

Developer creates snapshot before first edit: `git stash` → work → `git diff --stat`.
Never commits — Tech Lead merges and commits. Rollback: `git checkout -- .` + `git stash pop`. Tech Lead merges from worktrees after Phase 6.

The following agent file patches were applied to increase orchestrator and developer
reliability. When creating new orchestrator profiles, verify these are present.

| # | Improvement | Files changed | Source |
|---|------------|---------------|--------|
| 3 | **Edit→Lint→Test cycle** | `developer-agent.md` §1 | Aider, SWE-Agent |
| 5 | **Self-correction 3 attempts** | `developer-agent.md` | Aider |
| 6 | **Reality check** | `plan.md` oversight table | Aider, Claude Code |
| 7 | **Architect/Editor contracts** | `architect-agent.md` + `developer-agent.md` | Aider |
| 8 | **Artifact validation** | `plan.md` | OpenCode+ |
| 9 | **READ/WRITE-ONLY split** | `researcher.md` + `developer-agent.md` | OpenCode+ |
| 10 | **Curated skills catalog** | `skills/.curated/index.json` | Codex CLI |

Design docs for each in `/home/user/dev/global_changes/`.

### #6 Reality check — orchestrator verifies subagents

Orchestrator runs independent verification after delegate_task claims side-effects:

```
After delegate_task claiming "server on port 8643":
  orchestrator: curl localhost:8643/health
  → fail → return to subagent
  → pass → accept
```

Added as 7th oversight check: **Reality check** | After phases 6,8,8.5 |
оркестратор САМ запускает проверочную команду.

### #7 Module Contracts — architect output contract

`architect-agent.md` now requires `§Module Contracts` table in every architecture doc:

```markdown
| Module | Input (API/Event) | Output (API/Event) | Developer |
|--------|-------------------|-------------------|-----------|
| voice_proxy.py | POST /stt (audio) | JSON {text: ...} | dev-1 |
```

Architecture doc is INCOMPLETE without this section.

### #8 Artifact validation — structural checks

Orchestrator validates every artifact for required sections before accepting:

| Artifact | Required sections | Check |
|----------|-------------------|-------|
| requirements | SMART goal, Actors, Acceptance Criteria, NFRs | `grep "## SMART Goal"` |
| system-analysis | SMART, 5 Whys, Goal Tree, WSM/AHP, Developer Task Spec | `grep "## Root Cause"` |
| architecture | Topology, Module Contracts, Data Flow | `grep "## Module Contracts"` |
| plan | File ownership, Bite-sized tasks, Principles checklist | `grep "OWNERSHIP"` |
| test-report | Traceability matrix, Failures (expected vs actual), Evidence | `grep "## Traceability"` |

Missing section → artifact REJECTED → return to agent.

### #9 READ/WRITE-ONLY — responsibility separation

**Researcher** (`researcher.md`): READ-ONLY. Never writes code. Never edits project files.
Output: markdown doc in `docs/research/`.

**Developer** (`developer-agent.md`): WRITE-ONLY for external world. No web_search, no browser.
Must ask Researcher/Architect/Tech Lead for information.

### #10 Curated skills catalog

15 skills indexed in `~/.hermes/skills/.curated/index.json` with categories and descriptions.

### Developer workflow improvements (#3, #5)

`developer-agent.md` replaced RED→GREEN→REFACTOR with **Edit→Lint→Test→Fix cycle**:

```
1. EDIT   — write code (1 file at a time)
2. LINT   — run linter. Errors? → fix → retry
3. TEST   — run tests. Fail? → read error → fix → retry
4. GREEN  — all passed → submit to Tech Lead
5. RETRY  — after 3 attempts → ask Tech Lead
```

Self-correction loop added: **3 attempts max, change approach each time.**
10 attempts of the same fix = antipattern.

## Orchestrator toolsets — terminal is MANDATORY (v1.4)

**Do NOT deploy an orchestrator without `terminal`.** Lesson from session
`20260613_185333_4c67b4` — the orchestrator literally said:

> «не могу выполнить напрямую — я сейчас в роли plan (оркестратор), у меня
> нет инструмента terminal. Сабагенты с terminal симулируют вывод вместо
> реального выполнения.»

Without `terminal`, the orchestrator is a blind manager. It cannot:
- Verify subagent outputs (`curl localhost:8643/health`)
- Prepare worktrees for developers (`git worktree add`)
- Read logs (`tail -f /var/log/...`)
- Check if a deployed service is actually running
- Restart crashed services

**Required toolsets for plan.md:**
```yaml
toolsets: [delegation, todo, file, session_search, skills, clarify, terminal]
```

The `terminal` role is **verification, not implementation**. Use it for quick
health checks and prep work; delegate heavy coding/ops to sub-agents.

## ⚠️ Verified model failures (v2.3)

These models have been tested in production and FAILED:

### Kimi K2.7 batch delegation → interrupted

When spawning 3 observers via batch `delegate_task` with Kimi K2.7, ALL three
returned `status='interrupted'` with "Parent agent interrupted — child did not
finish in time." Single-task `delegate_task` with Kimi may still work. Batch
mode fails reliably on current Kimi provider.

**Mitigation:** Use DeepSeek V4 Pro for all observer spawning. For leaf
subagents that don't need batch mode, Kimi remains a viable fallback.

### GPT-5.5 quota exhaustion

All spawns with gpt-5.5 return `insufficient_quota`. The `sk-proj-...` key
associated with the custom:openai provider has exhausted quota. Do NOT route
any agents to gpt-5.5 without first verifying quota.

### Qwen 3.6 35B (local) — too slow for orchestrator

Tested on Jetson GB10 ARM64 via llama.cpp (CPU). Session `20260613_180400_56c38b`:

| Metric | Value |
|--------|-------|
| Input tokens (prompt + context) | **116,338** |
| Output tokens | 298 |
| Latency | **313.3 sec (5 min 13 sec)** |
| Second call | **319.4 sec (5 min 19 sec)** |

At 116K context (430-line prompt + dialog + artifacts), generation speed
is ~0.9 tok/sec — unusable for interactive orchestration. This is the
steady-state context size for an orchestrator by Phase 3-4.

**Qwen 3.6 35B is NOT suitable for orchestrator role on Jetson CPU.**
It may work as a developer or analyst (shorter context, fewer turns).

### Subagent hallucination on DeepSeek

When delegating research tasks to sub-agents via `delegate_task` with
DeepSeek V4 Pro, the sub-agent often returns the search **plan** instead
of actual results:

```
# Expected: structured report with findings
# Received: "<antml:function_calls><antml:invoke name='web_search'>..."
```

The sub-agent emits the tool call XML but doesn't actually execute it.
This is a DeepSeek-specific behavior — it generates the format of tool
use without performing the tool use.

**Mitigation:** Orchestrator with `terminal` verifies key sub-agent outputs
by re-running at least 1 of 3 claimed results. If a sub-agent claims
«port 8080 is open» — orchestrator runs `curl localhost:8080` itself.

## Integration ownership void — plan file ownership ≠ integration (v2.5)

**The single most damaging pattern in multi-dev implementations:** the Plan assigns
each file to a specific developer, but no one owns the **integration points** --
how module A calls module B, what dataclass format they agree on, which parser the
orchestrator actually imports.

**Structural fix (v2.5):** Two new roles added to the orchestrator team:
- **DevOps Engineer (#10)** — owns integration. Phase 6a: Integration Gate. Greps
  imports, verifies dataclass compatibility, runs integration tests. If module exists
  but isn't imported → returns to developer with exact line reference.
- **Enterprise Architect (#11)** — cross-project alignment. Checks architecture decisions
  don't conflict with adjacent projects (Hermes, OpenCode+, Android). Guards standards:
  384-dim embeddings, Neo4j CE single DB, plugin architecture. Advises Architect (#4).

From the codemes_neo4j_repo-graph cycle (2026-06-17):

- Dev #1 built `codebase_scanner.py` with `TreeSitterParser` (tree-sitter, typed dataclasses)
- Dev #2 built `codebase_parser.py` with `TreeSitterParserL2` (tree-sitter Query API, dicts)
- Dev #3 built `codebase_indexer.py` with regex fallback and its OWN dataclasses
- **Result:** three parsers, three incompatible dataclass hierarchies, the indexer
  uses regex (not tree-sitter), embeddings module never called, 0 CALLS/INHERITS
  relationships in production graph. 10.8× bloat (8,400 lines for an ~780-line MVP).

**Root cause:** the Plan's ownership matrix is per-FILE, not per-CAPABILITY.
Integration is nobody's file → nobody builds it.

**Prevention (Tech Lead gate after Phase 6):**
1. `grep -r "from codebase_scanner import" codebase_indexer.py` → must return hits
2. `grep -r "EmbeddingGenerator" codebase_indexer.py` → must find usage
3. For every module in the Plan's ownership matrix, verify it's imported by AT LEAST
   one other module OR the orchestrator
4. If a module exists but is imported nowhere → orphan module → return to developer

**Prevention (Architecture contract):** The Architecture doc's Module Contracts table
must specify not just "Module X produces Y" but "Module X is CONSUMED by Module Z
via import/API call at path Z:line."

**Prevention (Plan):** Add an explicit "Integration: who wires A→B?" row to the
ownership matrix. If no one owns it, Tech Lead owns it.

## Auditor = delegation quality controller (v1.1)

The Auditor (#10) watches the orchestrator's delegation quality, NOT just
subagent errors. New checks:

- Did orchestrator pass complete context? Correct toolsets?
- Did a requirement from Phase 1 survive all phases?
- Did any agent claim «done» without producing the artifact?
- Did any agent ask the user to test instead of testing autonomously?

Auditor output includes a **Delegation Quality** section in the final report.

## `/goal` integration (recommended)

After the first phase completes, the orchestrator should set a standing goal
so the cycle survives session restarts:

```
/goal Полный цикл оркестрации: [task slug]. Текущая фаза: [N/10]
```

This ensures that even if the session is interrupted, the orchestrator
resumes from the correct phase.

## Phase 0 heredoc pitfall (v1.7)

When generating `structure.md` via `cat > file << 'STRUCTEOF'`, the **single quotes**
around the heredoc delimiter prevent shell variable expansion. `$(tree ...)` and
`$(find ... | wc -l)` remain as literal text — not executed.

**Fix:** Use unquoted heredoc (`<< STRUCTEOF`) to let shell expand `$(...)` constructs.
Or execute commands separately and redirect output:

```bash
tree -L 2 -I '...' ~/.hermes > /tmp/tree.txt
find ... | xargs wc -l | tail -1 > /tmp/stats.txt
# Then embed the files in structure.md
```

### Phase 0 post-creation verification (v1.7)

After creating `structure.md`, **verify it contains real data, not unexecuted commands**:

```bash
grep -c '\$(' codemes_1/structure.md   # must return 0
grep -c '├──' codemes_1/structure.md   # must return >0
```

If `$(` appears in the file → Phase 0 incomplete → regenerate with unquoted heredoc.

## Post-cycle

After Phase 10, deliver the **Quadruple report** (Auditor + Critic + Idea Generator + Knowledge Curator) and offer to save lessons learned as skill patches or memory entries.

## ⚠️ Out-of-band interruption during delegate_task (DeepSeek)

**Pattern:** User sends out-of-band message while a long `delegate_task` (120-180s)
is running → turn gets `interrupted_by_user` → DeepSeek streaming fails with
`Connection error` → turn ends as `interrupted_during_api_call` → dialog appears
dead to the user.

**Log signature (from session 20260615_232325_5994f4):**
```
23:39:13  Turn ended: interrupted_by_user
23:39:14  Streaming failed before delivery: Connection error
23:39:14  Turn ended: interrupted_during_api_call
```

**Why:** DeepSeek V4 Pro connection drops when the turn is interrupted mid-stream.
The user sees no response, re-sends the message → second interruption → loop.

**Mitigation:**
1. **Use `/steer`** instead of direct messages during delegate_task — steers without interrupting
2. **Wait** — delegate_task typically finishes in 2-3 minutes; the dialog will resume
3. **For orchestrator:** warn user when spawning long delegate_task: «Запускаю sub-агентов (это займёт 2-3 минуты). Не отправляй сообщения пока они работают — используй /steer если нужно подкорректировать.»
4. **Fallback provider:** Kimi K2.7 handles stream interruptions more gracefully than DeepSeek

## ⚠️ Knowledge Curator (#13) — autonomous cron fallback

The Knowledge Curator is spawned by the orchestrator at Phase 1 (alongside Auditor,
Critic, Idea Generator). **However**, the orchestrator may fail to spawn it:
- Wrong model routing (observer spawning with incompatible model)
- API quota exhaustion
- Orchestrator skip (only spawns 3 of 4 observers)

**Autonomous fallback** (created 2026-06-15):
- **Script:** `~/.hermes/scripts/knowledge-curator-ingest.py` — scans all
  `~/dev/codemes/*/docs/` artifacts, extracts entities into Neo4j KnowledgeEntity
  nodes, tracks processed files via `.curator_state`
- **Cron job:** `00713e568e40` — runs every 3 hours (requires gateway running)
- **Manual run:** `python3 ~/.hermes/scripts/knowledge-curator-ingest.py`

**State tracking:** Uses `~/.hermes/skills/.curator_state` (JSON: `{file_path: hash}`).
Hash = SHA256 of `path + mtime + size`. Only processes new/modified artifacts.

**Gateway requirement:** Cron jobs fire only when `hermes gateway` is running.
Without gateway, run manually or start gateway: `hermes gateway install && hermes gateway start`.

See `references/knowledge-curator-autonomous.md` for full details.

## ⚠️ plan.md hardcoded model pitfall

The observer spawning code in `plan.md` (lines 260-295) historically had hardcoded
`model="kimi-k2.7-code"` and `provider="custom:kimi"` on all 4 delegate_task calls.
This contradicted the routing rules (lines 229-232) which say "do NOT hardcode model."

**Symptom:** Orchestrator sees conflicting instructions → may skip observer spawns or
use wrong provider → observers fail with quota/auth errors.

**Fix (applied 2026-06-15):** Removed hardcoded model/provider from Knowledge Curator
spawn code (4th delegate_task). Uses configured model from `delegation.model` in
config.yaml. The first 3 observers still have hardcoded models — if quota/auth issues
recur, remove those too.

## ⚠️ Subagent fabrication — verify ALL external side effects

**Sub-agents fabricate.** They claim writes, deployments, and database inserts that
never happened. This is NOT model-specific — observed on DeepSeek V4 Pro, GPT-5.5,
and Kimi K2.7.

## ⚠️ Delegate_task timeout with large file writes (DeepSeek)

**Pattern:** Sub-agent writes a large file (50KB+, e.g. 97KB architecture document) via
`write_file` → the write succeeds → BUT the final API call for the summary times out
→ `delegate_task` returns `status: max_iterations` or `interrupted` → orchestrator sees
"failed" and may re-spawn the sub-agent.

**Symptom:** `delegate_task` result shows `exit_reason: "max_iterations"` but
`tool_trace` includes `write_file` with a large `args_bytes` value. The file IS on disk.

**Verification protocol (BEFORE re-spawning):**
1. Check `tool_trace` for `write_file` calls — if present, the artifact likely exists
2. `stat` the expected output path: `ls -la <path>` or `wc -l <path>`
3. If file exists with reasonable size → the phase succeeded, just without summary
4. Read the first/last 30 lines to verify content integrity
5. If file missing or empty (<500 bytes) → re-spawn

**Observed:** 2026-06-17 — Architect (#4) wrote 97KB/1,680-line file, API timed out
at summary generation. File was complete and valid. Re-spawning would have duplicated
8+ minutes of work.

### How to detect

After EVERY `delegate_task` that claims an external side effect, run a verification:

| Claim | Verify with |
|-------|-------------|
| "Wrote file at path X" | `read_file` or `stat X` |
| "Created Neo4j nodes" | `curl -u neo4j:changeme ... 'MATCH (n) WHERE n.type IN [...] RETURN ...'` |
| "Server running on port N" | `curl localhost:N/health` |
| "Deployment successful" | `curl` + health check + `git log -1` |
| "Tests passed" | Run `grep` on test output for actual PASS/FAIL counts |

### When subagent fabricated

1. **Find the script** — sub-agents often write real Python scripts to `/tmp/` but don't execute them
2. **Run it yourself** — `python3 /tmp/ingest_*.py` or equivalent
3. **Verify again** — re-run the Cypher/curl check
4. **Report to user** — «Sub-agent claimed X but didn't do it. I fixed it. Result: Y.»

### Why this happens

Sub-agents produce plausible-looking terminal output in their summaries without
actually running the commands. The tool trace in `results[].tool_trace` shows
`terminal` calls but the output may be fabricated. Trust only your own verification.

See `references/subagent-fabrication.md` for detailed examples and verification scripts.

## ClarifyBridge — interruptible delegation (v2.3, 2026-06-15)

Sub-agents can now ask the user questions during execution (OpenCode parity).
`delegate_tool.py` has `_ClarifyBridge` — a thread-safe queue relay that
replaces the sub-agent's `clarify` handler. The orchestrator polls for
pending questions while waiting for the child future.

**How it works:**
```
Sub-agent: clarify("NPM or pip?")
  → bridge.ask() → queue.put() → block (600s timeout)
Orchestrator: poll loop detects pending question
  → progress_callback("subagent.clarify", question, choices, subagent_id)
  → user answers → bridge.answer(question_id, response)
  → sub-agent unblocks, continues
```

**Role-based fallback (600s timeout for ALL agents):**

| Agent | User silent 600s → | Action |
|-------|-------------------|--------|
| **Requirements Analyst (#1)** | **CYCLE HALTS** | No requirements = no foundation. Set `/goal`, report to user, wait. |
| **Architect (#4)** | **Consult Researcher (#3)** | Researcher aggregates research artifact, education graph, prior cycles. Answer with ⚠️ «Предполагаю на основе research. Проверь.» |
| **All others** | **Orchestrator self-answers** | Based on cycle context, artifacts, goal_preview. Notify: «Sub-agent X спросил Y. Ответил Z. Ок?» |

**Orchestrator's duty:** When a `subagent.clarify` progress event fires, the
orchestrator MUST handle it BEFORE proceeding to the next phase. A blocked
sub-agent with a pending question stalls the entire cycle. Use your own
`clarify` tool to present the question to the user. After answer (or timeout
+ fallback), inject via the bridge and continue.

**Pitfall:** The orchestrator must check for pending questions via the
poll loop. If the orchestrator ignores `subagent.clarify` events, sub-agents
will timeout after 600s and continue with degraded context.

## plan as default agent (v2.3)

To make the orchestrator the default agent for every session:
```bash
hermes config set agent.default plan
```

This ensures every new Hermes session starts with the full orchestration
lifecycle: Phase 0 bootstrap → Phase 1 Requirements → ... → Phase 10 Audit.

## Team Topology (v2.5 — 15 agents)

5 observers (was 4): Auditor (#12 process), Critic (#13 dead code), Idea Generator (#14 unheard ideas), Knowledge Curator (#15 → Neo4j Knowledge Graph), Enterprise Architect (#11 cross-project alignment).

2 new operational roles:
- **DevOps Engineer (#10)** — owns integration points. Phase 6a: Integration Gate. Verifies all modules are wired together (grep imports, dataclass compatibility, integration tests). Direct answer to "nobody owned integration."
- **Enterprise Architect (#11)** — cross-project alignment. Knows the full landscape (Hermes, OpenCode+, Education Graph, Claw Graph, Android). Checks for conflicts and duplication between projects. Advises Architect (#4) on Phase 4.

Knowledge Curator agent file: `~/.hermes/agents/knowledge-curator.md` (created 2026-06-15).
Agent file includes per-phase entity extraction table, cross-cycle connection rules,
and report format. Orchestrator spawns it alongside the other 3 observers at Phase 1.

Developer temperatures differ by role: Dev #1-4 (precision, 0.1-0.3 Kimi), Dev #5-7 (creative, 0.5-0.8 DeepSeek).

## v2.4 — Methodology-driven over-engineering & LLM-dependency trap (2026-06-16)

Lessons from the full P0 Memory Scaffolding cycle (`hermes-p0-memory_20260615_232649`):
10 phases, 7 production files (~1,900 LOC), 323 tests, all 6 ACs met. The Critic's final
report identified systemic patterns worth encoding.

### Methodology-driven bloat

**Symptom:** Documentation-to-code ratio of ~2:1 (4K lines of markdown for 2K lines of code).
Agents fill ALL template sections even when there's nothing meaningful to add:
- AHP matrices for choices where one alternative obviously dominates
- Deployment health checks for features that were never deployed
- NFRs that can't be measured in the current environment
- C4 Level 1 diagrams showing 4 boxes for a system of 7 files

**Root cause:** AGENTS.md prescribes artifact structures with mandatory sections. Agents
dutifully fill every section — the quality gate checks section PRESENCE, not section VALUE.

**Mitigations for orchestrator:**
1. When spawning Phase 2 (System Analysis), instruct: «WSM sufficient. AHP only if >3
   alternatives and choice is genuinely close. Skip AHP when WSM gap >3 points.»
2. When spawning Phase 4 (Architecture), instruct: «One C4 diagram (Container level) is
   sufficient for systems with <10 modules. Skip Context/Component/Deployment diagrams.»
3. When spawning Phase 1 (Requirements), instruct: «Only declare NFRs that CAN BE MEASURED
   with available tools. Mark others as design-intent, not pass/fail criteria.»
4. **Artifact quality gate addendum:** After checking section presence, check: «Does this
   section contain information not already captured elsewhere?» Duplicate content across
   phases is a smell.

### LLM-dependent feature trap

**Symptom:** The ConsolidationManager TiMem pipeline was fully built (535 lines, HMAC-SHA256,
atomic transactions) but always returns placeholders because `_call_consolidation_llm` hook
does not exist in `MemoryManager`. The HMAC protects strings containing «(No LLM available)».

**Root cause:** The architecture assumed LLM integration was orthogonal to the pipeline design.
In practice, the LLM hook IS the pipeline's output path — without it, consolidation is dead code.

**Rule:** When any Phase 4-5 design depends on an external integration point (LLM call, API
endpoint, plugin hook), the Plan phase MUST include an explicit task to verify that integration
point EXISTS in the current codebase. If it doesn't, either:
- Add the integration task to the plan BEFORE the dependent feature
- Defer the dependent feature to a later cycle
- Replace the dependency with a self-contained alternative

**Detection pattern:** Search for methods called via `hasattr()` checks — these are integration
points that may not exist (`hasattr(self._mm, "_call_consolidation_llm")` → False).

### NFR measurability gate

**Symptom:** NFR2 (consolidation throughput <5s) and NFR6 (compression ratio ≤10%) were
declared but deferred to "design-verified" because they can't be measured without a live LLM.

**Rule:** Phase 1 Requirements MUST only declare NFRs where:
- The measurement tool exists in the current environment
- The measurement can be executed during Phase 6 (by the developer) or Phase 8.5 (by the tester)
- The measurement produces a numeric result comparable to the target

NFRs that can't be measured become "design-intent" annotations, not pass/fail acceptance criteria.
Mark them explicitly: `NFR-X: <target> (DESIGN-INTENT — measurement deferred to P1)`.

### Phase 9 is NOT optional

**Symptom:** Post-Deploy Research (Phase 9) was initially skipped — the cycle went 8→8.5→10.
When Phase 9 was finally run, it discovered that consolidation was never triggered in production
(0 entries in `memory_consolidations` after deployment). This finding came too late — the project
was already marked "complete."

**Rule:** Phase 9 MUST run BEFORE Phase 10. It is the reality check on the entire cycle.
Run it in parallel with Phase 8.5 if needed, but never skip it. The Phase 9 report answers:
- Did the deployed code actually execute in production?
- Do the NFR measurements hold with real data?
- What surprises emerged that weren't visible in tests?

### Codebase audit as research phase (success pattern)

**Success pattern:** The Researcher (#3) was delegated to conduct a **codebase audit** with
5 concrete Research Questions, each answered with file:line references to the actual source.
This discovered that `is_system_provider` did not exist in the codebase — a critical gap that
would have broken SegTreeMem registration as a system provider.

**When to use:** Any feature that extends an existing subsystem (MemoryProvider ABC,
MemoryManager, plugin infrastructure) MUST include a codebase audit RQ: «What is the ACTUAL
state of the target files?» Do not trust architecture docs or assumptions — verify with `read_file`
and `search_files` on the real codebase.

**RQ template for codebase audits:**
1. What is the actual API surface of the target class? (read the ABC)
2. What registration/discovery mechanisms exist and what are their constraints? (read the manager)
3. What hooks fire at which lifecycle points? (read the agent loop)
4. What indexes and schemas already exist? (read the state DB init)
5. What is the actual plugin loading flow? (read the plugin discovery code)

## Phase lifecycle improvements (v1.3)

The following patches were applied to `plan.md` on 2026-06-13 to fix
orchestrator reliability. When creating new orchestrator profiles or
repairing drift, verify these are present:

1. **Delegate failure protocol** — 3 retry attempts before escalating to user.
   Never silently skip a phase.
2. **Mid-turn steering handler** — table of reactions for out-of-band user
   messages (stop/correct/new task/status).
3. **Phase lifecycle contract** — ENTRY/EXIT/ROLLBACK conditions for every phase.
   Don't start without ENTRY, don't declare done without EXIT.
4. **Artifact caching rule** — read → summarise → inject into next delegate_task.
   Sub-agents are stateless; never assume they remember the previous phase.
5. **Developer deviation audit** — `docs/deviation-log.md` for every rule
   violation. Checked by Tech Lead (Phase 5) and Security (Phase 7).
6. **Explicit toolsets** — `plan.md` must use `[delegation, todo, file,
   session_search, skills, clarify]`, not `[]` (which enables ALL tools).

## References

- `references/deep-research-validation.md` — **NEW (2026-06-17)**. Ground-truth checklist for deciding whether full Phase 3 research is warranted: package freshness, git activity, codebase size verification, decision matrix. Lesson: one measurement on real data > ten papers about the tool.

- `references/codebase-graph-architecture-cycle.md` — **NEW (2026-06-17)**. Full 4-phase cycle methodology: live Neo4j ground-truth census, codebase census, tree-sitter + embedding benchmarks on target hardware, 4-architecture comparison (Flat / Hierarchical Hybrid / Event-Sourced / Multi-Modal), Neo4j schema, critical pitfalls (57× documentation drift, bottleneck inversion, delegate_task timeout pattern). Use as template for any codebase-as-graph project.

- `references/codebase-graph-full-cycle-case-study.md` — **NEW (2026-06-17)**. Full 10-phase cycle case study: codemes_neo4j_repo-graph. Key learnings: integration ownership void (3 orphan modules, 10.8× bloat), SD-2 priority shift (embeddings 5.8× faster than predicted), census error (12.7×), model fallback (GPT-5.5 → DeepSeek for observers), delegate_task timeout with large files. Metrics: 35K nodes, 25 PASS/4 FAIL, ~$0.80 total cost.

- `references/hermes-p0-memory-cycle-20260616.md` — **NEW (2026-06-16)**. Full-cycle case study: P0 Memory Scaffolding (temporal retrieval + consolidation pipeline). 10 phases, 7 production files (~1,900 LOC), 4K lines of documentation, 323 tests, 6/6 ACs met. Key lessons: methodology-driven over-engineering (2:1 doc-to-code ratio), LLM-dependency trap (consolidation placeholder because hook missing), NFR measurability gate (2 of 8 NFRs deferred), Phase 9 mandatory (found 0 production consolidations), codebase audit as critical research phase (discovered missing is_system_provider).

- `references/idea-generator-checklist.md` — **NEW (2026-06-15)**. Idea Generator (#12) 4-question framework: unheard ideas, missing connections, information sources, pipeline optimizations. Includes codebase-audit methodology (diff architecture docs vs actual source code), output format, and pitfalls. Proven across hermes-p0-memory (Phase 4) and evolving-agents (Phase 1) sessions.
- `references/subagent-fabrication.md` — **NEW (2026-06-15)**. Verification protocol for sub-agent side-effect claims (Neo4j, file writes, deployments). Pattern: sub-agent fabricates, orchestrator verifies with curl/stat/read_file.
- `references/knowledge-curator-autonomous.md` — **NEW (2026-06-15)**. Autonomous Knowledge Curator cron fallback: script, cron job (00713e568e40), state tracking, first-run results (2,281 entities from 27 artifacts). Use when orchestrator fails to spawn Knowledge Curator or for background Neo4j ingestion.
- `references/model-selection-guide.md` — verified GGUF sizes, Q4 hallucination
  boundary (32K), DGX Spark memory budget, model-by-model assessment.
- `references/memory-scaffolding-research.md` — **NEW (2026-06-15)**. Condensed memory
  scaffolding research: 5-layer stack, 8 best practices, 8 Hermes gaps (P0-P3),
  5 key trends, top June 2026 papers. Produced by 8-iteration deep research
  cycle. Load when working on Hermes memory architecture.
- `references/managerial-oversight-checklist.md` — 7 cross-phase checks the
  orchestrator runs at every quality gate (requirement propagation, root cause
  resolution, goal tree completion, context completeness, agent accountability,
  tester autonomy, reality check).
- `references/code-agent-best-practices.md` — research across Claude Code,
  Aider, Codex CLI, SWE-Agent, Cursor, OpenCode+. Top 10 improvements for
  Hermes, known pitfalls, adaptation guide.
- `references/error-ledger-pattern.md` — canonical issue ledger/backlog pattern for continuing after multi-phase defects, including compression recovery and summary/detail synchronization.
- `references/vcs-plan-baseline-preflight.md` — VCS baseline + canonical plan readiness gate for long orchestration projects after compression/error-ledger recovery.
- `references/promptbreeder-hotswap-patterns.md` — how Hermes loads agents (3-layer architecture), hot-swap via ephemeral_system_prompt, profile-based sandbox pattern, Promptbreeder operators, Immutable Safety Core, and known pitfalls. Use when architecting agent evolution features for Hermes.
- `references/hermes-mutability-map.md` — detailed Mermaid diagram and table showing which Hermes components can be mutated by Promptbreeder operators (Immutable Safety Core 🔴, Conditional 🟡, Mutable 🟢, Out of Scope ⚪). Use when designing topology mutations or Promptbreeder operator scope.
