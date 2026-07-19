# DGX Spark Model Comparison (July 2026)

Condensed findings from a deep-research session comparing three models for local deployment on DGX Spark (128GB, Grace Blackwell GB10, ARM64).

## Hardware Constraints

| Parameter | Value |
|---|---|
| RAM | 128 GB unified LPDDR5X |
| GPU | Blackwell, SM12.1, ~1000 FP4 TOPS |
| CUDA | Requires 13.1+, arch flag `121` |
| CPU | Grace (ARM64 SBSA), 20 cores |
| Memory BW | ~273 GB/s |

## llama.cpp for DGX Spark

**Critical:** Standard ARM64 llama.cpp binaries do NOT include CUDA arch flags for Blackwell. They run CPU-only. Use:

- **Fork:** `croll83/llama.cpp-dgx` — TurboQuant + NVFP4 + DFlash MTP, compiled for SM12.1
- **Prebuilt wheels:** Available on NVIDIA forums (CUDA 13.1, SM12.1a, ARM64 SBSA)
- **Build:** `cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="121"`

## MoE Performance on DGX Spark

| Active params | Expected tok/s (llama.cpp, Q4) |
|---|---|
| 3B | 50–80 |
| 4B | 40–60 |
| 17B | 10–25 |

Source: NVIDIA forum benchmarks (April 2026), MoE models like Qwen3.5-35B-A3B.

## Model Candidates (ranked)

### Tier 1: Maximum Quality — Nex-N2-Pro
- **Total/Active:** 397B / 17B
- **Architecture:** Qwen3.5 MoE, Agentic Thinking post-training
- **GGUF:** `morikomorizz/Nex-N2-Pro-MTP-GGUF:IQ2_XS` (~120 GB)
- **On Spark:** IQ2_XS + KV cache = tight fit in 128 GB. ~10–20 tok/s.
- **Benchmarks:** SWE-Bench Pro 58.8, BrowseComp 83.7, GPQA Diamond 90.7
- **Best for:** Complex coding, deep analysis, when GPT-5.5/Opus-class quality matters

### Tier 2: Fast Interactive — Nex-N2-mini
- **Total/Active:** 35B / 3B
- **Architecture:** Qwen3.5 MoE, Agentic Thinking (same as Pro)
- **GGUF:** `Frosty40/Nex-N2-mini-B70-Turbo-GGUF:Q4_K_M` (~20 GB)
- **On Spark:** 50–80 tok/s, comfortable interactive use
- **Benchmarks:** SWE-Bench Verified 74.4, GPQA Diamond 82.6, IFEval 89.1
- **Best for:** Daily coding, chat, prototyping — can run alongside other models

### Tier 3: World Model — Qwen-AgentWorld-35B (non-abliterated)
- **Total/Active:** 35B / 3B
- **Architecture:** Qwen3.5 MoE, 3-stage LWM training (CPT→SFT→RL)
- **GGUF:** `unsloth/Qwen-AgentWorld-35B-A3B-GGUF:Q4_K_M` (~20 GB)
- **On Spark:** 50–80 tok/s
- **AgentWorldBench:** 56.39 (above Claude Sonnet 4.6 at 56.04)
- **Best for:** Environment simulation, RL agent training — NOT a chat model

### Tier 4: Uncensored (caution) — Huihui-AgentWorld-35B-abliterated
- **Total/Active:** 35B / 3B
- **GGUF:** `Gwakweena/Huihui-Qwen-AgentWorld-35B-A3B-abliterated-Q4_K_M-GGUF`
- **Risk:** Abliteration degrades quality; bigger models suffer more (Nathan Sapwell, April 2026)
- **Best for:** When censorship removal is the priority; prefer non-abliterated for quality

## Rejected Candidates

| Model | Reason |
|---|---|
| Qwen3.5-397B-A17B (bartowski Q4_K_M) | ~220 GB — won't fit in 128 GB |
| Qwen-AgentWorld-397B | No GGUF available |
| DeepSeek-V4-Pro | No verified GGUF for llama.cpp |
| Huihui4-48B-A4B | No GGUF; experimental untuned merge of 256 experts; "just a test" per authors |

## Non-Quantized (BF16/FP16) Models on DGX Spark

**Research date:** July 12, 2026. Full research session: «проведи глубокое исследование и найди лучшую неквантованную модель на одном dgx spark».

### Memory Budget for Non-Quantized Inference

BF16/FP16 = 2 bytes/parameter. Theoretical max: 128 GB / 2 = 64B params. Practical (OS ~4-8 GB + KV cache ~12-20 GB for 32K context):

| Model class | Max total params (BF16) | Room for KV cache |
|---|---|---|
| Dense | ~50-55B | Tight (~20 GB) |
| MoE | ~55-60B | Comfortable (~40-60 GB) |
| MoE ≤35B total | Any | Very comfortable (60+ GB) |

KV-cache saving: `--kv-cache-dtype fp8` halves KV cache memory (vLLM), critical for dense 49B+ models.

### Ranked: Best Non-Quantized Models (BF16/FP16 safetensors, not GGUF)

#### 🥇 Qwen3.6-35B-A3B — BEST OVERALL
- **HF:** `Qwen/Qwen3.6-35B-A3B`
- **Total/Active:** 35B / 3B
- **Architecture:** Qwen3.6 MoE Hybrid (GatedDeltaNet + Attention, pattern LLLF)
- **BF16 weight:** ~67 GB → **61 GB free** for KV cache + system
- **Context:** 262K native
- **Speed (est.):** 40–80 tok/s (MoE, only 3B active per token)
- **Benchmarks:**
  - SWE-bench Verified: **73.4%**
  - MMLU-Pro: ~86
  - GPQA Diamond: ~85
- **License:** Apache 2.0
- **Ecosystem:** Official vLLM recipe (`recipes.vllm.ai`), NVFP4 variant for Blackwell, proven on DGX Spark (NVIDIA forums: «Single-Spark always on agent team — Qwen3.6-35B resident»)
- **Release:** April 2026 — newest architecture in weight class
- **Best for:** Daily coding, agents, chat — the default choice

#### 🥈 Nemotron-Super-49B-v1.5 — BEST DENSE (slow but precise math)
- **HF:** `nvidia/Llama-3_3-Nemotron-Super-49B-v1`
- **Total:** 49.9B (DENSE — all params active)
- **Architecture:** DeciLM (NAS-optimized Llama-3.3, variable attention/FFN per layer)
- **BF16 weight:** ~100 GB → **only ~20 GB free** (tight! Use FP8 KV cache)
- **Context:** 128K
- **Speed (est.):** 2–4 tok/s (dense 49B on 273 GB/s BW — memory-bandwidth-bound)
- **Benchmarks:**
  - MATH-500: **95.9** (best in class)
  - MMLU-Pro: 78.5
  - GPQA Diamond: 52.0
  - LiveCodeBench: 28.0 (weak coding)
- **License:** Llama 3.3 Community
- **Best for:** Math/reasoning-heavy workloads where speed doesn't matter

#### 🥉 Qwen3.6-27B — DENSE, FASTER
- **HF:** `Qwen/Qwen3.6-27B`
- **Total:** 27B (DENSE)
- **BF16 weight:** ~54 GB → 74 GB free
- **Speed (est.):** 8–15 tok/s
- **Benchmarks:** MMLU-Pro ~84, GPQA Diamond ~82
- **Best for:** When you need dense (not MoE) with good speed

#### 4. Huihui4-48B-A4B-abliterated — EXPERIMENTAL (caution)
- **HF:** `huihui-ai/Huihui4-48B-A4B-abliterated`
- **Total/Active:** 48.65B / 4B
- **Architecture:** Gemma4 MoE (256 experts)
- **BF16 weight:** 97.3 GB → tight (~23 GB free)
- **Risks:** Experimental («just a test» per authors). Abliterated — quality degradation. Gemma4 has weaker coding benchmarks than Qwen3.6.
- **MLX variant** (`LibraxisAI/Huihui4-48B-A4B-vmlx-fp16`): Apple Silicon ONLY — will NOT run on DGX Spark (ARM64 Linux ≠ macOS)

### Rejected Non-Quantized Candidates

| Model | BF16 size | Reason |
|---|---|---|
| Huihui-MoE-60B-A3B-abliterated | ~120 GB | 120 GB + KV cache > 128 GB. Does NOT fit. |
| QwQ-56B-Ghost (JackCloudman) | ~112 GB | 112 GB + KV cache > 128 GB. Also: passthrough depth-upscaling from Qwen-32B WITHOUT continued pre-training — «Depth Delusion» (arXiv:2601.20994) shows adding layers without CPT INCREASES loss. |
| ALIA-40B (BSC-LT) | ~80 GB | Fits but is a BASE model (not instruct), needs fine-tuning. Weaker than Qwen3.6. |
| Llama-3.3-70B-Instruct | ~140 GB | 140 GB > 128 GB. Does NOT fit at BF16. |
| Qwen3.5-397B-A17B | ~794 GB | Way too large. |
| Any GGUF model | N/A | GGUF = quantized by definition. User asked for NON-quantized. |

### User's Linked Models — Why They Don't Qualify

All 6 models from the user's links were either GGUF (quantized), MLX (Apple-only), or too large at BF16:

| Link | Issue |
|---|---|
| `mradermacher/Huihui-MoE-60B-A3B-abliterated-GGUF` | GGUF = quantized. BF16 original = 120 GB, won't fit. |
| `LibraxisAI/Huihui4-48B-A4B-vmlx-fp16` | MLX format — macOS/Apple Silicon only. |
| `huihui-ai/Huihui4-48B-A4B-abliterated` | BF16 safetensors (97 GB, tight fit). Experimental abliterated model. |
| `mradermacher/QwQ-56B-Ghost-i1-GGUF` | GGUF = quantized. BF16 original = 112 GB, won't fit. Depth-upscaled frankenmerge. |
| `timteh673/Nemotron-Super-49B-v1.5-Uncensored-GGUF` | GGUF = quantized. Original BF16 fits (100 GB) but is uncensored variant. |
| `mradermacher/ALIA-40b-instruct-2601-ara-heretic-GGUF` | GGUF = quantized. Original BF16 fits (80 GB) but is a base model. |

### Quick Deploy: Qwen3.6-35B-A3B BF16 on DGX Spark

```bash
# Download non-quantized weights (~67 GB)
huggingface-cli download Qwen/Qwen3.6-35B-A3B --local-dir /models/qwen3.6-35b-bf16

# vLLM (recommended — 2.5× faster than llama.cpp)
docker run --gpus all -v /models:/models \
  hellohal2064/vllm-dgx-spark-gb10 \
  --model /models/qwen3.6-35b-bf16 \
  --dtype bfloat16 --max-model-len 32768 \
  --gpu-memory-utilization 0.90

# llama.cpp alternative (convert BF16→F16 GGUF, no quality loss)
python3 convert_hf_to_gguf.py /models/qwen3.6-35b-bf16 --outtype f16
./llama-server -m qwen3.6-35b-f16.gguf --no-mmap --jinja -c 32768
```

## Abliteration Quality Impact

Key findings from Nathan Sapwell's benchmark (April 2026), comparing Heretic vs HauhauCS vs Huihui across 5 Qwen models:

1. **Not lossless** — all techniques degrade capability; claim of "no changes to capabilities" is false
2. **Zero-refusal claim does not hold** — refusals are reduced but not eliminated
3. **Bigger models suffer more collateral damage** — the larger the model, the worse the degradation
4. **Huihui is inconsistent across models** — works well on some sizes, poorly on others
5. **Heretic is the most consistent** performer across model sizes
6. **Architecture matters** — hybrid Mamba2+Transformer responds differently than pure Transformer

## Key Sources

- Qwen-AgentWorld paper: arxiv.org/abs/2606.24597 (June 23, 2026)
- Nex-N2 announcement: nex-agi.com, OpenRouter free tier (June 9, 2026)
- DGX Spark llama.cpp stack: NVIDIA Developer Forums (April 23, 2026)
- Abliteration benchmark: nathan.sapwell.net/posts/hauhaucs-abliteration-analysis (April 18, 2026)
- llama.cpp-dgx fork: github.com/croll83/llama.cpp-dgx
- Ollama models: ollama.com/huihui_ai, ollama.com library for Nex-N2
