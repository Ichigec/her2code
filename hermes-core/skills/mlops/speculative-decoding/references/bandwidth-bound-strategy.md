# Bandwidth-Bound Speculative Decoding Strategy

## Context

On memory-bandwidth-bound hardware (GB10/DGX Spark, Jetson, consumer GPUs with LPDDR/DDR), inference is limited by how fast weights can be loaded from RAM — NOT by compute. This fundamentally changes which speculative decoding strategy is optimal.

## Key Insight: Quantize the TARGET, Not the Draft

The bottleneck in speculative decoding is the **target model verification pass** — every cycle must load ALL target model weights. The draft model (especially DFlash at ~700MB-3.5GB) is negligible.

| Approach | Draft Time | Verify Time | Bottleneck? |
|---|---|---|---|
| Quantize draft (INT4) | Faster draft | UNCHANGED | Target still slow |
| Quantize target (INT4) | UNCHANGED | **4x faster verify** | Draft now negligible |

**Conclusion: Always quantize the target model first.** Draft quantization provides minimal benefit on bandwidth-bound hardware because the draft is already tiny relative to the target.

## GB10 Math (273 GB/s LPDDR5x unified memory)

```
35B MoE bf16 target:  70 GB → 256 ms/verify  → baseline 3.9 tok/s
35B MoE INT4 target: 17.5 GB →  64 ms/verify  → baseline 15.6 tok/s

DFlash draft (6 layers, 737MB):   2.7 ms/forward (all 16 tokens in parallel)
Full model INT4 draft (sequential): 64 ms/token × 8 tokens = 512 ms
```

### 5 Strategies Compared (35B MoE on GB10)

| # | Strategy | VRAM | tok/s | Quality | Notes |
|---|---|---|---|---|---|
| 1 | bf16 target + DFlash draft | 71 GB | ~19 | Lossless | Current setup (acceptance 25%) |
| 2 | **INT4 target + DFlash draft** | **18 GB** | **~75** | ~1-2% loss | **BEST overall** |
| 3 | bf16 target + INT4 draft (same arch) | 88 GB | ~9 | Lossless | Sequential drafting = slow |
| 4 | Self-speculative (early exit) | 70 GB | ~4 | Lossless | Layer-skip, sequential |
| 5 | INT4 target + INT4 DFlash draft | 18 GB | ~76 | ~1-2% loss | Marginally faster than #2 |

### Why Quantized Draft (Strategy 3) Underperforms

A quantized full-size model as draft has high acceptance (~75%) because it's the same architecture producing nearly identical logits. BUT:
- **Sequential generation**: 8 tokens × 64ms = 512ms of draft time
- **VRAM**: 70GB (bf16 target) + 17.5GB (INT4 draft) = 87.5GB simultaneously
- The draft phase takes **longer than the verify phase** (512ms vs 256ms)
- SGLang/vLLM don't support this configuration natively (STANDALONE algorithm exists in SGLang but expects EAGLE-style draft)

### Why INT4 Target + DFlash (Strategy 2) Wins

- DFlash generates 16 tokens in **parallel** (block diffusion, single forward): ~3ms
- INT4 target verifies in 64ms instead of 256ms
- Total VRAM: 18GB — massive headroom for KV cache, batching
- INT4 quality loss on 35B+ MoE: ~0.5-1% on benchmarks (negligible for uncensored/chat models)
- At 25% acceptance: ~30 tok/s realistic; at 40% acceptance: ~50 tok/s

## Research Context

- **ML-SpecQD** (arXiv:2503.13565, Mar 2025): Multi-level speculative decoding with MXFP4 quantized drafts. 2.72x speedup. Uses quantized model AS draft, recursively accelerates draft itself.
- **MoE-SpeQ** (arXiv:2511.14102, Nov 2025): Quantized draft + expert offloading for MoE. Exploits architectural alignment between quantized draft and full-precision target.
- **Self-speculative decoding** (arXiv:2309.08168): Layer-skip + early-exit. No separate draft model. Works but lower speedup on bandwidth-bound hardware.
- **LayerSkip** (arXiv:2404.16710): Early-exit inference + self-speculative. Trains early layers to predict tokens.

## SGLang Quantized Draft Support

SGLang supports quantized draft models via:
```bash
--speculative-draft-model-quantization awq  # or gptq, fp8, etc.
```
Default: draft uses same quantization as target. Use `unquant` to force bf16 draft on quantized target.

Supported spec algorithms in SGLang: EAGLE, EAGLE3, NEXTN, STANDALONE (classic separate draft model), NGRAM, DFLASH.

## MoE Parameter Budget: Why Quantization Is Binary for MoE

For MoE models (Qwen3.5/3.6-35B-A3B, Agents-A1), the parameter breakdown shows that **experts ARE the model** — everything else is noise:

| Component | Params (35B MoE) | % of total | BF16 | FP8 dyn | INT4 (APEX) |
|---|---|---|---|---|---|
| **MoE routed experts** (256 per layer x 40 layers) | ~31.5B | **90%** | 63 GB | 31.5 GB | 16 GB |
| Full attention (10 layers) | ~0.8B | 2% | 1.6 GB | 0.8 GB | 0.5 GB |
| Linear attention (30 layers) | ~0.5B | 1% | 1.0 GB | 0.5 GB | 0.3 GB |
| Embeddings + LM head | ~1.0B | 3% | 2.0 GB | 1.0 GB | 0.5 GB |
| Shared expert + MTP head | ~0.6B | 2% | 1.2 GB | 0.6 GB | 0.4 GB |

**Key consequence**: "unquantized experts" or "quantize only attention" saves <2 GB. The choice for MoE is effectively:
- **BF16** (all-unquantized): ~66 GB
- **FP8 dynamic** (experts + attention quantized): ~36 GB
- **INT4/Q5 GGUF** (everything quantized): ~22 GB

There is no meaningful middle ground. If the user asks for "APEX without expert quantization" on an MoE model, the result is ~60-65 GB — same as BF16 — and provides no benefit over BF16 via SGLang.

### FP8 Dynamic: The GB10 Sweet Spot for MoE

FP8 dynamic quantization (via compressed-tensors/SensorRecipe) is the optimal target quantization on GB10 for DFlash deployment:

| Criterion | BF16 | **FP8 dyn** | INT4/Q5 GGUF |
|---|---|---|---|
| Size (35B MoE) | 66 GB | **36 GB** | 22 GB |
| Quality loss | 0% | **<0.5%** | 2-5% |
| DFlash compatible? | SGLang only | **SGLang only** | NO (llama.cpp MoE = 0 speedup) |
| Fits w/ Hermes stack? | TIGHT (~95/121 GB, OOM risk) | **YES (~60/121 GB, 60 GB headroom)** | YES w/ other models |
| Can run nex/world alongside? | NO | **YES** | YES |

FP8 recipe (from agents-a1-fp8/recipe.yaml) — what stays BF16 vs FP8:
- **FP8**: routed MoE experts, full_attention layers (the bulk of params)
- **BF16 (preserved)**: lm_head, vision encoder, router/gate (mlp.gate), embed_tokens, shared_expert, shared_expert_gate, linear_attn
- This split is optimal: precision-critical routing/embedding stays full precision; the 90% bulk gets FP8

### DFlash Deployment Matrix for MoE on GB10

| Target Quant | Size | Engine | DFlash? | Est. tok/s | Headroom |
|---|---|---|---|---|---|
| BF16 | 66 GB | SGLang | YES | 8-12 | ~26 GB (tight) |
| **FP8 dyn** | **36 GB** | **SGLang** | **YES** | **15-25** | **~60 GB (safe)** |
| INT4 GGUF | 22 GB | llama.cpp | **NO** (MoE spec = 0 gain) | 5-8 | ample |

## Decision Framework

```
Is hardware bandwidth-bound (GB10, Jetson, consumer GPU)?
├── YES → Quantize TARGET. Use DFlash/EAGLE3 draft at bf16.
│         Draft size is irrelevant (700MB DFlash << target).
│         │
│         ├── Need DFlash speculative decoding?
│         │   ├── YES → Use FP8 dynamic target via SGLang (36 GB for 35B MoE).
│         │   │         Near-lossless (<0.5%), 60 GB headroom on GB10.
│         │   │         INT4 GGUF has NO DFlash (llama.cpp MoE = 0 speedup).
│         │   └── NO (just fast inference, no spec decode)
│         │       └── INT4 GGUF via llama.cpp is fine (22 GB, 5-8 tok/s).
│         │
│         └── BF16 only if memory is guaranteed safe (<95 GB total on GB10,
│             stop Hermes Desktop + Docker first). Risky.
│
└── NO (H100, B200, datacenter GPU with HBM)
    ├── Compute-bound → Draft generation IS the bottleneck → quantize draft helps
    └── Large VRAM budget → can afford bf16 target + separate quantized draft
```
