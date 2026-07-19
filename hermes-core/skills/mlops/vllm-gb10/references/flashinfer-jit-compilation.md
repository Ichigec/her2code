# FlashInfer JIT Compilation on GB10 — Monitoring Guide

FlashInfer (vLLM's attention/MoE backend) JIT-compiles CUDA kernels at vLLM startup. On GB10 (DGX Spark) this takes **20-30 minutes** and goes through three distinct batches. The system is not hung during this time — it is compiling.

## Compilation Batches

### Batch 1: SM90 base kernels (~3 min, 12:15-12:18)
- 62 files: basic MoE utilities, cutlass backend setup, SM90 generated gemm kernels
- Fast because SM90 (Hopper) kernels are well-optimized in the compiler
- Files: `moe_gemm_mixed_utils`, `cutlass_fused_moe_instantiation`, `90_cutlass_kernel_file_gemm_sm90_*`

### Batch 2: Quantized MoE kernels (~7 min, 14:36-14:43)
- 5 files: fp8/fp4/uint4/uint8 MoE gemm variants
- ~2-3 min per kernel
- Files: `moe_gemm_kernels_{fp8_uint4,fp8_fp8,fp16_uint8,fp16_uint4,bf16_fp4}`

### Batch 3: SM120 Blackwell kernels (~8-10 min)
- 11 files: SM120-specific generated grouped gemm kernels
- Slowest batch — SM120 (Blackwell) is a newer target
- Files: `cutlass_kernel_file_gemm_grouped_sm120_M128_BS_group*.generated.cu`

## Monitoring Commands

```bash
# Total compiled .o files (progress)
find /home/user/.cache/flashinfer/ -name "*.cuda.o" ! -name "*.o.d" 2>/dev/null | wc -l

# Active compilation processes
ps aux | grep -c nvcc  # nvcc processes
ps aux | grep -c cicc  # cicc processes (front-end compiler)

# What's currently being compiled
ps aux | grep "[n]vcc" | sed 's/.*-c //' | sed 's/ -o.*//' | sed 's|.*/||'

# SM120 progress (the final batch)
compiled=$(find /home/user/.cache/flashinfer/ -path "*sm120*" -name "*.cuda.o" ! -name "*.o.d" 2>/dev/null | wc -l)
total=$(find /home/user/.cache/flashinfer/0.6.13/121a/generated/ -name "*sm120*" 2>/dev/null | wc -l)
echo "SM120: $compiled/$total"

# Cache directory size (grows as compilation progresses)
du -sh /home/user/.cache/flashinfer/
```

## After Compilation

Once all kernels are compiled, vLLM proceeds to:
1. Load model weights (66 GB BF16 → ~2-3 min on GB10 unified memory)
2. Profile run (~30 sec)
3. Start accepting requests

Check readiness:
```bash
curl -s --max-time 3 http://localhost:8000/v1/models | python3 -m json.tool
```

## Cache Persistence

Compiled kernels are cached in `/home/user/.cache/flashinfer/`. Subsequent vLLM starts with the same model skip compilation entirely (~30 sec startup instead of 25 min). The cache is tied to:
- FlashInfer version (e.g., 0.6.13)
- GPU architecture (e.g., 121a = GB10)
- Model config (e.g., fused_moe_120 = 120 experts config)

If you change the model architecture or FlashInfer version, recompilation occurs.

## Pitfall: MAX_JOBS=1 slows compilation

Setting `MAX_JOBS=1` (required to prevent OOM, see SKILL.md) means only one kernel compiles at a time instead of 19 in parallel. This makes compilation **3-5x slower** but prevents system crashes. The tradeoff is necessary on GB10 UMA.

## Quick Health Check

If vLLM has been "starting" for >40 minutes, something is wrong:
```bash
# Check if compilation is still progressing (new files appearing)
find /home/user/.cache/flashinfer/ -name "*.cuda.o" -newer /tmp/checkpoint_marker 2>/dev/null | wc -l
touch /tmp/checkpoint_marker
sleep 60
find /home/user/.cache/flashinfer/ -name "*.cuda.o" -newer /tmp/checkpoint_marker 2>/dev/null | wc -l
# If 0 after 60s, compilation is stuck — check dmesg for OOM
```
