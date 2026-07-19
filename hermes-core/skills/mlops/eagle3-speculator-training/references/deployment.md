# Deployment: HuggingFace Upload + LiteLLM + Hermes Integration

## 1. Upload Speculator to HuggingFace

### Prepare clean checkpoint

Only upload inference files — skip optimizer state, scheduler state, training state:

```bash
mkdir -p /tmp/eagle3_upload
cp /path/to/checkpoints/checkpoint_best/config.json /tmp/eagle3_upload/
cp /path/to/checkpoints/checkpoint_best/config.py /tmp/eagle3_upload/
cp /path/to/checkpoints/checkpoint_best/model.safetensors /tmp/eagle3_upload/
```

### Create README.md model card

```markdown
---
library_name: speculators
tags:
  - eagle3
  - speculative-decoding
  - vllm
  - qwen3.5
  - moe
license: mit
---

# EAGLE3 Speculator for [Model Name]

Trained using [speculators](https://github.com/vllm-project/speculators) library.

## Validation Metrics

| Position | Accuracy | Loss |
|----------|----------|------|
| 0 | 71.4% | 0.62 |
| 1 | 42.7% | 1.40 |
| 2 | 25.7% | 2.02 |

## Usage with vLLM

```bash
vllm serve /path/to/verifier-model \
  --speculative_config '{"method": "eagle3", "model": "USERNAME/model-name-eagle3-speculator", "num_speculative_tokens": 3}' \
  --dtype bfloat16 --gpu-memory-utilization 0.65 --max-model-len 8192
```
```

### Upload

```python
from huggingface_hub import HfApi, create_repo
import os

token = open(os.path.expanduser("~/.cache/huggingface/token")).read().strip()
api = HfApi(token=token)
repo_id = "YOUR_USERNAME/model-name-eagle3-speculator"

create_repo(repo_id, repo_type="model", token=token, exist_ok=True)
api.upload_folder(
    folder_path="/tmp/eagle3_upload",
    repo_id=repo_id,
    repo_type="model",
    token=token,
)
print(f"Upload complete: https://huggingface.co/{repo_id}")
```

Upload time: ~80 seconds for 1.2 GB model on a 100 Mbit connection.

## 2. LiteLLM Integration

### Add model to LiteLLM config

File: `docker/litellm/config.yaml` (relative to the compose file directory)

```yaml
  - model_name: "agents-a1-eagle3"
    litellm_params:
      model: "openai/agents-a1-eagle3"
      api_base: "os.environ/VLLM_API_BASE"
      api_key: "os.environ/VLLM_API_KEY"
      request_timeout: 600
      max_retries: 0
    model_info:
      mode: chat
```

Key details:
- `model: "openai/agents-a1-eagle3"` — LiteLLM sends this as the model name to vLLM. vLLM must be started with `--served-model-name agents-a1-eagle3` to match.
- `api_base: "os.environ/VLLM_API_BASE"` — resolves to `http://host.docker.internal:8000/v1` (vLLM on host, LiteLLM in Docker)
- `request_timeout: 600` — needed for first request (JIT compilation + CUDAgraph capture)
- `max_retries: 0` — don't retry on failure (vLLM is either up or down)

### Restart LiteLLM

```bash
cd /path/to/compose/dir
docker compose -f compose.phoenix.yml restart litellm
```

### Verify

```bash
curl -s http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-local" \
  -d '{
    "model": "agents-a1-eagle3",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 64
  }'
```

## 3. Hermes Integration

### Add model to Hermes config

```bash
# Get current models list, add the new one
hermes config set providers.local.models '["nex-n2-mini","qwen3.6-35b","agents-a1-eagle3"]'
```

Note: `hermes config set` replaces the entire list, so include all existing models.

### Use with Hermes

```bash
hermes chat --model agents-a1-eagle3 --provider local
```

## 4. vLLM Serving Command (Production)

```bash
source /path/to/vllm_venv/bin/activate

python -m vllm.entrypoints.cli.main serve /path/to/target-model \
  --speculative_config '{"method": "eagle3", "model": "USERNAME/model-name-eagle3-speculator", "num_speculative_tokens": 3}' \
  --dtype bfloat16 \
  --gpu-memory-utilization 0.65 \
  --max-model-len 8192 \
  --max-num-seqs 4 \
  --served-model-name agents-a1-eagle3 \
  --port 8000
```

Important flags for serving:
- NO `--enforce-eager` — CUDAgraph gives ~23% throughput boost
- NO `--kv-cache-dtype fp8` — not needed for serving, only for extraction
- `--served-model-name agents-a1-eagle3` — must match LiteLLM model_name
- vLLM downloads the speculator from HuggingFace on first launch (cached after)

## 5. Benchmarking

Use the benchmark script at `scripts/benchmark.py`:

```bash
# Baseline (no speculator) — launch vLLM without --speculative_config
python scripts/benchmark.py baseline

# Kill baseline, launch with speculator
python scripts/benchmark.py speculator
```

The script sends a warmup request (JIT/CUDAgraph), then 3 timed requests, then extracts spec decoding metrics from `/metrics`.

### Key metrics to compare

| Metric | Source | What to look for |
|--------|--------|------------------|
| Throughput | `tok/s = tokens / elapsed` | Speculator should be 1.3-1.5x faster |
| Acceptance rate | vLLM logs: `SpecDecoding metrics` | Position 0: 60-70% is good for 5k samples |
| Mean acceptance length | vLLM logs | 2.0+ is good for 3 speculative tokens |
| Quality | Compare output text | Semantically equivalent, not bit-identical |
