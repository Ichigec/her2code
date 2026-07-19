# AR → Diffusion Conversion

How to convert any pretrained autoregressive LLM (Qwen, LLaMA, GPT-2) into a diffusion language model.

## Why convert instead of training from scratch

| Approach | Tokens needed | GPU-days (27B) | Quality vs AR |
|:---------|:-------------|:---------------|:-------------|
| From scratch (LLaDA 1.0) | 2.3T | ~500-1000 | baseline |
| Conversion (DiffuLLaMA) | <200B | ~50-100 | 80-95% |
| Conversion + CART (Dream) | <200B | ~50-100 | 85-97% |

Conversion reuses AR pretrained weights as initialization, then continues training with diffusion objective. ~10x cheaper than from scratch.

## Architectural changes

```
AR Model                      Diffusion Model
─────────                     ───────────────
Attention: CAUSAL             → BIDIRECTIONAL
  (mask future tokens)           (see all positions)
Objective: NTP                → Masked ELBO
  (predict next token)           (predict masked tokens)
Decoding: Left-to-right       → Parallel denoising
  (token by token)               (all at once, T steps)
KV-cache: YES                 → NO (full forward per step)
  (incremental)                  (unless Fast-dLLM)
```

## 5 proven conversion approaches

### 1. DiffuLLaMA (ICLR 2025, HKUNLP)

**Paper**: arxiv.org/abs/2410.17891
**GitHub**: github.com/HKUNLP/DiffuLLaMA
**Scale**: 127M - 7B (GPT-2, LLaMA)

Method:
1. Take pretrained AR model
2. Replace causal attention → bidirectional
3. Unified objective: alpha * L_NTP + (1-alpha) * L_diffusion
4. Continue training with <200B tokens

Key insight: AR and diffusion objectives can be unified. NTP is a special case of masked prediction where only the last token is masked.

```python
# Conceptual
model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3-8B")
model.config.attention_type = "bidirectional"
# Train with: mask random tokens, predict them, bidirectional context
```

Cost: ~50-100 GPU-days for 27B (estimated from 7B scaling).

### 2. LLaDA 2.0 (Dec 2025, inclusionAI)

**Paper**: arxiv.org/abs/2512.15745
**GitHub**: github.com/inclusionAI/LLaDA2.X
**Scale**: up to 100B (largest diffusion LLM)

Two-phase conversion:
- Phase 1: Continual pre-training (AR weights frozen backbone + masked diffusion objective + dual training, ~1T tokens)
- Phase 2: Instruction tuning + VRPO alignment

LLaDA 2.0-flash: 100B total params, demonstrates code generation + complex instruction following.

LLaDA 2.1: 16B MoE (1B active), adds token editing (model corrects already-generated tokens).

### 3. Dream 7B (Aug 2025, HKUNLP + Huawei)

**Paper**: arxiv.org/abs/2508.15487
**Blog**: hkunlp.github.io/blog/2025/dream/
**Scale**: 7B

Key innovations:
- **AR-based initialization**: shifted mask prediction — model predicts token[t+1] from input[t] (masked), with bidirectional context. Maximum architectural alignment with AR weights.
- **CART** (Context-Adaptive Token-Level Noise Rescheduling): per-token adaptive noise instead of uniform masking. Easy tokens (rich context) get less noise, hard tokens get more. +5-10% on reasoning.

### 4. ZAYA1-8B (May 2026, Zyphra)

**Scale**: 8B MoE (760M active)
**First**: MoE diffusion model converted from AR LLM
**First**: Diffusion LLM trained on AMD GPUs (MI300x)

Uses TiDAR mid-training recipe. Results: 4.6x lossless speedup, 7.7x aggressive speedup.

### 5. Open-dLLM (2026, pengzhangzhi)

**GitHub**: github.com/pengzhangzhi/Open-dLLM
**Scope**: Full pipeline: data → training → checkpoints → eval → inference

First fully open-source diffusion LLM framework. Includes ready recipes for converting Qwen, LLaMA, and even BERT encoders.

```bash
git clone https://github.com/pengzhangzhi/Open-dLLM
# Config: base_model, attention=bidirectional, mask_token, diffusion_steps
python train.py --config configs/qwen3_diffusion.yaml
```

## Practical conversion for Qwen 3.6 → Diffusion

### Minimum viable approach (Open-dLLM + DiffuLLaMA method)

1. Start with Qwen3-1.7B (proof of concept)
2. Replace causal → bidirectional attention
3. Train with unified NTP + masked ELBO objective
4. ~10-20B tokens for proof of concept (~5-10 GPU-days)
5. Scale to 8B, then 27B

### Cost estimate for Qwen3.6-27B → Diffusion

| Resource | Estimate |
|:---------|:---------|
| GPU-days (A100) | 50-100 |
| Training tokens | 100-200B |
| Quality vs AR | 80-95% |
| Inference speedup | 3-5x |
| KV-cache | Lost (unless Fast-dLLM) |
| Streaming | Lost (response arrives all at once) |

## "Hacking Diffusion into Qwen3" (practical experiment)

Matthew Newton (matthewnewton.com/blog/arc-challenge-diffusion) directly adapted Qwen3-8B for diffusion-based ARC solving:

> "You can convert autoregressive models to diffusion by simply further training with a fully connected attention, with masked out inputs, rather than causal attention and predicting the next token."

His approach: fine-tuned Qwen3-8B, replaced causal → bidirectional, trained on masked prediction, used for ARC challenge (global generation, not left-to-right).

## Key trade-offs: AR vs converted Diffusion

| Feature | AR Qwen 3.6 | Diffusion Qwen 3.6 |
|:--------|:------------|:-------------------|
| Streaming output | YES | NO |
| KV-cache | YES | NO (unless Fast-dLLM) |
| Token-by-token | YES | NO (parallel blocks) |
| Speed | baseline | 3-5x faster |
| Bidirectional context | NO | YES |
| Error correction | NO | YES (iterative refinement) |
| Ecosystem maturity | Full | Emerging |

## I-DLM (Introspective Diffusion) — BEST AR knowledge preservation

**Paper**: arXiv 2604.11035 (Apr 2026)
**GitHub**: github.com/Introspective-Diffusion/I-DLM

**The first diffusion LLM to MATCH same-scale AR quality across 15 benchmarks.**

### Why standard conversion loses knowledge

AR models have **introspective consistency** — they agree with their own generations (acceptance rate ~0.98). Standard diffusion LMs with bidirectional attention LACK this (~0.57-0.70). I-DLM recovers it (~0.95+).

### Three key ingredients

1. **Strict causal masking** — do NOT switch to bidirectional! Causal attention for both masked and clean tokens.
2. **Logit shift (Dream shift)** — hidden state at position i predicts token i+1 (same as AR, but with diffusion decoding).
3. **All-masked objective** — CE loss on BOTH noisy (masked) AND clean tokens. Model learns to "agree with itself."

### Training recipe (remarkably cheap)

- Base: Qwen3-8B (pretrained AR)
- Method: **LoRA** on attention layers (NOT full retrain!)
- Data: **4.5B tokens** only
- Hardware: 8× H100
- Time: ~2-3 days
- Output: I-DLM-8B-LoRA adapter

### Results (15 benchmarks)

- AIME-24: **69.6** (+26 over LLaDA-2.1-mini 16B — half the params, better!)
- LiveCodeBench-v6: **45.7** (+15 over LLaDA-2.1-mini)
- **MATCHES base AR model quality** (first ever for diffusion)
- 2.9-4.1× throughput at high concurrency

### For Qwen3.6-27B conversion

Estimated: LoRA, ~4.5-10B tokens, 8× H100, ~5-7 days. Preserves 95%+ AR knowledge.

## Nemotron-Labs-Diffusion (tri-mode, May 2026)

**Paper**: arXiv 2607.05722 (July 2026); base method: Efficient-DLM (arXiv 2512.14067, Dec 2025)
**Weights**: nvidia/Nemotron-Labs-Diffusion-{3B,8B,14B} on HuggingFace
**License**: NVIDIA Nemotron Open Model License
**Architecture**: DENSE (confirmed on HF model card: "SOTA 3B, 8B, 14B dense LM family")

**One checkpoint, three decoding modes** — switch attention pattern only:

| Mode | Attention | Tokens/forward | Use case |
|:-----|:----------|:---------------|:---------|
| AR | Causal | 1 | Best quality |
| Diffusion | Bidirectional | 6× vs Qwen3-8B | Maximum speed |
| Self-speculation | Diffusion drafts → AR verifies | ~4× | Best balance |

### Key findings

- Base: Qwen3 converted via Efficient-DLM (joint AR+diffusion training, α=0.3)
- Both objectives peak TOGETHER — no quality/speed tradeoff
- +1.2% accuracy vs Qwen3-8B (BETTER than AR!)
- Self-spec mode: only 0.1% accuracy drop vs AR
- Real measurements (DGX Spark, 8B, BF16): AR 1.0×, Diffusion 1.20×, Self-spec 1.75×, Self-spec+LoRA 1.98×

## Nemotron-Labs-TwoTower (July 2026)

**Paper**: arXiv 2606.26493
**Base**: Nemotron-3-Nano-30B-A3B (MoE, 30B/3B active)

**Frozen AR backbone + trainable denoiser tower** — best for MAXIMUM knowledge preservation.

### Architecture

- **Context Tower** (FROZEN): original AR weights, causal attention, produces KV cache + Mamba-2 states
- **Denoiser Tower** (TRAINABLE): separate, bidirectional attention, takes AR hidden states + masked positions, produces denoised tokens

### Training

- Backbone: completely frozen (no retraining!)
- Denoiser: trained with ~2.1T tokens
- Can also do joint AR+diffusion training (alternative rows)

### Results

- **2.42× throughput** vs AR baseline
- **98.7% quality retention** (only 1.3% drop!)
- γ=0.8, S=16, 2×H100

### When to use

Best approach when you need to preserve 100% of AR knowledge. The AR backbone stays exactly as-is; the denoiser is purely additive.

## Efficient-DLM (NVIDIA's base paper)

**Paper**: arXiv 2512.14067 (Dec 2025, updated Apr 2026)
**GitHub**: NVlabs/Nemotron-Labs-Diffusion (implementation)
**Weights**: Efficient-DLM-4B, Efficient-DLM-8B on HuggingFace

NVIDIA's foundational AR→DLM conversion method. Key insight: "don't train DLMs from scratch — convert pretrained AR models." Built on Qwen3 checkpoints (0.6B, 1.7B, 4B). This is the academic basis for Nemotron-Labs-Diffusion.

### Critical findings from systematic ablation (Qwen2.5-1.5B, 50B tokens)

**1. Attention pattern is THE key decision:**

| Pattern | Avg Accuracy | Notes |
|:--------|:------------|:------|
| Bidirectional (Dream-style) | 19.29% | Massive quality loss from AR (41.79%) |
| Block-wise w/o clean context | 28.23% | Better, but still gap |
| Block-wise w/ clean context | **38.41%** | **Best — +19.12% over bidirectional** |

- Block-wise attention better preserves AR weight distributions (less weight drift in attention AND FFN layers)
- Bidirectional attention causes largest weight drift from pretrained weights

**2. Clean context conditioning is critical:**
- +9.46% accuracy improvement over noisy context
- Doubling training tokens on corrupted context CANNOT recover this gap
- Each block must be conditioned on CLEAN prefix during training (mimics test-time where all previous blocks are fully decoded)

**3. Token shift is UNNECESSARY and HARMFUL:**
- Contrary to Dream/LLaDA which keep token shift (predicting next token at masked position)
- Removing it consistently improves accuracy
- Predicting the mask token itself is easier than predicting the following token

**4. Optimal training block size = 16:**
- Too small (4-8): insufficient context for denoising
- Too large (64-128): excessive corruption, weight changes
- 16 is the sweet spot; evaluation block size can be larger (32-128) for more parallelism

**5. Position-dependent masking:**
- Assigns higher masking probabilities to LATER tokens in each block
- Mimics the left-to-right generation tendency that dLLMs retain
- Bridges training-test gap (uniform masking vs. confidence-based left-to-right sampling at test time)

### Efficient-DLM 8B results
- +5.4% accuracy over Dream 7B with 4.5× throughput
- +2.7% accuracy over Qwen3 4B with 2.7× throughput
- Training cost: ~10B tokens for functional conversion, ~100B for aggressive parallel generation

### Nemotron-Labs-Diffusion training recipe (from arXiv:2607.05722)

Built on Efficient-DLM with additional techniques. Full pipeline:

**Stage 1 — Pure AR (1T tokens):**
- α=0 (no diffusion loss)
- Strengthens left-to-right linguistic priors
- Critical: better AR initialization → better future planning → easier AR-to-diffusion conversion

**Stage 2 — Joint AR+Diffusion (300B tokens):**
- α=0.3 (diffusion loss weight; AR loss weight = 1)
- Block-wise attention with clean context conditioning
- No token shift
- Global loss averaging (all tokens across batch weighted equally — prevents gradient variance from variable masking)
- DP-rank varying masking ratios (different noise levels across parallel ranks)
- Position-dependent masking (more masking for later tokens)
- Dual-stream input: corrupted view + clean view concatenated, structured attention mask
- Clean stream uses strictly CAUSAL mask (enables AR loss computation in same forward pass)

**SFT (45B tokens):**
- Joint AR+diffusion (α=0.3)
- Loss computed only on answer parts (no masking on prompt)
- Batch 256, seq_len 16k

**Self-spec LoRA drafter:**
- Rank 128, α=512, ~36M params (0.4% of backbone)
- Applied to o_proj only
- LK-hybrid distribution-matching loss + token-level CE
- Active position mask: "accepted + 1" (loss only on accepted prefix + first rejected position)
- Temperature τ=3.0 for distribution matching

**Ablation contribution (cumulative, 25B tokens, 8B):**
| Technique | Δ Avg Accuracy |
|:----------|:---------------|
| Block-wise attention (baseline) | — |
| + Global Loss Averaging | +2.12% |
| + DP-rank Varying Masking | +0.71% |
| + Two-stage training | +5.74% |
| + AR loss (α=0.3) | +7.48% |
| **Total** | **+16.05%** |

### SOL (Speed-of-Light) analysis

Nemotron paper includes a speed-of-light analysis estimating theoretical max of diffusion decoding:
- **SOL ceiling: 7.60× TPF** (tokens per forward pass) with optimal sampler
- **Current confidence sampling: ~2-3× TPF** — only ~30-40% of SOL potential
- **Linear self-spec: 6.82× acceptance rate** (10.3% below SOL), but real TPF = 3.41× (76.5% below SOL due to doubled forward + prefix-only acceptance)
- **Per-category SOL range**: 3.49× (roleplay) to 11.26× (multilingual) — templated content has more confidently determined positions
- **Implication**: trained sampler is the #1 ROI for inference acceleration. Closing the SOL gap = 2-3× additional TPF

## Conversion method selection guide

| If you need... | Use... | Why |
|:---------------|:-------|:----|
| Maximum knowledge preservation | **I-DLM** or **TwoTower** | Causal attention kept / backbone frozen |
| Maximum speed | **Nemotron tri-mode** (diffusion mode) | 6× tokens per forward |
| Best balance | **Nemotron tri-mode** (self-spec) | 4× throughput, 99.9% quality |
| Cheapest conversion | **I-DLM** (LoRA) | 4.5B tokens, 8× H100, 2-3 days |
| Best 7B DLM quality | **NBDiff-7B** | Context-causal masking + block-growth, SOTA on math/reasoning |
| Full open-source pipeline | **Open-dLLM** | Data→train→eval→infer, all in one repo |
| Scale to 100B+ | **LLaDA 2.0** approach | Proven at 100B |
| Long-CoT reasoning | **DreamReasoner-8B** | Block-size curriculum learning for reasoning |
| Code generation | **DiffuCoder 7B** | Masked diffusion + coupled-GRPO for code |

## NBDiff-7B (Dec 2025, Huawei/Pangu)

**Paper**: arXiv 2512.06776
**Scale**: 7B dense (Pangu-Embedded-7B AR checkpoint)

Two key innovations:
1. **Context-causal masking**: block-causal attention (bidirectional within blocks, causal across blocks) — similar to Efficient-DLM but with cleaner formulation
2. **Block-growth**: training recipe that progressively grows block sizes during training, allowing the model to adapt to increasing parallelism

**Results**: SOTA 7B DLM on math and reasoning:
- GSM8K: 79.6% (Base), 83.8% (Instruct)
- MATH-500: 46.0% (Base)
- Outperforms Dream-7B, LLaDA-8B on reasoning benchmarks
- Maintains long-context modeling capabilities from AR base

**When to use**: Best 7B-scale DLM for math/reasoning. Alternative to DreamReasoner-8B (which uses block-size curriculum on Qwen3-8B).

## Additional open-source diffusion LLMs (not conversion-based)

### DreamReasoner-8B (June 2026, DreamLM)
- **Paper**: arXiv 2606.19257
- **GitHub**: DreamLM/DreamReasoner
- **Scale**: 8B dense (Qwen3-8B-Base)
- **Method**: Block-size curriculum learning (fine→coarse) for long-CoT reasoning
- **Key finding**: Large training block sizes HURT reasoning, small ones help. Curriculum from fine to coarse solves this.
- **Quality**: Comparable to Qwen3-8B-Thinking on math/code benchmarks

### DiffuCoder 7B (June 2025, Apple+HKU)
- **Paper**: arXiv 2506.20639
- **GitHub**: apple/ml-diffucoder
- **Scale**: 7B dense, masked diffusion for code
- **Innovation**: Coupled-GRPO (diffusion-native RL) — +4.4% on EvalPlus, reduces AR bias
- **HF**: apple/DiffuCoder-7B-Instruct, apple/DiffuCoder-7B-cpGRPO

### MMaDA 8B (May 2025, Princeton+ByteDance)
- **Paper**: arXiv 2505.15809
- **GitHub**: Gen-Verse/MMaDA
- **Scale**: 8B dense, unified multimodal diffusion
- **Capability**: Text reasoning + multimodal understanding + text-to-image generation
- **HF**: Gen-Verse/MMaDA-8B-Base, Gen-Verse/MMaDA-8B-MixCoT

### RND1 30B (Oct 2025, Radical Numerics)
- **Report**: radicalnumerics.ai/assets/rnd1_report.pdf
- **Scale**: 30B total / 3B active (MoE), AR→diffusion conversion
- **Note**: Largest open MoE diffusion LLM at time of release
