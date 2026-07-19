# SGLang DFlash Deployment on DGX Spark (GB10)

Operational reference for running DFlash speculative decoding via SGLang on NVIDIA GB10
unified memory. Verified Jul 14 2026 with Qwen3.6-27B + z-lab DFlash draft.

## Build Requirements (ARM64 / GB10)

SGLang from PR #23000 needs build tools not present by default:

```bash
# 1. Rust compiler (for sglang-grpc Rust extension)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME/.cargo/env"

# 2. protoc (use torch's bundled version — no system package needed)
export PROTOC="$(python -c 'import torch,os;print(os.path.join(os.path.dirname(torch.__file__),\"bin\",\"protoc\"))')"

# 3. Install SGLang from PR #23000
pip install "git+https://github.com/sgl-project/sglang.git@refs/pull/23000/head#subdirectory=python"
```

**IMPORTANT: SGLang installs to its own venv.** When installing from a vLLM venv's `activate`,
pip may pull SGLang into a separate `sglang_venv` due to dependency conflicts. Always verify:
```bash
python -c "import sglang; print(sglang.__file__)"
# Should show the venv you expect
```

Recommended setup: dedicated `~/sglang_venv` separate from `~/vllm_venv`. They do NOT conflict.

## Attention Backend Selection

| Backend | GB10 (SM 12.1) | BF16 >50GB | FP8 <40GB | Notes |
|---|---|---|---|---|
| `flashinfer` | ✅ Default | ⚠️ JIT spike risk | ✅ Safe | Default for DFlash on GB10 |
| `triton` | ✅ Available | ✅ **Recommended** | ✅ Works | Zero JIT compilation (~10-15% slower) |
| `fa3` | ❌ AssertionError | ❌ | ❌ | `FlashAttention v3 Backend requires SM>=80 and SM<=90` |
| `fa4` | ⚠️ Untested | ⚠️ | ⚠️ | May work on SM 12.x, unverified for DFlash |

**BF16 >50 GB models: use `--attention-backend triton`** to avoid FlashInfer JIT OOM.
The JIT spike (20-30 GB from 6+ parallel cicc processes) combined with a 65 GB model
can exceed 121 GB unified memory. Triton bypasses this entirely. See SKILL.md pitfall #46.

## Critical Launch Flags for Hybrid GDN Models

```bash
--attention-backend flashinfer              # ONLY working backend on GB10
--mamba-scheduler-strategy extra_buffer     # REQUIRED for GDN/Mamba linear-attention layers
--mem-fraction-static 0.75                  # 27B: works; 35B MoE may need 0.85+
--trust-remote-code                         # DFlash draft uses custom dflash.py
```

Without `--mamba-scheduler-strategy extra_buffer`, SGLang may fail to schedule GDN
(GatedDeltaNet) linear-attention layers correctly in the hybrid Qwen3.6 architecture.

## Startup Sequence & Timing (Qwen3.6-27B)

Total cold start: **~5 minutes**. Sequence:

| Phase | Time | Log signal |
|---|---|---|
| Config parse + tokenizer init | ~10s | `server_args=ServerArgs(...)` |
| Target model weight loading (15 shards) | ~3-4 min | `Multi-thread loading shards: 100%` |
| Target KV cache allocation | ~1s | `KV Cache is allocated` |
| Target CUDA graph capture (bs 1-4) | ~40s | `Capture cuda graph end` |
| Draft model weight loading (1 shard) | ~22s | `type=DFlashDraftModel` |
| Draft KV cache allocation | ~1s | |
| Draft CUDA graph capture (bs 1-4) | ~28s | `Capture cuda graph end` |
| Server ready | | `The server is fired up and ready to roll!` |

## First-Request JIT Compilation

The **first decode batch** after server start is **very slow** (~1.4 tok/s) due to Triton
kernel JIT compilation. Subsequent decode batches reach steady state (10-15 tok/s).

Log evidence:
```
Decode batch ... accept len: 5.30, accept rate: 0.29, gen throughput (token/s): 1.41   ← JIT
Decode batch ... accept len: 3.62, accept rate: 0.17, gen throughput (token/s): 10.57  ← steady
```

Always send a warmup request before benchmarking.

## API Gotcha: Model Name

SGLang uses the **full `--model-path`** as the served model name in API responses. Requests
must use this exact string as the `model` field:

```bash
# CORRECT — model field matches --model-path exactly
curl -s http://localhost:8123/v1/chat/completions \
  -d '{"model":"/home/user/models/Qwen3.6-27B","messages":[...]}'

# WRONG — custom served-model-name is NOT supported by SGLang like vLLM
curl -s http://localhost:8123/v1/chat/completions \
  -d '{"model":"qwen3.6-27b","messages":[...]}'  # → 404 or model not found
```

To check the exact model name: `curl -s http://localhost:8123/v1/models | python3 -m json.tool`

## Monitoring Acceptance Rate

SGLang logs spec decode stats per decode batch (every ~40 generated tokens):

```bash
# Real-time acceptance monitoring
tail -f /tmp/sglang_dflash.log | grep --line-buffered "accept len"

# Example output:
# Decode batch ... accept len: 4.38, accept rate: 0.23, gen throughput (token/s): 10.53
# Decode batch ... accept len: 6.92, accept rate: 0.40, gen throughput (token/s): 1.43 (JIT)
```

Key metrics in log line:
- `accept len`: mean number of tokens accepted per draft block (0 to block_size-1)
- `accept rate`: fraction of draft tokens accepted (0.0 to 1.0)
- `gen throughput (token/s)`: wall-clock generation speed

## SGLang vs vLLM: DFlash on Hybrid GDN Targets

| Metric | SGLang (PR #23000) | vLLM 0.25.0 |
|---|---|---|
| Accept rate | 20-40% | **0.0-0.7%** (BROKEN) |
| Throughput | 10-15 tok/s | 2-3 tok/s (SLOWER than baseline) |
| Hidden state extraction | ✅ Correct | ❌ Garbage for GDN layers |
| Root cause | Proper GDN+FullAttention handling | DFlashProposer doesn't extract correct hidden states from hybrid layers |

**Always use SGLang for DFlash on Qwen3.6 hybrid GDN targets.** vLLM DFlash is unverified
on pure-attention (non-hybrid) targets.

## DFlash Draft Config: 27B vs 35B-A3B

| Parameter | Qwen3.6-27B-DFlash | Qwen3.6-35B-A3B-DFlash |
|---|---|---|
| num_hidden_layers | 5 | 6 |
| target_layer_ids | [1, 16, 31, 46, 61] (5 IDs) | [1, 6, 11, 16, 22, 27, 32, 37] (8 IDs) |
| num_target_layers | 64 | 40 |
| block_size location | Top-level `config.json` | Nested in `dflash_config` |
| mask_token_id | 248070 | 248077 |
| intermediate_size | 17408 | 6144 |
| sliding_window | 2048 | 4096 |
| hidden_size | 5120 | 2048 |
| Model size | 3.46 GB | 737 MB |

The 35B draft is actually **smaller** (737 MB vs 3.46 GB) because hidden_size=2048
(MoE has smaller hidden dimension per expert vs dense model's 5120).
