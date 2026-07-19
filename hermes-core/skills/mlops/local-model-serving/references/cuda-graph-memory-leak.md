# CUDA Graph Memory Leak on DGX Spark (GB10) with qwen35moe

> July 2026. Root cause: llama.cpp CUDA graph accumulation on GB10 unified memory with Qwen3.5/3.6 MoE architecture.

## TL;DR

**Fix:** `export GGML_CUDA_DISABLE_GRAPHS=1` before launching llama-server. Disables CUDA graphs entirely — slight performance cost (~5-10% tok/s) but stops memory growth completely.

## Mechanism

llama.cpp caches compiled CUDA graphs for reuse. On normal models (GPT-OSS, Gemma), a new graph is created every ~256 tokens. On qwen35moe (attention + DeltaNet hybrid), the compute graph changes every 2 tokens → 500 new graphs per 1000-token generation.

Each graph is stored in `std::unordered_map<const void*, unique_ptr<ggml_cuda_graph>>` keyed by `cgraph->nodes[0]` (first node pointer). An eviction sweep runs every 5 seconds, removing graphs unused for ≥10 seconds. But during active generation, graphs accumulate faster than eviction.

At ~30 MB per CUDA graph × 500 graphs = 15 GB peak per generation cycle. On unified memory (GB10), this is shared system RAM → OOM killer.

## Code Evidence

`ggml/src/ggml-cuda/common.cuh:1234`:
```cpp
bool is_enabled() const {
    static const bool disable_cuda_graphs_due_to_env = (getenv("GGML_CUDA_DISABLE_GRAPHS") != nullptr);
    return !(disable_due_to_gpu_arch || disable_cuda_graphs_due_to_env);
}
```

Setting ANY value to `GGML_CUDA_DISABLE_GRAPHS` disables graph capture. GB10 (SM 12.1) is NOT auto-excluded — `disable_due_to_gpu_arch` defaults to `false`.

## Confirmation

- [Issue #20315](https://github.com/ggml-org/llama.cpp/issues/20315): RPC server fills entire unified memory + 16 GB swap → OOM. Fix: `GGML_CUDA_DISABLE_GRAPHS=1`. Reproduced on ASUS GX10 (GB10, same chip as DGX Spark). Also reproduced on llama-server (not just RPC).
- [croll83/llama.cpp-dgx](https://github.com/croll83/llama.cpp-dgx): "v5 + DFlash leaks ~2-3 GB/hour... reaching OOM in days." Fork now deprecated — upstream surpassed it.
- [Issue #21265](https://github.com/ggml-org/llama.cpp/issues/21265): Memory leak on RPC CUDA backend (OPEN as of July 2026).

## Secondary Fixes

1. **`--flash-attn on`** (explicit, not `auto`): Required when using `--cache-type-k q8_0 --cache-type-v q8_0`. Without it, KV cache silently falls back to f16 (2× memory).

2. **`-np 2`** (limit parallel slots): Default `auto` may create 4+ slots, each with its own KV cache allocation. At 256K context with q8_0: ~3 GB per slot.

3. **`-c 65536`** for non-reasoning models: Nex and AgentWorld don't need 256K context. 64K saves ~2 GB KV cache per model.

## Verification

After applying `GGML_CUDA_DISABLE_GRAPHS=1`:
```bash
# Monitor RSS over hours — should be flat
while true; do
  for pid in $(pgrep llama-server); do
    rss=$(awk '/VmRSS/{printf "%.1f", $2/1048576}' /proc/$pid/status)
    echo "$(date +%H:%M:%S) PID $pid RSS=${rss}GB"
  done
  sleep 300
done
```

## Not a Fix

- `--max_requests_before_restart`: Only applies to worker-based servers (uvicorn), not llama-server.
- Reducing context: Reduces KV cache (fixed at startup) but doesn't stop CUDA graph accumulation.
- Restarting models periodically: Workaround, not a fix. With the env var, no restart needed.
