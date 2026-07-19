# Diffusion LLM Improvement Map

Comprehensive guide to improving diffusion LLMs (DiffusionGemma, LLaDA, Dream). Organized by ROI level.

## Current limitations (DiffusionGemma 26B-A4B, June 2026)

| Problem | Details |
|:--------|:--------|
| Quality gap | -5..-20 pp vs Gemma 4 AR on ALL benchmarks |
| No KV-cache | Each diffusion step = full forward pass |
| No streaming | Response arrives all at once |
| Fixed canvas (256) | Block size hardcoded, cannot adapt dynamically |
| 1 request at a time | Diffusion loop occupies entire GPU |
| Safety guardrails | RLHF-aligned, refusal directions in weights |
| GPU underutilization | At low load, GPU sits idle (Optimus paper) |

## Benchmark gap detail

| Benchmark | Gap (pp) | Closeable | How |
|:----------|:---------|:----------|:----|
| MMLU Pro | -10..15 | 50-70% | CART + SFT |
| AIME 2026 | -15..20 | 40-60% | DoT + thinking mode |
| LiveCodeBench v6 | -10..15 | 30-50% | Token editing + SFT |
| GPQA Diamond | -5..10 | 60-80% | Steps 128 + CART |
| tau2-bench | -5..8 | 70-90% | VRPO alignment |
| MMMLU | -5..10 | 60-80% | SFT + steps tuning |

Overall: ~50% of the gap is closeable with known techniques.

## Level 1: Quick wins (no retraining)

### Steps tuning
- 32 steps: ~17s, ~85% quality
- 64 steps: ~30s, ~95% quality (sweet spot)
- 128 steps: ~60s, ~99% quality

### Thinking mode
Built-in reasoning channel (Gemma 4 style). Add thinking token at start of system prompt. Intermediate diffusion steps are interpretable (Google audit) — they recover CoT-like benefits automatically.

### Abliteration
Apply OBLITERATUS to remove safety guardrails. Orthogonal to diffusion architecture — modifies attention/MLP refusal directions, not diffusion head.

### Prompt engineering for diffusion
Diffusion models excel at infilling (filling masks) vs pure generation. Frame prompts as templates with `<mask>` placeholders rather than open-ended generation requests.

## Level 2: Inference optimization (training-free)

### Fast-dLLM v2 (NVIDIA Labs, ICLR 2026)
- **What**: Block-diffusion LLM with hierarchical KV caching (block-level cache across blocks + sub-block cache within partially decoded blocks)
- **Result**: up to 2.5× speedup over standard AR decoding, <2% quality loss
- **v1** (May 2025): approximate block-wise KV-cache, up to 27.6× throughput for full-sequence diffusion
- **GitHub**: NVlabs/Fast-dLLM (v2 has separate `v2/` directory)
- **v1 supports**: Dream, LLaDA (DiffusionGemma support was in development)
- **v2 supports**: block diffusion models (BD-LM architecture)
- **Paper v2**: arXiv:2509.26328

### S2D2 (Self-Speculative Decoding, Mar 2026)
- **What**: Training-free self-speculation for block-diffusion LMs. Same model acts as both drafter (block diffusion, block_size>1) and verifier (block_size=1, i.e. AR mode)
- **Key insight**: block_size=1 degenerates block diffusion to AR — no separate model needed
- **Result**: 4.7× acceleration, training-free, plug-and-play
- **Paper**: arXiv:2603.25702

### AdaBlock-dLLM (ICLR 2026)
- **What**: Semantic-aware adaptive block size scheduler. Aligns block boundaries with semantic steps by adjusting block size at runtime.
- **Discovery**: "Volatility Band" (VB) — token confidence dynamics during denoising reveal semantic structure
- **Result**: +2-3% quality, +10-20% TPF, training-free, plug-and-play
- **GitHub**: lgxi24/AdaBlock-dLLM
- **Paper**: arXiv:2509.26432

### Optimus (2026)
- **What**: Elastic decoding — dynamically adapt decoding granularity to runtime load
- **Low load**: more tokens per step, fewer steps, higher throughput
- **High load**: fewer tokens per step, more steps, higher quality
- **Result**: GPU utilization ~95%, up to 3.2x throughput
- **Paper**: arxiv.org/abs/2605.24832

### TEAM (Temporal-Spatial Consistency Guided Expert Activation)
- **What**: Delayed caching for MoE diffusion models
- **For decoded tokens**: activate experts only for recently accepted tokens
- **For masked tokens**: full forward pass
- **Result**: fewer expert activations, higher throughput on MoE
- **Paper**: arxiv.org/html/2602.08404

### Dynamic-dLLM
- Adaptive block sizes: 128/256/512 tokens depending on context
- Model decides block size dynamically

### Token editing (LLaDA 2.1)
- Model can go back and correct already-generated tokens
- "The diffusion model that fixes its own mistakes"
- Key for closing quality gap with AR

### S2D2 (Mar 2026)
- **What**: Training-free self-speculative decoding for block-diffusion LMs
- **How**: Same model acts as drafter (block_size>1, diffusion) and verifier (block_size=1=AR). No auxiliary model needed.
- **Result**: 4.7× acceleration, lossless
- **Paper**: arXiv:2603.25702

### AdaBlock-dLLM (ICLR 2026)
- **What**: Semantic-aware adaptive block size scheduler (training-free, plug-and-play)
- **How**: Aligns block boundaries with semantic steps by adjusting block size at runtime via "Volatility Band" analysis of token confidence dynamics
- **Result**: +2-3% quality, +10-20% TPF
- **GitHub**: lgxi24/AdaBlock-dLLM

### Trained sampler (Nemotron)
- **What**: Lightweight classifier that predicts whether top-1 prediction at each denoising step is correct
- **Why**: Confidence-based sampling uses only ~30% of diffusion's parallelism potential. SOL (Speed-of-Light) analysis shows 7.60× TPF theoretical ceiling.
- **Result**: +3-5% accuracy at same TPF, or +2-3× TPF at same accuracy
- **Cost**: ~1-2 GPU-days to train sampler

### Block-R1 (May 2026)
- **What**: Dynamic block size RL post-training — different domains have different optimal block sizes
- **Key finding**: Fixed one-for-all block size limits multi-domain RL
- **Result**: +2-5% multi-domain, sample-level best-improved training block sizes
- **GitHub**: YanJiangJerry/Block-R1

### RO-GRPO (Routing-Optimized GRPO, ICLR 2026)
- **What**: Converts MoE routing statistics (entropy + load variance) into scalar reward for GRPO
- **Why needed for DG**: DiffusionGemma is MoE (26B-A4B). Without routing-aware reward, GRPO concentrates traffic on 1-2 experts → routing collapse
- **Dependency**: REQUIRES StableDRL first — raw GRPO collapses on dLLMs. StableDRL staircase attention enables GRPO on block-diffusion → RO-GRPO prevents MoE routing collapse on top
- **Chain**: StableDRL → GRPO stable → RO-GRPO routing reward → full RL pipeline
- See `references/posttraining-methods-compatibility.md` for full compatibility matrix including GAD, DES-MoE, Anchored Self-Play, etc.

### StableDRL (2026)
- **What**: Fixes reward collapse in diffusion LLM RL training
- **How**: Unconditional clipping + self-normalization
- **Use**: Stabilizes RL post-training of diffusion LLMs

## Level 3: Fine-tuning
- Two modes: Speedy Mode (less editing, faster) and Quality Mode (more editing, higher accuracy)
- **Paper**: arXiv:2602.08676

### Trained sampler (Nemotron-Labs-Diffusion)
- **What**: Lightweight classifier that predicts whether top-1 prediction at each denoising step is correct (matches eventual committed token)
- **Why**: Confidence threshold is a fixed heuristic; trained sampler is optimized
- **Result**: +3-5% accuracy at same TPF, or +2-3× TPF at same accuracy
- **Cost**: ~1-2 GPU-days to train sampler
- **Key insight from SOL analysis**: confidence-based sampling uses only ~30% of theoretical parallelism potential. Optimal sampler could achieve 7.60× TPF (see SOL analysis below).

## Level 3: Fine-tuning

### ddm-sft (Discrete Denoising Model SFT)
1. Randomly mask fraction t~U[0,1] of tokens in target
2. Forward pass with bidirectional attention
3. Loss: cross-entropy on masked positions only
- Standard SFT method for diffusion LLMs
- Works with LoRA (target: attention layers, NOT diffusion head)
- Cost: 4-8 GPU-hours (LoRA rank 16)

### Hackable Diffusion (Google official, JAX)
- Modular research toolbox in google-deepmind/gemma repo
- Uses D3PM-uniform corruption (not simple masking)
- Reference task: Sudoku Solver
- Better post-fine-tune quality than mask-based

### LoRA fine-tuning
```python
lora_config = LoraConfig(
    r=16, lora_alpha=32,
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    # NOT diffusion head
)
```
- Via Unsloth or LLaMA-Factory + DiffuLLaMA
- 4-bit QLoRA possible (8GB VRAM for small models)

### EAGLE Drafter (NVIDIA NeMo)
- Train lightweight draft model for speculative decoding
- DiffusionGemma verifies, EAGLE drafts candidate blocks
- 2-3x speedup, lossless

## Level 4: Alignment

### VRPO (Variance-Reduced Preference Optimization)
- Standard DPO fails: diffusion has no exact log-likelihood, only ELBO with high variance
- VRPO formally analyzes ELBO variance, derives bounds on bias/variance
- Uses control variate for variance reduction
- LLaDA 1.5: +8-12 pp on alignment benchmarks after VRPO

### ELBO-KTO (Unpaired Preference Optimization, Oct 2025)
- No need for paired preferences, only labels (good/bad)
- Combines ELBO log-likelihood surrogate with prospect-theoretic unpaired preference optimization
- Aligns LLaDA-8B-Instruct without pairwise data
- Use when paired preference data is unavailable

### Coupled-GRPO (Apple, DiffuCoder, Jun 2025)
- Diffusion-native RL: coupled sampling for GRPO
- Two diffusion rollouts per step, coupled for lower variance
- +4.4% on EvalPlus (code generation)
- Reduces reliance on AR causal bias during decoding
- Paper: arXiv:2506.20639. GitHub: apple/ml-diffucoder

### Block-R1 (Dynamic Block Size RL, May 2026)
- Different domains (math, code, text) have different optimal block sizes
- Fixed one-for-all block size limits multi-domain RL performance
- Solution: sample-level best-improved training block sizes
- Also proposes b1: dynamic-size reasoning block method for dLLMs
- Paper: arXiv:2605.11726. GitHub: YanJiangJerry/Block-R1

### StableDRL (Stabilizing RL for Diffusion LLMs, 2026)
- Fixes reward collapse in diffusion LLM training
- Unconditional clipping + self-normalization
- Use when RL training for diffusion LMs becomes unstable

### Unpaired Preference Optimization (Oct 2025)
- No need for paired preferences, only labels (good/bad)
- Margin-aware loss
- Works with diffusion models

## Level 5: Research frontier

### CART (Context-Adaptive Token-Level Noise Rescheduling)
From Dream 7B. Key insight: uniform masking is suboptimal.

1. Estimate contextual informativeness per token (how well context predicts it)
2. Easy tokens (rich context) → less noise (as if later in diffusion)
3. Hard tokens (little context) → more noise (as if earlier)
4. Result: +5-10% on reasoning benchmarks

### Diffusion-of-Thought (DoT)
- Reasoning steps generated in PARALLEL, not sequentially
- Each step can use context from ALL other steps (bidirectional)
- No error propagation (mistake in step 1 doesn't cascade)
- DiffusionGemma audit already showed intermediate steps are interpretable

### Hybrid AR + Diffusion (Nemotron-Labs-Diffusion, May 2026)

**NVIDIA's tri-mode model** — one checkpoint, three decoding modes, switch attention pattern only. **Explicitly confirmed as DENSE** on HuggingFace model card ("SOTA 3B, 8B, 14B dense LM family").

- Paper: arXiv 2607.05722 (submitted July 7, 2026; weights released May 19, 2026)
- Sizes: 3B, 8B, 14B dense (open weights, HuggingFace) + 8B VLM variant
- Base: Qwen3 converted via Efficient-DLM (arXiv 2512.14067)
- Joint AR-diffusion training, α=0.3 — both objectives peak TOGETHER (no tradeoff)
- 6× more tokens per forward vs Qwen3-8B; 4× throughput on SPEED-Bench (GB200, SGLang)
- +1.2% accuracy vs Qwen3-8B (BETTER than AR!)
- Self-spec mode: 0.1% accuracy drop, 4× throughput; 2.2× speed-up vs Qwen3-8B-Eagle3 in SGLang
- Real measurements (DGX Spark, 8B, BF16): AR 1.0×, Diffusion 1.20×, Self-spec 1.75×, Self-spec+LoRA 1.98×
- GitHub: NVlabs/Nemotron-Labs-Diffusion (includes SGLang deployment guide for DGX Spark)
- Self-spec eliminates separate draft model: diffusion drafts → AR verifies in same checkpoint

### Nemotron-Labs-TwoTower (July 2026)

Frozen AR backbone + trainable denoiser tower. Best for MAXIMUM knowledge preservation.
- Base: Nemotron-3-Nano-30B-A3B (MoE, 30B/3B active)
- Backbone completely frozen, only denoiser trained (~2.1T tokens)
- 2.42× throughput, 98.7% quality retention
- arXiv: 2606.26493

### I-DLM (Introspective Diffusion, Apr 2026)

**First DLM to MATCH AR quality** across 15 benchmarks.
- Keeps causal attention (not bidirectional) + logit shift + all-masked objective
- LoRA only: 4.5B tokens, 8× H100, ~2-3 days
- AIME-24: 69.6 (+26 over LLaDA-2.1-mini 16B with half the params)
- Introspective acceptance: AR ~0.98, standard DLM ~0.57-0.70, I-DLM ~0.95+
- 2.9-4.1× throughput at high concurrency
- GitHub: Introspective-Diffusion/I-DLM
- MoE variant: github.com/yifan1130/I-DLM-MOE
- Serving: SGLang (paged KV cache, continuous batching, CUDA graphs)
- Introspective Strided Decoding (ISD): single-pass generation + verification with p/q acceptance criterion

## Nemotron-Labs-Diffusion training ablation (from arXiv:2607.05722)

Progressive ablation on Ministral3-8B, 25B tokens, evaluated in diffusion mode:

| Technique | Avg Accuracy | Δ |
|:----------|:-------------|:---|
| Block-wise attention (baseline) | 54.23% | — |
| + Global Loss Averaging | 56.35% | +2.12% |
| + DP-rank Varying Masking | 57.06% | +0.71% |
| + Two-stage training | 62.80% | +5.74% |
| + AR loss (α=0.3) | **70.28%** | **+7.48%** |

**Key takeaways:**
1. **AR loss + two-stage training contribute +13.22% out of +16.05% total** — they are the dominant quality drivers
2. **α=0.3 is the sweet spot** — both AR and diffusion objectives peak TOGETHER, not competing. No α in [0.1, 0.5] improves one mode at the expense of the other
3. **Global loss averaging** prevents samples with few highly-weighted noisy tokens from disproportionately influencing batch loss
4. **Position-dependent masking** assigns higher masking probabilities to later tokens (mimics left-to-right tendency)
5. **No token shift** — removing it consistently improves accuracy (contrary to prior works Dream/LLaDA that kept it)
6. **Diffusion loss preserves AR accuracy** — adding diffusion loss (α=0.3) slightly BOOSTS AR mode: +0.14% (base), +0.43% (instruct)

**Nemotron training recipe (14B scale):**
- Stage 1: 1T tokens, pure AR continuous pretraining (α=0)
- Stage 2: 300B tokens, joint AR+diffusion (α=0.3)
- SFT: 45B tokens, joint AR+diffusion
- Hardware: 256× H100, global batch 512, seq_len 4096 (base) / 16k (SFT)
- LR: 1e-5→3e-6 (base), 2.5e-6→2.5e-7 (SFT), WSD schedule, AdamW, wd=0.1
- Self-spec LoRA: rank 128, α=512, ~36M params (0.4% of backbone), o_proj only

## SOL (Speed-of-Light) analysis (from Nemotron paper)

Nemotron's SOL analysis estimates the theoretical upper bound of diffusion decoding with an optimal sampler:

| Metric | Current (confidence sampling) | SOL ceiling | Gap |
|:-------|:------------------------------|:------------|:----|
| TPF (tokens per forward) | ~2-3× | **7.60×** | ~60% unused |
| Per-category range | — | 3.49× (roleplay) to 11.26× (multilingual) | Category-dependent |

**Implications:**
1. Confidence-based sampling is far from optimal — substantial headroom for better samplers
2. Templated content (multilingual, QA) has more confidently-determined positions → higher SOL
3. Open-ended generation (roleplay) has lower SOL
4. Linear self-speculation achieves 6.82× acceptance rate (10.3% below SOL), but real TPF is 3.41× (76.5% below SOL) due to doubled forward-pass cost + prefix-only acceptance
5. **Trained sampler is the #1 ROI for inference acceleration** — closing the SOL gap is worth 2-3× additional TPF

## Scaling insight: Diffusion = Super Data Learners (arXiv:2511.03276)

Diffusion training acts as **implicit data augmentation**: each token is seen in all possible configurations (predicted from left, right, or both contexts). Key findings:

| Property | AR | Diffusion |
|:---------|:---|:----------|
| Data efficiency (1 epoch) | Baseline | ~equivalent |
| Multi-epoch improvement | Plateaus after ~15 epochs | **Improves for 500+ epochs** |
| Data-constrained regime | Quickly overfits | **Outperforms AR** |
| Compute trade | — | Expensive FLOPs, cheap data |

**Practical application**: When data is limited, diffusion models can train longer without overfitting. Especially valuable for domain-specific fine-tuning (medical, legal, code).

## Scaling laws for diffusion LMs (arXiv:2602.15014)

First scaling law study comparing masked, uniform-state, and interpolating discrete diffusion:
- Masked diffusion can be made ~12% more FLOP-efficient with simple cross-entropy objective
- Perplexity is informative WITHIN a diffusion family but misleading ACROSS families
- Uniform-state diffusion remains competitive and outperforms AR/masked on GSM8K despite worse perplexity
- Compute-optimal diffusion models are ~2× smaller than AR equivalents

### LLaDA 2.0 scaling roadmap
| Model | Params | Active | Approach | Quality vs AR |
|:------|:-------|:-------|:---------|:--------------|
| LLaDA 1.0 | 8B | 8B (dense) | From scratch, 2.3T tokens | ~parity LLaMA3 8B |
| LLaDA 1.5 | 8B | 8B | + VRPO alignment | +8-12 pp over 1.0 |
| Dream 7B | 7B | 7B | AR-init + CART | gap vs AR 7B |
| DiffusionGemma | 26B | 4B (MoE) | Gemma 4 + diffusion head | -5..20 pp vs Gemma 4 |
| ZAYA1-8B | 8B | 760M (MoE) | AR→Diffusion (TiDAR) | preview quality |
| LLaDA 2.0/2.1 flash | 100B | 6.1B (MoE) | AR conversion + scale | ≈ Qwen3-30B (NOT SOTA!) |
| LLaDA 2.1 mini | 16B | 1.4B (MoE) | + token editing | ≈ Qwen3-8B |
| **I-DLM 8B** | **8B** | **8B** | **LoRA on Qwen3-8B** | **MATCHES AR (15 bench!)** |
| **Nemotron tri-mode** | **3/8/14B** | same (DENSE) | **Efficient-DLM** | **+1.2% vs Qwen3-8B** |
| **Nemotron TwoTower** | **30B** | **3B (MoE)** | **Frozen AR + denoiser** | **98.7% of AR** |
| **DreamReasoner-8B** | **8B** | **8B (DENSE)** | **Block-size curriculum** | **≈ Qwen3-8B-Thinking** |
| **DiffuCoder 7B** | **7B** | **7B (DENSE)** | **Masked diff + cpGRPO** | **code-specialized** |
| **MMaDA 8B** | **8B** | **8B (DENSE)** | **Unified multimodal diff** | **multimodal** |
| **RND1** | **30B** | **3B (MoE)** | **AR→Diffusion** | **largest open MoE dLLM** |
| **NBDiff-7B** | **7B** | **7B (DENSE)** | **Context-causal masking + block-growth** | **SOTA 7B DLM (GSM8K 79.6%)** |
| Mercury 2 | ?(closed) | ? | Commercial | 1009 tok/s |
| Seed Diffusion | ?(closed) | ? | Commercial (ByteDance) | 2146 tok/s |
| Gemini Diffusion | ?(closed) | ? | Commercial (Google) | 1479 tok/s |

**Key insight (July 2026)**: 100B diffusion (LLaDA 2.1-flash) only matches Qwen3-30B AR — diffusion needs ~3-4× more params for parity. Exception: I-DLM 8B matches AR at same scale by keeping causal attention. NBDiff-7B achieves SOTA 7B DLM quality via context-causal masking + block-growth (arXiv:2512.06776). The field is at ~2023 AR maturity: technology works, scale achieved, SOTA quality gap is closing fast.

## Nemotron-Labs-Diffusion training ablation (arXiv:2607.05722)

Progressive ablation on 25B tokens, Ministral3-8B base:

| Technique | Avg Accuracy | Δ |
|:----------|:-------------|:--|
| Block-wise attention (baseline) | 54.23% | — |
| + Global Loss Averaging | 56.35% | +2.12% |
| + DP-rank Varying Masking | 57.06% | +0.71% |
| + Two-stage training (AR first, then joint) | 62.80% | +5.74% |
| + AR loss (α=0.3) | **70.28%** | **+7.48%** |
| **Total** | **70.28%** | **+16.05%** |

Key findings:
- AR loss + two-stage training = +13.22% out of +16.05% total
- AR and diffusion are complementary, not competing — both peak at α=0.3
- α sensitivity: [0.1, 0.5] range — no value improves one mode at expense of other
- Training: Stage 1 = 1T tokens pure AR, Stage 2 = 300B tokens joint (α=0.3), SFT = 45B tokens
- Hardware: 256× H100, global batch 512, seq_len 4096, LR 1e-5→3e-6 WSD schedule

### SOL (Speed-of-Light) analysis

Nemotron's SOL analysis estimates the theoretical upper bound of diffusion decoding with an optimal sampler:
- **Current confidence-based sampling**: ~2-3× TPF (uses ~30% of potential)
- **Linear self-speculation**: 6.82× acceptance rate, but 3.41× real TPF (2 forwards per cycle)
- **SOL ceiling**: **7.60× TPF** — 76.5% more tokens per forward than self-speculation
- **Category variance**: SOL spans 3.49× (roleplay) to 11.26× (multilingual)
- **Implication**: Better samplers are the #1 research direction for diffusion LLM acceleration

### Efficient-DLM findings (arXiv:2512.14067)

NVIDIA's foundational AR→DLM conversion method. Key ablation findings:

1. **Block-wise attention > bidirectional**: +19.12% accuracy (better preserves AR weight distributions)
2. **Clean context conditioning**: +9.46% accuracy (each block conditioned on clean prefix, not noisy)
3. **No token shift**: removing token shift consistently improves accuracy (opposite of prior work)
4. **Optimal block size**: 16 for training (sweet spot). Too small = insufficient context, too large = excessive corruption
5. **Position-dependent masking**: higher masking for later tokens mimics left-to-right tendency
6. **Training cost**: ~10B tokens for functional conversion, ~100B for aggressive parallel generation

## Layer collapse in diffusion LLMs (arXiv:2605.06366)

Critical finding: DLMs have fundamentally different internal dynamics vs AR models.

| Property | AR (Llama-3.1-8B) | Diffusion (LLaDA-8B) |
|:---------|:-------------------|:---------------------|
| Redundant layers | Deep layers (undertrained) | **EARLY layers** (overtrained!) |
| Outlier channels | Change per layer, moderate | **Single super-outlier** (ch 3848), persists 15+ layers |
| Pruning top channel | -4% accuracy | **-83% → total collapse** |
| 3-bit GPTQ quantization | -64.7% on GSM8K | **-1.8%** (DLM robust!) |
| Optimal sparsity | Sparse late layers | **Sparse early layers** (inverted!) |

Key insight: layer collapse in DLMs is driven by **overtraining** (not undertraining like AR). A dominant outlier becomes indispensable; remaining representations collapse into redundancy.

**Practical implications**:
- Do NOT add layers to diffusion LLMs — early layers are already redundant
- DLMs are surprisingly robust to quantization (3-bit GPTQ viable)
- Sparsity allocation must be inverted vs AR: more sparse in early layers

## Depth scaling: why more layers HURT (arXiv:2601.20994)

"Depth Delusion" study: 30 transformer architectures (17M–7B, depths 2–80, widths 256–6144).

| Finding | Formula | Implication |
|:--------|:--------|:------------|
| Optimal depth | D* ∝ C^0.12 | Grows very slowly with compute |
| Optimal width | W* ∝ C^0.34 | Grows 2.8× faster than depth |
| Critical depth | D_crit ∝ W^0.44 | Beyond this, more layers = worse |
| Mechanism | Gradient starvation: ‖∇_ℓ L‖ ≈ ‖∇_D L‖ · e^(-(D-ℓ)/τ(W)) | Early layers get exponentially weak gradients |

At 7B scale: 64-layer model (6.38B params) **underperforms** 32-layer (6.86B params) by 0.12 nats.
Existing models (GPT-3: 96 layers, PaLM: 118) are 3.6–4.9× deeper than optimal.

**For Nemotron-14B** (hidden~5120, ~48 layers): D_crit ≈ 5120^0.44 ≈ 33 layers. Model is already beyond critical depth.

**Recommendation**: Scale width (hidden_dim) not depth. Or use LayerNorm Scaling (NeurIPS 2025) to mitigate curse of depth.

## Diffusion LLMs as super data learners (arXiv:2511.03276)

Diffusion training = implicit data augmentation. Each token seen in all possible configurations (sometimes predicted from left, sometimes right, sometimes both).

| Property | AR | Diffusion |
|:---------|:---|:----------|
| Data efficiency (1 epoch) | Baseline | ~equivalent |
| Multi-epoch improvement | Plateau after ~15 epochs | **Improves 500+ epochs** |
| Data-constrained regime | Overfits quickly | **Outperforms AR** |
| Compute trade | — | Cheap FLOPs, expensive data |

**Practical**: when data is limited, train diffusion LLMs longer (more epochs) without overfitting. Especially useful for domain-specific fine-tuning (medical, legal, code).

### Scaling DiffusionGemma: 3 paths
- **Path A (more experts)**: 26B→52B, 8→16 experts, same 4B active → more capacity, same speed
- **Path B (more active)**: 4B→8B active (top-4 routing) → higher quality, lower speed
- **Path C (bigger canvas)**: 256→512/1024 tokens per block → higher throughput per step, linear VRAM

### Mercury (commercial, closed)
- Mercury 2: 1009 tokens/sec on H100, up to 10x vs AR
- Closed API, no open weights
- Inception Labs; first commercial-scale dLLM

### Seed Diffusion (commercial, closed)
- ByteDance Seed + Tsinghua AIR; 2146 tok/s on H20 GPUs (5.4× over AR)
- Code generation focus; arXiv 2508.02193
- Closed preview, no open weights

### Gemini Diffusion (commercial, closed)
- Google DeepMind; ~1479 tok/s; ~Gemini 2.0 Flash-Lite quality
- Internal precursor to DiffusionGemma; waitlist only

### Key resources
- **awesome-language-diffusion** (Optimizer077/awesome-language-diffusion): 356 verified papers, daily updated. Best living index of the field.
- **Awesome-Diffusion-LLM** (Jianguo99/Awesome-Diffusion-LLM): another curated list, less comprehensive.
- **dLLM survey** (arXiv 2508.10875): comprehensive taxonomy of continuous/discrete/multimodal DLMs.
