# Multi-Model GPU Contention on DGX Spark

> 3-4 July 2026. Investigation into garbage tokens from multi-instance llama-server on DGX Spark (GB10, 128GB unified memory). **Fixed: `--no-mmap` resolves all contention.**

## Executive Summary

**Problem:** Multiple llama-server processes on DGX Spark: only the first-loaded model works; others produce garbage (repeating `////`, `????`). Memory is available, models are correctly quantized.

**Root cause:** Default `--mmap` creates conflicting memory mappings between multiple CUDA contexts on unified memory. The CUDA UVA driver cannot properly isolate mmap'd pages across contexts.

**Fix:** Add `--no-mmap` to EVERY llama-server instance. Loads weights explicitly via `read()` instead of mmap. Verified: all 3 models work simultaneously at 28-35 tok/s each.

**Independent confirmation:** re-cinq.com blog: "mmap is the enemy on unified memory"; llama.cpp issue #12991 (multiple instances on same GPU lock up); issue #20052 (multi-GPU garbage with repeating `?` characters); vLLM forum: "llama.cpp locks CUDA context causing conflicts".

## Experimental Data

### Without --no-mmap (broken)

| Test | Config | Model 1 | Model 2 | Model 3 |
|------|--------|---------|---------|---------|
| A | nex first, qwen second, world third (32K) | ✅ nex | ❌ qwen `////` | ❌ world `////` |
| B | qwen first, nex second (2 models) | ✅ qwen | ✅ nex | — |
| C | qwen first, nex second, world third (32K) | ✅ qwen | ✅ nex | ❌ world `////` |
| D | -c 4096 (3 models) | ❌ nex `????` | ✅ qwen | ❌ world `////` |

**Pattern:** first-loaded model works. Later models break. Reducing context doesn't help.

### With --no-mmap (fixed)

| Test | Config | Model 1 | Model 2 | Model 3 |
|------|--------|---------|---------|---------|
| E | qwen first, nex second, world third (32K) | ✅ qwen | ✅ nex | ✅ world |
| F | Raw completion (all 3) | ✅ `2+2 equals 4...` | ✅ `2+2 equals 4...` | ✅ `<think>...` |
| G | Chat (all 3) | ✅ reasoning+content | ✅ `Hello` | ✅ `Final answer: Hello` |
| H | Code gen (all 3) | ✅ (thinking mode) | ✅ `def reverse...` | ✅ `def reverse(s): return s[::-1]` |

**All 3 models work correctly. No garbage tokens.**

## Test Methodology

```bash
# Kill all, load ONE model with --no-mmap, test
for pid in $(pgrep -x llama-server); do kill -9 $pid; done; sleep 3

export GGML_CUDA_ENABLE_UNIFIED_MEMORY=1
llama-server -m model.gguf --alias name --no-mmap -ngl 99 -c 32768 \
  --host 127.0.0.1 --port PORT --jinja &

# Wait for model, then test
curl -s http://127.0.0.1:PORT/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"prompt":"What is 2+2?","max_tokens":16,"temperature":0}' \
  | python3 -c "
import sys,json
t=json.load(sys.stdin)['choices'][0]['text']
print('GARBAGE' if set(t.strip())<=set('/?') else 'OK:', repr(t[:40]))
"
# If OK, load next model and repeat. If GARBAGE, --no-mmap is missing.
```

## What it's NOT

- **NOT OOM** — plenty of free memory (45GB+)
- **NOT quantization** — APEX models work perfectly in isolation  
- **NOT context size** — same pattern at 4096 and 32768
- **NOT loading order fixable** — order changes which models break but doesn't fix root cause

## Related

- `references/q8-ssm-garbage-tokens.md` — Q8_0 on SSM tensors (same symptom: repeating `/`)
- `references/dgx-spark-deployment.md` — full DGX Spark deployment guide
- `templates/start-llama.sh` — launch script with `--no-mmap` built in
