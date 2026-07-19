# MoE KV Cache Sizing

## Qwen3.5/Qwen3.6 MoE Architecture

Qwen3.5/3.6 MoE models (35B-A3B, 235B-A22B, etc.) use a hybrid architecture:
- **48 total layers**
- **12 attention layers** (Gated Attention) — these have traditional KV cache
- **36 DeltaNet layers** (Gated DeltaNet linear-attention) — these use a fixed-size recurrent state (orders of magnitude smaller than KV cache)

## KV Cache Calculation

Traditional attention KV cache size:
```
KV_bytes = 2 × n_attn_layers × n_kv_heads × head_dim × context_length × bytes_per_element
```

For Qwen3.5-35B-A3B (verified against llama.cpp memory reports):
- n_attn_layers = 12
- n_kv_heads = 4
- head_dim = 128
- bytes_per_element = 1 (Q8_0)

```
KV_cache(256K) = 2 × 12 × 4 × 128 × 262144 × 1 = 3,221,225,472 bytes ≈ 3.0 GB
KV_cache(128K) = 2 × 12 × 4 × 128 × 131072 × 1 = 1,610,612,736 bytes ≈ 1.5 GB
KV_cache(64K)  = 2 × 12 × 4 × 128 × 65536 × 1  = 805,306,368 bytes  ≈ 0.8 GB
```

## Common Mistake

The naive estimate using ALL 48 layers would give:
```
48 layers × ... = 12.9 GB for 256K  ← WRONG (4× overestimate)
```

This is because DeltaNet layers don't store per-token KV pairs — they maintain a compact recurrent state matrix (typically ~d_model × d_model, independent of context length).

## Verified Memory Budget

For Qwen3.5 MoE 35B/3B on DGX Spark with Q8_0 KV cache:

| Context | KV Cache | Notes |
|:-------:|:--------:|-------|
| 64K | ~0.8 GB | Minimal overhead |
| 128K | ~1.5 GB | Comfortable for most uses |
| 256K | ~3.0 GB | Native max context |

Add ~1 GB per llama-server instance for CUDA runtime, NCCL, and other overhead.

## Verified Q8_0 File Size

SuperQwen-AgentWorld-35B-A3B-abliterated Q8_0 (McG-221):
- `total` (tensors): 34,660,610,688 bytes (34.7 GB)
- `totalFileSize` (GGUF on disk): 36,903,132,032 bytes (36.9 GB)
- Source: HF API `/api/models/McG-221/SuperQwen-AgentWorld-35B-A3B-abliterated-Q8_0-GGUF`
- Date verified: 2026-07-01
