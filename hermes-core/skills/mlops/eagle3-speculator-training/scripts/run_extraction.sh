#!/bin/bash
# Wrapper script: starts vLLM, waits for health, runs extraction, stops vLLM.
# Use for long-running extractions (50k+ samples, 6+ hours) to avoid
# process lifecycle issues with separate background terminals.
#
# Usage:
#   Edit variables below, then:
#   terminal(background=true, notify_on_complete=true) — bash run_extraction.sh
#
# The script is resumable: data_generation_offline.py skips samples
# that already have .safetensors files in the output dir.
set -euo pipefail

# ============ Configuration ============
MODEL=/path/to/target-model
TRAINING_DATA=/path/to/training_data
HIDDEN_STATES=/path/to/hidden_states
VLLM_VENV=/path/to/vllm_venv
SPEC_VENV=/path/to/speculators_venv
SPECULATORS=/path/to/speculators
MAX_SAMPLES=50000
CONCURRENCY=8
TARGET_LAYERS="3 19 39"
VLLM_PORT=8000
LOGDIR=/tmp/eagle3_bench
# =======================================

mkdir -p "$LOGDIR"
rm -f "$LOGDIR/EXTRACTION_DONE"

# Start vLLM
echo "[$(date '+%H:%M:%S')] Starting vLLM..."
MAX_JOBS=5 NVCC_THREADS=5 "$VLLM_VENV/bin/python" -m vllm.entrypoints.cli.main serve \
  "$MODEL" \
  --speculative_config "{\"method\": \"extract_hidden_states\", \"num_speculative_tokens\": 1, \"draft_model_config\": {\"hf_config\": {\"eagle_aux_hidden_state_layer_ids\": [$TARGET_LAYERS, 40]}}}" \
  --kv_transfer_config '{"kv_connector": "ExampleHiddenStatesConnector", "kv_role": "kv_producer", "kv_connector_extra_config": {"shared_storage_path": "/tmp/hidden_states"}}' \
  --dtype bfloat16 \
  --gpu-memory-utilization 0.65 \
  --max-model-len 8192 \
  --max-num-seqs 4 \
  --kv-cache-dtype fp8 \
  --no-enable-prefix-caching \
  --enforce-eager \
  --no-enable-chunked-prefill \
  --port "$VLLM_PORT" > "$LOGDIR/vllm.log" 2>&1 &
VLLM_PID=$!
echo "[$(date '+%H:%M:%S')] vLLM PID: $VLLM_PID"

# Wait for vLLM to be ready
echo "[$(date '+%H:%M:%S')] Waiting for vLLM..."
for i in $(seq 1 120); do
  if curl -sf "http://localhost:${VLLM_PORT}/health" > /dev/null 2>&1; then
    echo "[$(date '+%H:%M:%S')] vLLM ready!"
    break
  fi
  sleep 10
done

# Start data generation
echo "[$(date '+%H:%M:%S')] Starting hidden states extraction..."
cd "$SPECULATORS"
"$SPEC_VENV/bin/python" scripts/data_generation_offline.py \
  --preprocessed-data "$TRAINING_DATA" \
  --endpoint "http://localhost:${VLLM_PORT}/v1" \
  --output "$HIDDEN_STATES" \
  --max-samples "$MAX_SAMPLES" \
  --concurrency "$CONCURRENCY" \
  --validate-outputs > "$LOGDIR/extraction.log" 2>&1
EXTRACT_EXIT=$?

echo "[$(date '+%H:%M:%S')] Extraction exit code: $EXTRACT_EXIT"

# Stop vLLM
echo "[$(date '+%H:%M:%S')] Stopping vLLM..."
kill "$VLLM_PID" 2>/dev/null || true
sleep 5
kill -9 "$VLLM_PID" 2>/dev/null || true

# Count results
COUNT=$(ls "$HIDDEN_STATES" 2>/dev/null | wc -l)
echo "[$(date '+%H:%M:%S')] Hidden states generated: $COUNT"
echo "[$(date '+%H:%M:%S')] DONE" > "$LOGDIR/EXTRACTION_DONE"
