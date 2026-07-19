# DSpark Progressive Block Size Training

DSpark (DFlash + Markov head + confidence head) is the recommended approach for training
block-diffusion draft models at block_size > 16. This reference covers the progressive
training pipeline validated through deep research (14+ papers) and speculators source code.

## Why Progressive Training Is Required

No paper successfully trains block_size=64 from scratch. All successful approaches use
progressive scaling — starting at small blocks and gradually increasing:

- **TDAR** (arXiv:2602.09555): 4 -> 8 -> 16 -> 32 -> 64
- **T*** (arXiv:2601.11214): AR-init -> small block -> gradually increase with RL
- **SDAR** (arXiv:2510.06303): Pretrain at 4, jump to target during SFT
- **LLaDA 2.0** (arXiv:2512.15745): Warmup-Stable-Decay block size scheduling

Direct training at BS=64 causes quality collapse: up to 15% drop on MATH500 (T* data).

## Why DSpark (Not Plain DFlash) for BS > 16

Plain DFlash (parallel block diffusion) suffers "suffix decay" — rapid acceptance loss
at positions > 8 in each block. DSpark adds:
1. **Markov logit-bias head**: injects inter-token dependencies (combats suffix decay)
2. **Confidence head**: predicts per-position acceptance probability (enables early
   stopping at inference — only verify high-confidence leading positions)

Without Markov head at BS=64: positions 0-8 ~20-40%, positions 31-63 ~0-2%.
With DSpark Markov head (rank=512, gated): positions 0-30 held steady ~15-25%.

## Training Parameter Table

| Parameter | Stage 1 (BS=16) | Stage 2 (BS=32) | Stage 3 (BS=64) |
|---|---|---|---|
| `--speculator-type` | `dspark` | `dspark` | `dspark` |
| `--block-size` | 16 | 32 | 64 |
| `--from-pretrained` | (none) | Stage 1 ckpt | Stage 2 ckpt |
| `--num-layers` | 5 | 5 | 6 |
| `--full-attention-indices` | 5 | 5 | 6 |
| `--dflash-decay-gamma` | 7.0 | 14.0 | 28.0 |
| `--per-position-loss-weight` | `fixed-exp-decay` | `fixed-exp-decay` | `dpace` |
| `--dpace-alpha` | — | — | 0.5 |
| `--markov-rank` | 256 | 384 | 512 |
| `--markov-head-type` | `vanilla` | `vanilla` | `gated` |
| `--max-anchors` | 3072 | 3072 | 2048 |
| `--loss-fn` | `{"ce": 0.1, "tv": 0.9}` | same | same |
| `--epochs` | 5 | 3 | 3 |
| `--lr` | 3e-4 | 1e-4 | 5e-5 |
| `--muon-lr` | 3e-3 | 1e-3 | 5e-4 |
| `--noise-std` | 0.05 | 0.05 | 0.05 |
| `--draft-attn-impl` | `simple_flex_attention` | same | same |
| `--enable-confidence-head` | yes | yes | yes |
| `--confidence-head-with-markov` | yes | yes | yes |

### Gamma Scaling Logic

DFlash uses exponential position-dependent loss weighting: `w_k = exp(-(k-1) / gamma)`.

| Block Size | gamma | Position (BS-1) Weight | Signal |
|---|---|---|---|
| 16 | 7 | w_15 = exp(-14/7) = 0.135 | Adequate |
| 32 | 14 | w_31 = exp(-30/14) = 0.117 | Adequate |
| 64 | 28 | w_63 = exp(-62/28) = 0.108 | Adequate |

With default gamma=7 at BS=64: w_63 = exp(-62/7) = 0.00014 — effectively ZERO training
signal for positions 20+. Must scale gamma proportionally (4x linear for 4x block size).

### Markov Rank Scaling

More block positions = more correction needed. DSpark default is rank=256 for BS=5.
For BS=64, rank=512 gives the Markov head enough capacity to maintain inter-token
dependencies across 63 positions. Use `gated` head type (better than `vanilla` for
long blocks — applies hidden-gated bias instead of simple first-order).

## Data Preparation

### Dataset Size

- Minimum: 5K samples (sanity check only)
- Recommended: 50K-100K samples (production quality)
- DFlash paper: 800K samples (Nemotron V2 + CodeAlpaca)

### Data Pipeline (speculators)

```bash
# Prepare 100K samples from UltraChat + ShareGPT
python scripts/prepare_data.py \
    --model /path/to/target-model \
    --trust-remote-code \
    --data ultrachat \
    --data sharegpt \
    --output ./training_data_100k \
    --max-samples 100000 \
    --seq-length 8192 \
    --overwrite
```

Key: `--seq-length 8192` for training (draft model is context-length independent —
learns local patterns, works at 262K context at inference). Training seq-length does
NOT need to match deployment context length.

### Hidden State Extraction

Must extract from **full_attention layers** (not linear_attention) for hybrid MoE models:

```bash
# Use FP8 model for extraction to avoid BF16+Hermes OOM
# CRITICAL: --max-model-len MUST match training seq-length (8192).
# Without it, vLLM uses model default (262K) → encoder cache OOM on multimodal models.
python scripts/launch_vllm.py /path/to/target-fp8 \
    --target-layer-ids 3 7 11 15 19 23 27 31 35 39 \
    -- --max-model-len 8192 \
       --gpu-memory-utilization 0.65 \
       --enforce-eager \
       --trust-remote-code

python scripts/data_generation_offline.py \
    --model /path/to/target-fp8 \
    --data-path ./training_data_100k \
    --output-path ./hidden_states_dspark \
    --target-layer-ids 3 7 11 15 19 23 27 31 35 39 \
    --concurrency 4
```

For Agents-A1 (Qwen3.5-MoE, 40 layers, full_attention_interval=4):
- Full attention layer indices: 3, 7, 11, 15, 19, 23, 27, 31, 35, 39
- WRONG (pretrained default): [1, 6, 11, 16, 22, 27, 32, 37] — 6/8 are linear_attention

## Expected Results Per Stage

| Stage | Block Size | Expected tau | Expected speedup | Notes |
|---|---|---|---|---|
| 1 | 16 | 5-7 | 3-4x | Proven, well-supported |
| 2 | 32 | 8-15 | 4-6x | Pareto-optimal throughput |
| 3 | 64 | 10-25* | 5-8x* | Experimental, confidence head early-stopping |

*Stage 3 tau heavily depends on Markov head effectiveness. Confidence head enables
early stopping: if positions 30+ have <5% confidence, only top 20-30 positions are
verified, making effective tau similar to BS=32.

**BS=32 (Stage 2) is the recommended production checkpoint** — it is the Pareto-optimal
throughput endpoint. BS=64 is experimental.

## Research Bibliography

| Paper | Year | Key Finding |
|---|---|---|
| DFlash (arXiv:2602.06036) | 2026 | Block diffusion spec decoding, BS=16 optimal |
| DSpark (arXiv:2607.05147) | 2026 | Markov head + confidence head |
| SDAR (arXiv:2510.06303) | 2026 | Tested BS 4-64, progressive training |
| TDAR (arXiv:2602.09555) | 2026 | Progressive Block Size Extension to 64 |
| T* (arXiv:2601.11214) | 2026 | RL-based progressive block scaling |
| Fast-dLLM v2 (arXiv:2509.26328) | 2026 | BS=32 optimal, sub-block caching |
| Nemotron TwoTower | 2026 | BS 128 vs 32 quality data |
| Block-Diffusion-Pareto | 2026 | BS 64/128 Pareto-dominated |
| DFlare (arXiv:2606.02091) | 2026 | Scale depth, not block size |
| "Teaching Diffusion to Speculate" (arXiv:2606.11552) | 2026 | Chain-breaker analysis |
