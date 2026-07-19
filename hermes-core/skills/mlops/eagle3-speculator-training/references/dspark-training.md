# DFlash / DSpark Deep Research

> Compiled from session 20260716_001818_b57562 + web research (July 2026).
> Covers: paper hyperparameters, speculators library bugs, SGLang serving, GB10 specifics.

## 1. Paper Comparison

### DFlash (Z-Lab, arXiv:2602.06036, ICML 2026)

Block diffusion speculative decoding — draft model predicts an entire block of N tokens in a single parallel forward pass using non-causal (bidirectional) attention.

**Key results**: Up to 6x lossless speedup on Qwen3-8B, ~2.5x faster than EAGLE-3.

**Training hyperparameters (from paper §A.1, verified against TeX source):**
| Parameter | Value |
|---|---|
| Block size | 16 (default), 8/10 alternatives |
| Draft layers | 5 (8B targets), 8 (30B/35B targets) |
| Target feature layers | 5 (evenly spread between 2nd and 3rd-to-last) |
| Loss decay gamma | 7 (bs16), 5 (bs10), 4 (bs8) |
| Optimizer | AdamW |
| Learning rate | 6e-4 |
| LR schedule | Cosine, warmup ratio 0.04 |
| Gradient clipping | 1.0 |
| Epochs | 6 |
| Max sequence length | 3072 (4096 for Coder) |
| Anchor positions per sequence | 512 (random) |

**Key ablation findings:**
- Block size 16 > 8 significantly (tau=6.33 vs 5.21 on Math500)
- Train at 16, infer at 8 generalizes well (tau=5.09); reverse does not (tau=5.02)
- 5 layers is optimum (vs 3 or 8)
- 5 target features > 3 features
- KV injection >> input fusion (EAGLE-style)
- Random anchor sampling > uniform block division

### DSpark (DeepSeek, arXiv:2607.05147, July 2026)

Semi-autoregressive speculator extending DFlash. Adds:
- **Markov head**: bigram bias modeling intra-block dependencies (fixes DFlash's suffix decay)
- **Confidence head**: per-position prefix survival probability for adaptive verification length

**Key result**: 2-layer DSpark already beats 5-layer DFlash across all domains.

**Loss function** (three-term):
- `ce_loss`: cross-entropy with exponential position decay
- `l1_loss`: L1 alignment on hidden states (alpha-weighted)
- `confidence_loss`: BCE on confidence head vs empirical acceptance rate

## 2. Speculators Library — Validated Arguments (train.py)

Source: `/home/user/dev/speculators/scripts/train.py` (1205 lines)

### DSpark-specific arguments

| Argument | Default | DSpark value | Notes |
|---|---|---|---|
| `--speculator-type` | (required) | `dspark` | Extends dflash with markov + confidence |
| `--block-size` | 8 | 16 | Tokens drafted per block |
| `--num-layers` | (required) | 5 | Draft transformer layers |
| `--markov-rank` | 256 | 256 (0=disable) | Bigram head rank |
| `--markov-head-type` | `vanilla` | `vanilla` | Options: vanilla, gated, rnn |
| `--enable-confidence-head` | True | (omit=redundant) | BooleanOptionalAction |
| `--confidence-head-with-markov` | True | (omit=redundant) | Requires markov_rank > 0 |
| `--dflash-decay-gamma` | (required) | 7.0 (bs16) | exp(-(k-1)/gamma) position decay |
| `--per-position-loss-weight` | (required) | `fixed-exp-decay` | Or `dpace` (requires --loss-fn ce) |
| `--loss-fn` | (required) | `{"ce":0.1,"tv":0.9}` | CE + total variation |
| `--noise-std` | 0.05 | (omit=redundant) | UNIFORM noise [-std, +std], not Gaussian |
| `--draft-attn-impl` | `simple_flex_attention` | (keep default) | Required for block mask |
| `--full-attention-indices` | (omit=all-SWA) | **OMIT** | All-SWA is supported default for dspark |
| `--mask-token-id` | (required) | from target tokenizer | Must be valid vocab ID |
| `--max-anchors` | 3072 | 3072 (2048 for bs64) | Blocks sampled per sequence |
| `--draft-vocab-size` | 32000 | 32000 | Subsampled from target vocab |

### Checkpointer behavior (CRITICAL)

- Saves to `<save_path>/<epoch_number>/` per epoch
- With `--save-best`: creates `checkpoint_best -> <best_epoch>` symlink
- `cleanup_keep_only_best()` DELETES non-best epoch dirs after each epoch
- `--resume-from-checkpoint` is DEFAULT (not opt-in) — will silently resume optimizer state
- Use `--no-resume-from-checkpoint` for fresh starts
- Use per-stage save paths: `--save-path $SAVE/bs16` not `--save-path $SAVE`

### `--from-pretrained` constraints

- CANNOT be combined with decoder-shaping flags: `--num-layers`, `--draft-arch`, `--full-attention-indices`, `--sliding-window`
- Triggers `parser.error()` via `validate_draft_init_args()`
- Progressive BS training (16→32→64) is therefore IMPOSSIBLE without rewriting the validation

## 3. Hidden States Format (offline)

Expected directory layout:
```
<hidden-states-path>/
├── hs_0.safetensors
├── hs_1.safetensors
└── hs_<N>.safetensors
```

Per-file contents:
```python
{
    "hidden_states": tensor[seq_len, num_target_layers + 1, hidden_size],
    "token_ids": tensor[seq_len]
}
```

- `num_target_layers` = len(`--target-layer-ids`) passed to train.py
- The `+1` is the verifier's last layer (auto-appended by vLLM)
- `hidden_states[:, :-1]` → concatenated aux hidden states (input to fc layer)
- `hidden_states[:, -1]` → verifier_last_hidden_states
- `token_ids` MUST match `input_ids` from the Arrow dataset — mismatches silently dropped

## 4. SGLang DFLASH Serving Internals

Source: `/home/user/sglang_venv/lib/.../sglang/srt/speculative/`

### Worker architecture

- **DFlashWorker** (v1, `dflash_worker.py`): spec-v1, synchronous scheduling
- **DFlashWorkerV2** (v2, `dflash_worker_v2.py`): spec-v2, overlap scheduling (draft overlaps target verify)
- **Selection**: `SGLANG_ENABLE_SPEC_V2=1` (default=True) → v2 always used
- v2 adds Triton fused kernels: `_prepare_dflash_draft_block_unchecked`, `_compute_dflash_accept_bonus_triton_unchecked`

### Draft model requirements

DFlashDraftModel checkpoint must contain:
- `layers.*.self_attn.{q,k,v,o}_proj.weight`
- `layers.*.mlp.{gate,up,down}_proj.weight`
- `layers.*.{input_,post_attention_]layernorm.weight`
- `fc.weight` — target feature projection (shape: [hidden_size, num_target_layers * hidden_size])
- `hidden_norm.weight`, `norm.weight`
- NO embeddings, NO lm_head (reuses target's)
- `config.json` MUST have `num_hidden_layers` (REQUIRED field)

### Hybrid mamba (Qwen3.5) support

- `qwen3_5.py:1174` implements `set_dflash_layers_to_capture()` — first-class DFLASH target
- `hybrid_linear_attn_backend.py:967` implements `update_mamba_state_after_mtp_verify`
- DFlashWorker commits mamba SSM/conv states after accepted verify steps
- `--mamba-scheduler-strategy extra_buffer` is MANDATORY

### Attention backend on GB10 (sm_121)

| Backend | Status | Notes |
|---|---|---|
| `triton` | ✅ Works | RECOMMENDED — no JIT spike |
| `flashinfer` | ⚠️ Risky | May JIT for edge-case MoE variants on sm_121 |
| `trtllm_mha` | ❌ Rejected | Explicitly does not support SM120/121 |

### Multimodal (VLM) support

- `qwen3_vl.py:1305` implements `set_dflash_layers_to_capture` — supported
- `validate_dflash_request` only rejects: logprobs, hidden_states return, grammar constraints
- DFlash forces `CaptureHiddenMode.FULL` on all prefills (heavier but correct)
- Images processed during prefill; DFlash operates on decode only

## 5. Real-World DFlash/DSpark Checkpoints (HuggingFace)

| Model | Type | Layers | Block | Optimizer | Notes |
|---|---|---|---|---|---|
| z-lab/Qwen3.6-35B-A3B-DFlash | DFlash | 6 | 16 | — | Pretrained, 737MB, wrong target_layer_ids |
| z-lab/Alpamayo-R1-10B-DFlash | DFlash | 2 | 8 | — | Target layers [24,30,31,32,34] |
| RedHatAI/DeepSeek-V4-Flash-speculator.dflash | DFlash | 5 | — | Muon | All-SWA, 2B params |
| inference-optimization/Qwen3-8B-DFlash-b16 | DFlash | 5 | 16 | Muon | lr=1e-3 |
| mgoin/GLM-5.2-speculator.dspark-block16 | DSpark | 5 | 16 | — | Full attention, aux layers [8,23,39,55,70] |
| Dogacel/Qwen3-8B-DSpark | DSpark | — | — | — | TorchSpec training |

## 6. DSpark vs EAGLE3 Memory Budget (GB10, BF16 35B target)

### Training
```
Target (frozen, BF16):       65.5 GB
Hidden states (disk):         ~5 GB (batched)
Draft model + optimizer:      ~4 GB
Activations:                  ~8 GB
─────────────────────────────────────
Total:                      ~83 GB  ✅
```

### Serving (SGLang)
```
Target BF16:                65.5 GB
System + Hermes:             12.0 GB
KV cache (mem-frac 0.62):    pre-alloc in pool
Activations (4 seq):         ~10 GB
DFlash draft:                 ~1.4 GB
─────────────────────────────────────
Total:                      ~89 GB  ✅
```

## 7. Recommended DSpark Configurations

| Scenario | Block Size | Layers | Gamma | Markov | Serving Backend | Expected tau |
|---|---|---|---|---|---|---|
| Single-user throughput | 16 | 5 | 7.0 | 256 vanilla | SGLang triton | 5-7 |
| Higher concurrency | 8 | 5 | 4.0 | 256 vanilla | SGLang triton | 4-5 |
| Maximum depth (research) | 16 | 8 | 7.0 | 512 gated | SGLang triton | 7-8 |

## 8. User Workflow Preferences (Pavel)

- MAX_JOBS=5 is the preferred value for BF16 MoE on GB10 (not 1, not 10)
- `--limit-mm-per-prompt '{"image": 0}'` for text-only training data extraction
- `--max-num-seqs 1` for hidden state extraction (minimizes profiling)
- Images MUST be supported at serving time (DFlash doesn't break VLM)
- 262K context MUST be preserved in serving config
- Context=262144 during hidden state extraction is fine with image=0 + seqs=1
