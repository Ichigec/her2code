---
name: agent-improvement-pipeline
description: "Patterns and lessons learned from building the Agent Improvement Pipeline (audit & observability plugin for Hermes). Use when orchestrating multi-agent development cycles."
version: 1.1.0
author: Hermes Agent (plan orchestrator)
metadata:
  hermes:
    tags: [orchestration, multi-agent, audit, testing, security]
---

# Agent Improvement Pipeline — Lessons Learned

## When to Use

When orchestrating multi-agent development cycles with delegate_task — especially:
- Spawning 7+ developers in parallel
- Building Hermes plugins
- Any project with cross-stream dependencies
- Creating sanitized distributable packages for other users

## Full Lifecycle (9 Phases)

Every multi-agent engineering project follows this pipeline. Skip phases only when artifacts already exist from a prior cycle.

| # | Phase | Agent | Deliverable | Skip if... |
|:--:|-------|-------|-------------|------------|
| 1 | Requirements | `requirements-agent` | Clarified scope doc | Requirements already clear |
| 2 | System Analysis | `system-analyst` | SMART goals, 5 Whys, WSM/AHP | Trivial project |
| 3 | Research | `researcher` (+ sub-agents) | Research synthesis, best practices | Domain already known |
| 4 | Architecture | `architect` | `docs/architecture/<slug>.md` | Architecture exists |
| 5 | Tech Lead Plan | `techlead` | `.hermes/plans/<ts>-<slug>.md` | ≤2 developers needed |
| 6 | Developers | `developer` ×N | Working code + tests (all 4 dev agents now mandate `quality_gate_runner.py` after every write_file/patch) | — |
| 7 | Security Audit | `security` | Findings list + fixes | Non-critical project |
| 8 | Deployment | `deployment` (or manual) | Running system | — |
| 8.5 | Acceptance | `quality_gate_runner.py` (acceptance gate) | Acceptance gate PASS against deployed service | — |
| 9 | Iterate | Orchestrator | Retrospective, skill updates | — |
| 10 | Idea Generator | `idea-generator` | Cross-phase synthesis: unheard ideas, connections, missing info, pipeline optimization, creative proposals | After every complete cycle |

**Parallel opportunities:**
- Phases 1+2+3 can run in parallel (different agents, no dependencies)
- Phases 4 (architecture) can run for multiple independent subsystems in parallel
- All developers in Phase 6 run in parallel (batch `delegate_task`)

**Per-subsystem sizing:**
- **3+ developers** → full lifecycle (1→2→3→4→5→6→7→9)
- **1-2 devs, ≤5 files** → Architect → Developer (skip 5)
- **1 dev, ≤3 files** → Developer directly (skip 4+5)

## Single-Script Startup Pattern (`start.sh`)

When distributing a multi-service stack, provide ONE script that starts everything:

```bash
bash start.sh              # full stack
bash start.sh --no-voice   # skip optional services
bash start.sh --status     # health check
bash start.sh --stop       # graceful shutdown
```

**Script structure:**
1. Parse flags (--no-voice, --no-android, --status, --stop)
2. Check prerequisites (python3, docker, node)
3. Start Docker containers (Neo4j, searchbox, relay)
4. Start model server (llama.cpp / vLLM)
5. Start API proxy (LiteLLM)
6. Start agent framework (Hermes API server)
7. Initialize databases (copy empty schemas)
8. Register plugins
9. Start voice proxy
10. ADB reverse (Android)
11. Initialize graph schema (Neo4j)
12. Health-check + print status table

**Config pattern:** ALL settings through environment variables with `${VAR:-default}`:
```bash
LLAMA_PORT="${LLAMA_CPP_PORT:-8092}"
HERMES_PORT="${HERMES_API_PORT:-8643}"
```
Never hardcode paths — use `${HOME}/...` or `${CODEX_ROOT}/...`.

Full template: `references/start-sh-template.sh`.

## README Dual-Purpose Pattern

When a README.md serves BOTH humans and AI agents, add a header block:

```markdown
# Project Name

> **Для людей:** Этот файл — документация. Смотри SETUP.md для установки.
> **Для AI-агентов:** Этот файл — контекст. Загружается в системный промпт.
```

This prevents agents from treating setup instructions as context noise, and humans from treating architecture as their install guide.

## Distributable Sanitization Checklist

When preparing a project for distribution to other people:

**Six domains to sanitize:**
1. **Secrets:** grep for `sk-`, `api_key`, `token`, `password`, `-----BEGIN`. Replace ALL with fake values.
2. **Paths:** `grep -rn '/home/<user>'` → replace with `${HOME}`. Exception: research/archival docs.
3. **Databases:** Ship empty (schema only). Use `.sql` files + create from them at startup.
4. **Models:** Single local provider. Remove all paid API entries (DeepSeek, OpenAI, etc.).
5. **Code:** Remove `__pycache__/`, `*.pyc`, `.git/`, `node_modules/`.
6. **Documentation:** README + SETUP + SEQUENCE + architecture docs. Include diagrams.

**APK verification:** `strings app.apk | grep -iE 'sk-|api.key|token.{20,}|192\.168\.|10\.4\.'` — must be empty (except UI string resource names like `api_key_hint`).

**Final verify:** `grep -rn '/home/<user>' --include='*.yaml' --include='*.json' --include='*.env' --include='*.sh'` → 0 hits.

Full checklist: `references/distribution-packaging.md`.

## Interface Contracts Pattern

**Problem:** Parallel developers writing to the same file (e.g., A1 and A2 both modifying `audit_db.py`) → race conditions, merge conflicts.

**Rule:**
1. **Freeze the contract first** — dataclasses + public method signatures in a shared stub
2. **Commit the contract** before developers branch
3. **Each dev works on their implementation** independently
4. **Mutual approval** before merge

**Template:**
```python
# plugins/foo/contract.py — FROZEN, approved by tech lead
from dataclasses import dataclass

@dataclass
class SharedType:
    field: str
    ...

class SharedAPI:
    def method_a(self, x: str) -> int: ...
    def method_b(self, y: int) -> str: ...
```

## Stream Sizing Rule

**Problem:** Stream F+G (7 files for 1 developer) → 600s timeout.

**Rule:** ≤3 new files per developer stream.

| Files to create | Streams needed |
|:---:|:---:|
| 1–3 | 1 stream |
| 4–6 | 2 streams |
| 7+ | 3+ streams |

Apply at planning time (Phase 5, tech lead).

## PII Audit Gate

**Problem:** `redact_pii()` implemented but never called in tool trace path (security finding #4).

**Rule:** Every component that persists data MUST have:
1. PII redaction applied before storage
2. A dedicated test class (`Test...PIIRedactedInDB`) with real PII-like fixtures
3. E2E test: subagent → result with PII → verify redacted in DB + reports

**Test patterns:**
```python
class TestToolResultPIIRedactedInDB:
    def test_email_redacted(self, recorder, audit_db):
        recorder.record_tool_result(trace_id, {"result": "email: user@example.com"})
        trace = audit_db.get_session_tool_traces(session_id)[0]
        assert "user@example.com" not in trace.result_summary
        assert "<REDACTED:email>" in trace.result_summary
```

Cover all patterns: email, API key (sk-*), bearer token, SSN, IP, credential assignment.

## Cross-Stream Verification Gate

**After merging any two streams:**
```bash
python3 -m pytest plugins/audit/tests/ -v --tb=short
python3 -c "import plugins.audit"  # verify imports clean
```

Checklist:
- [ ] All unit tests for merged streams pass
- [ ] Integration tests (if any) pass
- [ ] Import check (no ImportError)
- [ ] No stale files from merge conflicts

## Batch Delegate Pattern

**Do:** Launch all independent developers in one `delegate_task(tasks=[...])` call.
**Don't:** Sequential delegate_task for independent work.

**Exception — orchestrator depth limit:** Do NOT use `role='orchestrator'` sub-agents to spawn developers when the plan has 7+ streams. Sub-orchestrators time out (600s) because they must read the plan, then spawn their own children — two layers of tool calls without giving results back to the parent. Spawn developers directly from the root orchestrator instead.

## Phase Skipping: Two Rules (artifact-existence WINS)

There are TWO reasons to skip a phase — they work together, but artifact-existence takes priority:

### Rule 1: Artifact already exists → skip phase (NON-NEGOTIABLE)

Before starting ANY phase, check if the artifact exists. If yes, skip — the work is done.

| Phase | Artifact | Skip if... |
|:-----:|----------|------------|
| 4 | `docs/architecture/<slug>.md` | File exists + is ≥100 lines (not a stub) |
| 5 | `.hermes/plans/<ts>-<slug>.md` | File exists + covers the target streams |

**This rule overrides Rule 2.** Even if Rule 2 says «Architect needed for 1-2 devs», if the architecture doc already exists (e.g. from a prior full cycle), skip it. Re-running a completed phase is waste.

### Rule 2: Task sizing → skip phases (only when artifact is MISSING)

Use this when no prior artifacts exist and you're deciding the minimal lifecycle:

- **3+ developers needed** → full lifecycle: Architect → Tech Lead → Developers
- **1-2 developers, ≤5 files** → Architect → Developer directly (skip Tech Lead plan)
- **1 developer, ≤3 files, no architecture questions** → Developer directly

### Decision flowchart

```
Is architecture doc present + ≥100 lines?
  ├─ YES → skip Architect → Is plan.md present?
  │          ├─ YES → go straight to Developer
  │          └─ NO  → use Rule 2 for Plan decision
  └─ NO  → use Rule 2 for both Architect + Plan decisions
```

### Real example: Agent Improvement Pipeline, Stream A only

- Architecture doc: `docs/architecture/agent-improvement-pipeline.md` — 1058 lines ✅
- Plan: `.hermes/plans/...agent-improvement-pipeline.md` — 1951 lines, Stream A specs included ✅
- **Decision:** Skip Architect, skip Tech Lead. Go straight to Developer. Even though Stream A has 6 files (Rule 2 would say «Architect → Developer»), Rule 1 wins — both artifacts exist.

## Pre-existing Code Discovery

**Problem:** When re-spawning a timed-out developer, their files may already exist (previous attempt completed the work before hitting its time limit). New developer wastes time rewriting.

**Rule:** Before spawning developers, verify target files:
```bash
ls plugins/<name>/<expected_file>.py
```
If files exist → adjust task from "create" to "verify, test, fix gaps."

**Advanced version — Specification Inference (SpecRover pattern):** Instead of just checking file existence, read the existing code, infer its current specification (methods, signatures, exceptions, callers), compare with target architecture, and create a **Spec Delta** JSON with `action: new|refactor|reuse` and `reuse_potential` (0.0–1.0). Developer then gets "refactor parse(): dict→ParsedDocument, update 2 callers, 60% reusable" instead of "create parser". Implemented in `plan3/techlead-agent.md` Step 0.3. See `multi-agent-orchestration` skill → `references/techlead-v4-p2-implementation.md`.

## PEP 668 Workaround for Graph Dependencies

When building subsystems that use Neo4j (knowledge graph, practice graph), the `neo4j` Python driver needs installation on PEP 668 systems:
```bash
pip install neo4j --break-system-packages
```
Document this in the subsystem's own skill, not as a global dependency.

## Distributable Packaging

When asked to produce a sanitized, runnable distribution of the entire project (for other people):

**Core principle:** The distribution must be complete AND clean — everything needed to run, nothing that compromises security.

**Six sanitization domains:** secrets → paths → databases → models → code → documentation.

Full checklist and directory structure: `references/distribution-packaging.md`.

**Quick rules:**
- All `.env` → `.env.example` with fake values
- All paths `/home/<user>` → `${HOME}`
- All databases empty (schema only)
- Model: single local provider, no paid APIs
- Every `sk-*` key → `sk-fake...` or `sk-local`
- Verify with grep before shipping

## Security Audit Timing

Run security audit (Phase 7) AFTER all developers complete but BEFORE declaring done.
This cycle's audit found: 1 CRITICAL (disabled SSL), 1 HIGH (path traversal), 3 MEDIUM, 4 LOW — all fixed before deployment.

## AGENTS.md — Project Context Single Source of Truth

**Pattern:** Extract ALL project-level conventions from agent files into one `~/.hermes/AGENTS.md` (or `<project>/AGENTS.md`). Agent files keep ONLY role-specific instructions.

**Extraction principle:** If ≥2 agents would otherwise duplicate a convention → it goes to AGENTS.md. Methodology that only one agent uses (Vane pipeline, 9-stage analysis) stays in the agent file.

**Orchestrator loading:** `plan.md` reads AGENTS.md at cycle start and injects relevant excerpts into every `delegate_task` context.

Full pattern, extraction table, and agent shrinkage reference: `references/agents-md-migration.md`.

## Auditor as Evolution Driver

**Before:** Auditor = silent observer → one-shot Phase 10 report.

**After:** Auditor = persistent cross-cycle evolution driver.

**Key mechanisms:**
- **`auditor_memory.md`** — append-only cross-cycle memory (agent performance trends, mutation log)
- **Auto-apply safe changes** — pitfalls, environment facts, build commands applied automatically when detected ≥2 cycles
- **Mutation proposals** — Promptbreeder-inspired patches to agent files (ADD_INSTRUCTION, REMOVE, REWORD, etc.)
**Topology proposals** — ADAS-inspired changes to the agent graph (add/remove gates, change escalation paths). See `multi-agent-orchestration` → `references/meta-agent-papers-2025-2026.md` for ADAS (evolutionary search), AFlow (MCTS over workflow DAGs), and SDB Architecture (propose/verify/commit/reject). All three now have concrete implementations in plan2.

**plan.md integration:** Auditor section expanded with auto-apply rules table, mutation proposal format, and cross-cycle trend reporting.

Full specification, output format, and EvoAgentX inspiration: `references/auditor-evolution-driver.md`.

When applying this pattern, create `~/.hermes/auditor_memory.md` (empty template) and update `plan.md` to load it at cycle start alongside AGENTS.md.

## Phase 10 — Idea Generator (Cross-Phase Synthesis)

After all other phases complete, the Idea Generator reads EVERY artifact produced in the cycle and produces a forward-looking synthesis report. This is NOT a retrospective (which judges past performance) and NOT an audit (which verifies compliance). It is a creative, cross-cutting analysis.

**What it does (4-axis analysis):**
1. **Unheard Ideas** — Design→implementation gaps: what was promised vs what was built
2. **Connections** — Unsynthesized links between components that coexist but don't interact
3. **Missing Information** — Measurements that were estimated but never actually run
4. **Pipeline Optimization** — Critical path identification with quantified before/after impact

**Plus:** 5–8 Creative Proposals — forward-looking ideas beyond current scope, each with concept, mechanism, and implementation sketch.

**Key technique — Design↔Implementation Gap Detection:**
1. Extract specification from Architecture doc
2. Find implementation reality from Test Report
3. Identify root cause (tool substitution, missing integration, config bug)
4. Propose concrete fix with exact command/code

**Prerequisite:** Read ALL docs artifacts, all source files, the plan, structure.md, and config files before writing a single recommendation. The value is in cross-phase synthesis.

Full methodology, output format, and common gap types: `references/phase-10-idea-generator.md`.

## Tool underuse detection (v1.2)

**Pattern:** When a tool that SHOULD be heavily used is rarely invoked, it may indicate a block — either in the tool itself, in `DELEGATE_BLOCKED_TOOLS`, or in the orchestrator prompt not instructing agents to use it.

**Real case (2026-06-15):** `clarify` was in `DELEGATE_BLOCKED_TOOLS`, so sub-agents could never ask questions. Over many cycles, clarify was called 0 times. The Auditor should detect this anomaly and report: «Tool X was available but used 0 times across N phases — possible block or under-instruction.»

**Auditor check to add:**
- Count tool invocations per agent role across the full cycle
- Flag any tool that: is enabled in the agent's toolset, but was called 0 times, AND makes semantic sense for the role (e.g., clarify for requirements-analyst, delegate_task for orchestrator)
- Report as `MEDIUM` severity finding with proposed investigation: check `DELEGATE_BLOCKED_TOOLS`, check toolset config, check prompt instructions
