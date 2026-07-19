# Agents-A1 Architecture Analysis for EAGLE3

Verified from `huihui-ai/Huihui-Agents-A1-abliterated` config.json (July 2026).
Applies to all Qwen3.5-MoE based models (Agents-A1, Qwen3.6-35B-A3B, Nex-N2-mini,
Qwen-AgentWorld-35B-A3B, etc.).

## Architecture: Qwen3_5MoeForConditionalGeneration

| Parameter | Value | EAGLE3 Impact |
|---|---|---|
| hidden_size | 2048 | Draft MUST match (matches Qwen3-30B MoE draft) |
| num_hidden_layers | 40 | Fewer than Qwen3-30B (48) — different layer IDs |
| num_experts | 256 | MoE routing overhead |
| num_experts_per_tok | 8 routed + 1 shared | ~3B active params |
| moe_intermediate_size | 512 | Per-expert FFN |
| vocab_size | 248320 | Large — use --draft-vocab-size 8192 |
| num_attention_heads | 16 | Full attention layers |
| num_key_value_heads | 2 | GQA |
| head_dim | 256 | |
| full_attention_interval | 4 | Hybrid: 3 linear + 1 full per group |
| mtp_num_hidden_layers | 1 | MTP already built-in |
| max_position_embeddings | 262144 | 256K context |
| rope_theta | 10000000 | M-RoPE (multimodal) |
| dtype | bfloat16 | Training dtype |
| tie_word_embeddings | false | |

## Hybrid Attention Layer Map (CRITICAL)

Pattern: `[linear, linear, linear, full]` repeating, 10 groups = 40 layers.

```
Layer  0: linear_attention  ← default EAGLE3 picks [2, ...]
Layer  1: linear_attention
Layer  2: linear_attention  ← DEFAULT: WRONG (linear, not full)
Layer  3: full_attention    ← CORRECT: use this
Layer  4: linear_attention
Layer  5: linear_attention
Layer  6: linear_attention
Layer  7: full_attention
Layer  8: linear_attention
Layer  9: linear_attention
Layer 10: linear_attention
Layer 11: full_attention
Layer 12: linear_attention
Layer 13: linear_attention
Layer 14: linear_attention
Layer 15: full_attention
Layer 16: linear_attention
Layer 17: linear_attention
Layer 18: linear_attention
Layer 19: full_attention    ← CORRECT: use this (middle)
Layer 20: linear_attention  ← DEFAULT: WRONG (linear)
Layer 21: linear_attention
Layer 22: linear_attention
Layer 23: full_attention
Layer 24: linear_attention
Layer 25: linear_attention
Layer 26: linear_attention
Layer 27: full_attention
Layer 28: linear_attention
Layer 29: linear_attention
Layer 30: linear_attention
Layer 31: full_attention
Layer 32: linear_attention
Layer 33: linear_attention
Layer 34: linear_attention
Layer 35: full_attention
Layer 36: linear_attention
Layer 37: linear_attention  ← DEFAULT: WRONG (linear)
Layer 38: linear_attention
Layer 39: full_attention    ← CORRECT: use this (end)
```

### Default vs Correct Layer Selection

| Selection | Layers | Type | Result |
|---|---|---|---|
| Default `[2, 20, 37]` | 2, 20, 37 | ALL linear_attention | Silent low acceptance (~30-40%) |
| **Correct `[3, 19, 39]`** | 3, 19, 39 | ALL full_attention | Expected acceptance (~60-80%) |
| Extended `[3, 11, 19, 27, 35]` | 5 full_attn layers | More signal | Try if [3,19,39] gives <50% |

### Rule for Other Hybrid Models

For any model with `full_attention_interval: N`, full attention layers are at
indices `N-1, 2N-1, 3N-1, ...`. For Agents-A1 (N=4): indices 3, 7, 11, ..., 39.

Pick 3 evenly spaced: first (3), middle (19), last (39).

## Compatibility with Existing EAGLE3 Drafts

### nm-testing/Speculator-Qwen3-30B-MOE-VL-Eagle3

| Parameter | Existing Draft | Agents-A1 | Compatible? |
|---|---|---|---|
| hidden_size | 2048 | 2048 | YES |
| num_hidden_layers (target) | 48 (Qwen3-30B) | 40 (Agents-A1) | Different — layer IDs must change |
| draft_vocab_size | 8192 | 248320 (target) | Need remapping via token_freq.pt |
| draft_arch | llama | — | OK (draft can differ from target) |
| head_dim (draft) | 128 | 256 (target) | OK (draft internal) |
| speculators_version | 0.4.0.dev2 | Need >=0.5.0 | May need upgrade |

**Verdict**: hidden_size matches (2048). Can be used as initialization for
fine-tuning (`--from-pretrained`), but hidden states must be re-generated
from Agents-A1 (different layer count → different layer IDs). Token frequency
mapping must be recomputed. Retrain at least 3 epochs to adapt.

## MTP Built-In

Agents-A1 has `mtp_num_hidden_layers: 1` — a built-in Multi-Token Prediction
head. This provides ~1.2-1.7x speedup with zero training. EAGLE3 should beat
this (2-6x target), but MTP serves as the baseline to exceed.

Existing MTP-grafted GGUF models:
- `protoLabsAI/Agents-A1-MTP-GGUF` — for llama.cpp
- `wang-yang/Agents-A1-MTPLX-Q4` — for MLX/Apple Silicon

## Abliterated Model

`huihui-ai/Huihui-Agents-A1-abliterated` — BF16 safetensors, 65.4 GB (14
shards). Created with diff-in-means abliteration. Best quality abliterated
variant (huihui-ai is the community standard for abliteration).

Abliteration shifts the activation space, which degrades MTP acceptance
(~76% → ~65-70%). EAGLE3 trained on the abliterated model's own hidden
states does not suffer this degradation — another reason to prefer EAGLE3
over MTP for abliterated models.
