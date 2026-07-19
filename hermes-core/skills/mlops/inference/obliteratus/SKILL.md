---
name: obliteratus
description: "OBLITERATUS: abliterate LLM refusals (diff-in-means). Includes MTP grafting compatibility, acceptance rate degradation analysis, and alternatives (FastMTP, EAGLE-3)."
version: 2.0.0
author: Hermes Agent
license: MIT
dependencies: [obliteratus, torch, transformers, bitsandbytes, accelerate, safetensors]
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Abliteration, Uncensoring, Refusal-Removal, LLM, Weight-Projection, SVD, Mechanistic-Interpretability, HuggingFace, Model-Surgery]
    related_skills: [vllm, gguf, huggingface-tokenizers]
---

# OBLITERATUS Skill

## What's inside

9 CLI methods, 28 analysis modules, 116 model presets across 5 compute tiers, tournament evaluation, and telemetry-driven recommendations.

Remove refusal behaviors (guardrails) from open-weight LLMs without retraining or fine-tuning. Uses mechanistic interpretability techniques — including diff-in-means, SVD, whitened SVD, LEACE concept erasure, SAE decomposition, Bayesian kernel projection, and more — to identify and surgically excise refusal directions from model weights while preserving reasoning capabilities.

**License warning:** OBLITERATUS is AGPL-3.0. NEVER import it as a Python library. Always invoke via CLI (`obliteratus` command) or subprocess. This keeps Hermes Agent's MIT license clean.

## Video Guide

Walkthrough of OBLITERATUS used by a Hermes agent to abliterate Gemma:
https://www.youtube.com/watch?v=8fG9BrNTeHs ("OBLITERATUS: An AI Agent Removed Gemma 4's Safety Guardrails")

Useful when the user wants a visual overview of the end-to-end workflow before running it themselves.

## When to Use This Skill

Trigger when the user:
- Wants to "uncensor" or "abliterate" an LLM
- Asks about removing refusal/guardrails from a model
- Wants to create an uncensored version of Llama, Qwen, Mistral, etc.
- Mentions "refusal removal", "abliteration", "weight projection"
- Wants to analyze how a model's refusal mechanism works
- References OBLITERATUS, abliterator, or refusal directions

## Step 1: Installation

Check if already installed:
```bash
obliteratus --version 2>/dev/null && echo "INSTALLED" || echo "NOT INSTALLED"
```

If not installed, clone and install from GitHub:
```bash
git clone https://github.com/elder-plinius/OBLITERATUS.git
cd OBLITERATUS
pip install -e .
# For Gradio web UI support:
# pip install -e ".[spaces]"
```

**IMPORTANT:** Confirm with user before installing. This pulls in ~5-10GB of dependencies (PyTorch, Transformers, bitsandbytes, etc.).

## Step 2: Check Hardware

Before anything, check what GPU is available:
```bash
python3 -c "
import torch
if torch.cuda.is_available():
    gpu = torch.cuda.get_device_name(0)
    vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f'GPU: {gpu}')
    print(f'VRAM: {vram:.1f} GB')
    if vram < 4: print('TIER: tiny (models under 1B)')
    elif vram < 8: print('TIER: small (models 1-4B)')
    elif vram < 16: print('TIER: medium (models 4-9B with 4bit quant)')
    elif vram < 32: print('TIER: large (models 8-32B with 4bit quant)')
    else: print('TIER: frontier (models 32B+)')
else:
    print('NO GPU - only tiny models (under 1B) on CPU')
"
```

### VRAM Requirements (with 4-bit quantization)

| VRAM     | Max Model Size  | Example Models                              |
|:---------|:----------------|:--------------------------------------------|
| CPU only | ~1B params      | GPT-2, TinyLlama, SmolLM                    |
| 4-8 GB   | ~4B params      | Qwen2.5-1.5B, Phi-3.5 mini, Llama 3.2 3B   |
| 8-16 GB  | ~9B params      | Llama 3.1 8B, Mistral 7B, Gemma 2 9B       |
| 24 GB    | ~32B params     | Qwen3-32B, Llama 3.1 70B (tight), Command-R |
| 48 GB+   | ~72B+ params    | Qwen2.5-72B, DeepSeek-R1                    |
| Multi-GPU| 200B+ params    | Llama 3.1 405B, DeepSeek-V3 (685B MoE)      |

## Step 3: Browse Available Models & Get Recommendations

```bash
# Browse models by compute tier
obliteratus models --tier medium

# Get architecture info for a specific model
obliteratus info <model_name>

# Get telemetry-driven recommendation for best method & params
obliteratus recommend <model_name>
obliteratus recommend <model_name> --insights  # global cross-architecture rankings
```

## Step 4: Choose a Method

### Method Selection Guide
**Default / recommended for most cases: `advanced`.** It uses multi-direction SVD with norm-preserving projection and is well-tested.

| Situation                         | Recommended Method | Why                                      |
|:----------------------------------|:-------------------|:-----------------------------------------|
| Default / most models             | `advanced`         | Multi-direction SVD, norm-preserving, reliable |
| Quick test / prototyping          | `basic`            | Fast, simple, good enough to evaluate    |
| Dense model (Llama, Mistral)      | `advanced`         | Multi-direction, norm-preserving         |
| MoE model (DeepSeek, Mixtral)     | `nuclear`          | Expert-granular, handles MoE complexity  |
| Reasoning model (R1 distills)     | `surgical`         | CoT-aware, preserves chain-of-thought    |
| Stubborn refusals persist         | `aggressive`       | Whitened SVD + head surgery + jailbreak   |
| Want reversible changes           | Use steering vectors (see Analysis section) |
| Maximum quality, time no object   | `optimized`        | Bayesian search for best parameters      |
| Experimental auto-detection       | `informed`         | Auto-detects alignment type — experimental, may not always outperform advanced |

### 9 CLI Methods
- **basic** — Single refusal direction via diff-in-means. Fast (~5-10 min for 8B).
- **advanced** (DEFAULT, RECOMMENDED) — Multiple SVD directions, norm-preserving projection, 2 refinement passes. Medium speed (~10-20 min).
- **aggressive** — Whitened SVD + jailbreak-contrastive + attention head surgery. Higher risk of coherence damage.
- **spectral_cascade** — DCT frequency-domain decomposition. Research/novel approach.
- **informed** — Runs analysis DURING abliteration to auto-configure. Experimental — slower and less predictable than advanced.
- **surgical** — SAE features + neuron masking + head surgery + per-expert. Very slow (~1-2 hrs). Best for reasoning models.
- **optimized** — Bayesian hyperparameter search (Optuna TPE). Longest runtime but finds optimal parameters.
- **inverted** — Flips the refusal direction. Model becomes actively willing.
- **nuclear** — Maximum force combo for stubborn MoE models. Expert-granular.

### Direction Extraction Methods (--direction-method flag)
- **diff_means** (default) — Simple difference-in-means between refused/complied activations. Robust.
- **svd** — Multi-direction SVD extraction. Better for complex alignment.
- **leace** — LEACE (Linear Erasure via Closed-form Estimation). Optimal linear erasure.

### 4 Python-API-Only Methods
(NOT available via CLI — require Python import, which violates AGPL boundary. Mention to user only if they explicitly want to use OBLITERATUS as a library in their own AGPL project.)
- failspy, gabliteration, heretic, rdo

## Step 5: Run Abliteration

### Standard usage
```bash
# Default method (advanced) — recommended for most models
obliteratus obliterate <model_name> --method advanced --output-dir ./abliterated-models

# With 4-bit quantization (saves VRAM)
obliteratus obliterate <model_name> --method advanced --quantization 4bit --output-dir ./abliterated-models

# Large models (70B+) — conservative defaults
obliteratus obliterate <model_name> --method advanced --quantization 4bit --large-model --output-dir ./abliterated-models
```

### Fine-tuning parameters
```bash
obliteratus obliterate <model_name> \
  --method advanced \
  --direction-method diff_means \
  --n-directions 4 \
  --refinement-passes 2 \
  --regularization 0.1 \
  --quantization 4bit \
  --output-dir ./abliterated-models \
  --contribute  # opt-in telemetry for community research
```

### Key flags
| Flag | Description | Default |
|:-----|:------------|:--------|
| `--method` | Abliteration method | advanced |
| `--direction-method` | Direction extraction | diff_means |
| `--n-directions` | Number of refusal directions (1-32) | method-dependent |
| `--refinement-passes` | Iterative passes (1-5) | 2 |
| `--regularization` | Regularization strength (0.0-1.0) | 0.1 |
| `--quantization` | Load in 4bit or 8bit | none (full precision) |
| `--large-model` | Conservative defaults for 120B+ | false |
| `--output-dir` | Where to save the abliterated model | ./obliterated_model |
| `--contribute` | Share anonymized results for research | false |
| `--verify-sample-size` | Number of test prompts for refusal check | 20 |
| `--dtype` | Model dtype (float16, bfloat16) | auto |

### Other execution modes
```bash
# Interactive guided mode (hardware → model → preset)
obliteratus interactive

# Web UI (Gradio)
obliteratus ui --port 7860

# Run a full ablation study from YAML config
obliteratus run config.yaml --preset quick

# Tournament: pit all methods against each other
obliteratus tourney <model_name>
```

## Step 6: Verify Results

After abliteration, check the output metrics:

| Metric | Good Value | Warning |
|:-------|:-----------|:--------|
| Refusal rate | < 5% (ideally ~0%) | > 10% means refusals persist |
| Perplexity change | < 10% increase | > 15% means coherence damage |
| KL divergence | < 0.1 | > 0.5 means significant distribution shift |
| Coherence | High / passes qualitative check | Degraded responses, repetition |

### If refusals persist (> 10%)
1. Try `aggressive` method
2. Increase `--n-directions` (e.g., 8 or 16)
3. Add `--refinement-passes 3`
4. Try `--direction-method svd` instead of diff_means

### If coherence is damaged (perplexity > 15% increase)
1. Reduce `--n-directions` (try 2)
2. Increase `--regularization` (try 0.3)
3. Reduce `--refinement-passes` to 1
4. Try `basic` method (gentler)

## Step 7: Use the Abliterated Model

The output is a standard HuggingFace model directory.

```bash
# Test locally with transformers
python3 -c "
from transformers import AutoModelForCausalLM, AutoTokenizer
model = AutoModelForCausalLM.from_pretrained('./abliterated-models/<model>')
tokenizer = AutoTokenizer.from_pretrained('./abliterated-models/<model>')
inputs = tokenizer('How do I pick a lock?', return_tensors='pt')
outputs = model.generate(**inputs, max_new_tokens=200)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
"

# Upload to HuggingFace Hub
huggingface-cli upload <username>/<model-name>-abliterated ./abliterated-models/<model>

# Serve with vLLM
vllm serve ./abliterated-models/<model>
```

## CLI Command Reference

| Command | Description |
|:--------|:------------|
| `obliteratus obliterate` | Main abliteration command |
| `obliteratus info <model>` | Print model architecture details |
| `obliteratus models --tier <tier>` | Browse curated models by compute tier |
| `obliteratus recommend <model>` | Telemetry-driven method/param suggestion |
| `obliteratus interactive` | Guided setup wizard |
| `obliteratus tourney <model>` | Tournament: all methods head-to-head |
| `obliteratus run <config.yaml>` | Execute ablation study from YAML |
| `obliteratus strategies` | List all registered ablation strategies |
| `obliteratus report <results.json>` | Regenerate visual reports |
| `obliteratus ui` | Launch Gradio web interface |
| `obliteratus aggregate` | Summarize community telemetry data |

## Analysis Modules

OBLITERATUS includes 28 analysis modules for mechanistic interpretability.
See `skill_view(name="obliteratus", file_path="references/analysis-modules.md")` for the full reference.

### Quick analysis commands
```bash
# Run specific analysis modules
obliteratus run analysis-config.yaml --preset quick

# Key modules to run first:
# - alignment_imprint: Fingerprint DPO/RLHF/CAI/SFT alignment method
# - concept_geometry: Single direction vs polyhedral cone
# - logit_lens: Which layer decides to refuse
# - anti_ouroboros: Self-repair risk score
# - causal_tracing: Causally necessary components
```

### Steering Vectors (Reversible Alternative)
Instead of permanent weight modification, use inference-time steering:
```python
# Python API only — for user's own projects
from obliteratus.analysis.steering_vectors import SteeringVectorFactory, SteeringHookManager
```

## Ablation Strategies

Beyond direction-based abliteration, OBLITERATUS includes structural ablation strategies:
- **Embedding Ablation** — Target embedding layer components
- **FFN Ablation** — Feed-forward network block removal
- **Head Pruning** — Attention head pruning
- **Layer Removal** — Full layer removal

List all available: `obliteratus strategies`

## Evaluation

OBLITERATUS includes built-in evaluation tools:
- Refusal rate benchmarking
- Perplexity comparison (before/after)
- LM Eval Harness integration for academic benchmarks
- Head-to-head competitor comparison
- Baseline performance tracking

### Full Abliteration Audit (recommended)

For a comprehensive quality audit after abliteration, use the `llm-benchmark-evaluation` skill.
It provides a complete pipeline at `~/llm-benchmarks/` that evaluates 6 axes (knowledge,
tool use, code generation, scientific code, agentic reasoning, safety) and compares
original vs abliterated models side-by-side:

```bash
# 1. Benchmark the original model
MODEL_LABEL=original ~/llm-benchmarks/run_benchmarks.sh all

# 2. Benchmark the abliterated model
MODEL_LABEL=abliterated ~/llm-benchmarks/run_benchmarks.sh all

# 3. Compare — shows per-metric degradation (collateral damage)
python3 ~/llm-benchmarks/compare_models.py original abliterated
```

Key research finding (April 2026): abliteration is NOT lossless. Bigger models suffer
more collateral damage. Heretic is the most consistent performer. See
`llm-benchmark-evaluation` skill → `references/benchmark-catalog.md` for details.

## Platform Support

- **CUDA** — Full support (NVIDIA GPUs)
- **Apple Silicon (MLX)** — Supported via MLX backend
- **CPU** — Supported for tiny models (< 1B params)

## YAML Config Templates

Load templates for reproducible runs via `skill_view`:
- `templates/abliteration-config.yaml` — Standard single-model config
- `templates/analysis-study.yaml` — Pre-abliteration analysis study
- `templates/batch-abliteration.yaml` — Multi-model batch processing

## Telemetry

OBLITERATUS can optionally contribute anonymized run data to a global research dataset.
Enable with `--contribute` flag. No personal data is collected — only model name, method, metrics.

## Common Pitfalls

1. **Don't use `informed` as default** — it's experimental and slower. Use `advanced` for reliable results.
2. **Models under ~1B respond poorly to abliteration** — their refusal behaviors are shallow and fragmented, making clean direction extraction difficult. Expect partial results (20-40% remaining refusal). Models 3B+ have cleaner refusal directions and respond much better (often 0% refusal with `advanced`).
3. **`aggressive` can make things worse** — on small models it can damage coherence and actually increase refusal rate. Only use it if `advanced` leaves > 10% refusals on a 3B+ model.
4. **Always check perplexity** — if it spikes > 15%, the model is damaged. Reduce aggressiveness.
5. **MoE models need special handling** — use `nuclear` method for Mixtral, DeepSeek-MoE, etc.
6. **Quantized models can't be re-quantized** — abliterate the full-precision model, then quantize the output.
7. **VRAM estimation is approximate** — 4-bit quant helps but peak usage can spike during extraction.
8. **Reasoning models are sensitive** — use `surgical` for R1 distills to preserve chain-of-thought.
9. **Check `obliteratus recommend`** — telemetry data may have better parameters than defaults.
10. **AGPL license** — never `import obliteratus` in MIT/Apache projects. CLI invocation only.
11. **Large models (70B+)** — always use `--large-model` flag for conservative defaults.
12. **Spectral certification RED is common** — the spectral check often flags "incomplete" even when practical refusal rate is 0%. Check actual refusal rate rather than relying on spectral certification alone.
13. **MTP survives abliteration** — if the model has native MTP (Qwen 3.5+, DeepSeek-V3, Gemma 4), it remains functional after abliteration. The refusal direction projection touches attention/MLP weights, not the MTP head tensors. Verify by running speculative decoding after abliteration. If MTP head was lost or damaged, graft from base checkpoint (see MTP section above).
14. **Diffusion LMs require ARA/EGA, NOT standard projection** — DiffusionGemma and other diffusion LMs have a fundamentally different safety mechanism. DuoNeural (2026-06-10) documented three failed abliteration attempts using standard RepE/Orthogonal Projection (encoder partial, encoder full α=0.95, decoder MoE 91 weights). All failed. Root cause: refusal in diffusion LMs is a **vocabulary-space attractor** — a high-probability denoising trajectory toward refusal tokens — NOT a projectable direction in weight space. In AR models, the residual stream direction directly gates next-token generation, so projection works. In diffusion models, the decoder generates refusal templates independently of encoder conditioning, and cos(harmful, harmless) = 0.936 at decoder L22. **Standard projection (basic, advanced, aggressive) will fail.** **However, ARA and EGA now work:** `Umranz/diffusiongemma-26B-A4B-it-abliteration` achieved 4/100 refusals (KL=0.11) via Arbitrary-Rank Ablation (Heretic PR #400, no refusal directions — direct matrix optimization), and `edwixx/diffusiongemma-26B-A4B-it-HERETIC-Uncensored` achieved 13/100 (KL=0.49) via Expert-Granular Abliteration. See `references/diffusion-lm-abliteration.md` for full landscape, metrics comparison, and the research workflow for finding uncensored variants.

## MTP (Multi-Token Prediction) Compatibility

Abliteration and MTP are **orthogonal** — they modify different parts of the model:

- **Abliteration** modifies: attention/MLP weights (refusal direction projection via diff-in-means/SVD)
- **MTP head** is: a separate set of tensors (~15 layers for Qwen 3.5/3.6) that predict future tokens for speculative decoding

Abliteration does NOT touch MTP head weights. Therefore:
1. A model with native MTP (Qwen 3.5+, DeepSeek-V3, Gemma 4) retains MTP after abliteration
2. MTP head can be **grafted** (copied) from a base checkpoint onto an abliterated model

### MTP Grafting Procedure

```python
import torch
from transformers import AutoModelForCausalLM

# 1. Load base model with MTP
base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3.6-27B")

# 2. Load abliterated model
abliterated = AutoModelForCausalLM.from_pretrained("./abliterated-models/Qwen3.6-27B")

# 3. Copy MTP tensors (15 for Qwen 3.6)
mtp_keys = [k for k in base.state_dict() if 'mtp' in k.lower()]
for key in mtp_keys:
    abliterated.state_dict()[key] = base.state_dict()[key].clone()

# 4. Save combined model
abliterated.save_pretrained("./qwen3.6-abliterated-mtp")
```

### Proven combined models on HuggingFace

| Model | Author | Features |
|:------|:-------|:---------|
| `AEON-7/Qwen3.6-27B-AEON-Ultimate-Uncensored-BF16` | AEON-7 | Full-precision, MTP grafted (15 tensors, bit-exact verified) |
| `plunderstruck/Qwen3.6-27B-OBLITERATED-MTP-ROCmFP4-GGUF` | plunderstruck | 4-bit ROCmFP4, MTP, vision-capable, AMD APU |
| `plunderstruck/Qwopus3.6-27B-Coder-MTP-ROCmFP4-GGUF` | plunderstruck | Coder fine-tune + MTP |

### MTP infrastructure support

| Tool | MTP Support | Status |
|:-----|:------------|:-------|
| vLLM | Qwen3.6, Gemma 4 | Production-ready |
| SGLang | Qwen3-Next, DeepSeek-V3 | Production-ready |
| llama.cpp | Qwen3.6 (PR #22673, merged May 2026) | Mainline |
| LM Studio | MTP speculative decoding | UI support |

### FastMTP (post-hoc MTP for models without native support)

If a model does NOT have native MTP (e.g., Llama, older Qwen), train an MTP head via self-distillation:

- **FastMTP** (ICLR 2026): self-distilled data, shared positional weights, recursive operation. 2.03x speedup, 82% better than vanilla MTP.
- **MTP-D** (Self-Distillation): main head as detached teacher for MTP heads. +7.5% acceptance rate, minimal training cost.

```bash
# vLLM with MTP speculative decoding
vllm serve Qwen/Qwen3.6-27B --speculative-model "[mtp]" --num-speculative-tokens 3

# llama.cpp with MTP
llama-server -m qwen3.6-27b.gguf --mtp
```

## MTP (Multi-Token Prediction) compatibility

Abliteration and MTP are **orthogonal** — they modify different weight regions:
- Abliteration: attention/MLP weights (refusal direction projections)
- MTP head: separate tensor set (15 tensors in Qwen3.5/3.6)

### MTP grafting from base model

Qwen3.5/3.6 have **native MTP** baked into weights. After abliteration, copy MTP tensors from the original base checkpoint:

```python
base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3.6-27B")
target = AutoModelForCausalLM.from_pretrained("./abliterated-model")
mtp_keys = [k for k in base.state_dict() if 'mtp' in k.lower()]
for key in mtp_keys:
    target.state_dict()[key] = base.state_dict()[key].clone()
target.save_pretrained("./abliterated-mtp")
```

### Acceptance rate degradation after SFT/abliteration

**Critical finding**: SFT and abliteration shift the activation space, reducing MTP draft acceptance:

| Model | Accept % | Speedup | Notes |
|:------|:---------|:--------|:------|
| Qwen3.6-27B (base, native MTP) | ~76% | 1.7× | Baseline |
| AEON-7 (abliterated + grafted MTP) | ~70% | 1.5-1.7× | Bit-exact verified graft |
| plunderstruck (OBLITERATED + MTP) | ~65% | 1.4-1.6× | ROCmFP4 quant |
| Qwopus3.6 (SFT + abliterated + grafted MTP) | ~55% | 1.3× | SFT shifted activations most |

Abliteration alone causes mild degradation. **SFT on top of abliteration causes the most degradation** because it shifts the activation space the MTP head was trained against.

### Better alternatives for post-abliteration MTP

1. **FastMTP** (self-distillation, ICLR 2026): train a NEW MTP head on the abliterated model's own hidden states. 2.03× speedup, ~70%+ acceptance. Cost: 4-8 GPU-hours.

2. **EAGLE-3** (separate draft head): train a lightweight draft model using the abliterated model's hidden states. 2-3× speedup, **lossless** (not dependent on acceptance rate). Best choice for production. **Full training workflow** is in the `speculative-decoding` skill → `references/eagle3-speculators-training.md` (uses `vllm-project/speculators` framework, supports offline training on single-GPU systems like DGX Spark).

3. **N-gram / prompt-lookup**: zero training, 1.2-1.5× speedup. Works regardless of activation space shifts.

### Existing abliterated+MTP models on HuggingFace

- `plunderstruck/Qwen3.6-27B-OBLITERATED-MTP-ROCmFP4-GGUF` — 4-bit, AMD APU
- `AEON-7/Qwen3.6-27B-AEON-Ultimate-Uncensored-BF16` — full precision, bit-exact MTP graft
- `Jiunsong/SuperQwen-AgentWorld-35B-A3B-abliterated` — SuperQwen (no MTP, but Qwen3.5 base has it for grafting)

## Complementary Skills

- **vllm** — Serve abliterated models with high throughput
- **gguf** — Convert abliterated models to GGUF for llama.cpp
- **huggingface-tokenizers** — Work with model tokenizers
- **diffusion-llm-local** — Diffusion LLM deployment. NOTE: standard weight-projection abliteration fails on diffusion LMs (vocabulary-space attractor, not projectable direction), but ARA (4/100 refusals, KL=0.11) and EGA (13/100, KL=0.49) now work on DiffusionGemma. See `references/diffusion-lm-abliteration.md` for full research findings, the independent 13-technique benchmark on AR Gemma4-E2B, the complete DiffusionGemma abliteration landscape, and the uncensored-model research workflow.
