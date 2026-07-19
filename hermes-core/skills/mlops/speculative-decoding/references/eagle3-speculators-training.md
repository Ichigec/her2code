# EAGLE3 Draft Model Training with Speculators

Full workflow for training EAGLE3 speculative decoding draft models using the
`vllm-project/speculators` framework (v0.5.0+). Covers offline training (for
single-GPU systems like DGX Spark), online training (multi-GPU), MoE-specific
parameters, and adapting pre-trained drafts.

## Framework Overview

**Repository:** https://github.com/vllm-project/speculators
**Docs:** https://docs.vllm.ai/projects/speculators/
**PyPI:** `speculators>=0.5.0`

Speculators is the official vLLM framework for building, training, and deploying
speculative decoding draft models. Key features:
- E2E training of single and multi-layer draft models
- Supports both dense and MoE target models
- Trained models run seamlessly in vLLM (`vllm serve` auto-reads config)
- Also supports DFlash, P-EAGLE, MTP speculator types
- HuggingFace-compatible format

## Prerequisites

- Python 3.10+
- CUDA-capable GPU(s)
- vLLM >= 0.18 (separate venv recommended)
- speculators >= 0.5.0 (separate venv recommended)

```bash
# Speculators venv (training)
uv venv speculators_venv
source speculators_venv/bin/activate
uv pip install "speculators>=0.5.0"

# vLLM venv (hidden state extraction + deploy)
uv venv vllm_venv
source vllm_venv/bin/activate
uv pip install "vllm>=0.18"
```

## Training Modes

### Online Training (multi-GPU, 2+ GPUs)

vLLM runs on some GPUs, training runs on others simultaneously. Hidden states
are generated on-demand during training.

**Time:** ~17 min on 4×H100 (2 for vLLM, 2 for training)
**Best for:** Multi-GPU systems, rapid iteration

### Offline Training (single-GPU, e.g. DGX Spark)

Hidden states are pre-generated and cached to disk, then vLLM is stopped to
free GPU memory for training.

**Time:** ~10 min on 2×H100 (including data gen), ~2-4h on DGX Spark (35B MoE)
**Best for:** Single-GPU systems, DGX Spark, limited GPU memory

> **WARNING — background pipeline hazard:** The offline workflow involves
> launching vLLM, generating data, then killing vLLM. If you run this as an
> automated background script, ALWAYS save the vLLM PID (`VLLM_PID=$!`) and
> kill only that PID. Never use `kill $(pgrep -f vllm)` — it will match
> ANY vLLM process, including ones you or the user started manually in
> another session. See Pitfall #26 in the SKILL.md.

## Offline Training Workflow (DGX Spark)

### Architecture

```
┌─────────────────────────────────────────────────────┐
│  DGX Spark 128GB Unified Memory                     │
│                                                     │
│  Phase 1: vLLM serve target model                  │
│           → generate hidden states → save to disk   │
│           [35B MoE FP8 ≈ 35GB VRAM]                 │
│                                                     │
│  Phase 2: Stop vLLM → free VRAM                    │
│                                                     │
│  Phase 3: Train EAGLE3 draft model                 │
│           [draft ~0.4B + hidden states in memory]   │
│           [Single-GPU, no FSDP needed]              │
│                                                     │
│  Phase 4: Deploy vLLM with EAGLE3 speculator       │
└─────────────────────────────────────────────────────┘
```

### Step 1: Prepare Data

```bash
# in speculators venv
python scripts/prepare_data.py \
  --model InternScience/Agents-A1 \
  --data sharegpt \
  --data ultrachat \
  --output ./training_data \
  --max-samples 5000 \
  --seq-length 8192
```

Parameters:
- `--model` — Target model (HuggingFace ID or local path)
- `--data` — Dataset: `sharegpt`, `ultrachat`, or custom JSONL path. Can be supplied multiple times.
- `--max-samples` — Limit samples (start with 5K for testing)
- `--seq-length` — Maximum sequence length

For agentic models (Agents-A1), consider adding custom agent traces
(tool-calling, multi-step reasoning) as a JSONL dataset.

Output:
```
training_data/
├── data-*.arrow files
├── dataset_info.json
├── state.json
└── token_freq.pt    # Token frequencies for vocab mapping
```

**Time:** ~1-2 minutes for 5K samples

### Step 2: Launch vLLM Server

```bash
# in vLLM venv
# CRITICAL for hybrid attention models (Qwen3.5-MoE, Agents-A1):
#   Default layer IDs [2, 20, 37] hit ALL linear_attention layers!
#   Must specify --target-layer-ids to hit full_attention layers.
#   Agents-A1 pattern: [lin,lin,lin,full] x10, full at indices 3,7,11,...,39
#
# NOTE: --target-layer-ids is a launch_vllm.py argument, NOT a vLLM argument.
#   It must go BEFORE the -- separator. Putting it after -- passes it to vLLM
#   which doesn't understand it, causing silent fallback to default (wrong) layers.
# CRITICAL: Set MAX_JOBS and NVCC_THREADS before launching vLLM on GB10
# MAX_JOBS=1 for cold start (model not yet loaded, ~8GB free for compilers)
# MAX_JOBS=5 is safe AFTER model is loaded (40GB free, 5 cicc × 3GB = 15GB)
# — but can't change env of running process, so use 1 for first start.
# For subsequent starts (cache warm), MAX_JOBS=5 speeds up profile-run JIT.
export MAX_JOBS=1
export NVCC_THREADS=1

python scripts/launch_vllm.py \
  InternScience/Agents-A1 \
  --target-layer-ids 3 19 39 \
  -- --dtype bfloat16 \
     --gpu-memory-utilization 0.65 \
     --max-model-len 8192 \
     --max-num-seqs 4 \
     --kv-cache-dtype fp8 \
     --no-enable-prefix-caching \
     --swap-space 0 \
     --enforce-eager \
     --port 8000
```

**Do NOT set `--max-num-batched-tokens`** below `--max-model-len`. Since
`launch_vllm.py` force-adds `--no-enable-chunked-prefill`, vLLM requires
`max_num_batched_tokens >= max_model_len`. Setting it to 1024 with
`max-model-len 8192` causes a `ValidationError`. Omit the flag entirely
(vLLM defaults it to `max_model_len`).

DGX Spark memory tuning (GB10 unified memory — GPU RAM == System RAM):
- `--gpu-memory-utilization` is NOT a consumption limit — it's a KV cache budget
  (`CUDA_total × utilization`). Model weights ALWAYS load fully (66.5 GiB for BF16).
  See `references/vllm-uma-memory-tuning.md` for the full derivation.
- **0.65 is the correct value for BF16 Agents-A1** (NOT 0.5-0.55, which causes
  system hangs: budget = 66.9 GiB, model = 66.5 GiB, remainder = 0.4 GiB —
  insufficient for vLLM's profile_run → PyTorch grabs system RAM → swap → hang).
- **0.75 causes NVRM OOM** — the AutoTuner phase (FlashInfer kernel autotuning
  after model load) needs extra GPU memory. 0.65 is proven safe. Verified Jul 13 2026.
- `--max-model-len 8192` matches the `--seq-length 8192` in Step 1. KV cache cost is
  negligible for this model (335 MB for 8192×4 batch in fp8) — only 10/40 layers have
  full attention. Even 32768 would only cost 1.3 GB.
- `--kv-cache-dtype fp8` halves KV cache — safe for EAGLE3 (hidden states come from
  model layers, not KV cache). Agents-A1's KV cache is tiny anyway (only 10 full_attention
  layers out of 40, 2 KV heads, ~20 KB/token).
- `--concurrency 4` in data_generation_offline.py should match `--max-num-seqs 4` in vLLM.
  Higher concurrency sends more concurrent requests than vLLM can batch, wasting client
  memory on queued results.
- `--swap-space 0` — on unified memory, swap targets the same RAM (pointless).
- `--enforce-eager` — disables CUDA graph capture, saves ~1-2 GiB.
- For FP8 model (~35GB): `--gpu-memory-utilization 0.5` is fine (35GB model leaves
  plenty of headroom at any utilization).

Wait for server:
```
INFO:     Application startup complete.
```

### FlashInfer JIT Compilation on GB10 (Expect 40-60 min Cold Start)

vLLM on GB10 with FlashInfer has **two waves** of JIT compilation:

**Wave 1 — Startup JIT (before model load, ~30-40 min with MAX_JOBS=1):**
FlashInfer compiles CUTLASS MoE GEMM kernels for all supported dtype/quant
combinations. ~104 .o files, ~155 MB cache. Kernels: moe_gemm_kernels_{bf16,fp16,
fp8,fp4,fp32}_{bf16,fp8,fp4,uint4,uint8,fp16,fp32}, cutlass_kernel_file_gemm_sm90
(M64/M128 groups), cutlass_kernel_file_gemm_grouped_sm120 (Blackwell-specific).

**Wave 2 — Profile-Run / AutoTuner JIT (after model load, ~10-20 min):**
After weights load, vLLM runs a profile pass with actual tensor shapes. This
triggers compilation of NEW kernel variants (different M sizes: M16, M256)
that weren't needed at startup. FlashInfer AutoTuner then benchmarks 21 tactics
per GEMM (gemm1, gemm2) and saves configs to
`~/.cache/vllm/flashinfer_autotune_cache/`.

**Total cold-start time: ~50-60 min** (Wave 1 + model load ~8 min + Wave 2).
Subsequent starts reuse cache → ~8 min (model load only).

**Symptoms that confuse:**
- Log appears FROZEN for 10-20 min after "Encoder cache will be initialized..."
  — Python stdout is block-buffered when redirected to file. The process is
  working (check `ps -o utime= -p <pid>` — if CPU time increases, it's alive).
- Port 8000 not open during Wave 2 — APIServer waits for EngineCore.
- `ps aux | grep nvcc` shows 4-6 compiler processes even though "nothing is
  happening" — these are Wave 2 kernels compiling sequentially (MAX_JOBS=1).

**FlashInfer cache location — CRITICAL for Hermes-launched vLLM:**
When vLLM is launched from Hermes (HOME=/home/user/.hermes/home), FlashInfer
cache goes to `~/.hermes/home/.cache/flashinfer/` NOT `~/.cache/flashinfer/`.
Previous compilation in `~/.cache/` is NOT reused → full recompilation (50-60
min again). Fix: copy or symlink cache before launching:
```bash
cp -rn ~/.cache/flashinfer/* ~/.hermes/home/.cache/flashinfer/
```

**Manual pre-compilation workaround (ninja build):**
If vLLM keeps crashing during compilation (OOM from cicc processes), pre-compile
the FlashInfer cache manually using ninja, outside of vLLM:
```bash
cd ~/.cache/flashinfer/0.6.13/121a/cached_ops/fused_moe_120/
source /home/user/vllm_venv/bin/activate
export MAX_JOBS=1 NVCC_THREADS=1
ninja -j1
```
This compiles all .o files and links the .so without loading the model. Then
launch vLLM — it will find the cached .so and skip compilation entirely.

**MAX_JOBS tuning:**
- `MAX_JOBS=1` — safe for cold start (model not yet loaded, ~8 GB free for
  compilers). Required when launching vLLM with 66 GB model.
- `MAX_JOBS=5` — safe AFTER model is loaded (40 GB free, 5 cicc × 3 GB = 15 GB).
  Cannot change env of running process, so use 1 for first start. For subsequent
  starts (cache warm), 5 speeds up Wave 2 significantly.
- `MAX_JOBS=1 NVCC_THREADS=1` adds ~30 min to startup but prevents OOM.
  `MAX_JOBS=5` with warm cache adds ~5 min.

The script auto-selects target layer IDs for EAGLE3 if `--target-layer-ids`
is not specified. Default: `[2, num_layers//2, num_layers-3]`.

**CRITICAL for hybrid attention models**: Qwen3.5-MoE architectures (Agents-A1,
Qwen3.6-35B-A3B) use `[linear, linear, linear, full]` repeating pattern
(`full_attention_interval: 4`). The default selection `[2, 20, 37]` lands on
ALL linear_attention layers — hidden states from these layers are less
informative, causing silent low acceptance rates. Always specify
`--target-layer-ids 3 19 39` (or similar full_attention indices) for hybrid
models. See `references/agents-a1-architecture.md` for the full layer map.

### Step 3: Generate Hidden States (Offline)

```bash
# in speculators venv
python scripts/data_generation_offline.py \
  --preprocessed-data ./training_data \
  --endpoint http://localhost:8000/v1 \
  --output ./training_data/hidden_states \
  --max-samples 5000 \
  --concurrency 4 \
  --validate-outputs
```

Output: one `hs_N.safetensors` file per sample.

**What vLLM does here is forward pass, NOT generation.** Each sample's tokens
are run through the model in a single forward pass to extract intermediate
layer activations. This is ~5-10x faster than autoregressive generation of
the same number of tokens. For 5K samples (~6.5M tokens total), expect
~1-2h on DGX Spark at ~500-1000 tokens/sec forward throughput.

**Per-sample disk estimation:**
```
avg_seq_len × num_extracted_layers × hidden_size × dtype_bytes = bytes
```
For Agents-A1 (3 layers, hidden_size=2048, BF16):
```
4096 × 3 × 2048 × 2 = ~50 MB per sample (avg seq_len ~1300 → ~16 MB actual)
5K samples: ~80-250 GB depending on avg seq_len
10K samples: ~160-500 GB
```

**Disk space:** ~1.6TB for 50K samples (Llama-3.1-8B, avg seq 1024). For 5K
samples on a 35B MoE model, estimate ~200-400GB. Use fast NVMe.

**Resuming:** The script auto-detects existing `hs_*.safetensors` files and
skips them. Just rerun the same command.

**Multi-node:** Split dataset with `--world-size N --rank i` across machines.

### Step 4: Stop vLLM

**CRITICAL — never use `kill $(pgrep -f vllm)` in pipeline scripts.** This
matches ANY process with "vllm" in its command line, including vLLM instances
launched manually in other sessions. If a background pipeline from a previous
session is still running, its cleanup phase will SIGTERM your new vLLM process.

**Correct approach — save and kill the specific PID:**
```bash
# When launching vLLM in background, save the PID:
python scripts/launch_vllm.py ... &
VLLM_PID=$!

# ... wait for server, generate hidden states ...

# Kill ONLY this specific vLLM process:
kill $VLLM_PID
wait $VLLM_PID 2>/dev/null

# Verify GPU memory is freed
nvidia-smi  # or: free -h on GB10
```

**Before launching vLLM, always check for leftover processes:**
```bash
pgrep -af "vllm.entrypoints"  # should be empty
pgrep -af "data_generation"   # should be empty
```

If leftover processes exist from a previous session, kill them by their specific
PID (shown by `pgrep -af`), not by pattern match.

### Step 5: Train EAGLE3 Draft Model

```bash
# in speculators venv
# Single-GPU training (DGX Spark)
python scripts/train.py \
  --verifier-name-or-path InternScience/Agents-A1 \
  --data-path ./training_data \
  --hidden-states-path ./training_data/hidden_states \
  --save-path ./checkpoints/agents-a1-eagle3 \
  --speculator-type eagle3 \
  --draft-arch qwen3 \
  --num-layers 1 \
  --draft-vocab-size 8192 \
  --epochs 10 \
  --lr 1e-4 \
  --total-seq-len 8192 \
  --batch-size 8 \
  --on-missing skip \
  --ttt-steps 3 \
  --fc-norm \
  --norm-output \
  --norm-before-residual \
  --optimizer muon \
  --muon-lr 1e-3 \
  --muon-momentum 0.95 \
  --muon-weight-decay 0.1 \
  --target-layer-ids 3 19 39 \
  --hidden-states-dtype bfloat16 \
  --logger tensorboard \
  --log-dir ./logs
```

**Multi-GPU (FSDP) if available:**
```bash
CUDA_VISIBLE_DEVICES=2,3 torchrun \
  --standalone --nproc_per_node=2 \
  scripts/train.py \
  --verifier-name-or-path InternScience/Agents-A1 \
  --data-path ./training_data \
  --hidden-states-path ./training_data/hidden_states \
  --save-path ./checkpoints/agents-a1-eagle3 \
  --speculator-type eagle3 \
  --draft-arch qwen3 \
  --num-layers 1 \
  --draft-vocab-size 8192 \
  --epochs 10 \
  --lr 1e-4 \
  --on-missing skip \
  --ttt-steps 3 \
  --target-layer-ids 3 19 39
```

### Key train.py Parameters

| Parameter | Default | Description |
|---|---|---|
| `--speculator-type` | `eagle3` | Type: eagle3, dflash, dspark, peagle, mtp |
| `--draft-arch` | `llama` | Draft decoder architecture: `llama` or `qwen3` |
| `--num-layers` | 1 | Number of transformer layers in draft model |
| `--draft-vocab-size` | None | Reduced vocab size (uses token_freq.pt to select top-K tokens) |
| `--batch-size` | 8 | Batch size for training (reduce if OOM) |
| `--ttt-steps` | 3 | Training-Time Test rollout steps (paper recommends 7 for max quality) |
| `--fc-norm` | False | Per-layer RMSNorm before FC projection (Eagle 3.1 paper) |
| `--norm-output` | True (eagle3) | Feed post-norm hidden states back across TTT steps |
| `--norm-before-residual` | False | Normalize before residual connection (Eagle 3.1) |
| `--optimizer` | `muon` | Muon for 2D weights + AdamW for rest. Alt: `adamw` |
| `--muon-lr` | 1e-3 | Learning rate for Muon optimizer (2D weights) |
| `--muon-momentum` | 0.95 | Momentum for Muon optimizer |
| `--muon-weight-decay` | 0.1 | Weight decay for Muon optimizer |
| `--on-missing` | `generate` | Behavior when cached hidden states missing: generate, skip, warn, raise |
| `--on-generate` | `delete` | After generating: `delete` (pure online) or `cache` (hybrid) |
| `--total-seq-len` | 8192 | Max total sequence length for training batches |
| `--target-layer-ids` | auto | Layer IDs for hidden states. Must match launch_vllm.py |
| `--hidden-states-dtype` | `bfloat16` | Dtype for hidden states (bfloat16, float16, float32) |
| `--from-pretrained` | None | Path to existing draft checkpoint (for fine-tuning) |
| `--dry-run` | False | Build, init, save checkpoint, exit (validate before training) |

### Step 6: Deploy

```bash
# in vLLM venv
vllm serve InternScience/Agents-A1 \
  --speculative-config '{
    "method": "eagle3",
    "model": "./checkpoints/agents-a1-eagle3",
    "num_speculative_tokens": 4,
    "eagle_topk": 1
  }' \
  --dtype bfloat16 \
  --gpu-memory-utilization 0.8
```

For llama.cpp deployment, convert the draft to GGUF:
```bash
python convert_hf_to_gguf.py ./checkpoints/agents-a1-eagle3 \
  --outfile eagle3-draft.gguf --outtype f16
```

## Online Training Workflow (Multi-GPU)

```bash
# Terminal 1: vLLM server (GPUs 0,1)
# in vLLM venv
CUDA_VISIBLE_DEVICES=0,1 python scripts/launch_vllm.py \
  InternScience/Agents-A1 -- --data-parallel-size 2 --port 8000

# Terminal 2: Training (GPUs 2,3)
# in speculators venv
CUDA_VISIBLE_DEVICES=2,3 torchrun --standalone --nproc_per_node=2 \
  scripts/train.py \
  --verifier-name-or-path InternScience/Agents-A1 \
  --data-path ./output \
  --vllm-endpoint http://localhost:8000/v1 \
  --save-path ./output/checkpoints \
  --draft-vocab-size 8192 \
  --epochs 5 \
  --lr 1e-4 \
  --total-seq-len 8192 \
  --on-missing generate \
  --on-generate delete
```

Online training generates hidden states on-demand via vLLM API and deletes
them after loading (pure online mode). **Note**: For hybrid attention models
(Agents-A1, Qwen3.5-MoE), also pass `--target-layer-ids 3 19 39` to both
`launch_vllm.py` and `train.py` — see hybrid attention warning above.

## Fine-tuning Pre-trained Draft (Faster Path)

Instead of training from scratch, fine-tune an existing EAGLE3 draft from
a similar architecture:

```bash
python scripts/train.py \
  --verifier-name-or-path InternScience/Agents-A1 \
  --from-pretrained nm-testing/Speculator-Qwen3-30B-MOE-VL-Eagle3 \
  --data-path ./training_data \
  --hidden-states-path ./training_data/hidden_states \
  --save-path ./checkpoints/agents-a1-eagle3-finetuned \
  --epochs 3 \
  --lr 5e-5 \
  --on-missing skip \
  --ttt-steps 3
```

**Before attempting:** Verify hidden_size compatibility:
```python
from transformers import AutoConfig
c1 = AutoConfig.from_pretrained("nm-testing/Speculator-Qwen3-30B-MOE-VL-Eagle3")
c2 = AutoConfig.from_pretrained("InternScience/Agents-A1")
print(f"Draft hidden_size: {c1.hidden_size}")
print(f"Target hidden_size: {c2.hidden_size}")
print(f"Match: {c1.hidden_size == c2.hidden_size}")
```

## MoE-Specific Notes

- `--draft-arch qwen3` is required for Qwen3.5-MoE targets (Agents-A1, Qwen3.6-35B-A3B)
- Speculators framework explicitly supports MoE model training (both non-MoE and MoE)
- MoE routing overhead may reduce acceptance rate — compensate with:
  - More TTT steps (7 instead of 3)
  - More training data (10-20K samples)
  - Lower `num_speculative_tokens` at inference (2-3 instead of 4)
- Expert specialization means the draft model needs to learn routing-aware
  token prediction — more diverse training data helps

## DGX Spark Memory Budget

**CRITICAL**: On GB10, GPU and CPU share the same physical RAM (unified memory).
CUDA `total_memory` = 121.69 GiB = system RAM (NOT 128 GB or 130 GB).
vLLM's `gpu_memory_utilization` is a fraction of this CUDA total, NOT a consumption
limit — model weights always load fully. See `references/vllm-uma-memory-tuning.md`
for the full derivation and vLLM source code analysis.

### BF16 (66.5 GiB model — abliterated, max quality)

| Phase | VRAM Usage | Notes |
|---|---|---|
| vLLM serve (BF16, util=0.65) | ~79 GiB | 66.5 GiB weights + 5 GiB profile/overhead + 7.6 GiB KV cache (fp8, mostly unused) |
| Hidden state generation | ~79 GiB | vLLM running, data pipeline lightweight (~2 GiB client) |
| Training (0.4B draft) | ~17 GiB | 1 GiB draft + 4 GiB hidden states batch + 4 GiB gradients + 8 GiB activations |
| Deploy (BF16 + draft, util=0.85) | ~103 GiB | 66.5 GiB weights + KV cache + draft model |

**BF16 is memory-tight**: vLLM (79 GiB at 0.65) + OS/other procs (~12 GiB) = 91 GiB
of 121.69 GiB. Leaves ~30 GiB headroom for data generation client. Must use offline
training (generate hidden states first, stop vLLM, then train).

**DO NOT set `--gpu-memory-utilization` below 0.60 for BF16**: at 0.55, budget =
66.9 GiB, model = 66.5 GiB, remainder = 0.4 GiB — insufficient for vLLM's profile_run
(~3 GiB) → PyTorch grabs system RAM → swap → system hangs. This was verified Jul 13 2026.

### FP8 (35 GiB model — quantized, faster)

| Phase | VRAM Usage | Notes |
|---|---|---|
| vLLM serve (FP8, util=0.5) | ~61 GiB | 35 GiB weights + 5 GiB overhead + 21 GiB KV cache |
| Training (0.4B draft) | ~17 GiB | Same as BF16 |
| Deploy (FP8 + draft, util=0.6) | ~73 GiB | 35 GiB weights + KV cache + draft |

FP8 has enough headroom (61+17=78 GiB < 121.69 GiB) for online training if desired,
but offline is still recommended for stability.

## Training Time Estimates

| System | Target Model | Samples | Time |
|---|---|---|---|
| 2× H100 | Llama-3.1-8B | 5K | ~10 min |
| 4× H100 | Qwen3-8B | 5K | ~17 min (online) |
| DGX Spark | Agents-A1 (35B MoE) | 5K | ~2-4h (offline) |
| DGX Spark | Agents-A1 (35B MoE) | 10K | ~4-8h (offline) |

## Verification

After training, verify the draft model works:

```bash
# Dry-run validation (builds model, saves checkpoint, exits)
python scripts/train.py \
  --verifier-name-or-path InternScience/Agents-A1 \
  --from-pretrained ./checkpoints/agents-a1-eagle3 \
  --dry-run \
  --save-path ./validation

# Then test in vLLM
vllm serve InternScience/Agents-A1 \
  --speculative-config '{"method": "eagle3", "model": "./checkpoints/agents-a1-eagle3", "num_speculative_tokens": 4}'
```

## References

- Speculators docs: https://docs.vllm.ai/projects/speculators/
- Online training tutorial: https://docs.vllm.ai/projects/speculators/en/latest/user_guide/tutorials/train_eagle3_online/
- Offline training tutorial: https://docs.vllm.ai/projects/speculators/en/latest/user_guide/tutorials/train_eagle3_offline/
- train.py CLI reference: https://docs.vllm.ai/projects/speculators/en/latest/cli/train/
- DeepWiki (training system): https://deepwiki.com/vllm-project/speculators/3.2-model-training-with-eagle3
- EAGLE-3 paper: https://arxiv.org/abs/2503.01840
- Example train.py (GPT-OSS-120B): https://huggingface.co/stevenabreu7/gpt-oss-120b-speculator.eagle3/blob/main/train.py
