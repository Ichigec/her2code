# Plan3 — Local Multi-Model Orchestrator (Full Specification)

## Overview

Plan3 is a fully-local variant of the plan2 orchestrator for DGX Spark 128GB.
Three specialized models replace one cloud model, with hard model-routing rules.

## Model Routing Table

| Role Type | Model | Provider | Benchmarks | Agent Files |
|-----------|-------|----------|------------|-------------|
| **Reasoning** | `qwen3.6-35b` | `custom:local` | GPQA 86.0 | requirements, system-analyst, researcher, architect, auditor, critic, idea-generator, knowledge-curator, enterprise-architect, aflow-orchestrator |
| **Coding** | `nex-n2-mini` | `custom:local` | SWE-Bench 74.4, Terminal-Bench 60.7 | techlead, developer, devops, jidoka, security, deployment, tester |
| **Simulation** | `agentworld` | `custom:local` | AgentWorldBench 56.39 | sim-rl-agent |

**Rule:** NEVER delegate coding to Qwen3.6. NEVER delegate reasoning to Nex.

## Agent Files

```
~/.hermes/agents/plan3.md              — Orchestrator (based on plan2.md)
~/.hermes/agents/plan3/
├── requirements-agent.md              → 🧠 Qwen3.6
├── system-analyst.md                  → 🧠 Qwen3.6
├── researcher.md                      → 🧠 Qwen3.6
├── architect-agent.md                 → 🧠 Qwen3.6
├── techlead-agent.md                  → 🤖 Nex
├── developer-agent.md                 → 🤖 Nex
├── devops-engineer.md                 → 🤖 Nex
├── jidoka-evaluator.md                → 🤖 Nex
├── security-agent.md                  → 🤖 Nex
├── deployment-agent.md                → 🤖 Nex
├── tester-agent.md                    → 🤖 Nex
├── sim-rl-agent.md                    → 🔮 AgentWorld (NEW)
├── auditor.md                         → 🧠 Qwen3.6
├── critic.md                          → 🧠 Qwen3.6
├── idea-generator.md                  → 🧠 Qwen3.6
├── knowledge-curator.md               → 🧠 Qwen3.6
├── enterprise-architect.md            → 🧠 Qwen3.6
└── aflow-orchestrator.md              → 🧠 Qwen3.6
```

Each sub-agent has `model:` and `provider:` in frontmatter.
Plan3 orchestrator includes a Model Routing Table section and Pipeline Modes (Fugu/Fusion).

## Pipeline Modes

| Mode | Activation | Flow | Time |
|------|-----------|------|------|
| Full Cycle | default | 10 phases BDUF | 10-30 min |
| Fugu | "быстро", "fugu", "fast" | Thinker(Qwen3.6)→Worker(Nex)→Verifier→Synthesizer | ~11s |
| Fusion | "проанализируй", "сравни", "fusion" | Qwen3.6 ∥ Nex → Synthesizer | ~8s |

## Context Budget

Problem: full plan2.md = 66KB = ~30K tokens. With history = 100K+. On local Qwen3.6 = 200s+ prefill.

Solution: trimmed prompt (~20K tokens, ~15s prefill):
- plan2.md → skill `multi-agent-orchestration-plan3`
- In prompt: current phase (0.5K) + artifact summary (2K) + routing table (0.5K) + history (15K)
- Full artifacts via read_file as needed

## Deployment

Requires llama.cpp-dgx + llama-swap with matrix mode (3 models, ~100 GB).
Config: `/home/user/dev/llama/llama-swap.yaml`
Model download: `/home/user/dev/llama/download-models.sh`

## Code Changes

`agent/observer.py`: +3 plan3 mutations in `_ADAS_MUTATIONS` + plan3 periodic pipeline_depth.

## GUI

New `SubagentDropdown` component in `apps/desktop/src/app/shell/subagent-dropdown.tsx`.
Statusbar items: 🦞 Claw (action), 🎻 P2 (menu), 🧬 P3 (menu with model groups).
