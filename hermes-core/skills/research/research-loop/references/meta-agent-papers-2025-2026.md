# Meta-Agent & Orchestration Papers (2025–2026)

Condensed knowledge bank: three landmark papers for agent architecture search,
workflow optimization, and production runtime patterns. Use as bootstrap context
when researching agent orchestration, plan2 improvement, or multi-agent system design.

---

## ADAS (ICLR 2025) — Automated Design of Agentic Systems

**arXiv:** 2408.08435 | **Authors:** Shengran Hu, Cong Lu, Jeff Clune (UBC/Vector)  
**Code:** github.com/ShengranHu/ADAS | **Award:** Outstanding Paper (NeurIPS 2024 OWA Workshop)

**Core idea:** Agents shouldn't be hand-designed. Meta-agent writes Python code for new agents,
tests them on benchmarks, keeps an archive of discoveries, and iteratively improves.
Turing-complete search space — code can express any possible agent design.

**Algorithm — Meta Agent Search:**
1. Meta-agent receives archive of past agents + domain tasks
2. Programs a new `forward(self, taskInfo)` function using FM_Module primitives
3. Evaluates agent on benchmark
4. Adds to archive if interesting
5. Repeats — archive feeds back into meta-agent

**Six operator families identified:**
| Family | Examples | Mechanism |
|--------|---------|-----------|
| LLM-as-optimizer | OPRO (DeepMind) | LLM generates → evaluates → analyzes errors → improves |
| Textual gradients | ProTeGi, TextGrad, Trace | Gradient descent in text space |
| Evolutionary + archive | EvoPrompt, Promptbreeder, **ADAS** | Population + mutation + selection |
| Symbolic learning | Agent Symbolic Learning | Agent writes Python to self-modify |
| MCTS-based | AFlow, ReST-MCTS* | Tree search over workflow DAGs |
| Score-based | ScoreFlow | DPO-like on preference pairs |

**Key results:** Auto-discovered agents outperform hand-crafted SOTA. Agents transfer
across models (GPT-4o → Claude) and domains (coding → math).

**Key innovation:** Code > natural language for agent representation. Code allows
inventing new control flow, building blocks, and arbitrary compositions.

---

## AFlow (ICLR 2025 Oral) — Automating Agentic Workflow Generation

**arXiv:** 2410.10762 | **Authors:** Jiayi Zhang, Jinyu Xiang, Mingchen Zhuge et al. (DeepWisdom/MetaGPT)  
**Code:** github.com/FoundationAgents/AFlow | **Status:** ICLR 2025 Oral

**Core idea:** Workflow optimization as MCTS search over code-represented workflows.
Uses pre-defined Operators to dramatically reduce search space vs ADAS.

**Architecture — 4 layers:**
- **Node:** Atomic LLM call (model, prompt, temperature, output format)
- **Operator:** Predefined reusable block (Generate, Format, Review&Revise, Ensemble, Test, Programmer, Custom)
- **Edge:** Python code connecting nodes (conditions, loops, parallel execution)
- **Workflow:** Complete DAG = MCTS tree node

**MCTS variant — 4 phases per iteration:**
1. **Selection:** Soft mixed probability — λ × uniform + (1−λ) × softmax(score). Always can select blank template (prevents local optima).
2. **Expansion:** LLM optimizer (Claude-3.5-sonnet) generates new workflow from selected node's experience.
3. **Evaluation:** 5× runs on validation set (20% of data) for accurate signal.
4. **Backpropagation:** Score + modification + improvement stored at tree node.

**Key results:** 5.7% avg improvement over hand-crafted SOTA. GPT-4o-mini + AFlow > GPT-4o at 4.55% cost. On MATH lv5: AFlow 73.6 vs ADAS 35.4 (×2.1).

**AFlow vs ADAS:**
| | ADAS | AFlow |
|---|---|---|
| Search | Evolutionary (linear archive) | MCTS (tree-structured experience) |
| Space | Full Python agents | Workflows from Operators |
| Efficiency | Low (linear scan) | High (operators cut space) |
| MATH result | 35.4 | 73.6 |
| Transfer | Excellent | Not systematically tested |
| Ambition | Invent new agents | Optimize known patterns |

---

## SDB Architecture (2026) — Production Agent Runtime Patterns

**arXiv:** 2605.20173 | **Author:** Vasundra Srinivasan (Stanford, O'Reilly author)  
**Code:** github.com/vasundras/agent-runtime-patterns | **Date:** May 2026

**Core idea:** The seam where LLM outputs become system actions is the load-bearing
primitive of production agents. Formalize it as the Stochastic-Deterministic Boundary (SDB).

**SDB — Four-part contract:**
- **Proposer:** LLM — generates proposals (text, tool calls, plans)
- **Verifier:** Deterministic code — schema check, business rules, transition predicate
- **Commit:** Durable write — only if verification passes
- **Reject:** Typed signal — structured error back to proposer

**Empirical basis:** Audit of 5 open-source frameworks found verifier+commit at 19/21 LLM-to-action
call sites. 21 failure post-mortems: 15 (71%) localize to SDB weaknesses, 17 (81%) fixes strengthen it.

**Three concerns + 6 patterns:**
| Concern | Pattern P1-P2 | Pattern P3-P5 | Pattern P4-P6 |
|---------|--------------|--------------|--------------|
| Coordination | P1: Hierarchical Delegation | P2: Scatter-Gather + Saga | — |
| State | P3: Event-Driven Sequencing | P5: Shared State Machine | — |
| Control | P4: Supervisor + Gate | P6: Human in the Loop | — |

**Reliability model:** y(t) = μt + σξ(t)
- σ = per-call LLM variance (compresses with each model generation)
- μ = architectural momentum (from pattern choice + SDB strength)
- **As σ → 0, μ becomes the dominant lever**

**Replay Divergence (new failure mode):** Deterministic event log + stochastic LLM consumers
→ different downstream outputs under model-version change. P5 (Shared State Machine)
more resilient than P3 (Event-Driven Sequencing).

**5-step selection methodology:** Classify Runtime → Choose State Spine → Wrap with
Coordination → Bound with Control → Sequence the Build → 6-line Architecture Decision Record.

---

## How these relate to each other

```
ADAS ──► "Любого агента можно открыть автоматически" (Turing-complete search)
   │
   └──► AFlow ──► "MCTS эффективнее эволюции для поиска workflow" (×2.1 на MATH)
            │
            └──► SDB ──► "Любой найденный workflow нужно обернуть в production contract"
                         (propose→verify→commit/reject иначе сломается в проде)
```

**For plan2 application:** ADAS → meta-agent that programs plan2 variants. AFlow → MCTS\nover plan2 phase sequences. SDB → wrap every plan2 decision in propose/verify/commit/reject.\nFoT → dynamic execution graph for plan2 phases with parallel execution + caching.\n\n---\n\n## Framework of Thoughts — FoT (Feb 2026)\n\n**arXiv:** 2602.16512 | **Authors:** Felix Fricke, Simon Malberg, Georg Groh (TU Munich)\n**Date:** February 2026 | **Code:** released with paper\n\n**Core idea:** Not a prompting scheme — a **foundation framework** for implementing\nand optimizing ANY chain/tree/graph reasoning scheme. Re-implements ToT, GoT, and ProbTree\ninside FoT and shows 10.7× avg speedup via parallel execution + caching.\n\n**Three innovations over GoT framework:**\n1. **Dynamic graph structures** — Execution graph can be modified BY operations during execution (not static)\n2. **Safe parallel execution** — Scheduler + Controller with race-condition prevention via ancestor/descendant constraints\n3. **Persistent caching** — Process cache (within one instance) + Persistent cache (across dataset)\n4. **Built-in optimizers** — Optuna for hyperparameters, DSPy for prompts\n\n**Architecture:**\n- **Execution Graph:** Directed multigraph of Operations + Connections (dynamic, can change)\n- **Reasoning Graph:** Byproduct — which thoughts influenced which (static, only past)\n- **Operations:** Functions that (1) generate new thoughts AND (2) modify the execution graph\n- **Scheduler:** Only schedules operations whose ancestors are complete\n- **Controller:** Executes operations, respecting graph constraints\n\n**Safe parallel constraints:** Operation o can: see ancestors + descendants + self. CANNOT touch\nancestors (already executed) or non-exclusive descendants (race condition). CAN modify exclusive\ndescendants. This prevents data races while allowing dynamic graph growth.\n\n**Key results:**\n- 10.7× avg speedup across 5 tasks (ToT on Game of 24: 782s → 22s, 35.4×)\n- Cost reduction: Game of 24: 29.6¢ → 16.1¢ (-46%) with persistent cache\n- Hyperparameter optimization: +3-5% task scores while reducing costs\n\n**FoT vs related work:**\n| | GoT (Besta) | AFlow (Zhang) | ADAS (Hu) | **FoT (Fricke)** |\n|---|---|---|---|---|\n| What | Prompting scheme | Workflow search | Agent evolution | **Framework for schemes** |\n| Graph | Static, manual | Workflow DAG | Code (Turing) | **Dynamic, runtime-modifiable** |\n| Parallel | No | No (MCTS seq) | No | **Yes + race safety** |\n| Cache | No | No | No | **Process + Persistent** |\n| Opt | No | MCTS self | Evolutionary | **Optuna + DSPy built-in** |\n\n**For plan2:** FoT's execution graph model maps directly to plan2 phases as Operations.\nPhases could be dynamically added/removed/parallelized by the Scheduler, with results\ncached between cycles. Safe parallel constraints would allow multiple independent phases\nto run concurrently (e.g., Research + Architecture).
