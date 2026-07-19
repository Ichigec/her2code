# APEX-Quant: MoE Adaptive Quantization — Deep Dive

**Research date:** 2026-07-17  
**Sources:** GitHub (localai-org/apex-quant), ACL 2025 paper (arXiv 2411.02355), HuggingFace, presenc.ai, bric.pe.kr, NVIDIA Forums

---

## Two Meanings of "APEX" in Quantization Context

| Term | What | Use |
|------|------|-----|
| **NVIDIA APEX (AMP)** | FP16 mixed-precision training library. O1/O2 levels match FP32 accuracy via whitelist/blacklist + dynamic loss scaling. Deprecated → `torch.cuda.amp`. | Training |
| **APEX-Quant** (`localai-org/apex-quant`) | Adaptive per-layer quantization for MoE inference on llama.cpp. Different precision per tensor type. 5 quality tiers. 30+ pre-quantized models on HF. | Inference |

---

## Why APEX-Quant Works (MoE-Specific)

MoE models have structural sparsity: 97% of routed expert weights are INACTIVE on any given token (8/256 experts active). APEX exploits this:

```
Routed Expert weights (gate/up/down): 97% inactive → aggressive quant (Q4_K, IQ4_XS, IQ2_S)
Shared Expert weights: always active, heavy-tailed (kurtosis 13.10) → Q8_0 minimum
Attention/SSM weights: few params, quality-critical → Q6_K uniform
Edge layers (first/last ~5): most sensitive → Q6_K
Middle layers: redundant → aggressive compression
```

Runs on stock llama.cpp — no patches, uses `--tensor-type-file` + `--tensor-type`.

---

## Accuracy: APEX vs FP16 on Qwen3.5-35B-A3B (64.6 GB FP16)

| Metric | FP16 | APEX I-Quality | APEX Balanced | APEX Mini | Q8_0 uniform |
|--------|------|:--------------:|:------------:|:---------:|:------------:|
| Size | 64.6 GB | **21.3 GB** (−67%) | 23.6 GB (−63%) | **12.2 GB** (−81%) | 37.0 GB |
| Perplexity ↓ | 6.537 | 6.552 | 6.533 | 7.088 | 6.533 |
| HellaSwag ↑ | 82.5% | **83.5%** (+1.0) | 83.0% | 81.0% | 83.0% |
| MMLU ↑ | 41.5% | 41.4% | 41.3% | 41.3% | — |
| ARC-Challenge ↑ | 56.9% | **57.9%** (+1.0) | — | 57.2% | — |
| TruthfulQA ↑ | 37.2% | **38.4%** (+1.2) | — | 36.7% | — |
| tok/s (tg128) | 30.4 | **63.1** (+108%) | 60.8 | **74.4** (+145%) | — |

**Headline:** APEX I-Quality beats FP16 on HellaSwag, ARC, and TruthfulQA at 1/3 the size. Improvement comes from quantization acting as regularization — noise suppression in inactive experts.

---

## 5 Quality Tiers

| Tier | Size | PPL | HellaSwag | MMLU | tok/s | Best For |
|------|------|-----|-----------|------|-------|----------|
| I-Quality | 21.3 GB | 6.552 | 83.5% | 41.4% | 63 | Max quality, beats FP16 on some benchmarks |
| Quality | 21.3 GB | **6.527** | 83.0% | 41.2% | 62 | Lowest perplexity of any quant |
| I-Balanced | 23.6 GB | 6.548 | 83.0% | 41.0% | 61 | Best all-rounder, lower KL divergence |
| Balanced | 23.6 GB | 6.533 | 83.0% | 41.3% | 61 | Interactive use, serving |
| I-Compact | 16.1 GB | 6.669 | 81.8% | 41.7% | 70 | 16 GB GPUs |
| Compact | 16.1 GB | 6.783 | 82.5% | 40.9% | 70 | 24 GB GPUs |
| Mini | **12.2 GB** | 7.088 | 81.0% | 41.3% | **74** | 16 GB consumer GPUs |

---

## APEX vs Uniform Quantization (Same Size)

| Comparison | Size | PPL | HellaSwag | Winner |
|------------|:----:|:---:|:---------:|--------|
| APEX Quality vs Q8_0 | 21.3 vs 37.0 GB | 6.527 vs 6.533 | 83.0% vs 83.0% | **APEX** (38% smaller!) |
| APEX I-Quality vs Q4_K_M | 21.3 vs 21.0 GB | 6.552 vs ~6.62 | 83.5% vs ~81% | **APEX I-Quality** |
| APEX Mini vs IQ2_M | 12.2 vs 12.5 GB | 7.088 vs ~8.5 | 81.0% vs ~75% | **APEX Mini (decisive)** |

---

## General Quantization Science (ACL 2025: arXiv 2411.02355)

500K+ evaluations, Llama-3.1 (8B/70B/405B) + DeepSeek-R1-Distill.

| Format | 8B | 70B | 405B | Verdict |
|--------|:--:|:---:|:----:|---------|
| W8A8-FP (FP8) | 99.3% | 99.7% | 100.1% | ✅ Lossless |
| W8A8-INT (INT8) | 100.3% | 99.9% | 99.3% | ✅ ~1-3% degradation |
| W4A16-INT (INT4) | 98.7% | 99.5% | 99.98% | ✅ Surprisingly good |

Key findings:
- FP8 is effectively lossless — simple round-to-nearest, no calibration data
- INT4 weight-only rivals 8-bit — refutes prior claims of 10-point drops
- Larger models MORE robust to quantization
- GPTQ > AWQ by ~2.9 points (8B), ~0.8 points (70B)
- Text similarity: BERTScore ≥0.92, STS ≥0.95 for all quantization levels (strong semantic preservation)

---

## GGUF Quantization Impact (Cross-Model)

| Quant | Bits | Δ PPL | Δ GSM8K | Quality vs FP16 |
|-------|:----:|:-----:|:-------:|-----------------|
| Q8_0 | 8.0 | +0.0–0.2% | ~0% | ≈100% Gold standard |
| Q6_K | 6.5 | +0.3–0.6% | ~0% | ≈99.5% |
| Q5_K_M | 5.5 | +0.9–1.2% | −0.5% | ≈99% |
| Q4_K_M | 4.5 | +1.5–1.9% | −1.5% | ≈98.5% Sweet spot |
| AWQ 4-bit | 4.0 | +1.2–1.7% | −1.3% | ≈98.5% |
| Q3_K_M | 3.5 | +3.8–5.0% | −5% | ≈95% Risky for agents |
| Q2_K | 2.5 | +11–14% | −14% | ≈86% Never |

MoE-specific: more sensitive than dense models at same active size. Q4_K_M or higher for MoE; Q3 is risky. Multilingual degrades faster (~2-3% at Q4_K_M vs ~1.5% English).

---

## Model-Specific Quantization Availability

All models below share Qwen3.5/3.6-35B-A3B MoE architecture → same quantization patterns.

| Model | GGUF Available | APEX-Quant | Quantized Benchmarks |
|-------|:--------------:|:----------:|:--------------------:|
| qwen3.6-35b | ✅ Full suite | ✅ Primary benchmark model | ✅ MMLU-Pro, AIME, GPQA at Unsloth |
| n2-nex-min | ✅ 5+ repos (Q8_0, Q4_K_M, IQ) | ❌ Not yet | ❌ None published |
| agents-a1 | ✅ Q4_K_M, F16, FP8 | ✅ Listed on HF | ❌ Model ~3 weeks old |
| superqwen | ✅ Q8_0, Q4_K_XL | ❌ Not yet | ❌ None published; abliteration may alter sensitivity |

---

## Key Sources

- APEX-Quant GitHub: https://github.com/localai-org/apex-quant
- APEX-Quant models (mudler): https://huggingface.co/mudler
- "Give Me BF16 or Give Me Death" (ACL 2025): https://arxiv.org/abs/2411.02355
- LLM Quantization Impact Leaderboard 2026: https://awesomeagents.ai/leaderboards/llm-quantization-impact-leaderboard/
- NVIDIA Forums PTQ thread: https://forums.developer.nvidia.com/t/optimizing-llms-for-performance-and-accuracy-with-post-training-quantization/340981
- Presenc AI benchmarks: https://presenc.ai/research
- bric.pe.kr GGUF showdown + Qwen3.6 VRAM tables
- Unsloth Qwen3.6 quantization docs: https://unsloth.ai
