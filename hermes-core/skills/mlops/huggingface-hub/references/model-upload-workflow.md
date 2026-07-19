# Model Upload Workflow: Quantized GGUF → HuggingFace

Full pattern for preparing and uploading a quantized GGUF model to HuggingFace Hub,
extracting benchmark data from a Hermes session.

## Step 1: Extract session data

```python
# Load the session
session_search(session_id="YYYYMMDD_HHMMSS_xxxxxx")

# Find benchmark results files on disk
search_files(pattern="*.json", path="/path/to/benchmark_results/", target="files")
read_file("/path/to/benchmark_results/model_variant.json")
```

## Step 2: Identify the best model

Compare across variants and baselines. Key metrics:
- **Perplexity (PPL):** lower is better, wikitext-2
- **HellaSwag:** higher is better (commonsense reasoning)
- **Winogrande, MMLU, ARC:** higher is better
- **Size (GB):** practical constraint
- **tg128 (t/s):** inference speed

## Step 3: Compute checksums

```bash
md5sum model.gguf
sha256sum model.gguf
```

## Step 4: Write model card (README.md)

### Required frontmatter

```yaml
---
license: apache-2.0
base_model: <original_hf_model_id>
library_name: llama.cpp
pipeline_tag: text-generation
tags: [quantization-method, base-model-family, ...]
quantized_by: <your_hf_username>
---
```

### Model card sections

1. **What makes this model special** — why it exists, what post-training was applied
2. **Why this quantization** — size vs quality tradeoff vs Q8_0 baseline
3. **Full benchmark table** — comparison with baselines (F16, Q8_0, other quants)
4. **Key takeaways** — per-metric analysis
5. **Quantization details** — method, profile, imatrix, calibration data
6. **Model architecture** — parameter table
7. **Usage** — llama.cpp example commands
8. **File information** — size + SHA256
9. **Credits** — base model, post-training, quantization tool

## Step 5: Authenticate and upload

### 5a. User: store token (do ONCE)

The user must run this from their terminal:

```bash
~/.hermes/hermes-agent/venv/bin/python3 -c "
from huggingface_hub import login
login(token='hf_...YOUR_TOKEN...')
print('Done')
"
```

This stores the token at `/home/user/.cache/huggingface/`.

### 5b. Hermes agent: create repo

```python
import json, urllib.request

TOKEN="hf_..." # will be populated from session context
data = json.dumps({"type": "model", "name": "model-name", "private": False}).encode()
req = urllib.request.Request(
    "https://huggingface.co/api/repos/create",
    data=data,
    headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(req) as resp:
    print(json.loads(resp.read()))
```

### 5c. Hermes agent: upload README and GGUF

Create a Python script and run it via the hermes-agent venv:

```python
import os
os.environ["HF_HOME"] = "/home/user/.cache/huggingface"
# CRITICAL: Hermes runs with HOME=/home/user/.hermes/home,
# so the token stored by step 5a is invisible without this override.

from huggingface_hub import HfApi

api = HfApi()
repo = "username/model-name"

# Upload README (fast)
with open("README_MODEL_CARD.md", "rb") as f:
    api.upload_file(path_or_fileobj=f.read(), path_in_repo="README.md",
                    repo_id=repo, repo_type="model",
                    commit_message="Add model card with benchmarks")

# Upload GGUF (slow — 21+ GB, run in background with notify_on_complete)
api.upload_file(path_or_fileobj="/path/to/model.gguf", path_in_repo="model.gguf",
                repo_id=repo, repo_type="model",
                commit_message="Add quantized GGUF")

# Verify
print(api.list_repo_files(repo))
```

Run it:
```bash
/home/user/.hermes/hermes-agent/venv/bin/python3 /tmp/upload_script.py
```

For large GGUF files, use `terminal(background=True, notify_on_complete=True, timeout=3600)`.

### Why not `hf upload`?

The `hf` CLI from Hermes tool calls cannot find stored tokens because:
- Hermes terminal/execute_code runs under `HOME=/home/user/.hermes/home`
- The token was stored at `/home/user/.cache/huggingface/` (real user home)
- `hf` CLI looks at `$HF_HOME` or `$HOME/.cache/huggingface/`
- And `hf` may fail with `ModuleNotFoundError` if run outside the correct Python env

The `HfApi.upload_file()` approach with `HF_HOME` override is the only reliable method from within Hermes.

## Token permission requirements

Fine-grained token needs:
- `repo.write` scoped to the target user namespace
- `repo.content.read`
- `repo.access.read`

Create at: https://huggingface.co/settings/tokens
Choose: Fine-grained → Repositories → Write access

## Example: SuperQwen APEX-I-Quality v3

Base: Qwen/Qwen-AgentWorld-35B-A3B
Post-training: Jiunsong/SuperQwen-AgentWorld-35B-A3B-abliterated (Obliteratus + Supertune)
Quantization: APEX I-Quality (imatrix-guided, Q6_K experts, Q8_0 shared)
Imatrix: 256K tokens of code/tools/math corpus
Result: 21 GB, PPL 5.870 (10% better than F16 baseline!), HellaSwag 82.5%

Repo: <GITHUB_USER>/SuperQwen-AgentWorld-35B-A3B-abliterated-APEX-I-Quality
File: SuperQwen-APEX-I-Quality-v3.gguf (22.8 GB)
SHA256: afb6a47af5301e45d7e1de792e76d5611acb9d909b2a6d2a69fd645a12052162
