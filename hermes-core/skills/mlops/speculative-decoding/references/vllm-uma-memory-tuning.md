# vLLM Memory Tuning on Unified Memory Architecture (UMA)

DGX Spark (GB10), Jetson Orin, GH200 — platforms where GPU and CPU share
physical RAM. vLLM's default memory assumptions break here in non-obvious ways.

## The Core Problem

On discrete GPUs (A100, H100), GPU VRAM and system RAM are separate pools.
`gpu_memory_utilization=0.92` means "use 92% of GPU VRAM" — system RAM is
untouched. On UMA (GB10), **CUDA total_memory == system RAM** (121.69 GiB).
Setting `gpu_memory_utilization=0.92` means vLLM tries to claim 112 GiB of
the 121.69 GiB total — leaving only 9.7 GiB for the OS, which is unstable.

## How vLLM Calculates Memory (Source Code Analysis)

vLLM v0.25.0, file `vllm/v1/worker/utils.py`, function `request_memory()`:

```python
def request_memory(init_snapshot, cache_config):
    requested_memory = math.ceil(
        init_snapshot.total_memory * cache_config.gpu_memory_utilization
    )
    # ... validates free_memory >= requested_memory ...
    return requested_memory
```

Key: `init_snapshot.total_memory` comes from `torch.cuda.mem_get_info()` on UMA
(see `vllm/utils/mem_utils.py`, `MemorySnapshot.measure()`). vLLM has a UMA
codepath that uses `psutil.virtual_memory().available` for `free_memory`, but
`total_memory` still comes from CUDA = 121.69 GiB.

**The budget formula:**
```
budget = CUDA_total × gpu_memory_utilization
       = 121.69 GiB × utilization
```

This budget must cover:
1. **Model weights** (always loaded fully, regardless of utilization)
2. **Profile run** (~3 GiB — vLLM does a dummy forward pass to measure memory)
3. **vLLM overhead** (~2 GiB — CUDA context, scheduler, etc.)
4. **KV cache** (budget - weights - profile - overhead = available for KV cache)

## Why Too LOW Is Catastrophic on UMA

On discrete GPUs, setting `gpu_memory_utilization` too low just means less KV
cache — the model still loads into VRAM, system RAM is unaffected. On UMA:

```
util=0.55:  budget = 121.69 × 0.55 = 66.9 GiB
            model weights = 66.5 GiB
            remainder = 0.4 GiB  ← need 5+ GiB for profile + overhead
            
            → Profile run allocates ~3 GiB beyond budget
            → On UMA, "beyond GPU budget" = system RAM (same pool)
            → PyTorch grabs system RAM via cudaMalloc
            → Linux starts swapping
            → System hangs (unified memory = swap targets same RAM)
```

**Symptom**: System freezes during vLLM initialization, specifically during
"Loading safetensors checkpoint shards" → profile run phase. No error message,
just a hard hang requiring power cycle.

## Correct Values for Common Models on DGX Spark

| Model | Weights (BF16) | Min util | Recommended util | Budget at rec | System gets |
|---|---|---|---|---|---|
| Agents-A1 (35B MoE) | 66.5 GiB | 0.60 | **0.65** | 79.1 GiB | 34.6 GiB |
| Qwen3.6-35B-A3B | 66.5 GiB | 0.60 | **0.65** | 79.1 GiB | 34.6 GiB |
| Agents-A1 FP8 | ~35 GiB | 0.40 | **0.50** | 60.8 GiB | 52.9 GiB |
| Llama-3.1-8B | ~16 GiB | 0.20 | **0.30** | 36.5 GiB | 77.2 GiB |

**Formula to calculate minimum safe utilization:**
```
min_util = (model_weights + 5 GiB) / 121.69
```
Where 5 GiB = profile_run (3 GiB) + overhead (2 GiB). Add 1-2 GiB margin.

## Optimization Flags for Memory-Constrained UMA

| Flag | Effect | Safe for EAGLE3? |
|---|---|---|
| `--max-num-batched-tokens` | Reduces profile_run memory — BUT must be >= `max-model-len` when chunked prefill is off (which `launch_vllm.py` forces). Omit this flag to let vLLM auto-set it to `max-model-len` | Yes |
| `--kv-cache-dtype fp8` | Halves KV cache size | Yes — hidden states come from model layers, not KV cache |
| `--max-num-seqs 4` | Fewer concurrent sequences = less KV cache pre-allocation | Yes |
| `--max-model-len 8192` | Matches training data seq-length. KV cache cost is negligible for MoE models with few KV heads | Yes (KV cache = 335 MB for 8192x4 batch in fp8) |
| `--no-enable-prefix-caching` | Don't cache prefix tokens | Yes |
| `--swap-space 0` | Disable CPU swap for KV cache (pointless on UMA — same RAM) | Yes |
| `--enforce-eager` | Disable CUDA graph capture, saves ~1-2 GiB | Yes (slight perf cost) |

## KV Cache Is Tiny for Qwen3.5-MoE (Agents-A1)

This model has a hybrid attention architecture:
- 30/40 layers: `linear_attention` (Gated DeltaNet, **no KV cache**)
- 10/40 layers: `full_attention` (standard, has KV cache)
- 2 KV heads, head_dim=256 (GQA — very few KV heads)

Per-token KV cache: 2 × 2 × 256 × 10 layers × 2 bytes (BF16) = **20 KB/token**
For batch=4 × 4096 tokens: **336 MB** (BF16), **168 MB** (FP8)

This means vLLM's default behavior of pre-allocating huge KV cache pools is
especially wasteful for this model. At `util=0.92`, vLLM reserves ~50 GiB for
KV cache that will never be used — the actual need is <0.5 GiB.

## CRITICAL: CUDA Compiler (`cicc`) Processes on UMA

Even with the correct `gpu_memory_utilization`, vLLM can still crash the system
on UMA. The cause is **invisible to `nvidia-smi`** — it's in process RSS.

### What Happens

When vLLM starts, PyTorch JIT-compiles CUDA kernels. This spawns multiple
`cicc` (NVIDIA CUDA compiler) and `cudafe++` processes. On discrete GPUs
these are harmless (they use system RAM, not VRAM). On UMA, **system RAM IS
GPU RAM** — these processes directly compete with the model for the same
physical memory pool.

### Measured Impact (Jul 13, 2026, DGX Spark)

- **19 parallel `cicc` + 1 `cudafe++` processes** spawned during vLLM startup
- Total RSS: **43.2 GB** (measured from kernel OOM dump)
- Combined with 66.5 GB model (CUDA driver allocation, invisible to RSS):
  `66.5 + 43.2 + 8 (system) = 117.7 GB` out of 127.4 GB → **9 GB free → OOM**

Individual `cicc` RSS ranged from 0.6 GB to 4.1 GB. The largest:
```
[41189]  1000  1444373  1081584  1081312  ...  cicc   = 4.1 GB RSS
[41253]  1000  1378988  1038445  1037867  ...  cicc   = 4.0 GB RSS
[41316]  1000  1126288  1013253  1012518  ...  cicc   = 3.9 GB RSS
```

### The Fix: Limit Compiler Parallelism

```bash
# BEFORE launching vLLM — set these environment variables:
export MAX_JOBS=1        # Compile one kernel at a time (not 19 in parallel)
export NVCC_THREADS=1    # Single-threaded nvcc invocation

# Then launch vLLM normally
MAX_JOBS=1 NVCC_THREADS=1 python scripts/launch_vllm.py ...
```

**Memory savings**: 43.2 GB → ~3 GB (one `cicc` process at a time).
**Trade-off**: Slower startup (sequential compilation), but no OOM crash.

### How to Diagnose

```bash
# Check for cicc processes consuming RAM
ps aux | grep -E "cicc|cudafe" | awk '{sum += $6} END {printf "Total: %.1f GB\n", sum/1024/1024}'

# Full memory picture during vLLM startup
ps aux --sort=-%mem | head -20    # Top RSS consumers
free -h                           # System-level view
# NOTE: nvidia-smi is NOT sufficient — CUDA driver allocations
# (model weights) are NOT shown in process RSS, and cicc processes
# are NOT shown in nvidia-smi. You need BOTH views.
```

### Kernel OOM Log Analysis

When the system crashes, check previous boot's kernel logs:
```bash
journalctl -b -1 -k --no-pager | grep -A50 "oom-kill\|invoked oom"
```

Key indicators of `cicc` OOM:
- `NVRM: Out of memory [NV_ERR_NO_MEMORY]` in dmesg (NVIDIA driver can't allocate)
- `VLLM::EngineCor` in OOM dump with low RSS (~273 MB) — model is in driver memory
- Many `cicc` processes with high RSS in the task list
- `Free swap = 0kB` — swap fully exhausted before OOM kill

## `--max-num-batched-tokens` vs `--max-model-len` Constraint

When chunked prefill is disabled (which `launch_vllm.py` force-adds via
`--no-enable-chunked-prefill`), vLLM requires:
```
max_num_batched_tokens >= max_model_len
```

Setting `--max-num-batched-tokens 512` with `--max-model-len 4096` causes:
```
ValidationError: max_num_batched_tokens (512) is smaller than max_model_len (4096).
```

**Fix**: Either remove `--max-num-batched-tokens` (vLLM defaults it to
`max_model_len`) or set it >= `max_model_len`. Do NOT try to use a small
`max-num-batched-tokens` to reduce memory when chunked prefill is off —
it doesn't help and causes a crash.

## Verification Commands

```bash
# Check CUDA total (should be ~121.69 GiB on GB10)
python3 -c "import torch; f,t = torch.cuda.mem_get_info(); print(f'{t/1024**3:.2f} GiB')"

# Check system RAM matches CUDA total (unified memory confirmation)
python3 -c "import torch, psutil; _,t = torch.cuda.mem_get_info(); print(f'CUDA: {t/1024**3:.2f} GiB, RAM: {psutil.virtual_memory().total/1024**3:.2f} GiB')"

# Calculate safe utilization for a given model
python3 -c "
model_gb = 66.5  # BF16 Agents-A1
cuda_total = 121.69  # GiB
overhead = 5  # profile + vLLM overhead
min_util = (model_gb + overhead) / cuda_total
print(f'Min safe utilization: {min_util:.2f}')
print(f'Recommended (min + 0.05 margin): {min_util + 0.05:.2f}')
"

# Monitor memory while vLLM loads (run in separate terminal)
watch -n 2 'free -h; echo "---"; nvidia-smi --query-gpu=memory.used --format=csv,noheader 2>/dev/null || echo "nvidia-smi N/A on UMA"'
```

## Session Reference

- **Discovered**: Jul 13, 2026, during EAGLE3 training pipeline setup
- **Symptom 1**: `--gpu-memory-utilization 0.55` caused system hangs on DGX Spark
- **Root cause 1**: Budget (66.9 GiB) barely covered model weights (66.5 GiB),
  leaving 0.4 GiB — insufficient for vLLM's profile_run (~3 GiB)
- **Fix 1**: `--gpu-memory-utilization 0.65` + optimization flags
- **Symptom 2**: `--gpu-memory-utilization 0.65` STILL crashed the system
- **Root cause 2**: 19 parallel `cicc` CUDA compiler processes consumed 43.2 GB
  RSS (invisible to nvidia-smi). Combined with 66.5 GB model = 109.7 GB → OOM.
  Kernel logs showed `NVRM: Out of memory` (driver) then Linux OOM killer.
- **Fix 2**: `MAX_JOBS=1 NVCC_THREADS=1` before launching vLLM
- **Symptom 3**: `--max-num-batched-tokens 512` with `--max-model-len 4096`
  caused `ValidationError` (chunked prefill disabled by launch_vllm.py)
- **Fix 3**: Remove `--max-num-batched-tokens` or set >= `--max-model-len`
- **vLLM version**: 0.25.0
- **Source files analyzed**: `vllm/v1/worker/utils.py` (request_memory),
  `vllm/utils/mem_utils.py` (MemorySnapshot.measure — UMA codepath at line 147:
  `is_integrated_gpu` → uses `psutil.virtual_memory().available` for free_memory),
  `vllm/v1/worker/gpu_worker.py` (determine_available_memory — profile_run),
  `vllm/model_executor/model_loader/weight_utils.py` (safetensors_weights_iterator),
  `vllm/model_executor/model_loader/default_loader.py` (load_weights — uses safe_open/mmap)
