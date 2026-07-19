---
name: eagle3-speculator-training
description: "Use when training EAGLE3 (or dflash/peagle/mtp) speculative decoding draft models using the speculators library (vllm-project/speculators) on a single GPU. Covers the full offline pipeline: data prep, vLLM hidden-states extraction, and draft model training. Includes Qwen3.5 MoE specifics and pitfalls."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [eagle3, speculative-decoding, speculators, vllm, draft-model, qwen, training]
    related_skills: [vllm-gb10, serving-llms-vllm]
---

# EAGLE3 Speculator Training Pipeline

## Overview

The [speculators](https://github.com/vllm-project/speculators) library trains speculative decoding draft models that deploy directly into vLLM. The offline pipeline has 3 phases:

1. **Data prep** (`prepare_data.py`) — tokenize chat data, build loss masks, compute token frequencies
2. **Hidden states extraction** (`launch_vllm.py` + `data_generation_offline.py`) — run vLLM as a "producer" that extracts intermediate layer activations for each training sample
3. **Training** (`train.py`) — train a small draft model on the extracted hidden states

The draft model learns to predict the verifier's next-token distribution from intermediate hidden states, enabling vLLM to speculative-decode at 1.3–2x throughput with zero quality loss.

## When to Use

- Training an EAGLE3/dflash/peagle/MTP speculator for a target model served in vLLM
- Single-GPU machine (DGX Spark, single H100, etc.) with enough VRAM to hold the verifier model + KV cache
- Target model is a HuggingFace local directory (not just a Hub ID)

**Don't use for:**
- Online training (vLLM + training on same GPU simultaneously) — needs 2+ GPUs
- Models not yet supported by vLLM's `extract_hidden_states` speculative method

## Prerequisites

- **Two venvs** (they have conflicting deps):
  - `vllm_venv` — for `launch_vllm.py` (vLLM 0.25.0+)
  - `speculators_venv` — for `prepare_data.py`, `data_generation_offline.py`, `train.py`
- Speculators repo cloned: `git clone https://github.com/vllm-project/speculators`
- Install speculators in editable mode in the speculators_venv: `pip install -e .`
- Target model downloaded locally (e.g. `/home/user/dev/a1-agents`)
- Training data available (ShareGPT, UltraChat, or custom JSONL)

## Phase 1: Data Preparation

```bash
cd /path/to/speculators
source /path/to/speculators_venv/bin/activate

python scripts/prepare_data.py \
  --model /path/to/target-model \
  --data sharegpt \
  --output /path/to/training_data \
  --max-samples 5000 \
  --seq-length 8192
```

**Output:** HuggingFace dataset on disk with columns:
- `input_ids` (List[int32]) — tokenized + chat-templated conversation
- `loss_mask` (List[bool]) — True for assistant tokens (trainable positions)
- `seq_len` (int64) — actual sequence length
- `messages` (List[dict]) — original conversation (for multimodal re-tokenization)
- `token_freq.pt` — token frequency statistics for draft vocab subsampling

**Key checks after prep:**
```bash
python -c "
from datasets import load_from_disk
ds = load_from_disk('/path/to/training_data')
print(f'Samples: {len(ds)}')
print(f'Features: {ds.features}')
item = ds[0]
print(f'input_ids type: {type(item[\"input_ids\"])}, len: {len(item[\"input_ids\"])}')
"
```

## Phase 2: Hidden States Extraction

### Step 2a: Launch vLLM as hidden-states producer

```bash
cd /path/to/speculators
source /path/to/vllm_venv/bin/activate

# For MoE models already loaded in GPU memory, MAX_JOBS=5 is safe.
# For first cold start (model not in memory), use MAX_JOBS=1.
export MAX_JOBS=5
export NVCC_THREADS=5

python scripts/launch_vllm.py \
  /path/to/target-model \
  --target-layer-ids 3 19 39 \
  -- --dtype bfloat16 \
     --gpu-memory-utilization 0.65 \
     --max-model-len 8192 \
     --max-num-seqs 4 \
     --kv-cache-dtype fp8 \
     --no-enable-prefix-caching \
     --enforce-eager \
     --port 8000
```

**What `launch_vllm.py` does:**
- Reads model config to determine `num_hidden_layers` (e.g. 40 for Qwen3.5 MoE)
- Appends the last layer to `--target-layer-ids` automatically (via `--include-last-layer`, default True). So `[3, 19, 39]` becomes `[3, 19, 39, 40]`
- Configures `speculative_config` with `method=extract_hidden_states`
- Configures `ExampleHiddenStatesConnector` as `kv_producer` — writes `.safetensors` to `/tmp/hidden_states/`
- Auto-appends `--no-enable-chunked-prefill` (required for hidden states extraction)

**Choosing target layer IDs:**
- Default (omit flag): `[2, num_hidden_layers // 2, num_hidden_layers - 3, num_hidden_layers]`
- For 40-layer models: `[3, 19, 39]` + auto-appended 40 = `[3, 19, 39, 40]`
- Rule of thumb: pick layers from early, middle, and late in the network
- **WARNING:** Whatever you pass here MUST also be passed to `train.py --target-layer-ids`

**vLLM args explained:**
| Arg | Why |
|-----|-----|
| `--max-model-len 8192` | **MANDATORY — never omit.** Must match `--seq-length` from `prepare_data.py`. Without it, vLLM uses model default (262K) → encoder cache OOM on multimodal models (Agents-A1, Qwen3.5-MoE). See pitfall #22. |
| `--gpu-memory-utilization 0.65` | Leave room for hidden states buffer + JIT compilation. MoE models need more headroom. |
| `--kv-cache-dtype fp8` | Halves KV cache memory. May cause minor accuracy drop in extracted hidden states — acceptable for draft training. |
| `--max-num-seqs 4` | Low concurrency — hidden states extraction is memory-heavy per request. |
| `--enforce-eager` | Disables torch.compile/CUDAGraph. Required: CUDAgraph capture is incompatible with hidden states extraction. |
| `--no-enable-prefix-caching` | Prefix caching interferes with per-request hidden state isolation. |
| `--no-enable-chunked-prefill` | Auto-added by launch_vllm.py. Some models warn about this. |

**Wait for server to be ready:**
```bash
until curl -sf http://localhost:8000/health > /dev/null 2>&1; do sleep 2; done
echo "vLLM ready"
```

Model loading takes ~7 minutes for a 65 GiB MoE model on EXT4 (no prefetch due to checkpoint > 90% RAM).

### Step 2b: Generate hidden states

```bash
cd /path/to/speculators
source /path/to/speculators_venv/bin/activate

python scripts/data_generation_offline.py \
  --preprocessed-data /path/to/training_data \
  --endpoint http://localhost:8000/v1 \
  --output /path/to/hidden_states \
  --max-samples 5000 \
  --concurrency 8 \
  --validate-outputs
```

**What it does:** Sends each sample's `input_ids` to vLLM via Completions API with `kv_transfer_params`. vLLM runs a forward pass, extracts hidden states from target layers, writes them to `/tmp/hidden_states/hs_<idx>.safetensors`. The script then moves them to `--output`.

**Timing (DGX Spark, Qwen3.5 MoE 65GB, 5000 samples):**
- ~38 minutes at concurrency=8
- ~2.2 it/s throughput
- Output: ~101 GiB of `.safetensors` files (4999 files, ~20MB each)

**After generation, stop vLLM** (Ctrl+C or `kill <pid>`) to free GPU memory for training.

**For long extractions (50k+ samples, 6+ hours):** use the wrapper script at `scripts/run_extraction.sh` instead of separate terminals. It starts vLLM, waits for health, runs extraction, stops vLLM, and writes a completion marker. Launch via `terminal(background=true, notify_on_complete=true)`.

## Phase 3: Training

```bash
cd /path/to/speculators
source /path/to/speculators_venv/bin/activate

python scripts/train.py \
  --verifier-name-or-path /path/to/target-model \
  --data-path /path/to/training_data \
  --hidden-states-path /path/to/hidden_states \
  --save-path /path/to/checkpoints \
  --speculator-type eagle3 \
  --draft-arch qwen3 \
  --draft-attn-impl sdpa \
  --num-layers 1 \
  --draft-vocab-size 8192 \
  --token-freq-path /path/to/training_data/token_freq.pt \
  --target-layer-ids 3 19 39 \
  --epochs 10 \
  --lr 1e-4 \
  --total-seq-len 8192 \
  --on-missing skip \
  --ttt-steps 3 \
  --norm-output \
  --optimizer muon \
  --muon-lr 1e-3 \
  --muon-momentum 0.95 \
  --hidden-states-dtype bfloat16 \
  --logger tensorboard \
  --log-dir /path/to/logs \
  --run-name "my-model-eagle3-v1"
```

**Key training args:**
| Arg | Description |
|-----|-------------|
| `--speculator-type eagle3` | EAGLE-3 algorithm. Alternatives: dflash, peagle, mtp |
| `--draft-arch qwen3` | Draft architecture. Use `qwen3` for Qwen-family verifiers, `llama` for Llama-family |
| `--num-layers 1` | Number of draft transformer layers. 1 is a good starting point. |
| `--draft-vocab-size 8192` | Subsampled vocab size. Reduces draft head size. Must have `token_freq.pt`. |
| `--target-layer-ids 3 19 39` | MUST match what was passed to `launch_vllm.py` (without the auto-appended last layer) |
| `--on-missing skip` | Skip samples without hidden states. Use `generate` for online mode (needs vLLM running). |
| `--draft-attn-impl sdpa` | MANDATORY on GB10/DGX Spark. Default `simple_flex_attention` crashes with Triton OOM. Use `sdpa` or `eager`. |
| `--ttt-steps 3` | Test-Time Training steps — number of speculative tokens to predict |
| `--optimizer muon` | Muon optimizer for 2D weights + AdamW for embeddings/norms. Often converges faster. |
| `--fc-norm` | Apply normalization before FC layer. WARNING: conflicts with `--norm-before-fc` (enabled by default). Use one or the other, not both. |
| `--norm-output` | Normalize draft output hidden states |
| `--total-seq-len 8192` | Must match `--seq-length` from prepare_data.py |
| `--dry-run` | Build draft, init weights, save checkpoint, exit. Validate config before full run. |

**Always do a dry run first:**
```bash
python scripts/train.py \
  --verifier-name-or-path /path/to/target-model \
  --data-path /path/to/training_data \
  --hidden-states-path /path/to/hidden_states \
  --save-path /tmp/dry-run \
  --speculator-type eagle3 \
  --draft-arch qwen3 \
  --draft-attn-impl sdpa \
  --num-layers 1 \
  --draft-vocab-size 8192 \
  --token-freq-path /path/to/training_data/token_freq.pt \
  --target-layer-ids 3 19 39 \
  --dry-run
```

## Model-Specific Notes: Qwen3.5 MoE

- **Architecture:** `Qwen3_5MoeForConditionalGeneration` (hybrid linear attention + MoE)
- **Config:** `model_type=qwen3_5_moe_text`, 40 hidden layers, hidden_size=2048, vocab_size=248320
- **AutoProcessor:** Qwen3.5 uses `Qwen3VLProcessor` (not a plain tokenizer), which creates a `messages` column even for text-only data
- **vLLM resolution:** `launch_vllm.py` auto-detects architecture from `config.json`
- **Draft arch:** Use `--draft-arch qwen3` (not `llama`)
- **Memory:** 65.5 GiB model weights + ~10 GiB KV cache (fp8) at 0.65 utilization. Fits on 128GB GPU (DGX Spark).
- **`--no-enable-chunked-prefill` warning:** vLLM warns this model doesn't officially support disabling chunked prefill. It works in practice for hidden states extraction but may cause issues if used for regular serving.

## Benchmark Results (Qwen3.5 MoE, DGX Spark GB10)

Two benchmark runs with 3 prompts × 256 tokens, temperature=0, warm (after JIT/CUDAgraph compilation):

### With `--enforce-eager` (extraction mode, not recommended for serving)

| Metric | Baseline | EAGLE3 Speculator | Speedup |
|--------|----------|-------------------|---------|
| Throughput | 16.2 tok/s | 22.2 tok/s | **1.37x** |
| Inter-token latency | 61.6ms | ~45ms | 27% reduction |

### With CUDAgraph (no `--enforce-eager`, recommended for serving)

| Metric | Baseline | EAGLE3 Speculator | Speedup |
|--------|----------|-------------------|---------|
| Throughput | 20.0 tok/s | 26.7 tok/s | **1.34x** |
| Inter-token latency | ~50ms | ~37ms | 26% reduction |

### Key insight: CUDAgraph helps both sides equally

CUDAgraph speeds up baseline (+23%) and speculator (+20%) proportionally, so the **relative speedup stays ~1.34x** regardless of mode. The bottleneck is GPU compute (MoE forward pass on 65GB model), not Python/kernel-launch overhead. To get more speedup, improve the draft model (more training data → higher acceptance rate), not the serving config.

### Acceptance rates (same in both modes, from vLLM `SpecDecoding metrics`)

| Position | Acceptance | Notes |
|----------|------------|-------|
| 0 | 63.6% | ~64% of first draft tokens accepted |
| 1 | 28.0% | Conditional on pos 0 accepted |
| 2 | 10.3% | Conditional on pos 0+1 accepted |
| Mean acceptance length | 2.02 tokens | Avg tokens accepted per draft |

### Quality

Outputs are NOT bit-identical at temperature=0, but semantically equivalent. Minor differences (e.g. "Drafting" vs "Draft", "total order value" vs "the total order value"). This is expected: speculator and non-speculator use different kernel paths, causing small floating-point differences in MoE routing that occasionally select different tokens.

### How to benchmark

Use the benchmark script at `scripts/benchmark.py` (see support files). Quick manual method:

1. Launch baseline vLLM (no `--speculative_config`), send a warmup request, then 3 timed requests
2. Kill baseline, launch speculator vLLM (with `--speculative_config`), send warmup + 3 timed requests
3. Compare throughput via curl timing and `/metrics` endpoint
4. Acceptance rates appear in vLLM server logs as `SpecDecoding metrics: Mean acceptance length: ...`
5. Also check `vllm:speculative_token_draft_total` and `vllm:speculative_token_accepted_total` in `/metrics`

### Deployment command (serving — NO `--enforce-eager`)

```bash
python -m vllm.entrypoints.cli.main serve /path/to/target-model \
  --speculative_config '{"method": "eagle3", "model": "/path/to/checkpoints/checkpoint_best", "num_speculative_tokens": 3}' \
  --dtype bfloat16 \
  --gpu-memory-utilization 0.65 \
  --max-model-len 8192 \
  --max-num-seqs 4 \
  --served-model-name agents-a1-eagle3 \
  --port 8000
```

**Do NOT use `--enforce-eager` for serving.** It is only needed for hidden states extraction (Phase 2). For production serving, CUDAgraph should be enabled (default) for ~23% higher throughput on both baseline and speculator.

**`--served-model-name`** sets the model name that vLLM reports to clients. Without it, vLLM uses the filesystem path (e.g. `/home/user/dev/a1-agents`). Set it to match the LiteLLM model_name for clean routing.

## Phase 4: Upload to HuggingFace + Integration

### Upload speculator to HuggingFace

```bash
# Prepare clean upload dir (only model files, no optimizer/scheduler state)
mkdir -p /tmp/eagle3_upload
cp /path/to/checkpoints/checkpoint_best/config.json /tmp/eagle3_upload/
cp /path/to/checkpoints/checkpoint_best/config.py /tmp/eagle3_upload/
cp /path/to/checkpoints/checkpoint_best/model.safetensors /tmp/eagle3_upload/

# Upload
python3 -c "
from huggingface_hub import HfApi, create_repo
token = open('~/.cache/huggingface/token'.replace('~', __import__('os').path.expanduser('~'))).read().strip()
api = HfApi(token=token)
repo_id = 'YOUR_USERNAME/model-name-eagle3-speculator'
create_repo(repo_id, repo_type='model', token=token, exist_ok=True)
api.upload_folder(folder_path='/tmp/eagle3_upload', repo_id=repo_id, repo_type='model', token=token)
print(f'Upload complete: https://huggingface.co/{repo_id}')
"
```

After upload, vLLM can use the HF model name directly: `"model": "YOUR_USERNAME/model-name-eagle3-speculator"` in `--speculative_config`.

### LiteLLM integration

Add to LiteLLM `config.yaml` (alongside other vLLM models):

```yaml
  - model_name: "agents-a1-eagle3"
    litellm_params:
      model: "openai/agents-a1-eagle3"
      api_base: "os.environ/VLLM_API_BASE"
      api_key: "os.environ/VLLM_API_KEY"
      request_timeout: 600
      max_retries: 0
    model_info:
      mode: chat
```

Then restart LiteLLM: `docker compose -f compose.phoenix.yml restart litellm`

### Hermes integration

```bash
# Add model to Hermes local provider
hermes config set providers.local.models '["existing-model","agents-a1-eagle3"]'
```

Then use: `hermes chat --model agents-a1-eagle3 --provider local`

See `references/deployment.md` for detailed integration steps.

## Common Pitfalls

1. **`AttributeError: 'list' object has no attribute 'tolist'`** in `build_client_item`. HuggingFace datasets store `input_ids` as Python `list` (not `torch.Tensor`) when the feature type is `List(Value('int32'))`. The fix: `build_client_item` must check `hasattr(input_ids, "tolist")` before calling it. This affects models that use `AutoProcessor` (Qwen3VLProcessor) instead of a plain tokenizer (Llama). Fix is in `src/speculators/train/data.py:149`.

2. **`pgrep -f "vllm.entrypoints"` kills unrelated processes.** Never use `pgrep -f "vllm.entrypoints"` in cleanup scripts — it matches ANY process with that string, including a vLLM server you launched manually in a different terminal. Use the specific PID from `$!` instead.

3. **8192 token limit rejection.** Samples with exactly `seq_length` tokens get rejected by vLLM because `max_model_len=8192` but the request needs `input_tokens + 1 output_token = 8193`. This skips ~0.02% of samples (1 in 5000). Either increase `--max-model-len` to 8193+ or accept the skip. The `--on-missing skip` flag in training handles this gracefully.

4. **Two venvs required.** `vllm_venv` and `speculators_venv` have conflicting dependencies (different torch versions, flashinfer, etc.). Never `pip install speculators` into the vLLM venv or vice versa.

5. **`--target-layer-ids` must match between launch_vllm.py and train.py.** `launch_vllm.py` auto-appends the last layer (`--include-last-layer` default True). `train.py` does NOT auto-append. Pass the SAME explicit IDs to both (e.g. `3 19 39`). The last layer is handled internally by the training code reading the verifier config.

6. **MAX_JOBS too high causes GPU OOM during JIT.** For MoE models already loaded in GPU memory, `MAX_JOBS=5` is safe. `MAX_JOBS=10` risks OOM during FlashInfer/CUTLASS kernel JIT compilation. For first cold start (model not yet in memory), use `MAX_JOBS=1`.

7. **`--enforce-eager` is mandatory for hidden states extraction (Phase 2).** CUDAGraph capture is incompatible with the `extract_hidden_states` speculative method. Without `--enforce-eager`, vLLM may crash during the first inference request. However, `--enforce-eager` is NOT needed for serving (Phase 4) — see pitfall #15.

8. **Disk space for hidden states.** 5000 samples × ~20MB each = ~100GB. Ensure the output directory has enough space. The `/tmp/hidden_states/` intermediate path is on tmpfs (RAM-backed) — the `ExampleHiddenStatesConnector` writes there first, then `data_generation_offline.py` moves files to `--output`.

9. **`--no-enable-chunked-prefill` is auto-added.** `launch_vllm.py` appends this automatically (line 107-109). Don't pass it manually to avoid duplication. Some models (Qwen3.5 MoE) warn about this but it works.

10. **NVRM GPU OOM during warmup.** Kernel log may show `nvCheckOkFailedNoLog: Out of memory [NV_ERR_NO_MEMORY]` during FlashInfer autotune warmup. This is a non-fatal warning — vLLM handles it internally and proceeds. Only worry if the server crashes after this message.

11. **Triton flex_attention backward OOM on GB10 (sm121).** Training crashes with `OutOfMemoryError: out of resource: triton_tem_fused_flex_attention_backward Required: 114688 Hardware limit: 101376`. The default draft attention implementation (`simple_flex_attention`) generates Triton kernels that exceed the GB10's shared memory limit. Fix: add `--draft-attn-impl sdpa` to use PyTorch native SDPA instead. This affects all DGX Spark / GB10 GPUs.

12. **tensorboard not in apt.** `python3-tensorboard` package doesn't exist in Ubuntu apt repos. Install via pip. If `pip` is missing from the venv (created without `--upgrade-deps`), bootstrap it first: `python -m ensurepip --upgrade && python -m pip install tensorboard`.

13. **`--fc-norm` and `--norm-before-fc` are mutually exclusive.** `--norm-before-fc` is enabled by default. Adding `--fc-norm` causes a Pydantic ValidationError: `norm_before_fc and fc_norm are mutually exclusive`. Just use `--norm-output` without `--fc-norm` — the default normalization is sufficient.

14. **speculators_venv may not have pip.** If the venv was created with `python -m venv` without `--upgrade-deps`, `pip` won't be present. Fix: `python -m ensurepip --upgrade` inside the venv, then `python -m pip install <package>`.

15. **`--enforce-eager` is for extraction only, NOT for serving.** Phase 2 (hidden states extraction) requires `--enforce-eager` because CUDAGraph capture is incompatible with the `extract_hidden_states` speculative method. But Phase 4 (deployment/serving with a trained EAGLE3 model) should NOT use `--enforce-eager` — CUDAgraph gives ~23% throughput improvement on both baseline and speculator. The relative speedup stays ~1.34x either way, but absolute throughput is higher without eager mode.

16. **Background processes from previous AI sessions can kill vLLM.** If a previous session launched a background pipeline containing `kill $(pgrep -f "vllm.entrypoints")`, that script will match and SIGTERM ANY vLLM process — including one you started manually in a different terminal. Before launching vLLM, check for lingering background processes: `pgrep -f "vllm.entrypoints" | head`. If found, kill the parent script, not the vLLM process itself.

17. **Never blame the user for process death without forensic evidence.** When a process dies unexpectedly, do NOT assume the user killed it. Run forensic analysis FIRST: `journalctl --since "<time>" --until "<time>" -k` for kernel OOM/Xid errors, `session_search` for background scripts from previous sessions that may contain `kill` commands, `ps aux` for process tree analysis. State findings as evidence ("kernel log shows SIGTERM at 16:30:14, matching a background script from yesterday's session") not accusations ("you killed it"). The user may be running long-lived processes across multiple terminals and sessions.

18. **vLLM EngineDeadError during long hidden states extraction.** When running `data_generation_offline.py` against vLLM for extended periods (50k+ samples, 6+ hours), the vLLM EngineCore can crash with `EngineDeadError`. The API server returns 500 errors, and the extraction script aborts. Root cause is likely GPU memory pressure from accumulated hidden states buffers. Mitigation: (a) use `--concurrency 4` instead of 8 for 50k+ runs, (b) monitor vLLM logs for `EngineDeadError`, (c) the extraction script is resumable — it skips samples that already have `.safetensors` files in the output dir, so just restart vLLM + extraction.

19. **Long-running extraction (6+ hours) needs a wrapper script, not separate background processes.** When using Hermes `terminal(background=true)` for vLLM and a separate terminal for extraction, the vLLM process can be killed when the session continues or the background process times out. Instead, use a single wrapper script (`scripts/run_extraction.sh`) that: (a) starts vLLM, (b) waits for health, (c) runs extraction, (d) kills vLLM, (e) writes a completion marker. Launch it via `terminal(background=true, notify_on_complete=true)` so you get notified when the entire pipeline finishes.

20. **`--served-model-name` is required for LiteLLM routing.** When serving with vLLM for production use through LiteLLM, always set `--served-model-name` to match the LiteLLM `model_name`. Without it, vLLM reports the filesystem path (e.g. `/home/user/dev/a1-agents`) as the model ID, and LiteLLM will not route requests correctly.

21. **ShareGPT dataset has 120,675 samples total.** The `Aeala/ShareGPT_Vicuna_unfiltered` dataset (used by the `sharegpt` preset) contains 120k conversations. For 50k training samples, `prepare_data.py` processes all 120k and subsamples to `--max-samples`. For 100k+, consider `ultrachat` (207k samples) or `magpie` for larger runs.

22. **CRITICAL — `--max-model-len` MUST be set in the vLLM args for hidden state extraction, or vLLM uses the model's default (262K) and OOMs (verified Jul 16 2026)**: The Phase 2a example above includes `--max-model-len 8192`, but custom extraction scripts (e.g., DSpark `step1_hidden_states.sh`) often forget it. Without it, vLLM defaults to the model's `max_position_embeddings` (262144 for Qwen3.5/3.6). This triggers catastrophic memory consumption during initialization: (a) vLLM allocates KV cache for 262K context (even with `--kv-cache-dtype fp8`, 4 sequences × 262K × 4KB/token = ~4 GB — manageable), but (b) **multimodal models** (Agents-A1, Qwen3.5-MoE with vision encoder) initialize an encoder cache with budget=262144 tokens and profile 16 image items of max feature size — this alone consumes 10-15 GB. Combined with the BF16 model (65 GB) + vLLM overhead, RAM hits 119/121 GB and vLLM never passes the health check. **Symptoms**: the script loops on `curl http://localhost:PORT/health` forever, RAM used climbs to 119 GB, vLLM log shows `Using max model len 262144` + `Encoder cache will be initialized with a budget of 262144 tokens`. **FIX**: Always pass `--max-model-len 8192` (or whatever your `--seq-length` from `prepare_data.py` was) in the `--` args to `launch_vllm.py`. Hidden state extraction only processes training samples, which are ≤8192 tokens — the full context window is never needed. Also set `--gpu-memory-utilization 0.65` (not higher) for BF16 models on GB10.

## P-EAGLE Training (Parallel Multi-Token Prediction)

P-EAGLE extends EAGLE-3 with parallel multi-token prediction using Conditional-On-Distribution (COD) sampling. Instead of generating draft tokens sequentially (autoregressive), P-EAGLE predicts multiple tokens in a single forward pass, reducing drafting latency and enabling deeper speculation.

### When to use P-EAGLE vs EAGLE3

| | EAGLE3 | P-EAGLE |
|---|---|---|
| Prediction | Sequential (autoregressive draft) | Parallel (single forward pass) |
| Max depths | Limited by compounding error | Can go deeper (8+ positions) |
| Draft layers | 1-2 | 4+ (more capacity needed) |
| Training data | 5k minimum | 50k+ recommended |
| Memory | Lower | Higher (COD sampling helps) |
| Best for | Quick sanity check, small models | Production, maximizing acceptance length |

### P-EAGLE training command

```bash
cd /path/to/speculators
source /path/to/speculators_venv/bin/activate

python scripts/train.py \
  --verifier-name-or-path /path/to/target-model \
  --data-path /path/to/training_data_50k \
  --hidden-states-path /path/to/hidden_states_50k \
  --save-path /path/to/peagle-checkpoints \
  --speculator-type peagle \
  --draft-arch qwen3 \
  --draft-attn-impl sdpa \
  --num-layers 4 \
  --num-depths 8 \
  --down-sample-ratio 0.7 \
  --down-sample-ratio-min 0.2 \
  --draft-vocab-size 8192 \
  --token-freq-path /path/to/training_data_50k/token_freq.pt \
  --target-layer-ids 3 19 39 \
  --epochs 5 \
  --lr 6e-4 \
  --total-seq-len 8192 \
  --on-missing skip \
  --no-norm-before-residual \
  --scheduler-type cosine \
  --hidden-states-dtype bfloat16 \
  --logger tensorboard \
  --log-dir /path/to/logs_peagle \
  --run-name "my-model-peagle-8depth-v1"
```

### P-EAGLE-specific args

| Arg | Description |
|-----|-------------|
| `--speculator-type peagle` | P-EAGLE algorithm (parallel prediction) |
| `--num-layers 4` | More layers than EAGLE3 (4 vs 1) — parallel prediction needs more capacity |
| `--num-depths 8` | Number of parallel prediction depths (positions). 8 = predict 8 tokens in one pass. |
| `--down-sample-ratio 0.7` | COD sampling: geometric decay ratio for retained tokens per depth |
| `--down-sample-ratio-min 0.2` | Minimum retention ratio (floor for COD sampling) |
| `--lr 6e-4` | Higher LR than EAGLE3 (6e-4 vs 1e-4) — P-EAGLE benefits from faster learning |
| `--no-norm-before-residual` | P-EAGLE-specific: disable norm before residual connection |
| `--scheduler-type cosine` | Cosine LR schedule — better for larger datasets |

### P-EAGLE deployment

```bash
python -m vllm.entrypoints.cli.main serve /path/to/target-model \
  --speculative_config '{"method": "peagle", "model": "/path/to/peagle-checkpoints/checkpoint_best", "num_speculative_tokens": 8}' \
  --dtype bfloat16 \
  --gpu-memory-utilization 0.65 \
  --max-model-len 8192 \
  --max-num-seqs 4 \
  --served-model-name agents-a1-peagle \
  --port 8000
```

See `references/peagle-training.md` for detailed P-EAGLE vs EAGLE3 comparison, scaling estimates, disk space requirements, COD sampling explanation, and RedHat reference results.

### Expected P-EAGLE results (projection)

With 50k samples and 8 depths, expected acceptance rates (based on RedHat Qwen3-8B P-EAGLE reference):

| Position | EAGLE3 (5k, ttt=3) | P-EAGLE (50k, 8 depths) |
|----------|---------------------|-------------------------|
| 0 | 63.6% | ~65% |
| 1 | 28.0% | ~45% |
| 2 | 10.3% | ~28% |
| 3 | — | ~15% |
| 4 | — | ~8% |
| 5-7 | — | ~3-5% |
| **Mean length** | **2.02** | **~3.5-4.0** |
| **Expected speedup** | **1.34x** | **1.8-2.0x** |

## DFlash / DSpark Training (Block Diffusion Speculators)

DFlash and DSpark are **block diffusion** draft models — they predict an entire block of N tokens in a **single parallel forward pass** (non-causal/bidirectional attention), vs EAGLE3's sequential autoregressive drafting. This gives 3-6x speedup (vs EAGLE3's ~1.3x).

**DSpark** (DeepSeek, July 2026) extends DFlash with a Markov head (bigram bias) and Confidence head (per-position acceptance probability). A 2-layer DSpark already beats a 5-layer DFlash.

### Key differences from EAGLE3

| | EAGLE3 | DFlash/DSpark |
|---|---|---|
| `--speculator-type` | `eagle3` | `dflash` or `dspark` |
| Prediction | Sequential (autoregressive) | Parallel (single forward → block of N tokens) |
| `--block-size` | n/a | 8 or 16 (paper default: 16) |
| `--dflash-decay-gamma` | n/a | 7 (bs16), 5 (bs10), 4 (bs8) — position-dependent loss decay |
| `--markov-rank` | n/a | 256 (DSpark only, 0 disables) |
| `--per-position-loss-weight` | n/a | `fixed-exp-decay` (with ce+tv loss) or `dpace` (requires pure ce loss) |
| `--full-attention-indices` | n/a | OMIT entirely — dspark/dflash default to all sliding-window attention |
| Draft layers | 1-2 | 5 (paper default for 35B targets) |
| Serving | vLLM `--speculative_config` | SGLang `--speculative-algorithm DFLASH` |
| Expected speedup | ~1.3x | 3-6x |

### DSpark training command

```bash
torchrun --standalone --nproc_per_node 1 \
    scripts/train.py \
    --verifier-name-or-path "$MODEL" \
    --data-path "$TRAINING_DATA" \
    --hidden-states-path "$HIDDEN_STATES" \
    --save-path "$SAVE/bs16" \
    --run-name "dspark-bs16" \
    --speculator-type dspark \
    --draft-arch qwen3 \
    --block-size 16 \
    --num-layers 5 \
    --target-layer-ids 3 7 11 15 19 23 27 31 35 39 \
    --max-anchors 3072 \
    --draft-vocab-size 32000 \
    --token-freq-path "$TRAINING_DATA/token_freq.pt" \
    --mask-token-id 248077 \
    --markov-rank 256 \
    --markov-head-type vanilla \
    --loss-fn '{"ce": 0.1, "tv": 0.9}' \
    --dflash-decay-gamma 7.0 \
    --per-position-loss-weight fixed-exp-decay \
    --epochs 6 \
    --lr 6e-4 \
    --total-seq-len 8192 \
    --optimizer muon \
    --draft-attn-impl simple_flex_attention \
    --noise-std 0.05 \
    --save-best \
    --checkpoint-freq 1.0 \
    --no-resume-from-checkpoint \
    --on-missing skip \
    --logger tensorboard \
    --log-dir "$SAVE/bs16/logs"
```

### DSpark-specific pitfalls (CRITICAL — all verified against speculators source)

23. **`--full-attention-indices` is 0-indexed and MUST be < `--num-layers`.** Passing `"5"` for 5 layers (intending "the 5th layer") triggers `parser.error()`. Default for dspark/dflash is all sliding-window — OMIT the flag entirely. `SLIDING_WINDOW_SPECULATOR_TYPES = ("dflash", "dspark")` in train.py.

24. **`--per-position-loss-weight=dpace` REQUIRES `--loss-fn ce` (not ce+tv).** `dpace` uses `exp(-elementwise_loss)` as a probability — only valid with pure CE. Mixed loss `{ce, tv}` + `dpace` = `parser.error()`.

25. **Progressive block-size training (BS=16→32→64) is BROKEN in speculators.** `--from-pretrained` conflicts with decoder-shaping flags (`--num-layers`, `--draft-arch`, etc.) → `parser.error()`. Checkpointer saves to `<save>/<epoch>/` + `checkpoint_best` symlink, NOT `<save>/checkpoint_bs16`. Same `--save-path` across stages + default `--resume-from-checkpoint` silently resumes optimizer state. **Use single BS=16 training instead** (paper: "train at 16, infer at 8-16").

26. **`--muon-lr` auto-set to `10 * --lr` if omitted.** Explicitly passing `--muon-lr 3e-3` with `--lr 3e-4` is redundant but correct. Paper default LR=6e-4 for DFlash.

27. **Pretrained DFlash checkpoint `target_layer_ids` may point to linear_attention layers.** z-lab's Qwen3.6-35B-A3B-DFlash ships with `[1,6,11,16,22,27,32,37]` — 6 of 8 are linear_attention in Qwen3.5's hybrid layout. Always verify against the target model's `layer_types` / `full_attention_interval`. Snap each ID to the nearest full_attention layer.

28. **DSpark draft has NO embeddings and NO lm_head.** It reuses the target model's. The checkpoint contains only: `layers.*`, `fc.weight` (target feature projection), `hidden_norm.weight`, `norm.weight`, markov/confidence head weights. This is by design.

29. **SGLang DFLASH serving (not vLLM).** DFlash/DSpark speculators serve via SGLang, not vLLM serving. See DSpark serving section below.

### DSpark serving via SGLang

```bash
python -m sglang.launch_server \
    --model-path "$MODEL" \
    --trust-remote-code \
    --dtype bfloat16 \
    --speculative-algorithm DFLASH \
    --speculative-draft-model-path "$SAVE/bs16/checkpoint_best" \
    --speculative-num-draft-tokens 15 \
    --tp-size 1 \
    --attention-backend triton \
    --mem-fraction-static 0.62 \
    --context-length 262144 \
    --chunked-prefill-size 8192 \
    --max-running-requests 4 \
    --mamba-scheduler-strategy extra_buffer \
    --host 0.0.0.0 --port 8102
```

**Serving flags validated against SGLang source (dflash_worker_v2.py):**
- `--attention-backend triton`: REQUIRED on GB10 (sm_121) — FlashInfer has no sm_121 kernels, `trtllm_mha` explicitly rejects SM120/121
- `--mamba-scheduler-strategy extra_buffer`: MANDATORY for hybrid mamba (Qwen3.5) + DFLASH v2 (overlap scheduling). `no_buffer` errors, `extra_buffer_lazy` unsupported with spec
- Qwen3.5 first-class DFLASH target: `qwen3_5.py:1174` implements `set_dflash_layers_to_capture`
- `SGLANG_ENABLE_SPEC_V2=1` is default → DFlashWorkerV2 (overlap) is used
- Multimodal NOT blocked: VL models implement `set_dflash_layers_to_capture` (qwen3_vl.py:1305). DFlash operates on decode only; vision encoder runs in prefill unaffected
- `--speculative-num-draft-tokens` must equal `block_size - 1` from training

### DFlash + Multimodal (VLM) models

DFlash does NOT break vision/multimodal capabilities:
- Vision encoder processes images during **prefill** (DFlash not involved)
- DFlash operates during **decode** (text generation after image understanding)
- Hidden states from target layers already contain image context — draft model doesn't need to see pixels
- `--limit-mm-per-prompt` during training extraction: set to `{"image": 0}` (text-only dataset) — but OMIT it during serving (let SGLang handle images normally)

See `references/dspark-training.md` for the full deep research: paper comparison table, progressive training bug analysis, SGLang DFLASH worker internals, and real-world checkpoint examples from HuggingFace.

## Choosing `num_speculative_tokens` at Serving Time

**You cannot increase `num_speculative_tokens` beyond what the draft model was trained for.** The draft model trained with `--ttt-steps 3` (EAGLE3) or `--num-depths 8` (P-EAGLE) can only predict that many positions. Setting `num_speculative_tokens: 8` with a model trained for 3 positions will:

1. Compute 8 draft positions (GPU time wasted)
2. Positions 3-7 have ~0% acceptance (never trained)
3. Net throughput **decreases** because draft computation overhead grows without benefit

**Rule:** `num_speculative_tokens` at serving time ≤ `--ttt-steps` (EAGLE3) or `--num-depths` (P-EAGLE) at training time.

**To increase speculative depth, you must retrain** with higher `--ttt-steps` or `--num-depths`, and ideally with more training data (50k+) to maintain acceptance rates at deeper positions.

## Expected Results (Qwen3.5 MoE, 5000 samples, 3 TTT steps)

Training metrics from a real run (10 epochs, Muon optimizer, SDPA attention):

| Position | Accuracy | Loss | Notes |
|----------|----------|------|-------|
| 0 | 71.1% | 0.63 | ~71% of first speculative tokens accepted |
| 1 | 42.1% | 1.42 | Conditional on position 0 accepted |
| 2 | 25.0% | 2.04 | Conditional on positions 0+1 accepted |

- Checkpoint size: ~5.2 GB total (includes optimizer state, scheduler state, best + epoch checkpoints)
- Best checkpoint at `checkpoint_best/` — contains `config.json`, `model.safetensors`, `val_metrics.json`
- `train_command.txt` in checkpoint dir records the exact command + git SHA + library versions

**Interpreting metrics:** Position 0 accuracy is the most important — it directly maps to speculative decoding acceptance rate. 71% means ~71% of the time, the first draft token is correct and doesn't need verification. Expected throughput speedup: ~1.3-1.5x.

## Verification Checklist

- [ ] `prepare_data.py` completed — dataset has `input_ids`, `loss_mask`, `seq_len`, `messages`, `token_freq.pt`
- [ ] `build_client_item` works — tested with `python -c "from speculators.train.data import build_client_item; ..."`
- [ ] vLLM server started — `curl http://localhost:8000/health` returns 200
- [ ] vLLM log shows `ExampleHiddenStatesConnector` initialized with correct `shared_storage_path`
- [ ] vLLM log shows `Using auxiliary layers from speculative config: (3, 19, 39, 40)`
- [ ] `data_generation_offline.py` completed — hidden_states dir has N `.safetensors` files
- [ ] `--validate-outputs` passed — token IDs and seq_len match between dataset and hidden states
- [ ] vLLM stopped — GPU memory freed (`nvidia-smi` shows <1GB used)
- [ ] `train.py --dry-run` passed — checkpoint written to save_path
- [ ] Training started — loss decreasing in tensorboard logs

## Quick Reference: Full Pipeline (Copy-Paste)

```bash
#!/bin/bash
set -euo pipefail

MODEL=/path/to/target-model
SPECULATORS=/path/to/speculators
TRAINING_DATA=/path/to/training_data
HIDDEN_STATES=/path/to/hidden_states
CHECKPOINTS=/path/to/checkpoints
VLLM_VENV=/path/to/vllm_venv
SPEC_VENV=/path/to/speculators_venv
MAX_SAMPLES=5000
SEQ_LEN=8192
TARGET_LAYERS="3 19 39"
VLLM_PORT=8000

# Phase 1: Data prep
cd "$SPECULATORS" && source "$SPEC_VENV/bin/activate"
python scripts/prepare_data.py \
  --model "$MODEL" --data sharegpt \
  --output "$TRAINING_DATA" \
  --max-samples $MAX_SAMPLES --seq-length $SEQ_LEN

# Phase 2a: Launch vLLM (foreground, separate terminal)
cd "$SPECULATORS" && source "$VLLM_VENV/bin/activate"
export MAX_JOBS=5 NVCC_THREADS=5
python scripts/launch_vllm.py "$MODEL" \
  --target-layer-ids $TARGET_LAYERS \
  -- --dtype bfloat16 --gpu-memory-utilization 0.65 \
     --max-model-len $SEQ_LEN --max-num-seqs 4 \
     --kv-cache-dtype fp8 --no-enable-prefix-caching \
     --enforce-eager --port $VLLM_PORT

# Phase 2b: Generate hidden states (separate terminal, while vLLM runs)
cd "$SPECULATORS" && source "$SPEC_VENV/bin/activate"
python scripts/data_generation_offline.py \
  --preprocessed-data "$TRAINING_DATA" \
  --endpoint "http://localhost:$VLLM_PORT/v1" \
  --output "$HIDDEN_STATES" \
  --max-samples $MAX_SAMPLES --concurrency 8 --validate-outputs

# Stop vLLM (Ctrl+C in its terminal)

# Phase 3: Train
cd "$SPECULATORS" && source "$SPEC_VENV/bin/activate"
# Ensure pip + tensorboard exist (venv may lack pip)
python -m ensurepip --upgrade 2>/dev/null || true
python -m pip install tensorboard -q 2>/dev/null || true

python scripts/train.py \
  --verifier-name-or-path "$MODEL" \
  --data-path "$TRAINING_DATA" \
  --hidden-states-path "$HIDDEN_STATES" \
  --save-path "$CHECKPOINTS" \
  --speculator-type eagle3 --draft-arch qwen3 \
  --draft-attn-impl sdpa \
  --num-layers 1 --draft-vocab-size 8192 \
  --token-freq-path "$TRAINING_DATA/token_freq.pt" \
  --target-layer-ids $TARGET_LAYERS \
  --epochs 10 --lr 1e-4 --total-seq-len $SEQ_LEN \
  --on-missing skip --ttt-steps 3 \
  --norm-output \
  --optimizer muon --muon-lr 1e-3 --muon-momentum 0.95 \
  --hidden-states-dtype bfloat16 \
  --logger tensorboard --log-dir /path/to/logs --run-name "eagle3-v1"
```
