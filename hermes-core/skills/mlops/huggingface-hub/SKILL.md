---
name: huggingface-hub
description: "HuggingFace hf CLI: search/download/upload models, datasets."
version: 1.0.0
author: Hugging Face
license: MIT
tags: [huggingface, hf, models, datasets, hub, mlops]
platforms: [linux, macos, windows]
---

# Hugging Face CLI (`hf`) Reference Guide

The `hf` command is the modern command-line interface for interacting with the Hugging Face Hub, providing tools to manage repositories, models, datasets, and Spaces.

> **IMPORTANT:** The `hf` command replaces the now deprecated `huggingface-cli` command.

## Quick Start
*   **Installation:** `curl -LsSf https://hf.co/cli/install.sh | bash -s`
*   **Help:** Use `hf --help` to view all available functions and real-world examples.
*   **Authentication:** Recommended via `HF_TOKEN` environment variable or the `--token` flag.

### Authentication in Hermes Agent (critical pitfall)

**Do NOT pass HF tokens inline in Python strings or shell commands.** Hermes aggressively sanitizes tokens in `execute_code` and `terminal` tool calls — the token gets progressively stripped with each use, causing `SyntaxError: unterminated string literal` or `401 Unauthorized`.

**Why `hf auth login` doesn't work from the user's terminal:**
- `huggingface_hub` is installed only in `~/.hermes/home/.local/`, not system-wide
- The `hf` CLI binary at `~/.hermes/home/.local/bin/hf` fails with `ModuleNotFoundError: No module named 'huggingface_hub'` when run outside Hermes

**Correct workflow (user runs this ONCE in their terminal):**

```bash
~/.hermes/hermes-agent/venv/bin/python3 -c "
from huggingface_hub import login
login(token='hf_...YOUR_TOKEN...')
print('Done')
"
```

This stores the token under `/home/user/.cache/huggingface/`.

**Correct workflow (Hermes agent uses this for all subsequent calls):**

```python
import os
os.environ["HF_HOME"] = "/home/user/.cache/huggingface"
# ^^^ CRITICAL: Hermes tool calls run under HOME=/home/user/.hermes/home,
# so we must explicitly point to the real user's HF cache.

from huggingface_hub import HfApi
api = HfApi()
api.whoami()  # verify
```

**Why `HF_HOME` override is needed:** Hermes `terminal` and `execute_code` run with `HOME=/home/user/.hermes/home`. The token stored by the user's `login()` call goes to `/home/user/.cache/huggingface/`. Without the override, `HfApi()` looks in `/home/user/.hermes/home/.cache/huggingface/` and finds nothing.

**Do NOT use `hf upload` or `hf` CLI from Hermes tool calls** — it can't find the token. Use `HfApi.upload_file()` from Python instead (see Upload section below).

### Uploading Large Models (GGUF)

When uploading quantized GGUF files to HuggingFace **from within Hermes tool calls:**

1. **Create the repo** via Python API (first create requires explicit `repo.create` — can be done via `urllib` POST to `/api/repos/create`)
2. **Upload the README/model card** separately as a small commit using `HfApi.upload_file()`
3. **Upload the GGUF** using `HfApi.upload_file()` which handles chunked uploads for large files
4. **Verify** with `api.list_repo_files()`

**Complete Hermes-safe upload pattern:**

```python
import os
os.environ["HF_HOME"] = "/home/user/.cache/huggingface"  # CRITICAL for Hermes

from huggingface_hub import HfApi
api = HfApi()
repo = "username/model-name"

# Upload model card
with open("README.md", "rb") as f:
    api.upload_file(
        path_or_fileobj=f.read(),
        path_in_repo="README.md",
        repo_id=repo,
        repo_type="model",
        commit_message="Add model card"
    )

# Upload GGUF (large file — set long timeout for terminal tool)
api.upload_file(
    path_or_fileobj="/path/to/model.gguf",
    path_in_repo="model.gguf",
    repo_id=repo,
    repo_type="model",
    commit_message="Add quantized GGUF"
)
```

**Run this script through the hermes-agent venv:**
```bash
/home/user/.hermes/hermes-agent/venv/bin/python3 /tmp/upload_script.py
```

**For background uploads of large files (21+ GB):** use `terminal(background=True, notify_on_complete=True, timeout=3600)` — the upload may take 30-60+ minutes depending on connection speed.

See `references/model-upload-workflow.md` for the full benchmark-extraction and model-card-authoring pattern.
See `references/large-model-download-workflow.md` for resilient download-resume workflow with process management and cache cleanup.

## Pitfalls

- **Stale `.incomplete` cache files waste 10-25 GB.** After `hf download` completes,
  old `.incomplete` files from failed attempts remain in `.cache/huggingface/download/`.
  Always run `rm -rf .cache/` after verifying all safetensors are finalized.
- **`process(action="list")` only shows current-session processes.** To find stale
  `hf download` processes from past sessions, use `ps aux | grep "hf download"`.
- **`hf download` auto-resumes from `.incomplete`** — no `--resume` flag needed.
  Just re-run the identical command after a crash/SIGTERM.

---

## Core Commands

### General Operations
*   `hf download REPO_ID`: Download files from the Hub.
*   `hf upload REPO_ID`: Upload files/folders (recommended for single-commit).
*   `hf upload-large-folder REPO_ID LOCAL_PATH`: Recommended for resumable uploads of large directories.
*   `hf sync`: Sync files between a local directory and a bucket.
*   `hf env` / `hf version`: View environment and version details.

### Authentication (`hf auth`)
*   `login` / `logout`: Manage sessions using tokens from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).
*   `list` / `switch`: Manage and toggle between multiple stored access tokens.
*   `whoami`: Identify the currently logged-in account.

### Repository Management (`hf repos`)
*   `create` / `delete`: Create or permanently remove repositories.
*   `duplicate`: Clone a model, dataset, or Space to a new ID.
*   `move`: Transfer a repository between namespaces.
*   `branch` / `tag`: Manage Git-like references.
*   `delete-files`: Remove specific files using patterns.

---

## Specialized Hub Interactions

### Datasets & Models
*   **Datasets:** `hf datasets list`, `info`, and `parquet` (list parquet URLs).
*   **SQL Queries:** `hf datasets sql SQL` — Execute raw SQL via DuckDB against dataset parquet URLs.
*   **Models:** `hf models list` and `info`.
*   **Papers:** `hf papers list` — View daily papers.

### Discussions & Pull Requests (`hf discussions`)
*   Manage the lifecycle of Hub contributions: `list`, `create`, `info`, `comment`, `close`, `reopen`, and `rename`.
*   `diff`: View changes in a PR.
*   `merge`: Finalize pull requests.

### Infrastructure & Compute
*   **Endpoints:** Deploy and manage Inference Endpoints (`deploy`, `pause`, `resume`, `scale-to-zero`, `catalog`).
*   **Jobs:** Run compute tasks on HF infrastructure. Includes `hf jobs uv` for running Python scripts with inline dependencies and `stats` for resource monitoring.
*   **Spaces:** Manage interactive apps. Includes `dev-mode` and `hot-reload` for Python files without full restarts.

### Storage & Automation
*   **Buckets:** Full S3-like bucket management (`create`, `cp`, `mv`, `rm`, `sync`).
*   **Cache:** Manage local storage with `list`, `prune` (remove detached revisions), and `verify` (checksum checks).
*   **Webhooks:** Automate workflows by managing Hub webhooks (`create`, `watch`, `enable`/`disable`).
*   **Collections:** Organize Hub items into collections (`add-item`, `update`, `list`).

---

### Fetching Model Cards for Research (fast, no browser)

When researching models on HuggingFace, fetch README.md directly via raw URL — much faster
than browser and avoids timeouts on heavy HF pages:

```bash
# Get model card / README
curl -sL --max-time 30 "https://huggingface.co/{org}/{model}/raw/main/README.md" | head -200

# List all models by an organization (grep from HTML)
curl -sL --max-time 30 "https://huggingface.co/{org}" 2>&1 | grep -oE '{org}/[A-Za-z0-9_.-]+' | sort -u

# For arxiv papers, strip HTML tags and grep for benchmarks
curl -sL --max-time 30 "https://arxiv.org/html/{paper_id}v1" 2>&1 | sed 's/<[^>]*>//g' | grep -iE "MMLU|benchmark|score"
```

This works for model cards, config.json, and any file in the repo. Use `head -N` to limit
output. For llm-stats.com and similar JS-heavy sites, the HTML is not useful via curl —
use `web_search` + `web_extract` instead, or the browser tool.

### Large Model Downloads

For multi-gigabyte safetensors downloads (10+ GB), use `hf download --local-dir` with
the background process workflow documented in `references/large-model-download-workflow.md`.
Key points:

- `hf download` **auto-resumes** from `.incomplete` files — just re-run the same command
- Kill stale duplicate processes with `ps aux | grep "hf download"` before restarting
- Clean up `.cache/` after completion to reclaim 10-25 GB of stale incomplete files
- Verify: count safetensors shards, check all are ~5 GB (last one smaller)

### Global Flags
*   `--format json`: Produces machine-readable output for automation.
*   `-q` / `--quiet`: Limits output to IDs only.

### Extensions & Skills
*   **Extensions:** Extend CLI functionality via GitHub repositories using `hf extensions install REPO_ID`.
*   **Skills:** Manage AI assistant skills with `hf skills add`.
