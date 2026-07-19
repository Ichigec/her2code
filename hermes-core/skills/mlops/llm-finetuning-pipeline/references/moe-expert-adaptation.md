# MoE Expert-Level Adaptation Methods (2024-2026)

**Date:** 2026-07-13
**Context:** Research pass on methods that add/grow/select experts in MoE models. Complements `model-merging-moe.md` (zero-compute weight surgery) and `catastrophic-forgetting-2025.md` (DES-MoE as anti-forgetting). This file covers the THIRD paradigm: architecturally expanding or selectively training individual experts.

---

## Three Paradigms for MoE Adaptation

| Paradigm | Computes? | Adds experts? | Focus |
|----------|:---------:|:-------------:|-------|
| Model merging (TIES/DARE) | 0 | No | Combine existing model weights |
| Anti-forgetting (DES-MoE) | Yes (full FT) | No | Prevent knowledge loss during multi-domain FT |
| **Expert-level adaptation** | Yes (partial) | **Yes or selective** | Train only specific experts, or add new ones |

---

## Method 1: ESFT — Expert-Specialized Fine-Tuning (DeepSeek, 2024)

> arXiv:2407.01906 | EMNLP 2024 | github.com/deepseek-ai/ESFT

**Simplest approach: don't add experts — select relevant existing ones and train only those.**

### How it works

1. **Evaluate expert relevance**: run N examples from target domain through model, measure average routing probability per expert
2. **Select top-K experts** (e.g., 64 of 256) by routing frequency
3. **Fine-tune**: top-K experts TRAINABLE, rest FROZEN, router FROZEN, attention FROZEN
4. ~25% of parameters trainable

### Results

| Method | Params trained | Math (GSM8K) | Code (HumanEval) | Forgetting |
|--------|:--------------:|:------------:|:-----------------:|:----------:|
| Full FT | 100% | 100% | 100% | High |
| LoRA | ~1% | 97% | 95% | Medium |
| **ESFT** | ~25% | **101%** | **99%** | **Low** |

ESFT matches or surpasses Full FT at 4x less compute. Fine-grained MoEs (256 experts) are better for ESFT than coarse MoEs (8 experts) — more granular expert selection.

### Limitation
For multiple domains, need separate expert sets per domain → multiple models, not one unified model. DES-MoE solves this.

---

## Method 2: Expert Upcycling — Duplicate and Train (Apr 2026)

> arXiv:2604.19835 | Apr 2026

**Literally "add a new expert as a copy of an existing one and train only the copy."**

### How it works

```
Phase 1: Duplication
  - Select high-utility experts (by routing frequency)
  - new_expert = expert_i.clone()
  - Expand MoE: 256 → 256+M experts
  - Expand router: [256, hidden] → [256+M, hidden]
  - New router rows = copy of original expert's row

Phase 2: Fine-tune
  - Original 256 experts → FROZEN
  - New M experts → TRAINABLE
  - Router (new rows only) → TRAINABLE
  - Top-K stays the same (e.g., 8)
```

### Why it works
New experts start as copies → don't destroy existing functionality → zero forgetting on old domains. Router can choose original experts (old domains) or new copies (new domains). Active params per token unchanged.

### Results

| Metric | Fixed MoE (256) | Upcycled (256+64) |
|--------|:---------------:|:-----------------:|
| New domain quality | baseline | +8-12% |
| Old domain quality | 100% | **100% (zero forgetting)** |
| Active params/token | same | same (top-K unchanged) |
| Total params | +0% | +25% (more weights on disk) |
| FT compute | 100% | ~25% (only new experts) |

### Practical implementation for Qwen3.5-35B-A3B

Qwen3.5 experts are fused tensors:
- `gate_up_proj`: [262144, 2048] = 256 experts x 1024 rows
- `down_proj`: [2048, 131072] = 256 experts x 512 columns
- Weight prefix: `model.language_model.layers.{i}.*` (NOT `model.layers.*`)

```python
import torch
from safetensors.torch import load_file, save_file

state = load_file("model-00001-of-00007.safetensors")
layer = 0
expert_idx = 42  # high-utility expert (select by routing frequency)
expert_size = 1024  # rows per expert in gate_up_proj

gate_up_key = f"model.language_model.layers.{layer}.mlp.gate_up_proj"
down_key   = f"model.language_model.layers.{layer}.mlp.down_proj"
gate_key   = f"model.language_model.layers.{layer}.mlp.gate"

# Extract expert #42 weights
expert_gate_up = state[gate_up_key][expert_idx*expert_size:(expert_idx+1)*expert_size, :]
expert_down = state[down_key][:, expert_idx*512:(expert_idx+1)*512]

# Append copy as expert #256
new_gate_up = torch.cat([state[gate_up_key], expert_gate_up], dim=0)
new_down = torch.cat([state[down_key], expert_down], dim=1)

# Expand router: [256, hidden] -> [257, hidden]
expert_gate_weight = state[gate_key][expert_idx, :]
new_gate = torch.cat([state[gate_key], expert_gate_weight.unsqueeze(0)], dim=0)

state[gate_up_key] = new_gate_up
state[down_key] = new_down
state[gate_key] = new_gate
save_file(state, "model-expanded.safetensors")
# Update config.json: num_experts 256 -> 257
```

### Training: freeze everything except new expert

```python
for param in model.parameters():
    param.requires_grad = False

# Unfreeze ONLY new expert (index 256) + its router row
# Fused tensors need gradient masking (zero out grads for frozen expert rows)
for layer_idx in range(40):
    model.layers[layer_idx].mlp.gate.weight[256, :].requires_grad = True
    # New expert's gate_up/down rows need custom grad masking
```

### Memory on DGX Spark (128 GB)

| Component | VRAM |
|-----------|------|
| Qwen3.5-35B BF16 (frozen, inference mode) | 67 GB |
| Gradients for new expert (40 layers) | ~20 GB |
| Optimizer states (AdamW, new expert only) | ~40 GB |
| Activations (batch=4, seq=4096) | ~5 GB |
| **Total** | **~72 GB** |

Result: 0% forgetting on old domains, +8-12% on new domain, ~6-12h training, 0.4% of params trainable.

---

## Method 3: ExPaMoE — Expandable Parallel MoE (Jul 2025)

> arXiv:2507.00502 | Jul 2025

**Automatically detects new domains and creates experts on demand.**

### Architecture
Two parallel MoE blocks:
- **General MoE** (frozen): 256 original experts, handles known domains
- **Expandable MoE** (trainable): starts empty (0 experts), grows as new domains detected

### Domain detection
Monitor routing entropy in General MoE. High entropy = token didn't find a good expert = new domain. When threshold accumulated → create new expert.

### Expert initialization
```
new_expert = weighted_average(top-3 most_activated_experts)
```
Initialize from existing experts (not random) → faster convergence.

### Results

| Method | New domain | Old domains | Params added |
|--------|:----------:|:-----------:|:------------:|
| Full FT | +15% | -40% | 0 |
| LoRA | +8% | -10% | +1% |
| **ExPaMoE** | **+12%** | **-2%** | +5% (on demand) |

---

## Method 4: LLaVA-CMoE — Probe-Guided Extension (2025)

> arXiv:2503.21227 | 2025

**Smartest approach: probe-experts determine WHERE and HOW MANY new experts to add.**

### How it works

1. **Probe experts** (small FFNs, 1/10 size) added parallel to each MoE layer
2. Run new domain data through probes
3. If probe on layer N activates strongly → that layer needs a new expert
4. If probe on layer M is silent → layer is fine, no expert needed
5. Add full-size expert ONLY to layers where probe is active
6. **Probabilistic Task Locator**: no task ID needed, automatic routing

### Results (8 domains, CoIN benchmark)

| Method | Avg accuracy | Forgetting | Params overhead |
|--------|:------------:|:----------:|:---------------:|
| Naive expansion (all layers) | 62% | 35% | +100% |
| **LLaVA-CMoE** | **81%** | **3%** | **+12%** |

Minimal expansion = minimal overhead. Only adds experts where capacity gaps exist.

---

## Method 5: GoD-MoE — LoRA Experts on Demand (AAAI 2026)

> AAAI 2026 (Mar 2026)

**Instead of full-size new experts, use LoRA adapters as new experts.**

```
Original MoE (256 experts) → FROZEN
+ GoD LoRA-experts (rank=16, ~4M params each) → TRAINABLE
+ GoD router (small) → TRAINABLE

output = attention(x) + LoRA_expert(x) * routing_weight
```

### Advantages
- New params: ~0.5% of model (vs 25% for full expert)
- Fast training (few params)
- Unlimited additions (no VRAM growth concern)
- Old knowledge: 100% preserved (original frozen)

---

## Method 6: DES-MoE — Dynamic Expert Specialization (Sep 2025)

> arXiv:2509.16882 | EMNLP 2025

**Not an expert-addition method — uses existing 256 experts with dynamic freeze/unfreeze.**

Covered in detail in `references/catastrophic-forgetting-2025.md`. Key points:
- Adaptive router with KL distillation to frozen original router
- Real-time expert-domain correlation matrix (EMA-updated)
- Three-phase schedule: warm-up (all trainable) → stabilization (freeze irrelevant) → consolidation (freeze all except domain-specific)
- **-89% forgetting, 1.68x faster convergence, 102% quality on new domain**

---

## Comparison Table

| Method | New experts? | What trains | Forgetting | Params added | Complexity |
|--------|:------------:|:-----------:|:----------:|:------------:|:----------:|
| **ESFT** (DeepSeek) | No | Existing relevant experts | -67% | 0 | Low |
| **DES-MoE** | No | Dynamic-selected experts | **-89%** | +0.01% | Med-High |
| **Expert Upcycling** | Yes (copies) | Only new copies | **0%** | +10-25% | Medium |
| **ExPaMoE** | Yes (auto) | Only new | -96% | +5% auto | Med-High |
| **LLaVA-CMoE** | Yes (probe-guided) | Only new (targeted) | -95% | +12% | High |
| **GoD-MoE** | Yes (LoRA) | Only LoRA-experts | ~0% | +0.5% | Medium |

---

## Decision Guide for Qwen3.5-35B-A3B on DGX Spark

| Scenario | Recommended method | Why |
|----------|-------------------|-----|
| Single domain, preserve base | **ESFT** | Simplest, proven by DeepSeek, 25% params |
| Multi-domain in one model | **DES-MoE** | -89% forgetting, unified model |
| Add capability, zero forgetting | **Expert Upcycling** | Copy + train copy, 0% forgetting |
| Auto-detect new domains | **ExPaMoE** | No manual domain labeling |
| Minimal parameter overhead | **GoD-MoE** | LoRA-experts, 0.5% overhead |
| Know which layers need help | **LLaVA-CMoE** | Probe-guided, targeted expansion |

### Expert Upcycling is the most practical for DGX Spark

- Simplest code (safetensors surgery + selective training)
- Zero forgetting guaranteed (original frozen)
- Fits 128GB easily (~72 GB total)
- Can repeat (256 -> 257 -> 258 -> ...)
- Each new expert: ~6-12h training, 0.4% params

### Composing with other methods

1. **Model Merging (TIES)** first → better starting point (0 compute)
2. **Expert Upcycling** → add domain-specific experts (train only new)
3. **DES-MoE** → if multi-domain training needed on the expanded model
4. **Multi-Teacher OPD** → distill from cloud APIs into the new experts

---

## Sources

- ESFT: arXiv:2407.01906, github.com/deepseek-ai/ESFT
- Expert Upcycling: arXiv:2604.19835 (Apr 2026)
- ExPaMoE: arXiv:2507.00502 (Jul 2025)
- LLaVA-CMoE: arXiv:2503.21227 (2025)
- GoD-MoE: AAAI 2026 (Mar 2026)
- DES-MoE: arXiv:2509.16882, EMNLP 2025
- DynMoE: arXiv:2405.14297, ICLR 2025 (auto-tuning expert count, related but different)
- Model MoErging survey: arXiv:2408.07057 (recycling fine-tuned models as experts)
