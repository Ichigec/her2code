---
name: speculative-decoding
description: "Accelerate LLM inference with speculative decoding: MTP (native multi-token prediction), EAGLE3 (trained draft models), n-gram/prompt-lookup, and DFlash. Method selection, deployment in vLLM/llama.cpp/SGLang, and EAGLE3 draft model training via vllm-project/speculators on single-GPU systems (DGX Spark)."
version: 1.0.0
author: Hermes Agent
license: MIT
tags: [speculative-decoding, EAGLE3, MTP, inference-acceleration, vLLM, llama.cpp, draft-model, speculators, MoE]
dependencies: [vllm>=0.18, speculators>=0.5.0]
platforms: [linux, macos]
metadata:
  hermes:
    tags: [speculative-decoding, EAGLE3, MTP, inference-acceleration, vLLM, llama.cpp, draft-model, speculators, MoE]
    related_skills: [serving-llms-vllm, llama-cpp, llm-finetuning-pipeline, obliteratus, local-model-serving]
---

# Speculative Decoding for LLM Inference Acceleration

Accelerate LLM token generation by 1.2×–6× with zero quality loss. A small/cheap predictor proposes multiple tokens, the target model verifies them in a single forward pass, and accepted tokens are committed while rejected ones are corrected.

## When to Use

- User wants to **speed up LLM inference** («ускорить ответы», «faster generation», «speed up tokens»)
- User asks about **EAGLE / EAGLE3 / speculative decoding**
- User wants to train a **draft model** for their LLM
- User asks about **MTP** (Multi-Token Prediction)
- User has a model with MTP heads and wants to enable them
- User wants to compare speculative decoding approaches
- Post-abliteration MTP acceptance rate degraded → need alternative (see `obliteratus` skill)

## Method Comparison — Decision Tree

| Method | Speedup | Training? | MoE? | Lossless? | Best For |
|---|---|---|---|---|---|
| **MTP (native)** | 1.2–1.7× | No (built-in) | ✅ Native | ✅ | Quick win on Qwen3.5+, DeepSeek-V3, Gemma 4 |
| **EAGLE3** | 2–6× | Yes (draft model) | ✅ via speculators | ✅ | Max speedup, production, any model |
| **N-gram / prompt-lookup** | 1.2–1.5× | No | ✅ | ✅ | Zero-config, RAG/repetitive output |
| **DFlash** | 2–3× (2.5× > EAGLE-3) | Yes (block-diffusion) | ✅ | ✅ | Parallel drafting, SGLang deployments |
| **Self-speculative** | 1.3–1.8× | No | ⚠️ | ✅ | Early-exit layers, llama.cpp lookup |

### Quick Decision

1. **Model has native MTP?** → Enable MTP first (zero effort, 1.2–1.7×). See MTP section below.
2. **Need >2× speedup?** → Train EAGLE3 draft model. See `references/eagle3-speculators-training.md`.
3. **No time to train?** → Try n-gram/prompt-lookup (zero training, works immediately).
4. **Post-abliteration MTP degraded?** → Train EAGLE3 on the abliterated model's hidden states. See `obliteratus` skill → MTP compatibility section.

## MTP (Multi-Token Prediction)

Native speculative decoding built into the model weights. No separate draft model needed — auxiliary prediction heads propose tokens directly.

### Models with Native MTP

| Model Family | MTP Head | Layers | Deploy |
|---|---|---|---|
| Qwen3.5 / Qwen3.6 | ✅ `model_mtp.safetensors` | ~15 | vLLM, llama.cpp, SGLang, MLX |
| DeepSeek-V3 | ✅ MTP module | — | vLLM, SGLang |
| Gemma 4 | ✅ MTP head | — | vLLM, llama.cpp |
| Agents-A1 (Qwen3.5-MoE base) | ✅ Grafted from Qwen3.6 | — | GGUF, MLX |

### Deploy MTP

**vLLM:**
```bash
vllm serve Qwen/Qwen3.6-35B-A3B \
  --speculative-config '{"method": "mtp", "num_speculative_tokens": 4}'
```

**llama.cpp (PR #22673, merged May 2026):**
```bash
llama-server -m model.gguf --mtp
```

### MTP Grafting (for models without native MTP)

If a model is based on Qwen3.5/3.6 architecture but doesn't ship MTP heads (e.g., fine-tunes, abliterated models), graft MTP from the base checkpoint:

```python
import torch
from transformers import AutoModelForCausalLM
base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3.6-35B-A3B")
target = AutoModelForCausalLM.from_pretrained("./your-model")
mtp_keys = [k for k in base.state_dict() if 'mtp' in k.lower()]
for key in mtp_keys:
    target.state_dict()[key] = base.state_dict()[key].clone()
target.save_pretrained("./your-model-mtp")
```

### Known MTP Models on HuggingFace

| Model | Format | Notes |
|---|---|---|
| `protoLabsAI/Agents-A1-MTP-GGUF` | GGUF | Agents-A1 + grafted MTP for llama.cpp |
| `tepirale/Ornith-Agents-A1-3.6-35B-A3B-MTP-GGUF` | GGUF | MTP graft from Qwen3.6-35B-A3B |
| `wang-yang/Agents-A1-MTPLX-Q4` | MLX | 4-bit for Apple Silicon |
| `unsloth/Qwen3.6-35B-A3B-NVFP4-Fast` | NVFP4 | Includes MTP module |

### MTP Acceptance Rate Degradation

SFT and abliteration shift the activation space, reducing MTP draft acceptance:

| State | Accept % | Speedup |
|---|---|---|
| Base model (native MTP) | ~76% | 1.7× |
| After abliteration (grafted MTP) | ~65–70% | 1.4–1.7× |
| After SFT + abliteration | ~55% | 1.3× |

**Fix:** Train EAGLE3 on the modified model's hidden states (see training reference).

## EAGLE3 (Extrapolation Algorithm for Greater Language-model Efficiency)

EAGLE-3 (arXiv:2503.01840, March 2025) trains a lightweight draft model (~0.4B params) that predicts future tokens using the target model's hidden states. Key innovation: Training-Time Test (TTT) — simulates the accept/reject process during training.

### How EAGLE3 Works

1. **Draft model** takes hidden states from target model's intermediate layers as input
2. Draft autoregressively proposes K future tokens
3. Target model verifies all K tokens in a single forward pass
4. Accepted tokens are committed; first rejected token is corrected; remaining drafts discarded
5. Process repeats — **lossless** (output distribution identical to autoregressive decoding)

### EAGLE3 vs MTP

| Criterion | MTP | EAGLE3 |
|---|---|---|
| Speedup | 1.2–1.7× | **2–6×** |
| Training required | No | Yes (draft model) |
| Separate model | No | Yes (~0.4B) |
| Customizable | Fixed heads | Tunable architecture, TTT steps |
| MoE compatible | ✅ Native | ✅ via speculators |
| Post-abliteration | Degrades | Retrain on new hidden states |

### EAGLE3 Engine Support

| Engine | EAGLE3 | Flag/Config |
|---|---|---|
| **vLLM** | ✅ Full | `--speculative-config` with eagle3 method | Primary training + inference engine |
| **llama.cpp** | ✅ b9723+ | `--spec-type draft-eagle3 -md draft.gguf` | Qwen3.5/3.6 support added in b9723 (Jul 2026). PR #18039 |
| **SGLang** | ✅ SpecForge | Full training + inference | |
| **TensorRT-LLM** | ✅ | Production support | |

### EAGLE3 and Context Length

**EAGLE3 draft models are context-length independent.** The draft model (1 layer) takes a single hidden state from the target model and predicts the next hidden state — it learns a *local* pattern (hidden_state[t] → hidden_state[t+1]), not long-range dependencies. The target model handles long context; the draft model just guesses the next step.

- Draft model's KV cache is 1 layer deep and does NOT grow with context length
- `position_ids` increment by +1 per TTT step — no position extrapolation issue
- Training with `--max-model-len 8192` produces a draft that works at 256K context at inference
- The only constraint on inference context length is the target model's capacity (e.g., Agents-A1 supports 262144)

This means: **train at 8192, deploy at 256K — the draft model doesn't care.**

### Pre-trained EAGLE3 Draft Models

| Draft Model | Target Architecture | Size | Notes |
|---|---|---|---|
| `nm-testing/Speculator-Qwen3-30B-MOE-VL-Eagle3` | Qwen3-30B MoE | 0.4B | Closest to Agents-A1 (same Qwen3 MoE arch) |
| `thoughtworks/MiniMax-M2.5-Eagle3` | MiniMax-M2.5 MoE | — | MoE proven |
| `wantsleep/OLMoE_1B_7B_Eagle3` | OLMoE 1B/7B MoE | — | MoE proven |
| `stevenabreu7/gpt-oss-120b-speculator.eagle3` | GPT-OSS-120B | — | Includes train.py reference |

**No pre-trained EAGLE3 exists for Agents-A1 directly.** Use the Qwen3-30B MoE draft as a starting point (same architecture family), or train from scratch.

### Deploy EAGLE3

**vLLM:**
```bash
vllm serve InternScience/Agents-A1 \
  --speculative-config '{
    "method": "eagle3",
    "model": "nm-testing/Speculator-Qwen3-30B-MOE-VL-Eagle3",
    "num_speculative_tokens": 4,
    "eagle_topk": 1
  }'
```

**llama.cpp:**
```bash
llama-server -m agents-a1.gguf -md eagle3-draft.gguf \
  --spec-type draft-eagle3 \
  --draft 4
```

### Training EAGLE3 Draft Models

Use the `vllm-project/speculators` framework (v0.5.0+). Full training workflow — including offline pattern for single-GPU systems like DGX Spark — is in `references/eagle3-speculators-training.md`.

**Quick summary:**
1. Prepare data (`scripts/prepare_data.py`)
2. Launch vLLM with hidden state extraction (`scripts/launch_vllm.py`)
3. Generate hidden states offline (`scripts/data_generation_offline.py`)
4. Stop vLLM (free GPU memory)
5. Train draft model (`scripts/train.py` with `--speculator-type eagle3`)
6. Deploy with vLLM or convert to GGUF for llama.cpp

**Training time:** ~10 min on 2×H100 (8B model), ~2–4h on DGX Spark (35B MoE model).

## Eagle3 + RL Training: Critical Interactions

Eagle3 and RL training have **dangerous interactions**. The ReSpec paper (arXiv:2510.26475, Oct 2025) identified three critical gaps when using Eagle3 during RL training. **Do NOT use Eagle3 for rollout generation during RL unless you have an online draft adaptation system (NeMo RL online mode, ReSpec, or TIDE).** DFlash is less dangerous but still degrades — see `references/eagle3-rl-interaction.md` → "DFlash + RL Analysis" for detailed comparison.

### The Three Gaps (ReSpec, arXiv:2510.26475)

**GAP 1: Diminishing speedup at large batch sizes.** RL training uses large batch sizes for rollout generation → GPU already near full utilization → marginal parallelism from SD is minimal → draft + verification overhead can *exceed* speedup. On single-GPU systems (DGX Spark), this is especially severe.

**GAP 2: Drafter staleness.** The actor (target model) updates every RL step. An Eagle3 draft trained on an earlier snapshot becomes misaligned → acceptance length **drops continuously** as RL training progresses. Within 50-100 RL steps, the draft may provide negligible speedup.

**GAP 3: Drafter-induced policy degradation (MOST DANGEROUS).** Although SD acceptance preserves the marginal token distribution at each step, variance of multi-token acceptance probability compounds **exponentially**:

```
Var[∏ p(t)/q(t)] = ∏(1 + D_χ²(p(t)||q(t))) - 1
```

This causes: (a) systematically impoverished trajectories, (b) shifted rollout distribution → degraded rewards, (c) misleading gradients to the RL optimizer → the model learns from corrupted data. ReSpec measured a **measurable drop in reward** on Qwen2.5-7B when naively applying EAGLE-3 during RL.

### Safe Alternatives for RL Generation Stage

| Method | Safe for RL? | Why |
|---|---|---|
| **n-gram / prompt-lookup** | ✅ Best choice | Zero training → never stale; activation-agnostic → no distributional bias |
| **NeMo RL online draft** | ✅ With infra | Trains draft alongside policy, refits both into vLLM. 1.8× rollout speedup on 8B. Needs Megatron backend. |
| **ReSpec** | ✅ (research) | Dynamic SD config + on-policy KD + reward-weighted drafter updates. 4.5× on Qwen 3B-14B. |
| **TIDE** | ✅ (serving) | Zero-overhead draft adaptation via reused hidden states. Async on separate GPU. |
| **Static DFlash (naive)** | ⚠️ LESS DANGEROUS | Degrades slower than EAGLE-3 (8 target layers, parallel drafting, diffusion denoising) but still stale. Avoid for RL rollout. |
| **Static Eagle3 (naive)** | ❌ DANGEROUS | Stale draft + policy degradation risk. Do NOT use during RL. |

### Correct Pipeline Ordering

```
Phase 1: Distillation (cloud teacher → student SFT/LoRA/BAdam)
         [Eagle3 NOT needed here — it trains on student hidden states, not teacher]

Phase 2: RL training (GRPO/PPO/DAPO)
         [Use n-gram/prompt-lookup for speedup, NOT Eagle3]
         [OR use NeMo RL online draft mode if infra allows]

Phase 3: Eagle3 draft training (on FINAL student model)
         [2-4h on DGX Spark, offline pattern]
         [MUST be after all model modifications: SFT, abliteration, RL]
         [Alternative: DFlash draft training via --speculator-type dflash — parallel drafting, 2-3x speedup. DEPLOY via SGLang only — vLLM DFlash is BROKEN for hybrid GDN targets (0% acceptance, Jul 14 2026)]

Phase 4: Deploy student + Eagle3 → vLLM or llama.cpp
         [2-6× inference speedup, lossless for greedy decoding]
         [Alternative: Deploy with DFlash → SGLang, 2-3x speedup, parallel drafting]
```

**Key insight**: Eagle3 and distillation are **orthogonal** — Eagle3 trains on the student's (target model's) hidden states, not the teacher's. GLM-5.2 or any cloud teacher is not involved in Eagle3 training. But Eagle3 MUST be trained AFTER all model modifications (SFT, abliteration, RL), because any weight change shifts the hidden state space and degrades acceptance.

See `references/eagle3-rl-interaction.md` for detailed research findings, paper citations, and experimental data.

## N-gram / Prompt-Lookup Decoding

Zero-training speculative decoding that finds matching n-grams in the prompt/context to propose draft tokens.

```bash
# vLLM
vllm serve model --speculative-config '{"method": "ngram", "num_speculative_tokens": 5, "prompt_lookup_max": 4}'

# llama.cpp
llama-server -m model.gguf --lookup-cache-static lookup.bin
```

Best for: RAG (repeated context), code completion, structured output. Works with any model including MoE.

## DFlash (Block Diffusion for Flash Speculative Decoding)

DFlash (Z Lab, arXiv:2602.06036, Feb 2026) replaces EAGLE-3's autoregressive drafter with a **block diffusion model** that predicts an entire block of tokens in a single parallel forward pass. Uses bidirectional (non-causal) attention so all draft positions attend to each other simultaneously, maximizing GPU utilization.

- **Speedup**: 2–3× over autoregressive, ~2.5× faster than EAGLE-3 (6× on Qwen3-8B)
- **Draft size**: 6 layers (~1B params), Qwen3-style transformer with sliding window attention
- **Block size**: 16 (default), produces `block_size - 1` speculative tokens
- **Lossless**: Yes (target model verifies all draft tokens)

### DFlash vs EAGLE-3

| Criterion | EAGLE-3 | DFlash |
|---|---|---|
| Drafting | Autoregressive (sequential) | Parallel (block diffusion, single forward pass) |
| Draft layers | 1 layer (~0.4B) | 5-6 layers (~1B) |
| Attention | Causal | Bidirectional (non-causal) |
| GPU utilization | Sequential bottleneck | Parallel → better utilization |
| vLLM | ✅ Full | ✅ Native in 0.25.0+ |
| SGLang | ✅ | ✅ Fastest (FA4/TRT-LLM) |

### DFlash Real-World Performance (GB10, Jul 2026)

**CRITICAL: Performance depends HEAVILY on serving engine.** vLLM DFlash is **BROKEN** for Qwen3.6 hybrid GDN targets (0% acceptance — draft model generates garbage due to incorrect hidden state extraction from hybrid attention layers). SGLang correctly extracts hidden states and achieves 20-40% acceptance.

| Target | Draft | Engine | Throughput | Acceptance | Notes |
|---|---|---|---|---|---|
| Qwen3.6-27B (dense) | z-lab DFlash (5L, bs=16) | **SGLang** | 10-15 tok/s | 20-40% (3.5-6.9/16) | **RECOMMENDED** — Jul 14 2026 |
| Qwen3.6-27B (dense) | z-lab DFlash (5L, bs=16) | **vLLM 0.25.0** | 2-3 tok/s | **0.0-0.7%** | **BROKEN** — SLOWER than baseline! Jul 14 2026 |
| Qwen3.6-27B (dense) | z-lab DFlash (5L, bs=16) | transformers-native | ~23.5 tok/s | 13.4/16 (84%) | Via `dflash_generate()` — fastest but single-request |
| Qwen3.6-27B (dense) | none (baseline) | vLLM 0.25.0 | ~3.1 tok/s | N/A | Memory-bandwidth limited on GB10 |

**Bottom line**: For Qwen3.6 hybrid GDN targets, use **SGLang** for DFlash. vLLM DFlash is broken — the hidden state extraction path does not correctly handle GDN (GatedDeltaNet) + FullAttention hybrid layers, causing the draft model to receive garbage inputs and produce 0% acceptance.

### Pretrained DFlash Models

| Draft Model | Target | Source |
|---|---|---|
| `z-lab/Qwen3.5-35B-A3B-DFlash` | Qwen3.5-35B-A3B | Official (Z-Lab + Modal) — **closest to Agents-A1** |
| `z-lab/Qwen3.6-35B-A3B-DFlash` | Qwen3.6-35B-A3B | Official |
| `z-lab/Qwen3.5-122B-A10B-DFlash` | Qwen3.5-122B-A10B | Official |
| `modal-labs/Qwen3.5-397B-A17B-DFlash` | Qwen3.5-397B-A17B | Official (beats native MTP) |
| `z-lab/Qwen3.6-27B-DFlash` | Qwen3.6-27B (dense) | Official |
| `RedHatAI/gemma-4-31B-it-speculator.dflash` | Gemma 4 31B | Red Hat |
| `ji-farthing/Qwen3.5-35B-A3B-DFlash-SWA-ik-llama-GGUF` | Qwen3.5-35B-A3B | Community GGUF for llama.cpp |

**No DFlash draft exists specifically for Agents-A1.** The `z-lab/Qwen3.5-35B-A3B-DFlash` is architecturally compatible (same Qwen3.5-MoE: hidden_size=2048, vocab_size=248320, 40 layers) but will have reduced acceptance due to SFT/abliteration activation shift. Train on Agents-A1's own hidden states for max acceptance.

### Deploy DFlash

**SGLang (primary, recommended — ONLY working path for Qwen3.6 hybrid GDN targets):**
```bash
# GB10 / DGX Spark — verified Jul 14 2026
python -m sglang.launch_server \
  --model-path /path/to/Qwen3.6-27B \
  --trust-remote-code \
  --speculative-algorithm DFLASH \
  --speculative-draft-model-path /path/to/Qwen3.6-27B-DFlash \
  --speculative-num-draft-tokens 16 \
  --tp-size 1 \
  --attention-backend flashinfer \
  --mem-fraction-static 0.75 \
  --mamba-scheduler-strategy extra_buffer \
  --port 8123 --host 0.0.0.0

# For datacenter GPUs (H100/H200) — use FA4/TRT-LLM backends for max speed:
python -m sglang.launch_server \
  --model-path InternScience/Agents-A1 \
  --trust-remote-code \
  --speculative-algorithm DFLASH \
  --speculative-draft-model-path z-lab/Qwen3.5-35B-A3B-DFlash \
  --speculative-dflash-block-size 8 \
  --speculative-draft-attention-backend fa4 \
  --attention-backend trtllm_mha \
  --linear-attn-prefill-backend flashinfer \
  --linear-attn-decode-backend flashinfer \
  --mamba-scheduler-strategy extra_buffer \
  --tp-size 1 --max-running-requests 32 \
  --cuda-graph-max-bs-decode 32 \
  --cuda-graph-backend-prefill tc_piecewise \
  --enable-flashinfer-allreduce-fusion \
  --mem-fraction-static 0.8
```

**SGLang build requirements (ARM64 / GB10):**
- SGLang PR #23000 for DFlash support: `pip install "git+https://github.com/sgl-project/sglang.git@refs/pull/23000/head#subdirectory=python"`
- **Rust compiler** required: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y && source ~/.cargo/env`
- **protoc** required: use torch's bundled protoc — `export PROTOC="$(python -c 'import torch,os;print(os.path.join(os.path.dirname(torch.__file__),"bin","protoc"))')"`
- **GB10 attention backend**: MUST use `--attention-backend flashinfer` — FA3 (`fa3`) asserts `SM<=90`, GB10 is SM 12.1
- SGLang install creates separate venv (e.g., `~/sglang_venv`) — does NOT conflict with vLLM venv

**Transformers-native inference (works NOW on GB10, no vLLM/SGLang needed):** The `dflash.py` file shipped inside each DFlash model directory IS the inference engine. It provides `dflash_generate()` which takes the draft model + target model + input_ids and returns generated tokens with acceptance stats. This is the fastest path to a working DFlash deployment on DGX Spark — no inference engine PRs required. See `references/dflash-transformers-inference.md` for the full setup guide, and `templates/run_dflash.py` for a ready-to-use runner script.

**vLLM (BROKEN for Qwen3.6 hybrid GDN targets — verified Jul 14 2026):** vLLM 0.25.0 launches DFlash successfully (after patches #34-36), but produces **0% acceptance rate** on Qwen3.6-27B (hybrid GDN+FullAttention). The draft model generates garbage because vLLM's hidden state extraction path does not correctly handle GDN linear-attention layers in hybrid targets. Result: 2-3 tok/s (SLOWER than baseline 3.1 tok/s — every step pays draft + verify cost but gets only 1 token). **Use SGLang instead.** vLLM DFlash may work correctly on pure-attention targets (non-hybrid), but this is unverified.
```bash
# 27B dense
vllm serve /path/to/Qwen3.6-27B \
  --served-model-name "qwen3.6-27b-dflash" \
  --speculative-config '{"method":"dflash","model":"/path/to/Qwen3.6-27B-DFlash","num_speculative_tokens":15}' \
  --attention-backend flash_attn \
  --max-num-batched-tokens 32768 \
  --gpu-memory-utilization 0.90 \
  --max-model-len 32768 \
  --trust-remote-code --dtype bfloat16

# 35B-A3B MoE — same command, different paths + served-model-name
```
`num_speculative_tokens` = `block_size - 1` (16 - 1 = 15). Do NOT use `--disable-hybrid-kv-cache-manager` — it breaks hybrid target models (Qwen3.6 GDN + FullAttention). Instead, patch DFlashProposer for multi-group support (see pitfall #35). SGLang is still faster (FA4/TRT-LLM attention, schedule overlapping), but vLLM works after the two patches below.

**vLLM transformers-native** (slower than vLLM engine but simplest for testing): Use `dflash_generate()` directly. See `references/dflash-transformers-inference.md` for full guide and `templates/run_dflash.py` for a ready-to-use script supporting both 27B (dense) and 35B-A3B (MoE).

**llama.cpp:** Community GGUF drafts available (e.g., `ji-farthing/Qwen3.5-35B-A3B-DFlash-SWA-ik-llama-GGUF`). Use as `--model-draft` with DFlash speculative decoding.

### Training DFlash Draft Models

Supported in speculators v0.5.0+ via the same offline pipeline as EAGLE3, but with key differences:

```bash
# Phase 1-2: Extract hidden states (same as EAGLE3)
python scripts/launch_vllm.py --model InternScience/Agents-A1 \
  --target-layer-ids 3 7 11 15 19 23 27 31 35 39

# Phase 3: Train DFlash draft (key differences: --speculator-type dflash)
python scripts/train.py \
  --speculator-type dflash \
  --draft-arch qwen3 \
  --target-layer-ids 3 7 11 15 19 23 27 31 35 39 \
  --full-attention-indices 3 7 11 15 19 23 27 31 35 39 \
  --no-sample-from-anchor
```

Key differences from EAGLE3 training:
- `--speculator-type dflash` (not `eagle3`)
- DFlash is in `SLIDING_WINDOW_SPECULATOR_TYPES` — uses sliding window attention in draft layers
- `--full-attention-indices` controls which draft layers use full vs sliding attention
- `--sample-from-anchor` / `--no-sample-from-anchor` controls sampling mode (default: False for DFlash, True for DSpark)
- DFlash draft has 6 layers (vs EAGLE3's 1) → more memory during training

### DSpark (DFlash Extension)

DSpark extends DFlash with a **Markov logit-bias head** for improved prediction quality. Also in speculators (`--speculator-type dspark`, architecture `Qwen3DSparkModel`). Pretrained: `deepseek-ai/dspark_qwen3_8b_block7` (Qwen3-8B dense).

### DFlash/DSpark Block Size Scaling (>16)

**CRITICAL (research Jul 2026):** Block sizes >16 are **Pareto-dominated** on quality-vs-throughput. The Pareto frontier is {4, 16, 32}. Block 64/128 are strictly dominated (Block-Diffusion-Pareto, GitHub: BrutalCaeser). Nemotron TwoTower data confirms monotonic quality degradation (BS 128→32: +3-5 points across all tasks).

**However, BS=64 IS feasible with progressive training + DSpark:**

| Technique | Source | Purpose |
|---|---|---|
| Progressive training (4→8→16→32→64) | TDAR (arXiv:2602.09555), T* (arXiv:2601.11214), SDAR (arXiv:2510.06303) | Avoid quality collapse |
| DSpark Markov head (rank 256-512) | DSpark (arXiv:2607.05147) | Combat suffix decay at positions >8 |
| Confidence head (early stopping) | DSpark | Only verify high-confidence positions |
| Gamma scaling: gamma=28 for BS=64 | Derived (4x linear from gamma=7 at BS=16) | Maintain loss signal at position 63 |
| D-PACE adaptive weights | speculators `--per-position-loss-weight dpace` | Alternative to fixed exp decay |
| Fast-dLLM v2 sub-blocks (arXiv:2509.26328) | NVIDIA Labs | Train at 64, decode in sub-blocks of 8-16 |

**speculators train.py params for BS=64:**
```bash
--speculator-type dspark --block-size 64 --num-layers 6
--dflash-decay-gamma 28.0 --per-position-loss-weight dpace
--markov-rank 512 --markov-head-type gated
--enable-confidence-head --confidence-head-with-markov
```

**VRAM impact of BS=64 vs BS=16: <3% increase** — dominated by target model. Draft model activations increase ~4x but are tiny (~0.2GB vs 65GB target).

**Alternative: BS=32 is Pareto-optimal throughput endpoint** — consider training at BS=32 as the primary checkpoint, with BS=64 as experimental.

### DFlash + Agents-A1 Compatibility

| Factor | Status | Notes |
|---|---|---|
| Architecture match | ✅ | Same Qwen3.5-MoE (hidden_size=2048, vocab=248320, 40 layers) |
| Hybrid attention | ⚠️ | Pretrained z-lab DFlash uses target_layer_ids [1,6,11,16,22,27,32,37] — 6/8 are linear_attention layers. DFlash combines 8 layers via bidirectional attention, mitigating vs EAGLE3's 3-layer approach. Use `--target-layer-ids 3 7 11 15 19 23 27 31 35 39` (full_attention layers) for training. |
| Activation shift | ⚠️ | Agents-A1 SFT/abliteration shifts hidden states → reduced acceptance with pretrained z-lab DFlash. Train on Agents-A1's own hidden states for max acceptance. |
| vLLM deploy | ❌ BROKEN | vLLM DFlash produces 0% acceptance on Qwen3.6 hybrid GDN targets (Jul 14 2026). Use SGLang. |

See `references/dflash-speculators.md` for detailed architecture, config format, deployment recipes, and DSpark extension.
See `references/sglang-dflash-deployment.md` for SGLang DFlash operational reference on GB10: build requirements, startup timing, API gotchas, acceptance monitoring, 27B vs 35B draft config comparison.
See `references/dflash-transformers-inference.md` for transformers-native DFlash inference (no vLLM/SGLang needed — works NOW on GB10).
See `references/dspark-progressive-training.md` for the complete progressive DSpark training pipeline: 3-stage block size scaling (16->32->64) with full parameter tables, gamma scaling logic, Markov rank progression, data preparation for 100K+ samples, and 14-paper research bibliography.
See `references/bandwidth-bound-strategy.md` for quantization strategy on bandwidth-bound hardware (GB10/Jetson): why quantize target not draft, 5-strategy comparison, ML-SpecQD/MoE-SpeQ research context.
See `templates/run_dflash.py` for a ready-to-use runner supporting both 27B (dense) and 35B-A3B (MoE) targets.
See `templates/serve_sglang_dflash.sh` for a SGLang serve script template (BF16 27B/35B — RECOMMENDED for hybrid GDN targets).
See `templates/serve_sglang_dflash_fp8.sh` for a SGLang serve script template for FP8-quantized MoE targets with pre-flight checks (memory budget, port collision, MAX_JOBS guard). FP8 is the recommended quantization for DFlash on GB10: 36 GB (vs 66 GB BF16), <0.5% quality loss, 60 GB headroom for Hermes stack + KV cache.
See `templates/serve_vllm_dflash.sh` for a vLLM serve script template (native DFlash in vLLM 0.25.0+ — BUT BROKEN for hybrid GDN targets, see pitfall #37).

## Bandwidth-Bound Hardware Strategy (GB10, Jetson, Consumer GPUs)

**On memory-bandwidth-bound hardware, quantize the TARGET model, not the draft.** The bottleneck in speculative decoding is target verification (loading all target weights per cycle), not draft generation. The DFlash draft (~700MB) is negligible next to even an INT4 target (~17.5GB for 35B MoE).

| Strategy | VRAM (35B MoE) | Est. tok/s | Quality |
|---|---|---|---|
| bf16 target + DFlash | 71 GB | ~10-19 | Lossless |
| **INT4 target + DFlash** | **18 GB** | **~30-75** | ~1-2% loss |
| bf16 target + INT4 draft | 88 GB | ~9 | Lossless but SLOW (sequential drafting) |

The intuitive idea of "use a quantized version of the same model as draft" underperforms on bandwidth-bound hardware: sequential draft generation takes 512ms (8 × 64ms), which is **longer than the verify pass**. DFlash's parallel block diffusion (16 tokens in 3ms) is far superior.

**Decision rule:** If hardware is bandwidth-bound → quantize target first, use small parallel draft (DFlash/EAGLE3) at bf16. If compute-bound (datacenter HBM) → quantizing the draft may help.

See `references/bandwidth-bound-strategy.md` for the full math (GB10 = 273 GB/s LPDDR5x), 5-strategy comparison table, MoE parameter budget (experts = 90% of params — quantization is effectively binary), FP8 dynamic sweet spot for DFlash on GB10, and research context (ML-SpecQD, MoE-SpeQ, LayerSkip).
See `references/cross-architecture-speculative-decoding.md` for using model from family A as draft for family B target: 3 hard blockers (vocab mismatch, size ratio, hidden state format), DEER (0.5B diffusion drafter, 32-token acceptance), DiffuSpec (training-free DLM draft), and decision matrix.

## MoE-Specific Considerations

- **Routing overhead**: MoE models have expert routing that adds overhead per forward pass. Speculative decoding helps because verification is batched — the routing cost is amortized over K tokens.
- **llama.cpp MoE speculative decoding**: PR #19493 added support, but community testing shows **no net speedup on A3B models** (routing overhead eats the draft-model win). Use vLLM or SGLang for MoE speculative decoding.
- **Draft architecture**: For Qwen3.5-MoE targets, use `--draft-arch qwen3` in speculators training.
- **Acceptance rate**: MoE models may have lower acceptance rates due to expert specialization. Increase TTT steps (7 instead of 3) and use more training data.

## Benchmarking

Always benchmark WITHOUT speculative decoding first, then WITH:

```bash
# Baseline (no spec decoding)
vllm serve model --dtype bfloat16
# → measure tok/s with a representative prompt

# With EAGLE3
vllm serve model --speculative-config '{"method": "eagle3", ...}'
# → measure tok/s, compare

# Target: 2×+ improvement
```

Key metrics:
- **Tokens/sec** (throughput)
- **Acceptance rate** (fraction of draft tokens accepted)
- **Latency** (time-to-first-token, time-per-token)
- **Quality** (output should be identical to non-speculative for greedy decoding)

## Cross-References

- `references/eagle3-speculators-training.md` — Full EAGLE3 draft model training workflow: speculators framework setup, offline vs online training, DGX Spark single-GPU pattern, MoE-specific parameters, and adaptation of pre-trained drafts
- `references/eagle3-rl-interaction.md` — Eagle3 + RL training interactions: ReSpec three gaps (batch size, staleness, policy degradation), DFlash + RL analysis (4 architectural advantages, slower degradation but still not safe), safe alternatives (n-gram, NeMo RL online, ReSpec, TIDE), correct pipeline ordering, paper citations (arXiv:2510.26475, 2503.01840, 2510.19779, 2602.05145, 2602.06036, 2607.05147)
- `references/agents-a1-architecture.md` — Agents-A1 (Qwen3.5-MoE) architecture analysis: hybrid attention layer map (CRITICAL for correct EAGLE3 layer selection), config compatibility with existing drafts, MTP built-in status, abliteration impact
- `references/vllm-uma-memory-tuning.md` — vLLM memory management on unified memory (GB10/DGX Spark): why `gpu_memory_utilization` too LOW causes system hangs, budget formula, correct values per model, optimization flags, vLLM source code analysis
- `references/dflash-speculators.md` — DFlash block-diffusion draft models: architecture (6-layer bidirectional), config format, pretrained models (z-lab Qwen3.5-35B-A3B-DFlash + others), SGLang/vLLM deployment, speculators training (`--speculator-type dflash`), DSpark extension, Agents-A1 compatibility analysis
- `references/dflash-transformers-inference.md` — Transformers-native DFlash inference via `dflash_generate()`: model loading sequence, embed_tokens alias trick, dflash.py API, GB10 benchmark results (23.5 tok/s on 27B), dflash.py version differences between 27B and 35B models
- `obliteratus` skill — MTP compatibility with abliteration, acceptance rate degradation analysis
- `llm-finetuning-pipeline` skill — DGX Spark training infrastructure, memory budgeting
- `local-model-serving` skill — Model deployment, GGUF conversion, serving config
- `llama-cpp` skill — GGUF inference, speculative decoding in llama.cpp

## Pitfalls

1. **MoE + llama.cpp speculative decoding = no speedup**: llama.cpp PR #19493 added MoE spec decoding support, but A3B models show no net gain because expert routing overhead eats the draft-model win. Use vLLM or SGLang for MoE speculative decoding.
2. **MTP acceptance degrades after SFT/abliteration**: The MTP head was trained against the original model's activation space. SFT shifts activations, reducing acceptance from ~76% to ~55%. Fix: train EAGLE3 on the modified model's hidden states, or use n-gram (activation-agnostic).
3. **Hidden state dimensions must match**: When using a pre-trained EAGLE3 draft from a different model, verify `hidden_size` matches. Qwen3-30B and Agents-A1 (Qwen3.5-MoE) may differ — always check `config.json` before attempting cross-model draft reuse.
4. **DGX Spark is single-GPU**: Cannot run vLLM (for hidden state extraction) and training simultaneously. Must use offline training pattern: generate hidden states first, stop vLLM, then train. See training reference.
5. **Disk space for hidden states**: ~1.6TB for 50K samples (Llama-3.1-8B, avg seq len 1024). For 35B MoE models with larger hidden_size, expect more. Use smaller sample counts (5K) or generate in batches with deletion after loading.
6. **`num_speculative_tokens` tuning**: Higher K = more potential speedup but also more wasted compute on rejected drafts. Start with K=4, test K=2,4,8. For MoE models, lower K (2-3) may be better due to routing overhead per verification step.
7. **EAGLE3 is lossless for greedy decoding**: For temperature>0 sampling, the acceptance criterion uses distribution-matching (rejection sampling), which is also lossless but may have slightly lower acceptance rates.
8. **Draft model conversion to GGUF**: EAGLE3 draft models trained with speculators are in HuggingFace format. For llama.cpp deployment, convert to GGUF using `convert_hf_to_gguf.py` on the draft model directory.
9. **`--draft-arch qwen3` for Qwen3.5-MoE targets**: When training EAGLE3 for Qwen3.5-MoE based models (Agents-A1, Qwen3.6-35B-A3B, etc.), use `--draft-arch qwen3` not `--draft-arch llama`. The target and draft architectures don't have to match, but matching gives better results.
10. **TTT steps trade-off**: Higher TTT steps (7) give better acceptance rates but longer training time and more memory. Start with 3 (default), increase to 7 if acceptance rate is too low.
11. **Muon optimizer**: speculators defaults to Muon optimizer for 2D weights + AdamW for the rest. This converges faster than pure AdamW. Use `--optimizer adamw` only if Muon causes issues.
12. **Eagle3 during RL training is DANGEROUS**: ReSpec (arXiv:2510.26475) identifies three critical gaps: (1) large RL batch sizes eliminate SD speedup, (2) drafter becomes stale as actor updates every step, (3) multi-token draft variance compounds exponentially and degrades the RL policy. Use n-gram/prompt-lookup for RL rollout generation instead. Train Eagle3 only AFTER RL is complete, on the final model. See "Eagle3 + RL Training: Critical Interactions" section above.
13. **Eagle3 must be trained AFTER all model modifications**: SFT, abliteration, and RL all shift the hidden state space. An Eagle3 draft trained before these modifications will have degraded acceptance (~55% after SFT+abliteration vs ~76% on base model). Always train Eagle3 as the LAST step before deployment.
14. **Eagle3 and distillation are orthogonal**: Eagle3 trains on the student model's hidden states, not the teacher's. The cloud teacher (GLM-5.2, GPT-4o) is not involved in Eagle3 training. This means distillation and Eagle3 can coexist in the pipeline without interference, as long as Eagle3 comes after distillation.
15. **Online vs offline training on multi-GPU**: Online training (vLLM + training simultaneously) needs 2+ GPUs (one for vLLM, one for training). On single-GPU systems (DGX Spark), use offline training exclusively.
16. **Hybrid attention models: default layer IDs hit WRONG layers**: Qwen3.5-MoE models (Agents-A1, Qwen3.6-35B-A3B, etc.) use a hybrid attention pattern — 75% `linear_attention` (GatedDeltaNet, no KV cache) + 25% `full_attention` (standard), with `full_attention_interval: 4`. The default EAGLE3 layer selection `[2, num_layers//2, num_layers-3]` lands on ALL linear attention layers (e.g., for Agents-A1's 40 layers: [2, 20, 37] are all linear). This causes silent low acceptance rates because linear attention hidden states are less informative for token prediction. **FIX**: Pass `--target-layer-ids 3 19 39` to both `launch_vllm.py` and `train.py` to extract from full_attention layers (indices divisible by `full_attention_interval - 1`, i.e., 3, 7, 11, 15, 19, 23, 27, 31, 35, 39). **IMPORTANT**: In `launch_vllm.py`, `--target-layer-ids` is a script argument — it must go BEFORE the `--` separator, not after (after `--` passes it to vLLM which doesn't understand it, causing silent fallback to default wrong layers). See `references/agents-a1-architecture.md` for the full layer map.
17. **BF16 vs FP8 memory budget on DGX Spark — CRITICAL: BF16 can crash the machine**: BF16 (65GB model) requires ~87GB for vLLM serve. This is NOT just "online training won't fit" — **vLLM with BF16 model ALONE can crash the entire DGX Spark when the Hermes stack is running**. The real memory budget is: BF16 model (~66GB) + vLLM overhead/KV cache (~20-30GB) + Hermes Docker stack (gateway + dashboard + litellm + phoenix, ~4GB) + Hermes Desktop Electron/Chromium (~4-8GB) + system overhead (~3-5GB) = **97-113GB in a 121GB pool**. This caused **3 machine crashes in 14 hours** (Jul 12-13, 2026) during an EAGLE3 training pipeline cron job — the kernel OOM killer killed Hermes (oom_score_adj=300), then Chrome, then cicc, and the system became unstable enough to require reboots. Symptoms before crash: `journalctl` shows "Under memory pressure, flushing caches" every 20 seconds for hours, then OOM kills. **FIX — choose ONE before launching vLLM for hidden state extraction**: (a) Use APEX-quantized GGUF via llama.cpp instead of vLLM (~22GB vs 66GB — see `local-model-serving` skill for APEX quantization). (b) Use FP8 model (~33GB) or AWQ/INT4 (~20GB) in vLLM. (c) Stop Hermes Desktop (kill Electron) + stop non-essential Docker containers (litellm, phoenix) before launching vLLM — frees ~8-12GB. (d) Set `--gpu-memory-utilization 0.65` with optimization flags (see below) — NOT 0.5, which causes system hangs. FP8 (35GB model) has enough headroom for the offline pipeline. See `references/eagle3-speculators-training.md` → DGX Spark Memory Budget and `references/vllm-uma-memory-tuning.md` for detailed breakdown.

18. **CRITICAL — `gpu_memory_utilization` on GB10 unified memory: too LOW is as dangerous as too HIGH**: On DGX Spark (GB10), GPU and CPU share the same physical RAM (CUDA total = 121.69 GiB = system RAM). vLLM's `gpu_memory_utilization` is NOT a consumption limit — it's a **KV cache budget** calculated as `CUDA_total × utilization`. Model weights always load fully regardless of this parameter. The budget must cover: model_weights + profile_run (~3 GiB) + overhead (~2 GiB) + KV_cache. **Setting it too LOW (e.g., 0.55) is catastrophic**: budget = 66.9 GiB, model = 66.5 GiB, remainder = 0.4 GiB — insufficient for profile_run → PyTorch grabs system RAM → swap → system hangs. **Correct value for BF16 Agents-A1: 0.65** (budget = 79.1 GiB, remainder after model = 12.6 GiB — enough for profile + overhead + KV cache). Additional optimization flags for the launch_vllm.py command: `--kv-cache-dtype fp8` (halves KV cache, safe for EAGLE3 — hidden states come from model layers not KV cache), `--max-num-seqs 4`, `--swap-space 0` (pointless on UMA — swap targets the same RAM), `--enforce-eager` (saves ~1-2 GiB by disabling CUDA graphs), `--no-enable-prefix-caching`. See `references/vllm-uma-memory-tuning.md` for the full derivation, vLLM source code analysis, and calculation formula.
19. **CRITICAL — `cicc` CUDA compiler processes eat 43+ GB on UMA**: Even with the correct `gpu_memory_utilization=0.65`, vLLM can still crash the system. During startup, PyTorch JIT-compiles CUDA kernels, spawning 19+ parallel `cicc` (NVIDIA CUDA compiler) processes. On discrete GPUs these are harmless (they use system RAM, not VRAM). On UMA (GB10), system RAM IS GPU RAM — these processes directly compete with the model. Measured impact: 19 `cicc` processes = 43.2 GB RSS, combined with 66.5 GB model = 109.7 GB out of 127.4 GB → OOM. **This is invisible to `nvidia-smi`** (model is in driver memory, `cicc` is in process RSS — you need BOTH `ps aux` and `nvidia-smi` to see the full picture). **FIX**: Set `export MAX_JOBS=1` and `export NVCC_THREADS=1` before launching vLLM — limits to a single compiler process (~3 GB instead of 43 GB). Slower startup but no OOM. See `references/vllm-uma-memory-tuning.md` → "CUDA Compiler (cicc) Processes on UMA" section.
20. **`--max-num-batched-tokens` must be >= `--max-model-len` when chunked prefill is disabled**: `launch_vllm.py` force-adds `--no-enable-chunked-prefill`. With chunked prefill off, vLLM requires `max_num_batched_tokens >= max_model_len`. Setting `--max-num-batched-tokens 512` with `--max-model-len 4096` causes a `ValidationError`. **FIX**: Remove `--max-num-batched-tokens` entirely (vLLM defaults it to `max_model_len`) or set it >= `max_model_len`. Do NOT use small `max-num-batched-tokens` to reduce memory when chunked prefill is off.
18. **`--draft-vocab-size` for large-vocab models**: Qwen3.5-MoE models have vocab_size=248320. Using the full vocab makes the draft model's embedding/LM_head layers huge. Use `--draft-vocab-size 8192` (covers ~99% of token frequencies via `token_freq.pt`). The existing `nm-testing/Speculator-Qwen3-30B-MOE-VL-Eagle3` uses 8192, not 32000.
19. **Hidden state extraction is forward-pass, not generation**: The `data_generation_offline.py` step runs each sample through vLLM as a forward pass (not autoregressive generation). This is ~5-10x faster than generating the same number of tokens. For time estimation: ~500-1000 tokens/sec forward throughput on DGX Spark. The target model processes ALL tokens in the dataset (e.g., 6.5M tokens for 5K ShareGPT samples), not just assistant tokens.
20. **`--concurrency` in data_generation_offline.py must match `--max-num-seqs` in vLLM**: Higher concurrency (e.g., 16) sends more concurrent requests than vLLM can batch (e.g., max-num-seqs=4), wasting client memory on queued results. Set `--concurrency 4` when vLLM has `--max-num-seqs 4`.
21. **EAGLE3 draft model is context-length independent**: The draft model learns a local pattern (hidden_state[t] → hidden_state[t+1]) and has a 1-layer KV cache that does not grow with context. Training at `--max-model-len 8192` produces a draft that works perfectly at 256K context at inference. The only context-length constraint is the target model's capacity. See "EAGLE3 and Context Length" section above.
22. **FlashInfer JIT compilation has TWO waves on GB10 (50-60 min cold start)**: Wave 1 (~30-40 min) compiles MoE GEMM kernels before model load. Wave 2 (~10-20 min) compiles additional kernel variants during profile-run/AutoTuner after model load. Log appears frozen (Python stdout block-buffered) — check `ps -o utime= -p <pid>` to confirm process is alive. Total cold start: ~50-60 min. Subsequent starts with warm cache: ~8 min. See `references/eagle3-speculators-training.md` → "FlashInfer JIT Compilation on GB10" for details, manual ninja pre-compilation workaround, and MAX_JOBS tuning.
23. **FlashInfer cache splits between HOME locations**: When vLLM is launched from Hermes (HOME=/home/user/.hermes/home), FlashInfer cache goes to `~/.hermes/home/.cache/flashinfer/` NOT `~/.cache/flashinfer/`. Previous compilation is NOT reused → full 50-60 min recompilation. Fix: `cp -rn ~/.cache/flashinfer/* ~/.hermes/home/.cache/flashinfer/` before launching.
24. **gpu-memory-utilization 0.75 causes NVRM OOM on GB10**: The AutoTuner phase (FlashInfer kernel autotuning after model load) needs extra GPU memory beyond what 0.75 allocates. NVRM OOM errors appear in `journalctl -k` as `NV_ERR_NO_MEMORY`. 0.65 is proven safe for BF16 Agents-A1 (66.5 GiB model). Verified Jul 13 2026.
25. **Do NOT set `--max-num-batched-tokens` below `--max-model-len`**: `launch_vllm.py` force-adds `--no-enable-chunked-prefill`. With chunked prefill off, vLLM requires `max_num_batched_tokens >= max_model_len`. Setting `--max-num-batched-tokens 1024` with `--max-model-len 8192` causes `ValidationError`. Omit the flag entirely (vLLM defaults it to `max_model_len`).
26. **CRITICAL — Background pipeline scripts with `kill $(pgrep -f vllm)` kill ANY vLLM process, including manually-launched ones in other sessions**: The offline training reference (Step 4) and example scripts use `kill $(pgrep -f vllm)` or `kill $(pgrep -f "vllm.entrypoints")` to stop vLLM between phases. `pgrep -f` matches ANY process with that string in its command line — if a background pipeline from a PREVIOUS session is still running (e.g. stalled on Phase 4), its Phase 5 cleanup will SIGTERM your manually-launched vLLM in the current session. **Symptoms**: vLLM starts successfully, serves health checks, then receives SIGTERM ~2-3 minutes later with no user action. Log shows `[shutdown] API server: shutdown triggered` and `[shutdown] EngineCore: trigger received signal=SIGTERM`. **FIX**: (a) Always check for leftover background processes before launching vLLM: `pgrep -af "vllm.entrypoints"` and `pgrep -af "data_generation"`. (b) In pipeline scripts, save the vLLM PID explicitly (`VLLM_PID=$!`) and kill only that PID (`kill $VLLM_PID`), never use `pgrep -f` for cleanup. (c) When investigating unexpected vLLM deaths, use `session_search` to find previous sessions that may have left background pipelines running — the root cause may be a zombie script, not OOM or user action. Verified Jul 13 2026.
27. **`prepare_data.py` may produce `input_ids` as Python list instead of torch.Tensor for Qwen3.5-MoE models**: `data_generation_offline.py` calls `build_client_item()` which does `dataset_item["input_ids"].tolist()` — if `input_ids` is already a `list` (not a tensor), this raises `AttributeError: 'list' object has no attribute 'tolist'`. This was observed with Agents-A1 (Qwen3.5-MoE) on Jul 13 2026. The error occurs immediately at the start of hidden state generation (Phase 4), before any vLLM requests are sent. **FIX**: After `prepare_data.py`, verify the dataset format: `python -c "from datasets import load_from_disk; d = load_from_disk('./training_data'); print(type(d[0]['input_ids']))"`. If it's `list`, either patch `build_client_item` to handle both types (`torch.tensor(x) if isinstance(x, list) else x`), or re-run `prepare_data.py` checking if the tokenizer returns tensors. This bug causes Phase 4 to exit immediately, which then triggers Phase 5 (kill vLLM) in automated pipelines — compounding with pitfall #26.
28. **DFlash during RL is less dangerous than EAGLE-3 but still degrades**: DFlash has 4 architectural advantages over EAGLE-3 for RL (8 target layers vs 1-3, parallel drafting without error cascade, diffusion denoising robustness, adapter role with shared frozen components). However, it is still conditioned on target model hidden states and will go stale as RL updates the target's weights. DFlash degrades slower (estimated 100-200 RL steps vs 50-100 for EAGLE-3) but is NOT safe for RL rollout. Use n-gram/prompt-lookup for RL, train DFlash only AFTER all RL is complete. See `references/eagle3-rl-interaction.md` → "DFlash + RL Analysis" for the full comparison.
28. **DFlash pretrained models use WRONG target_layer_ids for hybrid attention MoE models**: The official `z-lab/Qwen3.5-35B-A3B-DFlash` uses `target_layer_ids: [1, 6, 11, 16, 22, 27, 32, 37]` — 6 of 8 are `linear_attention` layers (GatedDeltaNet) on Qwen3.5-MoE targets. This is the same class of bug as EAGLE3 pitfall #16, but DFlash combines 8 layers through bidirectional attention (vs EAGLE3's 3 layers), which partially mitigates the issue. Still, for best acceptance rates on Agents-A1 / Qwen3.5-MoE / Qwen3.6-35B-A3B, pass `--target-layer-ids 3 7 11 15 19 23 27 31 35 39` (full_attention layer indices, divisible by `full_attention_interval - 1 = 3`) when training a DFlash draft. When using the pretrained z-lab DFlash directly (without retraining), expect ~10-15% lower acceptance than a DFlash trained on correct layers.
29. **DFlash vLLM serving is NATIVE in vLLM 0.25.0+ (verified Jul 14 2026)**: vLLM 0.25.0 includes DFlash in `vllm/v1/spec_decode/dflash.py` (`DFlashProposer`), `vllm/v1/worker/gpu/spec_decode/dflash/`, and `vllm/config/speculative.py`. Launch with:
    ```bash
    vllm serve /path/to/target \
      --speculative-config '{"method":"dflash","model":"/path/to/draft","num_speculative_tokens":15}' \
      --attention-backend flash_attn --trust-remote-code --dtype bfloat16
    ```
    `num_speculative_tokens` = `block_size - 1` (block_size=16 → 15 spec tokens). The draft model is loaded via `trust_remote_code` (dflash.py auto_map). **NOTE**: SGLang is still the recommended path for max performance (FA4/TRT-LLM attention, schedule overlapping), but vLLM works out of the box. The `speculators convert` CLI still does NOT support DFlash (only eagle, eagle3, mtp).
30. **DFlash transformers-native inference: 5 critical gotchas (verified Jul 14 2026 on GB10)**: When running DFlash via `dflash_generate()` from the shipped `dflash.py`:
    - **(a) `dflash.py` is NOT a pip package** — it lives inside the draft model directory. Load it via `importlib.util.spec_from_file_location("dflash_mod", os.path.join(DRAFT_PATH, "dflash.py"))`.
    - **(b) `target.model.embed_tokens` alias REQUIRED**: `dflash.py` accesses `target.model.embed_tokens` for noise embeddings, but Qwen3_5/Qwen3_5Moe models nest it under `target.model.language_model.embed_tokens`. Must add: `target.model.embed_tokens = target.model.language_model.embed_tokens` after loading the target model.
    - **(c) `device_map=` requires `accelerate` package** — use `.to(DEVICE)` instead if accelerate isn't installed.
    - **(d) `apply_chat_template` in transformers v5 returns `BatchEncoding`, NOT a dict** — `isinstance(result, dict)` is `False` because `BatchEncoding` is dict-LIKE but not a `dict` subclass. It has `.to()` (moves tensors) but accessing `.shape` raises `KeyError: 'shape'`. Robust extraction: `ids = r["input_ids"] if isinstance(r, dict) else getattr(r, "input_ids", r)`, then `if not isinstance(ids, torch.Tensor): ids = torch.tensor(ids)`. See `templates/run_dflash.py` → `prep_input()` for the full handler.
    - **(e) Target model class depends on architecture**: Qwen3.6-27B (dense) → `Qwen3_5ForConditionalGeneration`; Qwen3.6-35B-A3B (MoE) → `Qwen3_5MoeForConditionalGeneration`. Both from `transformers.models.qwen3_5` / `transformers.models.qwen3_5_moe`.
    - **(f) `torch_dtype` is deprecated in transformers v5** — use `dtype=` parameter instead.
    See `references/dflash-transformers-inference.md` for full details and `templates/run_dflash.py` for a working script.
31. **DFlash real-world performance on GB10 (Qwen3.6-27B dense)**: Measured Jul 14 2026 — 23.5 tok/s decode, TTFT 1.1s, avg acceptance 13.4/16 (84%), VRAM 54.7 GB target + 3.5 GB draft = ~58 GB total. This is the first real DFlash benchmark on GB10 unified memory. The 84% acceptance rate with the pretrained z-lab DFlash is notably high, suggesting the dense Qwen3.6-27B model has less activation shift than MoE variants.
32. **DFlash draft models ship DIFFERENT dflash.py versions (27B vs 35B, verified Jul 14 2026)**: The `dflash.py` inside each draft model directory is NOT the same code. Two known differences:
    - **(a) `block_size` config location**: 27B-DFlash has `block_size: 16` at the top level of `config.json`. 35B-A3B-DFlash nests it inside `dflash_config: {"block_size": 16}`. The `DFlashDraftModel.__init__` does `config.block_size` → `AttributeError` on 35B. **FIX**: Before loading, hoist it: `from transformers import AutoConfig; cfg = AutoConfig.from_pretrained(DRAFT_PATH, trust_remote_code=True); if not hasattr(cfg, 'block_size') and hasattr(cfg, 'dflash_config'): cfg.block_size = cfg.dflash_config.get('block_size', 16)`. Then pass `config=cfg` to `AutoModel.from_pretrained`. See `templates/run_dflash.py` → `load_draft_with_config_fix()`.
    - **(b) `DynamicCache` initialization**: 27B-DFlash's `dflash.py` creates caches as `DynamicCache(config=_target_cfg)` (needed for Qwen3_5 linear-attention layers). 35B-A3B-DFlash's `dflash.py` uses bare `DynamicCache()` → crashes on linear-attention models. **FIX**: Patch the 35B `dflash.py` file directly — replace `past_key_values_target = DynamicCache()` and `past_key_values_draft = DynamicCache()` with the config-aware version from the 27B `dflash.py`. Clear the HF remote-code cache after patching: `rm -rf ~/.cache/huggingface/modules/transformers_modules/*DFlash*`.
33. **HuggingFace remote-code cache serves STALE dflash.py**: When `trust_remote_code=True`, transformers caches `dflash.py` in `~/.cache/huggingface/modules/transformers_modules/`. If you patch the model directory's `dflash.py`, the cached copy is used instead. **Always clear the cache after patching**: `rm -rf ~/.cache/huggingface/modules/transformers_modules/*DFlash*` (or the specific model subdirectory).
> **⏰ EXPIRY NOTICE (Jul 14, 2026):** Pitfalls #34–#36 below describe manual source patches to vLLM 0.25.0 for DFlash on hybrid-architecture targets (Qwen3.6 GDN+FullAttention). These patches are needed because vLLM upstream has not yet merged proper DFlash multi-group KV-cache support. They will likely be fixed in the next vLLM release (~Aug 2026). **Before applying, check**: (a) is `vllm/v1/spec_decode/dflash.py` still missing `validate_same_kv_cache_group` override? (b) does `qwen3_dflash.py` still have the `NotImplementedError` guard? If both are already fixed upstream, remove the patches and the manual `PATH` hack.

34. **DFlash vLLM: mixed sliding/full layer_types NotImplementedError (verified Jul 14 2026)**: DFlash draft models have mixed `layer_types` (e.g., 4 `sliding_attention` + 1 `full_attention`). vLLM 0.25.0's `vllm/model_executor/models/qwen3_dflash.py` raises `NotImplementedError: DFlash does not yet support mixed sliding/full attention via layer_types` at `_resolve_layer_attention()`. The code below the guard already handles per-layer types correctly. **FIX**: Patch `qwen3_dflash.py` — remove the `if any_sliding and not all_sliding: raise NotImplementedError(...)` block in `_resolve_layer_attention()` (around line 90). The per-layer logic below it (`is_sliding = layer_types[layer_idx] == SLIDING_ATTENTION`) works correctly. File: `/home/user/vllm_venv/lib/python3.12/site-packages/vllm/model_executor/models/qwen3_dflash.py`.
35. **DFlash vLLM: KV-cache group error for HYBRID target models (REVISED Jul 14 2026)**: The previous fix was to add `--disable-hybrid-kv-cache-manager`, which forces `unify_hybrid_kv_cache_specs()` to convert all KV cache specs to one type. This works for pure-transformer targets but **BREAKS for hybrid architecture targets** (Qwen3.6-27B `Qwen3_5ForConditionalGeneration` has both FullAttention layers AND GDN linear-attention layers with fundamentally different state types — `MambaSpec`/SSM states cannot be converted to `FullAttentionSpec`). **ERROR**: `ValueError: Hybrid KV cache manager is disabled but failed to convert the KV cache specs to one unified type.` **CORRECT FIX (3 parts)**:
    1. **Do NOT use `--disable-hybrid-kv-cache-manager`** — let the hybrid KV cache manager create separate groups for FullAttention and GDN layers.
    2. **Patch `DFlashProposer`** in `vllm/v1/spec_decode/dflash.py` — override `validate_same_kv_cache_group()` to a no-op (like `Step3p5MTPProposer` does) and override `initialize_attn_backend()` with the multi-group version from step3p5.py. Without this, the base class's `validate_same_kv_cache_group()` raises `AssertionError: All drafting layers should belong to the same kv cache group` because the DFlash draft's mixed sliding/full attention layers land in different KV-cache groups.
    3. **Ensure `ninja` is in PATH** for FlashInfer JIT compilation: `export PATH="/path/to/venv/bin:$PATH"` before launching vLLM. FlashInfer's `subprocess.run(["ninja", ...])` needs ninja accessible from the subprocess environment.
36. **DFlash vLLM: `FileNotFoundError: 'ninja'` during FlashInfer JIT after KV-cache init (verified Jul 14 2026)**: After the KV-cache groups are successfully initialized (pitfalls #34-#35 fixed), vLLM proceeds to CUDA graph profiling. FlashInfer's top-k/top-p sampling JIT compilation calls `subprocess.run(["ninja", ...])`, which fails with `FileNotFoundError: [Errno 2] No such file or directory: 'ninja'` if the vLLM venv `bin/` directory is not in `PATH`. This happens because `exec python -m vllm.entrypoints...` inherits the shell's `PATH`, and if the script hardcodes `PYTHON="/path/to/venv/bin/python"` but doesn't export the venv `bin/` dir, subprocesses can't find `ninja` (which lives at `/path/to/venv/bin/ninja`). **FIX**: Add `export PATH="/path/to/venv/bin:$PATH"` at the top of any serve script that launches vLLM. This is a general vLLM + FlashInfer issue, not DFlash-specific.
37. **CRITICAL — vLLM DFlash produces 0% acceptance on Qwen3.6 hybrid GDN targets (verified Jul 14 2026)**: Even after ALL patches (#34-36), vLLM DFlash launches and runs but the draft model generates garbage — acceptance rate 0.0-0.7%, mean acceptance length 1.0, per-position rates all 0.000 (except pos 0 at ~3%). **Symptoms**: generation throughput 2-3 tok/s (SLOWER than baseline 3.1 tok/s), drafted throughput 30-45 tok/s (draft model works fast but all outputs rejected), Triton JIT compilation warnings during inference. **Root cause**: vLLM's hidden state extraction path for DFlash (`DFlashProposer`) does not correctly handle hybrid GDN (GatedDeltaNet) + FullAttention layers in Qwen3.6 — the target hidden states passed to the draft model are wrong, so the draft model predictions are random. **The z-lab DFlash draft model is NOT broken** — SGLang achieves 20-40% acceptance with the exact same draft model. **FIX**: Use SGLang (`python -m sglang.launch_server --speculative-algorithm DFLASH ...` with `--attention-backend flashinfer`). Do NOT waste time debugging vLLM DFlash acceptance on hybrid targets — switch engines. vLLM DFlash may work on pure-attention (non-hybrid) targets but this is unverified.
38. **SGLang DFlash build requires protoc + rust on ARM64 (verified Jul 14 2026)**: Installing SGLang from PR #23000 on ARM64/GB10 requires: (a) Rust compiler (`curl ... | sh -s -- -y && source ~/.cargo/env`), (b) protoc (use torch bundled: `export PROTOC="$(python -c 'import torch,os;print(os.path.join(os.path.dirname(torch.__file__),"bin","protoc"))')"`). Without these, pip install fails with `can not find Rust compiler` or `Could not find protoc`. SGLang installs to its own venv — does NOT conflict with existing vLLM install.
39. **SGLang API model name = full --model-path string (verified Jul 14 2026)**: Unlike vLLM (which supports --served-model-name), SGLang uses the exact --model-path value as the model identifier in API requests. Sending a custom model name to a SGLang server will fail with model-not-found. Always use the full path string. Check with curl http://localhost:PORT/v1/models. See references/sglang-dflash-deployment.md for details.
40. **SGLang DFlash first decode batch is ~7x slower than steady state (verified Jul 14 2026)**: The first decode batch after server startup runs at ~1.4 tok/s (vs 10+ tok/s steady state) because Triton kernels (rejection_greedy_sample_kernel, eagle_prepare_inputs_padded_kernel, etc.) are JIT-compiled on first use. Always send a warmup request before benchmarking. Subsequent batches reach steady state immediately.
41. **Quantized draft model as spec decoder UNDERPERFORMS on bandwidth-bound hardware (verified Jul 14 2026)**: Using a quantized version of the same model (INT4/INT2) as the draft model seems appealing (high acceptance ~75% due to same architecture), but on bandwidth-bound hardware (GB10, Jetson, consumer GPU with LPDDR/DDR), the draft model must still be fully loaded per token generation. For 35B MoE in INT4: 17.5GB × 8 sequential tokens = 512ms draft time, vs 256ms verify time — **draft phase takes longer than verify**. Plus both models must coexist in VRAM simultaneously (88GB for bf16 target + INT4 draft). **FIX**: On bandwidth-bound hardware, quantize the TARGET instead (INT4 target + DFlash/EAGLE3 draft = 18GB VRAM, ~30-75 tok/s). See `references/bandwidth-bound-strategy.md` for full analysis and decision framework.
42. **SGLang speculative algorithms (verified Jul 14 2026)**: SGLang supports 6 speculative algorithms via `--speculative-algorithm`: EAGLE, EAGLE3, NEXTN (native MTP), STANDALONE (classic separate draft model — autoregressive, doesn't share embeddings with target), NGRAM (prompt-lookup), DFLASH (block diffusion). For quantized drafts, use `--speculative-draft-model-quantization awq` (or gptq/fp8). Default: draft inherits target's quantization. Use `unquant` to force bf16 draft on quantized target.
43. **Cross-architecture speculative decoding — vocabulary mismatch is a HARD BLOCKER (verified Jul 14 2026)**: Using a model from family A (e.g., DiffusionGemma, Gemma vocab=262144) as draft for a target from family B (e.g., Qwen3.6, vocab=248320) is impossible without retraining. Speculative decoding compares token IDs between draft and target — if they use different tokenizers, IDs don't align and acceptance is 0%. Additionally, using a **same-size** model as draft (e.g., DiffusionGemma-26B as draft for Qwen3.6-27B) fails on VRAM (108GB for both on GB10 — OOM). **Correct approaches for diffusion-based drafting of AR models**: (a) **DEER** (arXiv:2512.15176) — train a small 0.5B diffusion model under the target's tokenizer, achieves 32-token acceptance and 5.54x speedup on Qwen3-30B-A3B. (b) **DiffuSpec** (arXiv:2510.02358) — training-free if draft and target share a tokenizer, uses causal-consistency path search. (c) **DFlash** (already covered above) — purpose-built diffusion drafter, NOT a reused DLM. See `references/cross-architecture-speculative-decoding.md` for full analysis, DEER/DiffuSpec/DART/ML-SpecQD/MoE-SpeQ paper summaries, and decision matrix.
44. **MoE quantization is effectively binary — "unquantized experts" is not a middle ground**: For MoE models (Qwen3.5/3.6-35B-A3B, Agents-A1, DeepSeek-V3), routed experts are ~90% of total parameters (~31.5B of 35B). Quantizing only attention/embeddings (the remaining ~2B params) saves <2 GB — the model stays at ~64 GB (same as BF16). The real choices are: BF16 (66 GB), FP8 dynamic (36 GB, <0.5% quality loss — recommended for DFlash on GB10), or INT4/Q5 GGUF (22 GB, 2-5% loss). There is no meaningful "APEX without expert quantization" config. If a user asks for this, explain that experts ARE the model and the choice is FP8 or BF16. See `references/bandwidth-bound-strategy.md` → "MoE Parameter Budget" for the full breakdown.
45. **FP8 dynamic is the optimal DFlash target quantization on GB10 (verified Jul 16 2026)**: FP8 leaves 60 GB headroom (36 GB model vs 121 GB total), while BF16 leaves only ~26 GB (dangerously tight with Hermes stack — caused 3 crashes, pitfall #17). FP8 quality loss is <0.5% (vs 2-5% for INT4 GGUF). Critically, INT4 GGUF via llama.cpp has ZERO DFlash benefit on MoE models (pitfall #1), so the INT4 path loses both quality AND speedup. Use `templates/serve_sglang_dflash_fp8.sh` for the FP8 SGLang deployment recipe. The FP8 recipe quantizes routed experts + full_attention to FP8 while keeping lm_head, router/gate, embed_tokens, shared_expert, and linear_attn at BF16 — an optimal split.
46. **SGLang `--attention-backend triton` avoids FlashInfer JIT OOM on large BF16 models (verified Jul 16 2026)**: On GB10 unified memory, serving a BF16 model (65-70 GB) with `--attention-backend flashinfer` triggers a 20-30 GB JIT compilation spike during cold start (6+ parallel `cicc` CUDA compiler processes x 1.5-6 GB each). Combined with model weights (65 GB), this can exceed 121 GB total and crash the system. The JIT spike is INVISIBLE to `nvidia-smi` (process RSS, not GPU memory) — check `ps aux --sort=-%mem | head`. **FIX**: Use `--attention-backend triton` for BF16 models >50 GB on GB10 — completely bypasses FlashInfer, zero JIT compilation. ~10-15% slower steady-state but eliminates the OOM risk. For FP8/smaller models (<40 GB), flashinfer is fine (enough headroom for JIT spike). Also set `export MAX_JOBS=1 NVCC_THREADS=1` before launching SGLang.
47. **CRITICAL — `vm.min_free_kbytes` must be raised on DGX Spark (verified Jul 16 2026)**: The default `vm.min_free_kbytes` on DGX Spark is ~45167 (44 MB) — dangerously low for unified memory workloads. When GPU/CPU shared memory approaches 100%, the kernel itself starves before the OOM killer can fire, causing **hard system freezes** (not graceful OOM kills). Multiple DGX Spark users report this on NVIDIA forums. **FIX**: `sudo sysctl -w vm.min_free_kbytes=2097152` (reserve 2 GB for kernel/OOM killer), `vm.swappiness=10`, `vm.overcommit_memory=1`. Make permanent via `/etc/sysctl.d/99-dgx-spark.conf`. This was a root cause of repeated system crashes during BF16 model serving.
48. **Use FP8 model for hidden state extraction when serving BF16 (verified Jul 16 2026)**: When training a DFlash/DSpark draft for a BF16 target model, use the FP8 version of the same model for vLLM hidden state extraction (Step 1 of offline pipeline). FP8 hidden states are numerically close to BF16 (FP8 dynamic is ~lossless), and the draft model learns the mapping from hidden states to tokens — small FP8 noise is absorbed during training. This avoids the 65 GB BF16 + vLLM + Hermes OOM risk while producing draft-quality results equivalent to BF16 extraction. The BF16 model is only loaded at serving time (SGLang), where `--attention-backend triton` + `--mem-fraction-static 0.62` manage memory safely.
49. **DSpark progressive training requires `--from-pretrained` for block size scaling (verified Jul 16 2026)**: To train DSpark at BS=32 or BS=64, start from a BS=16 checkpoint via `--from-pretrained /path/to/checkpoint_bs16`. Direct training at large block sizes from scratch causes quality collapse (all papers agree: TDAR arXiv:2602.09555, T* arXiv:2601.11214, SDAR arXiv:2510.06303). The progressive schedule is: Stage 1 BS=16 gamma=7 -> Stage 2 BS=32 gamma=14 -> Stage 3 BS=64 gamma=28. See `references/dspark-progressive-training.md` for the full parameter table and concrete commands.
52. **DFlash is multimodal-safe — does NOT break image processing (verified Jul 16 2026)**: Common concern: will enabling DFlash on a VL model break images? No. DFlash operates ONLY on the decode phase (text generation). The vision encoder runs during prefill — DFlash is not involved. After target processes images in prefill, hidden states at layers [3,7,11,...] already carry image context. The DFlash draft predicts text from these image-aware hidden states without ever seeing pixels. Implication: at serving time, do NOT set limit-mm-per-prompt image:0 — the model must accept images normally. Image prefill runs at baseline speed, but text generation after the image IS accelerated by DFlash. Applies to EAGLE3 as well.

53. **Pretrained DFlash config.json has wrong target_layer_ids — snap to full_attention (verified Jul 16 2026)**: Official z-lab Qwen3.5-35B-A3B-DFlash ships target_layer_ids [1,6,11,16,22,27,32,37] — 6 of 8 are linear_attention (GDN) on Qwen3.5-MoE targets. FIX: (1) Read target model layer_types to find full_attention indices ([3,7,11,15,19,23,27,31,35,39] for Qwen3.5/3.6). (2) Snap each pretrained ID to nearest full_attention layer. (3) Ensure no duplicates. (4) Backup config.json before patching. Example: [1,6,11,16,22,27,32,37] snaps to [3,7,11,15,23,27,31,35]. Weights trained on wrong layers — snapped config loads but acceptance is suboptimal until Step 2 retraining on correct hidden states.

50. **speculators `--loss-fn` for DSpark: use weighted CE+TV not default kl_div (verified Jul 16 2026)**: The official DSpark training example (`dspark_qwen3_0_6b_sharegpt_online.sh`) uses a weighted combination of cross-entropy (10%) and total variation (90%) as the loss function. This differs from the default `kl_div` loss used for EAGLE3. The `tv` (total variation) component helps the Markov head learn smoother logit distributions across block positions.
51. **CRITICAL - Multimodal encoder cache profiling OOM during hidden state extraction (verified Jul 16 2026)**: When using `launch_vllm.py` for Step 1 (hidden state generation) with a multimodal target model (Qwen3.5-MoE VL, Agents-A1, Qwen3.6-VL), vLLM profiles **16 images at maximum feature size** x `max-num-seqs` during initialization. On GB10 with a 65 GB BF16 model, this adds a ~28 GB spike (91 to 119 GB) and crashes the system - even with correct `gpu_memory_utilization` and `MAX_JOBS`. **Diagnostic**: `nvcc procs: 0` in monitoring output means this is NOT a cicc JIT spike. Log shows `Encoder cache will be initialized with a budget of 262144 tokens, and profiled with 16 image items of the maximum feature size.` followed by RAM spike. **FIX**: Add `--limit-mm-per-prompt '{"image": 1}'` and `--max-num-seqs 1` to the vLLM launch arguments after the `--` separator in `launch_vllm.py`. Use image: 0 (not image: 1) because training datasets (UltraChat, ShareGPT) are text-only — the vision encoder is never exercised during extraction. Images are still fully supported at SERVING time (Step 3). See `vllm-gb10` skill -> "Multimodal Encoder Cache Profiling Spike" section for the full diagnostic table distinguishing JIT vs encoder cache OOM`.
