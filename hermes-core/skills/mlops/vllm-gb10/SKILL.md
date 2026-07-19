---
name: vllm-gb10
description: Run vLLM on NVIDIA GB10 (DGX Spark) — unified memory tuning, OOM prevention, EAGLE3 hidden state extraction
version: 1.0.0
---

# vLLM on GB10 DGX Spark

## Hardware: GB10 Unified Memory

GB10 (DGX Spark) has **128 GB LPDDR5x unified memory** — CPU and GPU share the SAME physical RAM.
- CUDA `total_memory` = ~121.69 GiB (= system RAM, NOT 128 GB)
- CUDA allocations ARE visible to `psutil.virtual_memory()` — there is no separate GPU memory
- `nvidia-smi` shows `Not Supported` for memory on GB10 — use `torch.cuda.mem_get_info()` or `free -h`
- Swap is useless here (same physical RAM), but kernel will use it → system hangs before OOM kill

## CRITICAL: CUDA JIT Compiler OOM (cicc processes)

**Root cause of most OOM hangs on GB10**: vLLM/PyTorch JIT-compiles CUDA kernels at startup, spawning up to **19 parallel `cicc` + `cudafe++` processes**. Each uses 0.6–4.1 GB RSS. Total: **up to 43 GB** on top of model weights.

These processes are NOT visible in `nvidia-smi` (no GPU memory tracking on GB10) but ARE visible in `ps`/kernel OOM dumps. Model weights (e.g. 66.5 GB BF16) are allocated via CUDA driver and also invisible to RSS.

**Breakdown at OOM**:
```
Model weights (CUDA driver alloc, invisible to RSS):  66.5 GB
cicc + cudafe++ compiler processes (RSS):             43.2 GB  ← THE KILLER
Other processes (OS, Hermes, Docker, etc):             8.0 GB
─────────────────────────────────────────────────────────────────
Total:                                               117.7 GB  (system has 127.4 GB → OOM)
```

**FIX — always set before launching vLLM on GB10**:
```bash
export MAX_JOBS=1
export NVCC_THREADS=1
```
This forces sequential compilation: 1 `cicc` (2–4 GB) instead of 19 (43 GB). Startup is slower but system survives.

**MAX_JOBS=10 is safe for MANUAL launches (user present)**: With a 66 GB model in memory, ~40 GB remains free. 10 parallel cicc processes × 3 GB = 30 GB, leaving 10 GB headroom. 5-10x faster compilation than MAX_JOBS=1. User can monitor and kill if OOM.

**Two modes:**
- **Automated/cron (no human watching):** `MAX_JOBS=1 NVCC_THREADS=1` — safe, slow
- **Manual launch (user present):** `MAX_JOBS=10 NVCC_THREADS=10` — fast, 30 GB peak, fits in 40 GB free

**Manual pre-compilation workaround (ninja build)**:
If vLLM keeps crashing during compilation, pre-compile FlashInfer cache manually outside vLLM:
```bash
cd ~/.cache/flashinfer/0.6.13/121a/cached_ops/fused_moe_120/
source vllm_venv/bin/activate
export MAX_JOBS=1 NVCC_THREADS=1
ninja -j1
```
This compiles all .o files and links the .so without loading the model. Then vLLM launch finds the cached .so and skips compilation.

**Detection**: check kernel logs for NVRM OOM + cicc processes:
```bash
journalctl -k --since "1 hour ago" | grep -i "oom\|nvrm\|out of memory"
ps aux | grep -c cicc  # if >5, MAX_JOBS is not set
```

## gpu_memory_utilization Tuning

`gpu_memory_utilization` is a fraction of CUDA `total_memory` (~121.69 GiB), NOT a hard limit on total consumption. Model weights are ALWAYS loaded fully regardless of this setting. The parameter only controls the KV cache budget = `total × util − model_weights − overhead − profile_run`.

**Formula**:
```
budget = 121.69 GiB × gpu_memory_utilization
KV cache budget = budget − model_weights − ~5 GiB (profile + overhead)
System gets = 121.69 GiB − budget − ~8 GiB (OS + other procs)
```

**Common mistakes**:
- Too LOW (e.g. 0.55): `budget = 66.9 GiB`. If model = 66.5 GiB, remainder = 0.4 GiB — insufficient for profile_run (~3 GiB). PyTorch grabs system RAM → swap → hang.
- Too HIGH (e.g. 0.92 default): `budget = 112 GiB`. KV cache gets ~40 GB that's never used (for small-KV models). System starves.

**Safe values for large MoE models (60–70 GB BF16)**:
- `0.65` — budget = 79.1 GiB, ~12.6 GiB for KV+profile, system gets ~34 GiB ✓ **PROVEN SAFE** (verified Jul 13 2026, including AutoTuner phase)
- `0.60` — budget = 73.0 GiB, ~6.5 GiB for KV+profile, system gets ~40 GiB ✓ (tight but works)
- `0.75` — **CAUSES NVRM OOM** — AutoTuner (FlashInfer kernel autotuning after model load) needs extra GPU memory. `journalctl -k` shows `NV_ERR_NO_MEMORY`. Do NOT use above 0.65 for BF16 MoE models.
- Below 0.58 — DANGER: insufficient for profile_run

**For small models (<20 GB)**: `0.85`–`0.90` is fine.

## KV Cache Optimization

### fp8 KV cache
```bash
--kv-cache-dtype fp8
```
- Halves KV cache memory (safe for inference, slight accuracy impact)
- **Safe for EAGLE3 training data extraction** — hidden states come from model layers, NOT from KV cache
- On GB10 with unified memory, every GB saved helps

### When KV cache is tiny (GQA models)
Models with few KV heads (e.g. 2 KV heads, 256 head_dim) and hybrid attention (75% linear layers without KV cache) have negligible KV cache (~20 KB/token). For such models:
- `--max-num-seqs 4` (reduce parallel sequences)
- `--max-model-len 8192` (limit pre-allocation)
- `--no-enable-prefix-caching` (don't waste memory on prefix cache)
- `--enforce-eager` (skip CUDA graph capture, saves 1–2 GB)

### max-num-batched-tokens constraint
When `--no-enable-chunked-prefill` is set (required by `launch_vllm.py` for hidden state extraction), vLLM requires:
```
max_num_batched_tokens >= max_model_len
```
Do NOT set `--max-num-batched-tokens` lower than `--max-model-len` — vLLM will crash with `ValidationError`.

## EAGLE3 Hidden State Extraction (launch_vllm.py)

The `speculators` library's `launch_vllm.py` script:
- Adds `--no-enable-chunked-prefill` automatically (required for hidden state connector)
- Adds `--speculative_config '{"method": "extract_hidden_states", ...}'`
- Adds `--kv_transfer_config '{"kv_connector": "ExampleHiddenStatesConnector", ...}'`
- Appends `--target-layer-ids` to `eagle_aux_hidden_state_layer_ids` + last layer

**Custom layer IDs**: For hybrid attention models (e.g. Qwen3.5 MoE with [lin,lin,lin,full] pattern), default `[2, N//2, N-3]` may hit ONLY linear attention layers. Use `--target-layer-ids` to select full_attention layers:
```bash
python scripts/launch_vllm.py /path/to/model \
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

## Complete Launch Template (GB10)

```bash
# CRITICAL: Prevent CUDA compiler OOM
export MAX_JOBS=1
export NVCC_THREADS=1

source /home/user/vllm_venv/bin/activate
cd /home/user/dev/speculators

python scripts/launch_vllm.py \
  /path/to/model \
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

## Monitoring Memory (GB10)

```bash
# Watch unified memory during vLLM startup
watch -n5 'free -h && echo "---" && ps aux --sort=-%mem | head -10 && echo "---" && ps aux | grep -c cicc'

# Check kernel for NVRM/OOM errors
journalctl -k --since "10 min ago" | grep -i "oom\|nvrm\|memory"
```

## FlashInfer JIT Compilation

On first vLLM startup with a new model, FlashInfer JIT-compiles CUDA kernels for 20-30 minutes. This is normal — the system is not hung. Compilation goes through three batches: SM90 base (~3 min) → quantized MoE (~7 min) → SM120 Blackwell (~10 min). Compiled kernels are cached in `~/.cache/flashinfer/` and reused on subsequent starts.

See `references/flashinfer-jit-compilation.md` for monitoring commands, batch details, and health checks.

## DiffusionGemma on GB10

DiffusionGemma 26B-A4B is a special case — it's a block-diffusion model (not autoregressive) with unique constraints:

**Memory profile** (much lighter than standard MoE):
- BF16: ~49GB (vs 66GB for Qwen3.5-MoE) → more headroom on 128GB GB10
- NVFP4: ~18GB → fits comfortably, 3.5M token KV cache at 0.70 util

**Stable settings** (tested on DGX Spark with Hermes):
- `--gpu-memory-utilization 0.60` — for BF16 (49GB). 0.70+ starves system RAM on GB10 unified memory → swap thrash (WindChimeRan benchmark, 2026-06-20). For NVFP4 (18GB), 0.70 is fine.
- `--max-num-seqs 4` — HARD LIMIT, not a tuning parameter. Diffusion state buffers per-sequence.
- `--attention-backend TRITON_ATTN` — required for bidirectional attention
- `VLLM_USE_V2_MODEL_RUNNER=1` — required env var for diffusion model runner
- `--diffusion-config '{"canvas_length": 256, "max_denoising_steps": 48}'` — NOT `--diffusion-steps`
- Do NOT use `--enforce-eager` — kills CUDA graph capture, major perf loss
- `--override-generation-config '{"max_new_tokens": null}'` — model defaults to 256 (one canvas)

**BF16 Performance** (WindChimeRan benchmark, CUDA graphs ON, random 1024-in/512-out):
- c=1: ~22 tok/s output, 66 tok/s total
- c=16: ~49 tok/s output, 146 tok/s total
- NVFP4 is ~2x faster but BF16 is full precision

**Canvas fill effect** — diffusion is per-canvas, not per-token:
- 256-token canvas costs same wall-clock regardless of how many tokens are actually emitted
- Short answers (8 tokens): ~16 tok/s (canvas wasted)
- Full canvas (256+ tokens): peak tok/s
- Agent tasks with long outputs naturally fill canvases → higher effective throughput

**Performance**: ~101 tok/s single (NVFP4), ~148 tok/s aggregate at c=4.
**Hermes tested**: confirmed working through Telegram gateway by miter37 (2026-06).

**🔴 Thinking-mode timeout on heavy presets:** `enable_thinking: true` + large system prompt (plan2 ≈ 15K tokens) = 350s+ delays. The model burns multiple canvases on hidden reasoning tokens before visible output. With diffusion's fixed per-canvas cost (48 denoising steps), 5+ thinking canvases before the tool call = 5+ minutes of invisible generation. **Disable thinking for non-reasoning tasks.** Full case study + diagnostic pipeline in `hermes-api-troubleshooting` → `references/diffusion-timeout-case-study.md`.

See `diffusion-llm-local` skill → `references/diffusiongemma-vllm-dgx-spark.md` for full serve script.

## DFlash Speculative Decoding on vLLM (0.25.0+)

DFlash is natively supported in vLLM 0.25.0 but requires THREE fixes before it will serve on Qwen3.6 models with hybrid attention (GDN + FullAttention layers). These patches are temporary — check if upstream vLLM has merged them before applying.

1. **Patch `_resolve_layer_attention()`** in `vllm/model_executor/models/qwen3_dflash.py` — remove the `NotImplementedError` guard for mixed sliding/full attention (the per-layer code below it works correctly).
2. **Patch `DFlashProposer`** in `vllm/v1/spec_decode/dflash.py` — override `validate_same_kv_cache_group()` to a no-op and override `initialize_attn_backend()` with the multi-group version from `step3p5.py`. Do NOT use `--disable-hybrid-kv-cache-manager` — it breaks hybrid target models (can't convert MambaSpec/SSM states to FullAttentionSpec).
3. **Export venv bin to PATH** — `export PATH="/path/to/venv/bin:$PATH"` so FlashInfer's JIT subprocess can find `ninja`.

See `speculative-decoding` skill → pitfalls #34-#36 for details, and `templates/serve_vllm_dflash.sh` for a ready-to-use script.

## Pitfalls

1. **`nvidia-smi` shows `Not Supported` for memory on GB10** — don't rely on it. Use `free -h` and `torch.cuda.mem_get_info()`.
2. **`--swap-space` is useless on GB10** — swap uses the same unified memory. Set `--swap-space 0`.
3. **CUDA driver allocations are invisible to RSS** — a process showing 300 MB RSS can hold 66 GB via CUDA. Only `torch.cuda.mem_get_info()` shows true usage.
4. **`cicc` processes spawn during JIT compilation** — if system hangs during vLLM startup, check `ps aux | grep cicc`. If >5 processes, `MAX_JOBS=1` was not set.
5. **`--no-enable-chunked-prefill` is force-added by `launch_vllm.py`** — don't try to enable chunked prefill when extracting hidden states.
6. **EAGLE3 draft model context length is independent of training `max-model-len`** — the draft model processes one hidden state at a time (position +1 per TTT step). 260K context is limited by the target model, not the draft.
7. **`--enforce-eager` is for hidden states EXTRACTION only, not for EAGLE3 SERVING.** When serving a trained EAGLE3 speculator, remove `--enforce-eager` to enable CUDAgraph — gives ~23% throughput improvement on both baseline and speculator. The relative speculator speedup stays the same (~1.34x) because the bottleneck is GPU compute (MoE forward pass), not Python/kernel-launch overhead.

8. **Triton `flex_attention` backward OOM on GB10 (sm121).** Training (not just vLLM serving) with `torch.compile` and flex_attention crashes: `OutOfMemoryError: out of resource: triton_tem_fused_flex_attention_backward Required: 114688 Hardware limit: 101376`. GB10's shared memory limit (101376 bytes) is lower than the kernel requires (114688 bytes). Fix: use `--draft-attn-impl sdpa` (for speculators training) or `torch.backends.cuda.enable_flash_sdp(True)` + disable flex_attention in any training code on GB10. This affects ALL training on GB10, not just speculators.

9. **`FileNotFoundError: 'ninja'` during FlashInfer JIT when launching vLLM via serve scripts.** If a serve script hardcodes `PYTHON="/path/to/venv/bin/python"` but does not export the venv `bin/` to `PATH`, FlashInfer's `subprocess.run(["ninja", ...])` fails because ninja lives at `/path/to/venv/bin/ninja`. This occurs after model loading and KV-cache initialization, during CUDA graph profiling. Fix: add `export PATH="/path/to/venv/bin:$PATH"` at the top of any serve script, or `source vllm_venv/bin/activate` before launching.

## Multimodal Encoder Cache Profiling Spike (SEPARATE from JIT)

**This is the #1 cause of OOM when launching multimodal models (Qwen3.5-MoE VL, Qwen3.6-VL, etc.) on GB10.** It is NOT the same as cicc JIT compilation — the two have different symptoms and fixes.

### What happens

After model weights load, vLLM profiles the vision encoder to calculate memory budget. It does a dry-run with:
- **16 images** at **maximum feature size** (default `--limit-mm-per-prompt` is 16 per modality)
- Multiplied by **`--max-num-seqs`** (e.g., 4 → 64 image profiles total)
- Plus encoder cache reservation for `max-model-len` tokens

Log signature: `Encoder cache will be initialized with a budget of 262144 tokens, and profiled with 16 image items of the maximum feature size.`

### Memory impact (verified Jul 16 2026, Agents-A1 BF16)

```
Model weights:     65.5 GB
System + Hermes:   ~12 GB
Encoder profiling: ~28 GB spike (16 images × max_feature_size × 4 seqs)
────────────────────────────────
TOTAL:             ~106 GB  → spike to 119 GB at peak
Available:         ~121 GB
RESULT:             OOM (119/121 GB)
```

### FIX — add to vLLM launch:

```bash
--limit-mm-per-prompt '{"image": 0}'    # for text-only training data extraction (UltraChat, ShareGPT)
# OR
--limit-mm-per-prompt '{"image": 1}'    # for serving or mixed data extraction (images still work at runtime)
--max-num-seqs 1                         # 1 seq instead of 4 (for hidden state extraction)
```

This reduces profiling spike from ~28 GB to ~3-5 GB (image:0) or near zero (image:0 + seqs=1). **Images are still supported at inference** — `--limit-mm-per-prompt` only limits the profiling budget, not runtime capacity. DFlash/EAGLE3 operate on decode only; vision encoder runs during prefill and is unaffected by speculative decoding.

### Diagnostic: JIT spike vs encoder cache spike

| Signal | cicc JIT spike | Encoder cache spike |
|---|---|---|
| `ps aux \| grep -c cicc` | >0 (5-19 processes) | **0** |
| Log signature | `Loading safetensors...` (during weight load) | `Encoder cache will be initialized...` (after weight load) |
| MAX_JOBS fix helps? | ✅ Yes (limits parallel cicc) | ❌ No (no compilation involved) |
| `--limit-mm-per-prompt` fix helps? | ❌ No | ✅ Yes |
| Timing | During 7-min weight load | After weight load, during profiling |

**KEY RULE**: If `nvcc procs: 0` appears in logs but RAM is spiking, the cause is encoder cache profiling, NOT JIT. Check `--limit-mm-per-prompt` and `--max-num-seqs`.

## MAX_JOBS Recommendation (updated Jul 16 2026)

| MAX_JOBS | cicc spike | Use case |
|---|---|---|
| 1 | ~3-6 GB | Automated/cron, no human watching |
| **5** | **~15 GB** | **Manual launch with BF16 MoE — USER PREFERRED** |
| 10 | ~30 GB | Manual launch with small models or lots of free RAM |

**MAX_JOBS=5 is the sweet spot for GB10 with BF16 MoE models (60-70 GB)**: 5 parallel cicc × 3 GB = 15 GB transient, fits in the ~30-40 GB headroom after model load. Faster than MAX_JOBS=1, safer than MAX_JOBS=10.

## Profile-Run JIT Compilation (Second Wave)

After model weights load, vLLM runs a **profile run** to determine KV cache sizes. This can trigger a **second wave of JIT compilation** because:
- Profile run uses actual tensor shapes (different from model-loading shapes)
- FlashInfer compiles new kernel variants for batch_prefill, moe_gemm with real dimensions
- With MAX_JOBS=1, this can take **10-20 minutes** after model load
- Log appears frozen (Python stdout is block-buffered when redirected to file)

**Symptoms**: Log stuck on "Encoder cache will be initialized..." for 10+ minutes. Port 8000 not open. EngineCore at 30-50% CPU. `ps aux | grep nvcc` shows compilation.

**IMPORTANT**: If `ps aux | grep nvcc` shows 0 processes, the stall is NOT JIT — it is the multimodal encoder cache profiling spike (see section above).

**Detection**: Check `ps -o utime= -p $(pgrep EngineCore)` — if CPU time is increasing, it's working, not hung.

**Cache location issue**: If vLLM is launched from Hermes (HOME=/home/user/.hermes/home), FlashInfer cache goes to `~/.hermes/home/.cache/flashinfer/` NOT `~/.cache/flashinfer/`. Previous compilation in `~/.cache/` is NOT reused → full recompilation. Fix: symlink or copy cache:
```bash
cp -rn ~/.cache/flashinfer/* ~/.hermes/home/.cache/flashinfer/
```

**What gets compiled (Agents-A1 Qwen3.5-MoE)**:
- 32× cutlass_kernel_file_gemm_sm90_M128 (CUTLASS GEMM instantiations)
- 16× cutlass_kernel_file_gemm_sm90_M64
- 20× cutlass_kernel_file_gemm (SM120 + SM80 variants)
- 16× moe_gemm_kernels_{bf16,fp16,fp8,fp4,fp32}_{bf16,fp8,fp4,uint4,uint8,fp16,fp32}
- 10× batch_prefill_with_kv_cache (ragged + paged, masks 0-3, binding, main)
- Total: ~104 .o files, ~155 MB cache, ~30-40 min with MAX_JOBS=1

## EAGLE3 on llama.cpp

llama.cpp supports EAGLE3 since release b9723 (`--spec-type draft-eagle3`), including Qwen3.5/3.6 architectures. The speculators library outputs in its own format — separate GGUF conversion is needed for llama.cpp deployment.
