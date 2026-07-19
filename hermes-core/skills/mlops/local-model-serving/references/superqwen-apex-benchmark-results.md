# SuperQwen-AgentWorld APEX Benchmark Results

Measured July 2026 on DGX Spark (GB10, 121 GB unified RAM, CUDA 13.0).
Model: Jiunsong/SuperQwen-AgentWorld-35B-A3B-abliterated (Qwen3_5MoeForConditionalGeneration, 40 layers, 256 experts, 8 active).

## PPL (wikitext-2-raw, ctx=2048)

| Model | Size | PPL | ± | Δ vs Q8_0 |
|-------|------|-----|---|-----------|
| Q8_0 (reference) | 35 GB | 5.8366 | ±0.036 | — |
| APEX v1 (code+tools+math corpus) | 22 GB | 5.8682 | ±0.036 | +0.032 |
| APEX v3 (FC+chat+code+tools+math corpus) | 22 GB | 5.8697 | ±0.036 | +0.033 |
| Q4_K_M | 20 GB | 5.9589 | ±0.036 | +0.122 |

v1 vs v3: Δ=0.0015 — 24× below measurement error. Statistically identical.

## Downstream Benchmarks (eval.sh, 400 tasks each)

| Metric | APEX v1 | APEX v3 | Δ | 95% CI (400 tasks) |
|--------|---------|---------|---|---------------------|
| HellaSwag | 82.75% | 82.50% | -0.25% | ±2.5% |
| Winogrande | 75.50% | 75.50% | 0% | ±2.5% |
| MMLU | 42.38% | 41.93% | -0.45% | ±2.5% |
| ARC-Challenge | 54.52% | 53.85% | -0.67% | ±2.5% |
| tg128 (t/s) | 38.54 | 40.16 | +4.2% | — |

All differences within statistical noise.

## Comparison with APEX Reference (Qwen3.5-35B-A3B base, not AgentWorld)

From APEX README, same hardware:

| Metric | APEX I-Q (Qwen3.5 base) | Our APEX v3 (SuperQwen) | Note |
|--------|------------------------|------------------------|------|
| PPL (ctx=2048) | 6.552 | 5.870 | Better (supertune effect) |
| HellaSwag | 83.5% | 82.5% | -1.0% (abliteration) |
| Winogrande | 74.5% | 75.5% | +1.0% |
| MMLU | 41.4% | 41.9% | +0.5% |
| ARC | 57.9% | 53.8% | -4.1% |

## SuperQwen Model Card Benchmarks (BF16, from Jiunsong's HF README)

SuperQwen vs original Qwen-AgentWorld (post-training: abliteration + supertune):

| Benchmark | Qwen-AgentWorld (original) | SuperQwen (abliterated+supertuned) | Δ |
|-----------|:-------------------------:|:----------------------------------:|:---:|
| HumanEval+ | 16.0% | 75.0% | +59.0 |
| MBPP+ | 45.0% | 89.0% | +44.0 |
| MMLU-Pro | 50.0% | 64.0% | +14.0 |
| IFEval | 51.0% | 63.0% | +12.0 |
| GPQA Diamond | 32.0% | 42.0% | +10.0 |
| Overall public top-5 500 | 38.8 | 66.6 | +27.8 |

## Qwen-AgentWorld AgentWorldBench (7 domains, 0-100 scale)

From Qwen's HF README. Five-dimensional rubric (Format, Factuality, Consistency, Realism, Quality):

| Model | MCP | Search | Term. | SWE | Android | Web | OS | Overall |
|-------|:---:|:------:|:-----:|:---:|:-------:|:---:|:--:|:-------:|
| GPT-5.4 | 70.1 | 37.3 | 53.7 | 66.3 | 60.0 | 51.8 | 68.6 | 58.3 |
| Claude Opus 4.8 | 54.9 | 35.1 | 59.2 | 64.1 | 61.5 | 54.7 | 66.6 | 56.6 |
| DeepSeek-V4-Pro | 63.3 | 27.6 | 51.3 | 59.4 | 55.2 | 50.3 | 63.7 | 53.0 |
| Qwen3.5-35B-A3B (base) | 57.9 | 26.0 | 46.1 | 47.6 | 53.2 | 47.1 | 56.3 | 47.7 |
| **Qwen-AgentWorld-35B** | 64.8 | 36.7 | 54.0 | 65.6 | 58.2 | 49.6 | 65.9 | **56.4** |

## Model Architecture

- Architecture: Qwen3_5MoeForConditionalGeneration
- Type: MoE + SSM hybrid (Gated DeltaNet + Gated Attention)
- Layers: 40 (10 × [3 DeltaNet→MoE + 1 Attention→MoE])
- Experts: 256 (8 routed + 1 shared), intermediate dim 512
- Hidden: 2048, Vocab: 248320
- Context: 262,144 tokens
- Chat template: separate `chat_template.jinja` file (NOT in tokenizer_config.json)
- AgentWorld guard: detects "Language World Model simulating" in system prompt → strict output mode
- Tool calling format: `<function=...><parameter=...></parameter></function>` (NOT JSON)

## Qwen3.5 vs Qwen3.6 vs SuperQwen (Same Hardware, Same Methodology)

All data from APEX eval suite on DGX Spark. `final/` = Qwen3.5-35B-A3B base, `qwen36_35b/` = Qwen3.6-35B-A3B, ours = SuperQwen APEX.

| Metric | Qwen3.5 F16 | Qwen3.5 APEX I-Q | Qwen3.6 Q8_0 | Qwen3.6 APEX I-Q | Our Q8_0 | Our APEX v1 | Our APEX v3 |
|--------|:-----------:|:----------------:|:------------:|:----------------:|:--------:|:-----------:|:-----------:|
| Size | 65 GB | 21 GB | ~34 GB | 21 GB | 35 GB | 22 GB | 22 GB |
| PPL | 6.537 | 6.552 | 6.720 | 6.735 | **5.837** | **5.868** | **5.870** |
| HellaSwag | 82.5% | 83.5% | 82.5% | 82.5% | — | 82.75% | 82.50% |
| Winogrande | 74.5% | 74.5% | — | — | — | 75.50% | 75.50% |
| MMLU | 41.5% | 41.4% | — | — | — | 42.38% | 41.93% |
| ARC | 56.9% | 57.9% | — | — | — | 54.52% | 53.85% |
| TruthfulQA | 37.2% | 38.4% | — | — | — | — | — |
| tg128 (t/s) | 30.4 | 63.1 | 9.7* | 63.9 | — | 38.5 | 40.2 |

*Qwen3.6 Q8_0 tg128=9.7 — likely different test config.

**Key finding:** SuperQwen PPL is 10-13% better than both Qwen3.5 and Qwen3.6 base models, thanks to Supertune post-training. ARC is 3-4% lower (abliteration side-effect). All other metrics within noise.

**Data source:** APEX repo has benchmark JSON files at `/home/user/dev/apex-quant/benchmark_results/` organized by model family (`final/` = Qwen3.5, `qwen36_35b/` = Qwen3.6, etc.). Each contains `apex_i_quality.json`, `baseline_results.txt`, `kl_results.txt`. Use these for cross-model comparisons without running expensive benchmarks.

## Key Takeaway

APEX v1 and v3 are statistically identical on all standard benchmarks. v3 uses 42% function calling data in calibration corpus (vs v1's 0%). For agentic use cases, v3 is recommended because:
1. Calibration corpus matches inference-time patterns (Qwen chat format with FC traces)
2. Slightly faster generation (+4.2% tg128)
3. No quality degradation on any metric
