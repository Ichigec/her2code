# Planning & Orchestrator Agents: Research Knowledge Bank

Condensed from a 5-subagent parallel research session (2026-06-24, ~250 API calls across arxiv, GitHub, HN, blogs).
Full artifacts at `/home/user/llm_planning_research_report.md`, `agentic_reasoning_patterns.md`, `coding_agent_architecture_research.md`, `research-multi-agent-best-practices.md`.

---

## Key Academic Papers

| Paper | arXiv | Year | Venue | Key Innovation |
|-------|-------|------|-------|----------------|
| ReAct | 2210.03629 | 2022 | ICLR 2023 | Reasoning + Acting interleaved loop |
| Tree of Thoughts | 2305.10601 | 2023 | NeurIPS 2023 | BFS/DFS tree search over reasoning steps |
| Plan-and-Solve | 2305.04091 | 2023 | ACL 2023 | Plan-then-execute two-stage prompting |
| Graph of Thoughts | 2308.09687 | 2024 | AAAI 2024 | DAG reasoning with merge/refine/generate ops |
| Reflexion | 2303.11366 | 2023 | NeurIPS 2023 | Verbal RL — self-reflection without weight updates |
| RAP | 2305.14992 | 2023 | EMNLP 2023 | MCTS with LLM as world model + reward function |
| ReWOO | 2305.18323 | 2023 | — | Decoupled reasoning from observations, 5× token-efficient vs ReAct |
| LLMCompiler | 2312.04511 | 2023 | ICML 2024 | DAG-based parallel function calling |
| AFlow | 2410.10762 | 2024 | ICLR 2025 | MCTS over workflow DAGs for auto-discovered agent architectures |
| ADAS | — | 2025 | ICLR 2025 | Evolutionary search over agent architectures (LLM as mutation operator) |
| ReST-MCTS* | 2406.03816 | 2024 | — | Process reward MCTS for self-training reasoning |
| Framework of Thoughts | 2602.16512 | 2026 | — | Unified dynamic CoT/ToT/GoT selection |
| SDB Architecture | 2605.20173 | 2026 | — | Stochastic-Deterministic Boundary — propose/verify/commit/reject contract |
| Multi-Agent Orchestration | 2511.15755 | 2025 | — | 348 trials: multi-agent > single-agent for decision support |
| Plan Reuse | 2512.21309 | 2025 | — | Caching LLM plans for latency reduction |

## Reasoning Pattern Comparison

| Pattern | Token Cost | Best For | When NOT to use |
|---------|-----------|----------|-----------------|
| CoT | Medium | Math, logic | Simple factual queries |
| ToT | High | Planning, puzzles | Linear problems |
| GoT | Very High | Complex synthesis | Single-path reasoning |
| ReAct | High | Tool use, QA | Latency-sensitive |
| Reflexion | Medium | Iterative tasks | One-shot tasks |
| Plan-and-Solve | Medium | Structured problems | Dynamic environments |
| ReWOO | **Low** | Multi-hop QA, parallel tools | Conditional tool chains |
| LLMCompiler | Medium | Tool orchestration | Single-tool tasks |

## Production Patterns (from Anthropic, Cursor, L-TPS, $47K post-mortem)

1. **Triple Guard**: MAX_STEPS + USD budget gate + LoopDetector (hash tool inputs) — 3 independent safety mechanisms
2. **Jidoka (Independent Evaluator)**: Separate LLM context, skepticism-tuned. NEVER let agent evaluate its own work.
3. **Standard Work Contracts**: Define "done" BEFORE work starts. Acceptance criteria + verification method.
4. **Artifact-based communication**: Sub-agents produce structured artifacts, not open-ended chat. No agent-to-agent P2P loops.
5. **Kaizen Ledger**: Every failure → permanent rule → injected into future worker prompts. "Every failure makes the system better."
6. **Durable event log + checkpoints**: State outside the engine. Crash → resume from last checkpoint.
7. **Model router (complexity-based)**: ~80% of calls don't need frontier models. L1-L5 classification → appropriate model.
8. **Dynamic context discovery (pull, not push)**: Files-as-context, grep/search for relevant info. A/B test: -46.9% tokens.
9. **Per-conversation USD budget** (not token budget): Hard dollar ceiling. $0.50 support, $5 research, $20 batch.
10. **Orchestrator-mediated communication**: No agent-to-agent clarification loops. Orchestrator has termination authority.

## Key Anti-Patterns

| Anti-Pattern | Consequence | Fix |
|---|---|---|
| Sub-agents chat directly | Infinite ping-pong ($47K) | Step cap + loop detector |
| Self-evaluation | Confident praise for mediocre work | Independent evaluator |
| Token budgets instead of $ | Abstract, easy to misconfigure | Charge actual API rates |
| All calls to frontier model | 3-10× unnecessary cost | Model router |
| Silently swallowing failures | Same mistakes repeated | Kaizen ledger |
| State inside orchestrator | No crash recovery | Durable event log |
| Single-agent for complex tasks | Vague recommendations | Multi-agent with specialists |
