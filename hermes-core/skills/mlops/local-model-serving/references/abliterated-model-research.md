# Abliterated Model Research — DGX Spark Session

Session date: 2026-07-01. Full transcript available via session_search.

## Abliteration Method Comparison

Source: nathan.sapwell.net analysis of Qwen3.6-27B abliteration techniques.

| Method | KL Divergence | Refusals (of 100) | Quality Rating | Notes |
|--------|:-----------:|:-----------------:|:---------------|-------|
| **Heretic v1.2.0** | **0.0015** | ~10 | 🥇 Excellent | MPOA decensoring, gold standard |
| Huihui | ~0.003 | ~15 | 🥈 Excellent | Standard abliteration |
| Obliteratus | ~0.005 | ~20 | 🥈 Good | Can combine with Supertune |
| Abliterix | ~0.010 | ~25 | 🥉 OK | 6.5× higher KL than Heretic |
| HauhauCS | ~0.010 | ~25 | 🥉 OK | Similar to Abliterix |

## Three-Model Abliterated Stack for DGX Spark

Final picks after deep research comparing all available abliterated GGUF variants.

### 🤖 Nex-N2-mini — Coding Agent

- **Repo:** `SC117/Huihui-Nex-N2-mini-abliterated-APEX-GGUF`
- **File:** `Huihui-Nex-N2-mini-abliterated-APEX-Quality.gguf` (21.3 GB)
- **Abliteration:** huihui-ai
- **Quant:** APEX Quality — beats Q8_0 on HellaSwag (+0.5pp), 2× smaller
- **No Q8_0 abliterated exists** — all abliterated Nex repos max out at Q4_K_M or APEX
- **Thinking mode:** requires Nex's patched llama.cpp for `<think>` tags. Works fine on stock llama.cpp for coding (no think tags needed).
- **Benchmarks (orig BF16):** SWE-Bench 74.4, Terminal-Bench 60.7, GPQA 82.6, IFEval 89.1

### 🧠 Qwen3.6-35B — Reasoning Agent

- **Repo:** `SC117/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved-APEX-GGUF`
- **File:** `Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved-APEX-I-Quality.gguf` (21.3 GB)
- **Abliteration:** Heretic v1.2.0 (KL 0.0015 — lowest of any method)
- **Quant:** APEX I-Quality — 83.5% HellaSwag (beats Q8_0), 63.1 tok/s
- **MTP preserved:** speculative decoding works out of the box
- **Only I-variants in this repo** (I-Quality, I-Balanced, I-Compact)
- **Benchmarks (orig):** GPQA 86.0, MTP 50 tok/s

### 🔮 AgentWorld-35B — Simulation Agent

- **Repo:** `Jiunsong/SuperQwen-AgentWorld-35B-A3B-abliterated-gguf-4bit`
- **File:** `SuperQwen-AgentWorld-35B-A3B-abliterated-Q4_K_M.gguf` (~20 GB)
- **Abliteration + Post-training:** Obliteratus + Supertune (targeted for AgentWorld tasks)
- **Benchmark improvements vs original:** HumanEval+ +59, MBPP+ +44, MMLU-Pro +14, IFEval +12
- **AgentWorldBench proxy:** −2.32 due to stricter response-integrity guards (not quality loss)
- **Only 4-bit available** — no Q8_0, no APEX
- **Huihui-AgentWorld** (alternative) is "crude, proof-of-concept" — no post-training, worse quality

## Memory Budget

```
Nex APEX Quality:      21 GB + 4 GB KV (Q8_0, 128K) = 25 GB
Qwen APEX I-Quality:   21 GB + 2 GB KV (Q8_0, 128K) = 23 GB
AgentWorld Q4_K_M:     20 GB + 1 GB KV (Q8_0, 64K)  = 21 GB
llama-server overhead:  ~3 GB
─────────────────────────────────────────────────────
Matrix total:          ~72 GB
Available:             ~95 GB
Headroom:              ~23 GB ✅
```

## KV Cache Estimation

For MoE models (35B/3B active), Q8_0 KV cache:
- ~2 bytes per token per layer for attention layers
- Approximate formula: `(context / 256) * 8 GB` for 256K context
- 128K context → ~4 GB, 64K → ~2 GB, 256K → ~8 GB

## Research Methodology

1. Search HF API: `curl -s "https://huggingface.co/api/models?search=<MODEL>+abliterated+GGUF"`
2. List GGUF siblings: `curl -s "https://huggingface.co/api/models/<REPO>?expand[]=siblings" | python3 -c "..." | grep .gguf`
3. Read README: `curl -sL "https://huggingface.co/<REPO>/raw/main/README.md"`
4. Compare: abliteration method (KL divergence), quant type (APEX vs standard), post-training presence
5. Verify stock llama.cpp compatibility
6. Budget memory: model size + KV cache estimate + overhead
