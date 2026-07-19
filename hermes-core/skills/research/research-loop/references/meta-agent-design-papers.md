# Meta-Agent Design Papers: ADAS & AFlow (ICLR 2025)

Two cornerstone papers on automated agent design — essential background for any
plan2 orchestrator improvement or agent architecture research.

---

## ADAS — Automated Design of Agentic Systems

**Authors:** Shengran Hu, Cong Lu, Jeff Clune (UBC / Vector Institute / CIFAR AI Chair)
**Venue:** ICLR 2025 (🏆 Outstanding Paper, NeurIPS 2024 Open-World Agent Workshop)
**arXiv:** 2408.08435 | **Code:** github.com/ShengranHu/ADAS (1.6k★, Apache 2.0)

### Core Idea
Meta-agent **writes Python code** for new agents, tests them, and iteratively improves.
Search space is Turing-complete (code, not prompts), so theoretically any agent can be discovered.

### Algorithm: Meta Agent Search (evolutionary)
```
ARCHIVE = []
for iteration in 1..N:
    new_agent_code = META_AGENT.program(archive=ARCHIVE, task=benchmark)
    score = evaluate(new_agent_code, holdout_tasks)
    ARCHIVE.append({code, score, novelty})
    # LLM sees full archive as context for next iteration
```

### Six Operator Families (taxonomy from paper)
| # | Family | Examples | Mechanism |
|---|--------|---------|-----------|
| 1 | LLM-as-optimizer | OPRO (DeepMind) | Generate → evaluate → analyze errors → improve |
| 2 | Textual gradients | ProTeGi, TextGrad, Trace | Gradient descent in text space |
| 3 | Evolutionary + archive | EvoPrompt, Promptbreeder, **ADAS** | Population + mutation + selection |
| 4 | Symbolic learning | Agent Symbolic Learning | Agent writes Python for self-improvement |
| 5 | MCTS-based | AFlow, ReST-MCTS* | Tree search over workflow DAGs |
| 6 | Score-based | ScoreFlow | DPO-like optimization on preference pairs |

### Key Results
- Auto-discovered agents **outperform hand-crafted SOTA** on ARC, DROP, MGSM, MMLU, GPQA
- Agents show **cross-model transfer**: trained on GPT-4o, outperform hand-crafted on Claude
- Agents show **cross-domain transfer**: coding agents work on math tasks
- Novel patterns discovered that no human designed: multi-expert cross-critique, human-like feedback simulation, decomposition-integration loops

### Limitation
Linear archive search (flat list) — loses context as archive grows. MCTS-based AFlow solves this.

---

## AFlow — Automating Agentic Workflow Generation

**Authors:** Jiayi Zhang, Jinyu Xiang, Mingchen Zhuge et al. (DeepWisdom / MetaGPT team, 14 authors)
**Venue:** ICLR 2025 **Oral** (top ~1.5% of accepted papers)
**arXiv:** 2410.10762 | **Code:** github.com/FoundationAgents/AFlow (544★, MIT)

### Core Idea
Reformulates workflow optimization as **MCTS search over code-represented workflows**.
Uses predefined Operators (Generate, Format, Review&Revise, Ensemble, Test, Programmer)
as building blocks — faster search than ADAS's from-scratch coding.

### Architecture: 4-Layer Stack
```
NODE       → atomic LLM call (model, prompt, temp, format)
OPERATOR   → reusable pattern of Nodes (Generate, Ensemble, Review&Revise...)
EDGE       → Python code connecting Nodes (conditions, loops, parallel)
WORKFLOW   → complete DAG = MCTS tree node
```

### MCTS Algorithm (4-phase cycle)
```
1. SELECTION    — Soft Mixed Probability: P = λ·uniform + (1-λ)·softmax(score)
                  λ=0.2 ensures exploration; W₀ (empty template) always selectable
2. EXPANSION    — LLM optimizer (Claude-3.5-sonnet) generates new workflow variant
                  Uses parent's experience: past modifications + success/failure logs
3. EVALUATION   — 5 runs on validation set (20% holdout); mean ± std
                  More expensive per iteration, but accurate signal → fewer total iterations
4. BACKPROP     — Records (score, modification, improvement) in tree node
                  When node revisited → exact experience reuse, no context loss
```

### Key Innovation: Tree-Structured Experience
ADAS's flat list loses context as it grows. AFlow's MCTS tree binds experience to
specific workflow nodes — when revisited, past success/failure is precisely recalled.

### Operators (predefined building blocks)
| Operator | Pattern | Source |
|----------|---------|--------|
| Generate | Simple LLM call | Baseline |
| Format | Structured output (XML/JSON) | — |
| Review&Revise | Critique → fix loop | Self-Refine (Madaan et al.) |
| Ensemble | Multiple answers → vote | Self-Consistency CoT (Wang et al.) |
| Test | Execute code on tests | Zhong et al. |
| Programmer | Generate + execute code | — |
| Custom | Free-form Node construction | Fallback |

### Results (GPT-4o-mini executor)
| Benchmark | Best Hand-Crafted | ADAS | **AFlow** | Δ over Hand-Crafted |
|-----------|:-:|:-:|:-:|:-:|
| HumanEval | 73.6 | 73.6 | **88.6** | +20% |
| MBPP | 69.2 | 68.1 | **78.0** | +13% |
| GSM8K | 91.6 | 89.3 | **94.7** | +3% |
| MATH lv5 | 56.2 | 35.4 | **73.6** | +31% |
| HotpotQA | 50.4 | 53.4 | **67.9** | +35% |
| DROP | 73.6 | 73.6 | **78.8** | +7% |
| **Average** | 69.1 | 65.6 | **80.3** | **+16%** |

Stunning: **GPT-4o-mini + AFlow > GPT-4o without AFlow** at **4.55% cost**.

---

## ADAS vs AFlow — Comparison

| Dimension | ADAS | AFlow |
|-----------|------|-------|
| Search algorithm | Evolutionary (flat archive) | MCTS (tree-structured) |
| What is searched | Complete agent code | Workflow from Operators + code edges |
| Search space | Turing-complete (agents in Python) | Code-represented workflows |
| Experience storage | Linear list (context loss at scale) | Tree nodes (precise recall on revisit) |
| Building blocks | FM_Module, Info primitives | Operators (Generate, Ensemble, ...) |
| Exploration guarantee | Mutation randomness | Soft Mixed Probability (λ=0.2 uniform) |
| Efficiency | Low (linear heuristic) | High (Operators reduce space, MCTS directs search) |
| MATH lv5 result | 35.4 | **73.6** (×2.1) |
| ICLR status | Accept | **Oral** |
| Novelty | Invents NEW agents from scratch | Optimizes workflows from known blocks |
| Transfer | Excellent (cross-model, cross-domain) | Not systematically tested |

---

## Application to Hermes plan2

### Level 1: Replace fixed pipeline with AFlow-like search
Current plan2: rigid `requirements → analysis → research → architecture → ...`
Proposed: define plan2 phases as Operators, run MCTS to find optimal sequence per project type.

### Level 2: ADAS for inventing new subagents
Run Meta Agent Search on historical Hermes projects to discover novel agent architectures
that outperform hand-designed researcher/architect/techlead agents.

### Level 3: Experience backpropagation in Neo4j
Store (project_type, workflow, score, modifications) in Neo4j. When new project matches
past type → retrieve optimal workflow from tree-structured experience.

### Level 4: Soft Mixed Probability for phase ordering
Instead of fixed phase order: `P(next_phase) = 0.2·uniform + 0.8·softmax(historical_success)`.
Allows plan2 to learn: "for Android projects, start with research, not requirements."

### Concrete 5-step adoption plan
| # | What | Complexity | Impact |
|---|------|-----------|--------|
| 1 | Define plan2 Operators (research, architect, review, ensemble...) | Low | Structure |
| 2 | MCTS selection for phase ordering | Medium | Adaptive pipeline |
| 3 | Experience backprop in Neo4j (project → workflow → score) | Medium | Cross-project memory |
| 4 | AFlow-search on historical projects → optimal workflow per type | High | Auto-improvement |
| 5 | ADAS-like meta-search for new subagent architectures | High | Agent evolution |

---

## Key Insight

> ADAS proves agents can invent agents better than humans. AFlow proves MCTS beats
> evolutionary search for workflow optimization (×2.1 on MATH). Together: **fixed
> pipelines must be replaced by search-based orchestration with tree-structured
> experience**. The ceiling of hand-designed plan2 is lower than what automated
> search can discover.
