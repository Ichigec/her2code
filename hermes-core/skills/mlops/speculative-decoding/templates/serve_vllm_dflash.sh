#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  vLLM Serve: DFlash Speculative Decoding
#  Works with any Qwen3.6 model (27B dense, 35B-A3B MoE).
#  Requires vLLM 0.25.0+ (native DFlash support).
#
#  ⚠️  Also requires 3 source patches to vLLM 0.25.0 — see skill pitfalls #34-36.
#  These patches will be obsolete once vLLM merges DFlash multi-group support.
#
#  Usage:
#    ./serve_vllm_dflash.sh --target 27b               # DFlash
#    ./serve_vllm_dflash.sh --target 35b               # DFlash MoE
#    ./serve_vllm_dflash.sh --target 27b --baseline     # No DFlash
#    ./serve_vllm_dflash.sh --target 27b --port 8000
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

# Ensure venv bin (ninja, etc.) is in PATH for FlashInfer JIT subprocess calls
export PATH="/home/user/vllm_venv/bin:$PATH"

PYTHON="/home/user/vllm_venv/bin/python"

# Model registry
declare -A TARGETS=(
  ["27b"]="/home/user/models/Qwen3.6-27B"
  ["35b"]="/home/user/models/Qwen3.6-35B-A3B"
)
declare -A DRAFTS=(
  ["27b"]="/home/user/models/Qwen3.6-27B-DFlash"
  ["35b"]="/home/user/models/Qwen3.6-35B-A3B-DFlash"
)
declare -A NAMES=(
  ["27b"]="qwen3.6-27b-dflash"
  ["35b"]="qwen3.6-35b-a3b-dflash"
)

# Defaults
MODEL_KEY="27b"
PORT=8123
MODE="dflash"

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --target)  MODEL_KEY="$2"; shift 2 ;;
    --port)    PORT="$2"; shift 2 ;;
    --baseline) MODE="baseline"; shift ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

TARGET="${TARGETS[$MODEL_KEY]}"
DRAFT="${DRAFTS[$MODEL_KEY]}"
NAME="${NAMES[$MODEL_KEY]}"

echo "╔══════════════════════════════════════════════════╗"
echo "║  vLLM — ${MODEL_KEY} [${MODE}]  Port: ${PORT}"
echo "║  Target: ${TARGET}"
echo "║  Draft:  ${DRAFT}"
echo "╚══════════════════════════════════════════════════╝"

# NOTE: Do NOT use --disable-hybrid-kv-cache-manager.
# It breaks hybrid target models (Qwen3.6 GDN+FullAttention) because
# unify_hybrid_kv_cache_specs() cannot convert MambaSpec → FullAttentionSpec.
# Instead, DFlashProposer must be patched for multi-group support (pitfall #35).

if [ "$MODE" = "dflash" ]; then
  exec $PYTHON -m vllm.entrypoints.openai.api_server \
    --model "$TARGET" \
    --served-model-name "$NAME" \
    --speculative-config "{\"method\":\"dflash\",\"model\":\"$DRAFT\",\"num_speculative_tokens\":15}" \
    --attention-backend flash_attn \
    --max-num-batched-tokens 32768 \
    --gpu-memory-utilization 0.90 \
    --max-model-len 32768 \
    --port "$PORT" \
    --trust-remote-code \
    --dtype bfloat16
else
  exec $PYTHON -m vllm.entrypoints.openai.api_server \
    --model "$TARGET" \
    --served-model-name "${NAME%-dflash}" \
    --attention-backend flash_attn \
    --max-num-batched-tokens 32768 \
    --gpu-memory-utilization 0.90 \
    --max-model-len 32768 \
    --port "$PORT" \
    --trust-remote-code \
    --dtype bfloat16
fi
