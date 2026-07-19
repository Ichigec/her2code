# Multi-Agent Orchestrator Variants (plan/plan1/plan2/plan3)

## Architecture Overview

Pavel runs **4 orchestrator variants**, each in `~/.hermes/agents/plan*.md` with a corresponding `~/.hermes/agents/plan*/` subdirectory of sub-agent definitions.

| Variant | File | Orchestrator Model | Sub-agents | Key Feature |
|---------|------|--------------------|------------|-------------|
| **Plan** (v1) | `plan.md` | deepseek-v4-pro | — | Original orchestrator, minimal features |
| **Plan1** | `plan1.md` | **glm-5.2 / zai** | 18 in `plan1/` | GLM orchestrator roles + DeepSeek sub-agents (cloud hybrid) |
| **Plan2** | `plan2.md` | deepseek-v4-pro | 20 in `plan2/` | Full feature set: structured JSON research, Tech Lead v3 sub-orchestrator, PEP/PDP gates |
| **Plan3** | `plan3.md` | qwen3.6-35b / local | 18 in `plan3/` | Fully local: multi-model router (Qwen+Nex+AgentWorld), Fugu/Fusion pipeline modes |

## GUI Buttons

Statusbar order: `🦞 Claw` → `🚀 P1` → `🎻 P2` → `🧬 P3` → `👁 Observers`

- `P1` = Plan1 dropdown (GLM/DeepSeek agents grouped by model)
- `P2` = Plan2 dropdown (all agents on Kimi/DeepSeek)
- `P3` = Plan3 dropdown (agents grouped by local model: Qwen/Nex/AgentWorld)

## Model Routing Strategy by Variant

### Plan1 — GLM orchestrator + DeepSeek execution

| Role type | Model | Provider | Agents |
|-----------|-------|----------|--------|
| Orchestrator (research, planning, architecture) | `glm-5.2` | `zai` | researcher, system-analyst, techlead-agent, architect-agent, enterprise-architect, aflow-orchestrator |
| Execution (code, test, deploy, security) | `deepseek-v4-pro` | `deepseek` | developer-agent, devops-engineer, security-agent, tester-agent, deployment-agent, requirements-agent, auditor, critic, idea-generator, knowledge-curator, jidoka-evaluator, sim-rl-agent |

### Plan2 — All DeepSeek (cloud)

Single model for all roles. CitationAgent uses `kimi-k2.7-code`. Dev Skeptic also on kimi.

### Plan3 — Fully local multi-model

| Role type | Model | Why |
|-----------|-------|-----|
| Reasoning | `qwen3.6-35b` | GPQA 86.0 |
| Coding | `nex-n2-mini` | SWE-Bench 74.4 |
| Simulation | `agentworld` | AgentWorldBench 56.39 |

## Lifecycle (all variants share the same 10-phase BDUF structure)

```
Phase 0:   Bootstrap + Capability Gate + AFlow + Observers spawn
Phase 1:   Requirements → docs/requirements/<slug>.md
Phase 2:   System Analysis → docs/system-analysis/<slug>.md
Phase 3.0: Research Plan (RQs) ── GATE A
Phase 3.1: Parallel Execution (5-7 sub-agents + debate) ── GATE B
Phase 3.2: Synthesis (JSON structured + .md view) ── GATE C
Phase 3.3: Citation Verification (≥90% valid) ── GATE D
Phase 4:   Architecture Trio (parallel: Architect + Enterprise + Project)
Phase 5:   Plan BDUF (Tech Lead → .hermes/plans/<ts>-<slug>.md + dag-state.json)
Phase 5.5: Pre-Flight Gate (7 BLOCKING checks)
Phase 6:   Progressive Dev Pipeline (Skeptic→Pragmatic→Creative→Maverick)
Phase 6a:  Integration Gate (DevOps)
Phase 6.5: Verification (System Analyst: 4 checks)
Phase 7:   Quality (SAST clean)
Phase 8:   Deployment
Phase 8.5: Acceptance Testing (traceability matrix)
Phase 9:   Post-Deploy Research
Phase 10:  Quadruple Report + AFlow Comparison
```

## What was ported from Plan3 → Plan2 (July 2026)

1. **Structured JSON research output** — GATE B/C/D now check `.json` (schema `research-output-v1`) instead of `.md` prose. Stricter: 7 completeness checks.
2. **Auto-routing by `routing_target`** — data-driven delivery instead of prompt-based instructions.
3. **Research filtering per StandardWork** — `must_see: true` hard constraint, EXIT-style tag matching, `research_filter.py`.
4. **RLEF Feedback Loop** — pattern detection after every 2nd SW, plan revision, loop guards (max 3 attempts/SW, max 150% budget).
5. **Developer escape hatch** — developer can query deep-plan-researcher for filtered-out findings.

## What was NOT ported (intentionally)

- Multi-Model Router — Plan2 is cloud-only (deepseek), no local model stack
- Fugu/Fusion pipeline modes — these break sequential execution
- Phase 6 orchestrator-direct — Plan2 delegates to Tech Lead v3 sub-orchestrator (better for sequential)

## Creating a New Variant

1. Copy an existing `planN.md` → `planN+1.md`, update frontmatter (label, model, provider, emoji)
2. Copy `agents/planN/` → `agents/planN+1/`, fix all frontmatter model/provider values
3. Add `PLAN(N+1)_AGENTS` to `subagent-dropdown.tsx`
4. Add statusbar item to `desktop-controller.tsx` + `use-statusbar-items.tsx` (4-point sync, see SKILL.md)
5. Update `/agent planN` references inside the orchestrator file
6. Update Model Routing table + all `delegate_task` model/provider values
7. Build: `cd apps/desktop && npm run pack`
