#!/bin/bash
# DiffusionGemma server startup + health-check watchdog
# Usage: bash start-diffusion.sh
#
# Expects these env vars (or edit inline):
#   DG_MODEL_PATH  - path to .gguf
#   DG_BINARY      - path to llama-diffusion-cli
#   DG_PORT        - HTTP port (default: 8646)

BINARY="${DG_BINARY:-/tmp/llama-diffusion-build/build/bin/llama-diffusion-cli}"
MODEL="${DG_MODEL_PATH}"
VENV_PYTHON="${DG_VENV_PYTHON:-/home/user/.hermes/hermes-agent/venv/bin/python3}"
SERVER_SCRIPT="$(dirname "$0")/diffusion-server.py"
LOG="${DG_LOG:-/tmp/diffusion-server.log}"
PORT="${DG_PORT:-8646}"

export DG_MODEL_PATH="$MODEL"
export DG_BINARY="$BINARY"
export DG_NGL="${DG_NGL:-99}"
export DG_CTX_SIZE="${DG_CTX_SIZE:-65536}"
export DG_PORT="$PORT"
export DG_MODEL_NAME="${DG_MODEL_NAME:-diffusion-gemma-26b}"
export DG_DEFAULT_STEPS="${DG_DEFAULT_STEPS:-64}"

echo "[$(date)] Starting DiffusionGemma server on :$PORT..." | tee -a "$LOG"
$VENV_PYTHON $SERVER_SCRIPT >> "$LOG" 2>&1 &
PID=$!
echo "PID: $PID" | tee -a "$LOG"

# Wait for startup
for i in $(seq 1 30); do
    sleep 2
    if curl -s http://localhost:$PORT/health > /dev/null 2>&1; then
        echo "[$(date)] Server ready (PID $PID)" | tee -a "$LOG"
        exit 0
    fi
done

echo "[$(date)] FAILED to start after 60s" | tee -a "$LOG"
kill $PID 2>/dev/null
exit 1
