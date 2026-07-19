#!/bin/bash
# SGLang + DFlash serve script for Qwen3.6 hybrid GDN targets
# This is the ONLY working DFlash deployment path for Qwen3.6-27B / 35B-A3B
# (vLLM DFlash produces 0% acceptance on hybrid GDN targets — see pitfall #37)
#
# Verified Jul 14 2026 on DGX Spark (GB10, SM 12.1)
# Results: 10-15 tok/s, 20-40% acceptance, 3.5-6.9 mean accept length
#
# Requirements:
#   - SGLang from PR #23000: pip install "git+https://github.com/sgl-project/sglang.git@refs/pull/23000/head#subdirectory=python"
#   - Rust compiler: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
#   - protoc: export PROTOC="$(python -c 'import torch,os;print(os.path.join(os.path.dirname(torch.__file__),"bin","protoc"))')"
#
# Usage:
#   bash serve_sglang_dflash.sh [PORT]
#   PORT defaults to 8123

set -euo pipefail

# --- CONFIG ---
SGLANG_VENV="${SGLANG_VENV:-$HOME/sglang_venv}"
MODEL="${MODEL:-/home/user/models/Qwen3.6-27B}"
DRAFT="${DRAFT:-/home/user/models/Qwen3.6-27B-DFlash}"
PORT="${1:-8123}"

# --- ACTIVATE VENV ---
source "$SGLANG_VENV/bin/activate"
source "$HOME/.cargo/env" 2>/dev/null || true
export PATH="$SGLANG_VENV/bin:$PATH"

# --- LAUNCH ---
echo "Starting SGLang DFlash on port $PORT"
echo "  Target: $MODEL"
echo "  Draft:  $DRAFT"

exec python -m sglang.launch_server \
    --model-path "$MODEL" \
    --speculative-algorithm DFLASH \
    --speculative-draft-model-path "$DRAFT" \
    --speculative-num-draft-tokens 16 \
    --tp-size 1 \
    --attention-backend flashinfer \
    --mem-fraction-static 0.75 \
    --mamba-scheduler-strategy extra_buffer \
    --trust-remote-code \
    --port "$PORT" \
    --host 0.0.0.0

# --- MONITORING ---
# Logs: tail -f /tmp/sglang_dflash.log (or wherever stdout is redirected)
# Acceptance metrics in logs: grep "accept len" /tmp/sglang_dflash.log
#   Look for: "Decode batch ... accept len: 4.38, accept rate: 0.23, gen throughput (token/s): 10.53"
# Speed test:
#   curl -s http://localhost:$PORT/v1/chat/completions \
#     -H "Content-Type: application/json" \
#     -d '{"model":"<MODEL_PATH>","messages":[{"role":"user","content":"Hello"}],"max_tokens":100}' | python3 -m json.tool
