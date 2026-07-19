# Orchestration Papers — Reference Bank

Key papers on agent orchestration, workflow optimization, and self-evolving systems.
Referenced in plan2 design and observer architecture.

## ADAS — Automated Design of Agentic Systems
- **Authors:** Shengran Hu, Cong Lu, Jeff Clune (UBC/Vector Institute)
- **Venue:** ICLR 2025 (Outstanding Paper, NeurIPS 2024 Open-World Agent Workshop)
- **arXiv:** 2408.08435
- **Code:** github.com/ShengranHu/ADAS
- **Core idea:** Meta Agent Search — LLM programs new agents in code, evaluates them,
  stores best in archive, iterates. Auto-discovered agents outperform hand-crafted SOTA.
- **Key insight for plan2:** Evolutionary search over orchestrator architectures.
  Idea Generator + Critic + Auditor together form an ADAS loop: generate mutations →
  evaluate fitness → select → repeat across cycles.
- **6 operator families:** LLM-as-optimizer, textual gradients, evolutionary+archive,
  symbolic learning, MCTS-based, score-based.

## AFlow — Automating Agentic Workflow Generation
- **Authors:** Jiayi Zhang et al. (DeepWisdom/MetaGPT team)
- **Venue:** ICLR 2025 Oral
- **arXiv:** 2410.10762
- **Code:** github.com/FoundationAgents/AFlow
- **Core idea:** MCTS over code-represented workflow DAGs. Operators (Generate, Format,
  Review, Revise, Ensemble, Test, Programmer) as building blocks. Soft mixed probability
  selection. 10.7× average speedup with parallel+caching.
- **Key insight for plan2:** Phases as AFlow Operators, MCTS for workflow search.
  AFlow Orchestrator runs parallel to plan2, returns alternative workflow for comparison.

## SDB Architecture — Stochastic-Deterministic Boundary
- **Author:** Vasundra Srinivasan (Independent, Stanford)
- **Venue:** arXiv:2605.20173, May 2026
- **Code:** github.com/vasundras/agent-runtime-patterns
- **Core idea:** Four-part contract at LLM→action boundary: Proposer (LLM) → Verifier
  (deterministic check) → Commit (durable write) → Reject (typed signal). 71% of
  production agent failures localize to boundary weaknesses.
- **6 runtime patterns:** Hierarchical Delegation, Scatter-Gather+Saga, Event-Driven
  Sequencing, Shared State Machine, Supervisor+Gate, Human in the Loop.
- **Key insight for plan2:** Every phase transition and every observer checkpoint
  must follow SDB contract. Architectural momentum μ dominates model variance σ
  as models improve. System Analyst = SDB Verifier for the plan2 lifecycle.
- **Replay Divergence:** LLM consumers of deterministic event log produce different
  outputs under model-version change. P5 (Shared State Machine with CAS) is resistant.

## FoT — Framework of Thoughts
- **Authors:** Felix Fricke, Simon Malberg, Georg Groh (TU Munich)
- **Venue:** arXiv:2602.16512, Feb 2026
- **Core idea:** Foundation framework for implementing ANY prompting scheme.
  Dynamic execution graphs (modifiable in runtime), safe parallel execution with
  race-condition prevention, process+persistent caching, Optuna+DSPy optimization.
- **Key insight for plan2:** Replace fixed phase order with FoT-style execution graph.
  Scheduler decides what to run next. Operations can modify the graph dynamically.
  FoT could be the runtime for plan2 phases.

## GoT — Graph of Thoughts
- **Authors:** Besta et al. (ETH Zurich SPCL)
- **Venue:** 2023
- **Code:** github.com/spcl/graph-of-thoughts
- **Core operations:** Generate, Aggregate, Refine, Score, Improve.
- **Key insight for plan2:** Plan as Graph of Operations — not a linear chain.
  Aggregate merges parallel research branches. Score acts as automatic gate
  before passing to next phase. Refine enables iterative improvement within
  a phase instead of single-attempt.
