---
name: multi-agent-orchestration
description: "Architect and run multi-agent workflows: orchestrator (plan agent) + 20 specialized sub-agents covering the full development lifecycle."
version: 2.15.0
author: Hermes Agent + User
license: MIT
metadata:
  hermes:
    tags: [orchestration, multi-agent, subagent, plan, architecture, developer, security, deployment, testing, auditor]
    related_skills: [subagent-driven-development, plan, architecture-design, requirements-analysis, build-engineering-standards, test-driven-development, secure-coding, orchestration-cycle]
---

# Multi-Agent Orchestration

Use this skill when designing or running multi-agent workflows — an orchestrator
agent coordinates a team of specialized sub-agents through the full development
lifecycle. **v2.15 adds DevOps Engineer (#10), Enterprise Architect (#11), and 5 new specialist roles (#16-20: Cross-Reference Resolver, Schema Validator, Data Quality Agent, Performance Engineer, Language Specialist). Integration Gate (Phase 6a) between Implement and Verification. Observer count: 5 (added Enterprise Architect as 5th persistent observer). Claw graph now has its own minimal 5-phase orchestrator (see `references/claw-orchestrator.md`).

Previous addition: v2.10 clarified the runtime contract: `/agent plan` applies a prompt/toolset/model preset to the live parent `AIAgent`; `delegate_task` creates isolated children but does not currently accept `agent_id`, so subagent personas must be injected explicitly via goal/context/toolsets/model/provider until runtime support exists.

**Agent files:** `~/.hermes/agents/` — `plan.md` (orchestrator) + 10 sub-agent personas.

For adapting this orchestrator to **OpenCode+** (local llama.cpp + LiteLLM), see `references/opencode-plus-orchestrator.md`. Key differences: `task` tool instead of `delegate_task`, `build` agent plays multiple specialist roles, no per-call model routing, agent config in `opencode.json`.

## Runtime contract — `/agent` presets vs delegated children (v2.10)

Current Hermes runtime has two separate mechanisms that must not be confused:

| Mechanism | What it loads | Scope | Key limitation |
|---|---|---|---|
| `/agent plan` | `~/.hermes/agents/plan.md` via `load_agents()` + `apply_agent()` | Mutates the live parent `AIAgent` until the next `/agent ...` switch | This is a prompt-driven orchestrator, not a deterministic workflow engine |
| `delegate_task(...)` | A fresh child `AIAgent` built from the parent/runtime config plus explicit call args | Isolated child context; returns only a summary | No `agent_id` parameter yet; it does **not** automatically load `requirements-agent.md`, `developer-agent.md`, etc. |

Practical rule: when the orchestrator delegates a role, inject the persona and contract explicitly in `goal`/`context`, and set `toolsets`, `model`, `provider`, and `role` on the call. Do not assume `delegate_task` will load the disk agent file by name.

```python
delegate_task(
    goal="You are requirements-agent. Collect requirements only; do not design or code.",
    context="Task: ...\nArtifacts to produce: docs/requirements/<slug>.md\nUser preference: test autonomously; do not ask User to verify.",
    toolsets=["clarify"],
    model="kimi-k2.7-code",
    provider="custom:kimi",
    role="leaf",
)
```

If true role-based child loading is required, the runtime feature should be explicit (e.g. `delegate_task(agent_id="requirements-agent", ...)`) and tested separately. Until then, treat `~/.hermes/agents/*.md` as top-level `/agent` presets plus source material for prompts, not as automatically addressable child-agent identities.

When presenting agent architecture to User, use the **visual chain format** (phases
with numbers under each block) and **comparison tables** — not paragraph descriptions.
See `references/agent-roles.md` for the canonical table.

## Architecture (v2.0)

```
Phase 1          Phase 2          Phase 3          Phase 4          Phase 5
Requirements → System Analyst → Deep Researcher → Architect → Tech Lead
(subagent)     (subagent,        (subagent,       (subagent)      (subagent,
               весь цикл)        весь цикл)                       управляет
                                                                   7 разработчиками)
                                                                        │
                                                                        ▼
                                                                   Phase 6
                                                                   Developers ×7
                                                                   (subagents)
                                                                        │
                              Phase 6.5                                │
                         Verification Gate ←───────────────────────────┘
                              │
                              ▼
Phase 10        Phase 9       Phase 8.5       Phase 8         Phase 7
Iterate    ←   Post-Deploy ←  Tester 🧪  ←   Deployment  ←   Security
+ Audit        (Researcher)   (acceptance)    (subagent)       (subagent)
(Auditor)
```

**Orchestrator = conductor AND manager.** Cross-references artifacts between phases,
verifies every agent DID their job, returns underperformers for rework.

**Auditor = delegation quality controller.** Watches for context loss, wrong toolsets,
phase skipping, and Tester autonomy violations.

## Lifecycle (v2.0 — 10 phases)

| # | Phase | Subagent | Role | Cycles? |
|---|-------|----------|------|---------|
| 1 | Requirements | `requirements-agent` | Asks clarifying questions; re-runs cycle after answers | No |
| 2 | System Analysis | `system-analyst` | SMART→5 Whys→Goal Tree→WSM/AHP + returns team to goals. Runs Phase 6.5 (verification gate) | **Yes** |
| 3 | Deep Research | `researcher` | Iterative search, hypothesis validation, source quality scoring, structured citations | **Yes** |
| 4 | Architecture | `architect` | Designs topology, verifies with user, searches education/claw/memory graph | **Yes** |
| 5 | Tech Lead | `techlead` | Plans, manages 7 developers, code review, principle compliance | No |
| 6 | Implementation | `developer-1…7` | RED→GREEN→REFACTOR. Stubborn, can break rules. No web access | No |
| 6a | **Integration Gate** | **`devops-engineer`** 🛠️ | Verifies ALL modules are cross-connected: grep imports, shared dataclasses, orchestrator actually calls the right parser. If orphan module found → return to Phase 6 with exact fix instruction. Prevents the \"nobody owned integration points\" failure pattern. | No |
| 6.5 | Verification | `system-analyst` | 4 checks: spec, goal tree, root cause, abstraction. Deviation routing | — |
| 7 | Security | `security-agent` | SAST gate, secret scanning, dependency audit. Protects the TEAM | No |
| 8 | Deployment | `deployment-agent` | Deploy + health check. Failure → return to Phase 1–2 | No |
| 8.5 | **Acceptance Testing** | **`tester-agent`** 🧪 | Autonomous testing against 3 requirement sources. Traceability matrix. **NEVER delegates testing to user.** Artifact: `docs/tests/<slug>.md` | No |
| 9 | Post-Deploy | `researcher` | Evidence collection → hypothesis validation → statistical analysis | — |
| 10 | Iterate + Audit + Critic + Ideas + Knowledge + Enterprise | **Orchestrator + Auditor + Critic + Idea Generator + Knowledge Curator + Enterprise Architect** | Metrics, retrospective. **Five reports:** Auditor (process+info), Critic (dead code+over-engineering), Idea Generator (unheard ideas+connections), Knowledge Curator (Knowledge Graph state+cross-cycle links), Enterprise Architect (cross-project conflicts, standards compliance, architectural debt) | — |

## Key Agent Patterns

### Executor Pattern (developer agent)

The developer agent is **designed to succeed where lifecycle-constrained agents fail**:

- **Can break rules** — socat, qemu wrapper, binary replacement, hardcoded URLs for debugging — any means to make it work
- **Doesn't give up** — no "impossible", only "haven't found the way yet"
- **1 bug → 1 fix → 1 test** — iterative, never batch
- **Tests on real device** — adb install, logcat, curl, health check
- **Returns to tech lead for review** — whatever "dirty" shortcuts were used, tech lead decides what to keep
- **No web access** — asks surrounding agents for information instead

### Tester Pattern (Phase 8.5 — NEW in v2.0)

The tester agent verifies the deployed system against ALL requirement sources:

- **3-source verification**: Requirements doc + System Analysis doc + user acceptance criteria
- **Autonomous execution (NON-NEGOTIABLE)**: uses `terminal` (curl/adb/ping), `browser`, `read_file`. NEVER says «проверь сам». NEVER uses `clarify` to delegate testing.
- **Traceability matrix**: every test → specific requirement ID. Tests without a requirement mapping are YAGNI.
- **Real deployment, real data**: tests the DEPLOYED system, not localhost. Reads configs for correct ports.
- **Measurable NFRs**: `time curl` for performance, `ab`/`wrk` for load, TLS/cert checks for security.
- **Reproducible failures**: every ❌ includes exact command to reproduce.
- **Escalation**: test failures → System Analyst (#2) decides: fix (→ Phase 6) or accept deviation.

### Managerial Oversight Pattern (NEW in v2.0)

The orchestrator is NOT just a conductor — it's a **manager** accountable for team output.
After every phase, cross-reference artifacts:

| Check | When | Red flag |
|-------|------|----------|
| Requirement propagation | Phase 1→2→3→4→8.5 | «User wanted tests» — but `docs/tests/` doesn't have them |
| Root cause resolution | Phase 2→6→8.5 | Fixed symptom, root cause remains |
| Goal tree completion | Phase 2→6.5→8.5 | Sub-goal has no implementation or test |
| Context completeness | Every delegation | Agent asks about something already in Requirements doc |
| Agent accountability | After every phase | Artifact exists but is empty; or agent claimed «done» without evidence |
| Tester autonomy | Phase 8.5 | Test report has `UNTESTABLE` without justification, or uses `clarify` |

**Red flag → return to agent**: «Requirement X from [source] is missing. Re-do.»

### Auditor Pattern (UPDATED in v2.0)

The Auditor (#10) silently observes ALL phases and checks:

**Original checks**: subagent failures, phase re-executions, context loss, tool misuse,
plan deviations, token waste, race conditions.

**NEW in v2.0 — Delegation quality**:
- Did orchestrator pass complete context? Correct toolsets?
- Did any sub-agent receive the wrong task?
- Did a requirement from Phase 1 survive all phases, or was it dropped?
- Did any agent claim «done» without producing the artifact?
- Did the Tester (or any agent) ask the user to test instead of testing autonomously?

Auditor output includes a **Delegation Quality** section:
```
### Delegation Quality
| # | Фаза | Агент  | Проблема делегирования            | Серьёзность |
|---|------|--------|----------------------------------|:----------:|
| 1 | 8.5  | Tester | Context не содержал requirements | 🔴          |
```

### Integration Gate (devops engineer, Phase 6a — NEW in v2.15)

After implementation, BEFORE verification, DevOps Engineer runs a mechanical check:

1. **Import graph verification**: `grep -r "from codebase_scanner import" codebase_indexer.py` — is the parser actually imported?
2. **Dataclass compatibility**: are `ParsedFile`, `ParsedFunction`, etc. defined once and used everywhere, or duplicated in 3 files with different fields?
3. **Orphan module detection**: any `.py` file listed in Plan's \"modules\" but never imported by the orchestrator?
4. **Integration smoke test**: call `full_scan()` → query Neo4j → verify expected entity types exist

If any check fails → return to Phase 6 with EXACT file:line fix instruction. This 5-minute gate prevents the most expensive failure pattern: 3 orphaned modules, 10.8× bloat, 2,150 dead lines.

### Verification Gate (system analyst, Phase 6.5)

After implementation, system analyst runs 4 checks:
1. Spec conformance — matches Developer Task Spec?
2. Goal tree alignment — advances defined sub-goals? No YAGNI work?
3. Root cause resolved — 5-Whys root cause fixed, or just symptom?
4. Correct abstraction level — fix at the right system level?

Deviation routing: scope→Phase 2, architecture→Phase 4, implementation→Phase 6.

### Why This Pattern Works

A lifecycle-constrained agent (10 phases, TDD, SAST, SOLID) **cannot** use hacky
workarounds — the lifecycle forbids them. By delegating implementation to a
special-purpose subagent with a different prompt ("works > pretty"), the orchestrator
preserves analytical rigor while gaining the flexibility to actually ship code.

**The Tester closes the loop**: requirements → code → deployment → autonomous verification
against the original requirements. No human in the testing loop. The Auditor then
double-checks that the Tester actually tested, not just claimed to.

## Root Cause: Why Agents Say «Проверь сам»

The most common failure pattern (cost: 14-22 hours in one case):

1. User's preference «тестируй сам» lives in MEMORY — which sub-agents CANNOT access
2. Orchestrator delegates without passing this requirement in context
3. Sub-agent (Deployment or Developer) interprets «проверь» as «health check only» — not «verify against requirements»
4. Sub-agent tells user: «проверь сам с телефона»
5. Auditor had no check for this pattern — violation undetected

**Fix (v2.0)**: dedicated Tester with NON-NEGOTIABLE autonomous execution mandate +
Orchestrator managerial oversight at every quality gate + Auditor delegation quality checks.

## Parallel Phase Execution

Phases 1 (Requirements), 2 (System Analysis), and 3 (Research) can run **in parallel**
via `delegate_task(tasks=[...])` — they have no mutual dependencies.

**Research-first variant (v2.13):** When the user explicitly orders «сначала research», swap Phase 3 before Phase 1. Order: 0 → 3 → 1 → 2 → 4 → ... Inject the completed research artifact into Phase 1 context with key findings summary. This is documented in `orchestration-cycle` skill §Research-first variant.

Phases 4 (Architecture) and 5 (Tech Lead) are **sequential** — architecture must finish
before tech lead can plan implementation.

## Cross-Phase Context Passing

Subagents are isolated — they have NO memory of the parent conversation.
Pass ALL relevant file paths explicitly in `context`.

| Downstream Phase | Must Read |
|-----------------|-----------|
| System Analyst (2) | Requirements doc |
| Researcher (3) | (independent, but benefits from requirements) |
| Architect (4) | Requirements + System Analysis + Research |
| Tech Lead (5) | Architecture (ALL) + System Analysis + Requirements |
| Developers (6) | Plan (their specific task slice) |
| Tester (8.5) | **Requirements doc + System Analysis doc + user acceptance criteria** |
| Auditor (10) | All phase artifacts |

**Critical for Tester**: pass ALL THREE requirement sources in context. If Tester doesn't
know what was required, it can't verify. This is the #1 delegation quality failure.

## Phase 1 — Batch clarifying questions (v2.3)

When the Requirements Analyst returns 10+ clarifying questions, do NOT call
`clarify` once per question — this fractures the user's attention and slows
the cycle. Instead:

1. Read the requirements artifact with `read_file`
2. Present ALL questions in a single message with choice labels (A/B/C/D)
3. Provide a response format: «Q1=A, Q2=B, Q3=свой вариант: ...»
4. Group related questions into blocks for readability

This lets User answer everything in one reply and unblocks the cycle immediately.

### Observer spawning — STATELESS PROBLEM (v2.15)

The five-observer pattern (Auditor #12 + Critic #13 + Idea Generator #14 + Knowledge Curator #15 + Enterprise Architect #11) was
validated in production on 2026-06-14 (codemes_1 packaging cycle) and on 2026-06-15
(multi-agent-runtime research cycle + promptbreeder-hotswap cycle). Results:

| Observer | Output | Value |
|----------|--------|-------|
| **Auditor #10** | Caught Phase 0 failure (structure.md = unexecuted template) | Reality check — prevented blind continuation |
| **Critic #11** | 13 findings: build.md=general.md duplicate, 48MB cruft, manifest.yaml≠pack.sh source of truth | Actionable cleanup + architectural debt discovery |
| **Idea Generator #12** | 6 parallel packaging streams, 6 missing agent connections, 9 information gaps | Directly informed Architecture and Plan phases |
| **Knowledge Curator #15** | Cross-cycle entity extraction, Neo4j node creation, knowledge base curation | Builds persistent Knowledge Graph, prevents knowledge loss between cycles |
| **Enterprise Architect #11** | Cross-project alignment, standards compliance, architectural debt across systems | Prevents conflicts between Hermes, OpenCode+, Claw, Education Graph |

**CRITICAL FINDING (v2.5):** `delegate_task` creates STATELESS leaf agents — they DIE
after returning results. Observers spawned at Phase 1 are GONE by Phase 2. The current
pattern spawns observers at Phase 1 and again at Phase 10 — but nothing in between.
This means observers see only FINAL artifacts, not the process of their creation.

**Symptom:** Critic discovers manifest.yaml≠pack.sh disconnect at Phase 10 (post-hoc),
not at Phase 6 when it could have prevented 1700 lines of dead library code.

**Solution — Observer Checkpoint Protocol (v2.11):** After each phase produces an artifact, the orchestrator spawns all three observers in a **batch `delegate_task`** with the artifact path and a 2-3 sentence summary. Observers are fire-and-forget (don't block the next phase), accumulate findings, and synthesise at Phase 10. This is implemented in `~/.hermes/agents/plan.md` §Observer checkpoints (lines 303-363). The batch shape per phase:

```
Phase 1: spawn Observer → .observations/checkpoint-01.md
Phase 2: spawn Observer + checkpoint-01.md → checkpoint-02.md
Phase 4: spawn Observer + checkpoint-02.md → checkpoint-04.md
Phase 6: spawn Observer + checkpoint-04.md → checkpoint-06.md
Phase 8.5: spawn Observer + checkpoint-06.md → checkpoint-08.md
Phase 10: spawn Observer + all checkpoints → FINAL.md (triple report)
```

This turns observers from "Phase 10 reporters" into "continuous auditors" without
requiring long-lived sub-agents (which Hermes runtime doesn't support).

See `references/observer-persistence-problem.md` for the deep runtime analysis.
See `references/resumable-observer-supervisor.md` for the target ObserverSupervisor design: durable observer identity, schemas, gate merge rules, permissions, migration, and tests.
See `references/first-observer-cycle.md` for the full codemes_1 case study.

**Observer responsibility boundaries (v2.15):**
- **Auditor #12:** Process quality, delegation quality, information sufficiency. Does NOT review code.
- **Critic #13:** Output quality — dead code, duplication, over-engineering. Reviews ALL artifacts including code.
- **Idea Generator #14:** Unheard ideas, missing connections, pipeline optimisations. Creative, not critical.
- **Knowledge Curator #15:** Knowledge Graph ingestion — extracts entities from every artifact into Neo4j, builds cross-cycle connections, curates and deduplicates the knowledge base.
- **Enterprise Architect #11:** Cross-project alignment — checks for conflicts with Hermes, OpenCode+, Android app, Education Graph, Claw Graph. Standards enforcement (384-dim embeddings, plugin architecture, Neo4j CE single-DB). Detects duplication across projects (this module already exists in OpenCode+).
See `references/degraded-orchestration-mode.md` for the exception protocol when observer/developer delegation is blocked by provider/model routing failures but the user explicitly asked the cycle to continue.

## Escalation Gateway Pattern

Subagents CANNOT use `clarify`. Only `requirements-agent` bridges to user:

```
developer → techlead → researcher → architect → system-analyst → requirements-agent → USER
   ↑ each level can answer OR escalate further                                  ↑ clarify tool
```

## Auto-Start Configuration (4-layer guarantee)

For `/agent plan` to automatically run the full cycle:

1. **plan.md activation trigger** — first thing in system prompt: «user message = task input, begin Phase 1»
2. **orchestration-cycle skill** — preload with `hermes -s orchestration-cycle`
3. **Trigger at top of system prompt body** — before any other content
4. **`/goal` standing goal** — after Phase 1, remind user: `/goal Full cycle: [slug]. Phase [N]/10`

### Persistence

**One `/agent plan` sticks for the entire session.** `apply_agent()` sets
`ephemeral_system_prompt` on the `AIAgent` object, which persists across all
turns. No need to re-type `/agent plan` every message. Switch back with
`/agent general` when done.

See `orchestration-cycle` skill for activation/persistence details.

For exception handling when delegate_task/provider routing blocks normal role delegation, see `references/degraded-orchestration-mode.md`.

## Orchestrator Model Selection (v2.12 — GPT-5.5 REMOVED)

The orchestrator is a **manager**, not a coder. But model selection is **hardware-gated**: a model that is intellectually capable of the role may still be practically unusable on consumer hardware due to prompt-prefill latency.

**v2.12 replaces GPT-5.5 ($10/1M output) with Kimi K2.7 ($0.60/1M in) as default for all roles.**

### The Prefill Bottleneck (v2.2)

The orchestrator's system prompt (`plan.md`) is ~30KB. Combined with persona, memory, skills, and conversation history, each API call carries **100K–120K input tokens**. Before the model can generate its first output token, it must prefill (compute attention over) ALL input tokens.

On datacenter hardware (hundreds of GPUs with HBM), 120K token prefill takes <5 seconds. On a single consumer GPU (Jetson GB10, unified memory), it takes **200+ seconds** — and gets slower as conversation history grows.

**Real measured data (Qwen 3.6 35B on Jetson GB10, via LiteLLM :4000):**

| API call | Input tokens | Output | Latency | Notes |
|----------|-------------|--------|---------|-------|
| #33 | 116,338 | 298 | **313.3s (5m13s)** | ~1 tok/s generation |
| #34 | 116,673 | 220 | **319.4s (5m19s)** | Context grew → even slower |
| #35 | — | — | **HTTP 500 ×3** | LiteLLM/llama.cpp crashed |

This is a **nonlinear degradation spiral**: each turn adds messages → context grows → next turn's prefill takes longer → user gets frustrated, sends mid-turn messages → context grows further → eventual crash.

### Hardware-Gated Model Selection Matrix

| Orchestrator model | Prefill 120K tok | Gen speed | Viable on Jetson GB10? | Viable on DGX/cloud? |
|-------------------|-------------------|-----------|----------------------|---------------------|
| **Qwen 3.6 35B** (local llama.cpp) | 200+ sec | ~1 tok/s | ❌ **UNUSABLE** | ✅ (with enough GPUs) |
| **DeepSeek V4 Pro** (cloud) | <5 sec | 50-100 tok/s | N/A (cloud) | ✅ (but drifts on management — see below) |
| **Kimi K2.7** (cloud, $0.60/1M in) | <5 sec | 60+ tok/s | N/A (cloud) | ✅ **BEST** — management + code, cost-effective |
| **Claude Sonnet 4** (cloud) | <5 sec | 60+ tok/s | N/A (cloud) | ✅ — strong management, more expensive |

### Recommendation (v2.12)

**On Jetson GB10 / consumer GPU: DO NOT use local models for orchestrator.** The prompt prefill time makes it practically unusable (5+ min/turn, crashes at high context).

```yaml
# Hermes config.yaml — recommended (v2.12: GPT-5.5 removed, Kimi default)
model:
  default: kimi-k2.7-code     # orchestrator ($0.60/1M in)
  provider: custom:kimi

delegation:
  provider: custom:kimi        # sub-agents use Kimi by default
  model: kimi-k2.7-code
```

**GPT-5.5 REMOVED (v2.12):** $10/1M output was too expensive. Kimi K2.7 ($0.60/1M in) replaces ALL management roles. DeepSeek V4 Pro still used for code/search roles (developer #5-7, security, deployment).

**Why not Qwen 3.6 35B as orchestrator on Jetson:**
- Qwen is intellectually capable (strong instruction-following with thinking mode)
- But the orchestrator role requires processing 100K+ token prompts EVERY turn
- On a single Jetson GPU, 120K token prefill = 200+ seconds before generation starts
- After 2-3 turns, context growth triggers LiteLLM 500 errors (connection timeout)
- This is a **hardware constraint**, not a model quality issue

**Where Qwen 3.6 35B DOES work well on Jetson:**
- Short-context tasks: developer sub-agents (5-10K context), one-shot code generation
- OpenCode+ plan/build where compactor keeps context small
- Any role where input tokens stay under 20K

**Why DeepSeek V4 Pro struggles as orchestrator (separate problem):**
RL-trained on math/code tasks, not multi-turn management. With 363 lines / 25KB of orchestrator prompt, it loses focus, drifts on structured output, and struggles with 10+ tool calls per turn. It's an excellent developer, poor CEO. But at least it responds in seconds, not minutes.

### Model Routing Table (v2.4 — GPT-4.1 EXCLUDED, Kimi K2.7 added)

На 2026-06-15 доступны два основных провайдера: Kimi K2.7, DeepSeek V4 Pro.
GPT-5.5 исключён по стоимости, GPT-4.1 исключён по указанию пользователя.

#### Управление и надзор (Kimi K2.7)

| Role | Model | Why |
|------|-------|-----|
| **Orchestrator** | **Kimi K2.7** | Management, 10-phase cycle, instruction-following. NOT code. |
| **Requirements Analyst** (#1) | Kimi K2.7 | User dialogue, clarifications — language precision |
| **System Analyst** (#2) | Kimi K2.7 | 5 Whys, goal tree, WSM/AHP — analytics, not code |
| **Architect** (#4) | Kimi K2.7 | Topology, module contracts, design — structure over speed |
| **Auditor + Critic + Idea Gen + Knowledge Curator** (#10-13) | Kimi K2.7 | Creative analysis, pattern discovery, delegation quality, knowledge graph. **Fallback: DeepSeek V4 Pro** — proven in codemes_neo4j_repo-graph (Auditor 155s, Critic 144s, Idea Gen 196s with quality reports). |

#### Разработка и контроль (Kimi K2.7 + DeepSeek)

| Role | Model | Why |
|------|-------|-----|
| **Tech Lead** (#5) | **Kimi K2.7** | Planning, code review — strategic oversight |
| **Developer #1-4** (#6) | **Kimi K2.7** | Code, tests, debug — primary group. **Temperature: 0.1–0.3** |
| **Developer #5-7** (#6) | DeepSeek V4 Pro | Code, tests — secondary group. **Temperature: 0.5–0.8** |
| **Tester** (#8) | **Kimi K2.7** | curl/adb/logcat, autonomous testing |
| **Researcher** (#3) | DeepSeek V4 Pro | 1M context, iterative multi-source search. **Routes findings to Architect, Tech Lead, Developers, Security, Tester after Phase 3** |
| **Security** (#7) | DeepSeek V4 Pro | SAST, code analysis, vulnerability scanning |
| **Deployment** (#9) | DeepSeek V4 Pro | Shell, docker, health checks |

#### Правила переключения

1. **Model routing table is desired policy, not proof of runtime routing.** Before launching role-routed batches or observer checkpoints, run delegation capability preflight: inspect the live `delegate_task` shape and smoke-test one tiny child for the requested route.
2. **If explicit `model/provider` fields are available and smoke passes**, pass the model/provider from the table directly in the delegation call.
3. **If explicit routing is not available or smoke does not prove the route**, do not fabricate model-routed subagent output. Classify the phase as `DEGRADED` or `BLOCKED`, write a deviation/preflight artifact, and use `references/delegation-capability-preflight.md` + degraded mode safeguards.
4. **Оркестратор НЕ пишет код** — при позыве к `write_file` или `terminal(код)` → делегировать Developer'у only after capability preflight says delegation is usable for that role; otherwise continue locally only as an explicitly documented degraded fallback.
5. **DeepSeek — только код и поиск** — дрифтует на management-задачах (10-фазный цикл)
6. **GPT-4.1 ЗАПРЕЩЁН** — исключён из всех ролей
7. **GPT-5.5 УБРАН (стоимость)** — $10/1M output слишком дорого. Kimi K2.7 ($0.60/1M in) заменяет все management-роли.

#### Баланс токенов (на основе данных сессии e30edf, ~1.7M токенов, пересчитано v2.12)

| Модель | Ролей | Токенов | Доля |
|--------|-------|---------|------|
| DeepSeek V4 Pro | Researcher, Dev#5-7, Security, Deploy | ~700K | 41% |
| Kimi K2.7 | Orchestrator + все management + Tech Lead + Dev#1-4 + Tester + 4 observers | ~1.0M | 59% |

Стоимость полного цикла: **~$1.10** ($0.60 Kimi + $0.50 DeepSeek). $50 = ~45 циклов (было ~23 с GPT-5.5).
Подробный расчёт: `references/model-routing-cost.md`.

## Toolsets Pitfall (v2.1)

**`toolsets: []` in agent frontmatter = ALL tools, not "no tools".**

Python: `agent_def.toolsets or None` → empty list `[]` is falsy → becomes `None` (all tools enabled). This creates a dangerous mismatch: the orchestrator prompt says «your tools: delegate_task, todo, clarify, read_file, search_files» but the agent actually has 25+ tools available.

**Fix:** Always use an explicit list:
```yaml
toolsets: [delegation, todo, file, session_search, skills, clarify]
```

## Phase Lifecycle Contract (v2.1)

Each phase is a **contract** with three conditions. Before starting, verify ENTRY. Before declaring done, verify EXIT. When it fails, follow ROLLBACK.

See `references/phase-lifecycle-contract.md` for the full table.

See `references/phase-lifecycle-contract.md` for the full table.
See `references/memory-preflight.md` for the mandatory 5-layer pre-flight check.
See `references/context-compaction-recovery.md` for restoring a partially preserved orchestration cycle after context compaction and closing Phase 10 with an evidence bundle.
See `references/delegation-capability-preflight.md` for proving the live delegate_task schema/provider route before launching model-routed observers or developer batches.
See `references/delegation-route-repair-reload-boundary.md` for repairing Hermes delegation routing itself: same-session smoke can be stale; use fresh-process smoke plus scoped rollback.
See `references/agent-runtime-contract.md` for the `/agent plan` vs `delegate_task` runtime distinction and current `agent_id` gap.
See `references/clarify-bridge.md` for the sub-agent → parent clarify relay (ClarifyBridge in delegate_tool.py): thread-safe queue, 600s timeout, poll loop, orchestrator integration.
For long runtime projects, also run the VCS baseline + canonical plan readiness gate from `orchestration-cycle` → `references/vcs-plan-baseline-preflight.md` before resuming the next implementation slice after context compaction or error-ledger recovery.

```
Phase 6 (Implement):
  ENTRY:  plan.md exists; file ownership assigned
  EXIT:   all code complete + tests green
  ROLLBACK: git revert to pre-phase state

Phase 8.5 (Acceptance Test):
  ENTRY:  deployment verified; system operational
  EXIT:   traceability matrix complete; all 🔴 resolved or accepted
  ROLLBACK: return to Phase 6 for fixes
```

**Rule**: Never start a phase without ENTRY. Never declare a phase done without EXIT.

## Delegate Failure Protocol (v2.6)

When `delegate_task` fails or returns no usable output:

1. **Retry once** — same parameters (transient: timeout, network)
2. **Second failure** → retry with more explicit context (error message + hints)
3. **Third failure** → escalate to user via `clarify` (which phase, error, proposed fix)
4. **Never silently skip** — if a phase cannot complete, pause and report

Partial output handling: run managerial oversight check → red flag → return for rework. No red flag → accept with `<!-- PARTIAL: ... -->` note.

### Degraded orchestration mode — provider/model outage

If the user explicitly ordered the cycle to continue, but normal role delegation is blocked by provider/model routing errors or repeated child interruptions, the orchestrator may continue in **degraded mode** instead of stopping. This is not a shortcut: it requires stronger evidence.

Required safeguards:

1. Write a deviation note in `.observations/` or `docs/deviation-log.md` naming the failed agent/phase, blocker, and substitute path.
2. Keep phase artifacts separated even if the parent session performs the work locally.
3. Replace missing subagent review with real output: targeted tests, full regression, SAST/secrets scan, acceptance smoke, traceability matrix.
4. Final Phase 10 report must state the degradation clearly and decide whether objective gates still pass.
5. At the next phase, attempt to restore normal delegation with a small single-child smoke before launching batches.

See `references/degraded-orchestration-mode.md` for the case-study pattern and evidence bundle.

### Live Hermes delegation route repair reload boundary

When the task is to repair Hermes delegation routing itself, a same-session `delegate_task` smoke can keep failing after the disk fix because the parent Hermes process still has old imported tool/runtime code or old runtime config. Prove the fix with: RED regression test → minimal runtime/config fix with backup → targeted tests → **fresh Hermes process** smoke using explicit `model/provider` → touched-file regression → scoped rollback commands. Do not use `git restore .` in User's Hermes checkout; unrelated work is often present. See `references/delegation-route-repair-reload-boundary.md` for the smoke and rollback templates.

**Rule:** If a project doesn't have `AGENTS.md`, ask the user 6 questions and
generate one BEFORE starting work. See `references/memory-preflight.md`.

## Mid-Turn Steering Handler (v2.1)

User can send out-of-band messages `[OUT-OF-BAND USER MESSAGE — ...]` during delegation:

| User says | Action |
|-----------|--------|
| «стоп», «stop» | Cancel delegation immediately. Report phase + cancelled work. |
| Correction | Cancel/re-delegate with correction if in-flight; adjust next phase if done. |
| New task | Queue. Complete current phase first. |
| «что делаешь?» | Report active phase, sub-agent, ETA. |

**Rule**: Never ignore an out-of-band message.

**⚠️ Out-of-band + DeepSeek = connection error (2026-06-15):** Sending out-of-band messages during long `delegate_task` calls (120-180s) causes a double failure on DeepSeek V4 Pro: the turn gets `interrupted_by_user` AND the API stream fails with `Connection error`. The turn ends as `interrupted_during_api_call` — the user sees no response and re-sends, causing a loop. **Mitigation:** use `/steer` (doesn't interrupt), or warn the user when spawning long delegate_task: «Запускаю sub-агентов (2-3 мин). Не отправляй сообщения — используй /steer для корректировки.»

## Artifact Caching Rule (v2.1)

Sub-agents are stateless — their output is **lost** after delegation returns. To pass context:

1. **Read** the artifact with `read_file` after each phase
2. **Summarise** 2-5 key findings in the `context` field of the next `delegate_task`
3. **Include** the artifact path so the next sub-agent can read the full doc
4. **Never assume** a sub-agent remembers anything — re-inject critical context

```python
delegate_task(
  goal="Design architecture for X.",
  context="""
    Requirements: docs/requirements/slug.md
    Key: root cause = ADB reverse drops on USB reconnect
    System Analysis: docs/system-analysis/slug.md
    Selected alternative: cron watchdog (WSM 8.5/10)
  """,
  toolsets=[...]
)
```

## Pre-Flight Memory Check (v2.3 — MANDATORY before Phase 1)

Before **any** delegation, the orchestrator MUST run the 5-layer memory scan.
This prevents the most expensive failure pattern: re-discovering known facts.

| Layer | Action | Tool | Purpose |
|-------|--------|------|---------|
| 1. **Context** | Read `~/.hermes/AGENTS.md` | `read_file` | Environment, global pitfalls, port maps |
| 2. **Project** | Read `~/dev/codemes/<project>/AGENTS.md` | `read_file` | Project tech stack, commands, known pitfalls |
| 3. **Procedural** | Load relevant skills | `skill_view` | Workflows, how-to, API endpoints |
| 4. **Relational** | Query Neo4j for pitfalls | `mcp_*_search` | `Project→Pitfall→Solution` graph |
| 5. **Session** | Search past sessions | `session_search` | Prior art, decisions, patterns |

**Real cost of skipping:** 16-25 hours wasted re-discovering that Hermes Gateway API
was already configured on port 8643. The orchestrator and developer built 5
intermediate proxy layers on top of a working system because AGENTS.md was never read.

**When to run:** Before Phase 1 (requirements). Result informs context passed to ALL
sub-agents. Re-run light version (layers 1-3) before Phase 6 (implementation).

**Workspace structure** (all projects):
```
~/dev/codemes/
├── AGENTS.md                   ← universal (environment, global pitfalls)
├── <project>/AGENTS.md         ← project-specific (tech, commands, pitfalls)
```

**Rule:** If a project doesn't have `AGENTS.md`, ask the user 6 questions and
generate one BEFORE starting work. See `references/memory-preflight.md`.

## Pitfalls

- **Model routing requires capability preflight, not wishful context (v2.9).** A routing table in the prompt does not prove the live delegation tool can enforce `model/provider` for children. Before model-routed observers/developer batches, inspect current schema and run a tiny smoke probe for the **intended** route. A default `delegate_task` smoke proves only that some child route works — not that `custom:kimi:kimi-k2.7-code` or another role route works. If the route is unproven, classify as `DEGRADED`/`BLOCKED`, write `docs/tests/delegation-preflight.md` or `.observations/delegation-preflight.md`, and use degraded safeguards instead of presenting local work as independent subagent output. Do not patch live `~/.hermes/config.yaml` or `~/.hermes/hermes-agent` for route repair unless the user allowed the side effect and there is a clean branch/worktree or equivalent rollback boundary. See `references/delegation-capability-preflight.md`.
- **Batch delegation to Kimi K2.7 (v2.12).** Kimi batches of 8+ tasks may cause interruptions — limit to 5-6 tasks. Use DeepSeek for larger batches. If batch fails, re-launch tasks individually on verified models.
- **`cp -r dir/*` does NOT copy dotfiles (v2.5).** Templates like `.env.template` are silently skipped by `cp -r dir/*` because `*` glob excludes dotfiles by default. **Fix:** use `shopt -s dotglob; cp -r dir/* dest/; shopt -u dotglob` in bash scripts. This cost 1 full rework cycle in codemes_1 (BUG-01 in acceptance testing).
- **Integration ownership void (v2.14).** The Plan assigns per-FILE ownership but NO ONE owns the integration points — how module A calls module B, what dataclass they share, which parser the orchestrator actually imports. Result: orphan modules built in isolation, incompatible dataclass hierarchies, the orchestrator uses its own regex instead of the tree-sitter parser two other devs built. 10.8× bloat (8,400 lines → 780-line MVP). **Prevention:** Tech Lead `grep`s for imports between modules after Phase 6; Architecture Module Contracts specify CONSUMER paths, not just PRODUCER APIs; Plan adds "Integration: who wires A→B?" row. Full case study: `orchestration-cycle` → `references/codebase-graph-full-cycle-case-study.md`. (2026-06-17, codemes_neo4j_repo-graph cycle.)
- **GPT-5.5 REMOVED (v2.12, cost).** $10/1M output was too expensive. Replaced by Kimi K2.7 ($0.60/1M in) for ALL roles. DeepSeek for code/search only. See plan.md Model Routing Table.
- **`max_tokens` vs `max_completion_tokens`.** GPT-5.x models reject `max_tokens` — but Hermes auto-converts when `base_url` hostname is `api.openai.com` (see `_max_tokens_param` in `run_agent.py`). Custom proxies at different hostnames won't get this conversion. Kimi K2.7 uses standard `max_tokens`.
- **Skipping pre-flight = 80% time wasted on re-discovery.** Always run the 5-layer scan.
- **Root cause over band-aids.** When a system prompt fix masks a missing API (e.g.,
  adding "You are Hermes" to ChatViewModel instead of launching Hermes Gateway),
  the orchestrator MUST escalate to root cause analysis (Phase 2), not accept the patch.
  User explicitly corrects this pattern: "не надо менять системный промпт. надо
  решать корневую проблему."
- Don't skip the verification gate (Phase 6.5)
- Developer needs isolation — no web search, ask the right agent instead
- Senior agents (2,3,4,10) must persist — killing them loses context
- Orchestrator doesn't code or analyze — coordinate AND verify, don't do the work
- Subagents are not durable — interrupted parent kills children
- Subagent summaries are self-reports — always verify side-effect claims
- **Context loss between orchestrator and sub-agents** — «test autonomously» in memory ≠ in context. Pass EVERY user preference as explicit context.
- **Tester context** — must include all 3 requirement sources. Tester CANNOT search for them.
- **Red flag → don't pass the gate** — return agent for rework, don't silently accept incomplete work
- **Auditor watches delegation, not just errors** — wrong toolsets, missing context are delegation failures
- Respect documented requirements — if requirements prescribe a solution (e.g., Tailscale), use it
- Test autonomously — use real tool calls, never ask user to verify
- **System Analysis scope creep (v2.13).** The System Analyst must NOT produce pseudocode, file lists, or architecture sketches — those belong to Architecture and Plan. The Dev Task Spec should define boundaries, I/O, and acceptance criteria — not class hierarchies. Also: AHP is only valuable when constructed from independent pairwise judgments. If the AHP matrix is derived mathematically from WSM weights (CR=0), it adds no new information and ~40 lines of noise. Report "AHP confirms WSM winner A2" in one sentence. SMART goal must be readable in one breath — move per-metric thresholds to a separate table.
- **Orchestrator ≠ Developer model** — DeepSeek Pro для кода (developers, researcher, deployment, tester). Orchestrator uses Kimi K2.7 ($0.60/1M in); local models fail on 100K+ token prompts. GPT-5.5 removed due to cost. See Orchestrator Model Selection (v2.2).
- **Every phase has ENTRY/EXIT/ROLLBACK** — verify before starting, verify before declaring done
- **Tree-sitter lazy-init with regex fallback (v2.15).** When integrating an optional heavy dependency (tree-sitter, sentence-transformers), use lazy-init with sentinel: `_parser = None` -> `_get_parser()` imports on first call -> sets `_parser = False` on ImportError -> returns `None` for fallback path. The orchestrator `_parse_file()` tries tree-sitter first, falls back to regex if unavailable. Same pattern for embeddings: `EmbeddingGenerator` lazy-init in `_get_embedder()`, batch-encode in `full_scan()` after parsing, attach to parsed entities before Neo4j write. This pattern enabled CALLS (0->1,976) and embeddings (0->1,135) without breaking the regex-only deployment. (2026-06-17, codemes_neo4j_repo-graph cycle.)
- **Driver-close anti-pattern (v2.15).** Testing a Neo4j connection by calling `driver.close()` after the test silently breaks all subsequent writes. Fix: use `with driver.session() as s: s.run("RETURN 1")` instead. (2026-06-17, run_watcher.py BUG-1.)
- **Sub-agent terminal simulation (DeepSeek V4 Pro)** — sub-agents with `toolsets: ["terminal"]` may SIMULATE command execution rather than actually running commands. Signals: (a) `tool_trace: []` in results, (b) unrealistic `duration_seconds` (1-3s for scripts that take 30+s), (c) summary shows commands formatted in `<terminal>` tags as echo rather than real output. **Fix:** Verify with a simple `curl` health check sub-agent first. If simulated, fall back to telling the user the exact command to run. This is a model quirk, not a tool bug — DeepSeek V4 Pro in sub-agent mode sometimes defaults to describing actions rather than executing them.
- **Check the live orchestrator toolsets before assuming capabilities.** Current `plan.md` should include `terminal` (`toolsets: [delegation, todo, file, session_search, skills, clarify, terminal]`) so the orchestrator can verify subagent claims with real `git`, `pytest`, `curl`, logs, and health checks. Older plan profiles omitted `terminal`, leaving the orchestrator blind. If `terminal` is absent, do not fake verification: either patch the profile with explicit approval, switch to a capable agent, or delegate verification to a proven child and then record the degradation.
