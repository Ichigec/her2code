# DiffusionGemma OpenAI-Compatible API Wrapper

Wrap `llama-diffusion-cli` (PR #24423) as an HTTP server with OpenAI-compatible
`/v1/chat/completions` and `/v1/models` endpoints. This is the only way to use
diffusion models with LiteLLM or any OpenAI-compatible client — standard
`llama-server` loads the model but fails on inference.

## Architecture

```
Client → HTTP :8646 → FastAPI → llama-diffusion-cli subprocess → GGUF model
         (OpenAI API)       (async, semaphore-locked)
```

Single-inference lock prevents VRAM exhaustion (48 GB model).

## Dependencies

```bash
pip install fastapi uvicorn
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DG_MODEL_PATH` | `.../edwixx__diffusiongemma-...-FP16.gguf` | Path to GGUF |
| `DG_BINARY` | `/tmp/llama-diffusion-build/build/bin/llama-diffusion-cli` | Binary path |
| `DG_NGL` | `99` | GPU layers (all on GPU) |
| `DG_CTX_SIZE` | `65536` | Context size |
| `DG_PORT` | `8646` | Listen port |
| `DG_MODEL_NAME` | `diffusion-gemma-26b` | Model ID in API |
| `DG_DEFAULT_STEPS` | `64` | Default diffusion steps |
| `DG_DEFAULT_MAX_TOKENS` | `256` | Default max tokens |

## Startup

```bash
/home/user/.hermes/hermes-agent/venv/bin/python3 /home/user/dev/Opencode/diffusion-server.py
```

## API

```bash
# Health
curl http://localhost:8646/health

# Models
curl http://localhost:8646/v1/models

# Chat completion
curl -s http://localhost:8646/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "diffusion-gemma-26b",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 50,
    "temperature": 0.8,
    "diffusion_steps": 32
  }'
```

Performance: ~0.5s per diffusion step (32 steps = ~17s on Jetson GB10).

## LiteLLM Integration

Add to LiteLLM `config.yaml`:

```yaml
  - model_name: "diffusion-gemma-26b-heretic"
    litellm_params:
      model: "openai/diffusion-gemma-26b"
      api_base: "http://host.docker.internal:8646/v1"
      api_key: "not-needed"
```

Then use: `/model custom:litellm:diffusion-gemma-26b-heretic`

## Pitfalls

- **Must be FP16/BF16** — quantized GGUFs may not work with the diffusion loop
- **No streaming** — the model generates entire response at once (not autoregressive)
- **Single-inference only** — semaphore-locked to prevent VRAM exhaustion
- **Watchdog needed** — the Python process may die; use a cron watchdog like voice proxy
