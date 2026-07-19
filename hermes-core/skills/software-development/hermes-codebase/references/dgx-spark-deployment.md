# DGX Spark Deployment: llama.cpp + llama-swap + multi-model

NVIDIA DGX Spark (GB10 Grace Blackwell, 128GB unified memory, ARM64).
Deploy multiple LLM models simultaneously with model routing.

## Architecture

```
Hermes Agent → llama-swap :8080 → llama.cpp-dgx
                    ├── Nex-N2-mini Q8_0 (35GB, coding)
                    ├── Qwen3.6-35B Q8_0 (35GB, reasoning)
                    └── AgentWorld Q4_K_M (16GB, simulation)
```

## llama.cpp-dgx

Special fork for DGX Spark: `croll83/llama.cpp-dgx`
- Compiled with `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="121"` (Blackwell SM12.1)
- Supports NVFP4, TurboQuant, DFlash MTP
- Standard llama.cpp binaries run CPU-only on Spark

```bash
git clone https://github.com/croll83/llama.cpp-dgx
cd llama.cpp-dgx
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="121"
cmake --build build --config Release -j20
```

## llama-swap

Transparent proxy that dynamically loads/unloads models from llama.cpp.
Matrix mode keeps multiple models in memory simultaneously.

```yaml
# llama-swap.yaml
port: 8080
models:
  - name: nex
    port: 8081
    unload: false
    cmd: >
      llama-server -m model.gguf -ngl 99 -c 262144
      --cache-type-k q8_0 --cache-type-v q8_0
      --host 127.0.0.1 --port 8081

matrix:
  - models: ["nex", "qwen", "world"]
```

## KV-cache optimization

`--cache-type-k q8_0 --cache-type-v q8_0` quantizes KV-cache to 8-bit.
Reduces cache size by 50% with negligible quality loss.

For Qwen3.5-MoE (12 attention layers out of 48):
- 256K context FP16 KV-cache: ~6GB
- 256K context Q8 KV-cache: ~3GB

## Memory budget (128GB DGX Spark)

| Model | Quant | Size | KV-cache 256K | Total |
|-------|-------|------|---------------|-------|
| Nex-N2-mini | Q8_0 | 35GB | ~3GB (Q8) | ~41GB |
| Qwen3.6-35B | Q8_0 | 35GB | ~3GB (Q8) | ~41GB |
| AgentWorld | Q4_K_M | 20GB | ~2GB (64K Q8) | ~24GB |
| **Все три** | | **90GB** | **8GB** | **~98GB** |

## Model download

```bash
# Nex-N2-mini Q8_0
huggingface-cli download Frosty40/Nex-N2-mini-B70-Turbo-GGUF --include "*Q8_0*" --local-dir ~/models/

# Qwen3.6-35B Q8_0
huggingface-cli download unsloth/Qwen3.6-35B-A3B-GGUF --include "*Q8_0*" --local-dir ~/models/

# Qwen-AgentWorld Q4_K_M
huggingface-cli download unsloth/Qwen-AgentWorld-35B-A3B-GGUF --include "*Q4_K_M*" --local-dir ~/models/
```

## Hermes config

```yaml
# ~/.hermes/config.yaml
model:
  provider: custom:local
  model: nex
  api_base: http://localhost:8080/v1
  api_key: not-needed
```

Switch models: `/model custom:local:nex`, `/model custom:local:qwen`, `/model custom:local:world`

## Pitfalls

1. **llama-swap must be compiled for ARM64.** Standard amd64 binary won't run on DGX Spark.
2. **Matrix mode loads ALL models at once.** Memory must accommodate all models + KV-cache.
3. **Q8_0 KV-cache halves memory but doesn't hurt quality.** Always use it for Spark.
4. **MoE models are more sensitive to quantization than dense models of same total size.** 35B/3B MoE in Q3 shows noticeable degradation; prefer Q4_K_M or higher.
