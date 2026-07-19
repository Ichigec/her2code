#!/bin/bash
# SGLang + DFlash serve script for FP8-quantized MoE targets
# Optimized for Agents-A1 / Qwen3.5-35B-A3B / Qwen3.6-35B-A3B on DGX Spark (GB10)
#
# FP8 dynamic is the recommended target quantization on GB10 for DFlash:
#   - 36 GB vs 66 GB (BF16) — 60 GB headroom for Hermes stack + KV cache
#   - <0.5% quality loss vs 2-5% for INT4 GGUF
#   - Near-lossless hidden states for DFlash draft acceptance
#
# This script adds pre-flight checks vs the BF16 template:
#   - Memory budget validation (pitfall #17: BF16 can crash DGX Spark)
#   - Port collision detection
#   - MAX_JOBS=1 / NVCC_THREADS=1 to prevent cicc OOM (pitfall #19)
#   - Configurable block_size, max_requests, mem_fraction
#
# Usage:
#   bash serve_sglang_dflash_fp8.sh [PORT]
#   MODEL=/path/to/model DRAFT=/path/to/draft bash serve_sglang_dflash_fp8.sh
#   PORT=8102 bash serve_sglang_dflash_fp8.sh

set -euo pipefail

# --- CONFIG ---
SGLANG_VENV="${SGLANG_VENV:-$HOME/sglang_venv}"
MODEL="${MODEL:-/home/user/models/agents-a1-fp8}"
DRAFT="${DRAFT:-/home/user/models/Qwen3.6-35B-A3B-DFlash}"
PORT="${1:-8102}"
HOST="${HOST:-0.0.0.0}"
MEM_FRAC="${MEM_FRAC:-0.65}"       # 0.65 for FP8 (36GB model, plenty headroom); 0.70 for BF16 is risky
MAX_REQ="${MAX_REQ:-4}"
BLOCK_SIZE="${BLOCK_SIZE:-16}"

NUM_DRAFT_TOKENS=$((BLOCK_SIZE - 1))

# --- PRE-FLIGHT ---
AVAIL_GB=$(awk '/MemAvailable/ {printf "%.0f", $2/1024/1024}' /proc/meminfo)
echo "Available RAM: ${AVAIL_GB} GB"

if ss -tlnp 2>/dev/null | grep -q ":${PORT} "; then
    echo "ERROR: Port ${PORT} already in use!"
    ss -tlnp | grep ":${PORT} "
    exit 1
fi

# Estimate model size from path
MODEL_SIZE_GB=36
if [[ "$MODEL" == *"fp8"* ]]; then MODEL_SIZE_GB=36
elif [[ "$MODEL" == *"gguf"* ]] || [[ "$MODEL" == *"GGUF"* ]]; then MODEL_SIZE_GB=22
else MODEL_SIZE_GB=66; fi  # assume BF16

NEEDED=$((MODEL_SIZE_GB + 20))
if [ "$AVAIL_GB" -lt "$NEEDED" ]; then
    echo "ERROR: Need ${NEEDED} GB, only ${AVAIL_GB} GB available."
    echo "Running model servers:"
    pgrep -af "llama-server\|sglang\|vllm" || echo "  (none found)"
    exit 1
fi

echo "Model: ${MODEL} (~${MODEL_SIZE_GB} GB)"
echo "Draft: ${DRAFT}"
echo "Port: ${PORT}  MemFrac: ${MEM_FRAC}  DraftTokens: ${NUM_DRAFT_TOKENS}"

# --- LAUNCH ---
export PATH="$SGLANG_VENV/bin:$PATH"
export MAX_JOBS=1
export NVCC_THREADS=1
source "$SGLANG_VENV/bin/activate"
source "$HOME/.cargo/env" 2>/dev/null || true

echo "Launching SGLang (cold start: 5-15 min FlashInfer JIT on first run)..."

exec python -m sglang.launch_server \
    --model-path "$MODEL" \
    --trust-remote-code \
    --speculative-algorithm DFLASH \
    --speculative-draft-model-path "$DRAFT" \
    --speculative-num-draft-tokens "$NUM_DRAFT_TOKENS" \
    --tp-size 1 \
    --attention-backend flashinfer \
    --mem-fraction-static "$MEM_FRAC" \
    --mamba-scheduler-strategy extra_buffer \
    --host "$HOST" \
    --port "$PORT" \
    --max-running-requests "$MAX_REQ" \
    --cuda-graph-max-bs-decode "$MAX_REQ"
