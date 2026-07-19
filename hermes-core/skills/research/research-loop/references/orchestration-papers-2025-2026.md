# Multi-Agent Orchestration Papers (ICLR 2025 + 2026)

Key papers discussed with Pavel on 2026-06-26. For the research-loop skill.

## ADAS (Automated Design of Agentic Systems)
- **Venue:** ICLR 2025, Outstanding Paper (NeurIPS 2024 Open-World Agent Workshop)
- **Authors:** Shengran Hu, Cong Lu, Jeff Clune (UBC / Vector Institute)
- **arXiv:** 2408.08435
- **Code:** github.com/ShengranHu/ADAS
- **Key mechanism:** Meta Agent Search — LLM as mutation operator over agent code. Evolutionary search discovers agents that outperform hand-crafted SOTA.
- **Key insight:** Agents can invent better agents than humans. Code representation is Turing-complete → any possible agent design is reachable.
- **Plan2 application:** Idea Generator as meta-agent, `(:Mutation)` nodes as evolutionary archive, plan2 phases as search space.

## AFlow (Automating Agentic Workflow Generation)
- **Venue:** ICLR 2025 Oral
- **Authors:** Jiayi Zhang et al. (DeepWisdom / MetaGPT team)
- **arXiv:** 2410.10762
- **Code:** github.com/FoundationAgents/AFlow
- **Key mechanism:** MCTS over code-represented workflow DAGs. Operators (Generate, Format, Review, Revise, Ensemble, Test, Programmer) as search primitives. Soft mixed probability selection + LLM-based expansion + execution evaluation + experience backpropagation.
- **Key result:** +5.7% avg over hand-crafted, GPT-4o-mini + AFlow > GPT-4o at 4.55% cost, 2.1× over ADAS on MATH.
- **Plan2 application:** AFlow Orchestrator agent searches alternative plan2 workflows via MCTS, compared against main plan at Phase 10.

## SDB Architecture (Stochastic-Deterministic Boundary)
- **Venue:** arXiv, May 2026
- **Author:** Vasundra Srinivasan (Stanford)
- **arXiv:** 2605.20173
- **Code:** github.com/vasundras/agent-runtime-patterns
- **Key mechanism:** Four-part contract: PROPOSER (LLM) → VERIFIER (deterministic check) → COMMIT (durable write) → REJECT (typed signal). Six runtime patterns: Hierarchical Delegation, Scatter-Gather+Saga, Event-Driven Sequencing, Shared State Machine, Supervisor+Gate, Human in the Loop.
- **Key insight:** As model variance σ compresses, architectural momentum μ becomes the dominant reliability lever. y(t) = μt + σξ(t).
- **Plan2 application:** Every phase transition is an SDB contract. System Analyst = Verifier. Observer checkpoint protocol = explicit SDB implementation.

## Framework of Thoughts (FoT)
- **Venue:** arXiv, February 2026
- **Authors:** Felix Fricke, Simon Malberg, Georg Groh (TU Munich)
- **arXiv:** 2602.16512
- **Key mechanism:** Foundation framework for implementing ANY prompting scheme. Dynamic graph structures (execution graph modifiable at runtime), safe parallel execution with race-condition protection, process + persistent caching, built-in Optuna + DSPy optimization.
- **Key result:** 10.7× average speedup via parallelization + caching. Caching reduces costs by 14-46%.
- **Plan2 application:** Phases as FoT Operations, Scheduler for parallel execution, Process Cache within cycles, Persistent Cache across cycles.
