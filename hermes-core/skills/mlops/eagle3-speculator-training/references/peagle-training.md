# P-EAGLE Training Reference

## Algorithm Comparison

### EAGLE3 (sequential/autoregressive draft)
- Draft model generates tokens one at a time: t1 → t2 → t3
- Each token depends on the previous → compounding error
- Position N acceptance = P(correct | all previous correct) — drops geometrically
- Best for: quick sanity checks, small datasets, single-GPU

### P-EAGLE (parallel draft)
- Draft model predicts all N tokens in a single forward pass
- No compounding error between positions (parallel, not sequential)
- Uses COD (Conditional-On-Distribution) sampling for memory-efficient training
- Best for: production, maximizing acceptance length, large datasets

## Scaling Estimates

### Dataset size vs acceptance rate (EAGLE3, ttt=3)

| Samples | Pos 0 | Pos 1 | Pos 2 | Mean len | Speedup |
|---------|-------|-------|-------|----------|---------|
| 5k | 63.6% | 28.0% | 10.3% | 2.02 | 1.34x |
| 50k | ~65% | ~40% | ~22% | ~2.5 | ~1.5x |
| 100k | ~67% | ~45% | ~25% | ~2.7 | ~1.6x |

### P-EAGLE with 8 depths (projected)

| Samples | Mean len | Speedup |
|---------|----------|---------|
| 50k | ~3.5-4.0 | ~1.8-2.0x |
| 100k | ~4.0-4.5 | ~2.0-2.2x |

## Disk Space Requirements

| Samples | Hidden states | Training data | Total |
|---------|---------------|----------------|-------|
| 5k | ~101 GB | ~55 MB | ~101 GB |
| 50k | ~1 TB | ~550 MB | ~1 TB |
| 100k | ~2 TB | ~1.1 GB | ~2 TB |

Each hidden state file is ~20 MB (4 layers × seq_len × hidden_size × bfloat16).

## Timing Estimates (DGX Spark GB10, Qwen3.5 MoE 65GB)

| Phase | 5k samples | 50k samples |
|-------|------------|-------------|
| Data prep | ~2 min | ~2 min |
| vLLM startup | ~10 min | ~10 min |
| Hidden states extraction | ~38 min | ~6.3 hours |
| EAGLE3 training (10 epochs) | ~4.5 hours | ~10 hours |
| P-EAGLE training (5 epochs, 8 depths) | — | ~10-15 hours |

## P-EAGLE Reference Results (RedHat Qwen3-8B, 5k samples, 4 depths)

From the speculators example script:

| Position | Acceptance |
|----------|------------|
| 0 | 40.84% |
| 1 | 10.84% |
| 2 | 1.58% |
| 3 | 0.15% |
| Mean length | 1.53 |
| Acceptance rate | 13.35% |

Note: These are with only 5k samples and 4 depths. With 50k+ samples and 8 depths, significantly better results are expected.

## COD Sampling Explanation

Conditional-On-Distribution (COD) sampling is P-EAGLE's memory optimization:

- At each depth, only a fraction of tokens are retained for training
- `--down-sample-ratio 0.7`: retain 70% of tokens at each depth
- `--down-sample-ratio-min 0.2`: never go below 20% retention
- This prevents memory from growing linearly with `--num-depths`
- Without COD, 8 depths on 50k samples would require ~8x memory

## Serving: EAGLE3 vs P-EAGLE

| | EAGLE3 serving | P-EAGLE serving |
|---|---|---|
| `--speculative_config` method | `"eagle3"` | `"peagle"` |
| `num_speculative_tokens` | ≤ `--ttt-steps` (e.g. 3) | ≤ `--num-depths` (e.g. 8) |
| Draft model size | ~1.2 GB (1 layer) | ~5 GB (4 layers) |
| GPU memory overhead | Low | Moderate |
| Best for | Low-latency, small batch | High throughput, large batch |
