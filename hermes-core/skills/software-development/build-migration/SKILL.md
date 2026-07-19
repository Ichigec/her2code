---
name: build-migration
description: "Build Agent migration guide — full 7-phase engineering lifecycle for porting the Hermes build agent to other platforms (Cursor, Claude Code, OpenCode, custom agents). Self-contained reference."
version: 1.0.0
tags: [build, agent, migration, lifecycle, tdd, security, architecture, multi-platform]
---

# Build Agent — Migration Guide

Self-contained reference for porting the Hermes **build agent** full engineering
lifecycle to another platform (Cursor, Claude Code, OpenCode, custom agents).

You do **not** need access to `build.md` or Hermes internals to implement this.

## 1. Purpose

The build agent delivers **safe, iterative software** through a mandatory
seven-phase lifecycle:

- Gathers requirements at every stage (not just at the start).
- Designs before coding (BDUF).
- Implements with TDD and secure-by-default patterns.
- Gates quality with tests, review, and SAST.
- Documents deployment and operations explicitly.
- Closes each cycle with metrics and retrospective.

**Outcomes per cycle:**
- Working, tested, reviewed code.
- Traceable docs: requirements → architecture → plan → feature README → deployment → retro.
- Security pipeline active on every non-trivial change.
- Reproducible builds (lockfiles, `.env.example`).

## 2. Lifecycle Overview

| # | Phase | Artifact | Mandatory |
|---|-------|----------|-----------|
| 1 | Requirements | `docs/requirements/<slug>.md` | Yes |
| 2 | Architecture | `docs/architecture/<slug>.md` | Yes |
| 3 | Plan (BDUF) | `.hermes/plans/<ts>-<slug>.md` or equivalent | Yes |
| 4 | Implement | Code + lockfiles + `docs/<feature>/README.md` | Yes |
| 5 | Quality | Green tests + review + security gate | Yes |
| 6 | Deployment | `docs/deployment/<slug>.md` | Yes |
| 7 | Iterate | `docs/retrospectives/<date>-<slug>.md` | Yes |

**Depth scales with complexity.** A one-line fix still passes all phases but produces proportionally short artifacts. Phases are never skipped.

### Gates

| Transition | Gate |
|------------|------|
| Requirements → Architecture | Requirements doc or explicit assumptions |
| Architecture → Plan | Architecture doc + **user sign-off** |
| Plan → Implement | Plan saved; principles checklist passed |
| Implement → Quality | Code complete; checkpoint audits clean |
| Quality → Commit | Tests green; review OK; no High/Critical security findings |
| Quality → Deployment | Deployment approach documented |
| Deployment → Iterate | Retro written |

**Commit policy:** only when the user requests it (or workflow explicitly includes commit).

## 3. Cross-Cutting Principles

Apply at **every** phase.

| Principle | Rule |
|-----------|------|
| **KISS** | Simplest solution that works |
| **DRY** | Single source of truth |
| **YAGNI** | Build only what is needed now |
| **BDUF** | Requirements → Architecture → Plan before code |
| **SOLID** | SRP, OCP, LSP, ISP, DIP |
| **APO** | No optimization without measurement |
| **Versioning** | Lockfiles, pinned deps, `.env.example`, reproducible build/run |

## 4. Per-Phase Playbook

### Phase 1 — Requirements
**Goal:** Clear, testable requirements before design.
- Who are the actors? What is the user journey?
- Acceptance criteria and out-of-scope?
- NFRs: performance, security, availability, scalability?
- Constraints: timeline, stack, compliance?
**Output:** `docs/requirements/<slug>.md`

### Phase 2 — Architecture
**Goal:** Technical design with user collaboration before planning.
- Monolith / microservices / layered / event-driven / agent-loop?
- Integrations: REST, gRPC, MCP, A2A, queues?
- Agent systems: context vs memory vs docs; orchestration; toolset boundaries?
**Output:** `docs/architecture/<slug>.md` — get user sign-off.

### Phase 3 — Plan (BDUF)
**Goal:** Bite-sized, TDD-oriented implementation plan.
- Tasks: 2–5 minutes each. Include exact paths, code snippets, commands.
- Principles checklist before save: KISS, DRY, YAGNI, BDUF, SOLID, APO, Versioning.
**Output:** `.hermes/plans/YYYY-MM-DD_HHMMSS-<slug>.md`

### Phase 4 — Implement
**Skills:** TDD, secure-coding, implementation-delivery.
**Loop per task:**
1. Write failing test → confirm failure.
2. Minimal implementation → test passes.
3. Lint + targeted tests after every edit.
4. Checkpoint: secure-coding self-audit on `git diff` at each milestone.
**Documentation:** `docs/<feature>/README.md`

### Phase 5 — Quality
1. Self-review or delegate: spec compliance → code quality.
2. Full test suite green.
3. **Mandatory security gate** — run scanners on diff (semgrep, bandit, gitleaks).
4. No commit with High/Critical findings.

### Phase 6 — Deployment
**Output:** `docs/deployment/<slug>.md`
Document: build/publish commands, CI workflows, env vars, logging, metrics, alerts, rollback.

### Phase 7 — Iterate
**Output:** `docs/retrospectives/YYYY-MM-DD-<slug>.md`
Capture: metrics, what worked/didn't, action items, tech debt, principle compliance.

## 5. Security Pipeline

Always on for implementation and quality phases.

**While Implementing:**
- Parameterized queries; no `shell=True`; no hardcoded secrets.
- Validate all untrusted input at boundaries.
- OWASP Top 10 / CWE Top 25 awareness.
- Checkpoint: self-audit the diff at each logical milestone.

**Before Commit — SAST Audit (mandatory):**
1. Run scanners on diff: semgrep, bandit, gitleaks, pip-audit, npm audit.
2. Grep fallback when scanners absent.
3. Baseline-aware triage: only new High/Critical findings block commit.
4. Independent security reviewer — never review your own code.

## 6. Agent-Specific Concerns

When the build agent works on code agents (LLM tool users):

**Context:** System prompt (fixed role, lifecycle rules, gates) + Retrieved (skills loaded on demand, repo docs, RAG) + Ephemeral (conversation turns, tool outputs).

**Memory:** Short-term (conversation buffer) → Working (plan/requirements docs in repo) → Long-term (vector store / files).

**Orchestration:** Saved plans → dispatch fresh subagent per task. Each subagent gets full task text. Two-stage review after each task: spec compliance → code quality. Toolsets: least privilege per role.

## 7. Documentation Contract

Every feature must have a doc an agent can use without chat history: `docs/<feature>/README.md`
Required: Goal, Context, Architecture summary, File map, Setup, Run, Test, Key decisions, Security notes.

## 9. Research & Future Improvements

See [`references/vane-patterns.md`](references/vane-patterns.md) — analysis of Vane (35k★ AI answering engine)
identifying 9 architecture patterns applicable to build-migration:

| Pattern | What it solves |
|---------|---------------|
| Mode-based complexity | Quick/Standard/Deep — scale phase depth to task size |
| Classification-triage | Pre-phase decision: which phases are actually needed? |
| Reasoning preamble | Micro-plan before every implementation step |
| Anti-patterns in prompts | `<mistakes_to_avoid>` section per phase |
| Iteration budget + done | Explicit step tracking with completion signal |
| Sidecar widgets | Parallel lint/SAST/metrics during implementation |
| Action registry | Contextual phase enablement (skip architecture for config changes) |

Use this to confirm a successful migration:
- [ ] Mission statement present (safe, iterative, docs, analysis, RE)
- [ ] All 7 phases listed with artifacts
- [ ] Cross-cutting principles referenced
- [ ] Gates between phases documented
- [ ] Security pipeline present
- [ ] Commit-only-on-request policy stated
- [ ] Subagent plan execution documented

Skills/bundles needed: build-engineering-standards, requirements-analysis, architecture-design, plan, test-driven-development, secure-coding, implementation-delivery, requesting-code-review, sast-audit, deployment-operations, continuous-improvement, subagent-driven-development.

Repo structure (created on first use):
```
docs/requirements/  docs/architecture/  docs/deployment/
docs/retrospectives/  docs/<feature>/README.md
.hermes/plans/
```
