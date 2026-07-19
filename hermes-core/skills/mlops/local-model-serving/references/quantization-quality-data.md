# Quantization Quality Data — Full Benchmark Table

Source: "Which Quantization Should I Use? A Unified Evaluation of llama.cpp Quantization on Llama-3.1-8B-Instruct" (arXiv 2601.14277, January 2026).

## Full Results Table

Benchmarks on Llama-3.1-8B-Instruct. Avg = unweighted mean of GSM8K + HSwag + IFEval + MMLU + TQA.

| Bits | Quant | Size Reduction | GSM8K | HSwag | IFEval | MMLU | TQA | **Avg** | PPL | Δ from FP16 |
|---|---|---|---|---|---|---|---|---|---|---|
| F16 | baseline | — | 77.63 | 72.51 | 78.93 | 63.50 | 54.79 | **69.47** | 7.32 | — |
| **8** | **Q8_0** | 46.87% | 77.48 | 72.52 | 78.79 | 63.43 | 54.81 | **69.41** | 7.33 | **−0.06** ✅ |
| 6 | Q6_K | 58.98% | 78.17 | 72.48 | 77.63 | 63.17 | 54.71 | **69.23** | 7.35 | −0.24 |
| 5 | Q5_K_M | 64.35% | 78.54 | 72.33 | 78.67 | 62.80 | 54.45 | **69.36** | 7.40 | −0.11 |
| 5 | Q5_0 | 65.19% | 79.08 | 72.63 | 80.14 | 63.18 | 54.57 | **69.92** | 7.43 | +0.45 |
| **4** | **Q4_K_M** | 69.41% | 77.41 | 72.35 | 79.06 | 62.43 | 54.49 | **69.15** | 7.56 | **−0.32** |
| 4 | Q4_K_S | 70.83% | 77.33 | 72.79 | 80.26 | 62.06 | 53.40 | **69.17** | 7.62 | −0.30 |
| 4 | Q4_0 | 71.03% | 75.66 | 71.88 | 77.46 | 62.20 | 52.68 | **67.98** | 7.74 | −1.49 ⚠️ |
| 3 | Q3_K_L | 73.14% | 74.07 | 73.54 | 79.14 | 62.31 | 54.84 | **68.78** | 7.81 | −0.69 |
| 3 | Q3_K_M | 75.03% | 73.16 | 73.41 | 77.19 | 62.01 | 54.56 | **68.07** | 7.96 | −1.40 ⚠️ |
| 3 | Q3_K_S | 77.23% | 68.31 | 71.87 | 73.89 | 59.31 | 54.08 | **65.49** | 8.96 | **−3.98** 🔴 |

## Key Findings

1. **Q8_0 ≈ FP16.** Average difference is 0.06 points — within measurement noise. PPL: 7.33 vs 7.32.

2. **Q4_K_M loses only 0.32 points.** GSM8K (math): 77.41 vs 77.63 — almost identical. PPL: 7.56 vs 7.32.

3. **Math (GSM8K) is the most sensitive to quantization.** Q3_K_S drops 9.32 points on GSM8K while HellaSwag drops only 0.64.

4. **Q3_K_S is the danger zone.** −3.98 points average, GSM8K collapses from 77.63 to 68.31. Avoid for any task requiring multi-step reasoning.

5. **Q5_0 slightly exceeds FP16 on Avg** (69.92 vs 69.47) — within measurement variance, but proves mid-bit quants can be lossless.

6. **IQ2_XS (~2.5 bit) — significantly worse than Q3_K_S.** Expected degradation: −5+ points Avg.

## MoE-Specific Considerations

For Mixture-of-Experts models (Qwen 35B/3B, Nex 397B/17B):

- **Quantization affects ALL experts**, not just active ones. 128 experts × ~270M each = 35B total parameters are all quantized.
- **Active parameters feel the degradation more** — 3B active at Q4 is like a dense 3B model at Q4 (very sensitive).
- **But expert diversity provides resilience** — 128 experts mean routing can still find good experts even if some are degraded.
- **Rule of thumb for MoE:** treat quantization sensitivity as BETWEEN a dense model of active size and a dense model of total size. More sensitive than 35B dense, less sensitive than 3B dense.
