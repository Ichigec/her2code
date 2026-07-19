# Model Merging and Surgery for MoE Models

**Date:** 2026-07-11
**Context:** Creating custom models from existing 35B MoE bases (AgentWorld, SuperQwen, Agents-A1) on DGX Spark 128GB

## How TIES and DARE Actually Work

Model merging uses **task vector arithmetic**: `task_vector = fine_tuned_model - base_model`. Each task vector encodes what the model learned during fine-tuning. Merge = combine task vectors and add to base.

### TIES-Merging (arXiv:2310.02384) — Three Steps

1. **Trim** — keep only top-k% parameters by magnitude per task vector (drop noise)
2. **Elect Sign** — for conflicting parameters (models disagree on sign), choose dominant sign by summed magnitude. E.g., A=+0.05 vs B=−0.03 → sign=+, value=(0.05−0.03)=+0.02
3. **Merge** — average only non-conflicting parameters, zero out conflicts

The `density` parameter (0.5–0.7) controls what fraction of parameters survive trimming. Higher density = more parameters retained = more interference risk but more signal.

### DARE (arXiv:2311.03079) — Drop And Rescale

1. **Drop** — randomly zero out fraction p (typically 0.9 = 90%) of each task vector's parameters
2. **Rescale** — multiply remaining 10% by `1/(1−p)` = 10× to preserve expected magnitude

Mathematically unbiased in expectation: E[rescaled] = original. Works because LLM parameters are **redundant** — most task vector params are noise. DARE removes noise randomly, TIES removes it intelligently.

**DARE-TIES** (most popular 2025–2026 combo): first DARE (random drop), then TIES (resolve conflicts among survivors).

### When to Use Which

| Method | Best for | Risk |
|--------|----------|------|
| TIES | Complementary models (different domains) | Over-pruning if density too low |
| DARE | Safe merge, many models | Random drop may remove critical params |
| DARE-TIES | Default choice, best of both | — |
| SLERP | Two-model smooth blend | Only works for 2 models |

---

## mergekit Methods

| Method | Description | Quality | Zero Compute? |
|---|---|---|:---:|
| TIES | Intelligent merge with conflict resolution (zero-out conflicting weights) | 🥇 | ✅ |
| DARE | Random drop + rescale conflicting weights | 🥈 | ✅ |
| SLERP | Spherical interpolation between two models | 🥈 | ✅ |
| Model Stock | Weighted average with anchor model | 🥈 | ✅ |
| Passthrough | Layer stacking (depth upscaling) | ⚠️ Needs CPT | ✅ |
| NuSLERP | Non-uniform SLERP | Experimental | ✅ |
| Model Breadcrumbs | Drop + rescale with noise threshold | 🥈 | ✅ |

### mergekit TIES Example (DGX Spark)

```yaml
# merge_agentworld_agents_a1.yml
merge_method: ties
dtype: bfloat16
models:
  - model: Jiunsong/SuperQwen-AgentWorld-35B-A3B
    parameters:
      density: 0.7
      weight: 0.6
  - model: huihui-ai/Huihui-Agents-A1-abliterated
    parameters:
      density: 0.5
      weight: 0.4
base_model: Qwen/Qwen3.5-35B-A3B
```

```bash
mergekit-yaml merge_agentworld_agents_a1.yml ./merged-model \
  --lazy-unpickle --copy-tokenizer --out-shard-size 5B
```

**Memory with lazy-unpickle:** ~8 GB peak RAM. DGX Spark 128GB is massively over-provisioned.

---

## MoE Limitations (CRITICAL)

### mergekit does NOT support qwen35moe

- **PR #696** is OPEN, not merged
- Qwen3.5 hybrid architecture (GatedDeltaNet + Attention, pattern LLLF) breaks standard merge paths
- Users report gibberish when trying basic Qwen3.5 merges
- `mergekit-moe` creates MoE FROM dense models — does NOT merge existing MoE models

### Workaround: Custom safetensors-level surgery

Qwen3.5-35B-A3B experts are stored as **fused tensors**:
- `gate_up_proj`: shape [262144, 2048] = 256 experts × 1024 rows each
- `down_proj`: shape [2048, 131072] = 256 experts × 512 columns each
- Expert #N: gate_up_proj[N*1024:(N+1)*1024, :]

**Weight prefix:** `model.language_model.layers.{i}.*` (NOT `model.layers.{i}.*` — Qwen3.5 is multimodal)

### Expert Transplant (conceptual)

```python
import safetensors.torch as st
import torch

model_a = st.load_file("agent_world_model-00001-of-00021.safetensors")
model_b = st.load_file("agents_a1_model-00001-of-00021.safetensors")

key = "model.language_model.layers.0.mlp.gate_up_proj"
experts_a = model_a[key]  # [262144, 2048]
experts_b = model_b[key]

# Transplant: 192 experts from A, 64 from B
merged = torch.cat([
    experts_a[:192*1024, :],
    experts_b[192*1024:256*1024, :]
], dim=0)  # same shape, transplanted weights
```

### Expert Cloning (to increase parameter count)

- +64 experts × 40 layers × 3.15M = +8.1B → ~41.7B
- +128 experts × 40 layers × 3.15M = +16.1B → ~49.7B
- **WARNING:** Cloned experts add ZERO diversity without retraining. Router must be programmatically expanded from [256, 2048] to [N, 2048].

### Layer Stacking (depth upscaling)

- Each Qwen3.5 layer ≈ 828M params
- +10 layers (one LLLF cycle + extra) = +8.3B → ~41.9B
- +15 layers = +12.4B → ~46.1B
- **CRITICAL:** Must maintain LLLF pattern (3 linear + 1 full attention). Random stacking breaks architecture.
- **CRITICAL:** Without continual pretraining, model generates garbage (SOLAR paper, Pretergeek data)

---

## Qwen3.5-35B-A3B Architecture Details

```
40 blocks (pattern LLLF × 10):
  30 × Linear Attention (GatedDeltaNet/SSM) — ~2M params each
  10 × Full Attention — ~23M params each

256 experts × 40 layers × 3.15M = 32.2B params (92% of total)
Shared Expert × 40 = 126M
Routers × 40 = 21M
Embedding (vocab 248,320 × 2048) = 508M
LM Head = 508M
Vision Tower (27-layer ViT) = ~300M
MTP head (1 layer, 256 experts) = ~790M
TOTAL: ~33.7B params
```

---

## Model Surgery Approaches Summary

| Approach | Resulting Size | Quality Without Training | Needs CPT? | Risk |
|---|---|---|:---:|:---:|
| TIES merge | 35B | Good | ❌ | 🟢 LOW |
| SLERP merge | 35B | Good | ❌ | 🟢 LOW |
| Passthrough (different models) | 38-46B | Moderate | ✅ 500M-1B tokens | 🟡 MED |
| Layer cloning (same model) | 38-46B | Garbage | ✅ 2-3B tokens | 🔴 HIGH |
| Expert cloning | 42-50B | Garbage | ✅ 1-2B tokens | 🟡 MED |
| Expert transplant | 35B | Good if router retrained | ✅ 200-500M tokens | 🟢 LOW |
| Hybrid (layers + experts) | 45-55B | Garbage | ✅ Significant training | 🔴 VERY HIGH |

---

## Recommended Path for DGX Spark 128GB

**Practical (lower risk):**
1. mergekit TIES: Agents-A1 + SuperQwen → merged 35B (0 compute, works immediately)
2. QLoRA distillation: cloud teacher → 25K examples → train on merged model (~20h)
3. Deploy via APEX GGUF → llama.cpp

**Ambitious (higher risk, needs validation):**
1. Custom safetensors surgery: transplant experts from AgentWorld + Agents-A1
2. Expand router programmatically
3. BAdam Full FT with continual pretraining (5-8 days minimum)
4. Extensive evaluation required

**NOT recommended:**
- Layer stacking on qwen35moe (no tooling, no evidence, breaks LLLF pattern)
- Expert cloning without extensive retraining
- Any structural modification without at least 200-500M tokens of continual training

---

## Sources

- mergekit: https://github.com/arcee-ai/mergekit
- mergekit PR #696 (Qwen3.5 MoE support): https://github.com/arcee-ai/mergekit/pull/696
- SOLAR paper: arXiv:2312.15166
- LLaMA Pro paper: arXiv:2401.02415
- Qwen3.5 config: HuggingFace API
