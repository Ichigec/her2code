# APEX Quantization Benchmarks

Full benchmark data from the APEX Technical Report. All measurements on Qwen3.5-35B-A3B, NVIDIA DGX Spark (GB10, 122 GB VRAM). Perplexity on wikitext-2-raw, context 2048. Accuracy via llama.cpp, 400 tasks.

Source: https://github.com/mudler/apex-quant

## Core Metrics

| Configuration | Size (GB) | Perplexity | KL mean | KL max | HS | WG | MMLU | ARC | TQA | tg128 (t/s) |
|---------------|-----------|-----------|---------|--------|------|------|------|------|------|-------------|
| F16 | 64.6 | 6.537 | -- | -- | 82.5% | 74.5% | 41.5% | 56.9% | 37.2% | 30.4 |
| Q8_0 | 34.4 | 6.533 | 0.0046 | 14.71 | 83.0% | 75.3% | 41.2% | 57.9% | 37.7% | 52.5 |
| **APEX Quality** | **21.3** | **6.527** | **0.0114** | **5.85** | **83.0%** | **74.5%** | **41.2%** | **56.2%** | **37.7%** | **62.3** |
| **APEX I-Quality** | **21.3** | **6.552** | **0.0102** | **5.59** | **83.5%** | **74.5%** | **41.4%** | **57.9%** | **38.4%** | **63.1** |
| APEX Balanced | 23.6 | 6.533 | 0.0088 | 6.03 | 83.0% | 74.5% | 41.3% | 56.9% | 36.8% | 60.8 |
| APEX I-Balanced | 23.6 | 6.548 | 0.0078 | 5.77 | 83.0% | 73.3% | 41.0% | 57.5% | 37.5% | 61.4 |
| APEX Compact | 16.1 | 6.783 | 0.0469 | 7.56 | 82.5% | 73.3% | 40.9% | 55.2% | 36.5% | 69.8 |
| APEX I-Compact | 16.1 | 6.669 | 0.0332 | 5.50 | 81.8% | 75.0% | 41.7% | 55.5% | 37.9% | 69.8 |
| APEX Mini | 12.2 | 7.088 | 0.0870 | 5.57 | 81.0% | 75.5% | 41.3% | 57.2% | 36.7% | 74.4 |
| Unsloth UD-Q8_K_XL | 45.3 | 6.536 | 0.0025 | 4.36 | 82.5% | 74.8% | 41.3% | 57.9% | 38.1% | 36.4 |
| Unsloth UD-Q4_K_XL | 20.7 | 6.554 | 0.0097 | 3.14 | 83.0% | 73.5% | 40.6% | 56.2% | 37.5% | 58.1 |
| bartowski IQ2_M | 11.3 | 7.303 | 0.1113 | 6.07 | 80.3% | 74.0% | 39.6% | 56.2% | 35.0% | 76.2 |

## Tier Recommendations

| Tier | Variant | Size | Best for |
|------|---------|------|----------|
| Maximum accuracy | APEX I-Quality | 21.3 GB | Reasoning, coding — beats Q8_0 on accuracy |
| Conservative | APEX I-Balanced | 23.6 GB | Lowest KL divergence, best perplexity |
| Balanced | APEX Quality | 21.3 GB | Lowest perplexity, ties Q8_0 on accuracy |
| Efficiency | APEX I-Compact | 16.1 GB | Consumer GPUs, surprisingly competitive |
| Minimal | APEX Mini | 12.2 GB | 16 GB VRAM, beats IQ2_M on all metrics |

## Compatibility

- **Stock llama.cpp** — no patches, no custom builds. Works with any llama.cpp build that supports the model architecture.
- **I-variants** use diverse imatrix: chat, code, reasoning, tool-calling (no Wikipedia). Better accuracy, slightly higher perplexity.
- **Non-I variants** use standard imatrix. Better perplexity, slightly lower accuracy on reasoning benchmarks.

## Key APEX Repos on HuggingFace

- `SC117/*-APEX-GGUF` — abliterated models with APEX (Nex, Qwen3.6, etc.)
- `mudler/*-APEX-GGUF` — original (non-abliterated) models with APEX
- I-variant availability varies by repo — always check via API.
