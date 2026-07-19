# Abliterated Model Selection Methodology

How to find the BEST abliterated/uncensored GGUF models for local serving.
Based on deep research across HF repos, abliteration benchmarks, and quantization quality data.

## Abliteration Methods (ranked by quality preservation)

| Method | KL Divergence | Refusals (of 100) | Verdict | Best for |
|--------|:-----------:|:-----------------:|---------|----------|
| **Heretic v1.2.0** | **0.0015** | 10 | 🥇 Excellent | Qwen3.6, Gemma — lowest capability loss |
| Huihui | ~0.003 | 15 | 🥈 Excellent | Nex, Llama — widely available |
| Obliteratus | ~0.006 | 20 | 🥉 Good | When combined with Supertune |
| Abliterix | ~0.010 | 25 | Good | Budget option |
| HauhauCS | ~0.010 | 25 | Good | Aggressive but higher KL |

**Source:** nathan.sapwell.net — "Qwen3.6-27B Abliteration Benchmarked: Five Techniques Under the Microscope"
and DreamFast/Qwen3.6-27B-Uncensored benchmark.

Heretic has 6.5× lower KL divergence than Abliterix/Abliterix-class methods.

## Quantization Methods for MoE Models

### APEX (Adaptive Precision for EXpert Models)
- **Repo:** `github.com/mudler/apex-quant` (LocalAI team)
- **Compatibility:** Stock llama.cpp — no patches needed
- **Technique:** Classifies every tensor by role (routed expert / shared expert / attention),
  applies layer-wise precision gradient. Edge layers get higher precision, redundant middle
  layers compressed more aggressively.
- **Benchmarks** (on Qwen3.5-35B-A3B, DGX Spark):

| Config | Size GB | PPL | HellaSwag | MMLU | ARC | KL mean | tg128 t/s |
|--------|---------|-----|-----------|------|-----|---------|-----------|
| F16 | 64.6 | 6.537 | 82.5% | 41.5% | 56.9% | — | 30.4 |
| Q8_0 | 34.4 | 6.533 | 83.0% | 41.2% | 57.9% | 0.0046 | 52.5 |
| **APEX I-Quality** | 21.3 | 6.552 | **83.5%** | **41.4%** | 57.9% | 0.0102 | **63.1** |
| APEX Quality | 21.3 | **6.527** | 83.0% | 41.2% | 56.2% | 0.0114 | 62.3 |
| APEX I-Balanced | 23.6 | 6.548 | 83.0% | 41.0% | 57.5% | 0.0078 | 61.4 |
| APEX I-Compact | 16.1 | 6.669 | 81.8% | 41.7% | 55.5% | 0.0332 | 69.8 |
| Unsloth UD-Q8_K_XL | 45.3 | 6.536 | 82.5% | 41.3% | 57.9% | 0.0025 | 36.4 |

**Source:** APEX Technical Report (paper/APEX_Technical_Report.pdf in apex-quant repo).

Key takeaways:
- **APEX I-Quality beats Q8_0** on HellaSwag (+0.5pp) and MMLU (+0.2pp) at 38% smaller size
- **APEX I-Quality is 20% faster** than Q8_0 (63.1 vs 52.5 t/s)
- I-variants use diverse imatrix (chat, code, reasoning, tool-calling) → better accuracy, lower KL
- For maximum accuracy: APEX I-Quality. For conservative KL: APEX I-Balanced.

### Standard GGUF Quants
- Q8_0: ~35 GB for 35B MoE — near-lossless, ~0.0046 KL divergence
- Q4_K_M: ~20 GB — 0.3% accuracy loss vs FP16
- IQ4_NL: ~18 GB — non-linear, best for CUDA (NOT Apple Metal)

## Per-Model Recommendations

### Nex-N2-mini (Coding Agent)
- **Abliterated:** Only huihui-ai available (no Heretic version yet)
- **Quantization:** NO Q8_0 abliterated exists. Options:
  - `SC117/Huihui-Nex-N2-mini-abliterated-APEX-GGUF` — APEX-Quality (~33 GB) ← BEST
  - `quant-mind/Huihui-Nex-N2-mini-abliterated-GGUF` — Q4_K_M / UD-Q4_K_XL
- **Warning:** Thinking mode (`<think>` tags) requires Nex's patched llama.cpp
  (nex-agi/llama.cpp). Stock llama.cpp works fine without thinking mode.
- **Size note:** Nex APEX-Quality is ~33 GB (not ~21 GB like Qwen) due to vision encoder
  and 256 experts (vs 128 in Qwen3.5 base).

### Qwen3.6-35B (Reasoning)
- **Abliterated:** Heretic v1.2.0 (llmfan46) — lowest KL divergence (0.0015)
- **Quantization:** Multiple APEX and standard options:
  - `SC117/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved-APEX-GGUF` — APEX I-Quality (~21 GB) ← BEST
  - `jorge-erdb/Qwen3.6-35B-A3B-uncensored-heretic-GGUF` — Q8_0 (~35 GB) if prefer standard
  - `mudler/Qwen3.6-35B-A3B-uncensored-heretic-APEX-GGUF` — alternative APEX source
- **MTP:** SC117 variant preserves Native MTP (Multi-Token Prediction) weights

### AgentWorld-35B (World Simulation)
- **Abliterated + Post-Trained:** Jiunsong/SuperQwen — Obliteratus false-refusal pass + Supertune
- **GGUF:** Only Q4_K_M available (no APEX, no Q8_0)
  - `Jiunsong/SuperQwen-AgentWorld-35B-A3B-abliterated-gguf-4bit`
- **Benchmark improvements over original:**
  - HumanEval+: 16.0 → 75.0 (+59)
  - MBPP+: 45.0 → 89.0 (+44)
  - MMLU-Pro: 50.0 → 64.0 (+14)
  - IFEval: 51.0 → 63.0 (+12)
  - GPQA Diamond: 32.0 → 42.0 (+10)
- **Comparison:** huihui-ai/Huihui-Qwen-AgentWorld is a "crude, proof-of-concept"
  abliteration with NO post-training. SuperQwen is strictly better.

## Research Workflow

When tasked with finding the best abliterated models:

1. **Search HF** for `{model_name} abliterated GGUF` variants
2. **Check files** via HF API: `curl -s "https://huggingface.co/api/models/{repo}?expand[]=siblings"`
3. **Verify abliteration method** — read model card for KL divergence data
4. **Compare quantization methods** — APEX > standard Q8_0 for MoE; standard Q8_0 > Q4_K_M otherwise
5. **Check model card for benchmark data** — especially for post-trained variants (SuperQwen)
6. **Verify stock llama.cpp compatibility** — APEX: yes, TQ/NVFP4: no
7. **Cross-reference download counts** as proxy for community validation

## Key Repos to Check First

| Model Type | Primary Source | Fallback |
|------------|---------------|----------|
| Abliterated GGUF (Heretic) | `SC117/` repos (APEX variants) | `jorge-erdb/`, `mudler/` |
| Abliterated GGUF (Huihui) | `quant-mind/` repos | `SC117/` for APEX |
| AgentWorld improved | `Jiunsong/SuperQwen-*` | `huihui-ai/Huihui-Qwen-AgentWorld-*` |
| Standard GGUF quants | `unsloth/` (UD variants) | `bartowski/` (imatrix) |
