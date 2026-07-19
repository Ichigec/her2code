# Memory-Efficient Training Methods for 35B+ Models on DGX Spark

**Date:** 2026-07-11
**Hardware:** NVIDIA DGX Spark (GB10 Grace Blackwell), 128GB unified LPDDR5x, aarch64, CUDA 13, sm_121
**Target Model:** Qwen3.5-35B-A3B (MoE, 35B total params, 3B active, 256 experts, 40 layers)

## Memory Formulas (bytes per parameter)

| Method | Formula | bytes/param | 35B Memory | Fits 128GB? |
|--------|---------|:-----------:|:----------:|:-----------:|
| Standard AdamW (mixed precision) | wts(2)+grads(2)+m(4)+v(4) | 12 | 420 GB | ❌ |
| 8-bit Adam (bitsandbytes) | wts(2)+grads(2)+m_int8(1)+v_int8(1) | 6 | 196 GB | ❌ |
| Adafactor | wts(2)+grads(2)+factored(~0.5) | 4-4.5 | 147 GB | ❌ (borderline) |
| GaLore (realistic for qwen35moe) | wts(2)+grads(2)+low_rank(~3.5) | ~7.5 | 245 GB | ❌ |
| Q-GaLore (INT4) | int4_wts(0.5)+grads(2)+proj(~1) | ~3.4 | 119 GB | ⚠️ borderline |
| LOMO | wts(2)+m_fp32(4)+v_fp32(4) | ~10 | 326 GB | ❌ |
| **BAdam (block-wise, D=40)** | wts(2)+active_block(~0.4) | **~2.4** | **84 GB** | **✅** |
| LoRA (BF16 base) | wts(2)+adapter(~0.05)+optim(~0.05) | ~2.1 | 74 GB | ✅ |
| QLoRA (4-bit base) | wts_4bit(0.5)+adapter(0.05)+optim(0.05) | ~0.6 | 20 GB | ✅ |

## BAdam (Block-wise Adam) — RECOMMENDED for 35B Full FT

- **Paper:** arXiv:2404.02827, NeurIPS 2024
- **Repo:** https://github.com/Ledzy/BAdam
- **Memory:** `2M + 16M/D` GB (M=params in B, D=num blocks). For 35B/40 layers: 70 + 14 = 84 GB
- **How it works:** Processes optimizer blocks one at a time (layer-level). Only the active block's gradients and optimizer states are in memory.
- **Compatibility:** Pure PyTorch, NO custom CUDA kernels → best sm_121/aarch64 compatibility
- **Speed:** ~40× slower than standard AdamW (40 forward/backward per step). 25K×3ep ≈ 5-8 days for 35B.
- **MoE:** Layer-level blocks work for any architecture (architecture-agnostic)
- **Risk:** Not tested on MoE in original paper, but layer-level partitioning is architecture-agnostic

### BAdam Configuration for Qwen3.5-35B-A3B

```python
from badam import BlockOptimizer
import torch

# Qwen3.5 weights are under model.language_model.layers.* (multimodal!)
block_prefixes = [f"model.language_model.layers.{i}." for i in range(40)]

base_optimizer = torch.optim.AdamW(
    [p for p in model.parameters() if p.requires_grad],
    lr=2e-5,
)

optimizer = BlockOptimizer(
    base_optimizer=base_optimizer,
    model=model,
    block_prefix_list=block_prefixes,
    switch_block_every=50,      # update block every 50 steps
    switch_mode="random",       # random block order
    num_kept_backward=3,        # keep gradients for 3 blocks simultaneously
)
```

## GaLore — NOT RECOMMENDED for qwen35moe

- **Paper:** arXiv:2403.03507, ICML 2024 Oral
- **Critical finding:** Qwen3.5's small weight matrices (hidden_size=2048, moe_intermediate_size=512) give only **37.5% gradient compression** vs 91.5% on LLaMA-7B dense models
- GaLore's low-rank projection is ineffective when weight matrices are already small
- Q-GaLore (INT4 variant) at ~119GB is borderline but same MoE concerns

## LOMO — NOT RECOMMENDED

- **Paper:** arXiv:2306.09782
- Memory too high (326 GB for 35B)
- Hook-based gradient fusion conflicts with MoE autograd

## aarch64 / CUDA 13 / sm_121 Compatibility Matrix

| Method | Pure Python? | CUDA kernels? | sm_121 risk | Notes |
|--------|:---:|:---:|:---:|---|
| BAdam | ✅ | None | None | Only needs PyTorch ≥ 2.7 |
| GaLore | ✅ | None | None | Only needs PyTorch |
| Q-GaLore | ❌ | INT4 via bitsandbytes | HIGH | Needs bitsandbytes |
| LOMO | ✅ | None | None | Only needs PyTorch |
| 8-bit Adam | ❌ | Yes (C++/CUDA) | HIGH | Needs sm_121 arch flags |
| Adafactor | ✅ | None | None | Built into PyTorch |
| QLoRA | ❌ | NF4 via bitsandbytes | HIGH | Same as 8-bit Adam |

**Key insight:** BAdam has BETTER compatibility on DGX Spark than QLoRA, because bitsandbytes needs custom CUDA kernels compiled for sm_121 while BAdam is pure PyTorch.

## Qwen3.5-35B-A3B Architecture Breakdown

| Component | Params |
|-----------|--------|
| Embedding (vocab 248,320 × hidden 2048) | 508M |
| LM Head | 508M |
| Full Attention layers (10× ~23M) | 231M |
| DeltaNet/Linear Attention layers (30× ~2M) | 60M |
| Expert FFNs (40 layers × 256 experts × 3.15M) | 32.2B |
| Shared Experts (40× 3.15M) | 126M |
| Routers (40× 0.52M) | 21M |
| **TOTAL** | **~33.7B** |

**Key:** hidden_size=2048 and moe_intermediate_size=512 are unusually small. This makes GaLore ineffective (only 37.5% compression).

## Maximum BF16 Model Size by Method

| Method | Max BF16 Model | Key Constraint |
|--------|:---:|---|
| Standard AdamW | ~8B | 12 bytes/param |
| 8-bit Adam | ~15B | 6 bytes/param, bitsandbytes risk |
| Adafactor | ~22B | 4.5 bytes/param, borderline |
| **BAdam** | **~45B** | 2.4 bytes/param |
| LoRA (BF16) | ~50B | 2.1 bytes/param, base frozen |
| QLoRA | ~100B+ | 0.6 bytes/param |

## Sources

- BAdam paper: https://arxiv.org/abs/2404.02827
- BAdam repo: https://github.com/Ledzy/BAdam
- GaLore paper: https://arxiv.org/abs/2403.03507
- LOMO paper: https://arxiv.org/abs/2306.09782
- Qwen3.5 config: HuggingFace API `/api/models/Qwen/Qwen3.5-35B-A3B`
