# Self-Quantization Runbook — SuperQwen Session

Concrete runbook from the July 2026 session quantizing `Jiunsong/SuperQwen-AgentWorld-35B-A3B-abliterated` (BF16 → F16 GGUF → APEX I-Quality).

## Pre-requisites

- llama.cpp (root-owned pre-built binaries at `/home/user/dev/llama.cpp/build/bin/`)
- Fresh llama.cpp clone for conversion scripts: `/home/user/tmp/llama.cpp-fresh/`
- APEX quant: `/home/user/dev/apex-quant/` (clone from `localai-org/apex-quant`)
- Python with torch: `/home/user/jupyterlab/.venv/bin/python3`
- `hf` CLI at `~/.local/bin/hf` (v1.21.0+)
- 128 GB RAM (DGX Spark), ~220 GB free disk

## Step 1: Download BF16 weights

**NEVER use `hf download` for safetensors shards** — it only downloads metadata (config.json, README) and skips weights.

Reliable approach: curl loop with `-C -` (resume):

```bash
DEST="/home/user/models/SuperQwen-bf16"
BASE="https://huggingface.co/Jiunsong/SuperQwen-AgentWorld-35B-A3B-abliterated/resolve/main"
SHARDS=21
mkdir -p "$DEST"

# Parallel batches (4-5 shards each) to survive GUI restarts
for i in $(seq -w 1 $SHARDS); do
  F="model-000${i}-of-00021.safetensors"
  curl -sS -L -C - "$BASE/$F" -o "$DEST/$F" && echo "[$i/$SHARDS] OK" || echo "[$i/$SHARDS] FAIL"
done

# Don't forget tokenizer + config files!
curl -sS -L "$BASE/tokenizer.json" -o "$DEST/tokenizer.json"
curl -sS -L "$BASE/tokenizer_config.json" -o "$DEST/tokenizer_config.json"
curl -sS -L "$BASE/model.safetensors.index.json" -o "$DEST/model.safetensors.index.json"
```

**Verify integrity:** All shards should be ~3-3.7 GB. Shards < 1 GB are incomplete — delete and re-download.

```bash
for i in $(seq -w 01 21); do
  f="$DEST/model-000${i}-of-00021.safetensors"
  [ -f "$f" ] && echo "shard $i: $(( $(stat -c%s "$f") / 1024 / 1024 )) MB" || echo "shard $i: MISSING"
done
```

## Step 2: Convert BF16 → F16 GGUF

llama.cpp repo is root-owned → copy scripts to writable location:

```bash
mkdir -p /tmp/gguf-convert
cp /home/user/tmp/llama.cpp-fresh/convert_hf_to_gguf.py /tmp/gguf-convert/
cp -r /home/user/tmp/llama.cpp-fresh/conversion /tmp/gguf-convert/
cp -r /home/user/tmp/llama.cpp-fresh/gguf-py/gguf /tmp/gguf-convert/

# Patch base.py for version mismatch (target_model_dir, fp8_as_q8):
sed -i 's/fuse_gate_up_exps: bool = False)/fuse_gate_up_exps: bool = False, target_model_dir = None, fp8_as_q8 = False)/' \
  /tmp/gguf-convert/conversion/base.py

# Run conversion (needs torch — use jupyterlab venv):
cd /tmp/gguf-convert
/home/user/jupyterlab/.venv/bin/python3 convert_hf_to_gguf.py \
  /home/user/models/SuperQwen-bf16 \
  --outtype f16 \
  --outfile /home/user/models/SuperQwen-f16.gguf
```

Expected: ~65 GB, 733 tensors, ~2 minutes at 500 MB/s.

## Step 3: Generate importance matrix

### Option A: Basic corpus (code+tools+math, ~73MB)

```bash
# See calibration-256k-plan.md for corpus construction
/home/user/dev/llama.cpp/build/bin/llama-imatrix \
  -m /home/user/models/SuperQwen-f16.gguf \
  -f /home/user/models/imatrix-cal/calibration_combined.txt \
  -o /home/user/models/SuperQwen-imatrix.gguf \
  -c 2048 -b 512 -t 16 -ngl 0 \
  --chunks 125 --save-frequency 50 --process-output \
  2>&1 | tee /home/user/models/imatrix_run.log
```

### Option B: Agentic corpus (FC+chat+code+tools+math, ~19MB) — RECOMMENDED for AgentWorld

See `references/agentic-calibration-corpus.md` for full corpus construction guide.

```bash
/home/user/dev/llama.cpp/build/bin/llama-imatrix \
  -m /home/user/models/SuperQwen-f16.gguf \
  -f /home/user/models/imatrix-cal-v3/calibration_v3.txt \
  -o /home/user/models/SuperQwen-imatrix-v3.gguf \
  -c 2048 -b 512 -t 16 -ngl 0 \
  --chunks 125 --save-frequency 50 --process-output \
  2>&1 | tee /home/user/models/imatrix_v3_run.log
```

Expected: ~23 min (v1 basic corpus), ~47 min (v3 agentic corpus, slower due to swap pressure if Docker running). PPL on calibration text: v1 ~3.004, v3 ~3.349 (higher is normal — FC JSON is harder than code).

Check MoE coverage:
```bash
grep -E "partial data|storing only" imatrix_run.log
```

## Step 4: APEX I-Quality quantization

```bash
# CORRECT SYNTAX: --profile i-quality (NOT --i-quality)
# NUM_LAYERS=40 for SuperQwen (config.json: num_hidden_layers=40)
cd /home/user/dev/apex-quant
NUM_LAYERS=40 LLAMA_CPP_DIR=/home/user/dev/llama.cpp/build/bin \
  ./scripts/quantize.sh \
  --profile i-quality \
  --imatrix /home/user/models/SuperQwen-imatrix-v3.gguf \
  /home/user/models/SuperQwen-f16.gguf \
  /home/user/models/SuperQwen-APEX-I-Quality-v3.gguf
```

Expected: ~22 GB, ~6 minutes (379s on DGX Spark).

## Step 5: Create Q8_0 reference (for KL divergence)

```bash
# Q8_0 (35GB) is the safe KL reference — F16+APEX=87GB would OOM
/home/user/dev/llama.cpp/build/bin/llama-quantize \
  /home/user/models/SuperQwen-f16.gguf \
  /home/user/models/SuperQwen-Q8_0.gguf Q8_0
# ~2 minutes, 35 GB output
```

## Step 6: Evaluate (PPL + KL + HellaSwag + MMLU + ARC + speed)

### PPL only (ctx=2048, fast — 5-10 min per model)

```bash
cd /home/user/dev/apex-quant
PPL_CONTEXT=2048 PPL_GPU_LAYERS=99 ./scripts/perplexity.sh \
  /home/user/models/SuperQwen-APEX-I-Quality-v3.gguf \
  /home/user/.cache/apex-quant/eval-data/wiki.test.raw
```

### Full eval (PPL+KL+HS+WG+MMLU+ARC+speed — 10-15 min per model)

```bash
# MUST set EVAL_DATA_DIR explicitly (HOME is /home/user/.hermes/home under Hermes)
cd /home/user/dev/apex-quant
EVAL_DATA_DIR=/home/user/.cache/apex-quant/eval-data \
LLAMA_CPP_DIR=/home/user/dev/llama.cpp/build/bin \
  ./scripts/eval.sh \
  /home/user/models/SuperQwen-APEX-I-Quality-v3.gguf \
  --kl-reference /home/user/models/SuperQwen-Q8_0.gguf \
  --only ppl,kl,hellaswag,winogrande,mmlu,arc,speed \
  -o /tmp/eval_apex_v3.json
```

## Actual Results (July 2026 session)

SuperQwen-AgentWorld-35B-A3B-abliterated (abliterated + Supertune — PPL lower than reference Qwen3.5):

| Model | Size | PPL (ctx=2048) | HellaSwag | Winogrande | MMLU | ARC | tg128 t/s |
|-------|------|:---------:|:---------:|:----------:|:----:|:---:|:---------:|
| Q8_0 (reference) | 35 GB | 5.837 | — | — | — | — | — |
| APEX v1 (code+tools+math) | 22 GB | 5.868 | 82.75% | 75.50% | 42.38% | 54.52% | 38.54 |
| APEX v3 (FC+chat+code+tools+math) | 22 GB | 5.870 | 82.50% | 75.50% | 41.93% | 53.85% | 40.16 |
| Q4_K_M | 20 GB | 5.959 | — | — | — | — | — |

v1 and v3 are statistically identical (ΔPPL=0.002, within ±0.036 error). v3 slightly faster (+4.2% tg128).

## Pitfalls hit in this session

1. **`hf download` skips safetensors shards** — even with `--include "*.safetensors"`. Use curl.
2. **Missing tokenizer files** → `NotImplementedError: BPE pre-tokenizer was not recognized`. Always download `tokenizer.json`, `tokenizer_config.json`, `model.safetensors.index.json`.
3. **Damaged shards from interrupted downloads** → `ValueError: mmap length is greater than file size`. Verify all shard sizes before conversion. Re-download any shard < 3 GB.
4. **`target_model_dir` TypeError** → llama.cpp repo version mismatch. Patch `conversion/base.py` or use fresh clone.
5. **Root-owned llama.cpp** → copy scripts to /tmp, patch there, run from copy.
6. **Background processes killed by GUI restarts** → use foreground mode for conversions under 5 min. For imatrix (2-5 hours), consider cron job.
7. **Wikitext-2 zip dead** → use `datasets` library from jupyterlab venv to extract from parquet.
8. **`--i-quality` is WRONG syntax** → use `--profile i-quality`. The `quantize.sh` script accepts `--profile` (long form) only.
9. **`NUM_LAYERS=48` is WRONG for SuperQwen** → `config.json` says `num_hidden_layers: 40`. Always check the model's config, don't assume.
10. **eval.sh can't find wikitext under Hermes** → `HOME=/home/user/.hermes/home`, so `~/.cache/` resolves wrong. Pass `EVAL_DATA_DIR=/home/user/.cache/apex-quant/eval-data` explicitly. Also create wikitext-2-raw symlink.
11. **KL with F16 reference = OOM** → F16 (65GB) + APEX (22GB) = 87GB simultaneous load. Use Q8_0 (35GB) instead — PPL difference is 0.004.
12. **PPL + imatrix in parallel = swap thrash** → 65GB + 22GB = 87GB contention. Run sequentially.
13. **eaddario parquets are single-row** → 37MB of text in one row. Must chunk into ~2KB segments before sampling.
14. **xLAM is gated** → use Hermes FC + Glaive FC (ungated, 80k combined samples).
15. **`datasets` not installed** → `pip install --break-system-packages datasets pandas pyarrow` (PEP 668 on Ubuntu 24.04).
