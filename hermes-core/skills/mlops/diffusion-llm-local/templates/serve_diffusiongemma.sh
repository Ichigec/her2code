#!/bin/bash
# serve_diffusiongemma.sh — vLLM server for DiffusionGemma 26B-A4B (abliterated, BF16)
# Target: NVIDIA DGX Spark (GB10, aarch64, 128GB unified memory)
# Model: Umranz/diffusiongemma-26B-A4B-it-abliteration (ARA, 4/100 refusals, KL=0.11)
#
# BF16 performance on DGX Spark (GB10) — measured 2026-07-14:
#   bench_diffusiongemma.py results:
#     short (8 tok):     6.8 tok/s  — canvas barely filled
#     medium (128 tok): 28.2 tok/s  — partial canvas
#     full canvas (256): 52.6 tok/s  — 7.7× faster than short
#     multi-canvas (512): 51.7 tok/s  — consistent per-canvas
#     code gen (512):   91.1 tok/s  — best case for agent tasks
#
# Speed optimizations (BF16, no quantization):
#   1. GPU_MEM_UTIL=0.60 — GB10 unified memory, 0.70+ starves system RAM → swap thrash
#   2. VLLM_USE_V2_MODEL_RUNNER=1 — required for diffusion model runner path
#   3. TRITON_ATTN backend — optimal for bidirectional attention on GB10
#   4. CUDA graphs ON (no --enforce-eager) — FULL_AND_PIECEWISE compilation
#   5. max-num-batched-tokens=8192 — chunked prefill batching
#   6. override-generation-config max_new_tokens=null — remove default 256 cap
#   7. Per-request enable_thinking=false for speed (thinking tokens counted in output)
#   8. Long outputs fill canvas → higher throughput (diffusion is per-canvas, not per-token)

set -euo pipefail

# ─── Config ──────────────────────────────────────────────────────────────────
MODEL_DIR="/home/user/models/diffusiongemma-26B-A4B-it-abliteration"
DOCKER_IMAGE="vllm/vllm-openai:gemma"
CONTAINER_NAME="diffusiongemma"
PORT=8000

# Optimal parameters (researched for DGX Spark GB10, BF16)
MAX_MODEL_LEN=${MAX_MODEL_LEN:-262144}         # 262144 — full context window
MAX_NUM_SEQS=${MAX_NUM_SEQS:-4}               # DiffusionGemma hard limit (state buffers)
GPU_MEM_UTIL=${GPU_MEM_UTIL:-0.60}            # 0.60 for BF16 on GB10 (0.70+ = swap thrash)
MAX_NUM_BATCHED_TOKENS=${MAX_NUM_BATCHED_TOKENS:-8192}  # 8192 for chunked prefill batching

# Diffusion-specific config (from model's generation_config.json)
CANVAS_LENGTH=${CANVAS_LENGTH:-256}           # 256-token parallel generation canvas
MAX_DENOISING_STEPS=${MAX_DENOISING_STEPS:-48}  # 48 denoising iterations

# ─── Pre-flight: memory check ────────────────────────────────────────────────
AVAIL_GB=$(awk '/MemAvailable/ {printf "%.0f", $2/1024/1024}' /proc/meminfo)
echo "Available memory: ${AVAIL_GB} GB (need ~52 GB for 26B bf16 + KV cache)"

if [ "$AVAIL_GB" -lt 52 ]; then
    echo ""
    echo "⚠️  Not enough memory! ${AVAIL_GB} GB available, need ~52 GB."
    echo ""
    echo "Running processes consuming memory:"
    ps aux --sort=-%mem | head -10 | awk '{printf "  PID %s  RSS %.1fGB  %s\n", $2, $6/1024/1024, $11}'
    exit 1
fi

# ─── Pre-flight: temperature check (DGX Spark overheats at ~95C) ─────────────
GPU_TEMP=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null || echo "0")
if [ "$GPU_TEMP" -gt 85 ] 2>/dev/null; then
    echo ""
    echo "⚠️  GPU temperature is ${GPU_TEMP}°C! DGX Spark throttles at ~95°C."
    read -p "Continue anyway? (y/N) " -r
    [[ $REPLY =~ ^[Yy]$ ]] || exit 1
else
    echo "GPU temperature: ${GPU_TEMP}°C (OK, throttle limit ~95°C)"
fi

# ─── Pull correct image (gemma tag has DiffusionGemma support) ───────────────
echo "Checking Docker image..."
if ! docker image inspect "$DOCKER_IMAGE" >/dev/null 2>&1; then
    echo "Pulling $DOCKER_IMAGE (has DiffusionGemma support)..."
    docker pull "$DOCKER_IMAGE"
else
    echo "✓ Image $DOCKER_IMAGE found locally"
fi

# Verify diffusion_gemma support in the image
if ! docker run --rm --entrypoint python3 "$DOCKER_IMAGE" \
    -c "import vllm.model_executor.models.diffusion_gemma" 2>/dev/null; then
    echo "❌ Image $DOCKER_IMAGE lacks DiffusionGemma support!"
    echo "   Trying to pull latest gemma tag..."
    docker pull "$DOCKER_IMAGE"
fi

# ─── Stop existing container ─────────────────────────────────────────────────
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Removing existing container..."
    docker rm -f "$CONTAINER_NAME"
fi

# ─── Launch ──────────────────────────────────────────────────────────────────
echo ""
echo "Starting DiffusionGemma vLLM server (BF16, full precision) on port $PORT..."
echo ""
echo "  Dtype:              bfloat16 (full precision, no quantization)"
echo "  Max length:         $MAX_MODEL_LEN tokens"
echo "  Max seqs:           $MAX_NUM_SEQS (diffusion state buffer limit)"
echo "  GPU util:           $GPU_MEM_UTIL (GB10 unified memory safe zone)"
echo "  Canvas:             $CANVAS_LENGTH tokens × $MAX_DENOISING_STEPS steps"
echo "  Attention backend:  TRITON_ATTN (bidirectional)"
echo "  CUDA graphs:        ON (FULL_AND_PIECEWISE)"
echo ""

docker run -itd \
    --name "$CONTAINER_NAME" \
    --ipc=host \
    --network host \
    --gpus all \
    -e VLLM_USE_V2_MODEL_RUNNER=1 \
    -v "${MODEL_DIR}:/models/diffusiongemma:ro" \
    "$DOCKER_IMAGE" \
    --model /models/diffusiongemma \
    --served-model-name diffusiongemma-abliterated \
    --host 0.0.0.0 \
    --port "$PORT" \
    --trust-remote-code \
    --dtype auto \
    --max-model-len "$MAX_MODEL_LEN" \
    --max-num-seqs "$MAX_NUM_SEQS" \
    --max-num-batched-tokens "$MAX_NUM_BATCHED_TOKENS" \
    --gpu-memory-utilization "$GPU_MEM_UTIL" \
    --diffusion-config "{\"canvas_length\": $CANVAS_LENGTH, \"max_denoising_steps\": $MAX_DENOISING_STEPS}" \
    --attention-backend TRITON_ATTN \
    --enable-auto-tool-choice \
    --tool-call-parser gemma4 \
    --reasoning-parser gemma4 \
    --override-generation-config '{"max_new_tokens": null}' \
    --default-chat-template-kwargs '{"enable_thinking": true}' \
    --mm-processor-kwargs '{"max_soft_tokens": 1120}' \
    --limit-mm-per-prompt '{"image": 7}' \
    -tp 1

echo ""
echo "✓ Container started: $CONTAINER_NAME"
echo ""
echo "Watch logs:    docker logs -f $CONTAINER_NAME"
echo "Stop server:   docker rm -f $CONTAINER_NAME"
echo "Test request:  python3 scripts/bench_diffusiongemma.py"
echo ""

# Wait for server to be ready
for i in $(seq 1 120); do
    if curl -sf "http://localhost:${PORT}/health" >/dev/null 2>&1; then
        echo "✓ Server ready at http://localhost:${PORT}"
        exit 0
    fi
    if [ $((i % 10)) -eq 0 ]; then
        echo "  ...still loading (${i}s elapsed)"
    fi
    sleep 5
done

echo "⚠️  Server not ready after 600s. Check logs: docker logs $CONTAINER_NAME"
exit 1
