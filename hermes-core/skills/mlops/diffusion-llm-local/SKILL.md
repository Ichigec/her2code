---
name: diffusion-llm-local
description: Deploy, fine-tune, and optimize diffusion-based LLMs (DiffusionGemma, LLaDA, Dream, Nemotron) locally — vLLM/Unsloth/llama.cpp deployment, ddm-sft/CART fine-tuning, Fast-dLLM/Optimus/DFlash inference optimization, AR→diffusion conversion (I-DLM, Nemotron tri-mode, TwoTower, DiffuLLaMA), VRPO alignment, open-source diffusion LLM landscape.
---

# Diffusion LLM — Local Deployment

## When to use
User wants to run a diffusion-based (non-autoregressive) language model locally — DiffusionGemma, Edwixx Diffusion, or any GGUF with `diffusion-gemma` architecture.

## Architecture
Diffusion LLMs use block-diffusion decoding (parallel, not token-by-token). Standard `llama.cpp` does NOT support them — the architecture is `diffusion-gemma`, which fails with:
```
error loading model: unknown model architecture: 'diffusion-gemma'
```

Support exists only in **PR #24423** (unmerged as of 2026-06). Two approaches:

| Binary | What it does | Can it serve? |
|--------|-------------|---------------|
| `llama-diffusion-cli` | Interactive CLI chat (like `llama-cli`) | No HTTP |
| `llama-server` (PR build) | Loads model, OpenAI API | **Loads but inference fails** — "context does not logits computation" |
| `llama-diffusion-gemma-server` | Low-level logits server (stdin binary protocol) | Not directly |

**Correct approach**: Python FastAPI wrapper around `llama-diffusion-cli` → OpenAI-compatible `/v1/chat/completions` → LiteLLM.

## Deployment options (3 paths)

| Method | VRAM min | Streaming | Notes |
|:-------|:---------|:----------|:------|
| **vLLM** (recommended) | ~18GB (4-bit) | ❌ | Native support, OpenAI API, easiest |
| **Unsloth** | ~18GB (4-bit) | ❌ | Memory-efficient, fine-tuning support |
| **llama.cpp PR #24423** | ~48GB (FP16) | ❌ | Custom build, GGUF only, most hackable |

### Path A: vLLM (recommended, simplest)

**Use the official Docker image** `vllm/vllm-openai:gemma` — it has DiffusionGemma support built in. Do NOT use `vllm/vllm-openai:gemma4` (lacks diffusion support). A bare `pip install vllm` may work but the Docker image is the tested path.

**Critical flags** (researched for DGX Spark GB10, see `references/diffusiongemma-vllm-dgx-spark.md` for full details and sources):

```bash
VLLM_USE_V2_MODEL_RUNNER=1 \
vllm serve google/diffusiongemma-26B-A4B-it \
  --trust-remote-code \
  --dtype auto \
  --max-model-len 100000 \
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
  --host 0.0.0.0 --port 8000
```

**Flag rationale:**
- `VLLM_USE_V2_MODEL_RUNNER=1` — REQUIRED for diffusion model runner path (without it, model loads but inference fails)
- `--diffusion-config` — replaces the old `--diffusion-steps` flag. Sets canvas (parallel token block) and denoising iterations. Values from model's `generation_config.json`.
- `--attention-backend TRITON_ATTN` — optimal for GB10 bidirectional attention. Do NOT use `--enforce-eager` (disables CUDA graph capture, kills performance).
- `--tool-call-parser gemma4` / `--reasoning-parser gemma4` — Gemma 4 native parsers for tool calling and thinking mode.
- `--override-generation-config '{"max_new_tokens": null}'` — model defaults to `max_new_tokens: 256` (one canvas). Override to allow multi-canvas responses.
- `--max-num-seqs 4` — HARD LIMIT. DiffusionGemma uses per-sequence state buffers; more than 4 causes OOM in state memory.
- `--gpu-memory-utilization 0.60` — BF16 on GB10. **0.70+ starves system RAM → swap thrash** (WindChimeRan benchmark, 2026-06-20). GB10 unified memory: 0.70×121GB=85GB leaves only 36GB for OS+Docker, barely enough. 0.60=72GB → model 49GB + KV ~18GB, system gets 49GB.
- `--max-model-len` — user preference: 262144 (full context). Can reduce to 100000 for more KV cache headroom.

**Docker launch** (recommended for DGX Spark):
```bash
docker run -itd --name diffusiongemma \
  --ipc=host --network host --gpus all \
  -e VLLM_USE_V2_MODEL_RUNNER=1 \
  -v /path/to/model:/models/diffusiongemma:ro \
  vllm/vllm-openai:gemma \
  --model /models/diffusiongemma \
  --served-model-name diffusiongemma \
  --trust-remote-code --dtype auto \
  --max-model-len 100000 --max-num-seqs 4 \
  --max-num-batched-tokens 8192 \
  --gpu-memory-utilization 0.60 \
  --diffusion-config '{"canvas_length": 256, "max_denoising_steps": 48}' \
  --attention-backend TRITON_ATTN \
  --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4 \
  --override-generation-config '{"max_new_tokens": null}' \
  --default-chat-template-kwargs '{"enable_thinking": true}' \
  --mm-processor-kwargs '{"max_soft_tokens": 1120}' \
  --limit-mm-per-prompt '{"image": 7}' \
  -tp 1
```

**Runtime details** (from vLLM logs):
```
Architecture: DiffusionGemmaForBlockDiffusion
dtype: bfloat16
KV cache dtype: fp8_e4m3 (automatic)
Attention backend: TRITON_ATTN
Chunked prefill: enabled
Prefix caching: enabled
CUDA graph: FULL_AND_PIECEWISE (do NOT use --enforce-eager)
```

**Performance on DGX Spark (GB10)** — actual benchmarks (WindChimeRan, 2026-06-20, random 1024-in/512-out, CUDA graphs ON):

| Config | Conc. | Output tok/s | Aggregate tok/s | Source |
|--------|-------|-------------|-----------------|--------|
| BF16 (49GB) | 1 | **22.1** | 66 | WindChimeRan |
| BF16 (49GB) | 16 | **48.6** | 146 | WindChimeRan |
| NVFP4 (18GB) | 1 | **45.4** | 136 | WindChimeRan |
| NVFP4 (18GB) | 16 | **73.1** | 219 | WindChimeRan |
| NVFP4 (18GB) | 1 | 101–158 | 148–257 | miter37 / ai-muninn |

**Verified BF16 benchmarks (Pavel's DGX Spark, 2026-07-14, abliterated model):**

| Test | Out tok | Time | Out tok/s | Notes |
|------|---------|------|-----------|-------|
| short (8 tokens) | 8 | 1.2s | **6.8** | Canvas barely filled |
| medium (128 tokens) | 66 | 2.3s | **28.2** | Partial canvas |
| full canvas (256 tokens) | 216 | 4.1s | **52.6** | Full canvas, optimal |
| multi-canvas (512 tokens, prose) | 512 | 9.9s | **51.7** | 2 canvases, consistent |
| code generation (512 tokens) | 512 | 5.6s | **91.1** | Code predictable → 1.8x faster than prose |

**Code generation speed bonus:** Code hits 91.1 tok/s vs prose 51.7 tok/s — nearly 2x. Diffusion benefits from structured/predictable outputs. Canvas fill ratio: full canvas 7.7× faster than short answer.

**Why the wide NVFP4 range (101–158)?** Diffusion tok/s "lies" — it's per-canvas, not per-token:
- A 256-token answer and an 8-token answer cost ~same wall-clock (48 denoising steps per canvas)
- Short answer (8 tokens): canvas barely filled → low tok/s (~16 tok/s)
- Full canvas (256 tokens): canvas fully utilized → peak tok/s (~158 NVFP4, ~60 BF16)
- For agent tasks (long reasoning/code): canvases fill naturally → higher effective tok/s
- Benchmark with `bench_diffusiongemma.py` script to measure real throughput

**DGX Spark thermal**: stock cooling overheat-reboots at ~95°C under sustained diffusion load. Monitor: `nvidia-smi --query-gpu=temperature.gpu`. External fans recommended for sustained benchmarks.

**Speed optimization pathways** (ranked): NVFP4 quantization (2-3×) → disable thinking per-request (visible +20-30%) → GPU_MEM_UTIL tuning (+5-10%) → reduce denoising_steps (quality risk) → update vLLM image. See `references/diffusiongemma-vllm-dgx-spark.md#speed-optimization-pathways-ranked-by-impact` for full analysis with expected gains, difficulty, and risks for each pathway.

**Disable thinking per-request** (for speed benchmarks):
```json
{"chat_template_kwargs": {"enable_thinking": false}}
```

**NVFP4 alternative** — if BF16 doesn't fit or for higher throughput:
```bash
vllm serve nvidia/diffusiongemma-26B-A4B-it-NVFP4 \
  --hf-overrides '{"diffusion_sampler": "entropy_bound", "diffusion_entropy_bound": 0.1}' \
  ... (same flags as above)
```

See `references/diffusiongemma-vllm-dgx-spark.md` for full serve script, research sources, and Hermes agent integration notes.

### Path B: Unsloth (4-bit, lowest VRAM)

```python
from unsloth import FastDiffusionModel
model, tokenizer = FastDiffusionModel.from_pretrained(
    "google/diffusiongemma-26B-A4B-it",
    load_in_4bit=True,
)
# Min ~18GB RAM (VRAM + system). Supports fine-tuning.
```

### Path C: llama.cpp PR #24423 (full control, GGUF)

## Step-by-step (llama.cpp path)

### 1. Build the PR fork

```bash
cd /tmp
git clone --depth 1 https://github.com/ggml-org/llama.cpp llama-diffusion-build
cd llama-diffusion-build
git fetch origin pull/24423/head:diffusion-gemma
git checkout diffusion-gemma
cmake -B build -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=ON
cmake --build build -j$(nproc) --target llama-diffusion-cli
```

Binary at `build/bin/llama-diffusion-cli`.

**LoRA support**: `llama-diffusion-cli` supports `--lora FNAME` and `--lora-scaled FNAME:SCALE` for loading LoRA adapters at inference time. Confirmed working on build from PR #24423 (2026-07-14). Load multiple adapters with comma-separated paths. This enables RL-trained LoRA weights to be used directly without merging into the base model.

### 2. Create the Python wrapper

Use the reference server script (`references/diffusion-server.py`). Key points:
- Wraps `llama-diffusion-cli` as a subprocess (NOT `llama-server`)
- Provides `/health`, `/v1/models`, `/v1/chat/completions`
- Single-inference semaphore (diffusion models use full GPU)
- Converts OpenAI chat messages to Gemma prompt format
- Parses diffusion CLI output to extract clean response

Env vars for configuration:
```bash
DG_MODEL_PATH=/path/to/model.gguf
DG_BINARY=/path/to/llama-diffusion-cli
DG_NGL=99           # GPU layers
DG_CTX_SIZE=65536   # context size
DG_PORT=8646
DG_MODEL_NAME=diffusion-gemma-26b
DG_DEFAULT_STEPS=64 # diffusion steps (fewer=faster, more=better)
```

### 3. Start with watchdog

Background processes die on shell exit. Use a startup script with health-check loop:

```bash
#!/bin/bash
# Export env vars, launch server, wait for /health to respond
$VENV_PYTHON $SERVER_SCRIPT >> $LOG 2>&1 &
for i in $(seq 1 30); do
    sleep 2
    curl -s http://localhost:$PORT/health && exit 0
done
exit 1
```

### 4. Add to LiteLLM config

```yaml
  - model_name: "diffusion-gemma-26b-heretic"
    litellm_params:
      model: "openai/diffusion-gemma-26b"
      api_base: "http://host.docker.internal:8646/v1"
      api_key: "not-needed"
      request_timeout: 900
      max_retries: 0
```

Then `docker restart litellm`.

### 5. Use

```
/model diffusion-gemma-26b-heretic
```

## Model format notes

- Only **FP16/BF16 GGUF** works with current PR. Quantized versions (Q4_K_M etc.) may fail.
- `edwixx__diffusiongemma-26B-A4B-it-HERETIC-Uncensored-FP16.gguf` — 48 GB, worked.
- Diffusion steps: 32–128. Fewer = faster (17s for 32 steps), more = better quality.
- Context: model reports `n_ctx_train=262144`, but VRAM limits practical context. 65K worked on 124GB GPU. Use `--n-gpu-layers 99` to load all layers on GPU.

## Performance

### GPU (DGX Spark / Jetson GB10, vLLM)

See `references/diffusiongemma-vllm-dgx-spark.md` for full benchmarks. Highlights:
- BF16: 22–53 tok/s (real, 1–16 concurrent)
- NVFP4: 45–158 tok/s (2-3× faster)
- Code generation: 91 tok/s (structured output benefits diffusion)

### CPU (llama.cpp PR #24423, no GPU)

On 20-core ARM64 with 48GB FP16 GGUF. **Diffusion steps are the dominant cost factor** — halving steps roughly halves generation time:

| diffusion_steps | max_tokens | Time | Notes |
|:----------------|:-----------|:-----|:------|
| 8 | 64 | **~32s** | Fast, usable for RL data collection |
| 16 | 128 | **~4 min** | Standard phase 1, ~24GB RSS |
| 32 | 128 | ~8 min (est.) | Phase 2 |
| 64 | 256 | ~16 min (est.) | Phase 3 |

Model resident memory: ~24 GB RSS (virtual ~113 GB due to memory mapping). Full RL training timing and launch gotchas: see `references/diffusiongemma-cpu-rl-launch.md`.

## Quality gap awareness

DiffusionGemma trades quality for speed. On ALL public benchmarks it scores **-5 to -20 percentage points** below Gemma 4 26B-A4B (AR). Google's own framing: "trails standard Gemma 4 on every public benchmark." Use AR Gemma 4 for quality-critical workloads (math proofs, production code). Use DiffusionGemma for speed-first workloads (agents, voice, real-time).

**Exception — Nemotron-Labs-Diffusion**: joint AR+diffusion training (α=0.3) produces diffusion models that **EXCEED AR quality** (+1.2% over Qwen3-8B on 10 benchmarks). I-DLM 8B also matches AR across 15 benchmarks. The quality gap is NOT inherent to diffusion — it stems from training method. Nemotron ablation (arXiv:2607.05722): AR loss contributes +7.48%, two-stage training +5.74%, out of +16.05% total improvement over baseline.

Key gap areas: MMLU Pro (-10..15), AIME (-15..20), LiveCodeBench (-10..15), GPQA (-5..10).

## Thinking mode

DiffusionGemma supports Gemma 4-style thinking mode — add the thinking token at the start of the system prompt. The model emits an internal reasoning channel followed by the final answer. Audit by Google showed **intermediate diffusion steps are interpretable** — they recover many benefits of CoT automatically, even without explicit thinking mode.

## Fine-tuning diffusion LLMs

Three approaches, from cheapest to most expensive:

| Method | Tool | Cost | Use case |
|:-------|:-----|:-----|:---------|
| LoRA + ddm-sft | Unsloth / LLaMA-Factory | 4-8 GPU-hours | Domain adaptation |
| Hackable Diffusion | Google JAX toolbox | 10-50 GPU-hours | Research, custom tasks |
| CART retraining | Custom | 20-50 GPU-hours | Quality improvement |

### ddm-sft (Discrete Denoising Model SFT)

Replaces next-token prediction with mask-and-denoise objective. Standard SFT method for diffusion LLMs:

1. Randomly mask fraction t∈[0,1] of tokens in target response
2. Forward pass with bidirectional attention
3. Loss: predict masked tokens (cross-entropy on masked positions only)

LoRA target modules: attention layers (q_proj, v_proj, k_proj, o_proj). Do NOT target diffusion head.

### Hackable Diffusion (Google official recipe)

Google's JAX modular toolbox. Uses **D3PM-uniform corruption** (not simple masking) for better post-fine-tune quality. Reference: Sudoku Solver recipe in google-deepmind/gemma repo.

### CART (Context-Adaptive Token-Level Noise Rescheduling)

From Dream 7B. Instead of uniform masking probability, estimate per-token contextual informativeness and assign less noise to easy tokens (rich context) and more to hard tokens. Yields +5-10% on reasoning benchmarks. See `references/diffusion-llm-improvement.md` for details.

## Inference optimization (training-free)

| Technique | Speedup | Quality cost | How |
|:----------|:--------|:-------------|:-----|
| **Fast-dLLM v2** (ICLR'26) | 2.5× over AR | <2% | Hierarchical KV cache (block-level + sub-block) |
| **Fast-dLLM v1** | up to 27.6× | <2% | Approximate block-wise KV-cache for full-seq diffusion |
| **S2D2** (Mar'26) | 4.7× | ~0% | Training-free self-speculation (same model, block=1 as verifier) |
| **AdaBlock-dLLM** (ICLR'26) | +10-20% TPF | +2-3% quality | Semantic-aware adaptive block size, training-free |
| **Trained sampler** (Nemotron) | +2-3× TPF | +3-5% accuracy | Lightweight classifier predicts top-1 correctness |
| **Optimus** | up to 3.2× | variable | Elastic decoding: adapt granularity to runtime load |
| **TEAM** | MoE-specific | minimal | Delayed caching for decoded tokens in MoE models |
| **Steps tuning** | linear | tradeoff | 32 steps ≈ 85% quality, 64 ≈ 95%, 128 ≈ 99% |

Fast-dLLM v2 (NVIDIA Labs, ICLR 2026): block-diffusion with hierarchical caching. GitHub: NVlabs/Fast-dLLM.
S2D2: same model as drafter (block_size>1) and verifier (block_size=1=AR). Paper: arXiv:2603.25702.
AdaBlock-dLLM: aligns block boundaries with semantic steps via "Volatility Band" analysis. GitHub: lgxi24/AdaBlock-dLLM.
Trained sampler: Nemotron SOL analysis shows 7.60× TPF theoretical ceiling — confidence sampling uses only ~30%. See `references/diffusion-llm-improvement.md` for SOL analysis.

## Diffusion-accelerated AR inference (DFlash)

DFlash (ICML 2026, Z-Lab) uses a **lightweight block-diffusion model as a draft model** for speculative decoding of any AR LLM. The target model stays UNCHANGED — no conversion needed. The diffusion drafter generates an entire block of 16 tokens in a single parallel forward pass, then the AR target verifies them.

| Metric | DFlash | EAGLE-3 (SOTA AR spec) | Native MTP |
|:-------|:-------|:----------------------|:-----------|
| Speedup (greedy) | **4.5–6.1×** | 1.8–2.2× | 2–3× |
| Speedup (temp=1) | 3.5–4.5× | 1.6–1.9× | — |
| Acceptance length (τ) | 6.5–7.9 | 3.0–3.5 | — |
| Lossless? | ✅ | ✅ | ✅ |
| Retrain target? | ❌ | ❌ | ❌ |
| Draft model size | ~5 layers (~200-400M) | 1 layer (~100M) | built-in |

**Ready-made draft models** (HuggingFace `z-lab/`): Gemma-4-31B-it, Gemma-4-26B-A4B-it, Qwen3.5-{4B,9B,27B,35B-A3B,122B-A10B}, Qwen3.6-{27B,35B-A3B}, Qwen3-{4B,8B,Coder-30B-A3B}, LLaMA-3.1-8B, gpt-oss-{20b,120b}, Kimi-K2.5/K2.6, MiniMax-M2.5/M2.7.

**Backends**: vLLM (v0.20.1+), SGLang, Transformers, MLX (Apple Silicon).

See `references/dflash-block-diffusion-speculative.md` for deployment commands, benchmark tables, and DGX Spark estimates.

## AR → Diffusion conversion

Any pretrained AR LLM (Qwen, LLaMA, GPT-2) can be converted to a diffusion model. Seven proven approaches with cost estimates and recipes in `references/ar-to-diffusion-conversion.md`. Key frameworks:

- **I-DLM** (Apr 2026) — BEST knowledge preservation. LoRA, 4.5B tokens, matches AR quality across 15 benchmarks. Keeps causal attention.
- **Nemotron-Labs-Diffusion** (May 2026) — tri-mode (AR/diffusion/self-spec), one checkpoint, switch attention only. Open weights 3B/8B/14B.
- **Nemotron-Labs-TwoTower** (Jul 2026) — frozen AR backbone + trainable denoiser. 98.7% quality, 2.42× speedup.
- DiffuLLaMA (ICLR 2025), Open-dLLM, Dream 7B, LLaDA 2.0 (scales to 100B).
- **DreamReasoner-8B** (Jun 2026) — block-size curriculum learning for long-CoT reasoning on Qwen3-8B-Base. Large training blocks hurt reasoning; curriculum (fine→coarse) fixes this. ≈ Qwen3-8B-Thinking quality.
- **DiffuCoder 7B** (Jun 2025, Apple+HKU) — code-specialized masked diffusion + coupled-GRPO. +4.4% on EvalPlus.
- **NBDiff-7B** (Dec 2025, Huawei/Pangu) — context-causal masking + block-growth. SOTA 7B DLM (GSM8K 79.6%). Paper: arXiv:2512.06776.
- **Efficient-DLM** (Dec 2025, NVIDIA) — foundational conversion method. Key findings: block-wise attention with clean context (+19% over bidirectional), no token shift, position-dependent masking. Basis for Nemotron-Labs-Diffusion. Paper: arXiv:2512.14067.

See `references/dense-diffusion-llm-landscape.md` for full model comparison (dense vs MoE vs closed, July 2026).

## Alignment for diffusion LLMs

Standard DPO/RLHF does NOT work — diffusion has no exact log-likelihood, only ELBO estimate with high variance. Methods:

- **VRPO** (Variance-Reduced Preference Optimization, LLaDA 1.5): control variate for ELBO variance reduction. +8-12 pp on alignment benchmarks.
- **ELBO-KTO** (Oct 2025): unpaired preference optimization — no pairwise data needed, only good/bad labels.
- **Coupled-GRPO** (Apple, DiffuCoder): diffusion-native RL with coupled sampling. +4.4% on EvalPlus (code).
- **Block-R1** (May 2026): dynamic block size RL — different domains have different optimal block sizes.
- **StableDRL** (2026): fixes reward collapse in diffusion RL via unconditional clipping + self-normalization.

See `references/diffusion-llm-improvement.md` for details and Nemotron training ablation data.

**Full RL alignment catalog** — compatibility matrix, DiffusionGemma-specific roadmap, StableDRL implementation plan, and all 5 proven methods: see `references/diffusion-llm-rl-alignment.md`.

**Anchored Self-Play + DES-MoE pipeline** — concrete 12-day training loop combining adversarial Code-vs-Test self-play with 3-phase MoE freezing: see `references/diffusiongemma-anchored-sp-desmoe-pipeline.md`. Working implementation at `/home/user/dev/rldiffusion/`.

**VRPO fallback for llama.cpp** — when `llama-diffusion-cli` only returns text (no logits), use reward-based VRPO instead of ELBO-based StableDRL: see `references/vrpo-fallback-for-llama-cpp.md`.

## Diffusion LLMs as Speculative Drafters for AR Models

Beyond DFlash (purpose-built diffusion drafter, covered above), two research approaches use general diffusion LLMs as draft models for AR targets:

| Method | Training? | Speedup | Key Constraint |
|:-------|:----------|:--------|:---------------|
| **DEER** (arXiv:2512.15176, Dec 2025) | Yes (2-stage) | 5.54x on Qwen3-30B-A3B | Trains 0.5B dLLM under target's tokenizer |
| **DiffuSpec** (arXiv:2510.02358, Sep 2025) | No | 3x | Requires shared tokenizer between DLM and AR target |

**Critical constraint**: Diffusion LLM and AR target MUST share the same tokenizer. Cross-family pairs (e.g., DiffusionGemma → Qwen) are blocked by vocabulary mismatch (262,144 vs 248,320 token IDs). DEER solves this by training its 0.5B draft from scratch on the target's tokenizer. DiffuSpec requires a pre-existing tokenizer match.

See `speculative-decoding` skill → `references/cross-architecture-speculative-decoding.md` for full analysis.

## Post-training RL compatibility

For methods originally designed for AR MoE (GRPO, self-play, adversarial distillation), see `references/posttraining-methods-compatibility.md` — compatibility matrix of 9 post-training methods with DiffusionGemma, including the critical StableDRL→RO-GRPO dependency chain and DiffusionGemma-specific bonuses.

## Support files

- `references/posttraining-methods-compatibility.md` — Compatibility analysis: 9 post-training methods (RO-GRPO, GAD, DES-MoE, Synergistic Reg., G-OPD, Anchored Self-Play, Agent Distillation, TCOD, Mistake Book) evaluated for DiffusionGemma. Tiered by architecture dependence.
- `references/diffusiongemma-vllm-dgx-spark.md` — Optimal vLLM serve parameters for DiffusionGemma on DGX Spark (GB10): full Docker launch script, flag rationale, NVFP4 vs BF16 comparison, Hermes agent integration, research sources
- `templates/serve_diffusiongemma.sh` — Production-ready launch script with memory/temperature checks, variable config, health-check loop. Copy to `~/models/` and run.
- `references/diffusion-server.py` — Full FastAPI OpenAI-compatible wrapper (copy and configure env vars)
- `references/diffusion-llm-improvement.md` — Comprehensive improvement map: Nemotron training ablation (arXiv:2607.05722), SOL analysis (7.60× ceiling), CART, VRPO, ELBO-KTO, Coupled-GRPO, Block-R1, StableDRL, DoT, token editing, Fast-dLLM v2, S2D2, AdaBlock-dLLM, trained sampler, Optimus, TEAM, Super Data Learners, scaling laws, scaling roadmap
- `references/diffusion-llm-rl-alignment.md` — Complete RL alignment reference: core problem (why standard RL fails on dLLMs), 5-method catalog (VRPO, StableDRL, Coupled-GRPO, Block-R1, ELBO-KTO) with paper links/code/results, DiffusionGemma compatibility matrix, 4-phase practical roadmap, StableDRL implementation plan for llama.cpp PR #24423
- `references/diffusiongemma-anchored-sp-desmoe-pipeline.md` — Anchored Self-Play + DES-MoE concrete pipeline: architecture, 12-day phase schedule, self-play loop details, diffusion-specific advantages, risk analysis. Links to working implementation at `/home/user/dev/rldiffusion/`.
- `references/ar-to-diffusion-conversion.md` — 8 conversion approaches (DiffuLLaMA, LLaDA 2.0, Dream 7B, ZAYA1-8B, Open-dLLM, I-DLM, Nemotron, NBDiff-7B) with recipes, cost estimates, Efficient-DLM ablation findings, and selection guide
- `references/dense-diffusion-llm-landscape.md` — Full landscape of dense vs MoE vs closed diffusion LLMs (July 2026), architecture comparison, DGX Spark selection guide
- `references/dflash-block-diffusion-speculative.md` — DFlash (ICML 2026): block diffusion draft model for AR speculative decoding. Speedup tables, deployment commands (vLLM/SGLang/MLX), Gemma 31B/Qwen3 DGX Spark estimates, comparison with EAGLE-3/MTP
- `references/llm-inference-acceleration.md` — Complete taxonomy of LLM inference acceleration: speculative decoding (EAGLE-3, Medusa, MTP, FastMTP), KV cache optimization, chunked prefill, quantization, system-level methods
- `references/diffusiongemma-cpu-rl-launch.md` — CPU inference timing data (4 min/gen), background process debugging (bash wrapper SIGTERM fix), resource limiter pattern, training step estimates (~4.5 days for 100 steps), LoRA/logits confirmation
- `scripts/start-diffusion.sh` — Startup script with health-check watchdog
- `templates/run_all_combined_launcher.py` — Combined launcher: server as Popen + training as subprocess.run in one process (prevents Hermes from killing server between turns)

## Pitfalls

- **`--diffusion-steps` flag is WRONG** — use `--diffusion-config '{"canvas_length": 256, "max_denoising_steps": 48}'` instead. The old `--diffusion-steps` flag is not recognized by current vLLM versions. Values come from the model's `generation_config.json`.
- **`VLLM_USE_V2_MODEL_RUNNER=1` is REQUIRED** — without it, DiffusionGemma loads but inference fails. This env var enables the v2 model runner path that supports diffusion decoding.
- **Do NOT use `--enforce-eager`** — it disables CUDA graph capture (`FULL_AND_PIECEWISE` mode), killing performance. The vLLM compile + CUDA graph path is essential for DiffusionGemma throughput.
- **`max-num-seqs` is a HARD LIMIT** — DiffusionGemma uses per-sequence diffusion state buffers. More than 4 causes OOM in state memory, not model weight memory. This is not tunable.
- **`max_new_tokens` defaults to 256** — the model's `generation_config.json` sets `max_new_tokens: 256` (one canvas). Use `--override-generation-config '{"max_new_tokens": null}'` to allow multi-canvas responses.
- **Use `vllm/vllm-openai:gemma` Docker image, NOT `:gemma4`** — the `:gemma` tag has DiffusionGemma support, `:gemma4` does NOT. Verify with `docker run --rm --entrypoint python3 vllm/vllm-openai:gemma -c "import vllm.model_executor.models.diffusion_gemma"`.
- **Thinking tokens inflate throughput measurements** — when benchmarking through an agent gateway, `enable_thinking: true` adds hidden reasoning tokens. Use `{"chat_template_kwargs": {"enable_thinking": false}}` per-request for clean throughput numbers.
- **🔴 CRITICAL: Thinking mode + large system prompts = EXTREME delays (350s+) on DiffusionGemma.** When `enable_thinking: true` is combined with a massive system prompt (plan2 orchestrator = ~15K+ tokens), the model generates hundreds of thinking tokens across multiple canvases before producing any visible output. Each canvas costs 48 denoising steps at ~25 tok/s → 2-3 canvases of thinking = 60-90 seconds of hidden generation. With multi-turn conversation context growing, this compounds to 350+ seconds. **Do NOT use thinking mode on DiffusionGemma with heavy presets.** Disable via `--default-chat-template-kwargs '{"enable_thinking": false}'` or per-request. **Case study:** session `20260714_224339_0e8a46` — user waited 350s (5 min 50 sec) for a tool-call response; model was generating thinking tokens across canvases. Diagnosis: check vLLM Docker logs for `Denoising steps` counts vs zero `Committed` tokens, and journalctl for gateway SIGKILL/restart events. Full diagnostic pipeline in `hermes-api-troubleshooting` → `references/diffusion-timeout-case-study.md`.
- **PR #24423 is NOT merged** — requires building from the PR branch.
- **`llama-diffusion-cli` does NOT return logits** — only text output. For RL training that needs ELBO estimates (StableDRL, VRPO), the Python wrapper (`diffusion-server.py`) only returns generated text via `/v1/chat/completions`. **Workaround**: use reward-based VRPO (no logits needed) instead of ELBO-based methods. The `vrpo_update.py` module at `/home/user/dev/rldiffusion/scripts/vrpo_update.py` provides a drop-in reward-based policy optimizer that works with text-only outputs. See `references/diffusion-llm-rl-alignment.md` for the full VRPO method.
- **ARM64 sandbox — use native images**: Docker on ARM64 (Jetson/DGX Spark) runs AMD64 images via QEMU emulation → 10-20x slower. Use `arm64v8/python:3.12-slim` (not `python:3.12-slim`) for native ARM64 code execution. Pull once with `docker pull arm64v8/python:3.12-slim`.
- **Standard `llama-server` can't run diffusion inference** — model loads but chat completions fail
- **Diffusion models are NOT autoregressive** — no token-by-token streaming, response comes all at once
- **One inference at a time** — the diffusion loop uses the full GPU
- **Git checkout may fail** if `.git/FETCH_HEAD` is owned by root → `rm -f .git/FETCH_HEAD && git fetch` (no sudo needed)
- **Python wrapper process dies after ~5 min** without watchdog — Hermes kills background processes between turns. Use a single all-in-one launcher script (server as Popen + training as subprocess.run) to keep both alive. Do NOT set `timeout` parameter — it defaults to 180s for background and kills the process (exit code 143). Omit `timeout` entirely for long-running training. See `references/diffusiongemma-cpu-rl-launch.md` for the complete pattern, exit code reference, and debugging commands.
- **Transformers v5 API change** — `apply_chat_template()` returns a **dict** (BatchEncoding) in transformers ≥5.0, not a tensor. Code that does `input_ids = tokenizer.apply_chat_template(...)` then `input_ids.shape[1]` will crash with `AttributeError`. Fix: `inputs = tokenizer.apply_chat_template(...); input_ids = inputs['input_ids'] if isinstance(inputs, dict) else inputs`.
- **vLLM 0.25+ requires transformers ≥5.0** — vLLM 0.24+ removed transformers v4 support. If vLLM fails with `ImportError: Support for Transformers v4 is deprecated`, upgrade: `pip install --upgrade "transformers>=5.0"`. Qwen3.6 architecture (`qwen3_5`) also requires transformers v5+.
- **DFlash transformers backend** — when vLLM/SGLang unavailable, DFlash works via `draft.spec_generate(input_ids, target=target)`. Only Qwen3 and LLaMA-3.1 families supported. See `references/dflash-block-diffusion-speculative.md` for code.
- **Adding layers HURTS diffusion LLMs** — Depth Delusion (arXiv:2601.20994): beyond D_crit ∝ W^0.44, more layers increase loss despite more params. At 7B scale, 64-layer underperforms 32-layer. Width should grow 2.8× faster than depth (W* ∝ C^0.34 vs D* ∝ C^0.12). Do NOT scale diffusion LLMs by stacking layers — scale width instead, or use LayerNorm Scaling (NeurIPS 2025) to mitigate.
- **Diffusion LLMs have INVERTED layer dynamics vs AR** — Layer Collapse (arXiv:2605.06366): DLMs have redundant EARLY layers (not deep ones like AR), dominated by a single super-outlier channel. Pruning it causes total collapse (-83% on GSM8K). DLMs are 3-bit quantization robust (-1.8% vs AR's -64.7%). Optimal sparsity is inverted: sparse early layers for DLMs, sparse late layers for AR. See `references/diffusion-llm-improvement.md` for details.
