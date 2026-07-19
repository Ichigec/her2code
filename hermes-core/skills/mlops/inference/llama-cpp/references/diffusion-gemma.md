# DiffusionGemma — Special llama.cpp Fork

DiffusionGemma uses a **block-diffusion architecture** (Google DeepMind) — fundamentally
different from autoregressive transformers. Standard `llama.cpp` cannot load these models.

## The Error

```
error loading model: unknown model architecture: 'diffusion-gemma'
```

## The Fix: PR #24423 Fork

Support exists only in [PR #24423](https://github.com/ggml-org/llama.cpp/pull/24423)
(unmerged as of June 2026). Tracked by [WayneTechLab/llama-diffusion-gemma](https://github.com/WayneTechLab/llama-diffusion-gemma).

### Build from existing llama.cpp repo

```bash
cd /path/to/llama.cpp
git fetch origin pull/24423/head:diffusion-gemma
git checkout diffusion-gemma
cmake -B build -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=ON
cmake --build build -j$(nproc) --target llama-diffusion-cli
cmake --build build -j$(nproc) --target llama-diffusion-gemma-server
```

### Or clone fresh

```bash
git clone --depth 1 https://github.com/ggml-org/llama.cpp
cd llama.cpp
git fetch origin pull/24423/head:diffusion-gemma
git checkout diffusion-gemma
# ... same cmake steps
```

### Build pitfalls

**FETCH_HEAD permission error**: If `git fetch` fails with `Permission denied` on `.git/FETCH_HEAD`,
it's likely root-owned from a previous `sudo` build. Fix:
```bash
rm -f .git/FETCH_HEAD
git fetch origin pull/24423/head:diffusion-gemma
```

**Checkout permission errors** (e.g. `tools/ui/...`): these are leftover root-owned files from
a previous build. Workaround: clone fresh to `/tmp` and build there instead:
```bash
cd /tmp && git clone --depth 1 https://github.com/ggml-org/llama.cpp llama-diffusion-build
cd llama-diffusion-build
git fetch origin pull/24423/head:diffusion-gemma
git checkout diffusion-gemma
```

## Binary Targets

| Binary | Purpose | HTTP Server? |
|---|---|---|
| `llama-diffusion-cli` | Interactive chat (like `llama-cli`) | No |
| `llama-diffusion-gemma-server` | Low-level logits server (stdin/stdout binary protocol) | **No** |
| `llama-diffusion-gemma-visual-server` | Visual entropy-bound decoder (streams per-step frames) | No |

## CRITICAL: NOT an HTTP Server

`llama-diffusion-gemma-server` is **not** a drop-in replacement for `llama-server`.
It communicates via a binary protocol over stdin/stdout. A Python driver is needed
to run the block-diffusion loop and expose an OpenAI-compatible API.

The WayneTechLab repo provides a Python wrapper (`diffusion-server.py`) that wraps
`llama-diffusion-cli` into an Ollama-compatible API on port 11435.

### PR's `llama-server`: loads but CANNOT infer

The PR also builds the standard `llama-server` target (`cmake --build build --target llama-server`).
This binary **can load** the diffusion model and exposes `/v1/models` successfully,
but `/v1/chat/completions` fails with:

```
"error": "the current context does not logits computation. skipping"
```

The diffusion architecture requires the dedicated `llama-diffusion-cli` loop — the
standard autoregressive chat completion path does not work even when the model loads.

## Diffusion-Specific CLI Flags

| Flag | Purpose | Default |
|---|---|---|
| `--diffusion-steps N` | Diffusion denoising steps (less = faster/worse) | 128 |
| `--diffusion-blocks N` | Max block-autoregressive blocks | 1 |
| `--diffusion-visual` | Show progressive generation in terminal | off |
| `--diffusion-visual-progress` | Show step progress bar | off |
| `--diffusion-visual-interval N` | Redraw every Nth step | — |

## Run Example

```bash
llama-diffusion-cli \
  -m /path/to/diffusiongemma.gguf \
  --n-gpu-layers 99 \
  --ctx-size 65536 \
  --diffusion-steps 128 \
  --diffusion-blocks 4 \
  --temp 0.8 \
  -p "Your prompt here"
```

**Context size notes** (tested on Jetson GB10 with 124 GB VRAM):
- `n_ctx_train` = 262144 (same as autoregressive Gemma)
- At FP16 (48 GB weights on GPU), ctx 65536 uses ~24 GB additional for KV cache — fits alongside a running Qwen model (~18 GB KV)
- ctx 32768 uses ~12 GB KV cache — safe default for tight VRAM
- ctx 262144 would need ~98 GB KV cache alone — won't fit with another model loaded

## Architecture Notes

- **Not autoregressive** — generates entire blocks in parallel via diffusion
- **Self-conditioning**: each step conditions on the previous step's logits
- **Non-causal attention**: `llama_set_causal_attn(ctx, false)`
- **No KV cache** in standard mode — whole sequence in one ubatch (`DG_KVCACHE=1` opt-in)
- The model must be **FP16/BF16** — quantized GGUFs may not work with the diffusion loop
- Sizes: 26B-A4B MoE ≈ 48 GB FP16 on disk
