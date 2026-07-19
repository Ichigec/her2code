# DGX Spark Coding Models — Community Research (July 2026)

Deep research across NVIDIA Developer Forums (10+ threads), AI-Girls Lab benchmarks,
Hugging Face model cards, community articles, and Hacker News. Single Spark (GB10, 128 GB).

## Top 5 — Ranked by Forum Consensus

### 🥇 #1: Qwen3.6-35B-A3B (NVFP4 / PrismaQuant 4.75-bit, vLLM, MTP n=3)

Community "daily driver" for single Spark — most recommended across all threads.

| Parameter | Value |
|-----------|-------|
| Architecture | MoE: 35B total / 3B active, 256 experts, Gated DeltaNet |
| Quantization | **PrismaQuant 4.75-bit** (~19-23 GB, vLLM-native) or **NVFP4** (NVIDIA official) |
| Speed | 50–97 tok/s (NVFP4+MTP), 50-64 tok/s (stable daily), 28-30 tok/s (FP8 no MTP) |
| SWE-bench Verified | 73.4% |
| Terminal-Bench 2.0 | 51.5 |
| Context | 256K |
| Speculative | **MTP n=3** — measured optimum for DGX Spark (n=2 leaves ~10% on table, n=4 regresses) |
| Engine | **vLLM** (forum recommendation), llama.cpp works too |
| License | Apache 2.0 |

Sources:
- `rdtand/Qwen3.6-35B-A3B-PrismaQuant-4.75bit-vllm` — "MTP n=3 is the measured optimum"
- `nvidia/Qwen3.6-35B-A3B-NVFP4` — official, May 2026
- `sakamakismile/Huihui-Qwen3.6-35B-A3B-abliterated-NVFP4` — uncensored, SWE-bench 73.4
- [Single-Spark Setups thread](https://forums.developer.nvidia.com/t/single-spark-setups-which-models-do-you-actually-run-for-coding-and-how-sharing-mine-a-test-prompt/374423)

Forum quote: "Qwen3.6-35B-A3B — PrismaQuant 4.75-bit (vLLM) — my daily driver; fastest and most capable small model I've found for the Spark."

### 🥈 #2: Qwen3.6-27B (Dense, Q4_K_M, llama.cpp, MTP)

Best coding quality — beats 397B models. Slow on single Spark but 77.2% SWE-bench.

| Parameter | Value |
|-----------|-------|
| Architecture | **Dense**: all 27B active per token |
| Quantization | Q4_K_M GGUF (~15-18 GB) or FP8 |
| Speed | 10-15 tok/s (FP8, one Spark), ~60 tok/s (Q4_K_M+MTP on RTX 3090) |
| SWE-bench Verified | **77.2%** — beats Qwen3.5-397B-A17B |
| Context | 256K |
| Speculative | MTP (1.4–1.86×) |
| Engine | llama.cpp or vLLM |
| License | Apache 2.0 |

Forum quote: "Qwen3.6 27B is the sweet spot for local development" — Hacker News.
"Qwen3.6-27B outperforms Qwen3.5-397B-A17B MoE on SWE-bench Verified (77.2% vs ~76.2%)" — deepresearch.ninja.

Trade-off: dense = slower on DGX Spark (10-15 tok/s vs 50-97 for MoE). Better for batch/background coding, worse for interactive agents.

### 🥉 #3: Qwen3-Coder-Next (80B-A3B, FP8, vLLM)

Purpose-built coding model. 256K context. Fits one Spark with another model.

| Parameter | Value |
|-----------|-------|
| Architecture | MoE: 80B total / 3B active |
| Quantization | **FP8** (native!) |
| Speed | ~43 tok/s |
| Context | 256K |
| Engine | vLLM (community Docker) |
| License | Apache 2.0 |

Forum HOW-TO: "native FP8 version is supported out of the box in community Docker and performs reasonably well at ~43 t/s."

⚠️ vLLM default params disable prefix caching — "really affects coding workflows due to prompt re-processing at each request." Tune the config.

AI-Girls Lab: fits alongside Gemma 4 26B on single Spark (dual-server config).

### #4: DeepSeek-V4-Flash (Q2 GGUF, llama.cpp)

Frontier coding model that ONLY fits one Spark at Q2. Holds up surprisingly well.

| Parameter | Value |
|-----------|-------|
| Architecture | MoE: 284B total |
| Quantization | **Q2 GGUF** — only quant fitting 128 GB |
| Speed | ~10-15 tok/s |
| Quality | Community: "strong coder, Q2 holds up" |
| Engine | llama.cpp |
| License | MIT |

Forum quote: "DeepSeek-V4-Flash (Q2 GGUF, llama.cpp) — strong coder; Q2 is the only quant that fits one Spark, but it holds up."

⚠️ Extreme quantization (Q2) — exception to "big model + bad quant < smaller + good quant" rule. Base model quality compensates.

### #5: Gemma 4 31B (Dense, Q4_K_M, llama.cpp)

Architectural diversity — dense, not MoE. Google QAT preserves quality.

| Parameter | Value |
|-----------|-------|
| Architecture | Dense: 31B, 60 layers (sliding window attention) |
| Quantization | Q4_K_M GGUF (~18 GB) or TurboQuant |
| Speed | ~1.85 tok/s (F16!), needs Q4_K_M for ~10-20 tok/s |
| Context | 128K |
| Multimodality | Text + images |
| Engine | llama.cpp (preferred for Gemma attention) |
| License | Gemma |

Forum verdict: AI-Girls Lab switched to Gemma 4 as main model ("I tore out every giant model"). But direct coding comparisons show Qwen models ahead — "Gemma4 and NVIDIA models [are] very far behind" on coding benchmarks. Best as architectural diversity option.

## Speculative Decoding — DGX Spark Comparison

| Method | Speedup | Engine | Model Support | Notes |
|--------|:-------:|--------|---------------|-------|
| **MTP n=3** | 1.4–1.86× | vLLM, llama.cpp | Qwen3.6 (built-in) | 🔴 Breaks tool calling on vLLM per community reports |
| **DFlash** | up to 6× (theor.) | vLLM | Qwen3.6-35B-A3B (`z-lab/Qwen3.6-35B-A3B-DFlash`) | Public HF repo, block-diffusion |
| **EAGLE-3** | 2–5× | llama.cpp only | Needs custom draft model (~400 MB) | Lossless. No draft for Agents-A1 yet |

**Critical:** MTP breaks tool calling on vLLM. Forum consensus: disable MTP when the coding agent uses tools (bash, file ops, etc.) until Qwen team provides guidance.

Quote: "My strong recommendation: disable MTP until there's clearer guidance from the Qwen team on how to make it work reliably with tool calling" — dredyson.com

## What Pavel Already Has (for comparison)

| Model | Quant | Size | SWE-Bench | Terminal-Bench | Engine |
|-------|-------|------|:---------:|:--------------:|--------|
| Nex-N2-mini | APEX-Quality | ~33 GB | 74.4 | 60.7 | llama.cpp |
| Agents-A1 35B | APEX I-Quality | ~22 GB | N/A | N/A | llama.cpp |
| SuperQwen-AgentWorld | APEX I-Quality v3 | ~22 GB | N/A | N/A | llama.cpp |

**Assessment:** Nex-N2-mini (74.4 SWE-Bench) is still competitive with Qwen3.6-35B-A3B (73.4 SWE-Bench). But Qwen3.6-35B-A3B on NVFP4/PrismaQuant in vLLM gives 1.5–3× more speed at comparable quality.

Pavel's all-4-current-models-are-same-architecture problem remains: they're all Qwen MoE. Gemma 4 31B (dense) or DeepSeek-V4-Flash (different MoE) would add genuine architectural diversity.

## Quantization Comparison for DGX Spark

| Method | Size (35B MoE) | Speed | Engine | Quality | Notes |
|--------|:--------------:|:-----:|--------|---------|-------|
| **NVFP4** | ~19 GB | 50-97 tok/s | vLLM | Near-FP8 | NVIDIA's native FP4, fastest |
| **PrismaQuant 4.75b** | ~19-23 GB | 50-64 tok/s | vLLM | Near-FP8 | Community favorite, "daily driver" |
| **APEX I-Quality** | ~22 GB | 63 tok/s | llama.cpp | Beats F16 on some benchmarks | Pavel already uses this |
| **Q4_K_M** | ~18-20 GB | 40-50 tok/s | llama.cpp | Quality floor for MoE | Good fallback |
| **FP8** | ~37 GB | 28-30 tok/s | vLLM | Baseline | Official, no speculative gain |
| **Q2** | ~10-12 GB | 10-15 tok/s | llama.cpp | Degraded but usable | Only way to fit DeepSeek-V4-Flash |

## Key Forum Threads Referenced

1. [Single-Spark setups — which models do you actually run for coding](https://forums.developer.nvidia.com/t/single-spark-setups-which-models-do-you-actually-run-for-coding-and-how-sharing-mine-a-test-prompt/374423) — primary source, community rankings
2. [For local Agent, QWEN3.6 35B OR QWEN3-CODER-NEXT?](https://forums.developer.nvidia.com/t/for-loacl-agent-qwen3-6-35b-or-qwen3-coder-next/367721)
3. [HOW-TO: Run Qwen3-Coder-Next on Spark](https://forums.developer.nvidia.com/t/how-to-run-qwen3-coder-next-on-spark/359571)
4. [Benchmark Report: Qwen3.6-35B-A3B-NVFP4 on DGX Spark](https://forums.developer.nvidia.com/t/benchmark-report-qwen3-6-35b-a3b-nvfp4-on-nvidia-dgx-spark-jetson-thor-blackwell-6000-pro/371810)
5. [AI-Girls Lab — DGX Spark llama.cpp Dual Server](https://ai-girls.org/en/2026/04/06/dgx-spark-llama-cpp-dual-server-en/)
6. [AI-Girls Lab — Gemma4 Local LLM Optimization](https://ai-girls.org/2026/06/12/gemma4-local-llm-en/)
7. [Owning Inference — Qwen3.6 on DGX Spark for real coding](https://www.devashish.me/p/owning-inference-qwen36-on-dgx-spark)
8. [spark-coder-bench — DGX Spark Coding Model Benchmark](https://github.com/mani-mal/spark-coder-bench)
9. [NVFP4 + Qwen3.6 35B-A3B — 97 tok/s](https://llmrequirements.com/news/2026-06-03-nvfp4-qwen-3-6-35b-dgx-spark)
10. [Qwen3.6 27B/35B-A3B vs Gemma 4 vs DeepSeek V4](https://deepresearch.ninja/2026/05/Qwen3.6-27B/35B-A3B-vs-Gemma-4-vs-DeepSeek-V4-A-Comprehensive-Analysis-of-the-Open-Weight-Frontier-May-2026/)
