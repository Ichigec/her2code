---
name: llm-benchmark-evaluation
description: "Evaluate LLM quality across 6 axes: scientific code, tool use/function calling, agentic reasoning, general code generation, knowledge/reasoning, and safety. Full pipeline for vLLM OpenAI-compatible endpoints: lm-eval-harness, BFCL V4, EvalPlus, SciCode, τ-bench, HarmBench. Includes abliteration audit (original vs uncensored model comparison)."
version: 1.0.0
tags: [LLM, evaluation, benchmark, SciCode, BFCL, function-calling, tool-use, agentic, HarmBench, abliteration, vLLM, inspect-ai, tau-bench, EvalPlus]
related_skills: [evaluating-llms-harness, obliteratus, serving-llms-vllm, weights-and-biases]
---

# LLM Benchmark Evaluation

Evaluate LLM quality across 6 axes using a unified pipeline that works with any vLLM OpenAI-compatible endpoint.

## When to Use

Trigger when the user:
- Wants to "benchmark" or "evaluate" a model's quality
- Asks about SciCode, BFCL, function calling evaluation, tool use benchmarks
- Wants to compare models (original vs abliterated, quantized vs full precision)
- Needs to verify model quality after fine-tuning, quantization, or abliteration
- Asks "how good is this model" or "как проверить качество модели"
- Wants to run SWE-bench, τ-bench, HumanEval+, or similar benchmarks

## 6 Evaluation Axes

| Axis | What it measures | Primary benchmark | Runtime |
|------|-----------------|-------------------|---------|
| **Knowledge & Reasoning** | MMLU, GSM8K, ARC, IFEval | lm-eval-harness (200+ tasks) | ~30 min |
| **Tool Use / Function Calling** | Simple, parallel, multi-turn calls | BFCL V4 | ~20 min |
| **General Code** | Code generation with rigorous tests | EvalPlus (HumanEval+, MBPP+) | ~15 min |
| **Scientific Code** | Real research problems across 16 disciplines | SciCode (80 problems) | ~1 hour |
| **Agentic Reasoning** | Tool-agent-user dialogue with policies | τ-bench (airline, retail, telecom) | ~30 min |
| **Safety / Refusal** | Refusal rate on 400 harmful prompts | HarmBench | ~10 min |

## Pipeline

A working pipeline exists at `~/llm-benchmarks/` with 7 files (~1400 lines):
- `config.env` — model name, vLLM endpoint, benchmark selection
- `setup.sh` — one-time dependency installation + repo cloning
- `run_benchmarks.sh` — main runner with error handling and timing
- `collect_results.py` — aggregates all results into `summary.json` + `report.md`
- `harmbench_eval.py` — custom HarmBench refusal rate evaluation
- `compare_models.py` — abliteration audit (original vs modified model comparison)
- `README.md` — documentation

### Quick Start

```bash
cd ~/llm-benchmarks
./setup.sh                          # one-time install (~10 min)
# Edit config.env: set MODEL_NAME, MODEL_LABEL, VLLM_PORT
./run_benchmarks.sh all             # all 6 benchmarks
./run_benchmarks.sh lm_eval         # just basics (~30 min)
./run_benchmarks.sh lm_eval,bfcl,harmbench  # selective
```

### Running Individual Benchmarks

All benchmarks connect to vLLM via OpenAI-compatible API (`http://localhost:PORT/v1`).

#### 1. lm-eval-harness (Knowledge, Reasoning, Code, IF)
```bash
lm_eval --model local-chat-completions \
  --model_args "model=MODEL,base_url=http://localhost:8000/v1/chat/completions,num_concurrent=4" \
  --tasks mmlu,gsm8k,humaneval,arc_challenge,hellaswag,ifeval,truthfulqa_mc2,winogrande \
  --output_path ./results/ --log_samples --batch_size 4
```

Extended tasks: add `mmlu_pro,bigbench_hard,gpqa` for deeper evaluation (~2-3 hours).

#### 2. BFCL V4 (Function Calling / Tool Use)
```bash
pip install bfcl-eval

# If vLLM is already running (your case on DGX Spark):
# Set in .env: LOCAL_SERVER_ENDPOINT=localhost, LOCAL_SERVER_PORT=8000,
#   REMOTE_OPENAI_BASE_URL=http://localhost:8000/v1

bfcl generate --model MODEL-FC --test-category simple_python,parallel,live_multiple,multi_turn_base \
  --skip-server-setup
bfcl evaluate --model MODEL-FC

# Or let BFCL manage vLLM itself:
bfcl generate --model MODEL --backend vllm --num-gpus 1 --local-model-path /path/to/model
```

**FC mode**: append `-FC` suffix to model name for native function calling format.
**Non-FC mode**: model name without suffix, BFCL parses text output.

#### 3. EvalPlus (Rigorous Code Generation)
```bash
pip install evalplus
export OPENAI_API_KEY=dummy OPENAI_BASE_URL=http://localhost:8000/v1

evalplus.evaluate --model MODEL --dataset humaneval --backend openai --base-url http://localhost:8000/v1 -n 1
evalplus.evaluate --model MODEL --dataset mbpp --backend openai --base-url http://localhost:8000/v1 -n 1
```

HumanEval+ has 80x more tests than original HumanEval. MBPP+ has 35x more tests.

#### 4. SciCode (Scientific Code)
```bash
git clone https://github.com/scicode-bench/SciCode.git
cd SciCode && pip install -e .

# Download test_data.h5 from Google Drive:
# https://drive.google.com/drive/folders/1W5GZW6_bdiDAiipuFMqdUhvUaHIj6-pR
# Save as: ./eval/data/test_data.h5

cd eval/inspect_ai
inspect eval scicode.py --model openai/MODEL --base-url http://localhost:8000/v1 --temperature 0
```

SciCode uses `inspect_ai` framework — supports any OpenAI-compatible endpoint.
80 research problems → 338 subproblems across 16 scientific disciplines.
Even o3-mini solves only 10.8%. GPT-4o: 1.5%.

#### 5. τ-bench (Tool-Agent-User Interaction)
```bash
git clone https://github.com/sierra-research/tau2-bench
cd tau2-bench && uv sync

# Uses LiteLLM → any OpenAI-compatible endpoint
tau2 run --domain airline,retail,telecom \
  --agent-llm openai/MODEL --user-llm openai/MODEL \
  --num-trials 1 --num-tasks 10
```

τ³-bench (latest): adds voice full-duplex + knowledge retrieval (RAG) domains.
Results at [taubench.com](https://taubench.com).

#### 6. HarmBench (Safety / Refusal Rate)
Uses custom `harmbench_eval.py` script (in templates/). Sends 400 harmful prompts from `walledai/HarmBench` dataset, detects refusals via heuristic matching, reports per-category refusal rates.

```bash
python3 harmbench_eval.py
# Reads env vars: VLLM_BASE_URL, MODEL_NAME, MODEL_LABEL, RESULTS_DIR
```

## Abliteration Audit

Compare original vs abliterated model to measure collateral damage.

```bash
# 1. Run benchmarks on original model
MODEL_LABEL=original ./run_benchmarks.sh all

# 2. Switch vLLM to abliterated model, run same benchmarks
MODEL_LABEL=abliterated ./run_benchmarks.sh all

# 3. Compare
python3 compare_models.py original abliterated
```

Output shows:
- Per-metric delta (color-coded: red=degradation, green=improvement)
- Refusal rate change (should drop after abliteration)
- MMLU change (knowledge degradation check)
- Top degradations (collateral damage ranking)

### Key Research Finding (April 2026)

Abliteration is **NOT lossless** (source: Nathan Sapwell benchmark study):
- Bigger models suffer MORE collateral damage
- Heretic is the most consistent performer (least quality drop)
- HauhauCS "0 refusals" and "lossless" claims do NOT hold up
- Heretic is non-deterministic — different runs produce different results
- Methodology: lm-eval-harness with vLLM at bf16 + HarmBench 400 + KL divergence + weight analysis

## Results Collection

```bash
python3 collect_results.py MODEL_LABEL
```

Produces:
- `summary.json` — machine-readable JSON with all benchmark scores
- `report.md` — human-readable Markdown with tables
- `pipeline_status.log` — per-benchmark SUCCESS/FAILED + timing

## Benchmark Catalog

See `references/benchmark-catalog.md` for:
- Current SOTA scores for each benchmark (as of July 2026)
- Dataset sizes and test categories
- GitHub repos, papers, leaderboards
- 50+ additional benchmarks categorized by type (function calling, agentic, coding, GUI/web)

## Templates

- `templates/config.env` — starter configuration file
- `templates/harmbench_eval.py` — custom HarmBench evaluation script (400 prompts, refusal detection)
- `templates/compare_models.py` — abliteration audit comparison tool with color-coded output

## Pitfalls

1. **BFCL model naming**: FC mode requires `-FC` suffix. If FC mode fails, the script falls back to non-FC (text parsing). Check `SUPPORTED_MODELS.md` in gorilla repo for compatible model names.

2. **SciCode test data**: `test_data.h5` must be downloaded from Google Drive manually (gdown may fail). Without it, evaluation cannot run.

3. **τ-bench requires Python ≥3.12**: Uses `uv sync` instead of pip. If setup fails, try `uv sync --all-extras`.

4. **vLLM endpoint must be running**: All benchmarks depend on a live vLLM server. Verify with `curl http://localhost:8000/v1/models` before starting.

5. **BFCL `--skip-server-setup`**: Use this flag when vLLM is already running (DGX Spark case). Without it, BFCL tries to start its own vLLM instance, causing port conflicts.

6. **EvalPlus `--base-url`**: Some versions of EvalPlus don't support `--base-url` flag. Set `OPENAI_API_KEY` and `OPENAI_BASE_URL` environment variables instead.

7. **lm-eval `local-chat-completions` vs `local-completions`**: Use `local-chat-completions` for chat models (instruct-tuned). Use `local-completions` for base models (no chat template).

8. **HarmBench dataset loading**: The HuggingFace dataset name may vary (`walledai/HarmBench` vs `harmbench/harmbench_behaviors_text_test`). The script tries multiple names.

9. **Benchmark contamination**: For models that may have seen benchmark data during training, prefer contamination-free benchmarks: LiveCodeBench (code), LiveBench (general), BFCL live data (tool use).

## Complementary Skills

- **evaluating-llms-harness** — bundled skill for lm-eval-harness specifics
- **obliteratus** — abliteration procedure; use this skill for the quality audit AFTER abliteration
- **serving-llms-vllm** — vLLM server setup and configuration
- **weights-and-biases** — log benchmark results as W&B experiments for tracking
