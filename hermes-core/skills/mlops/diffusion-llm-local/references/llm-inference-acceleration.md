# LLM Inference Acceleration — Complete Taxonomy (July 2026)

Covers ALL major methods for speeding up LLM inference, from training-free quick wins to architectural conversion. Relevant to both AR and diffusion LLMs.

## A. Algorithmic (no retraining)

### Speculative decoding

| Method | Speedup | Quality | Training | How |
|:-------|:--------|:--------|:---------|:----|
| EAGLE-3 | 2-6.5× | Lossless | Yes (draft head) | Hidden states → lightweight draft model, multi-layer fusion |
| Medusa | 2-3× | Lossless | Yes (multi-head) | Multiple prediction heads on hidden states |
| MTP (native) | 1.5-2× | Lossless | Built into model | Qwen3.5/3.6, DeepSeek-V3 have MTP in weights |
| FastMTP | 2.03× | Lossless | Yes (self-distill) | Post-hoc MTP head training, shared positional weights |
| N-gram | 1.2-1.5× | Lossless | No | Lookup by n-gram matching |
| Prompt-lookup | 1.3-1.8× | Lossless | No | Match against prompt text |
| Self-speculation (Nemotron) | 1.75-4× | ~99.9% | Built into model | Diffusion drafts → AR verifies, same checkpoint |

**EAGLE-3 is the production king (2026)**: up to 6.5× on reasoning models, uses target model's hidden states, natively supported in vLLM/SGLang/TensorRT-LLM.

### KV cache optimization

- **PagedAttention** (vLLM): virtual memory for KV cache, eliminates fragmentation
- **RadixAttention** (SGLang): prefix tree for KV cache reuse
- **Prefix caching**: cache common prompt prefixes across requests
- **KV cache quantization**: FP8/NVFP4/TurboQuant, 4-6× compression, near-zero quality loss
- **KV eviction / token pruning**: drop low-attention KV entries
- **MLA** (Multi-head Latent Attention, DeepSeek): compresses KV cache into latent space

### Chunked prefill / disaggregated inference

- **SARATHI**: piggyback decodes with chunked prefills
- **DistServe / Mooncake**: split prefill and decode to different GPU pools
- **Continuous batching**: dynamic batch composition per token step

### Parallel speculative decoding

- **P-EAGLE / Saguaro**: parallelize speculation and verification (normally sequential)

## B. Architectural (requires training/conversion)

### MTP head training (post-hoc)

**FastMTP** (ICLR 2026, Tencent):
1. Generate self-distilled data (model teaches itself)
2. Train shared MTP head: recursive operation, shared positional weights, language-aware dynamic vocab compression
3. Result: 2.03× speedup (82% better than vanilla MTP)

**MTP-D** (Self-Distillation):
- Main head = teacher (detached), MTP heads = students
- +7.5% acceptance rate improvement
- Minimal additional training cost

### EAGLE-3 draft head training

Train a lightweight Llama-style draft model that uses target model's hidden states. Minimizes KL divergence against target logits. Training-time test + multi-layer fusion.

```bash
# vLLM with EAGLE-3
vllm serve model \
  --speculative-model eagle3 \
  --num-speculative-tokens 4
```

### MTP grafting (copy from base model)

For models based on Qwen3.5/3.6 (which have native MTP): copy 15 MTP tensors from base checkpoint.

```python
mtp_keys = [k for k in base.state_dict() if 'mtp' in k.lower()]
for key in mtp_keys:
    target.state_dict()[key] = base.state_dict()[key].clone()
```

**Caveat**: SFT/abliteration shifts activation space → MTP acceptance drops. See obliteratus skill for details.

### Diffusion conversion

See `references/ar-to-diffusion-conversion.md`. I-DLM (LoRA, 4.5B tokens) is the cheapest high-quality path.

### Hybrid AR+Diffusion (Nemotron tri-mode)

One checkpoint, switch attention pattern at inference time. See `references/ar-to-diffusion-conversion.md` § Nemotron-Labs-Diffusion.

## C. Quantization

- **Weight**: INT4 (AWQ, GPTQ), NVFP4 (Blackwell), ROCmFP4 (AMD)
- **KV cache**: FP8, INT4, TurboQuant (4-6× compression)
- **Activation**: FP8, FP4 (Blackwell)

## D. System-level

- Tensor Parallelism (TP), Pipeline Parallelism (PP), Expert Parallelism (EP for MoE)
- CUDA graphs, FlashAttention-3 / FlexAttention
- Async scheduling (vLLM MRV2: `VLLM_USE_V2_MODEL_RUNNER=1`)

## Recommended stack for maximum speedup

Combine multiple orthogonal methods:

```
Base model (AR)
├── EAGLE-3 speculative decoding (2-3×, lossless)
├── KV cache FP8 quantization (4-6× cache compression)
├── Chunked prefill (better TTFT)
└── Weight quantization (INT4/NVFP4, 2-4× VRAM reduction)

Combined: ~3-4× effective speedup, all lossless
```

For diffusion LLMs, additionally:
- Fast-dLLM KV-cache (up to 27.6×)
- Optimus elastic decoding (up to 3.2×)
- Nemotron self-speculation mode (1.75-4×)

## MTP support by framework (July 2026)

| Framework | MTP | EAGLE-3 | N-gram |
|:----------|:----|:--------|:-------|
| vLLM | ✅ Qwen3.5/3.6, DeepSeek-V3 | ✅ | ✅ |
| SGLang | ✅ Qwen3-Next, DeepSeek | ✅ | ✅ |
| llama.cpp | ✅ Qwen3.6 (PR #22673, merged May 2026) | ❌ | ✅ |
| LM Studio | ✅ UI support | ❌ | ❌ |
