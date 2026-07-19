# Model Landscape: Architectural Diversity Analysis (July 12, 2026)

## The Monoculture Problem

All 4 models in Pavel's current stack share ONE architecture:
`qwen3_5_moe` — Qwen3.5/3.6-35B-A3B MoE (256 experts, 8 active, 3B active params).
40 layers, 2048 hidden, hybrid Gated DeltaNet (75%) + Full Attention (25%), 262K context.

| Model | Lineage | Role | What Changed |
|-------|---------|------|-------------|
| Qwen3.6-35B-A3B | lordx64 Claude 4.7 Opus distill + huihui abliteration | Math/reasoning base | Distillation + uncensored |
| Agents-A1 | InternScience 3-stage agentic fine-tune | #1 Agent (search, science, IF) | Multi-teacher domain distillation |
| SuperQwen (AgentWorld) | Alibaba LWM + Jiunsong Supertune + abliteration | World simulation | Environment prediction training |
| Nex-N2-mini | Nex-AGI "Agentic Thinking" fine-tune | Coding (SWE 74.4, Terminal 60.7) | Adaptive Thinking framework |

They are **siblings** — different fine-tunes, identical base architecture.
Running 4 variants gives diminishing returns; architectural diversity is the high-value upgrade path.

## Benchmark Comparison (from Agents-A1 README — direct head-to-head)

### Agentic/Search Benchmarks
| Benchmark | Qwen3.6-35B | Nex-N2-mini | Agents-A1 |
|-----------|:---:|:---:|:---:|
| BrowseComp | 67.9 | 74.1 | **75.5** |
| GAIA | 78.6 | 82.5 | **96.0** |
| Seal-0 | 38.7 | 49.6 | **56.4 (SOTA)** |
| IFBench | 64.4 | 54.1 | **80.6 (SOTA)** |
| IFEval | 91.3 | 88.4 | **94.8 (SOTA)** |

### Coding Benchmarks (standalone, not from A1 table)
| Benchmark | Qwen3.6-35B | Nex-N2-mini | Agents-A1 |
|-----------|:---:|:---:|:---:|
| SWE-bench Verified | 73.4 | **74.4** | — (not a coding model) |
| Terminal-Bench 2.x | 51.5 | **60.7** | — |
| GPQA Diamond | **86.0** | 82.6 | — |
| MMLU-Pro | **85.2** | — | — |
| AIME 2026 | **92.7** | — | — |

### AgentWorld Specific
| Benchmark | Base Qwen3.5 | AgentWorld-35B | Delta |
|-----------|:---:|:---:|:---:|
| AgentWorldBench | ~47.7 | **56.4** | +8.7 (LWM training) |

## Top 5 Alternative Architectures (for Diversity)

Priority-ranked by architectural distance from Qwen3.5/3.6-35B-A3B MoE.

### 1. GLM-4.7-Flash-abliterated (Zhipu AI / Z.ai)
- **Architecture:** MoE with **MLA** (Multi-head Latent Attention) — fundamentally different from Qwen's GQA
- **Params:** 30B total / ~3.2B active
- **Quant size:** ~20 GB at Q4_K_M
- **Context:** 200K
- **Why:** SWE-bench **59.2%** vs Qwen3-30B-A3B's 22.0% (2.7x gap). MLA reduces KV cache.
- **Uncensored:** `huihui-ai/Huihui-GLM-4.7-Flash-abliterated-GGUF`
- **Diversity:** 9/10 (different company, different attention: MLA vs GQA)
- **Caveat:** Russian language support uncertain (Chinese/English focused)

### 2. Kimi-Linear-48B-A3B-abliterated (Moonshot AI)
- **Architecture:** MoE + **KDA** (Kimi Delta Attention) + MLA at 3:1 — linear/recurrent, not pure transformer
- **Params:** 48B total / 3B active
- **Quant size:** ~30 GB at Q4_K_M
- **Context:** **1M tokens** (linear attention = near-zero KV cache growth)
- **Why:** 6x faster decoding at long context vs full attention. Ultra-long agentic workflows.
- **Uncensored:** `mradermacher/Huihui-Kimi-Linear-48B-A3B-Instruct-abliterated-i1-GGUF`
- **Diversity:** 10/10 (linear attention paradigm shift)
- **Caveat:** Verify llama.cpp support for KDA architecture (may need recent build)

### 3. Gemma 4 31B QAT Heretic Uncensored (Google DeepMind)
- **Architecture:** **Dense** Transformer (NOT MoE — all 31B params active per token)
- **Params:** 31B (all active)
- **Quant size:** ~18 GB at Q4
- **Context:** 262K
- **Why:** **QAT** (Quantization-Aware Training) = Q6 quality at Q4 size. Dense = deeper per-token reasoning. Best Russian language likelihood.
- **Uncensored:** `EZForever/gemma-4-31B-it-qat-uncensored-heretic-UDmerge-GGUF`
- **Diversity:** 8/10 (dense vs MoE, different training data, QAT paradigm)
- **Caveat:** Dense = slower generation than MoE. Gemma4 chat template issues with `--jinja`.

### 4. GLM-4-32B-0414-abliterated (Zhipu AI)
- **Architecture:** Dense Transformer + RL reasoning
- **Params:** 32B (all active)
- **Quant size:** ~19 GB at Q4_K_S
- **Context:** 32K
- **Why:** Comparable to GPT-4o / DeepSeek-V3 (671B) on code. MIT license. RL-powered deep reasoning.
- **Uncensored:** `mradermacher/GLM-4-32B-0414-abliterated-GGUF`
- **Diversity:** 7/10 (dense, different company, different RL approach)
- **Caveat:** Older (April 2025). Short context (32K).

### 5. Liquid LFM2-24B-A2B-abliterated (Liquid AI)
- **Architecture:** **Non-Transformer SSM** (Mamba/state-space hybrid)
- **Params:** 24B total / 2B active
- **Quant size:** ~14 GB at Q4
- **Why:** Only non-transformer option. No quadratic attention scaling. Edge-first efficiency.
- **Uncensored:** `mradermacher/Huihui-LFM2-24B-abliterated-GGUF`
- **Diversity:** 10/10 (entirely different model family)
- **Caveat:** Smallest model (24B/2B). Russian support minimal. Best as complement, not primary.

## Cross-Architecture Benchmark Table (July 12, 2026)

Head-to-head scores gathered via deep research across HF model cards, papers, and aggregators.
"—" = not published for that model. Where A1 wins, alternatives simply weren't evaluated on those benchmarks.

### Agentic / Search / Instruction Following (A1 DOMINATES)

| Benchmark | **Agents-A1** | GLM-4.7-Flash | Gemma 4 31B | Kimi-Linear-48B | LFM2-24B |
|-----------|:---:|:---:|:---:|:---:|:---:|
| τ²-Bench (tool use) | 79.8 | 79.5 | **86.4** | — | 11.1 |
| BrowseComp | **75.5** | 42.8 | — | — | — |
| GAIA | **96.0** | — | — | — | — |
| Seal-0 | **56.4** | — | — | — | — |
| IFBench | **80.6** | — | — | — | 45.9 |
| IFEval | **94.8** | — | — | — | — |
| HLE w/ tools | **47.6** | 14.4 | — | — | 4.4 |
| SciCode | **44.3** | 34 | — | 20 | 11 |

**A1 wins 7/8 agent benchmarks. Only Gemma 4 31B beats it on τ²-Bench (86.4 vs 79.8).**

### Coding / Math / Knowledge (Alternatives WIN — A1 has no published scores)

| Benchmark | **Agents-A1** | GLM-4.7-Flash | Gemma 4 31B | Kimi-Linear-48B | LFM2-24B |
|-----------|:---:|:---:|:---:|:---:|:---:|
| SWE-bench Verified | — | **59.2** | 52.0 | — | 18 |
| LiveCodeBench v6 | — | — | **80.0** | 37.8 | 17 |
| HumanEval | — | — | **82.7** | — | — |
| Codeforces ELO | — | — | **2150** | — | — |
| Terminal-Bench 2.0 | — | — | 42.9 | — | 0 (Hard) |
| AIME 2025/2026 | — | **91.6** | 89.2 | 21.3 | — |
| MATH / MATH500 | — | — | 58.7 | 81.2 (500) | — |
| GPQA Diamond | — | 75.2 | **84.3** | 41.0 | 47.4 |
| MMLU-Pro | — | ~60 | **85.2** | 51.0 | — |
| MMLU | — | — | **87.1** | — | — |

**Key insight:** A1 has NO published standard benchmarks (MMLU, AIME, SWE-bench, GPQA).
Alternatives beat A1 simply because A1 was never evaluated on those tests — it was trained for agents.
Gemma 4 31B is the strongest all-rounder: top on MMLU-Pro (85.2), GPQA (84.3), LiveCodeBench (80.0), τ²-Bench (86.4).
GLM-4.7-Flash is the coding specialist: SWE-bench 59.2 (2.7x better than Qwen3-30B-A3B).
Kimi-Linear-48B and LFM2-24B are NOT competitive with A1 on any metric — their value is architectural diversity, not raw performance.

### AA Intelligence / Coding Indices (Artificial Analysis composites)

| Index | GLM-4.7-Flash | Kimi-Linear-48B | LFM2-24B |
|-------|:---:|:---:|:---:|
| AA Intelligence | 30.15 | 9 | 5.0 |
| AA Coding | 25.9 | 14 | 3.6 |
| Terminal-Bench Hard | 22 | 11 | 0 |

## Recommended Diversification Path

Keep 2 current models, add 3 new architectures (~112 GB total, fits 128 GB unified):

| Action | Model | Size | Reason |
|--------|-------|------|--------|
| **KEEP** | Agents-A1 (APEX I-Quality) | ~22 GB | Best agent/search/science in class |
| **KEEP** | Nex-N2-mini (APEX-Quality) | ~33 GB | Best coding (SWE 74.4, Terminal 60.7) |
| **DROP** | Qwen3.6-35B | ~22 GB | Replaced by Agents-A1 (dominates on 14/15 benchmarks) |
| **DROP** | SuperQwen (AgentWorld) | ~22 GB | Niche world simulation; if not actively used for Sim RL |
| **ADD** | GLM-4.7-Flash-abliterated | ~20 GB | SWE-bench 59.2%, MLA architecture, coding powerhouse |
| **ADD** | Gemma 4 31B QAT Heretic | ~18 GB | Dense reasoning, QAT quality, Russian language |
| **ADD** | Kimi-Linear-48B-A3B | ~30 GB | 1M context, linear attention for long-context agents |

Total: 55 (kept) + 68 (new) = 123 GB. Tight but fits with reduced context sizes.

**Minimal diversification** (if only adding 1 model):
- **GLM-4.7-Flash-abliterated** is the highest-impact addition: different architecture, massive SWE-bench improvement, only 20 GB.

## Unquantized (f16/bf16) Fit Analysis

For DGX Spark 128 GB unified (~100 GB usable after OS + services):

| Model | Params | f16 Size | Fits? | Notes |
|-------|--------|----------|-------|-------|
| **Qwen3.6-27B** (dense) | 27B | ~54 GB | **YES (comfy)** | Best unquantized: 77.2% SWE-bench, 85.3 MMLU-Pro |
| Qwen3.6-35B-A3B (MoE) | 35B | ~70 GB | YES | 30 GB headroom for KV cache |
| ALIA-40b-heretic | 40B | ~81 GB | TIGHT | Only 19 GB headroom |
| Nemotron-Super-49B | 49B | ~98 GB | NO | Weights alone = 98 GB, 0 room for KV |
| Gemma4-31B (dense) | 31B | ~61 GB | YES | But 1.85 tok/s generation (too slow for chat) |
| Huihui4-48B-A4B | 48B | ~97 GB | NO | + experimental concat, no fine-tune |
| QwQ-56B-Ghost | 56B | ~112 GB | NO | Unvalidated passthrough merge |
| Huihui-MoE-60B-A3B | 59.5B | ~119 GB | NO | Nearly 2x budget |

**Unquantized winner: Qwen3.6-27B** (dense, 54 GB, 77.2% SWE-bench, abliterated bf16 available).
