---
name: llm-finetuning-pipeline
description: "Train, fine-tune, or distill LLMs locally on DGX Spark (GB10/Blackwell). Method selection (Full FT / LoRA / QLoRA / distillation), student model selection, framework comparison (Unsloth / LLaMA-Factory / TRL / NeMo), Docker setup for aarch64+CUDA 13, memory budgeting, and deploy pipeline (BF16 → GGUF/APEX → llama.cpp/vLLM)."
version: 1.0.0
author: Pavel's Hermes
metadata:
  hermes:
    tags: [fine-tuning, distillation, LoRA, QLoRA, DGX-Spark, Unsloth, TRL, NeMo, training, student-model, knowledge-distillation]
---

# LLM Fine-tuning / Distillation Pipeline

Train, fine-tune, or distill LLMs locally on DGX Spark (128 GB unified memory, GB10 Grace Blackwell). Covers method selection, student model selection, framework setup, and deployment of the trained model.

## Trigger

Use when Pavel asks about:
- **Training / дообучение** a local model («дообучить модель», «fine-tune», «дистилляция», «train student model»)
- **Distillation** — transferring knowledge from a teacher (cloud API or local large model) to a smaller student
- **Multi-teacher distillation** — distilling from multiple teachers simultaneously («multi-teacher», «несколько учителей», «ensemble distillation», «GAD», «G-OPD», «ExOPD», «reward extrapolation», «surpass teacher»)
- **Adversarial distillation** — student vs discriminator minimax game, role-swap distillation («adversarial distillation», «role-swap», «code-test co-evolution», «GAD discriminator»)
- **On-policy distillation / on-policy trajectories** — student generates its own trajectories for training («траектории модели», «on-policy», «self-distillation», «self-play»)
- **RL for code / GRPO / RLVR** — training with execution rewards, DeepSeek-R1 style («GRPO», «RL with code», «execution feedback», «SWE-bench training»)
- **Diffusion model RL training** — DiffusionGemma, diffusion LLM fine-tuning, rldiffusion pipeline («diffusiongemma RL», «rldiffusion», «diffusion text model RL», «StableDRL», «diffu-GRPO», «GDPO»)
- **Catastrophic forgetting** — preventing knowledge loss during fine-tuning («забывание», «catastrophic forgetting», «forgetting prevention»)
- **MoE expert adaptation** — adding, growing, or selectively training individual experts («add expert», «expert upcycling», «ESFT», «train only new expert», «expert growing», «expand MoE»)
- **MoE routing stability** — router collapse, routing drift, train-inference routing mismatch, R3 routing replay, freeze router, RO-GRPO, EPnG, expert addition safety («routing collapse», «router freeze», «router LoRA», «routing drift», «MoE RL stability», «R3 routing replay», «RO-GRPO», «add expert safely», «expert collapse»)
- **LoRA / QLoRA / Full FT** — choosing between parameter-efficient and full fine-tuning
- **Student model selection** — which base model to train on DGX Spark
- **Framework comparison** — Unsloth vs LLaMA-Factory vs TRL vs NeMo for DGX Spark
- **Training throughput estimates** — how long will training take on DGX Spark
- **KD-logit** — knowledge distillation at the logit level (teacher + student co-resident)

## DGX Spark as a Training Platform

### Hardware for Training

| Parameter | Value | Training Implication |
|---|---|---|
| Chip | GB10 Grace Blackwell Superchip | CPU+GPU unified, no PCIe bottleneck |
| GPU arch | sm_121 (Blackwell) | Triton kernels need sm_121 patches; flash-attn needs source build |
| Platform | aarch64 (ARM64) | x86 binaries fail; need native wheels or Docker |
| CUDA | 13.x | Source-build Triton required (specific commit) |
| Unified Memory | 128 GB LPDDR5x, 273 GB/s | Teacher + Student co-resident for KD-logit |
| FP4 | NVFP4 hardware | 4-bit float training possible (experimental) |
| NVLink-C2C | 200 Gb/s CPU↔GPU | Near-zero latency data loading |

### Proven Throughput (measured, not estimated)

From `albond/DGX_Spark_Unsloth_Lossless_Speedup` (July 2026) — optimized Unsloth with sm_121a kernels and flash-linear-attendance for GatedDeltaNet/SSM layers:

| Model | BF16 Weights | LoRA tok/s | Full FT? | Full FT tok/s |
|---|---:|---:|:---:|---:|
| Qwen3.5-0.8B | 1.8 GB | 5,650 | ✅ | ~5,000 |
| Qwen3.5-2B | 4.4 GB | 3,461 | ✅ | 3,173 |
| **Qwen3.5-4B** | **9.0 GB** | **1,712** | **✅** | **~1,600** |
| Qwen3.5-9B | 18.0 GB | 1,095 | ❌ | — |
| Qwen3.5-27B | 54.0 GB | 370 | ❌ | — |

Speedup vs stock Unsloth: **7.67× LoRA, 8.35× Full FT** — achieving wall-clock parity with rented H100 at $0 cost. Full benchmark details in `references/dgx-spark-training-benchmarks.md`.

### Wall-clock Training Time

| Dataset × Epochs | Mode | Stock Unsloth | Optimized (albond) | H100 Rental Equivalent |
|---|---|---:|---:|---:|
| 25K × 3 ep (LoRA r=128) | LoRA | ~5 days | **~20 h** | $50–60 |
| 100K × 3 ep (LoRA) | LoRA | ~20 days | ~3 days | $200–250 |
| 100K × 3 ep | Full FT | ~25 days | ~3 days | $200–300 |

Break-even: $4,699 hardware ÷ $2.49/h H100 = **79 days of continuous training**.

## Method Selection Matrix

| Method | Bytes/param | 35B Memory | Fits 128GB? | Quality | When to Choose |
|---|---:|---:|:---:|:---:|---|
| **Standard AdamW** (mixed precision) | 12 | 420 GB | ❌ | 🥇 | Models ≤8B only |
| **8-bit Adam** (bitsandbytes) | 6 | 196 GB | ❌ | 🥇 | ≤15B; needs sm_121 bitsandbytes build |
| **Adafactor** | 4-4.5 | 147 GB | ❌ | 🥈 | ≤22B; no momentum may hurt FT quality |
| **🔥 BAdam** (block-wise Adam) | ~2.4 | **84 GB** | **✅** | 🥇 | **35B Full FT — ONLY method that fits** |
| **LoRA** (BF16 base, frozen) | ~2.1 | 74 GB | ✅ | 🥈 ~98% | Up to 50B; fast iteration; mergeable |
| **QLoRA** (4-bit base + LoRA) | ~0.6 | 20 GB | ✅ | 🥉 ~95% | 35B-100B+; maximum model size |
| **Response Distillation (SFT)** | — | — | ✅ | 🥈 | Cloud teacher → student; best ROI (Phase 1 bootstrap) |
| **On-Policy Distillation (OPD)** | — | ~98 GB | ✅ | 🥇 | Student generates trajectories, teacher gives token-level feedback; **10× cheaper than RL** (2025+ paradigm) |
| **GAD (Adversarial Distillation)** | — | ~98 GB | ✅ | 🥇 | Black-box API teachers — discriminator distinguishes student from teacher (Microsoft, arXiv:2511.10643) |
| **G-OPD / ExOPD** | — | ~98 GB | ✅ | 🥇+ | λ>1 reward extrapolation — student **surpasses** teacher (arXiv:2602.12125, white-box only) |
| **Self-Distillation (OPSD)** | — | varies | ✅ | 🥈 | Single model = teacher + student; no external teacher needed (arXiv:2601.18734) |
| **Logit Distillation (KD-logit)** | — | ~98 GB | ✅ | 🥇 reasoning | Local teacher + student co-resident |
| **On-policy (GKD)** | — | — | ✅ | 🥈 alignment | Student generates, teacher corrects |

### Maximum Unquantized (BF16) Model Size on DGX Spark 128GB

| Training Method | Max BF16 Model | Key Constraint |
|---|---|---|
| Standard AdamW Full FT | ~8B | 12 bytes/param × 8B = 96GB + activations |
| 8-bit Adam Full FT | ~15B | 6 bytes/param, but bitsandbytes sm_121 risk |
| Adafactor Full FT | ~22B | 4.5 bytes/param, borderline |
| **BAdam Full FT (block-wise)** | **~45B** | 2.4 bytes/param; 84GB for 35B ✅ |
| LoRA (BF16 base) | ~50B | 2.1 bytes/param; base frozen |
| QLoRA (4-bit base) | ~100B+ | 0.6 bytes/param |

### BAdam — Full Fine-Tuning of 35B on DGX Spark

**BAdam** (arXiv:2404.02827, NeurIPS 2024) is the ONLY method that allows Full FT of 35B MoE in 128GB. It processes optimizer blocks one at a time (layer-level), keeping only the active block's gradients/states in memory.

- **Memory**: `2M + 16M/D` GB (M=params in B, D=num blocks). For 35B/40 layers: 70 + 14 = **84 GB** ✅
- **Compatibility**: Pure PyTorch, NO custom CUDA kernels → **best sm_121/aarch64 compatibility** (ironically better than QLoRA which needs bitsandbytes)
- **Speed**: ~40× slower than standard AdamW (40 forward/backward passes per step). 25K×3ep ≈ 5-8 days for 35B.
- **MoE**: Layer-level blocks work for any architecture (architecture-agnostic)
- **Risk**: Not tested on MoE in the original paper, but layer-level partitioning is architecture-agnostic

```python
from badam import BlockOptimizer
# Qwen3.5 weights are under model.language_model.layers.* (multimodal!)
block_prefixes = [f"model.language_model.layers.{i}." for i in range(40)]
optimizer = BlockOptimizer(
    base_optimizer=torch.optim.AdamW(...),
    model=model,
    block_prefix_list=block_prefixes,
    switch_block_every=50,
    switch_mode="random",
    num_kept_backward=3,
)
```

Full method comparison (BAdam vs GaLore vs LOMO vs Adafactor) in `references/memory-efficient-training-methods.md`.

### Recommended Hybrid Pipeline

**2025-2026 paradigm (see `references/on-policy-distillation-2025.md` for full research):**

**Phase 1 (Bootstrap): Off-policy SFT — cloud teacher generates 10-50K examples → filtered → SFT with LoRA, low LR (1e-5). 80% of value. ~20h.
Phase 2 (Key innovation): On-Policy Distillation — student generates OWN trajectories → teacher gives token-level feedback (GAD for black-box API, JSD β=0.5, λ=0.5). ~10× cheaper than RL. ~10h, 2-3 iterations.
Phase 3 (Code): GRPO with execution rewards (test pass/fail, no reward model). + CodeRL+ execution semantics, P-GRPO anti-hacking.
Phase 4 (Agentic): Multi-turn RL (MURPHY) — generate → run → fix → repeat. SWE-smith or Self-Play SWE-RL data.
Phase 5: Anti-forgetting merge (DES-MoE for MoE, DARE-TIES) → GGUF/APEX quantize → deploy**

**Weak-to-Strong shortcut (arXiv:2607.05394):** Run RL on Qwen3-4B (cheap, fits 128GB) → transfer policy shift to Qwen3-35B via OPD. Avoids expensive RL on 35B. ~10× cheaper. GitHub: `BytedTsinghua-SIA/Direct-OPD`. AIME: 48.3% → 55.1% (RL on 1.5B) → 62.4% (OPD on 7B) vs 63.1% (direct RL on 7B) at 10× fewer GPU-hours.

**Legacy pipeline (2022-2024, still valid but superseded):**
Response distillation → SFT → Optional KD-logit (local 27B teacher, both in unified memory) → Quantize → Deploy

**Eagle3 speculative decoding ordering**: If you plan to use Eagle3 for inference acceleration, train it as the **LAST step** before deployment, AFTER all SFT/distillation/abliteration/RL. Eagle3 trains on the student's hidden states — any weight change after Eagle3 training shifts the hidden state space and degrades acceptance (~55% after SFT+abliteration vs ~76% on base). Eagle3 and distillation are orthogonal (the cloud teacher is not involved in Eagle3 training). However, Eagle3 during RL is DANGEROUS — it can degrade the RL policy through distributional bias and misleading gradients (see `speculative-decoding` skill → "Eagle3 + RL Training: Critical Interactions"). Use n-gram/prompt-lookup for RL rollout speedup instead.

## Student Model Selection

### Top Candidates (July 2026)

| Model | Params | BF16 | MMLU | HumanEval | GSM8K | Full FT? | Notes |
|---|---|---:|---:|---:|---:|:---:|---|
| **Qwen3-4B-Instruct-2507** | 4B | 9 GB | 72.0 | 82.0 | 87.2 | ✅ | 🥇 Best overall: native tool-calling, 119 languages, thinking mode |
| Qwen3-8B | 8B | 18 GB | 75.1 | 84.9 | 92.3 | ❌ LoRA | 🥈 Max quality, but Full FT doesn't fit comfortably |
| Qwen3-1.7B | 1.7B | 3.8 GB | 62.1 | 65.4 | 70.5 | ✅ | ⚡ Ultra-fast prototyping (~4h train) |
| Phi-4-mini | 3.8B | 8.5 GB | 72.0 | 78.0 | 84.3 | ✅ | Strong reasoning, MIT license |
| DS-R1-Distill-Qwen-7B | 7B | 15.6 GB | 74.4 | 80.5 | 85.2 | ❌ LoRA | Pre-trained on reasoning traces |
| Gemma-3-4B | 4B | 9 GB | 65.0 | 55.0 | 55.0 | ✅ | Weaker than Qwen3 at same size |

### Selection Rule

**Qwen3-4B-Instruct-2507 is the default student for DGX Spark.** Reasons:
1. Full FT fits: 9GB weights + 18GB grads + 9GB optimizer = ~36GB / 128GB ✅
2. Best small-model benchmark scores (distillabs #1 across 12 SLMs, 8 tasks)
3. Native function calling (critical for agent use cases)
4. Thinking mode toggle (`enable_thinking: false`) — avoids Hermes retry loop issues
5. Unsloth native support + proven throughput on DGX Spark
6. Apache 2.0 license
7. Well-trodden path: convert → GGUF/APEX → llama.cpp already verified on DGX Spark

**Exceptions:**
- Max quality needed → Qwen3-8B + LoRA (84.9% HumanEval)
- Ultra-fast prototype → Qwen3-1.7B (5,650 tok/s, ~4h train)
- Reasoning specialist → DeepSeek-R1-Distill-Qwen-7B

## Training 35B+ Models (Unquantized BF16)

### 35B MoE Student Candidates (all qwen35moe architecture, ~35B params, ~67 GB BF16)

| Model | Specialization | Key Benchmark | Full FT (BAdam) | LoRA (BF16) | QLoRA |
|---|---|---|:---:|:---:|:---:|:---:|
| **Qwen3.6-35B-A3B** 🆕 | Universal, coding, agentic | SWE-bench 73.4, MMLU-Pro ~86, GPQA ~85 | ✅ 84GB | ✅ 74GB | ✅ 20GB |
| **Agents-A1-35B** (abliterated) | Reasoning, science, agent | GAIA 96, IFBench 80.6 | ✅ 84GB | ✅ 74GB | ✅ 20GB |
| **Nex-N2-mini** (abliterated) | Coding, terminal, SWE | SWE-Bench 74.4, Terminal-Bench 60.7 | ✅ 84GB | ✅ 74GB | ✅ 20GB |
| **SuperQwen-AgentWorld** | World simulation, agentic | HumanEval+ 75 (+59 vs orig) | ✅ 84GB | ✅ 74GB | ✅ 20GB |
| **Qwen3.5-35B-A3B** (base) | Universal | MMLU 75, HumanEval 82 | ✅ 84GB | ✅ 74GB | ✅ 20GB |
| DS-R1-Distill-Qwen-32B | Reasoning (CoT) | AIME 72.6, MMLU 74.4 | ✅ 80GB | ✅ 70GB | ✅ 20GB |

### Training Method by Model Size (DGX Spark 128GB)

| Model Size | Full FT Method | LoRA (BF16) | QLoRA (4-bit) |
|---|---|---|---|
| ≤4B | Standard AdamW (44GB) | ✅ 14GB | ✅ trivial |
| 5-8B | 8-bit Adam or BAdam | ✅ ~20GB | ✅ ~10GB |
| 9-22B | BAdam only (Full FT) | ✅ ~40-50GB | ✅ ~15GB |
| **35B** | **BAdam only (84GB)** | **✅ 74GB** | **✅ 20GB** |
| 45-50B | ❌ doesn't fit | ✅ ~90GB (tight) | ✅ ~25GB |
| 70B+ | ❌ | ❌ | ✅ ~35GB |

### Distillation for 35B Students (Cloud Teacher → 35B)

35B MoE models CAN be students for distillation from cloud teachers (GPT-4o, GLM-5.2, DeepSeek V4). The 35B class sits in a sweet spot: large enough to absorb complex reasoning, small enough to train on DGX Spark.

**Three-phase pipeline:**

| Phase | Method | Time on DGX Spark | Quality Gain |
|---|---|---|---|
| **Phase 1: Response SFT** | Cloud teacher → 10-50K examples → QLoRA/LoRA on 35B | ~20h (QLoRA) / ~5-8 days (BAdam) | +15-30% on domain tasks (80% of value) |
| **Phase 2: Multi-teacher** | GPT-4o + GLM-5.2 + DeepSeek V4 → ensemble/best-of-N | +2-3 days | +5-10% over single-teacher |
| **Phase 3: On-policy GKD** | Student generates → Teacher evaluates → DPO train | +3-5 days | +2-5% on reasoning |

**GKD (Generalized Knowledge Distillation)** works with black-box API teachers — student generates outputs, teacher evaluates/corrects them, student learns from its own mistakes. ICLR 2024 Spotlight. Adds 2-5% on reasoning beyond standard SFT.

Expected quality gains for 35B student (Agents-A1 baseline):

| Domain | Baseline | After GPT-4o Distillation | Gain |
|---|---|---|---|
| Instruction Following | IFBench 80.6 | ~90-95% | +10-15% |
| Reasoning (GSM8K) | ~85% | ~90-93% | +5-8% |
| Domain-specific | Weak | Strong | +30-50% |
| General Knowledge (MMLU) | ~75% | ~80-83% | +5-8% |

Full distillation analysis in `references/distillation-35b-student.md`.

## On-Policy Distillation: The 2025-2026 Paradigm

The field has shifted from off-policy SFT (student trains on teacher-generated data) to **on-policy distillation (OPD)** — student generates its OWN trajectories, teacher provides token-level feedback on them. This solves exposure bias (train/inference distribution mismatch).

**Key methods (all 2025+, see `references/on-policy-distillation-2025.md`):**

| Method | arXiv | Date | Key Innovation |
|--------|-------|------|----------------|
| Thinking Machines OPD | (blog) | Oct 2025 | Reverse KL on student trajectories, **10× cheaper than RL** |
| GAD | 2511.10643 | Nov 2025 | **Black-box distillation** — no teacher logits needed, API text only |
| PACED | 2603.11178 | Mar 2026 | Focus on "zone of proximal development" + AntiSD (push away from errors) |
| MOPD | 2606.30406 | Jun 2026 | Multi-teacher OPD (NVIDIA Nemotron 3 Ultra, 10+ teachers) |
| Self-Distilled RLVR | 2604.03128 | Apr 2026 | RLVR + self-distillation, one model = teacher + student |
| Self-Distilled Reasoner | 2601.18734 | Jan 2026 | **Tested on Qwen3-4B** — OPSD with privileged context |
| Weak-to-Strong OPD | 2607.05394 | Jul 2026 | RL on 4B → OPD transfer to 35B, **10× cheaper than RL on 35B** |

- **Self-play without external data (reasoning):**
  - **Absolute Zero** (arXiv:2505.03335, NeurIPS 2025): Zero-data self-play, proposer + solver, Python executor validates
  - **SPIRAL** (arXiv:2506.24119, ICLR 2026): **Tested on Qwen3-4B** — self-play on zero-sum games → +8.6% math (Kuhn Poker alone), +12.1% all games. Key innovation: Role-Conditioned Advantage Estimation (RAE) — separate baselines per role to prevent the model from attributing advantage to the role rather than move quality. Kuhn Poker is most effective because probabilistic reasoning / EV calculation transfers directly to math word problems. Beats SFT on 25K expert trajectories. GitHub: `spiral-rl/spiral`, run: `cmd/tinker/run_tinker_qwen3_4b.sh`
  - **SPC** (arXiv:2504.19162, NeurIPS 2025): Adversarial self-play critic — Sneaky Generator injects errors, Critic catches them

- **Self-play for programming (adversarial code-test co-evolution, see `references/self-play-programming-2025.md`):**
  - **Code-A1** (arXiv:2603.15611, Mar 2026): **Best for max code quality.** Two separate models with opposing goals — Code LLM rewarded for passing tests, Test LLM rewarded for finding bugs. Solves self-collusion (single-model self-play lets model generate easy tests for its own code). Mistake Book mechanism replays historical failures to prevent catastrophic forgetting in adversarial training. Composite reward (validity + difficulty) creates automatic curriculum. +8.6% HumanEval on Qwen3-4B. GitHub: `ZJU-REAL/Code-A1`
  - **CURE** (NeurIPS 2025 Spotlight): One model co-evolves code + test generation. Interaction-based rewards — **no ground-truth code needed**. Enables training on new domains without labeled data.
  - **ATGen** (arXiv:2510.14635, ICLR 2026): Test Generator vs Adversarial Bug-Generator. Adversary crafts subtle bugs (off-by-one, race conditions), generator must catch them. Paradoxically improves code writing — model learns where bugs arise.
  - **SAGE** (arXiv:2603.15255, Mar 2026): Setter-Solver asymmetric game. Setter generates problems + predicts solvability, Solver attempts them. Calibration reward creates automatic curriculum at edge of Solver's ability.
  - **Sol-Ver** (arXiv:2502.14948, NeurIPS 2025): Baseline single-model solver-verifier self-play. Vulnerable to self-collusion (Code-A1 fixes this).

**R1-style RL (self-generated reasoning + verifiable rewards):**
- **DeepSeek-R1** (arXiv:2501.12948, Nature): GRPO, rule-based rewards (test pass/fail), no reward model
- **Kimi K1.5** (arXiv:2501.12599): RL with 128K context, simple framework without MCTS

**Risk: Self-improvement reversal** (arXiv:2407.05013) — cap at 2-3 iterations, monitor diversity, mix in teacher data.

## Anti-Forgetting Strategies (2025-2026)

See `references/catastrophic-forgetting-2025.md` for full research.

**Key paradigm shift: RL > SFT for forgetting prevention.** Three independent 2025 papers converge:
- RL's Razor (arXiv:2509.04259): RL mode-seeking → preserves prior knowledge
- SFT Memorizes, RL Generalizes (arXiv:2501.17161, ICML 2025): SFT memorizes → forgets
- RFT Naturally Mitigates Forgetting (arXiv:2507.05386): RL = natural anti-forgetting
- **RL heals OOD forgetting from SFT** (arXiv:2509.12235): SFT→RL pipeline is itself anti-forgetting

**For MoE models (Qwen3-35B): DES-MoE** (arXiv:2509.16882, EMNLP 2025) — dynamic expert specialization, **-89% forgetting** at 6 domains, 68% faster convergence.

**🔥 SDFT (Self-Distillation Fine-Tuning, arXiv:2601.19897, MIT) — TESTED ON OUR EXACT MODEL.** The Tinker platform validated SDFT on **Qwen3.5-35B-A3B + LoRA rank 64** in a continual learning experiment. Result: **near-zero forgetting** (SDFT preserves previous skills), while standard SFT shows **severe forgetting**. Mechanism: EMA-smoothed frozen teacher (α=0.999) generates on-policy targets via in-context learning → student learns from self-generated signals, not directly from demonstrations. Interpreted theoretically as inverse RL — naturally compatible with GRPO. Implementation: ~2.5× FLOPs (two forward passes), no architectural changes, no replay buffer, no Fisher matrix. **This is the #1 recommended anti-forgetting method for our setup.**

**SWE-RL emergent improvement (arXiv:2502.18449, Meta, NeurIPS 2025):** RL on software engineering data not only preserves but **IMPROVES** general capabilities — math, reasoning, and language understanding all improved. This means the RL phase on code is not a forgetting risk but a potential booster for general quality.

**PRISM insight (arXiv:2605.01061):** MoE routing does NOT isolate task-specific knowledge into disjoint experts as commonly assumed. Routing operates per-sample, while forgetting accumulates across the task sequence. **Cannot rely on MoE routing alone for forgetting protection** — need explicit per-expert subspace constraints (O-LoRA, DOC) or DES-MoE correlation isolation.

**MoE routers exacerbate forgetting vs dense models** (arXiv:2503.05029, TMLR 2025): Systematic study showing routing imbalance increases during domain-shifted fine-tuning. Must maintain load balancing loss and monitor routing patterns.

**Additional lightweight anti-forgetting methods (2025-2026):**
- **Mask the Target** (arXiv:2605.29498): 5-line KL regularizer on non-target vocabulary for LoRA. Zero overhead.
- **LoRI** (arXiv:2504.07448, COLM 2025): Freeze A matrix, sparsify B. Reduces cross-task interference. Proven to preserve safety alignment.
- **Merge before Forget** (arXiv:2512.23017, ICLR 2026): Single LoRA pair, merge after each task. Tested on Qwen2.5. Memory-efficient.
- **O-LoRA** (arXiv:2310.14152, EMNLP 2023): Orthogonal subspace loss — new LoRA updates ⊥ previous. Composable with GRPO.
- **DOC** (arXiv:2509.23893): Dynamic orthogonal — online PCA tracks subspace drift. Improvement over O-LoRA.

**Lightweight mitigations (add to any training loop):**
- **EAFT** (arXiv:2601.02151): entropy-adaptive token gating — down-weight conflicting tokens
- **Low-Perplexity Token Learning** (arXiv:2501.14315, NeurIPS 2025): train only on low-perplexity tokens; LLM-generated data < human-authored for forgetting
- **SSU** (arXiv:2512.04844, ACL 2026): column-wise freezing by importance — more effective than LoRA/regularization/merging
- **Replay general data** (arXiv:2603.04964, Stanford): mixing general data **also improves target domain 1.87×**

**Catastrophic overtraining** (arXiv:2503.19206, ICML 2025): heavily pre-trained models (Qwen3) are MORE sensitive to fine-tuning — use extra care, lower LRs, more replay.

## Code-Specific RL Training (2025-2026)

See `references/code-rl-training-2025.md` for full research.

**GRPO with execution rewards is the dominant paradigm.** Key advances:
- **P-GRPO** (arXiv:2508.05170): process rewards only on successful rollouts (anti-hacking)
- **MURPHY** (arXiv:2511.07833): multi-turn GRPO with self-correction (generate→run→fix→repeat)
- **CodeRL+** (arXiv:2510.18471, ACL 2026): execution semantics as dense reward, drop-in for GRPO
- **DRIVE** (arXiv:2511.06307): data curation matters more than algorithm — curriculum, entropy expansion

**SWE-bench SOTA:** SWE-RL (Meta, arXiv:2502.18449), SWE-smith (50K instances, arXiv:2504.21798), Self-Play SWE-RL (bug injector + fixer, arXiv:2512.18552, **no human data**).

**Adversarial self-play for code (2025-2026):** Beyond GRPO+execution rewards, a new paradigm uses adversarial co-evolution of code generation and test generation. Code-A1 (two separate models with opposing goals, solves self-collusion) is the strongest; CURE works without ground-truth code; ATGen uses a bug-generator as adversary. See `references/self-play-programming-2025.md` for full details + DGX Spark pipeline (4B Test LLM + 35B Code LLM = 93 GB).

**Key datasets:** OpenCodeReasoning (735K samples, NVIDIA, HuggingFace), OpenCodeReasoning-II (2.5M solution-critique triples).

**Agentic frameworks:** Polar (arXiv:2605.24220, any harness), ProRL Agent (arXiv:2603.18815, rollout-as-a-service for limited hardware).

## Model Merging (Zero-Compute Model Enhancement)

Model merging combines weights from multiple models WITHOUT training — zero compute cost, works immediately. Use BEFORE distillation to get a better starting point.

### mergekit Methods

| Method | Description | Quality | Use Case |
|---|---|---|---|
| **TIES** | Intelligent merge with conflict resolution | 🥇 | Combining complementary models |
| **DARE** | Random drop + rescale | 🥈 | Safer merge, less interference |
| **SLERP** | Spherical interpolation | 🥈 | Two-model smooth blend |
| **Passthrough** | Layer stacking (depth upscaling) | ⚠️ | See depth upscaling verdict below |
| **Model Stock** | Weighted average with anchor | 🥈 | Multiple models → one |

### MoE Limitations (CRITICAL)

- **mergekit does NOT support qwen35moe** — PR #696 is OPEN, not merged
- Qwen3.5 hybrid architecture (GatedDeltaNet + Attention, pattern LLLF) breaks standard merge paths
- `mergekit-moe` creates MoE FROM dense models — does NOT merge existing MoE models
- Workaround: custom Python safetensors-level surgery (see `references/model-merging-moe.md`)

## MoE Expert-Level Adaptation (2024-2026)

Beyond merging (zero-compute weight surgery) and anti-forgetting (DES-MoE dynamic freeze/unfreeze), there's a third paradigm: **add new experts and train only them**, or **select existing experts and train only those**. This gives zero forgetting on old domains while learning new capabilities.

**Key methods (see `references/moe-expert-adaptation.md` for full details):**

| Method | Adds experts? | What trains | Forgetting | Params added |
|--------|:---:|:---:|:---:|:---:|
| **ESFT** (DeepSeek, arXiv:2407.01906) | No | Top-K relevant existing experts | -67% | 0 |
| **Expert Upcycling** (arXiv:2604.19835) | Yes (copies) | Only new copies | **0%** | +10-25% |
| **ExPaMoE** (arXiv:2507.00502) | Yes (auto) | Only new (auto-detected) | -96% | +5% |
| **LLaVA-CMoE** (arXiv:2503.21227) | Yes (probe-guided) | Only where needed | -95% | +12% |
| **GoD-MoE** (AAAI 2026) | Yes (LoRA) | LoRA-experts only | ~0% | +0.5% |

**Most practical for Qwen3.5-35B on DGX Spark: Expert Upcycling** — duplicate a high-utility expert (safetensors surgery), expand router, train only the new expert. Zero forgetting, ~72 GB VRAM, ~6-12h per expert. Concrete code in `references/moe-expert-adaptation.md`.

## Depth Upscaling: Evidence-Based Verdict

**Adding layers to a 35B MoE model on DGX Spark does NOT make sense.** Evidence:

| Evidence | Source | Finding |
|---|---|---|
| **SOLAR 10.7B** | arXiv:2312.15166, NAACL 2024 | DUS works for dense 7B→10.7B, BUT needs 300B tokens CPT |
| **LLaMA Pro** | arXiv:2401.02415, ACL 2024 | Block expansion works for 7B→8.3B, needs 80B tokens + 2830 GPU-hrs |
| **"Depth Delusion"** | arXiv:2601.20994 (Jan 2026) | Width should grow 2.8× faster than depth. Beyond D_crit ∝ W^0.44, **adding layers INCREASES loss** |
| **Pretergeek study** | Open LLM Leaderboard v2 | Without CPT: +4 layers = +7.4 pts, +8/+12/+16 layers = **plateau (0 gain)** |
| **MoE depth upscaling** | Literature search | **ZERO papers** on MoE layer stacking. All DUS research is dense-only |
| **Frankenmerges** | HF Leaderboard | Goliath-120B: "benchmarks coming soon" for 2+ years. Community uses for roleplay only |

**5 days on DGX Spark = ~50K tokens for 35B. SOLAR needed 300B tokens. That's 0.017% of required CPT.**

**Alternative that works:** `mergekit TIES (0 compute) → QLoRA distillation (20h) → BAdam Full FT (5-8 days)` gives +20-35% quality without structural risk.

Full analysis with all paper citations in `references/depth-upscaling-analysis.md`.

## Framework Comparison

| Framework | DGX Spark | Speed | KD-logit | Verdict |
|---|:---:|:---:|:---:|---|
| **Unsloth** | ✅ Official Docker | 🥇 7.67× faster | ❌ custom needed | **RECOMMENDED** — 2× faster, lowest memory |
| **LLaMA-Factory** | ✅ NVIDIA playbook | 🥈 | ✅ built-in | Good for WebUI quick start |
| **TRL (HuggingFace)** | ✅ | 🥉 | ✅ custom | Standard, but slower than Unsloth |
| **NVIDIA NeMo** | ✅ Official playbook | 🥈 | ✅ **built-in KD-logit** | For KD-logit phase |

### Unsloth for Qwen3.5-35B-A3B MoE (Confirmed)

Unsloth is the **only** framework that confirmed support for Qwen3.5-35B-A3B MoE on single GPU:
- **QLoRA 4-bit**: model fits in **17.5GB VRAM** (128GB budget → massive headroom)
- **12× faster MoE fine-tuning** (optimized kernels)
- **GRPO RL on single GPU** with vLLM colocate mode
- **Router frozen by default** for MoE models (critical for routing stability)
- Supports Qwen3-30B-A3B, Qwen3.5-35B-A3B, Qwen3.6-35B-A3B, DeepSeek, gpt-oss
- Colab notebooks available for GRPO with MoE models

## Docker Setup for DGX Spark Training

Base image: `nvcr.io/nvidia/pytorch:25.09-py3` with CUDA 13.

Critical dependencies (all need source builds on aarch64):
- **Triton**: specific commit `c5d671f` for sm_121 support
- **flash-attn** 2.8.3: patched to add sm_121 onto sm_80 kernel path (`IryNeko/patched-flash_attn-2.8.3-for-dgx-spark`)
- **flash-linear-attention** + **causal-conv1d**: MANDATORY for Qwen3.5 hybrid models (75% GatedDeltaNet/SSM layers). Without them, those layers fall back to pure PyTorch and dominate step time (the single biggest perf win in albond's project)
- **xformers**: needs sm_121/aarch64 hotfixes (`ubehera/finetune` has 5 hotfixes)

Recommended: use `albond/DGX_Spark_Unsloth_Lossless_Speedup` Docker image directly — it bakes in all optimizations.

## Memory Budget (128 GB Unified Memory)

| Component | Full FT 4B | LoRA 4B | KD-logit (27B teacher) |
|---|---:|---:|---:|
| Student weights (BF16) | 9 GB | 9 GB | 9 GB |
| Gradients | 9 GB | 0 (frozen) | 9 GB |
| Optimizer states (Adam) | 18 GB | 0.5 GB (LoRA) | 18 GB |
| Activations (bs=1, seq=8192) | ~8 GB | ~4 GB | ~8 GB |
| Teacher (inference, frozen) | — | — | 54 GB |
| **Total** | **~44 GB** | **~14 GB** | **~98 GB** |
| **Free** | **84 GB** | **114 GB** | **30 GB** |

## Quick Start Code Patterns

### Full FT with Unsloth (primary path)

```python
from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset
import torch, wandb

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="Qwen/Qwen3-4B-Instruct-2507",
    max_seq_length=8192,
    dtype=torch.bfloat16,
    load_in_4bit=False,  # Full FT needs BF16
)
model.gradient_checkpointing_enable()

dataset = load_dataset("json", data_files="distill_dataset.jsonl", split="train")

config = SFTConfig(
    output_dir="./checkpoints/qwen3-4b-v1",
    num_train_epochs=3,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=16,
    learning_rate=2e-5,  # Full FT: 2e-5, LoRA: 1e-4
    warmup_ratio=0.05,
    lr_scheduler_type="cosine",
    bf16=True,
    max_seq_length=8192,
    packing=True,
    report_to="wandb",
)

trainer = SFTTrainer(model=model, tokenizer=tokenizer, train_dataset=dataset, args=config)
trainer.train()
model.save_pretrained_merged("./models/qwen3-4b-distilled-v1", tokenizer)
```

### LoRA variant (for 8B+ or fast iteration)

```python
model = FastLanguageModel.get_peft_model(
    model,
    r=128,  # high rank for quality
    target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
    lora_alpha=128,
    lora_dropout=0.05,
)
# learning_rate=1e-4 for LoRA
```

### KD-logit loss function

```python
def kd_loss(student_logits, teacher_logits, labels, alpha=0.5, T=2.0):
    """L = alpha * KL(student_T || teacher_T) + (1-alpha) * CE(student, labels)"""
    from torch.nn.functional import kl_div, log_softmax, cross_entropy
    soft_loss = kl_div(
        log_softmax(student_logits / T, dim=-1),
        torch.softmax(teacher_logits / T, dim=-1),
        reduction="batchmean",
    ) * (T ** 2)
    hard_loss = cross_entropy(
        student_logits.view(-1, student_logits.size(-1)), labels.view(-1))
    return alpha * soft_loss + (1 - alpha) * hard_loss
```

## Deploy After Training

Trained BF16 model → deploy via existing `local-model-serving` skill pipeline:
1. `convert_hf_to_gguf.py --outtype f16` → GGUF
2. APEX I-Quality quantize (for Qwen3.5 MoE) or Q4_K_M / Q8_0 (for dense)
3. `llama-server --no-mmap --jinja` on DGX Spark

See `local-model-serving` skill for full deploy + serving details.

## Evaluation

Always evaluate BEFORE and AFTER training to measure delta:

| Metric | Tool | Target (Qwen3-4B) |
|---|---|---|
| Perplexity | `llama-perplexity` on wikitext | Δ < 0.05 from baseline |
| MMLU | lm-eval-harness | ≥72% (parity with base) |
| HumanEval | evalplus / BigCodeBench | ≥82% |
| GSM8K | lm-eval-harness | ≥87% |
| Function Calling | BFCL | Task-dependent |
| Task-specific | Custom eval | > teacher pass-through rate |

See `evaluating-llms-harness` skill for eval setup.

## Data Generation for Distillation

Key principles from Predibase LLM Distillation Playbook:
1. **Maximize teacher quality** — GPT-4o / GLM-5.2 / Qwen3-235B; iterate on prompts
2. **Diversity > volume** — 25K diverse examples beat 100K repetitive ones
3. **Filter** — remove bad teacher outputs, keep only quality responses
4. **Balance** — ensure all task types represented, no dominance
5. **Start simple** — SFT on 1-5K examples, evaluate, iterate

Data generation pipeline: diverse prompt pool → async cloud API calls → filter (length, quality, dedup) → JSONL. Temperature 0.7 for diversity in generation, 0.0 for classification tasks.

## Pitfalls

- **sm_121 != sm_120**: Blackwell GB10 is sm_121 (sometimes sm_121a). Standard PyPI wheels target sm_80/sm_90. Triton, flash-attn, and xformers ALL need source builds or patched wheels for sm_121. Use the prebuilt wheels from `IryNeko/patched-flash_attn-2.8.3-for-dgx-spark` and `ubehera/finetune` hotfixes.
- **Qwen3.5 is hybrid architecture**: 75% of decoder layers are GatedDeltaNet/SSM, not Attention. Without `flash-linear-attention` + `causal-conv1d`, those layers fall back to pure PyTorch and dominate step time. This is the single biggest performance fix in albond's 7.67× speedup. **Also affects EAGLE3**: when training speculative decoding draft models on Qwen3.5-MoE targets, the default hidden state layer selection hits ALL linear attention layers. See `speculative-decoding` skill → `references/agents-a1-architecture.md` for the correct `--target-layer-ids` fix.
- **Full FT 8B+ is tight on DGX Spark with standard AdamW**: 18GB weights + 18GB grads + 36GB optimizer = 72GB. Use **BAdam** (block-wise) for 9B-45B Full FT — only 84GB for 35B. See `references/memory-efficient-training-methods.md` for full method comparison.
- **GaLore is INEFFECTIVE on Qwen3.5 MoE**: Qwen3.5's small weight matrices (2048×512) give only 37.5% gradient compression vs 91.5% on dense LLaMA. Do NOT use GaLore for qwen35moe models. Use BAdam instead.
- **bitsandbytes (8-bit Adam, QLoRA NF4) has uncertain sm_121 support**: May need source compilation with `BNB_CUDA_VERSION=130 TORCH_CUDA_ARCH_LIST="12.1"`. BAdam (pure PyTorch) is ironically MORE compatible on bleeding-edge aarch64/Blackwell than QLoRA's bitsandbytes dependency.
- **Depth upscaling (layer stacking) for MoE = uncharted territory**: No academic evidence, no tooling support (mergekit PR #696 not merged), and "Depth Delusion" paper shows adding layers beyond critical depth INCREASES loss. Do NOT add layers to 35B MoE models — use BAdam Full FT or model merging instead.
- **Passthrough merge without CPT plateaus at 4 layers**: Pretergeek systematic study (Open LLM Leaderboard v2) shows +4 layers gives +7.4 points, but +8/+12/+16 layers give ZERO additional gain. SOLAR needed 300B tokens CPT to make depth upscaling work — 5 days on DGX Spark is 0.017% of that.
- **Qwen3.5 MoE weights are under `model.language_model.layers.*` not `model.layers.*`**: Qwen3.5 is multimodal with a vision tower. BAdam block_prefix_list must use the full prefix or it won't match any parameters.
- **GKD works with black-box API teachers**: Unlike logit-based KD (which needs open-weight teacher logits), GKD only needs the teacher to evaluate student outputs. Cloud APIs (GPT-4o, GLM-5.2) CAN be used for on-policy distillation.
- **KD-logit needs teacher + student in memory simultaneously**: Teacher (27B = 54GB frozen) + Student (4B = 9GB + 18GB grads + 9GB optimizer) = ~90GB. This works on DGX Spark's 128GB unified memory but leaves only 30GB headroom — stop other models and Docker containers first.
- **Learning rate differs by method**: Full FT → 2e-5; LoRA → 1e-4 (5× higher because adapter params start from random init). Using Full FT LR for LoRA causes underfitting; using LoRA LR for Full FT causes divergence.
- **Sequence packing is critical for throughput**: Without `packing=True` in SFTConfig, short sequences waste compute. Packing combines multiple examples into one sequence up to `max_seq_length`, dramatically improving tokens/step.
- **NVFP4 training is experimental**: While GB10 supports NVFP4 in hardware, training (not just inference) in 4-bit is not yet production-ready in Unsloth/TRL. Stick with BF16 for training, use NVFP4 for inference after conversion.
- **OOM killer targets Hermes during heavy model operations**: Full FT of 4B+ models uses 40+ GB. vLLM loading a BF16 35B MoE model uses ~87GB. Both exceed the safe budget when Hermes Docker (gateway + dashboard + litellm + phoenix, ~4GB) and Hermes Desktop Electron (~4-8GB) are also running on 121GB unified memory. The Linux OOM killer WILL target Hermes (oom_score_adj=300). In severe cases (vLLM + BF16 35B model), this causes **full machine crashes** — not just process kills — because unified memory means GPU+CPU share the same pool, and kernel OOM can destabilize the system. Run heavy training/inference in a separate SSH session, not inside Hermes terminal. For vLLM specifically: use quantized models (FP8 ~33GB, AWQ ~20GB) or stop Hermes Desktop + non-essential Docker containers first. See `local-model-serving` → OOM Killer Diagnosis and `speculative-decoding` → pitfall #17 for details.
- **Always checkpoint frequently**: DGX Spark unified memory means a kernel panic or power loss loses all training state. `save_steps=500` + `save_total_limit=3` keeps rolling checkpoints without disk bloat.
- **`enable_thinking: false` for Qwen3**: Qwen3-2507 has a thinking mode that can cause empty content in Hermes (reasoning tokens consume max_tokens budget). When deploying a trained Qwen3 model, add `--reasoning off` to llama-server or `enable_thinking: false` in chat template kwargs. See `local-model-serving` pitfall on thinking models.
- **Don't retrain from a quantized checkpoint**: Always start training from BF16/FP16 base weights. Starting from Q4_K_M GGUF and then training produces garbage — quantization artifacts compound with gradient updates.
- **2025-2026 paradigm shift: on-policy distillation > off-policy SFT** (arXiv: Thinking Machines Lab, Oct 2025). Off-policy SFT (training on teacher-generated data) suffers from exposure bias — the student learns a different distribution than what it generates at inference. On-policy distillation (student generates trajectories, teacher gives token-level feedback) is ~10× cheaper than RL and reaches higher quality. Use GAD (arXiv:2511.10643) for black-box API teachers where logits aren't available. See `references/on-policy-distillation-2025.md`.
- **RL causes LESS catastrophic forgetting than SFT** — three independent 2025 papers converge (arXiv:2509.04259, 2501.17161, 2507.05386). RL is mode-seeking and preserves prior knowledge. SFT memorizes and overwrites. The SFT→RL pipeline is itself an anti-forgetting strategy (arXiv:2509.12235) — RL heals OOD forgetting from SFT. When possible, use GRPO/RLVR instead of pure SFT. See `references/catastrophic-forgetting-2025.md`.
- **RL does NOT create new reasoning capabilities — it only improves sampling efficiency** (Limit of RLVR, arXiv:2504.13837, NeurIPS 2025). At pass@1, RL-trained models dominate. But at large pass@k, base models catch up or surpass — all correct RL solutions already exist in the base model's distribution. RL narrows the solution space (good for pass@1, bad for diversity). **Distillation (SFT on teacher traces) is the ONLY way to introduce genuinely new reasoning patterns.** Pipeline implication: Phase 1 (distillation/SFT) is where new capabilities enter; Phase 2 (RL) focuses the model on correct paths but cannot add what wasn't distilled. If the base model already has latent capability (e.g., math in Qwen3), pure RL can unlock it (R1-Zero style). If it lacks the capability, no amount of RL will create it — need distillation first. Also: don't overtrain SFT before RL — excessive SFT makes RL less effective (Quagmires, arXiv:2510.01624). See `references/rl-vs-sft-quality-gains-2025.md`.
- **For MoE models, use DES-MoE** (arXiv:2509.16882, EMNLP 2025): Dynamic expert specialization reduces forgetting by 89% vs full FT on MoE models. Three innovations: (1) adaptive router with KL distillation to frozen original router, (2) real-time expert-domain correlation matrix to isolate domain-specific gradients, (3) three-phase schedule (warm-up → stabilization → consolidation with progressive expert freezing). Results: 7% forgetting (vs 60% baseline), 1.68× faster convergence, 102% quality on new domain. Implementation sketch in `references/catastrophic-forgetting-2025.md`.
- **Catastrophic overtraining** (arXiv:2503.19206, ICML 2025): Heavily pre-trained models (like Qwen3) are MORE sensitive to fine-tuning. Extended pre-training increases parameter sensitivity. Use extra care: lower LRs (1e-5 not 2e-5), more replay data, selective updates. Don't assume a strong base model is easier to fine-tune — it's harder.
- **LR controls forgetting via loss landscape sharpness** (arXiv:2604.13627): Large LR → sharp minima → more forgetting. Small LR → flat minima → less forgetting. Even at the same SFT loss, different LRs produce different forgetting profiles. Always prefer smaller LR with more steps over larger LR with fewer steps.
- **Replaying general data improves TARGET domain too** (arXiv:2603.04964, Stanford): Mixing 10-30% general/pre-training data not only prevents forgetting but improves target domain performance 1.87×. This is counterintuitive — replay is not just defensive, it's beneficial.
- **Self-improvement reversal risk** (arXiv:2407.05013): Iterative self-improvement (STaR/SPIN/SPC loops) can produce "reversal" — benchmarks improve but solution diversity degrades and OOD generalization worsens. Cap at 2-3 iterations, monitor diversity metrics, mix in teacher/original data. Don't iterate indefinitely.
- **Reward hacking in self-training** (arXiv:2505.21444): Self-consistency signals work but models can exploit them instead of genuinely improving. Use P-GRPO (arXiv:2508.05170) — process rewards only on successful rollouts — to mitigate.
- **Data curation matters more than algorithm for code RL** (arXiv:2511.06307, DRIVE): Difficulty curriculum (easy→hard), entropy expansion (prevent mode collapse), and prompt quality filtering impact competitive programming RL more than switching RL algorithms.
- **Use LLM-generated data for less forgetting** (arXiv:2501.14315, NeurIPS 2025): Training on LLM-generated/rephrased data causes less forgetting than human-authored data because it stays closer to the model's existing distribution. When building SFT datasets, prefer teacher-generated or model-rephrased data over raw human text.
- **Always lead with the 2025-2026 paradigm**: When recommending a distillation/fine-tuning pipeline, lead with on-policy distillation (OPD), GRPO/RLVR, and self-play — NOT the legacy 2022-2024 SFT→GKD→DistiLLM-2 chain. Off-policy SFT is Phase 1 bootstrap only; the key innovation is Phase 2 (on-policy). The previous session (`20260712_222643_9e5285`) made this mistake — recommended legacy pipeline despite the skill already containing the 2025-2026 paradigm. See `references/on-policy-distillation-2025.md` for the current methods.
- **Weak-to-Strong transfer is practical** (arXiv:2607.05394): Run RL on Qwen3-4B (cheap, fits 128GB) → transfer policy shift to Qwen3-35B via on-policy distillation. RL is more sample-efficient on smaller models, and OPD transfers the learned policy. Avoids expensive RL on 35B. ~10× cheaper.
- **FREEZE the MoE router during RL — categorically** (arXiv:2510.11370, 2606.00395): Top-K routing is non-differentiable — it creates gradient blackout (zero gradient for unselected experts, almost everywhere) and first-order approximation failure (PPO/GRPO surrogate is invalid at routing boundaries). Training the router through RL is mathematically broken. LoRA on experts + frozen router is the safe default (Unsloth freezes router by default, ESFT/MoE-Sieve/DR-LoRA all freeze router). Even with frozen router, use **R3 (Rollout Routing Replay)** to fix numerical mismatch between inference (vLLM) and training (VeRL/Megatron) engines — tiny numerical differences can cause completely different expert selections. Collapse risk: <0.5% with frozen router + R3 vs ~90% with trainable router + RL. If router adaptation is needed (radical domain shift), do it during SFT only using DenseMixer STE or DES-MoE Phase A, then freeze before RL. See `references/moe-routing-stability-rl.md`.
- **Use RO-GRPO for GRPO on LoRA-MoE** (ICLR 2026, OpenReview rhD7ZuFAjU): Standard GRPO on LoRA-MoE causes routing collapse — router concentrates on 1-2 "confident" experts, rest become dead weight. Traditional load-balancing auxiliary loss is incompatible with GRPO. RO-GRPO converts routing statistics (entropy + load variance) into a scalar reward added to the GRPO reward: `R = R_task + λ · (entropy_bonus - load_penalty)`. No architecture changes, no extra training stages. First systematic study of LoRA-MoE in RFT. Without it, routing collapse in LoRA-MoE + GRPO is near-certain.
- **Five mechanisms of MoE routing collapse** — know which one you're fighting: (1) softmax redistribution when adding experts (fix: copy router weights, arXiv 2510.08008), (2) train-inference discrepancy (fix: R3), (3) expert collapse/dead experts from bad init (fix: SPRI SVD-partitioned init, arXiv 2606.16456), (4) routing drift during fine-tuning (fix: SAME orthogonal subspace, arXiv 2602.01990), (5) RL-specific concentration (fix: RO-GRPO). Each requires a different defense. See `references/moe-routing-stability-rl.md` → "Five Mechanisms" section.
- **Don't add new experts unless LoRA is provably insufficient** — for Qwen3.5-35B-A3B with 128 experts, LoRA on existing experts + frozen router + R3 + RO-GRPO is the safest path (79GB, <0.5% collapse risk). Adding experts requires: SPRI SVD-partitioned init (not random/zero), copy router weights for zero-loss extension (Beyond Sunk Costs), freeze all original experts (LLaVA-CMoE), DES-MoE three-phase schedule. Only escalate if rank=128 + EPnG adaptive allocation (arXiv 2607.01789) is still insufficient. See `references/moe-routing-stability-rl.md` → "Safe Expert Addition Protocol".
- **Synergistic Regularization losses are free insurance** (arXiv 2602.14159): Two plug-and-play losses orthogonal to load-balancing: (1) intra-layer specialization (penalize cosine similarity between experts' SwiGLU activations → complementary specialization), (2) cross-layer coupling (maximize joint Top-k routing across adjacent layers → coherent expert pathways). No architecture changes. Add to any MoE training to reduce expert overlap and routing ambiguity.
- **G-OPD/ExOPD enables student to surpass teacher** (arXiv:2602.12125, github.com/RUCBM/G-OPD): Generalized On-Policy Distillation introduces a reward scaling factor λ. Standard OPD = λ=1 (student matches teacher ceiling). **ExOPD = λ>1 (reward extrapolation)** — student amplifies teacher's distinctive characteristics and can **surpass** domain-expert teachers. Sweet spot: λ≈1.25. λ>1.5 → instability. Multi-teacher ExOPD: student distilled from math+code experts outperformed BOTH in their own domains. **White-box only** (needs teacher logits) — use GAD for API-only teachers. verl implementation: `policy_loss.lambda_vals=1.25`. For hybrid multi-teacher: G-OPD for local/white-box teacher (Qwen3.7), GAD for API/black-box teachers (GLM-5.2, DeepSeek, GPT, Fable). See `references/multi-teacher-adversarial-distillation.md`.

## Agent-Model Co-Evolution (Mutual Improvement Loop)

Fine-tune a model to understand a local agent's codebase, while the agent simultaneously improves its own code. Each cycle: agent code improves + model gets smarter → synergy. See `references/agent-self-improvement.md` for full research.

### Key Methods

| Method | arXiv | Principle | GPU? | Result |
|--------|-------|-----------|------|--------|
| **SICA** (Self-Improving Coding Agent) | 2504.15228 | Agent edits its own code. SWE-bench 17%→53% | No (API) | ICLR 2025 |
| **Gödel Agent** | 2410.04444 | Self-referential: modifies its own modification logic | No | ACL 2025 |
| **HGM** (Huxley-Gödel Machine) | 2510.21614 | Tree of self-modifications + Thompson Sampling | No | Beats SICA |
| **AlphaEvolve** | 2506.13131 | Evolution + programmatic evaluator | No (Google Borg) | 23% kernel speedup in Gemini |
| **Live-SWE-Agent** | 2511.13646 | Online self-evolution during task execution | No | 75.4% SWE-bench Verified |
| **Hermes Self-Evolution** | ICLR 2026 Oral | DSPy + GEPA prompt/skill evolution | No | Already exists for Hermes |
| **ReST-EM** | 2312.06585 | Generate K → filter correct → SFT → repeat | Yes | Growing-batch RL |
| **STaR** | 2203.14465 | Generate rationale → check → fine-tune on correct | Yes | Bootstraps reasoning |

### Training Data from Agent's Own Sessions

Hermes state.db contains **real code-editing trajectories** — no need for synthetic data generation:

```
state.db (703MB): 669 sessions, 31,934 messages
  ├── 503 patch operations (code edits with old/new strings)
  ├── 402 write_file operations
  ├── 5,822 terminal commands (with exit codes = reward signal)
  ├── 1,803 read_file operations (context for edits)
  └── 60 sessions classified as "bug_fix_with_debugging" (most valuable)
```

Use `scripts/trajectory_extractor.py` to extract structured trajectories from state.db into JSONL format for SFT/RL training. Each trajectory = user_request → reasoning → tool_call → tool_result → next_fix, with success/failure labels from terminal exit codes.

### SWE-smith: Generate Training Data from Any Codebase

SWE-smith (arXiv:2504.21798, NeurIPS 2025) turns any GitHub repo (including the agent's own codebase) into structured SWE training data: bug localization, program repair, feature implementation tasks. 50K instances from 128 repos. SWE-agent-LM-32B: 40.2% SWE-bench Verified.

### Simple Anti-Forgetting Stack for Co-Evolution (~135 lines)

When fine-tuning on agent code trajectories, use this minimal stack:

1. **SDFT** (self-distillation) — near-zero forgetting, tested on our model
2. **Data mixing** — 70% agent + 20% general code + 10% general instruction (replay anchor)
3. **Mask the Target** — 5 lines, KL on non-target vocabulary
4. **Synergistic Regularization** — 30 lines, expert specialization (intra+cross-layer)
5. **RO-GRPO** — 50 lines, routing entropy + load_var → reward (for RL phase)
6. **Frozen Router** — 0 lines (Unsloth default for MoE)
7. **Mistake Book** — 20 lines, experience replay every 100 steps

### Co-Evolution Loop (10-14 days per cycle)

```
Phase A (3 days, No GPU): Agent self-improvement (SICA + GEPA)
  → Agent runs on SWE-smith tasks from its own code
  → Edits its own code, benchmarks, keeps improvements
  → Collects training data (successful trajectories)

Phase B (5-7 days, DGX Spark): Model fine-tuning
  → SFT with SDFT (Unsloth QLoRA, rank=128)
  → RL with GRPO + RO-GRPO (ReST-EM pattern)
  → Evaluate: general benchmarks (no regression >3%) + agent tasks (+10%)

Phase C (1 day): Integration
  → Deploy fine-tuned model as agent backbone
  → Measure: agent v2 + fine-tuned > agent v1 + original
```



- `speculative-decoding` — Train EAGLE3 draft models to accelerate inference of fine-tuned models. Uses the same DGX Spark platform but trains a lightweight auxiliary draft model (~0.4B) rather than fine-tuning the target model. Important after SFT/abliteration: MTP acceptance degrades, EAGLE3 can be retrained on the modified model's hidden states. **CRITICAL**: Eagle3 must be trained AFTER all model modifications (SFT, RL, abliteration). Do NOT use Eagle3 during RL training — it causes policy degradation (see `speculative-decoding` skill → "Eagle3 + RL Training" section and `references/eagle3-rl-interaction.md`). Use n-gram/prompt-lookup for RL rollout speedup instead.
- `local-model-serving` — deploy trained models via llama.cpp, APEX quantization, serving config
- `evaluating-llms-harness` — MMLU/GSM8K/HumanEval evaluation suite
- `weights-and-biases` — experiment tracking during training (wandb integration)
- **Code RL training (2025-2026):** GRPO with execution rewards is the dominant code training paradigm. Key datasets: OpenCodeReasoning (735K, NVIDIA, HuggingFace), SWE-smith (50K instances). Frameworks: Unsloth/TRL GRPOTrainer, Polar (any harness), ProRL Agent (rollout-as-a-service). See `references/code-rl-training-2025.md`.
- **Self-play for programming (2025-2026):** Adversarial code-test co-evolution frameworks — Code-A1 (two-model adversarial, solves self-collusion, Mistake Book anti-forgetting), CURE (no ground-truth needed), ATGen (test vs bug-generator), SAGE (setter-solver curriculum), Sol-Ver (baseline), SPC (step-level critic). Plus SPIRAL deep-dive (RAE mechanism, Kuhn Poker → math transfer). Includes practical DGX Spark composition: SPIRAL on 4B → Code-A1 (4B Test LLM + 35B Code LLM, 93 GB) → Direct-OPD transfer to 35B. See `references/self-play-programming-2025.md`.
- **Anti-forgetting (2025-2026):** RL > SFT for forgetting prevention. For MoE: DES-MoE (-89% forgetting, three innovations: adaptive router KL distillation, expert-domain correlation matrix, three-phase freezing schedule). Lightweight: EAFT entropy gating, Low-Perplexity masking, SSU column-freeze. See `references/catastrophic-forgetting-2025.md`.
- **Model merging mechanisms:** TIES (trim → elect sign → merge), DARE (random drop → rescale by 1/(1-p)), DARE-TIES combo. When to use each. MoE surgery limitations (mergekit PR #696, qwen35moe fused tensors). See `references/model-merging-moe.md`.
- **MoE expert-level adaptation:** Three paradigms — merging (zero-compute), anti-forgetting (DES-MoE freeze/unfreeze), expert addition (add new experts, train only them). Methods: ESFT (select+train), Expert Upcycling (copy+train, 0% forgetting), ExPaMoE (auto-grow), LLaVA-CMoE (probe-guided), GoD-MoE (LoRA-experts). See `references/moe-expert-adaptation.md`.
- **MoE routing stability during RL + expert addition:** Five mechanisms of routing collapse (softmax redistribution, train-inference discrepancy, expert collapse, routing drift, RL-specific concentration). Router MUST be frozen during RL. R3 (Rollout Routing Replay) fixes numerical train-inference mismatch. RO-GRPO (ICLR 2026) adds routing entropy + load variance as GRPO reward — prevents LoRA-MoE routing collapse. EPnG adaptive prune-and-grow for LoRA allocation. SAME orthogonal subspace for router drift. SPRI SVD-partitioned init for new experts. Synergistic Regularization (intra-layer + cross-layer). Safe Expert Addition Protocol (6 steps: select → SPRI init → copy router → freeze originals → R3+RO-GRPO → DES-MoE phases). Recommendation: don't add experts, use LoRA on existing 128. See `references/moe-routing-stability-rl.md`.
- **Agent-Model Co-Evolution:** Self-improving agent loops (SICA, Gödel Agent, HGM, AlphaEvolve, Live-SWE-Agent) + model fine-tuning on agent code trajectories. Hermes state.db contains 773 real code edits across 60 bug-fix sessions — extract with `scripts/trajectory_extractor.py`. SWE-smith generates SWE training data from any repo. Simple anti-forgetting stack (~135 lines): SDFT + data mixing + Mask the Target + Synergistic Reg + RO-GRPO + Frozen Router + Mistake Book. See `references/agent-self-improvement.md`.
- **Multi-Teacher Adversarial Distillation (MTAD):** Full pipeline for 5-teacher distillation into 35B MoE student (dual LoRA Code+Test heads). Combines GAD (black-box API teachers) + G-OPD/ExOPD (white-box teacher, λ=1.25 surpass teacher) + TCOD progressive depth + Anchored Self-Play + Agent Distillation. 6-layer router protection, 4-layer forgetting protection. Method ranking (15 methods, 4 tiers). See `references/multi-teacher-adversarial-distillation.md`.

- **DiffusionGemma RL Training:** Research landscape + rldiffusion pipeline architecture — adversarial self-play with dual LoRA (Code↔Test), DES-MoE 3-phase expert freeze, StableDRL vs GDPO vs diffu-GRPO comparison, the logits bottleneck (llama-diffusion-cli returns no logits), and launch patterns for DGX Spark. See `references/diffusiongemma-rl-training.md`.

## References

- **On-policy distillation (2025-2026):** Thinking Machines OPD, GAD (black-box), PACED, MOPD (multi-teacher, 95% oracle at 2 iters), self-distillation, self-play (Absolute Zero, SPIRAL on Qwen3-4B with GitHub repo + game-by-game results), DeepSeek-R1 GRPO, weak-to-strong transfer recipe (Direct-OPD with GitHub repo + AIME results + GPU-hour comparison). See `references/on-policy-distillation-2025.md`.
- **Multi-Teacher Adversarial Distillation (MTAD) Pipeline:** Complete pipeline design for distilling from 5 cloud teachers (GLM-5.2, DeepSeek V4, GPT-5, Fable 5, Qwen3.7) into 35B MoE student with dual LoRA heads (Code+Test). 6 phases (collection→SFT→RL warmup→role-swap→curriculum→eval), 6-layer router protection, 4-layer forgetting protection. G-OPD/ExOPD (reward extrapolation λ>1, student surpasses teacher), GAD implementation details (Bradley-Terry, multi-teacher discriminators), TCOD temporal curriculum, Anchored Self-Play, Agent Distillation. Method ranking (15 methods, 4 tiers). Budget: ~$800 API + 22 days. See `references/multi-teacher-adversarial-distillation.md`.
- `references/code-rl-training-2025.md` — 2025-2026 code RL research: P-GRPO, MURPHY (multi-turn GRPO), CodeRL+ (execution semantics), SWE-RL/SWE-smith/Self-Play SWE-RL, OpenCodeReasoning dataset (735K), Polar/ProRL agentic frameworks
- `references/catastrophic-forgetting-2025.md` — 2025-2026 forgetting research: RL > SFT (3 convergent papers), DES-MoE (-89% for MoE), EAFT entropy gating, Low-Perplexity masking, SSU column-freeze, Nested Learning (-70%), replay improves target 1.87×, catastrophic overtraining
- `references/rl-vs-sft-quality-gains-2025.md` — Deep research on RL vs SFT quality gains (9 papers, 2025-2026). RL gives bigger pass@1 gains but does NOT create new reasoning patterns — only improves sampling efficiency (Limit of RLVR, NeurIPS 2025). Distillation adds new capabilities, RL focuses them. SFT expands correct trajectories, RL squeezes incorrect ones (ICLR 2026). Don't overtrain SFT before RL (Quagmires, NeurIPS 2025). Includes DeepSeek-R1-Zero numbers, pass@k analysis, mechanism diagrams, and pipeline implications.
- `references/dgx-spark-training-benchmarks.md` — detailed throughput data, framework comparison, Docker setup, and source links
- `references/memory-efficient-training-methods.md` — BAdam vs GaLore vs LOMO vs 8-bit Adam vs Adafactor: memory formulas, max model sizes, MoE compatibility, sm_121/aarch64 readiness matrix
- `references/distillation-35b-student.md` — SFT/GKD/multi-teacher pipeline for 35B students, Predibase playbook findings, DistiLLM-2, expected quality gains (legacy 2022-2024 methods, superseded by on-policy-distillation-2025.md)
- `references/depth-upscaling-analysis.md` — SOLAR, LLaMA Pro, "Depth Delusion" paper, Pretergeek plateau data, MoE depth upscaling gap, evidence-based verdict
- `references/model-merging-moe.md` — mergekit methods, MoE limitations, expert surgery, qwen35moe weight structure, custom safetensors-level merge code
- `references/moe-expert-adaptation.md` — MoE expert-level adaptation: ESFT (select+train relevant experts), Expert Upcycling (duplicate+train copy, 0% forgetting), ExPaMoE (auto-detect+grow), LLaVA-CMoE (probe-guided), GoD-MoE (LoRA-experts). Includes safetensors surgery code for qwen35moe and decision guide
- `references/moe-routing-stability-rl.md` — MoE routing stability: 5 collapse mechanisms (softmax redistribution, train-inference discrepancy, expert collapse, routing drift, RL-specific), router freeze rationale (Top-K non-differentiability), R3/R2/Pr² routing replay, RO-GRPO (ICLR 2026, routing-aware reward for LoRA-MoE GRPO), EPnG (adaptive prune-and-grow), SAME (orthogonal subspace), Synergistic Regularization (intra+cross-layer), SPRI (SVD-partitioned init), Beyond Sunk Costs (zero-loss router extension), DenseMixer STE, GPT-OSS case study, safe expert addition protocol (6 steps), router monitoring checklist, collapse risk table
