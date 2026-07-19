# Meta-Agent Papers 2025-2026 — Research Synthesis

> Generated 2026-06-26. Summarizes three ICLR/arXiv papers applied to plan2 observer architecture.

## ADAS — Automated Design of Agentic Systems (ICLR 2025)

**Authors:** Shengran Hu, Cong Lu, Jeff Clune (UBC, Vector Institute)
**arXiv:** 2408.08435 | **Code:** github.com/ShengranHu/ADAS | **Stars:** 1.6k

**Core idea:** Meta Agent Search — a "meta" agent iteratively programs new agents in code, tests them on benchmarks, adds best performers to an archive, and uses the archive to inform future generations. Turing-complete search space (Python code) — can theoretically discover ANY agent architecture.

**Key mechanism:** Evolutionary search with LLM as mutation operator. Archive stores (code, score) pairs. Each iteration: meta-agent sees archive → generates new agent code → evaluates on benchmark → adds to archive.

**Results:** Auto-discovered agents outperform hand-crafted SOTA. Agents show cross-model AND cross-domain transfer.

**Applied in plan2:** Idea Generator uses ADAS-inspired `(:Mutation)` proposals. Each cycle → proposed changes to plan2. Auditor evaluates viability. Accepted mutations applied via `patch`. ADAS loop: generate → evaluate → select → apply → repeat.

---

## AFlow — Automating Agentic Workflow Generation (ICLR 2025 Oral)

**Authors:** Jiayi Zhang, Jinyu Xiang, Mingchen Zhuge et al. (DeepWisdom/MetaGPT)
**arXiv:** 2410.10762 | **Code:** github.com/FoundationAgents/AFlow | **Stars:** 544

**Core idea:** MCTS over code-represented workflow DAGs. Nodes = LLM invocations (with Operator wrappers: Generate, Format, Review&Revise, Ensemble, Test, Programmer). Edges = Python code (supports conditions, loops, parallelism). Each MCTS tree node = a complete workflow.

**Key mechanism:** 4-phase MCTS cycle: (1) Soft Mixed Probability Selection (λ=0.2 exploration, α=0.4 score weight), (2) LLM-Based Expansion, (3) Execution Evaluation (5 runs for robustness), (4) Experience Backpropagation. Early stop if top-k avg no improvement for N rounds.

**Results:** 5.7% avg improvement over hand-crafted workflows. GPT-4o-mini + AFlow > GPT-4o at 4.55% cost. On MATH lv5: 73.6 vs ADAS 35.4 (×2.1).

**Applied in plan2:** AFlow Orchestrator agent runs in parallel from Phase 0. Uses plan2 phases as Operators. MCTS searches for alternative workflows. Heuristic evaluation via auditor_memory.md + Neo4j. Result stored as `(:AFlowVariant)` in Neo4j. Compared to main plan2 in Phase 10.

---

## SDB Architecture — Stochastic-Deterministic Boundary (arXiv 2026)

**Author:** Vasundra Srinivasan (Independent Researcher, Stanford)
**arXiv:** 2605.20173 | **Code:** github.com/vasundras/agent-runtime-patterns

**Core idea:** Names the "stochastic-deterministic boundary" (SDB) as THE load-bearing primitive of production agent runtimes. Four-part contract: Proposer (LLM) → Verifier (deterministic check) → Commit (durable write) / Reject (typed signal).

**Key findings:**
- 5 open-source frameworks audited: 19/21 LLM-to-action call sites have explicit verifier+commit logic
- 21 agent failure post-mortems: 15 (71%) localize to boundary weaknesses; 17 (81%) fixes strengthen one of 4 parts
- **Replay Divergence:** new failure mode — LLM-based consumers of deterministic event log produce different outputs under model-version change
- Reliability model: y(t) = μt + σξ(t). μ = architectural momentum (pattern choice + SDB strength). σ = per-call LLM variance. As σ shrinks (model improvements), μ becomes dominant lever.

**6 runtime patterns:** P1 Hierarchical Delegation, P2 Scatter-Gather+Saga, P3 Event-Driven Sequencing, P4 Supervisor+Gate, P5 Shared State Machine, P6 Human in the Loop.

**Applied in plan2:** Every observer checkpoint follows SDB contract. Observers: Proposer (read artifact → analyze) → Verifier (check own output) → Commit (CREATE node in Neo4j) / Reject (typed error). SDB fixes the root cause of empty observer outputs: no durable write. System Analyst = plan2's SDB Verifier (4 checks + deviation routing).

---

## FoT — Framework of Thoughts (arXiv 2026)

**Authors:** Felix Fricke, Simon Malberg, Georg Groh (TU Munich)
**arXiv:** 2602.16512 | **Date:** February 18, 2026

**Core idea:** Not a prompting scheme itself, but a **foundation framework** for implementing ANY chain/tree/graph-based reasoning scheme with three built-in optimizations: dynamic graph structures, safe parallel execution, and intelligent caching.

**Key mechanisms:**

1. **Dynamic execution graphs** — Operations can MODIFY the execution graph at runtime (add/remove operations and edges). Unlike GoT's static graph, FoT's graph evolves as the LLM reasons. Constraints protect against race conditions during parallel modification.

2. **Safe parallel execution** — Controller + Scheduler modules. Operations that are ready (all ancestors executed) run in parallel. Graph modification constrained: an operation can only modify its exclusive descendants, not ancestors or non-exclusive descendants.

3. **Caching** — Two levels: Process Cache (within one problem instance) and Persistent Cache (across instances in a dataset). Reuses results of identical operations with identical inputs.

4. **Built-in optimizers** — Optuna for hyperparameter tuning + DSPy for prompt optimization. Optimization itself accelerated by caching (otherwise prohibitively expensive).

**Results:** Average 10.7× speedup across 5 tasks with parallel+persistent caching. Cost reduction up to 46% (Game of 24). Task scores improved on all schemes (ToT +3pp accuracy, GoT -5% mistakes, GoT DM +5% F1).

**Relationship to plan2:** FoT is an infrastructure framework, not a competing orchestrator. Plan2 phases could be implemented as FoT Operations, with the FoT Scheduler determining parallel execution of independent phases and FoT Cache reusing results between cycles. Unlike AFlow (which searches for workflows), FoT provides the runtime for executing them efficiently.
