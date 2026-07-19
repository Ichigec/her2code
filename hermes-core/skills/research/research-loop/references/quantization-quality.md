# Quantization Quality in Model Comparisons

When comparing models for local deployment, quantization level is a FIRST-CLASS variable — not a footnote. Use these rules:

## Data source
"Which Quantization Should I Use?" — arXiv 2601.14277 (January 2026). Full table in `local-model-serving` → `references/quantization-quality-data.md`.

## Quick reference for model comparisons

| Quant | Quality vs FP16 | Safe for coding? |
|-------|----------------|-----------------|
| Q8_0 | ≈100% (Δ −0.06) | ✅ Gold standard |
| Q4_K_M | ≈99.5% (Δ −0.32) | ✅ Sweet spot |
| Q3_K_L | ≈99% (Δ −0.69) | ⚠️ Noticeable on math |
| Q3_K_M | ≈98% (Δ −1.40) | ⚠️ Avoid for agents |
| IQ2_XS | ≈93% (estimated) | 🔴 Never |

## Critical rule
**Big model + bad quant < smaller model + good quant.** A 397B model in IQ2_XS (~2.5 bit) is worse than a 35B model in Q8_0. The parameter-count advantage is destroyed by extreme quantization.

## MoE sensitivity
MoE models (35B total / 3B active) are slightly more sensitive to quantization than dense models of the same active size — quantization compresses ALL experts, not just active ones.

## APEX-Quant (MoE-adaptive quantization)

For MoE models specifically, **APEX-Quant** (`localai-org/apex-quant`) assigns different precision per tensor type, exploiting the 97% sparsity of routed experts. On Qwen3.5-35B-A3B:

| Tier | Size | PPL | HellaSwag | vs FP16 |
|------|------|-----|-----------|---------|
| APEX I-Quality | 21.3 GB | 6.552 | **83.5%** | Beats FP16 on HellaSwag/ARC/TruthfulQA at 1/3 size |
| APEX Balanced | 23.6 GB | 6.533 | 83.0% | Near-lossless, 63% smaller than FP16 |
| APEX Mini | 12.2 GB | 7.088 | 81.0% | Fits 16 GB consumer GPUs |

Every APEX tier beats uniform quantization (Q8_0, Q4_K_M, Q3_K_M) at equivalent sizes. 30+ pre-quantized models on HuggingFace from `mudler`. Full deep dive: `references/apex-quant-deep-dive.md`.
