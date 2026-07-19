# 256K Token Calibration Plan for MoE APEX Quantization

Pavel's research: 256K tokens of diverse calibration data for APEX I-variant quantization of MoE models (256 experts need full activation).

## Why 256K?

Standard APEX calibration is 50K tokens. For MoE with 256 experts (Qwen3.5/3.6, DeepSeek), 50K is insufficient — the router may not reach rare experts, causing `partial data` warnings in llama-imatrix. 256K tokens (~5× standard) ensures all experts get activation statistics.

**Upper bound:** Beyond 256K, returns diminish and overfitting risk increases.

## Corpus Composition

Equal 25% split across 4 domains, no Wikipedia:

| Domain | Share | Tokens | Source |
|--------|:-----:|:------:|--------|
| Multi-turn chat | 25% | ~64K | UltraChat / OpenHermes |
| Code | 25% | ~64K | eaddario/imatrix-calibration `code_medium` / The Stack |
| Reasoning (math/CoT) | 25% | ~64K | OpenMathInstruct / MetaMathQA |
| Tool-calling (JSON) | 25% | ~64K | xLAM / Hermes-Function-Calling |

**No Wikipedia** — I-variants deliberately avoid encyclopedia bias to maximize downstream accuracy gains.

**For agentic models (AgentWorld, tool-calling models):** increase FC share to 40%+ and convert all text to the model's native chat format (e.g. Qwen `<|im_start|>` tokens). See `references/agentic-calibration-corpus.md` for complete download + formatting script.

### FC Dataset Availability

| Dataset | Repo | Gated? | Format |
|---------|------|:------:|--------|
| Hermes FC v1 | `NousResearch/hermes-function-calling-v1` | No | conversations[] + tools[] (JSON string) |
| Glaive FC | `glaiveai/glaive-function-calling` | No | plain text "SYSTEM:... USER:... ASSISTANT:..." |
| xLAM FC 60k | `Salesforce/xlam-function-calling-60k` | **YES** | tools[] + query + answers[] |
| UltraChat 200k | `HuggingFaceH4/ultrachat_200k` | No | messages[] (role/content) |

**Pitfall:** Hermes FC `tools` field is a JSON string, not a list — must `json.loads()` first. Glaive FC uses plain text markers — must regex-split and reformat. See `references/agentic-calibration-corpus.md` for working code.

For multilingual models (Qwen family), add ~10-15% of Russian/Chinese to activate multilingual experts.

## Quick Start: eaddario/imatrix-calibration

Ready-made dataset on HF with code and tools subsets:

```bash
mkdir -p /home/user/models/imatrix-cal
hf download eaddario/imatrix-calibration \
  --repo-type dataset \
  --include "*code*medium*" --include "*tools*medium*" \
  --local-dir /home/user/models/imatrix-cal
```

Files come as parquet — convert to text:
```bash
cd /home/user/models/imatrix-cal
# Extracts 'content' column from parquet to plain text
pipx run duckdb -noheader -ascii -c "SELECT content FROM 'code_medium.parquet';" > code.txt
pipx run duckdb -noheader -ascii -c "SELECT content FROM 'tools_medium.parquet';" > tools.txt

# Merge (add chat and reasoning from other sources later)
cat code.txt tools.txt > calibration_256k.txt
```

Expected size: ~1.0-1.3 MB for 256K tokens (English text + code).

## llama-imatrix Command

```bash
/home/user/dev/llama.cpp/build/bin/llama-imatrix \
  -m model-f16.gguf \
  -f calibration_256k.txt \
  -o imatrix.gguf \
  -c 2048 \
  -b 512 \
  -t 32 \
  -ngl 0 \
  --chunks 125 \
  --output-frequency 10 \
  --save-frequency 50 \
  --process-output \
  2>&1 | tee imatrix_run.log
```

| Parameter | Value | Rationale |
|-----------|:-----:|-----------|
| `-c 2048` | native context | Minimum KL-divergence per kalomaze tests; 512 degrades attention tensors |
| `--chunks 125` | 125×2048≈256K | Exact token target |
| `-ngl 0` | CPU-only | MoE GPU-offload slower due to sync overhead per expert tensor |
| `-t 32` | physical cores | More threads don't accelerate due to collector lock |
| `--save-frequency 50` | checkpoint | On 2-5 hour run, losing all on crash is unacceptable |
| `--process-output` | collect output.weight | APEX I-Quality config touches output layer |

**Expected runtime:** 2-5 hours for 35B MoE on 32-core CPU workstation.

## Resume After Crash

```bash
llama-imatrix \
  -m model-f16.gguf \
  -f calibration_256k.txt \
  -o imatrix.gguf \
  --in-file imatrix.gguf.at_100 \
  --chunk 100 --chunks 25 \
  -c 2048 -t 32 -ngl 0 --process-output
```

`--in-file` accumulates statistics, correctly recomputing weighted averages via `ncall`.

## MoE Coverage Check

After imatrix completes:
```bash
grep -E "partial data|storing only|no data" imatrix_run.log
```

Interpretation:
- <5 experts missed from 256×48: acceptable, APEX falls back to uniform quant
- >10% experts missed: expand corpus with more code/tools, re-run with `--in-file`
- Entire layers missed: corpus composition problem, need more diverse domains

`eaddario` dataset activates more rare experts than hand-built corpora — preferred starting point.
