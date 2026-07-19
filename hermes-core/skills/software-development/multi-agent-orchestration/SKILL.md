---
name: multi-agent-orchestration
description: "Architect and run multi-agent workflows: orchestrator (plan agent) + 20 specialized sub-agents covering the full development lifecycle."
version: 2.32.0
author: Hermes Agent + Pavel
license: MIT
metadata:
  hermes:
    tags: [orchestration, multi-agent, subagent, plan, architecture, developer, security, deployment, testing, auditor, jidoka, standard-work]
    related_skills: [subagent-driven-development, plan, architecture-design, requirements-analysis, build-engineering-standards, test-driven-development, secure-coding, orchestration-cycle]
---

# Multi-Agent Orchestration

Use this skill when designing or running multi-agent workflows — an orchestrator
agent coordinates a team of specialized sub-agents through the full development
**v2.20 adds Tech Lead v3 — sub-orchestrator for Phase 6. Tech Lead now creates the plan (Phase 5) AND executes it (Phase 6) by spawning developer-agents via `delegate_task(role='orchestrator')`, managing Skeptic→Pragmatic→Creative→Maverick escalation, running Review Swarm (5 reviewers per PASS), and merging results. Based on MetaGPT ProjectManager pattern (ICLR 2024) + hierarchical orchestration (Google ADK, CrewAI). Fallback: orchestrator direct execution on timeout. See `hermes-cross-stack` skill → `references/desktop-agent-activation-vertical.md` for the sub-orchestrator pattern.

**v2.21 research: Tech Lead v4 SOTA analysis.** Deep research against 15 SOTA coding agent papers (2024-2026) identified 7 structural blind spots in v3 and proposed v4 improvements: (1) Dynamic DAG (DynTaskMAS) — DAG updates in real-time from Phase 6 feedback, (2) Context Engineering Stack (Anthropic 2026 — 55% faster, 40% fewer errors) — 4-layer context with compaction/routing/budgets, (3) Spec Inference (SpecRover ICSE 2025) — infer current spec from code before planning, create delta-based StandardWork, (4) Closed-Loop Feedback (RLEF ICML 2025) — test results trigger plan revision, not just developer escalation, (5) AST-based Interface Verification (AutoCodeRover) — signature/protocol/return-type checks beyond grep, (6) Self-Evolution Engine (Darwin Godel ICLR 2026) — Neo4j CycleMetric nodes + pattern mining + self-modification, (7) Cost-Aware Execution Tracking — per-SW budget variance monitoring. Also proposes 3 new agents: Code Navigator (HyperAgent pattern), Test Designer (AgentCoder adversarial pattern), Integration Checker (per-module, continuous). Priority: P0 = Closed-Loop Feedback + Dynamic DAG. Full research + schemas + priority matrix: `references/techlead-v4-sota-research.md`.

**v2.23 — Adaptive Pre-Implementation Depth + P1 Research (2026-07-03).** Deep investigation into whether Requirements Agent, System Analyst, and Deep Plan Researcher are redundant. Key findings: (1) **System Analyst Phase 2 duplicates Tech Lead Phase 5 by 60-70%** — SMART goal→DAG, alternatives→model routing, developer task→StandardWork, goal tree→DAG. Recommendation: merge Phase 2 analysis into Tech Lead; keep Phase 6.5 verification as independent agent ("did we build the RIGHT thing?"). (2) **Pre-implementation token ratio is 1.5-2.5x implementation** (90-235K pre vs 50-150K impl), while SOTA systems (ChatDev, MetaGPT, OpenHands) run at 0.05-0.5x. (3) **Adaptive triggering needed**: bugfix→skip Phases 1-3 (Developer Query on-demand); known-domain feature→lightweight Phase 1 (2-3 Qs only, skip obvious questions already in AGENTS.md); architectural change→full pipeline. (4) SOTA evidence: Google multi-agent study shows 39-70% performance DROP on complex tasks with multiplied token spend; "Cut the Crap" (arXiv:2410.02506) shows average agentic workflow loads 3-5x more context than necessary. (5) Requirements Agent asks ~7K tokens of questions already answered in AGENTS.md/capability_report.json — only acceptance criteria and out-of-scope questions are unique value. Also: P1 deep dive on Context Engineering Stack (5-component: Registry→Router→Compactor→Budget→Auditor, with per-agent token budgets) and Interface Compatibility Verification (3-level: AST signature check → Protocol conformance → Runtime import+call test, replacing grep-only). Full analysis + task classifier logic + SOTA comparison tables + code examples: `references/adaptive-pre-implementation-depth.md` and `references/context-engineering-interface-verification.md`.

**v2.30 — Model routing drift audit + plan3 fully-local validation + start-llama.sh $HOME fix (2026-07-15).** Systematic audit of plan3's "Fully Local" design intent found 5 agents on cloud providers (3× deepseek-v4-pro, 2× kimi-k2.7-code BROKEN HTTP 400), 13 with inconsistent provider naming, and registry.json with 43 agents still on cloud from the plan2 era. **Root cause:** frontmatter and registry.json were copied from plan2 during fork and never updated — no automated enforcement of local-only policy. **5-source validation methodology formalized:** (1) sub-agent frontmatter model/provider, (2) registry.json, (3) physical llama-server health :8101/:8102/:8103, (4) LiteLLM config model→server mapping, (5) start-llama.sh operational health (PID files + process count + $HOME bug detection). **Routing table updated:** Reasoning model changed from `qwen3.6-35b` to `agents-a1-abliterated` (Agents-A1 APEX I-Quality, :8102, GAIA 96) — reflects 2026-07-09 model swap. **start-llama.sh $HOME fix:** script used `${HOME}` for model paths and PID dirs, but Hermes terminal sets `$HOME=/home/user/.hermes/home` → status reports all models as "не запущен" even when running. Fixed with `REAL_HOME=$(getent passwd "$(id -un)" | cut -d: -f6)`. **Files fixed:** 5 frontmatter patched, 13 normalized, registry.json 43 agents → local, start-llama.sh 5 `${HOME}` → `${REAL_HOME}`. **Script updated:** `scripts/validate-plan3-models.py` — now 5-check validation + auto-fix + $HOME bug detection. End-to-end tool-use test confirmed: all 3 models respond + tool_calls work. Validation reference: `references/plan3-model-routing-validation.md`.

**v2.28 — SimRL empirical validation (2026-07-04).** 68-test empirical evaluation of Qwen-AgentWorld (SuperQwen APEX v3, port 8103) for code verification — the first systematic measurement of what SimRL can actually do. Key findings: **97% accuracy on single-step predictions** (Python exception types/messages: 15/15 = 100%, terminal commands: 8/8 = 100%, DevOps scenarios: 6/6 = 100%, hard SWE edge cases: 12/12 = 100%). But **FAILS on multi-step state tracking** — 8-step arithmetic counter predicted value at step 2 instead of step 8 (compounding errors, the classic sim-to-real gap). AgentWorldBench score 56.39 uses LLM-as-judge rubric scoring (GPT-5.2, 5 subjective dimensions), NOT exact-match — single-step accuracy is significantly higher than the benchmark suggests. **CRITICAL architectural recommendation: SimRL is a PRE-FLIGHT CHECK, not a VERIFICATION GATE.** Pattern: SimRL predicts → Developer checks prediction → Real execution. NEVER use SimRL as sole verification — always follow with real execution. Also: 3 of 4 test "failures" were false negatives (English vs Russian locale, incorrect test expectations, non-executable test code) — always verify test correctness before declaring model failure. Full methodology, per-domain results, testing scripts, and Qwen-AgentWorld research analysis: `references/simrl-empirical-evaluation.md`.

**v2.27 — P2 review fixes + agent config review methodology (2026-07-03).** Systematic review of P2 implementation in `plan3/techlead-agent.md` (611 lines) found 5 issues: (1) **BUG** — Neo4j property name mismatch: Phase 11.1 CREATE used `budget_tokens` but 11.2 MATCH queried `m.budget` → pattern mining silently returned 0 results. (2-4) **GAPs** — StandardWork example and Developer Handoff template missing Spec Delta fields; "Запрещено" section didn't enforce Spec Inference as mandatory. (5) Cross-reference from "После деплоя" to Phase 11. All fixed. **Review methodology formalized:** 5-level check for agent prompt files — property consistency (CREATE/MATCH name match), example completeness (new features in examples not just instructions), template cross-reference (handoff includes new fields), prohibition enforcement (Запрещено covers mandatory steps), section cross-reference. Key insight: agent prompt files are code — they have write/read contracts, template instantiation, and enforcement. Review with same rigor. Details: `references/techlead-v4-p2-implementation.md` §Post-implementation review.

**v2.26 — P2 IMPLEMENTED: Spec Inference + Enhanced Self-Evolution Metrics (2026-07-03).** Spec Inference (SpecRover ICSE 2025 pattern) implemented in `plan3/techlead-agent.md` as Step 0.3 — before creating StandardWork, Tech Lead reads existing code via `read_file` + Neo4j queries, infers current specification (methods, signatures, exceptions, callers), compares with target architecture, creates **Spec Delta** JSON with `action: new|refactor|reuse` and `reuse_potential` (0.0–1.0). Documented in plan as `§SPEC DELTA` section. Prevents "create from scratch" when 60% already exists. Phase 11.1 enhanced from text-only "analyze" to actual Neo4j `CycleMetric` node creation via curl — 15 fields including `budget_tokens` for variance calculation. Frontmatter and role list updated. Files modified: `~/.hermes/agents/plan3/techlead-agent.md` (+78 lines). Implementation details: `references/techlead-v4-p2-implementation.md`.

**v2.25 — Tiered Schema IMPLEMENTED + plan3.md synchronized + validated (2026-07-03).** Designed and deployed the 3-layer structured research output schema + Tech Lead filtering pipeline. **Tiered Schema:** Layer 1 (structured core — mandatory: findings with enum `category` for routing + free-text `finding` for content), Layer 2 (conditional — pitfalls/benchmarks/alternatives when applicable), Layer 3 (unstructured_notes — escape hatch for meta-reasoning, debates, caveats; read by Architect/SA, NOT delivered to Developer). **Cross-cutting `must_see` flag:** hard constraint on Tech Lead filtering — prevents false negatives for pitfalls, security, high-confidence, platform-specific findings. **Tech Lead Step 4.3:** 5-pass EXIT-style relevance filtering (must_see → preserve_categories → tag_match → dependency → high_confidence+relevance). **ACON feedback:** per-cycle filter rules evolve based on developer requests for filtered-out findings. **plan3.md synchronized with 8 changes:** (1) Phase 3 structured output header + "Who reads what" table, (2) all GATE B/C/D refs → `.json`, (3) GATE C 7 structured completeness checks, (4) Phase 4 Architect Trio research input column, (5) Phase 5.5 `.json` + `schema_version` check, (6) Phase 6 filtered delivery block with must_see/ACON/escape hatch, (7) checkpoint table → `.json` refs, (8) routing table replaced with data-driven auto-routing via `routing_target` field. **Validation: 57/57 checks passed** across 6 files (schema 11, scripts 2, deep-plan-researcher 13, techlead 9, plan3 22). **Files created:** `~/.hermes/schemas/research-output-v1.json`, `~/.hermes/scripts/research_filter.py`, `~/.hermes/scripts/research_json_to_md.py`. **Agent files modified:** `deep-plan-researcher.md`, `techlead-agent.md`, `plan3.md`. Key design insight: `category` is enum for deterministic routing, `finding` is free text for research freedom — preserves both machine-parseability and research creativity. Full design rationale + plan3.md 8 changes + auto-routing table + validation details: `references/tiered-schema-research-output.md`.

**v2.24 — Context Compression SOTA + "Compress, Don't Exclude" principle (2026-07-03).** Deep research into compression mechanisms proposed by scientific community and frontier companies. Identified 8 categories: (1) Extractive (LLMLingua, EXIT — sentence/token filtering), (2) Abstractive (Anchored Iterative Summarization from Factory.ai — incremental merge into persistent session state, 95% info retention vs 60-70% naive), (3) Structured (ContextEvolve 3-agent decomposition — 33% better/29% fewer tokens; Structured Output Contracts — 30-83% overhead reduction), (4) Hybrid (ACON — failure-driven compression guidelines, 26-54% peak reduction; Kaizen rules = ACON guidelines), (5) Eviction (priority-based token budget enforcement), (6) Externalization (Tool Output Sandboxing — 315KB→5.4KB, 98% reduction), (7) Linguistic (Caveman — drop filler keep technical, ~75% output reduction), (8) KV-cache sharing (TokenDance — not applicable, external APIs). Designed 4-level compression stack for our pipeline: L1 Structuring (JSON contracts at creation), L2 Filtering (EXIT-style at delivery), L3 Compression (anchored iterative + ACON + caveman when over budget), L4 Externalization (sandbox + disk + Neo4j always). **CRITICAL CORRECTION**: initially proposed excluding research/system-analysis from developer context — this was WRONG. In BDUF pipeline, developer makes micro-decisions (algorithm choice, library, edge case handling) that REQUIRE research findings and system analysis root cause. Correct approach: COMPRESS + FILTER by SW relevance, never EXCLUDE. Full taxonomy + 8 categories + 4-level stack + implementation priority matrix + per-agent token budgets: `references/context-compression-sota.md`.

**v2.22 — P0 IMPLEMENTED (2026-07-03).** Dynamic DAG + Closed-Loop Feedback applied to all 4 files: `plan2/techlead-agent.md` (v3: +263 lines → 839), `plan3/techlead-agent.md` (v2: +139 lines → 535), `plan2.md` (+12 changes → 1228), `plan3.md` (+15 changes → 1243). Changes: (1) Static `Dependency DAG` → `Dynamic Task Graph` with dag-state.json artifact (machine-readable, versioned, updated at 5 event types), (2) `§6.5 Feedback Loop Closure` — 6.5a Feedback Collection (JSON schema per SW), 6.5b Pattern Detection (6 patterns after every 2nd SW), 6.5c Plan Revision Protocol, 6.5d Loop Guards (5 guards: max 3 attempts/SW, max 2× total retries, 150% budget cap, same error 3× → redesign, >3 DAG updates → freeze), (3) `Phase 11: Self-Evolution` with **user-gated governance** — 11.1 Metrics Collection (auto → Neo4j CycleMetric), 11.2 Pattern Mining + Proposal Saving (auto → `(:SelfModificationProposal {status: "pending"})` in Neo4j), 11.3 Apply Self-Modification (**ONLY on explicit user request** — user says «примени self-modifications» → clarify to pick proposals → apply approved → `SET status="applied"`), 11.4 Template Evolution (only within 11.3). Neo4j schema: `SelfModificationProposal` node with `DERIVED_FROM → CycleMetric`. Lifecycle contracts updated: Phase 5 EXIT now requires dag-state.json; Phase 6 ENTRY requires dag-state.json exists; Phase 6 EXIT requires dag-state.json updated + feedback collected + loop guards respected. Implementation details + dag-state.json schema: `references/techlead-v4-p0-implementation.md`.

Previous: v2.18 adds JidokaEvaluator (Gate 6b) and Tech Lead v2 with StandardWork contracts, ownership matrix, import contracts, structured developer handoff, and cost-aware routing. See `references/techlead-v2-standard-work.md` for contract formats, templates, and evaluation workflows.**

Previous addition: v2.10 clarified the runtime contract: `/agent plan` applies a prompt/toolset/model preset to the live parent `AIAgent`; `delegate_task` creates isolated children but does not currently accept `agent_id`, so subagent personas must be injected explicitly via goal/context/toolsets/model/provider until runtime support exists.

**Agent files:** `~/.hermes/agents/` — `plan.md` (orchestrator) + 10 sub-agent personas.

### Navigational pitfall — `plan` SKILL vs `plan*.md` AGENT FILES

When the user says «опиши plan2» or «как работает plan3», they mean the **orchestrator agent files** at `~/.hermes/agents/plan2.md` / `plan3.md` — NOT the `plan` skill (`skill_view('plan')`). The `plan` skill is for writing markdown implementation plans (BDUF bite-sized tasks). The `plan*.md` files are full multi-agent orchestrator definitions (29 agents, 13+ phases, model routing, gates). Always `read_file('~/.hermes/agents/plan<N>.md')` when the user references a plan agent, not `skill_view`. Three versions exist: `plan.md` (v2, cloud), `plan2.md` (v2 + Capability Gate + PEP/PDP + Tech Lead sub-orchestrator), `plan3.md` (v3, local multi-model). See `references/orchestrator-file-evolution.md` for the full diff history and timeline.

For adapting this orchestrator to **OpenCode+** (local llama.cpp + LiteLLM), see `references/opencode-plus-orchestrator.md`.

For external orchestrator design patterns (Claude Code, Cursor IDE, Codex, L-TPS, ReWOO) and their applicability to plan2, see `references/external-orchestrator-patterns.md`. Key inspirations: L-TPS (Jidoka evaluator, Kaizen ledger, Standard Work contracts), Cursor (recursive ownership, handoff propagation), Claude Code (coordinator 4-phase), ReWOO (parallel execution pattern). Key differences: `task` tool instead of `delegate_task`, `build` agent plays multiple specialist roles, no per-call model routing, agent config in `opencode.json`.

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
    context="Task: ...\nArtifacts to produce: docs/requirements/<slug>.md\nUser preference: test autonomously; do not ask Pavel to verify.",
    toolsets=["clarify"],
    model="kimi-k2.7-code",
    provider="custom:kimi",
    role="leaf",
)
```

If true role-based child loading is required, the runtime feature should be explicit (e.g. `delegate_task(agent_id="requirements-agent", ...)`) and tested separately. Until then, treat `~/.hermes/agents/*.md` as top-level `/agent` presets plus source material for prompts, not as automatically addressable child-agent identities.

When presenting agent architecture to Pavel, use the **visual chain format** (phases
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
| 5 | Tech Lead | `techlead` v3 🏭 | StandardWork contracts, ownership matrix, import contracts, dependency DAG, cost-aware routing, Jidoka evaluation criteria. **v3: also executes Phase 6** — spawns developers via `delegate_task(role='orchestrator')`, manages escalation (Skeptic→Pragmatic→Creative→Maverick), runs Review Swarm (5 reviewers), merges results. Sub-orchestrator for entire dev pipeline. | No |
| 6 | Implementation | `developer-1…7` | RED→GREEN→REFACTOR. Gets StandardWork contract + import contracts + Kaizen rules in structured handoff. Stubborn, can break rules. No web access | No |
| 6a | **Integration Gate** | **`devops-engineer`** 🛠️ | Verifies ALL modules cross-connected: grep imports against Tech Lead's import contracts, shared dataclasses, orchestrator actually calls the right parser. | No |
| 6b | **Jidoka Gate** | **`jidoka-evaluator`** 🔍 | Independent skeptic: checks EACH developer result against StandardWork acceptance criteria. Runs real verification commands. Returns PASS/FAIL with specific criterion-level issues. Gate between developer output and Tech Lead acceptance. | No |
| 6.5 | Verification | `system-analyst` | 4 checks: spec, goal tree, root cause, abstraction. Deviation routing | — |
| 7 | Security | `security-agent` | SAST gate, secret scanning, dependency audit. Protects the TEAM | No |
| 8 | Deployment | `deployment-agent` | Deploy + health check. Failure → return to Phase 1–2 | No |
| 8.5 | **Acceptance Testing** | **`tester-agent`** 🧪 | Autonomous testing against 3 requirement sources. Traceability matrix. **NEVER delegates testing to user.** Artifact: `docs/tests/<slug>.md` | No |
| 9 | Post-Deploy | `researcher` | Evidence collection → hypothesis validation → statistical analysis | — |
| 10 | Iterate + Audit + Critic + Ideas + Knowledge + AFlow comparison | **Orchestrator + Auditor + Critic + Idea Generator + Knowledge Curator** | Metrics, retrospective. **Four reports + AFlow comparison:** Auditor (process+info), Critic (cleanup+simplify), Idea Generator (unheard ideas+ADAS mutations), Knowledge Curator (Neo4j state+cross-cycle links). AFlow comparison: main plan2 vs alternative workflow from parallel MCTS search. | — |
| **PARALLEL** | **AFlow Variant** | **AFlow Orchestrator** | MCTS search over plan2 phases-as-Operators. Returns best-found alternative workflow. Compared to main plan2 in Phase 10. | No |

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

1. Pavel's preference «тестируй сам» lives in MEMORY — which sub-agents CANNOT access
2. Orchestrator delegates without passing this requirement in context
3. Sub-agent (Deployment or Developer) interprets «проверь» as «health check only» — not «verify against requirements»
4. Sub-agent tells user: «проверь сам с телефона»
5. Auditor had no check for this pattern — violation undetected

**Fix (v2.0)**: dedicated Tester with NON-NEGOTIABLE autonomous execution mandate +
Orchestrator managerial oversight at every quality gate + Auditor delegation quality checks.

## Plan3 — Local Multi-Model Variant

Plan3 is a fully-local variant of this orchestrator, using three specialized models on DGX Spark instead of a single cloud model:

| Role Type | Model | Provider | Server | Benchmarks |
|-----------|-------|----------|--------|------------|
| **Reasoning** (анализ, планирование, observers) | `agents-a1-abliterated` | `custom:local` | :8102 | GAIA 96.0, IFBench 80.6, IFEval 94.8, VLM |
| **Coding** (код, терминал, деплой) | `nex-n2-mini` | `custom:local` | :8101 | SWE-Bench 74.4, Terminal-Bench 60.7 |
| **Simulation** (симуляции сред) | `agentworld` | `custom:local` | :8103 | AgentWorldBench 56.39 |

> **Model swap (2026-07-09):** Reasoning model changed from `qwen3.6-35b` to `agents-a1-abliterated` (Agents-A1 APEX I-Quality, same GGUF on :8102). `qwen3.6-35b` remains as a LiteLLM alias to the same server but agents should use `agents-a1-abliterated` in frontmatter. All 18 sub-agent frontmatter files and registry.json were validated and corrected on 2026-07-15.

Key differences from plan2:
- **Fully local** — $0/cycle, все данные остаются на DGX Spark
- **Model routing** — каждый `delegate_task` включает `model` и `provider` по таблице выше
- **Model routing drift is the #1 configuration failure mode** — see Pitfall §model-routing-drift and run `scripts/validate-plan3-models.py` (5-check validation: frontmatter + registry + servers + start-llama.sh + LiteLLM) before any cycle.
- **Fugu mode** — быстрый пайплайн Thinker(Qwen3.6)→Worker(Nex)→Verifier(Qwen3.6)→Synthesizer (~11s)
- **Fusion mode** — параллельный анализ Qwen3.6 ∥ Nex → Synthesizer (~8s)
- **Context budget** — урезанный промпт оркестратора (~20K вместо 100K токенов), полная документация в навыке

Full specification: `references/plan3-local-multi-model-orchestrator.md`
Agent files: `~/.hermes/agents/plan3.md` + `~/.hermes/agents/plan3/*.md` (18 sub-agents)

## Parallel Phase Execution

See `references/memory-preflight.md` for the mandatory 5-layer pre-flight check.
via `delegate_task(tasks=[...])` — they have no mutual dependencies.

**Research-first variant (v2.13):** When the user explicitly orders «сначала research», swap Phase 3 before Phase 1. Order: 0 → 3 → 1 → 2 → 4 → ... Inject the completed research artifact into Phase 1 context with key findings summary. This is documented in `orchestration-cycle` skill §Research-first variant.

Phases 4 (Architecture) and 5 (Tech Lead) are **sequential** — architecture must finish
before tech lead can plan implementation.

## Cross-Phase Context Passing

**SDB (Stochastic-Deterministic Boundary) for plan2:** Every orchestrator decision that becomes a system action should follow the four-part contract: Proposer (LLM plan) → Verifier (deterministic check) → Commit (durable write to Neo4j or disk) / Reject (typed signal). See `references/meta-agent-papers-2025-2026.md` for the SDB Architecture (Srinivasan, 2026 — formal propose/verify/commit/reject contract), AFlow (Zhang et al., ICLR 2025 Oral — MCTS over workflow DAGs), ADAS (Hu et al., ICLR 2025 — evolutionary search over agent architectures), and FoT (Fricke et al., 2026 — dynamic reasoning framework with parallel execution and caching). All four papers now have concrete implementations or documented relationships to plan2: SDB in observer checkpoints, AFlow in parallel orchestrator, ADAS in Idea Generator mutations, FoT as candidate runtime for plan2 phases.

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

This lets Pavel answer everything in one reply and unblocks the cycle immediately.

### Observer spawning + AFlow parallel (v2.17)

The four-observer pattern (Auditor #10 + Critic #11 + Idea Generator #12 + Knowledge Curator #13) was
validated in production. AFlow Orchestrator (#14) runs in parallel from Phase 0. Results:

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

**v2.17 fix — Neo4j-only persistence (2026-06-26):** v2.16 used a hybrid approach (files on disk + Neo4j), but files prevent cross-cycle querying, deduplication, and relationship traversal. v2.17 switches ALL observers to **Neo4j-only**: each observer `CREATE`s a node directly via `curl` at every checkpoint. In Phase 10, observers query Neo4j (`MATCH`) instead of reading files.

**Neo4j schema (all observers):**

```cypher
(:AuditFinding)          ← Auditor
  {cycle, phase, phase_name, severity, finding, evidence, recommendation, timestamp}
  -[:FOUND_IN]->(:Phase)

(:CriticFinding)         ← Critic
  {cycle, phase, category, finding, root_cause, preventive, timestamp}
  -[:FOUND_IN]->(:Phase)
  -[:SAME_ROOT_CAUSE]->(:CriticFinding)

(:Idea)                  ← Idea Generator
  {cycle, phase, category, idea, source, potential_value, target, timestamp}
  -[:INSPIRED_BY]->(:KnowledgeEntity)

(:Mutation)              ← Idea Generator (ADAS)
  {target, change, rationale, expected_impact, confidence, status, timestamp}
  -[:APPLIES_TO]->(:Phase)

(:KnowledgeEntity)       ← Knowledge Curator (already exists, 250+ nodes)
  -[:RELATES_TO {predicate}]->(:KnowledgeEntity)

(:AFlowVariant)          ← AFlow Orchestrator
  {cycle, task, workflow, phases[], estimated_score, iterations, innovations, timestamp}
```

**Observer agent files (created/updated 2026-06-26):**
- `~/.hermes/agents/auditor.md` — SDB contract, Neo4j curl templates, cross-cycle MATCH queries, auditor_memory.md auto-generation
- `~/.hermes/agents/critic.md` — 3-question analysis, Neo4j CREATE, `[:SAME_ROOT_CAUSE]` links
- `~/.hermes/agents/idea-generator.md` — ADAS-inspired `(:Mutation)` proposals, 4-axis analysis, `[:INSPIRED_BY]` links
- `~/.hermes/agents/knowledge-curator.md` (updated) — `+terminal` tools, Neo4j MERGE templates, deduplication queries
- `~/.hermes/agents/aflow-orchestrator.md` (NEW) — MCTS over plan2 phases-as-Operators, heuristic evaluation, `(:AFlowVariant)` in Neo4j
- `~/.hermes/auditor_memory.md` (updated) — now a readme/quick-ref pointing to Neo4j as primary storage

**Toolsets (Neo4j-only):** All observers use `["file_ro", "search_files", "session_search", "terminal"]` — `terminal` for curl to Neo4j, `file` removed. Idea Generator adds `["skills", "memory"]`. Knowledge Curator keeps `["skills", "memory"]`.

See `references/observer-persistence-problem.md` for the v2.5 discovery that observers are stateless.
See `references/resumable-observer-supervisor.md` for the target ObserverSupervisor design.
See `references/first-observer-cycle.md` for the codemes_1 case study.
See `references/degraded-orchestration-mode.md` for exception protocols.

## Escalation Gateway Pattern

Subagents CANNOT use `clarify`. Exceptions: `requirements-agent` (user bridge), `techlead` v2 (production decisions). All others escalate through the chain:

```
developer → jidoka-evaluator → techlead → researcher → architect → enterprise-architect → system-analyst → requirements-agent → USER
   ↑ each level can answer OR escalate further                                    ↑ clarify tool (requirements-agent + techlead v2 only)
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

## SimRL Agent — On-Demand Simulation in Plan3

SimRL (`plan3/sim-rl-agent`) uses **Qwen-AgentWorld** (AgentWorldBench 56.39) and is **NOT a fixed phase** in the 10-cycle BDUF pipeline. It's an **on-demand external agent** — the orchestrator delegates it explicitly when environment simulation is needed. This is by design: AgentWorld is heavier than Qwen3.6/Nex, so it's called only when simulation adds unique value.

### Pipeline integration points

| Phase | Use case | Delegation |
|-------|----------|------------|
| **Pre-Flight Gate (5.5)** | Simulate execution of plan before real code — predict what will break | `goal="Simulate running the plan on this codebase. Predict failures."` |
| **Implementation (6)** | Developer calls SimRL before real commands (`rm`, `deploy`, `cp -r`) | `goal="Simulate: run this command. Predict stdout, stderr, exit code, changed files."` |
| **Integration Gate (6a)** | Simulate module interaction before real compilation | `goal="Simulate: module A calls module B with this dataclass. Predict compatibility."` |
| **Acceptance Testing (8.5)** | Generate N adversarial environments for edge-case testing | `goal="Sim-RL: generate 3 environment variants. Simulate test against each. Return rewards."` |
| **Fugu Verifier** | Simulate result before final answer | `goal="Verify by simulation: predict what the real execution would show."` |
| **Observer Feedback** | "What-if" analysis — `(:CriticFinding)` with simulation scenario | `goal="Simulate: what if module X crashes during deployment?"` |

### Delegation pattern

```python
delegate_task(
    goal="You are sim-rl-agent. Simulate {environment}.",
    context="Initial state: {state}. Action: {action}. History: {conversation_summary}.",
    toolsets=["terminal", "file"],
    model="agentworld",
    provider="custom:local",
)
```

### Sim RL mode (reinforcement learning)

When the orchestrator requests "Sim RL" specifically, SimRL generates:
1. **N environment variants** — different initial states (files, ports, dependencies)
2. **Trajectory simulation** — for each variant, simulate the agent's interaction
3. **Reward + trajectory** — return reward scores and full state history per variant
4. **Used for** — training/fine-tuning agents, generating synthetic RL data, adversarial test suites

### GUI placement

SimRL appears in the statusbar dropdown under a **dedicated Simulation group** (separate from Reasoning Qwen3.6 and Coding Nex):
```
🧬 P3 ▼
  🧠 Reasoning — Qwen3.6
  🤖 Coding — Nex
  🔮 Simulation — AgentWorld    ← отдельная секция
    🔮 SimRL                     ← единственный агент
```

### Design rationale

- **External to cycle**: SimRL doesn't get auto-spawned at Phase 0 like observers. It's called when needed.
- **Model isolation**: Uses AgentWorld model (separate from Qwen3.6/Nex), so it can run concurrently.
- **No redundancy**: Most phases don't need simulation. Only Pre-Flight, Integration, and Testing benefit significantly.
- **Adversarial strength**: AgentWorld excels at predicting environment states — far better than general-purpose models.

### Empirical validation (v2.28 — 2026-07-04)

68-test empirical evaluation on SuperQwen APEX v3 (port 8103) comparing model predictions to real execution:

| Category | Tests | Accuracy | What was tested |
|----------|:-----:|:--------:|-----------------|
| Terminal (basic) | 8 | **100%** | echo, arithmetic, ls nonexistent, pipe+grep, exit codes, find, python, env vars |
| SWE (exceptions) | 15 | **100%** | All Python exception types: ZeroDivision, KeyError, IndexError, NameError, ImportError, TypeError, JSONDecodeError, AttributeError, RecursionError, AssertionError, FileNotFoundError + 4 success cases |
| Filesystem | 6 | **100%** | mkdir+touch+ls, mv overwrite, chmod+execute, rm -rf, symlink lifecycle, df format |
| Web/API | 6 | **100%** | HTTP 404, GET/POST JSON, connection refused, redirect, DNS failure |
| Hard SWE edge cases | 12 | **100%** | float precision (0.1+0.2), int overflow, is vs ==, mutable default args, dict ordering, generator exhaustion, walrus operator, closure capture, try/except/finally, class inheritance, global vs local |
| Multi-step state | 7 | **86%** | ❌ counter through list (8-step arithmetic — compounding error); ✅ dict accumulation, class mutation, recursive fibonacci, stateful iterator, exception in loop, nested data |
| Real-world code | 8 | **88%** | regex, json nested, sorted key, os.path, subprocess, threading, SQL injection (1 false negative from test design) |
| DevOps/Deployment | 6 | **100%** | docker build fail, port conflict, git merge conflict, env var missing, pip version, systemd service |
| **TOTAL** | **68** | **97%** | |

**What SimRL CAN do (verified):**
- Predict exception types and exact error messages (11/11 types, 11/11 messages)
- Predict stdout of simple programs (print, list comprehension, string methods)
- Predict Python edge cases (float precision, mutable defaults, closure capture, generator exhaustion)
- Predict DevOps failure scenarios (docker, ports, git, systemd, pip)
- Predict HTTP behavior (status codes, connection errors, DNS)
- Identify security patterns (SQL injection)

**What SimRL CANNOT do (verified):**
- Track multi-step arithmetic state (8-step counter: predicted step-2 value instead of step-8)
- Replace real execution for verification (AgentWorldBench uses rubric scoring, not exact-match)
- Predict dynamic web content (AgentWorldBench Search domain: 36.69/100 — weakest)

**CRITICAL: SimRL = PRE-FLIGHT CHECK, not VERIFICATION GATE.**

```python
# CORRECT pattern in Phase 6 (Implementation):
developer_agent:
    1. Write code
    2. SimRL predicts: "will it crash? what exceptions?"    # ← Pre-flight
    3. Developer fixes predicted errors
    4. Real execution: pytest, real run                      # ← Verification
    5. If real execution diverges from prediction →
       SimRL was wrong, not the code (track for future)

# DANGEROUS pattern (NEVER do this):
developer_agent:
    1. Write code
    2. SimRL "verifies" code
    3. If SimRL says "OK" → deploy without real testing      # ← WILL FAIL
```

**AgentWorldBench vs empirical results:** The 56.39 benchmark score uses LLM-as-judge (GPT-5.2) on 5 subjective dimensions (Format, Factuality, Consistency, Realism, Quality) across ~2,170 samples with 26.7 avg turns per trajectory. Single-step exact-match accuracy is significantly higher (97%) because: (1) benchmark evaluates long multi-step trajectories where errors compound, (2) rubric scoring is stricter than exact-match for format/realism, (3) benchmark includes rare edge cases. The sim-to-real gap manifests in multi-step rollouts, not single-step predictions.

Full methodology, testing scripts, per-domain AgentWorldBench breakdown, Qwen-AgentWorld paper analysis, and sim-to-real literature review: `references/simrl-empirical-evaluation.md`.

Full documentation: `/home/user/dev/plan3/` (ARCHITECTURE.md, RESTORE.md, DIFFS.md).

### Model Routing Table

| Role Type | Model | Provider | Benchmarks |
|-----------|-------|----------|------------|
| **Reasoning** (анализ, планирование) | `qwen3.6-35b` | `custom:local` | GPQA 86.0 |
| **Coding** (код, терминал, деплой) | `nex-n2-mini` | `custom:local` | SWE-Bench 74.4, Terminal-Bench 60.7 |
| **Simulation** (симуляции сред) | `agentworld` | `custom:local` | AgentWorldBench 56.39 |

### Pipeline Modes (beyond Full Cycle BDUF)

| Mode | Trigger | Pipeline | Latency |
|------|---------|----------|---------|
| **Full Cycle** | default | 10 фаз BDUF, все артефакты | ~30 min |
| **Fugu** | "быстро", "fugu" | Thinker(Qwen3.6)→Worker(Nex)→Verifier(Qwen3.6)→Synthesizer(Qwen3.6) | ~11s |
| **Fusion** | "проанализируй", "fusion" | Qwen3.6 ∥ Nex → Synthesizer(Qwen3.6) | ~8s |

### Fugu Mode

Fugu replaces phases 5-8.5 (Tech Lead → Developers → Verification → Testing) with
a fast 4-call pipeline. No documentation, no observers.

```python
delegate_task(goal="Thinker: plan solution", model="qwen3.6-35b", provider="custom:local")
delegate_task(goal="Worker: execute plan", model="nex-n2-mini", provider="custom:local")
delegate_task(goal="Verifier: check result", model="qwen3.6-35b", provider="custom:local")
delegate_task(goal="Synthesizer: final answer", model="qwen3.6-35b", provider="custom:local")
```

### Fusion Mode

Two agents analyze the same prompt from different perspectives in parallel,
then a synthesizer combines their outputs.

```python
delegate_task(tasks=[
  {goal: "Analyze from reasoning perspective", model="qwen3.6-35b", provider="custom:local"},
  {goal: "Analyze from implementation perspective", model="nex-n2-mini", provider="custom:local"},
])
delegate_task(goal="Synthesizer: combine analyses", model="qwen3.6-35b", provider="custom:local")
```

### Agent Files

```
~/.hermes/agents/
├── plan3.md                          # Orchestrator (local, Qwen3.6)
├── plan3/                            # 18 sub-agents with model binding
│   ├── requirements-agent.md         # → Qwen3.6
│   ├── developer-agent.md            # → Nex
│   ├── sim-rl-agent.md               # → AgentWorld (NEW)
│   └── ...                           # rest of plan2 agents with models
```

### GUI Integration

Plan3 sub-agents appear in a statusbar dropdown grouped by model.
See `hermes-desktop-extension` skill → `references/subagent-dropdown-pattern.md`. (v2.12 — GPT-5.5 REMOVED)

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

**For LOCAL-ONLY deployment (DGX Spark, 3 models via llama-swap):** 
see `references/local-model-routing.md` — 29 roles mapped to Qwen3.6 (reasoning), 
Nex-N2-mini (code/terminal), AgentWorld (simulation). No cloud API needed.

#### Управление и надзор (Kimi K2.7)

| Role | Model | Why |
|------|-------|-----|
| **Orchestrator** | **Kimi K2.7** | Management, 10-phase cycle, instruction-following. NOT code. |
| **Requirements Analyst** (#1) | Kimi K2.7 | User dialogue, clarifications — language precision |
| **System Analyst** (#2) | Kimi K2.7 | 5 Whys, goal tree, WSM/AHP — analytics, not code |
| **Architect** (#4) | Kimi K2.7 | Topology, module contracts, design — structure over speed |
| **Auditor + Critic + Idea Gen + Knowledge Curator** (#10-13) | Kimi K2.7 | Creative analysis, pattern discovery, delegation quality, knowledge graph. **Fallback: DeepSeek V4 Pro** — proven in codemes_neo4j_repo-graph (Auditor 155s, Critic 144s, Idea Gen 196s with quality reports). |
| **Jidoka Evaluator** (Gate 6b) | Kimi K2.7 | Independent skepticism — evaluating code against acceptance criteria requires precision, not creativity. Single-purpose, low-context (reads StandardWork + code, returns PASS/FAIL). |
| **DevOps Engineer** (#6a) | DeepSeek V4 Pro | grep, find, mechanical import verification — no management required |

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

## Plan3 — Local Multi-Model Orchestrator (NEW in v2.19)

Plan3 is a fully-local fork of plan2 that routes sub-agents across three specialized models
instead of one cloud model. See `~/dev/plan3/` for the full architecture document and
`~/.hermes/agents/plan3/` for the 18 sub-agents with model bindings.

### Model Routing Table

| Role Type | Model | Provider | Benchmarks |
|-----------|-------|----------|------------|
| **Reasoning** (анализ, планирование) | `qwen3.6-35b` | `custom:local` | GPQA 86.0 |
| **Coding** (код, терминал, деплой) | `nex-n2-mini` | `custom:local` | SWE-Bench 74.4, Terminal-Bench 60.7 |
| **Simulation** (симуляции сред) | `agentworld` | `custom:local` | AgentWorldBench 56.39 |

### Fugu Mode (быстрый пайплайн)

4 sequential calls, ~11s, no documentation or observers:
```
Thinker(Qwen3.6) → Worker(Nex) → Verifier(Qwen3.6) → Synthesizer(Qwen3.6)
```
Activation: user says "быстро", "fugu", "fast".

### Fusion Mode (параллельный анализ)

2 parallel calls + synthesizer, ~8s:
```
Qwen3.6 ∥ Nex → Synthesizer(Qwen3.6)
```
Activation: user says "проанализируй", "сравни", "fusion".

### Local Orchestrator Context Budget

On DGX Spark, 100K+ token prefill = 200+ seconds. Solution: trimmed prompt (~20K tokens):
- Full documentation → skill `multi-agent-orchestration-plan3`
- Orchestrator prompt: current phase (0.5K) + artifact (2K) + routing table (0.5K) + history (15K)
- Full artifacts accessed via `read_file` as needed
- Result: 8-12s prefill instead of 200s

Plan2 deliberately uses **strictly sequential BDUF** (Big Design Up Front) — all phases execute in fixed order, none can be skipped. This is a conscious trade-off against dynamic frameworks (AFlow, FoT, ADAS):

| Property | Plan2 (fixed BDUF) | Dynamic (AFlow/FoT) |
|----------|-------------------|---------------------|
| **Predictability** | Orchestrator always knows next phase | Must decide which phase to run next |
| **Completeness** | No phase ever skipped — root cause guaranteed found | Risk of skipping critical analysis for "simple" tasks |
| **Auditability** | Observer checkpoints at fixed positions → cross-cycle comparable | Phase numbering unstable → cross-cycle comparison broken |
| **Context flow** | Each downstream agent gets ALL upstream context | May miss context if ordering changes |
| **Gate simplicity** | Gates assume all prior phases complete | Gates must check "was phase X even run?" |
| **BDUF payoff** | 5 analysis phases before code → prevents architectural rework | Risk of coding wrong architecture |
| **System Analyst** | Lives entire cycle — remembers WHY from beginning to end | No equivalent in dynamic frameworks |

**When dynamic frameworks add value (not compete with BDUF):**
- **AFlow (parallel)**: searches for alternative workflows WITHOUT disrupting the main plan2 sequence; results compared post-hoc in Phase 10
- **FoT (runtime)**: could be the executor for individual plan2 phases — Scheduler optimises parallel sub-agent execution WITHIN a phase, not across phases
- **ADAS (evolution)**: Idea Generator proposes mutations to plan2 between cycles; Auditor evaluates; accepted mutations applied to next cycle

The core insight: **BDUF is the spine; dynamic frameworks are the muscles.** Don't replace the spine; wrap it.

## Parallel Phase Execution
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

When the task is to repair Hermes delegation routing itself, a same-session `delegate_task` smoke can keep failing after the disk fix because the parent Hermes process still has old imported tool/runtime code or old runtime config. Prove the fix with: RED regression test → minimal runtime/config fix with backup → targeted tests → **fresh Hermes process** smoke using explicit `model/provider` → touched-file regression → scoped rollback commands. Do not use `git restore .` in Pavel's Hermes checkout; unrelated work is often present. See `references/delegation-route-repair-reload-boundary.md` for the smoke and rollback templates.

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

## Pre-Flight Infrastructure Validation (v2.33 — before ANY cycle)

Before starting a plan2/plan3 cycle, validate that all infrastructure the preset
depends on actually exists and works: (1) model routing cross-check (registry
models vs LiteLLM `/v1/models`), (2) gate script smoke test (do they crash on
`--json`?), (3) Neo4j schema (expected labels/relationships exist + populated),
(4) registry path validation (agent `path` fields resolve), (5) service
connectivity via `orchestrator_gate.py`. Takes ~60 seconds; catches the most
common mid-cycle failures (missing models, broken gates, empty Neo4j schemas).
Full checklist with copy-paste commands: `references/preset-infrastructure-validation.md`.

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

## Local Model Routing (Fugu / Fusion / MoA) — v2.19

When running plan2 on local models (DGX Spark, 3×35B MoE), route each phase to the model best suited for its task type. This is the local equivalent of the cloud Model Routing Table (§Model Routing Table).

### Local Model Profiles

| Model | Strength | Weakness | Best for |
|-------|----------|----------|----------|
| **Qwen3.6-35B** | GPQA 86.0, MTP 50 tok/s | Terminal-Bench 51.5 | Reasoning, analysis, planning |
| **Nex-N2-mini** | SWE-Bench 74.4, Terminal-Bench 60.7 | GPQA 82.6 | Coding, terminal, tools |
| **AgentWorld-35B** | AgentWorldBench 56.39 | Not general-purpose | Environment simulation, Sim RL |

### Phase Routing (Local)

| Phase | Model | Why |
|-------|-------|-----|
| Orchestrator | Qwen3.6 | GPQA 86.0 — pure reasoning, no code |
| 1-4 (Requirements→Architecture) | Qwen3.6 | All analysis, no tools |
| 5-8.5 (Tech Lead→Tester) | Nex | Code, terminal, curl, SAST |
| 10 (Observers) | Qwen3.6 | Pattern discovery, creative analysis |
| Sim RL (external) | AgentWorld | Only model that can simulate environments |

### Fugu Pipeline (fast mode for single requests)

Thinker (Qwen3.6) → Worker (Nex) → Verifier (Qwen3.6) → Synthesizer (Qwen3.6).
~11 seconds, 4 model calls. No documentation, no observers, no full cycle.
Activation: user says "быстро", "fast", "fugu".

### Fusion Pipeline (parallel analysis)

Qwen3.6 (analysis) ∥ Nex (implementation) → Synthesizer (Qwen3.6).
~8 seconds, parallel execution. Best of both perspectives.
Activation: user says "проанализируй", "сравни", "fusion".

### Quantization Pitfall (CRITICAL)

**Big model + bad quant < smaller model + good quant.** A 397B model in IQ2_XS (~2.5 bit) performs WORSE than a 35B model in Q8_0 (near-lossless). Never recommend extreme quantization to fit a large model when a smaller model in Q8_0 fits the hardware. See `local-model-serving` skill → `references/quantization-quality-data.md` for the full benchmark table (arXiv 2601.14277).

### Local Deployment Architecture

Full DGX Spark deployment with llama-swap matrix mode, 3 models simultaneously in memory, KV-cache quantization, and memory budgeting: `local-model-serving` → `references/dgx-spark-deployment.md`.

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
  Pavel explicitly corrects this pattern: "не надо менять системный промпт. надо
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
- **Jidoka evaluator must be deployed as a SEPARATE sub-agent call, not as the Tech Lead self-reviewing.** The Jidoka evaluator's system prompt is tuned for SKEPTICISM — it assumes the developer made mistakes and searches for them. Tech Lead's system prompt is tuned for MANAGEMENT — it assumes competence and checks for structural issues. If Tech Lead does both roles, the skepticism gets diluted and the "strongest lever" (evaluation separation) is lost. Always spawn Jidoka as a `delegate_task` with `role="leaf"`, passing the StandardWork contract and file paths as context.
- **StandardWork contracts are the communication boundary between Tech Lead and Developers.** If a developer doesn't receive a StandardWork contract, they cannot know what "done" means. The orchestrator MUST pass the StandardWork contract from the plan artifact into the developer's context. Without it, developers fall back to "I think this works" self-evaluation — which is exactly what StandardWork is designed to prevent.
- **Tech Lead v4: static DAG is the #1 blind spot — IMPLEMENTED v2.22.** The Dependency DAG built in Phase 5 was NEVER updated during Phase 6 execution. DynTaskMAS (2025) solved this with a Dynamic Task Graph Generator. **IMPLEMENTED (2026-07-03):** DAG stored as live JSON (`-dag.json`), updated at 5 events (new dependency, interface change, reuse > 0.7, budget overrun > 150%, 3 consecutive failures). Versioned, machine-readable. Applied to `plan2/techlead-agent.md` (Шаг 1: Dynamic Task Graph, 1a-1d), `plan3/techlead-agent.md` (same), both orchestrator files (lifecycle contracts + artifact validation + pre-phase gates). See `references/techlead-v4-p0-implementation.md` §Dynamic DAG.
- **Tech Lead v4: feedback loop is open — IMPLEMENTED v2.22.** Jidoka FAIL → developer escalation, but feedback NEVER returned to Tech Lead for plan revision. RLEF (ICML 2025) showed closed-loop execution feedback = 18-30% better iterative improvement. **IMPLEMENTED (2026-07-03):** Phase 6.5 Feedback Loop Closure in `plan2/techlead-agent.md` — 6.5a Feedback Collection (JSON per SW into dag-state.json), 6.5b Pattern Detection (6 patterns after every 2nd SW: import failures, coverage gaps, budget overruns, high reuse, repeated escalation, same error 3×), 6.5c Plan Revision Protocol (update remaining SW handoffs, log REV-NNN), 6.5d Loop Guards (5 guards: max 3 iterations/SW, max 2× total retries, 150% budget cap, loop detection, DAG thrashing freeze). Applied to both plan2 and plan3 orchestrator files (lifecycle contracts + quality gates + context flow diagram). See `references/techlead-v4-p0-implementation.md` §Feedback Loop.
- **Self-modification MUST be user-gated, not automatic (v2.22).** The Self-Evolution Engine (Phase 11) collects metrics and mines patterns automatically, but applying changes to routing rules, templates, or criteria requires explicit user request. 11.1 (metrics → Neo4j) and 11.2 (pattern mining + proposal saving as `(:SelfModificationProposal {status: "pending"})`) are AUTOMATIC. 11.3 (apply modifications) and 11.4 (template evolution) are ONLY triggered when user says «примени self-modifications» / «apply evolution». Proposals are visible in Phase 10 reports. User picks which to apply via `clarify`; approved → `SET status="applied"`, rejected → `SET status="rejected"`. This governance model prevents the agent from silently modifying its own operating parameters between cycles — a user safety requirement.
- **Tech Lead v3 sub-orchestrator context budget (v2.20).** When Tech Lead spawns 5 developers + 5 reviewers simultaneously, its own context can overflow from accumulating summaries. Mitigation: each developer gets an isolated session (fresh context); Tech Lead receives only summary output. If Tech Lead context > 80%, summarize + spawn fresh Tech Lead with summary. Max 5 parallel developers. Timeout per developer: 120s. Fallback: orchestrator spawns developers directly (v2 model) on Tech Lead timeout/error.
- **Validating orchestration structural changes requires 5 levels (v2.22).** After patching agent prompt files (techlead, orchestrator), grep alone proves text presence but not correctness. Use the 5-level validation methodology: (1) JSON parse all embedded schemas, (2) execute Cypher against real Neo4j, (3) cross-file contract test for path/label/guard consistency, (4) independent subagent reads file and checks 12 criteria with quoted evidence, (5) pattern injection simulation with mock dag-state.json. 56/56 tests passed for P0. See `references/techlead-v4-p0-implementation.md` §Validation methodology.
- **Cross-file contract tests produce false positives on strict path patterns (v2.22).** When the orchestrator uses a variable (`dag_state_path`) and the techlead uses the full path pattern (`<ts>-<slug>-dag.json`), a naive grep for the full pattern in the orchestrator file fails. This is correct design — orchestrators pass variables, techlead files define paths. Always verify with actual file content before declaring a failure.
- **BDUF-everything is a token waste for simple tasks (v2.23).** Running all tasks through Phases 1-3 (90-235K tokens pre-implementation) is justified for architectural changes but wasteful for bugfixes (0K needed) and simple features (15-25K needed). SOTA systems (OpenHands, SWE-Agent, ChatDev) run at 0.05-0.5x pre/impl token ratio vs our 1.5-2.5x. Google study: multi-agent coordination DROPPED performance 39-70% on complex tasks while multiplying token spend. **Fix:** Task classifier at Phase 0.4 determines depth mode (bugfix/feature/architectural) and routes accordingly — skip or lighten Phases 1-3 for non-architectural tasks. Developer Query mode (lightweight on-demand research) remains available in Phase 6 regardless. See `references/adaptive-pre-implementation-depth.md`.
- **System Analyst Phase 2 and Tech Lead Phase 5 do 60-70% of the same work (v2.23).** SMART goal→DAG decomposition, alternatives→model routing, developer task→StandardWork, goal tree→DAG, WSM/AHP→cost-aware routing. Phase 2 costs 20-40K tokens for ~25K waste. **Fix:** merge Phase 2 analysis responsibilities into Tech Lead (Step 0.3: Root Cause Check — 5 Whys + goal tree as checklist). KEEP Phase 6.5 verification as independent agent — it's the only agent that checks "did we build the RIGHT thing?" vs "did we build it RIGHT?" (Jidoka). See `references/adaptive-pre-implementation-depth.md` §System Analyst.
- **Requirements Agent asks questions already answered in AGENTS.md (v2.23).** Environment, stack, constraints, users — all in AGENTS.md or capability_report.json (Phase 0.2). ~7K tokens of questions produce ~7K waste. Only acceptance criteria, out-of-scope, and NFRs (when task touches them) are unique value. **Fix:** strip obvious questions; use adaptive questioning (0 for bugfix, 2-3 for feature, full set for architectural).
- **NEVER exclude research/system-analysis from developer context — COMPRESS instead (v2.24).** Initially proposed removing research artifact and system analysis from developer context to reduce noise. This was WRONG: in a BDUF pipeline, the developer makes micro-decisions at every step (which algorithm? which library? how to handle edge case? why this interface?) that REQUIRE research findings and system analysis root cause. Without them, developer codes blind or by intuition, which can contradict findings. **Correct approach:** COMPRESS + FILTER by SW relevance. Full research (8KB) → EXIT-filtered to SW-relevant findings (1.5KB, 5x compression). Full system analysis (5KB) → root cause + goal tree branch only (2KB). Tech Lead performs extraction at StandardWork creation time (Step 4.5: Research & Analysis Extraction). See `references/context-compression-sota.md` §Critical Principle.
- **Context compression has 8 mechanism categories — pick the right one per use case (v2.24).** (1) Extractive: LLMLingua/EXIT for filtering long docs by relevance. (2) Abstractive: Anchored Iterative Summarization (Factory.ai) for session state — incremental merge, not regenerate. (3) Structured: JSON contracts instead of markdown (30-83% reduction). (4) Hybrid: ACON — failure-driven guidelines that evolve (Kaizen rules = what to preserve). (5) Eviction: priority queue (test output first, NEVER drop StandardWork/AC/imports). (6) Externalization: tool output → SQLite sandbox (98% reduction, retrievable). (7) Linguistic: Caveman mode for agent-to-agent communication (~75% output reduction). (8) KV-cache: infra-level, not applicable for external APIs. Implementation priority: P1 = caveman + structured contracts + ACON + anchored state; P2 = EXIT filtering + sandboxing + eviction; P3 = ContextEvolve + LLMLingua. See `references/context-compression-sota.md`.
- **Rigid JSON schemas break research output — use tiered schema (v2.25).** A fixed enum-only schema forces research agent to force-fit, drop, or fabricate findings that don't match predefined categories. Meta-reasoning ("PEG is slower but better DX, consensus is DX > performance for small grammars") doesn't fit `best_practice|pitfall|benchmark`. **Fix:** 3-layer tiered schema — Layer 1 structured core (enum `category` for routing + free-text `finding` for content), Layer 2 conditional (pitfalls/benchmarks when applicable), Layer 3 `unstructured_notes` escape hatch (meta-reasoning, debates, caveats). Cross-cutting `must_see` flag prevents false negatives in Tech Lead filtering. JSON = primary artifact, MD = auto-generated view. See `references/tiered-schema-research-output.md`.
- **Cross-file validation produces false negatives on backtick-wrapped terms (v2.25).** When validating that agent files contain required content, grep/substring search for `` `must_see` findings `` fails if the file has `` `must_see` findings помечены `` (Russian suffix) or different backtick formatting. **Fix:** use bare substrings without backticks (`must_see` → search for `must_see` without surrounding backticks, or use partial phrases like `помечены` or `flagged correctly`). When automated validation reports FAIL, always read the actual file content before declaring a real failure — 2/57 initial false negatives were formatting artifacts, not missing content.
- **Agent prompt files are code — review them with code rigor (v2.27).** A Neo4j `CREATE` in Phase 11.1 used property `budget_tokens` but the `MATCH` in 11.2 queried `m.budget` — silently returning 0 results with no error. StandardWork examples didn't include Spec Delta fields that instructions mandated. Handoff templates said "create" when Spec Delta said "refactor". "Запрещено" didn't prohibit skipping Spec Inference. **5-level review for agent prompt files:** (1) property consistency — names in CREATE/MATCH/SET match across sections; (2) example completeness — new features appear in examples/templates, not just instructions; (3) template cross-reference — handoff templates include fields that instructions require; (4) prohibition enforcement — "Запрещено" covers all mandatory steps; (5) section cross-reference — related sections point to each other. See `references/techlead-v4-p2-implementation.md` §Post-implementation review.
- **Describe before implementing — user wants to approve design before code changes (v2.27).** User pattern: "мне нужно только описание сейчас" → describe the proposed changes in detail, wait for approval, THEN implement. If implementation starts prematurely, user says "откати эти изменения" and expects a clean rollback. This aligns with the existing RESEARCH→PLAN→CONFIRM→EXECUTE preference but specifically applies to agent config file changes: present the design (what sections, what lines, what new content) as text first, get "давай" or equivalent, then patch files.
- **GLM-5.2 silently crashes on context exhaustion (v2.29).** Unlike GPT-4/DeepSeek which return explicit "context length exceeded" errors, GLM-5.2 (Zhipu provider) simply stops responding — the connection drops or returns empty, and Hermes interprets this as session end. Combined with the plan2 preset overhead (68KB/17K tokens loaded before the first message), GLM-5.2's 128K window is dangerously small for orchestration cycles. Session 20260706_175000_1fd1dd (367 messages, GLM-5.2, plan2 preset) crashed at message 367 with 0 messages after the last user input. **Recommendation:** do NOT use GLM-5.2 for plan2/plan3 orchestrator sessions. Use DeepSeek V4 Pro (128K but throws explicit errors) or Kimi K2.7 (128K, better management). If GLM-5.2 must be used, switch to a general preset for meta-questions and use plan2 only for full cycles with tight context budgets. Qwen-AgentWorld achieves 97% accuracy on single-step predictions but FAILS on multi-step state tracking (8-step arithmetic counter predicted step-2 value instead of step-8). This is the classic sim-to-real gap: errors compound across rollout steps. AgentWorldBench mitigates this with teacher forcing during evaluation (reload real output after each prediction), but real SimRL usage has no teacher forcing. **Implication:** SimRL is reliable for "what will happen if I run this ONE command?" but NOT for "simulate an entire deployment sequence and tell me if it will work." Always use SimRL as a pre-flight check before real execution, never as a replacement for it. When delegating to SimRL, keep simulations to single-step or short (2-3 step) predictions for reliable results.
- **False negatives in model evaluation — verify test correctness first (v2.28).** In the 68-test SimRL evaluation, 3 of 4 "failures" were false negatives: (1) model predicted English error message but test system had Russian locale → "Permission denied" vs "Отказано в доступе"; (2) test expected wrong value (mv overwrite — model was RIGHT, test was wrong); (3) test code contained non-executable print statement that confused the model. **Rule:** when a model "fails" a test, first verify: (a) test expectations are correct (run the real code yourself), (b) locale/environment matches what the model would predict, (c) test code is actually executable as written. Only declare a genuine model failure after confirming the test itself is correct.
- **`$HOME` redirection breaks the ENTIRE plan2 pipeline (v2.29 — 2026-07-14).** Hermes terminal sets `$HOME=/home/user/.hermes/home` (session isolation). Agent `.md` files and YAML gate configs that use `~/.hermes/scripts/...` paths in bash code blocks or `check:` commands resolve to `/home/user/.hermes/home/.hermes/scripts/...` — **does not exist**. Every gate check, capability scan, and script invocation silently fails. **Diagnostic:** `echo $HOME` under Hermes terminal → if it ends in `.hermes/home`, ALL `~/.hermes/` paths are broken. **Fix:** replace `~/.hermes/` → `$HERMES_HOME/` in agent files (plan2.md had 38), YAML gates (all_gates.yaml had 7), and Python gate scripts (`os.path.expanduser("~")` → `os.environ.get("HERMES_HOME")`). Also check: `provider: deepseek` in agent files — `deepseek` is NOT a configured provider name; models like `deepseek-v4-pro` are registered under `custom:local` (via LiteLLM). Replace `provider: deepseek` → `provider: custom:local` (16 occurrences in plan2.md). Full diagnostic methodology + all fixes: `references/plan2-pipeline-diagnosis.md`.
- **`$HOME` breaks non-Hermes bash scripts too (v2.30 — 2026-07-15).** The v2.29 pitfall covers `~/.hermes/` paths in YAML/agent files. But ANY bash script using `${HOME}` breaks under Hermes terminal — including `start-llama.sh` which uses `${HOME}/models/*.gguf` for model paths and `${HOME}/dev/llama/pids/` for PID files. When models are started from a real shell (`HOME=/home/user`) but `start-llama.sh status` is run from Hermes terminal (`HOME=/home/user/.hermes/home`), PID files appear missing → status reports all models as "не запущен" even though they're running. **Fix:** replace `${HOME}` with `REAL_HOME=$(getent passwd "$(id -un)" | cut -d: -f6)` at the top of any bash script that resolves real filesystem paths (models, logs, PIDs). This is more robust than `$HERMES_HOME` for scripts that have nothing to do with Hermes config. Applied to `start-llama.sh` (5 `${HOME}` → `${REAL_HOME}` replacements). The validation script `scripts/validate-plan3-models.py` now checks for this bug (check #5: `check_start_llama()` detects missing REAL_HOME fix).
- **Agent file frontmatter `model/provider` does NOT control session model — only sub-agent delegation (v2.31 — 2026-07-15).** When you run `/agent plan3`, Hermes loads the system prompt and toolsets from `plan3.md`, but the MODEL comes from `model.default` / `model.provider` in `config.yaml`. The frontmatter `model: agents-a1-abliterated` in plan3.md ONLY applies to sub-agents spawned via `delegate_task(model=..., provider=...)`. **This is the #1 cause of «plan3 использует GLM вместо локальных моделей».** If `config.yaml` says `model.default: glm-5.2, provider: zai`, the orchestrator runs on GLM cloud regardless of what plan3.md frontmatter declares. **Fix:** `hermes config set model.default agents-a1-abliterated && hermes config set model.provider local`. Symptom diagnosis: open any session using `/agent plan3`, check the session header for Model/Provider — if it shows glm-5.2/zai instead of agents-a1-abliterated/local, this pitfall is active. The user can still switch back with `/model zai glm-5.2` for non-plan3 sessions.\n- **Model routing drift — registry.json and sub-agent frontmatter silently diverge from design intent (v2.30 — 2026-07-15).** Plan3 is designed as "Fully Local" (3 models via LiteLLM :4000), but the sub-agent frontmatter files (`~/.hermes/agents/plan3/*.md`) and `registry.json` had drifted: 5 agents still pointed to cloud providers (deepseek-v4-pro, kimi-k2.7-code) inherited from the plan2 era, and 2 of those (kimi) were BROKEN (HTTP 400). 13 agents had `provider: local` instead of `provider: custom:local` (inconsistent naming). registry.json had 43 agents on cloud providers. **Root cause:** when plan3 was forked from plan2, frontmatter and registry were copied but not updated — there is no automated check that enforces "local-only" policy. **Validation methodology — check ALL 4 sources of truth holistically:** (1) sub-agent frontmatter `model:` / `provider:` lines, (2) registry.json `agents[*].model` / `.provider`, (3) physical llama-server health on ports :8101/:8102/:8103, (4) LiteLLM config model→server mapping. **Fix applied:** Reasoning → `agents-a1-abliterated`/`custom:local`, Coding → `nex-n2-mini`/`custom:local`, Simulation → `agentworld`/`custom:local`. 5 frontmatter patched, 13 normalized, registry.json updated for 43 agents. Run `scripts/validate-plan3-models.py` before any plan3 cycle. Validation reference: `references/plan3-model-routing-validation.md`.

- **Pre-delegation hook enforcement (v2.32).** See above and `references/plan3-pre-delegation-hook.md`.
- **Plan2 validation 2026-07-15: 10 fixes, 7/7 gate.** research_deep gate legacy artifact filter, kimi→agents-a1 model replacement (34 files), Hermes API :18649→:8643, LiteLLM /health→/v1/models, observer gate config.yaml-aware, MCP registration, agents/dev/ files. Details: `references/preset-infrastructure-validation.md` §6-8.
