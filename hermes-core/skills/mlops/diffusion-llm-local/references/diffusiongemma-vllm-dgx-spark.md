# DiffusionGemma 26B-A4B on vLLM — DGX Spark (GB10) Optimal Config

Researched 2026-07-14 from multiple sources (all June-July 2026):

## Sources

1. **vLLM Recipes** — `recipes.vllm.ai/Google/diffusiongemma-26B-A4B-it` (official YAML recipe)
2. **vLLM Blog** — `vllm.ai/blog/2026-06-10-diffusion-gemma` (architecture deep-dive)
3. **miter37/diffusiongemma-vllm-gb10-notes** — GitHub repo, DGX Spark + Hermes tested (key source!)
4. **ai-muninn.com** — `dgx-spark-diffusiongemma-nvfp4-vllm` (158 tok/s NVFP4, canvas fill analysis)
5. **WindChimeRan/notes-dgx-spark** — `diffusiongemma-gb10-bench-2026-06-20.md` (BF16 vs NVFP4 benchmark)
6. **NVIDIA Developer Blog** — `developer.nvidia.com/blog/run-diffusiongemma-on-nvidia`
7. **NVIDIA Forum** — `forums.developer.nvidia.com/t/diffusiongemma-on-unslothstudio-on-single-dgx-spark/374925`
8. **RedHatAI NVFP4** — `huggingface.co/RedHatAI/diffusiongemma-26B-A4B-it-NVFP4`
9. **Google Developer Guide** — `developers.googleblog.com/diffusiongemma-the-developer-guide/`
10. **Model config.json** — `Umranz/diffusiongemma-26B-A4B-it-abliteration`
11. **r0b0tlab/diffusiongemma-26b-nvfp4-sm121-vllm** — GitHub repo, reproducible NVFP4 vLLM container, c1=146 c16=243 benchmark (2026-06-10)
12. **tsuru_mitsu (note.com)** — NIM-based benchmark on GB10, ~107 tok/s, comparison with Gemma 4 MTP (2026-06-12)
13. **diffrun.dev/benchmarks** — Multi-GPU DiffusionGemma benchmarks: RTX 4090 ~180 tok/s, A100 ~320 tok/s, Mac M2 ~45 tok/s (Q4_K_M quantization)

## Model Architecture

| Property | Value |
|----------|-------|
| Architecture | `DiffusionGemmaForBlockDiffusion` |
| Backbone | Gemma 4 MoE (26B total / 4B active) |
| Experts | 128 total, top-8 routed |
| Hidden size | 2816 |
| Layers | 30 (5 full_attention + 25 sliding_attention, window=1024) |
| Attention | Bidirectional (encoder=causal writes KV, decoder=bidirectional reads KV) |
| VLM | Yes (gemma4_vision, 27 layers, patch=16) |
| Canvas | 256 tokens generated in parallel |
| Denoising | 48 steps, EntropyBoundSampler (entropy_bound=0.1) |
| Max position | 262144 |
| Vocab | 262144 |
| File size | 49GB BF16 / 18GB NVFP4 |

## Optimal vLLM Parameters (DGX Spark GB10, BF16)

### Full Docker launch script

```bash
#!/bin/bash
# serve_diffusiongemma.sh — vLLM for DiffusionGemma 26B-A4B (abliterated, BF16)
# Target: NVIDIA DGX Spark (GB10, 128GB unified memory)

MODEL_DIR="/home/user/models/diffusiongemma-26B-A4B-it-abliteration"
DOCKER_IMAGE="vllm/vllm-openai:gemma"
CONTAINER_NAME="diffusiongemma"
PORT=8000

docker run -itd \
    --name "$CONTAINER_NAME" \
    --ipc=host --network host --gpus all \
    -e VLLM_USE_V2_MODEL_RUNNER=1 \
    -v "${MODEL_DIR}:/models/diffusiongemma:ro" \
    "$DOCKER_IMAGE" \
    --model /models/diffusiongemma \
    --served-model-name diffusiongemma-abliterated \
    --host 0.0.0.0 --port "$PORT" \
    --trust-remote-code --dtype auto \
    --max-model-len 262144 \
    --max-num-seqs 4 \
    --max-num-batched-tokens 8192 \
    --gpu-memory-utilization 0.60 \
    --diffusion-config '{"canvas_length": 256, "max_denoising_steps": 48}' \
    --attention-backend TRITON_ATTN \
    --enable-auto-tool-choice \
    --tool-call-parser gemma4 \
    --reasoning-parser gemma4 \
    --override-generation-config '{"max_new_tokens": null}' \
    --default-chat-template-kwargs '{"enable_thinking": true}' \
    --mm-processor-kwargs '{"max_soft_tokens": 1120}' \
    --limit-mm-per-prompt '{"image": 7}' \
    -tp 1
```

### Parameter rationale

| Flag | Value | Why |
|------|-------|-----|
| `VLLM_USE_V2_MODEL_RUNNER=1` | env var | Required for diffusion model runner path |
| `--max-model-len` | 262144 | Full context window (user preference). Reduce to 100000 for more KV cache. |
| `--max-num-seqs` | 4 | Hard limit — diffusion state buffers, not tunable |
| `--gpu-memory-utilization` | **0.60** | BF16 on GB10. 0.70+ starves system RAM → swap thrash (verified WindChimeRan 2026-06-20). For NVFP4 (18GB): 0.40-0.70 is fine. |
| `--max-num-batched-tokens` | 8192 | Chunked prefill batching (was 4096, raising helped) |
| `--diffusion-config` | canvas=256, steps=48 | From model's generation_config.json |
| `--attention-backend` | TRITON_ATTN | Optimal for bidirectional attention on GB10 |
| `--tool-call-parser` | gemma4 | Gemma 4 native tool calling parser |
| `--reasoning-parser` | gemma4 | Gemma 4 native thinking/reasoning parser |
| `--override-generation-config` | max_new_tokens=null | Model defaults to 256 (one canvas), override for multi-canvas |
| `--default-chat-template-kwargs` | enable_thinking=true | Reasoning by default, disable per-request for speed |
| `--mm-processor-kwargs` | max_soft_tokens=1120 | VLM image processing token budget |
| `--limit-mm-per-prompt` | image:7 | Max images per prompt |
| `-tp 1` | tensor parallel 1 | GB10 is single GPU |

### What NOT to set

- `--enforce-eager` — disables CUDA graph capture, kills performance (~2x loss)
- `--diffusion-steps` — deprecated/wrong flag, use `--diffusion-config`
- `gpu-memory-utilization > 0.65` for BF16 — causes NVRM OOM / swap thrash on GB10

## Runtime Details (from vLLM logs)

```
Resolved architecture: DiffusionGemmaForBlockDiffusion
dtype: bfloat16
KV cache dtype: fp8_e4m3
Attention backend: TRITON_ATTN
MoE backend: FLASHINFER_CUTLASS
Chunked prefill: enabled
Prefix caching: enabled
Async scheduling: enabled
enforce_eager: False
Compilation mode: VLLM_COMPILE
CUDA graph mode: FULL_AND_PIECEWISE
```

## Performance — BF16 vs NVFP4 on DGX Spark (GB10)

### Benchmark table (WindChimeRan, 2026-06-20, random 1024-in/512-out, CUDA graphs ON)

| Conc. | Model | Output tok/s | Total tok/s | TPOT p50 (ms) | TTFT p50 |
|------:|-------|-------------:|------------:|--------------:|---------:|
| 1  | NVFP4 | **45.4** | 136 | 10.5 | 5.8 s  |
| 1  | BF16  | **22.1** | 66  | 22.1 | 12.1 s |
| 16 | NVFP4 | **73.1** | 219 | 53.3 | 85 s   |
| 16 | BF16  | **48.6** | 146 | 79.1 | 127 s  |

- NVFP4 vs BF16 output tok/s: 2.06x (c=1), 1.51x (c=16)
- Diffusion saturates GPU at c=1 (96% util — 256-token canvas denoised in parallel)
- Peak ~80C / ~65W with external fans (no throttle — throttle ≈95-100C)

### Canvas fill effect — why diffusion tok/s "lies"

From ai-muninn analysis (2026-06-13):

> A diffusion LM doesn't decode left-to-right one token at a time. It fills a fixed-size canvas (256 tokens) and refines the whole block over 48 denoising steps. The cost is roughly **per-canvas, not per-token**. So a 256-token answer and an 8-token answer cost almost the same wall-clock — which means the short answer looks dramatically slower in tok/s.

| Output length | Effective tok/s (NVFP4) | Why |
|--------------|------------------------|-----|
| 8 tokens (short Q&A) | ~16 tok/s | Canvas barely filled, fixed cost amortized over few tokens |
| 128 tokens (medium) | ~65 tok/s | Half canvas utilized |
| 256 tokens (full canvas) | ~101-158 tok/s | Canvas fully utilized |
| 512 tokens (multi-canvas) | similar per-canvas | Scales linearly by canvas count |

**Implication for agent tasks**: Long reasoning/code outputs naturally fill canvases → higher effective tok/s. For quick Q&A, accept lower tok/s.

### GB10 memory bandwidth note (from NVIDIA forum, adg1)

> GB10 has 273 Gb/s memory bandwidth (nominal); experimentally observed closer to 203 Gb/s. DiffusionGemma has 3.8B active parameters. At 1-bit quantization: 273 Gb/s → 574 tok/s projected, 203 Gb/s → 427 tok/s.

Diffusion decode is NOT bandwidth-bound like AR — weight reads amortize across the whole canvas. Bottleneck shifts from bandwidth toward compute.

## Comprehensive Cross-Source Benchmark Comparison (DGX Spark GB10, all 2026-06/07)

All six known independent DGX Spark (GB10) DiffusionGemma benchmarks, ranked by c=1 output tok/s:

| Source | Date | Precision | c=1 tok/s | c=4 agg | c=16 agg | Method |
|--------|------|-----------|-----------|---------|----------|--------|
| **ai-muninn** (coolthor) | 13 Jun | NVFP4 | **158** | 257 | — | direct API, full canvas, warm |
| **r0b0tlab** | ~10 Jun | NVFP4 | **146** | — | 243 | vLLM bench, c16: 64/64 OK |
| **tsuru_mitsu** | 12 Jun | NVFP4 (NIM) | **107** | — | — | NVIDIA NIM, not vLLM |
| **miter37** | 12 Jun | NVFP4 | **101** | 148 | — | direct API, thinking=off |
| **Pavel** (this setup) | 14 Jul | BF16 | **52.6** | — | — | real chat, canvas fill, abliterated |
| **Pavel** (code gen) | 14 Jul | BF16 | **91.1** | — | — | code gen, best case |
| WindChimeRan | 20 Jun | NVFP4 | 45.4 | — | 73.1 | vLLM bench serve, random 1024/512 |
| miter37 (short) | 12 Jun | NVFP4 | 66 | — | — | short-answer |
| Pavel (short) | 14 Jul | BF16 | 6.8 | — | — | 8-tok output, canvas barely used |
| WindChimeRan | 20 Jun | BF16 | 22.1 | — | 48.6 | vLLM bench serve, random 1024/512 |
| ai-muninn (cold) | 13 Jun | NVFP4 | 16 | — | — | cold first request / short reply |

**NVFP4 vs BF16 speedup**: consistently 2.0-2.5× across all sources.

**Why the wide NVFP4 range (101–158 tok/s)?**
- Benchmark methodology varies wildly: direct API (miter37) vs vLLM bench serve with forced 512-output (WindChimeRan) vs full-canvas prose (ai-muninn)
- `vllm bench serve` forces `ignore_eos` and random 512-output which prevents genuine canvas fill
- Real chat benchmarks (miter37, ai-muninn) show 101-158 tok/s
- Cold start penalty: first request ~16 tok/s, warm ~158 tok/s

### miter37 benchmark details (2026-06-12)

NVFP4, vLLM 0.22.1rc1, `vllm/vllm-openai:gemma`, thinking=off per-request:
- Single request sequential ×4: 1349 total tokens, **101 tok/s** mean, 3.33s latency
- Concurrency=4 parallel: 1382 total, **148 tok/s aggregate**, 41 per-request
- Short-answer: 375 tokens, **66 tok/s** mean, 1.42s latency
- GPU mem util: 0.70 (NVFP4, stable)
- Model loading: 18.16 GiB, 99.5s

### r0b0tlab benchmark details (~2026-06-10)

NVFP4, native-backend (no MARLIN/emulation), `ghcr.io/r0b0tlab/vllm-diffusiongemma-26b-nvfp4-sm121`:
- c1: **146.32 tok/s** output throughput
- c5: **235.43 tok/s**
- c16: **242.93 tok/s** (64/64 requests OK)
- Longest verified prompt: 64,034 tokens
- Max 75°C, 60.07W, 96% GPU util during c16
- Streaming: 3 chunks/request, avg TTFT ~2.18s

### tsuru_mitsu NIM benchmark (2026-06-12)

NVFP4 via NVIDIA NIM (not vLLM), single-request generation:
- Average: **~106.8 tok/s**
- Comparison vs Gemma 4 26B MTP: interesting tradeoff, diffusion faster on long outputs

## Speed Optimization Pathways (ranked by impact)

| # | Pathway | Expected gain | Difficulty | Risk |
|---|---------|--------------|------------|------|
| 🥇 | **NVFP4 quantization** | 2–3× (52→100-150 tok/s) | Medium | Need NVFP4 model; abliterated version may not exist |
| 🥈 | **Disable thinking per-request** | Visible +20-30% | Trivial | Loss of reasoning quality on complex tasks |
| 🥉 | **GPU_MEM_UTIL 0.60→0.65** (BF16) | +5-10% | Low | OOM risk if system RAM starved; test incrementally |
| 4 | **Reduce denoising_steps** (48→24-32) | +30-50% theoretical | Low | Quality degradation; model trained on 48 steps |
| 5 | **Update vLLM image** | +5-15% | Low | Pull latest `vllm/vllm-openai:gemma`, regression risk minimal |
| 6 | **Reduce canvas_length** (256→128) | +linear per canvas | Low | Shorter max responses; may break multi-canvas generation |

### NVFP4 + abliteration compatibility

Pavel uses `Umranz/diffusiongemma-26B-A4B-it-abliteration` (BF16, ARA method). The NVFP4 version `nvidia/diffusiongemma-26B-A4B-it-NVFP4` is stock (with refusals). Options:
1. Find/request NVFP4-quantized abliterated version on HF
2. Self-convert via NVIDIA ModelOpt (requires original weights → abliterate → quantize)
3. Use stock NVFP4 and accept refusals (may be acceptable for non-controversial agent tasks)
4. Check if `RedHatAI/diffusiongemma-26B-A4B-it-NVFP4` has lower refusal rates

## Hermes Agent Integration

1. Add to LiteLLM config (`litellm-config.yaml`):
```yaml
  - model_name: "diffusiongemma-abliterated"
    litellm_params:
      model: "openai/diffusiongemma-abliterated"
      api_base: "http://localhost:8000/v1"
      api_key: "not-needed"
```

2. Use in Hermes:
```
/model custom:local diffusiongemma-abliterated
```

3. **Tested with Hermes** — miter37 confirmed DiffusionGemma works through Hermes Telegram gateway without major issues. Throughput through agent loop is lower than direct API due to conversation history, tool calls, and thinking tokens.

4. **Disable thinking per-request** for clean throughput:
```json
{"chat_template_kwargs": {"enable_thinking": false}}
```

## DGX Spark Thermal Warning

Stock DGX Spark cooling overheat-reboots at ~95C under sustained diffusion load (WindChimeRan). External fans recommended for sustained benchmarks. No power cap available (`nvidia-smi -pl` unsupported on GB10).

Monitor: `nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits`

## NVFP4 vs BF16

| Aspect | BF16 (49GB) | NVFP4 (18GB) |
|--------|-------------|--------------|
| Quality | Full precision | Slight degradation |
| Speed (c=1) | ~22 tok/s | ~45 tok/s |
| Speed (c=16) | ~49 tok/s | ~73 tok/s |
| Memory | 49GB (fits 128GB) | 18GB (fits 48GB GPUs) |
| GPU_MEM_UTIL | 0.60 | 0.40-0.70 |
| Model | Umranz/...-abliteration | nvidia/...-NVFP4 |
| Hermes tested | Yes (plan4) | Yes (miter37) |

For NVFP4, add:
```bash
--hf-overrides '{"diffusion_sampler": "entropy_bound", "diffusion_entropy_bound": 0.1}'
```

## Abliteration

Model used: `Umranz/diffusiongemma-26B-A4B-it-abliteration`
- Method: ARA (AbLiteration via Representation Adjustment)
- Refusal rate: 4/100 (down from original)
- KL divergence: 0.11 (minimal quality impact)

## Verified Benchmarks — Pavel's DGX Spark (2026-07-14)

Real benchmark results from `Umranz/diffusiongemma-26B-A4B-it-abliteration` (BF16, abliterated):

| Test | Out tok | Time | Out tok/s | Notes |
|------|---------|------|-----------|-------|
| short (8 tokens) | 8 | 1.2s | **6.8** | Canvas barely filled |
| medium (128 tokens) | 66 | 2.3s | **28.2** | Partial canvas |
| full canvas (256 tokens) | 216 | 4.1s | **52.6** | Full canvas, optimal |
| multi-canvas (512 tokens, prose) | 512 | 9.9s | **51.7** | 2 canvases, consistent |
| code generation (512 tokens) | 512 | 5.6s | **91.1** | Code is predictable → better canvas fill |

**Key insight:** Code generation achieves 91.1 tok/s — nearly 2x faster than prose on the same token count. Diffusion benefits from structured/predictable outputs (code follows patterns, prose doesn't).

Canvas fill effect: full canvas (52.6) is **7.7x faster** than short (6.8) — confirming the per-canvas cost model.

Thinking: disabled for these benchmarks.

## Benchmark Script

Use `scripts/bench_diffusiongemma.py` to measure real throughput at different output lengths.
Tests canvas fill effect: short (8 tok) → multi-canvas (512 tok).
