# On-Policy Distillation & Self-Generated Trajectories (2025-2026)

**Date:** 2026-07-12
**Context:** Research pass restricted to papers from January 2025+. The field has radically shifted from 2022-2024 methods (STaR, SPIN, GKD) to on-policy distillation as the dominant paradigm.

---

## Paradigm Shift: OPD > Off-Policy SFT

Thinking Machines Lab (Oct 2025, `github.com/thinking-machines-lab/tinker-cookbook`):
- Student generates on-policy trajectories → frozen teacher gives **token-level supervision** on them
- Reverse KL as loss function
- **~10x more efficient than RL** (1,800 GPU-h vs 17,920 GPU-h for equivalent quality)
- Off-policy SFT stuck at 60% even after 400K samples; OPD reached 74.4%
- Recommended hyperparams: JSD beta=0.5, on-policy mixing rate lambda=0.5

---

## Key Methods (2025-2026)

### GAD — Generative Adversarial Distillation (arXiv:2511.10643, Nov 2025)
GAN-like minimax: student = generator, discriminator distinguishes student vs teacher outputs. **Black-box: no teacher logits needed** — only text outputs via API. Ideal for GPT-4o/DeepSeek V4 distillation.

### PACED (arXiv:2603.11178, Mar 2026)
Gradient signal-to-noise ratio is bell-shaped over student pass-rate — collapses on too-easy AND too-hard problems. PACED concentrates training on "zone of proximal development." Also introduces **Anti-Self-Distillation (AntiSD)**: ascending divergence (reversing per-token sign) to push away from suboptimal distributions — path to self-improvement beyond teacher ceiling.

### MOPD — Multi-Teacher On-Policy Distillation (arXiv:2606.30406, Jun 2026, NVIDIA/Xiaomi)
Per-domain specialized teachers → one student via on-policy rollouts. NVIDIA Nemotron 3 Ultra used 2 iterations of MOPD with 10+ teachers (550B MoE). Directly applicable: GPT-4o (reasoning) + DeepSeek V4 (code) + GLM-5.2 (multilingual) → one student.

**Key innovation — policy-space integration (not weight-space):**
Mix-RL (weight-space) causes gradient conflicts between domains → compromised quality. MOPD integrates in policy space: student generates on-policy → per-domain teacher evaluates → unified DPO loss. No gradient conflicts, dense token-level signal, eliminates exposure bias.

**Per-domain routing:** Each prompt classified by domain → routed to specialist teacher:
```python
TEACHERS = {
    "math": "gpt-4o",       # math reasoning specialist
    "code": "deepseek-v4",  # code generation specialist
    "lang": "glm-5.2",      # multilingual specialist
}
```

**Results:**
| Method | AIME (math) | HumanEval (code) | Multi-domain avg | Forgetting |
|--------|:---:|:---:|:---:|:---:|
| Mix-RL | 42.1% | 78.3% | 60.2% | 12% |
| Off-policy SFT | 38.5% | 74.1% | 56.3% | 5% |
| **MOPD (2 iters)** | **51.3%** | **84.7%** | **68.1%** | **2%** |
| Oracle (best teacher per domain) | 55.0% | 88.0% | 71.5% | — |

MOPD reaches **95% of oracle quality** at 2 iterations. Cloud API models already specialized (no need to RL-train teachers). 2-3 iterations sufficient (self-improvement reversal risk beyond 3).

### MAD-OPD (arXiv:2605.01347, May 2026)
Multi-Agent Debate: teacher = collective of models debating over student's on-policy state. Breaks single-teacher ceiling. Task-adaptive divergence: JSD for agentic, reverse KL for code.

### Self-Distilled RLVR (arXiv:2604.03128, Apr 2026)
Combines RLVR with on-policy self-distillation. One model = teacher + student. Teacher gets privileged info (correct answer) → token-level policy differences modulate RL update magnitude. RLVR gives direction, self-distillation gives amplitude. Avoids instability of pure self-distillation.

### UniSD (arXiv:2605.06597, May 2026)
Self-distillation **without ANY external teacher**. Three axes: supervision reliability (multi-teacher agreement), representation alignment, training stability. 6 benchmarks x 6 models x 3 families.

### Self-Distilled Reasoner / OPSD (arXiv:2601.18734, Jan 2026)
**Directly tested on Qwen3-1.7B, Qwen3-4B, Qwen3-8B.** Single model as both teacher and student. Teacher receives ground-truth privileged context (correct answer) to provide token-level supervision via reverse KL. OpenThoughts dataset (up to 30K problem-solution pairs with CoT).

### Weak-to-Strong Transfer / Direct-OPD (arXiv:2607.05394, Jul 2026, Tsinghua+ByteDance)
**Practical recipe for DGX Spark:** Run RL on Qwen3-4B (fits 128GB easily) → transfer policy shift to Qwen3-35B via OPD. RL is more sample-efficient on smaller models; OPD transfers the learned policy. ~10x cheaper than direct RL on 35B.

**GitHub:** `BytedTsinghua-SIA/Direct-OPD`

**Key innovation — transfers policy SHIFT, not final policy:**
Direct-OPD transfers δ = log π_RL − log π_ref (the direction the teacher moved during RL), not π_RL itself. Student applies this shift starting from its own (higher) knowledge base. Student doesn't copy weak teacher's answers — it copies the *direction of improvement*.

**Results (R1-Distill-1.5B → R1-Distill-7B):**
| Metric | Base 1.5B | After RL on 1.5B | Direct-OPD on 7B | Direct RL on 7B |
|--------|:---:|:---:|:---:|:---:|
| AIME 2024 | 48.3% | 55.1% | **62.4%** | 63.1% |
| MATH-500 | 79.2% | 84.6% | 88.3% | 89.0% |
| GPU-hours | — | ~200 | +200 (OPD) | ~2,000 |

Direct-OPD reaches 98.9% of direct-RL quality at **10× fewer GPU-hours** (400 vs 2000). Multiple RL-discovered policy shifts can be applied sequentially to same student.

**DGX Spark implementation:** RL on Qwen3-4B (~44 GB, 1-2 days) → Direct-OPD on Qwen3.5-35B with LoRA (~74 GB, 2-3 days). Total ~3 days, fits 128GB comfortably.

### Nemotron-Cascade 2 (arXiv:2603.19220, Mar 2026)
NVIDIA production pipeline: cascade RL (domain-by-domain) + OPD between domains to prevent forgetting. After each RL domain, best checkpoint = teacher for OPD. **Gold medal IMO and IOI 2025.**

---

## Self-Play Without External Data (2025-2026)

### Absolute Zero Reasoner (arXiv:2505.03335, NeurIPS 2025)
Zero training data. One LLM as proposer (generates tasks) + solver (solves them). Python executor validates both. SOTA on math/coding with ZERO external data.

### SPIRAL (arXiv:2506.24119, ICLR 2026)
**Tested on Qwen3-4B!** Self-play on zero-sum games (Tic-Tac-Toe, Kuhn Poker, Simple Negotiation). Model plays against continuously improving versions of itself → automatic curriculum. Multi-turn RL (GRPO), win/loss/draw = verifiable reward.

**GitHub:** `spiral-rl/spiral` — run with `bash cmd/tinker/run_tinker_qwen3_4b.sh`

**Game-by-game results (Qwen3-4B):**
| Game | GSM8K (math) | General Reasoning |
|------|:---:|:---:|
| Kuhn Poker alone | +8.6% | +8.4% |
| Tic-Tac-Toe | +4.2% | +3.1% |
| Simple Negotiation | +3.8% | +5.2% |
| All three together | +12.1% | +11.3% |

Beats SFT on 25K expert trajectories. Even works on already-strong models: +2.0% avg on DeepSeek-R1-Distill-Qwen-7B. Skills transfer from games to academic benchmarks (probabilistic reasoning from poker → math word problems). Zero external data, zero annotation. Cap at 2-3 self-play iterations (self-improvement reversal risk).

### SPC — Self-Play Critic (arXiv:2504.19162, NeurIPS 2025)
Two copies: "Sneaky Generator" injects errors, Critic learns to catch them. Adversarial self-play → step-level assessment without manual annotation.

### PSV (arXiv:2512.18160, Dec 2025)
Self-play for code synthesis via **formal verification** (not unit tests). Sound, non-exploitable training signal.

---

## R1-Style RL with Self-Generated Reasoning

### DeepSeek-R1 (arXiv:2501.12948, Jan 2025, Nature)
GRPO (Group Relative Policy Optimization): sample G answers per question, advantage = normalized reward in group. No value/critic network. Rule-based rewards (test pass/fail) — no learned reward model. R1-Zero: pure RL without SFT → emergent reasoning. R1: multi-stage (cold-start SFT → RL → SFT on RL outputs → RL).

### Kimi K1.5 (arXiv:2501.12599, Jan 2025)
RL with RLVR, 128K context for longer reasoning chains. Simple framework without MCTS/value functions/process reward models. Matches OpenAI o1 on AIME (77.5) and MATH-500 (96.2).

---

## Risks

### Self-Improvement Reversal (arXiv:2407.05013)
Iterative self-improvement can produce "reversal": benchmarks improve but solution diversity degrades and OOD generalization worsens. Mitigation: cap at 2-3 iterations, monitor diversity, mix in teacher/original data.

### Reward Hacking in Self-Training (arXiv:2505.21444, May 2025)
Self-consistency signals work but model can exploit them instead of genuinely improving. Mitigation: mix external data, monitor diversity.

---

## Updated Pipeline (2025-2026 Paradigm)

```
Phase 1: Off-policy SFT (bootstrap, 80% of value)
  Cloud teacher → 10-50K examples → SFT with LoRA, low LR
  + Low-Perplexity Token Masking + Entropy-Adaptive Gating

Phase 2: On-Policy Distillation (key innovation)
  Student generates trajectories → teacher gives token-level feedback
  GAD for black-box API teachers, JSD beta=0.5, lambda=0.5
  PACED curriculum: focus on zone of proximal development
  MOPD for multi-teacher integration

Phase 3: GRPO RL with execution rewards (for code)
  Rule-based rewards (test pass/fail), no reward model needed
  + CodeRL+ execution semantics, P-GRPO anti-hacking

Phase 4: Multi-turn agentic RL
  MURPHY: generate → run → fix → repeat, retrospective credit

Phase 5: Anti-forgetting merge + deploy
  DES-MoE for MoE models, DARE-TIES merge, SDFT for continual learning
```

### Weak-to-Strong Shortcut
RL on Qwen3-4B (cheap) → OPD transfer to Qwen3-35B (avoids expensive RL on large model).
