# Dense Diffusion LLM Landscape (July 2026)

Comprehensive comparison of diffusion language models, focusing on **dense** architectures
(where all parameters are active, vs MoE). Compiled from a deep research session covering
arXiv papers, HuggingFace model cards, GitHub repos, and the awesome-language-diffusion index.

## Dense diffusion LLMs (open weights) — ranked by size

| Model | Params | Base AR model | Method | Creator | Date | Speedup | Quality vs AR | Weights |
|:------|:-------|:-------------|:-------|:--------|:-----|:--------|:-------------|:--------|
| **Nemotron-Labs-Diffusion-14B** | 14B dense | Qwen3 | Efficient-DLM (joint AR+diff) | NVIDIA | 05.2026 | 6× tok/fwd, 4× throughput (SPEED-Bench, GB200) | +1.2% vs Qwen3-8B | `nvidia/Nemotron-Labs-Diffusion-14B` |
| **I-DLM 8B** | 8B dense | Qwen3-8B (LoRA) | Causal attn + introspective | Together AI | 04.2026 | 2.9–4.1× throughput | MATCHES AR (15 bench) | `yifanyu/I-DLM-8B` |
| **DreamReasoner-8B** | 8B dense | Qwen3-8B-Base | Block-size curriculum | DreamLM | 06.2026 | block parallel | ≈ Qwen3-8B-Thinking | GitHub: DreamLM/DreamReasoner |
| **LLaDA 1.5** | 8B dense | LLaMA backbone | From scratch + VRPO | inclusionAI | 10.2025 | parallel decode | ≈ LLaMA3-8B, +8-12pp over 1.0 | `GSAI-ML/LLaDA-1.5` |
| **Dream 7B** | 7B dense | AR-init + CART | HKUNLP+Huawei | 08.2025 | parallel decode | ≈ LLaMA3-8B | Dream repo |
| **DiffuCoder 7B** | 7B dense | — | Masked diff + cpGRPO | Apple+HKU | 06.2025 | parallel decode | code-specialized | `apple/DiffuCoder-7B-Instruct` |
| **DiffuLLaMA 7B** | 7B dense | LLaMA-2-7b | AR→Diff (<200B tok) | HKUNLP | ICLR'25 | parallel decode | 80–95% of AR | `QuantFactory/diffullama-GGUF` |
| **NBDiff-7B** | 7B dense | Pangu-Embedded-7B | Context-causal masking + block-growth | Huawei/Pangu | 12.2025 | parallel decode | SOTA 7B DLM (GSM8K 79.6%) | arXiv:2512.06776 |
| **MMaDA 8B** | 8B dense | — | Unified multimodal diff | Princeton+ByteDance | 05.2025 | parallel decode | multimodal | `Gen-Verse/MMaDA-8B-Base` |

## MoE diffusion LLMs (open weights) — for reference

| Model | Total/Active | Method | Creator | Date |
|:------|:------------|:-------|:--------|:-----|
| DiffusionGemma-26B-A4B | 26B/4B | Gemma 4 + diffusion head | Google | 06.2026 |
| LLaDA 2.0-flash | 100B/6.1B | AR conversion + scale | inclusionAI | 12.2025 |
| LLaDA 2.1-mini | 16B/1.4B | + token editing | inclusionAI | 12.2025 |
| LLaDA-MoE | 7B/1.4B | First MoE dLLM from scratch | inclusionAI | 09.2025 |
| RND1 | 30B/3B | AR→Diffusion conversion | Radical Numerics | 10.2025 |
| Nemotron-Labs-TwoTower | 30B/3B | Frozen AR + denoiser tower | NVIDIA | 07.2026 |
| ZAYA1-8B | 8B/760M | TiDAR mid-training | Zyphra | 05.2026 |

## Closed commercial diffusion LLMs

| Model | Speed | Creator | Notes |
|:------|:------|:--------|:------|
| Mercury 2 | 1000+ tok/s (H100) | Inception Labs | First commercial dLLM, reasoning |
| Gemini Diffusion | 1479 tok/s | Google DeepMind | ~Gemini 2.0 Flash-Lite quality |
| Seed Diffusion | 2146 tok/s (H20) | ByteDance+Tsinghua | Code, 5.4× over AR |

## Architecture comparison: key differentiators

| Feature | DiffusionGemma (MoE) | Nemotron-Labs-Diff (Dense) | I-DLM (Dense) | LLaDA (Dense) |
|:--------|:---------------------|:---------------------------|:--------------|:--------------|
| Attention | Bidirectional | Switchable (AR↔Bi) | **Causal** (AR-like!) | Bidirectional |
| KV-cache | ❌ | ✅ (AR + self-spec) | ✅ (SGLang) | ❌ |
| Streaming | ❌ | ✅ (AR mode) | ✅ | ❌ |
| Tri-mode | ❌ | ✅ | ❌ | ❌ |
| Quality gap vs AR | -5..-20 pp | **+1.2%** (better!) | **0 pp** (matched!) | ~parity LLaMA3-8B |
| Canvas size | 256 fixed | adaptive | adaptive | adaptive |

## Selection guide for DGX Spark (128GB)

| Priority | Model | Why | VRAM (BF16) |
|:---------|:------|:----|:------------|
| Max size + speed | Nemotron-Labs-Diffusion-14B | Largest dense, tri-mode, +1.2% over AR | ~28GB |
| Max quality | I-DLM 8B | Matches AR quality, causal attn, SGLang | ~16GB |
| Reasoning/CoT | DreamReasoner-8B | Block curriculum, ≈ Qwen3-8B-Thinking | ~16GB |
| Code | DiffuCoder 7B | Code-specialized, coupled-GRPO | ~14GB |
| Multimodal | MMaDA 8B | Text + image gen + understanding | ~16GB |

## Living resources

- **awesome-language-diffusion** (github.com/Optimizer077/awesome-language-diffusion): 356 verified papers, daily updated. Best living index.
- **dLLM survey** (arXiv 2508.10875): comprehensive taxonomy.
- **vLLM blog** (vllm.ai/blog/2026-06-10-diffusion-gemma): DiffusionGemma deployment details.
- **Nemotron-Labs-Diffusion GitHub** (github.com/NVlabs/Nemotron-Labs-Diffusion): includes SGLang deployment guide for DGX Spark.

## Key insight (July 2026)

100B diffusion (LLaDA 2.1-flash) only matches Qwen3-30B AR — diffusion needs ~3-4× more params for parity.
**Exceptions**: I-DLM 8B matches AR at same scale by keeping causal attention; Nemotron-Labs-Diffusion
exceeds AR by 1.2% via joint AR+diffusion training. The field is at ~2023 AR maturity: technology works,
scale achieved, SOTA quality gap is closing fast.
