# DFlash — Block Diffusion for Flash Speculative Decoding

DFlash (Z Lab, arXiv:2602.06036, Feb 2026) replaces EAGLE-3's autoregressive drafter with a block diffusion model that predicts an entire block of tokens in a single parallel forward pass. Uses bidirectional (non-causal) attention so all draft positions attend to each other simultaneously.

## Architecture

The DFlash draft model uses Qwen3-style transformer layers with sliding window attention:

- **6 layers**: 5 `sliding_attention` + 1 `full_attention` (last layer)
- **Hidden size**: 2048 (matches Qwen3.5-MoE target)
- **Block size**: 16 (default) — produces `block_size - 1` speculative tokens
- **Attention**: Bidirectional (non-causal) — all mask token positions attend to each other + target hidden states simultaneously
- **Anchor point mechanism**: One anchor token + N mask tokens → single forward pass → all draft tokens at once
- **Target LM head**: Reuses the target model's LM head for vocabulary projection (no separate head)
- **Sliding window**: 4096 tokens in draft layers

### Config Format (from `z-lab/Qwen3.5-35B-A3B-DFlash/config.json`)

```json
{
  "architectures": ["DFlashDraftModel"],
  "model_type": "qwen3",
  "hidden_size": 2048,
  "num_hidden_layers": 6,
  "num_attention_heads": 32,
  "num_key_value_heads": 8,
  "head_dim": 128,
  "intermediate_size": 6144,
  "vocab_size": 248320,
  "layer_types": [
    "sliding_attention", "sliding_attention", "sliding_attention",
    "sliding_attention", "sliding_attention", "full_attention"
  ],
  "sliding_window": 4096,
  "max_window_layers": 6,
  "dflash_config": {
    "block_size": 16,
    "mask_token_id": 248077,
    "target_layer_ids": [1, 6, 11, 16, 22, 27, 32, 37]
  },
  "num_target_layers": 40,
  "auto_map": { "AutoModel": "dflash.DFlashDraftModel" }
}
```

### vLLM Registration (algos.py)

DFlash is registered in vLLM's speculators config system:

```python
@register_speculator("dflash")
def update_dflash(config_dict, pre_trained_config):
    # Architecture: DFlashDraftModel
    # Required fields:
    #   - draft_vocab_size
    #   - target_hidden_size
    #   - mask_token_id (required)
    #   - aux_hidden_state_layer_ids (required) → mapped to:
    #       eagle_aux_hidden_state_layer_ids (for gpu_model_runner)
    #       dflash_config.target_layer_ids (i-1 indexing, see #40727)
```

**Important indexing quirk**: `target_layer_ids` uses `i - 1` indexing relative to `aux_hidden_state_layer_ids` (vLLM issue #40727). When specifying layers in training, use the actual layer indices; the config conversion handles the offset.

## Sampling Modes

Controlled by `sample_from_anchor` config field:

| Mode | Default | Behavior | Speculative tokens |
|---|---|---|---|
| `False` | DFlash | Anchor is bonus token, only mask tokens predict. Slot 0 not trained. | `block_size - 1` |
| `True` | DSpark | Sample from anchor AND all mask positions. All slots trained. | `block_size` |

Training flags: `--sample-from-anchor` / `--no-sample-from-anchor`

## Pretrained DFlash Models on HuggingFace

### Official (Z-Lab + Modal)

| Model | Target | Notes |
|---|---|---|
| `z-lab/Qwen3.5-35B-A3B-DFlash` | Qwen3.5-35B-A3B | Joint retrain, 40k seq len, SWA. **Closest to Agents-A1** |
| `modal-labs/Qwen3.5-35B-A3B-DFlash` | Qwen3.5-35B-A3B | Mirror of above |
| `z-lab/Qwen3.6-35B-A3B-DFlash` | Qwen3.6-35B-A3B | For Qwen3.6 variant |
| `z-lab/Qwen3.5-122B-A10B-DFlash` | Qwen3.5-122B-A10B | Larger MoE |
| `modal-labs/Qwen3.5-397B-A17B-DFlash` | Qwen3.5-397B-A17B | Largest, beats native MTP |
| `z-lab/Qwen3.6-27B-DFlash` | Qwen3.6-27B (dense) | Dense model variant |

### Community / GGUF

| Model | Target | Format |
|---|---|---|
| `ji-farthing/Qwen3.5-35B-A3B-DFlash-SWA-ik-llama-GGUF` | Qwen3.5-35B-A3B | GGUF for llama.cpp |
| `abhinand/Qwen3.6-35B-A3B-DFlash-GGUF` | Qwen3.6-35B-A3B | GGUF |
| `lym00/Qwen3.6-35B-A3B-DFlash-GGUF-Test` | Qwen3.6-35B-A3B | GGUF test |

### Red Hat (speculators collection)

| Model | Target |
|---|---|
| `RedHatAI/gemma-4-31B-it-speculator.dflash` | Gemma 4 31B |

**No DFlash draft exists specifically for Agents-A1.** The `z-lab/Qwen3.5-35B-A3B-DFlash` is architecturally compatible but will have reduced acceptance due to SFT/abliteration activation shift.

## Deployment

### SGLang (Primary, Recommended)

```bash
export SGLANG_ENABLE_OVERLAP_PLAN_STREAM=1

python -m sglang.launch_server \
  --model-path Qwen/Qwen3.5-35B-A3B \
  --trust-remote-code \
  --speculative-algorithm DFLASH \
  --speculative-draft-model-path z-lab/Qwen3.5-35B-A3B-DFlash \
  --speculative-dflash-block-size 8 \
  --speculative-draft-attention-backend fa4 \
  --attention-backend trtllm_mha \
  --linear-attn-prefill-backend flashinfer \
  --linear-attn-decode-backend flashinfer \
  --mamba-scheduler-strategy extra_buffer \
  --tp-size 1 \
  --max-running-requests 32 \
  --cuda-graph-max-bs-decode 32 \
  --cuda-graph-backend-prefill tc_piecewise \
  --enable-flashinfer-allreduce-fusion \
  --mem-fraction-static 0.8
```

**With Agents-A1 as target:**
```bash
python -m sglang.launch_server \
  --model-path InternScience/Agents-A1 \
  --trust-remote-code \
  --speculative-algorithm DFLASH \
  --speculative-draft-model-path z-lab/Qwen3.5-35B-A3B-DFlash \
  --speculative-dflash-block-size 8 \
  ...
```

### vLLM

DFlash is registered in vLLM's `algos.py` (`@register_speculator("dflash")`), but full serving support is still in progress via PR #40898. The draft model loads via `DFlashDraftModel` architecture with `auto_map`. Once merged:

```bash
vllm serve InternScience/Agents-A1 \
  --speculative-config '{
    "method": "dflash",
    "model": "z-lab/Qwen3.5-35B-A3B-DFlash",
    "num_speculative_tokens": 7
  }'
```

### llama.cpp

Community GGUF drafts available. Use as draft model:
```bash
llama-server -m agents-a1.gguf -md dflash-draft.gguf \
  --spec-type draft-dflash \
  --draft 7
```

## Training via Speculators

DFlash training is supported in speculators v0.5.0+ (released Jun 2026). Uses the same offline pipeline as EAGLE3 but with different flags.

### Key Differences from EAGLE3 Training

| Aspect | EAGLE3 | DFlash |
|---|---|---|
| `--speculator-type` | `eagle3` | `dflash` |
| Draft layers | 1 layer (~0.4B) | 6 layers (~1B) |
| Attention | Causal | Bidirectional (non-causal) |
| Sliding window | No | Yes (`SLIDING_WINDOW_SPECULATOR_TYPES`) |
| `--full-attention-indices` | Not used | Controls which draft layers use full vs sliding attention |
| `--sample-from-anchor` | Not used | Controls sampling mode (default: False for DFlash) |
| Memory during training | Lower | Higher (6 layers vs 1) |
| Speculators class | `Eagle3Qwen3ForCausalLM` | `DFlashDraftModel` |

### Training Command

```bash
# Phase 1-2: Extract hidden states (same as EAGLE3)
# CRITICAL: Use full_attention layer indices for hybrid attention models!
python scripts/launch_vllm.py --model InternScience/Agents-A1 \
  --target-layer-ids 3 7 11 15 19 23 27 31 35 39

python scripts/data_generation_offline.py \
  --dataset ./training_data \
  --concurrency 4 \
  --output-dir ./hidden_states

# Phase 3: Train DFlash draft
python scripts/train.py \
  --speculator-type dflash \
  --draft-arch qwen3 \
  --verifier InternScience/Agents-A1 \
  --target-layer-ids 3 7 11 15 19 23 27 31 35 39 \
  --full-attention-indices 3 7 11 15 19 23 27 31 35 39 \
  --no-sample-from-anchor \
  --max-model-len 8192
```

### speculators CLI Conversion

The `speculators convert` command currently supports `eagle`, `eagle3`, and `mtp` algorithms. DFlash conversion is NOT yet in the CLI — use the training pipeline directly.

## DSpark (DFlash Extension)

DSpark (arXiv:2607.05147, DeepSeek, Jul 2026) extends DFlash with a **Markov logit-bias head** and **confidence-scheduled speculation**. Also in speculators (`--speculator-type dspark`) and registered in vLLM source (`@register_speculator("dspark")`).

- Architecture: `Qwen3DSparkModel`
- Config: `dspark_bonus_anchor: True` (1+N fill-in block, anchor is bonus token)
- Additional fields: `markov_rank`, `markov_head_type`, `block_size`, `enable_confidence_head`, `confidence_head_with_markov`
- `target_layer_ids` uses same `i-1` indexing as DFlash
- `sample_from_anchor` defaults to `True` (all slots predict, produces `block_size` tokens)
- Pretrained: `deepseek-ai/dspark_qwen3_8b_block7` (Qwen3-8B dense)
- **Confidence scheduling**: Uses a confidence head to dynamically decide whether to speculate or fall back to autoregressive decoding, improving throughput under varying acceptance conditions

### DSpark Training (speculators)

DSpark training uses the same offline pipeline as DFlash but with additional flags.
See `references/dspark-progressive-training.md` for the full progressive BS=16->32->64 pipeline.

```bash
# DSpark training command (from official example dspark_qwen3_0_6b_sharegpt_online.sh)
torchrun --standalone --nproc_per_node 1 scripts/train.py \
    --speculator-type dspark \
    --block-size 8 \
    --num-layers 3 \
    --target-layer-ids 2 14 25 \
    --markov-rank 256 \
    --markov-head-type vanilla \
    --enable-confidence-head \
    --confidence-head-with-markov \
    --loss-fn '{"ce": 0.1, "tv": 0.9}' \
    --confidence-head-alpha 1.0 \
    --max-anchors 3072 \
    --draft-vocab-size 32000 \
    --epochs 5 --lr 3e-4 \
    --optimizer muon --muon-lr 3e-3 \
    --draft-attn-impl simple_flex_attention
```

Key DSpark-specific train.py flags (verified in speculators 0.6.0 source):
- `--markov-rank` (default 256): Low-rank dim of Markov logit-bias head. Scale up for larger blocks (384 for BS=32, 512 for BS=64).
- `--markov-head-type` (default `vanilla`): `vanilla` (first-order), `gated` (hidden-gated, better for BS>16), `rnn` (recurrent state, marginal gains over gated).
- `--enable-confidence-head` / `--no-enable-confidence-head`: Per-position acceptance probability head.
- `--confidence-head-with-markov`: Feed Markov previous-token embedding into confidence head.
- `--confidence-head-alpha` (default 1.0): Weight of confidence-head BCE loss term.
- `--dflash-decay-gamma` (default 4.0): Exponential position decay gamma. Scale linearly with block size (gamma=7 for BS=16, 14 for BS=32, 28 for BS=64).
- `--per-position-loss-weight` (default `fixed-exp-decay`): Use `dpace` for adaptive weights at large block sizes.
- `--dpace-alpha` (default 0.5): D-PACE smoothing constant.
- `--loss-fn` (default `kl_div`): For DSpark, use `{"ce": 0.1, "tv": 0.9}` (from official example).
- `--from-pretrained`: Load checkpoint from previous stage (essential for progressive block size training).

## DFlash + Agents-A1 (Qwen3.5-MoE) Compatibility

### Architecture Match

| Parameter | z-lab DFlash config | Agents-A1 config | Match? |
|---|---|---|---|
| hidden_size | 2048 | 2048 | ✅ |
| vocab_size | 248320 | 248320 | ✅ |
| num_target_layers | 40 | 40 | ✅ |
| max_position_embeddings | 262144 | 262144 | ✅ |
| model_type | qwen3 (draft) | qwen3_5_moe (target) | ✅ compatible |
| full_attention_interval | — | 4 (hybrid) | ✅ same base |

### Hybrid Attention Layer Issue

Agents-A1 (Qwen3.5-MoE) uses hybrid attention: 75% `linear_attention` (GatedDeltaNet) + 25% `full_attention`, with `full_attention_interval: 4`.

Full attention layer indices: **3, 7, 11, 15, 19, 23, 27, 31, 35, 39**

The pretrained z-lab DFlash uses `target_layer_ids: [1, 6, 11, 16, 22, 27, 32, 37]` — **6 of 8 are linear_attention layers**. This is the same issue as EAGLE3 pitfall #16, but DFlash combines 8 layers through bidirectional attention (vs EAGLE3's 3 layers), which may partially mitigate the problem.

**For training on Agents-A1**: Use `--target-layer-ids 3 7 11 15 19 23 27 31 35 39` (full_attention layers only) for best acceptance rates.

### Activation Shift

Agents-A1 is a fine-tune of Qwen3.5-35B-A3B. SFT and abliteration shift the activation space. Using the pretrained z-lab DFlash (trained on base Qwen3.5-35B-A3B) will have reduced acceptance. For max acceptance, train DFlash on Agents-A1's own hidden states.

Expected acceptance degradation (estimated from EAGLE3 data):
- Base model DFlash: ~70-80% acceptance
- Agents-A1 with pretrained DFlash: ~55-65% acceptance
- Agents-A1 with trained DFlash: ~70-80% acceptance

## References

- Paper: arXiv:2602.06036 (Feb 2026)
- GitHub: https://github.com/z-lab/dflash
- Project page: https://z-lab.ai/projects/dflash/
- Speculators docs: https://docs.vllm.ai/projects/speculators/en/latest/user_guide/algorithms/dflash/
- Speculators v0.5.0 release: https://developers.redhat.com/articles/2026/06/04/speculators-v050-dflash-support-and-online-training
- LMSYS blog (DFlash + Spec V2): https://www.lmsys.org/blog/2026-06-15-next-generation-speculative-decoding-dflash-v2/
- vLLM PR: https://github.com/vllm-project/vllm/pull/40898
