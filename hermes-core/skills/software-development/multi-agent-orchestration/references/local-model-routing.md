# Local-Only Model Routing (DGX Spark / any Linux)

When ALL plan2 phases + observers must run on local models (no cloud API), 
this routing table replaces the cloud-based one. 

**Hardware assumed:** DGX Spark 128GB (or any machine with ≥100GB RAM).
Three models via llama-swap matrix: Qwen3.6 Q8_0, Nex-N2-mini Q8_0, AgentWorld Q4_K_M.

## Routing Rule

```
Writes code or works in terminal → Nex-N2-mini 🤖
Reasons, analyzes, designs       → Qwen3.6-35B 🧠
Simulates environments           → AgentWorld 🔮
```

## Benchmark Justification

| Criterion | Qwen3.6 | Nex-N2-mini | Δ | Winner for |
|-----------|---------|-------------|---|------------|
| GPQA Diamond | **86.0** | 82.6 | +3.4 | Reasoning roles |
| SWE-Bench Verified | 73.4 | **74.4** | +1.0 | Coding roles |
| Terminal-Bench 2.1 | 51.5 | **60.7** | **+9.2** | Terminal roles |
| IFEval | — | **89.1** | — | Instruction-following roles |
| AgentWorldBench | ~48 | — | **56.39** | Simulation roles |
| MTP speed | **50 tok/s** | 40 | +25% | Speed-critical roles |

## Full Assignment (29 roles)

### Qwen3.6 Q8_0 🧠 — 16 reasoning roles

| System | Roles |
|--------|-------|
| **Plan2 (analysis, phases 1-4)** | Orchestrator, Requirements Analyst, System Analyst, Researcher, Architect |
| **Plan2 (observers, phase 10)** | Auditor, Critic, Idea Generator (ADAS), Knowledge Curator, Enterprise Architect, AFlow Orchestrator |
| **Observer System (always-on)** | Observer Orchestrator (v5), Auditor (inline/deep/session-end), Critic, Idea Generator, Knowledge Curator |

### Nex-N2-mini Q8_0 🤖 — 12 tool-using roles

| System | Roles |
|--------|-------|
| **Plan2 (execution, phases 5-8.5)** | Tech Lead, Developers ×7, DevOps Engineer, Jidoka Evaluator, Security Agent, Deployment Agent, Tester |

### AgentWorld Q4_K_M 🔮 — 1 simulation role

| System | Role |
|--------|------|
| **Sim RL (outside cycle)** | Sim RL trainer, environment state predictor, adversarial scenario generator |

## Claw

Claw maintenance cycle = 5 deterministic scripts (Python/JS). Models NOT needed. Use `no_agent=true` in cron.

## Orchestrator Optimization

Full plan.md (30KB) + history = 120K tokens → 200s prefill on DGX Spark. 
**Fix:** keep plan.md in `skill_view`, pass only current phase context (~2K tokens) 
to orchestrator prompt. Active context ~20-40K tokens → 8-15s per turn.

## Switch Commands (Hermes)

```bash
/model custom:local:nex     # Phases 5-8.5 (code, terminal)
/model custom:local:qwen    # Phases 1-4 + observers (reasoning)
/model custom:local:world   # Simulations
```

## Memory Budget

```
Nex-N2-mini Q8_0 + 256K Q8 cache  = 35 + 3 + 3 = ~41 GB
Qwen3.6 Q8_0    + 256K Q8 cache  = 35 + 3 + 3 = ~41 GB  
AgentWorld Q4   + 64K Q8 cache   = 20 + 1 + 2 = ~23 GB
                                     TOTAL = ~105 GB  ⚠️ tight

Mitigation: AgentWorld in Q3_K_L (→ ~18 GB total) or Qwen3.6 at 128K context.
```

For the finalized 3-model Q8 config with exact numbers and llama-swap.yaml, 
see `local-model-serving` → `references/dgx-spark-deployment.md`.
