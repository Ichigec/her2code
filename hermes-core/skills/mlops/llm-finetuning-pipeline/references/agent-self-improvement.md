# Agent-Model Co-Evolution: Self-Improving Agents & Training Data from Codebases

**Date:** 2026-07-13
**Context:** Research on how to fine-tune a model to understand a local agent's codebase while the agent simultaneously improves its own code — mutual improvement loop.

---

## 1. Self-Improving Coding Agents (Code-Level, No GPU)

### SICA — Self-Improving Coding Agent (arXiv:2504.15228, ICLR 2025)
- **Core loop:** Agent runs on benchmark tasks → analyzes execution traces → edits its own source code → re-evaluates → keeps improvements, reverts regressions
- **Key innovation:** Eliminates distinction between meta-agent and target agent. The agent IS its own improver.
- **Results:** SWE-bench Verified 17%→53%. Additional gains on LiveCodeBench.
- **Code:** github.com/MaximeRobeyns/self_improving_coding_agent
- **No GPU needed** — uses LLM API calls for self-modification

### Gödel Agent (arXiv:2410.04444, ACL 2025)
- **Core loop:** Agent reads its own Python code (including modification logic) → LLM proposes modifications → monkey-patch at runtime → test → keep/revert
- **Key innovation:** Self-referential — can modify its own modification logic (true recursive self-improvement, inspired by Schmidhuber's Gödel Machine)
- **Results:** Outperforms manually crafted agents on DROP, MGSM, MMLU, GPQA
- **Code:** github.com/Arvid-pku/Godel_Agent

### HGM — Huxley-Gödel Machine (arXiv:2510.21614)
- **Core loop:** Grows a tree of self-modifications. Uses Clade-level Modified Productivity (CMP) + Thompson Sampling to decide which branches to expand
- **Key innovation:** "Metaproductivity" — agent improves at improving itself. Measures and optimizes the improvement process itself.
- **Results:** Outperforms SICA on SWE-bench Verified and Polyglot. Strong transfer to other datasets and LLMs.
- **Code:** github.com/metauto-ai/HGM

### Live-SWE-Agent (arXiv:2511.13646)
- **Core loop:** Software engineering agents self-evolve strategies DURING active task solving — online, not offline
- **Results:** 75.4% SWE-bench Verified, 45.8% SWE-Bench Pro

### AlphaEvolve (arXiv:2506.13131, Google DeepMind)
- **Core loop:** Evolutionary computation + LLM code generation. LLMs propose code changes → programmatic evaluator scores → evolutionary procedure maintains population
- **Results (production-deployed):** 0.7% of global Google compute recovered, 23% Gemini kernel speedup, 32.5% FlashAttention speedup
- **Code:** github.com/google-deepmind/alphaevolve_results

---

## 2. Model-Level Self-Improvement Methods

### ReST-EM — Reinforced Self-Training (arXiv:2312.06585, Google DeepMind)
- **Loop:** Generate K solutions → filter correct (reward filtering) → SFT on filtered → repeat
- **Key insight:** Growing-batch RL. Training on self-generated correct solutions surpasses training on human data.
- **Application:** Foundation for our RL phase — generate code solutions, filter by test pass, fine-tune.

### STaR — Self-Taught Reasoner (arXiv:2203.14465, Stanford)
- **Loop:** Generate rationale → check answer → if correct, add to SFT set → if wrong, provide hint, re-generate → fine-tune → repeat
- **Extension START (arXiv:2503.04625):** STaR + tool integration (code execution for self-checking)

### Self-Rewarding LM (Meta/NYU, 2024)
- **Loop:** LLM generates responses → same LLM evaluates (LLM-as-Judge, 5-point scoring) → preference pairs → iterative DPO
- **Key insight:** Eliminates separate reward model. Generator and judge co-improve.

### RAGEN/StarPO (arXiv:2504.20073)
- **Loop:** Multi-turn trajectory-level RL with structured rollouts. Variance filtering, redundancy reduction, KL constraint relaxation.
- **Key insight:** First systematic study of multi-turn agent RL training.

---

## 3. Hermes Agent Self-Evolution (ICLR 2026 Oral)

- **Repo:** github.com/NousResearch/hermes-agent-self-evolution
- **Method:** DSPy + GEPA (Genetic-Pareto Prompt Evolution)
- **What it does:** Agent reads execution traces, understands WHY tasks failed, evolves skills + tool descriptions + system prompts + agent code
- **No GPU needed** — optimization through API calls only
- **Already exists for Hermes Agent** — can be used directly

---

## 4. Training Data from Hermes state.db

The Hermes session database contains real code-editing trajectories — no synthetic generation needed.

### Statistics (as of 2026-07-13)
```
state.db: 703MB, 669 sessions, 31,934 messages
  ├── 503 patch operations (code edits with old/new strings)
  ├── 402 write_file operations (file creation)
  ├── 5,822 terminal commands (with exit codes = reward signal)
  ├── 1,803 read_file operations (context for edits)
  └── 60 sessions classified as "bug_fix_with_debugging" (most valuable for training)
```

### Extraction
Use `scripts/trajectory_extractor.py` to extract structured trajectories. Each trajectory contains:
- User request (the task)
- Assistant reasoning (why each action was taken)
- Tool calls (patch, terminal, read_file) with arguments
- Tool results (success/failure, output)
- Code changes (old_string → new_string per patch)
- Trajectory type classification

### Conversion to Training Format
After extraction, trajectories can be converted to:
1. **SFT pairs:** (task description, successful solution) from successful trajectories
2. **Preference pairs:** (successful fix, failed attempt) for DPO
3. **RL reward:** terminal exit_code=0 = success, exit_code≠0 = failure
4. **Code changes:** (old_code, new_code) pairs for learning editing patterns

---

## 5. SWE-smith: Generate Training Data from Any Codebase

SWE-smith (arXiv:2504.21798, NeurIPS 2025) — end-to-end toolkit for generating SWE training data from any GitHub repository.

- **Repo:** github.com/SWE-bench/SWE-smith
- **What it does:** Takes any repo URL → generates task instances (bug localization, program repair, feature implementation) → runs agent → collects trajectories → fine-tunes
- **Results:** 50K instances from 128 repos. SWE-agent-LM-32B: 40.2% SWE-bench Verified.
- **Can target the agent's own codebase** — generate training data from Hermes Agent source code

---

## 6. SWE-RL: RL on Code Improves General Capabilities

SWE-RL (arXiv:2502.18449, Meta, NeurIPS 2025) — critical finding:

> RL on software engineering data not only preserves but **IMPROVES** general capabilities — math, reasoning, and language understanding all improved.

This means:
- RL phase on agent code is NOT a forgetting risk
- RL on code can actually BOOST general quality
- Argument for using GRPO (not just SFT) in the co-evolution loop

---

## 7. Ready-Made Training Pipelines

### Recommended Stack for DGX Spark + Qwen3.5-35B-A3B

| Component | Tool | Why |
|-----------|------|-----|
| **Data generation** | SWE-smith | Turns any repo into SWE training gym (NeurIPS 2025) |
| **Agent self-improvement** | SICA approach + GEPA | Agent edits own code, no GPU needed (ICLR 2025 + ICLR 2026) |
| **SFT training** | Unsloth QLoRA | 17.5GB VRAM, 12× faster MoE, router frozen by default |
| **RL training** | Unsloth GRPO | Single GPU, vLLM colocate mode |
| **Evaluation** | SWE-bench Verified + HumanEval + MATH | General + specific benchmarks |

### What Does NOT Work on Single GPU (128GB)
- **DeepSWE/rLLM:** Required 64× H100 GPUs. Framework is general-purpose but reference setup is multi-GPU only.
- **verl with large MoE:** Designed for multi-GPU/Megatron. Not optimized for single GPU.
- **Full fine-tuning (not LoRA) of 35B MoE:** Would need ~280GB+ VRAM. QLoRA is necessary.

---

## 8. Co-Evolution Loop Design

```
Phase A (3 days, No GPU): Agent Self-Improvement
  ├── SICA loop: agent runs on SWE-smith tasks from its own code
  ├── GEPA: evolve prompts, skills, tool descriptions
  ├── Collect training data (successful trajectories)
  └── Output: improved agent code (v2) + 2000-5000 trajectories

Phase B (5-7 days, DGX Spark): Model Fine-Tuning
  ├── SFT with SDFT (Unsloth QLoRA, rank=128)
  │   ├── Data mix: 70% agent + 20% general code + 10% general instruction
  │   ├── SDFT: EMA-teacher, near-zero forgetting
  │   └── Synergistic Regularization (30 lines)
  ├── RL with GRPO + RO-GRPO (200-500 steps)
  │   ├── ReST-EM: generate → filter → train
  │   ├── RO-GRPO: routing entropy + load_var → reward
  │   └── Mistake Book: replay every 100 steps
  └── Evaluate: general (no regression >3%) + agent tasks (+10%)

Phase C (1 day): Integration
  ├── Deploy fine-tuned model as agent backbone
  └── Measure: agent v2 + fine-tuned > agent v1 + original
```

Each cycle: agent code improves + model gets smarter → synergy. Subsequent cycles add LoRI, Merge before Forget, TCOD, Anchored Self-Play for progressive refinement.

---

## 9. Anti-Forgetting for Co-Evolution

### Minimal Stack (~135 lines of code)

1. **SDFT** (self-distillation) — near-zero forgetting, TESTED ON OUR MODEL (Qwen3.5-35B-A3B + LoRA 64, Tinker platform)
2. **Data mixing** — 70% agent + 20% general code + 10% general instruction
3. **Mask the Target** — 5 lines, KL on non-target vocabulary
4. **Synergistic Regularization** — 30 lines, expert specialization
5. **RO-GRPO** — 50 lines, routing entropy + load_var → reward
6. **Frozen Router** — 0 lines (Unsloth default for MoE)
7. **Mistake Book** — 20 lines, experience replay

### Advanced Stack (iterations 2+)

8. **LoRI** — freeze A, sparsify B (COLM 2025)
9. **Merge before Forget** — single LoRA pair, merge after each cycle (ICLR 2026)
10. **TCOD** — progressive trajectory depth (1-2 → 3-4 → 5-7 → 10+ steps)
11. **O-LoRA** — orthogonal subspace, new updates ⊥ previous
12. **Anchored Self-Play** — reference bugs from previous iterations

---

## 10. Key Surveys

- **Survey of Self-Evolving Agents** (arXiv:2507.21046): What/When/How/Where to evolve. Model-agent co-evolution as key mechanism.
- **Comprehensive Survey of Self-Evolving AI Agents** (arXiv:2508.07407): MOP → MOA → MAO → MASE taxonomy. 128+ citations.
- **Recursive Self-Improvement in AI** (arXiv:2607.07663): Bounded self-refinement (convergent, practical) vs open-ended RSI (divergent, bounded by grounding/collapse/compute). Survey of 1,250+ papers.
