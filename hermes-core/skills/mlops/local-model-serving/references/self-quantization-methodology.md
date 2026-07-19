# Self-Quantization Methodology — Full Pipeline

How to quantize an LLM yourself from BF16/FP16 with minimal quality loss. Covers standard K-quant, importance-matrix-enhanced, and APEX MoE-aware pipelines.

## Golden Rule

**Quantize ONLY from BF16/FP16.** Requantizing an already-quantized model (`--allow-requantize`) severely degrades quality. `llama-quantize` warns about this explicitly.

## PTQ vs QAT — No Retraining Needed

A common misconception: that quantization requires re-training the model afterwards. This is FALSE for llama.cpp/APEX quantization.

| | PTQ (Post-Training Quantization) | QAT (Quantization-Aware Training) |
|---|---|---|
| **What it does** | Compresses ready weights → GGUF | Trains model to tolerate low precision |
| **When** | After all training is done | During training |
| **Needs GPU?** | No (only for imatrix, CPU works) | Yes — full training cycle |
| **Used by** | llama-quantize, APEX, GGUF ecosystem | Research settings, extreme ultra-low-bit |
| **Preserves fine-tunes?** | ✅ Yes — all post-training is kept | Needs re-fine-tuning after |

**llama.cpp and APEX use PTQ.** All post-training improvements (Supertune, abliteration, LoRA merges, instruction fine-tunes) are preserved because quantization only rounds existing weights — it doesn't change what the model knows. APEX I-Quality already beats FP16 on downstream benchmarks without any QAT.

## Why Quantization Loses Quality

Three mechanisms, in descending order of impact:

1. **Rounding error** — FP16 (65536 values) → INT4 (16 values). Information destroyed.
2. **Uneven layer importance** — attention layers are 10× more sensitive than feed-forward. Uniform Q4 wastes bits on FF and starves attention.
3. **Weight outliers** — 0.1% of weights have 100× the magnitude of the median. Q4 collapses them catastrophically.

## Three-Tier Pipeline

### Tier 1: Basic K-Quant (no calibration)

```
HF BF16 → convert_hf_to_gguf.py → F16.gguf → llama-quantize → Q4_K_M.gguf
```

Quality data from arXiv 2601.14277 (Llama-3.1-8B-Instruct):

| Quant | Size | Avg Score | Δ from FP16 | PPL |
|-------|:---:|:---:|:---:|:---:|
| Q8_0 | 53% | 69.41 | **−0.06** ✅ | 7.33 |
| Q6_K | 41% | 69.23 | −0.24 | 7.35 |
| Q5_K_M | 36% | 69.36 | −0.11 | 7.40 |
| Q4_K_M | 31% | 69.15 | −0.32 | 7.56 |
| Q3_K_M | 25% | 68.07 | −1.40 ⚠️ | 7.96 |
| Q3_K_S | 23% | 65.49 | **−3.98** 🔴 | 8.96 |

### Tier 2: With Importance Matrix (calibrated)

Adds a calibration step between conversion and quantization:

```bash
# Generate importance matrix
llama-imatrix \
  -m model-f16.gguf \
  -f calibration_data.txt \
  -o model.imatrix.gguf \
  --ctx-size 512 \
  --chunk 1024 \
  -ngl 99

# Quantize with imatrix
llama-quantize \
  --imatrix model.imatrix.gguf \
  model-f16.gguf \
  model-Q4_K_M-i.gguf \
  Q4_K_M
```

**Gain:** Q4_K_M + imatrix ≈ Q5_K_M without imatrix. IQ-series REQUIRES imatrix — IQ3_XXS without it produces catastrophic quality.

### Tier 3: APEX (MoE-aware mixed precision)

APEX classifies tensors by MoE role and applies different precision:

| Component | Sensitivity | APEX Quant | Why |
|-----------|:----------:|:----------:|-----|
| Shared Expert | CRITICAL | Q8_0 | Kurtosis 13.10 — heavy-tailed distribution |
| Routed Experts (128) | Low | IQ3_XXS | Rarely used, can compress aggressively |
| Attention (12 layers) | High | Q6_K | Affects every token |
| Embedding/Head | Medium | Q8_0 | Input/output layer |
| DeltaNet (36 layers) | Low | Q5_K | Linear attention, fewer errors |

Result: APEX I-Quality at 21 GB beats Q8_0 at 34 GB and even FP16 at 65 GB on downstream benchmarks.

**Quick path (recommended for one-off quantization):**

```bash
# 1. Convert HF model → F16 GGUF
python3 /home/user/dev/llama.cpp/convert_hf_to_gguf.py \
  /home/user/models/SuperQwen-bf16 --outtype f16 \
  --outfile /home/user/models/SuperQwen-f16.gguf

# 2. Generate imatrix (30-60 min)
/home/user/dev/llama.cpp/build/bin/llama-imatrix \
  -m /home/user/models/SuperQwen-f16.gguf \
  -f /home/user/dev/llama.cpp/tests/calibration_datasets/wikitext-2.txt \
  -o /home/user/models/SuperQwen.imatrix.gguf \
  --ctx-size 512 --chunks 500 -ngl 99

# 3. APEX I-Quality (auto-generates tensor-type config internally)
NUM_LAYERS=40 LLAMA_CPP_DIR=/home/user/dev/llama.cpp/build/bin \
  /home/user/dev/apex-quant/scripts/quantize.sh \
  --profile i-quality --layers 40 \
  --imatrix /home/user/models/SuperQwen.imatrix.gguf \
  /home/user/models/SuperQwen-f16.gguf \
  /home/user/models/SuperQwen-APEX-I-Quality.gguf
```

**`--layers 40` for Qwen3.5/Qwen3.6 MoE (AgentWorld, SuperQwen, Nex)** — confirmed via `config.json` → `num_hidden_layers`. NOT 48.

**`--profile i-quality`** (not `--i-quality`) — the quantize.sh flag syntax. Must also set `LLAMA_CPP_DIR` explicitly.

**`NUM_LAYERS=40` env var** sets the default layers count used by `generate_config.sh`.

**Full pipeline path** (for batch publishing to HF, with eval):

```bash
git clone https://github.com/localai-org/apex-quant.git
cd apex-quant
./apex_pipeline.sh \
  --config models/<model>.yaml \
  --profile I-Quality
```

APEX profiles: I-Quality (21 GB, max accuracy), Quality (21 GB, best PPL), I-Balanced (24 GB, min KL), I-Compact (16 GB, memory-constrained), Mini (12 GB, extreme).

## Calibration Datasets

### Science

arXiv 2405.20835: For modern LLMs (Llama-3+), calibration set has **diminishing effect** — K-quant methods are robust. Effect matters only at extreme low bits (2-3 bit).

### But for APEX and IQ-series — it matters

| Rule | Why |
|------|-----|
| Domain ≈ target task | Code calibration → better coding; wiki → better facts |
| Min 128 chunks × 2048 tokens | Less = underfit; much more = overfitting risk |
| Diversity > size | 1M tokens from 5 domains > 10M from one |
| NO random tokens | llama.cpp #5263: meaningful text > random |

### APEX I-variant mix

```
chat data     (~30%) — dialogues, instructions
code          (~25%) — Python, JS, shell
reasoning     (~25%) — chain-of-thought, math
tool-calling  (~20%) — JSON schema, function calls
```

**No Wikipedia** — downstream tasks (coding, reasoning) suffer from wiki calibration.

### Ready-to-use datasets

| Dataset | Size | Use case |
|---------|------|----------|
| `wikitext-2-raw-v1` (HF, parquet) | 2M tokens | General quality baseline |
| `eaddario/imatrix-calibration` (HF) | ~18M tokens | **Diverse mix (code+math+tools)** — best for APEX I-variants |
| `froggeric/imatrix` (HF) | ~100M tokens | Standard imatrix for K-quant |
| `dataset-build` (PyPI) | Generated | Diverse code + text |

**`eaddario/imatrix-calibration`** is the recommended calibration source for APEX. Contains `code_medium.parquet`, `tools_medium.parquet`, and `combined_math_code_medium.parquet`. Convert to plain text for imatrix:

```bash
hf download eaddario/imatrix-calibration --repo-type dataset \
  --include "*code*medium*" --include "*tools*medium*" \
  --local-dir ./imatrix-cal
# Parquet → text via pandas (use any venv with pandas/datasets):
python3 -c "
import pandas as pd
with open('calibration.txt','w') as f:
    for fn in ['code_medium.parquet','tools_medium.parquet','combined_math_code_medium.parquet']:
        df = pd.read_parquet(f'imatrix-cal/{fn}')
        for _, row in df.iterrows():
            t = str(row['content']).strip()
            if t: f.write(t + '\n\n')
"
```

### Downloading wikitext-2 (parquet format, June 2026)

The old zip URLs (S3, GitHub raw) are dead. Wikitext-2 is now parquet-only on HF. Use `datasets` library from any existing venv:

```bash
# Using jupyterlab or hermes venv
/path/to/venv/bin/python3 -c "
from datasets import load_dataset
ds = load_dataset('Salesforce/wikitext', 'wikitext-2-raw-v1', split='test')
with open('/home/user/models/eval-data/wikitext-2-raw/wiki.test.raw', 'w') as f:
    for item in ds:
        if item['text'].strip():
            f.write(item['text'].strip() + '\n')
"
```

Output: ~2891 lines, ~1.3 MB. This file can then be passed to `llama-perplexity -f` and `llama-imatrix -f`.

## Quality Evaluation

### 1. Perplexity (PPL) — basic metric

```bash
llama-perplexity \
  -m model-quant.gguf \
  -f /path/to/llama.cpp/tests/calibration_datasets/wikitext-2.txt \
  --ctx-size 512 \
  --chunks 500
```

| Δ PPL vs FP16 | Verdict |
|:---:|---------|
| < +0.02 | **Lossless** — indistinguishable |
| +0.02…0.10 | **Near-lossless** — production-ready |
| +0.10…0.30 | Noticeable but tolerable |
| > +0.30 | Significant degradation |

### 2. KL Divergence — probability distribution

```bash
llama-perplexity \
  -m model-quant.gguf \
  -f calibration.txt \
  --kl-divergence \
  --kl-divergence-base fp16-logits.bin \
  --ctx-size 512
```

| KL Divergence | Verdict |
|:---:|---------|
| < 0.005 | **Lossless** — Q8_0 level |
| 0.005–0.015 | **Excellent** — APEX I-Quality |
| 0.015–0.050 | **Good** — Q4_K_M level |
| > 0.100 | **Degraded** |

### 3. Downstream benchmarks — real tasks

```bash
llama-perplexity \
  -m model-quant.gguf \
  -f hellaswag_val.txt \
  --hellaswag --hellaswag-tasks 400 \
  --multiple-choice --multiple-choice-tasks 400
```

**Math (GSM8K) is the most sensitive to quantization.** Q3_K_S loses 9.32 points on GSM8K vs 0.64 on HellaSwag.

## Selective Precision Quantization (Manual APEX)

For cases where you want APEX-like mixed precision without the APEX tool:

```bash
# Create tensor-type-file
cat > /tmp/apex_tensors.txt << 'EOF'
blk.*.attn_q.weight q6_k
blk.*.attn_k.weight q6_k
blk.*.attn_v.weight q6_k
blk.*.attn_output.weight q6_k
output.weight q8_0
token_embd.weight q8_0
EOF

# Quantize with selective precision
llama-quantize \
  --tensor-type-file /tmp/apex_tensors.txt \
  --token-embedding-type q8_0 \
  --output-tensor-type q8_0 \
  model-f16.gguf \
  model-custom.gguf \
  Q4_K_M
```

## Quality Budget Framework

| Level | Δ Avg Score | When to use |
|-------|:---:|-------------|
| LOSSLESS | < 0.1 | Q8_0, APEX I-Quality — critical tasks |
| NEAR-LOSSLESS | 0.1–0.5 | Q5_K_M, Q4_K_M + imatrix — production |
| ACCEPTABLE | 0.5–1.5 | Q4_K_M no imatrix — dev/testing |
| DEGRADED | 1.5–4.0 | Q3_K_M — only if memory-critical |
| BROKEN | > 4.0 | Q3_K_S, IQ2 — avoid |

## IQ (Importance-aware Quantization) Series

IQ-series uses imatrix data differently from K-quants — it applies non-linear quantization that allocates more precision to important weights. **REQUIRES imatrix** — without it IQ3_XXS produces catastrophic quality.

| Quant | Bits | Size (vs F16) | Needs imatrix? |
|-------|:---:|:---:|:---:|
| IQ4_NL | ~4.5 | ~28% | Recommended |
| IQ4_XS | ~4.25 | ~26% | Recommended |
| IQ3_M | ~3.5 | ~22% | Required |
| IQ3_XXS | ~3.06 | ~19% | **MANDATORY** |
| IQ2_M | ~2.7 | ~17% | **MANDATORY** |
| IQ2_XS | ~2.31 | ~15% | **MANDATORY** |
| IQ2_XXS | ~2.06 | ~14% | **MANDATORY** |

## Full Recipe: Dense Model on DGX Spark

### Download BF16 weights (reliable curl method)

`hf download` often skips safetensors shards, only downloading metadata. Use `curl -C -` with a loop:

```bash
REPO="Jiunsong/SuperQwen-AgentWorld-35B-A3B-abliterated"
DEST="/home/user/models/SuperQwen-bf16"
BASE="https://huggingface.co/${REPO}/resolve/main"
mkdir -p "$DEST"

# Download metadata files first
for F in config.json tokenizer.json tokenizer_config.json chat_template.jinja \
         generation_config.json model.safetensors.index.json; do
  curl -sS -L "$BASE/$F" -o "$DEST/$F"
done

# Download safetensors shards (example: 21 shards for 35B model)
for i in $(seq -w 1 21); do
  echo "[$i/21] model-000${i}-of-00021.safetensors"
  curl -sS -L -C - "$BASE/model-000${i}-of-00021.safetensors" \
    -o "$DEST/model-000${i}-of-00021.safetensors"
done
```

Use `curl -sS` (not `-#`) — the progress bar requires a real TTY and kills background processes.

### Full pipeline

```bash
MODEL="meta-llama/Llama-4-Scout-17B-16E-Instruct"
OUTDIR="/home/user/models/quantized"
LLAMA="/home/user/dev/llama.cpp"
mkdir -p "$OUTDIR"

# 1. Download BF16
hf download "$MODEL" --local-dir "$OUTDIR/bf16"

# 2. Convert to F16 GGUF
python3 "$LLAMA/convert_hf_to_gguf.py" \
  "$OUTDIR/bf16" --outtype f16 \
  --outfile "$OUTDIR/model-f16.gguf"

# 3. Generate imatrix (30-60 min)
"$LLAMA/build/bin/llama-imatrix" \
  -m "$OUTDIR/model-f16.gguf" \
  -f "$LLAMA/tests/calibration_datasets/wikitext-2.txt" \
  -o "$OUTDIR/model.imatrix.gguf" \
  --ctx-size 512 --chunks 500 -ngl 99

# 4. Quantize
"$LLAMA/build/bin/llama-quantize" \
  --imatrix "$OUTDIR/model.imatrix.gguf" \
  "$OUTDIR/model-f16.gguf" \
  "$OUTDIR/model-Q4_K_M.gguf" \
  Q4_K_M

# 5. Verify
"$LLAMA/build/bin/llama-perplexity" \
  -m "$OUTDIR/model-Q4_K_M.gguf" \
  -f "$LLAMA/tests/calibration_datasets/wikitext-2.txt" \
  --ctx-size 512 --chunks 500

# 6. Cleanup (~70 GB freed)
rm "$OUTDIR/model-f16.gguf"
```

**Peak disk:** ~2.5× BF16 size (BF16 + F16 GGUF + quantized output ≈ 175 GB for 70 GB model). Pavel's DGX Spark has 2.2 TB free — not a concern.

## Operational Pitfalls

### MTP phantom layers in abliterated models

Abliterated Qwen models often have `mtp_num_hidden_layers: 1` in `config.json` but NO actual MTP weights. The converter extends `block_count` causing `llama-cli` to fail with "missing tensor blk.40.*". **Fix:** add `--no-mtp` to `convert_hf_to_gguf.py`.

Verify before converting:
```bash
python3 -c "
import json
with open('config.json') as f: c = json.load(f)
print('mtp_num_hidden_layers:', c.get('mtp_num_hidden_layers', 0))
with open('model.safetensors.index.json') as f: idx = json.load(f)
mtp = [k for k in idx['weight_map'] if 'mtp' in k.lower()]
print(f'MTP tensors in weight map: {len(mtp)}')
"
# If mtp_num_hidden_layers > 0 AND MTP tensors = 0 → add --no-mtp
```

### llama.cpp owned by root → clone fresh for Python scripts

When llama.cpp is in a root-owned directory (Docker-created), you can't `git pull` or edit conversion scripts. **Fix:** clone a fresh shallow copy for Python-only use:

```bash
git clone --depth 1 https://github.com/ggml-org/llama.cpp.git /home/user/tmp/llama.cpp-fresh
```

Use this clone ONLY for `convert_hf_to_gguf.py`. Keep the root-owned build for compiled binaries (`llama-quantize`, `llama-imatrix`, etc.).

### Parallel shard downloads → partial files

When downloading 21 shards in 3 parallel batches, some shards may be truncated (31 MB instead of 3.1 GB). These cause `ValueError: mmap length is greater than file size` during conversion. **Fix:** verify ALL shard sizes after parallel downloads:

```bash
for i in $(seq -w 01 21); do
  sz=$(stat -c%s "model-000${i}-of-00021.safetensors")
  echo "shard $i: $((sz/1024/1024)) MB"
done | grep -v "3... MB"  # highlight suspicious small shards
```

Delete truncated shards before re-downloading — `curl -C -` resume may not fix truncated files.

### `hf download --include` patterns

`hf download` silently skips files that don't match `--include` patterns. If you only included `*.safetensors`, you'll miss `tokenizer.json`, `tokenizer_config.json`, and `model.safetensors.index.json`. Always include all needed patterns or download metadata separately.

### Imatrix timing on DGX Spark (ARM64)

For Qwen3.5-35B-A3B MoE with 256K tokens (125 chunks × 2048 ctx) on DGX Spark (20-core ARM64 CPU, no GPU offload): **~23 minutes**. The 2-5 hour estimate applies to dense 70B models on 32-core x86. MoE models are faster because only 3B active parameters process each token during imatrix collection.

### Background processes killed by GUI restart

Hermes Desktop GUI kills background terminal processes on restart/navigation. **Workaround:** for critical long-running steps (imatrix, quantization), use foreground `terminal()` calls with a generous timeout. For multi-hour jobs, use a `cronjob` that survives GUI restarts.

### `quantize.sh` needs explicit `LLAMA_CPP_DIR`

The APEX `quantize.sh` script searches for `llama-quantize` in `./llama.cpp/build/bin` and `$LLAMA_CPP_DIR`. On Pavel's system where llama.cpp is at `/home/user/dev/llama.cpp/build/bin/`, auto-detection fails. Always set explicitly:

```bash
LLAMA_CPP_DIR=/home/user/dev/llama.cpp/build/bin bash scripts/quantize.sh --profile i-quality ...`
```

Also: `--profile i-quality` not `--i-quality`. And `NUM_LAYERS=40` must be set as env var (not `--layers` flag) for `generate_config.sh` to pick it up.

### Verified PPL Results (this session)

On SuperQwen-AgentWorld-35B-A3B-abliterated (Jiunsong), wikitext-2, ctx=512, DGX Spark:

| Model | Size | PPL | Notes |
|-------|:---:|:---:|-------|
| F16 GGUF | 65 GB | — | Reference (not measured, conversion artifacts retained) |
| **APEX I-Quality** | **22 GB** | **6.608** | 256K-token imatrix on code+math+tools corpus |
| Q4_K_M | 20 GB | 6.724 | Pre-quantized from Jiunsong, no calibration |

APEX I-Quality beats Q4_K_M by ΔPPL = −0.116 at +2 GB.
