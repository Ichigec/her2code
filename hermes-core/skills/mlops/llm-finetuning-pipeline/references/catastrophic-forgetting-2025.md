# Catastrophic Forgetting Prevention (2025-2026)

**Date:** 2026-07-12
**Context:** Research pass restricted to papers from January 2025+. The field has shifted: RL > SFT for forgetting prevention, MoE-specific methods emerged, and entropy/perplexity-based token selection is a new lightweight paradigm.

---

## Key Paradigm Shift: RL > SFT for Forgetting Prevention

Three independent 2025-2026 papers converge on this finding:

| Paper | arXiv | Date | Finding |
|-------|-------|------|---------|
| RL's Razor (MIT) | 2509.04259 | Sep 2025 | RL mode-seeking → preserves prior knowledge. KL-divergence as measurable forgetting metric |
| SFT Memorizes, RL Generalizes | 2501.17161 | ICML 2025 | SFT memorizes training data → forgets. RL generalizes → preserves |
| RFT Naturally Mitigates Forgetting | 2507.05386 | Jul 2025 | RL = natural anti-forgetting paradigm, comparable to multi-task training |

**RL Heals OOD Forgetting from SFT** (arXiv:2509.12235): The standard SFT→RL pipeline is itself an anti-forgetting strategy — RL recovers what SFT damaged. However, RL rarely surpasses the best OOD checkpoint already reached during early SFT.

**MIFO** (arXiv:2510.04454): Plug-and-play SFT+RL with anti-forgetting. Only **1.5% SFT data + 20.4% RL data** vs prior SoTA. Selects high-entropy tokens for loss, freezes RL-critical parameters.

---

## MoE-Specific: DES-MoE (arXiv:2509.16882, EMNLP 2025)

**Most directly relevant for Qwen3-35B MoE.** Dynamic Expert Specialization: routes and specializes experts to domains without cross-domain interference.

- **Forgetting reduced by 89%** vs full FT at 6 domains (7% forgetting vs 60% baseline)
- Matches single-domain ESFT (Expert-Specific Fine-Tuning) performance
- 68% faster convergence than conventional methods (1.68× speedup)
- **102% quality on new domain** (vs 100% baseline — freezing irrelevant experts concentrates gradients, reduces noise)
- One unified model instead of a zoo of domain-specific models

### Three Innovations

**1. Adaptive Router (Distillation-based):**
Router is trained on new domain but regularized via KL-divergence with frozen original router:
```
routing_old = frozen_router(hidden_states)      # preserves pre-trained routes
routing_new = adaptive_router(hidden_states)     # learns new domain routes
router_loss = KL(routing_new || routing_old) * λ  # distillation regularization
total_loss = task_loss + router_loss
```
Forces router to keep original routes for old domains while carving out new domain routes into free/underutilized experts.

**2. Expert-Domain Correlation Mapping:**
Real-time matrix `[256 experts × N domains]` updated via exponential moving average:
```
correlation[i][d] = EMA(avg routing probability of domain-d tokens to expert-i)
```
When fine-tuning domain 3, if expert 3 has high correlation with domain 1 → freeze it. Route domain-3 tokens to free experts (55, 178). Updated every step.

**3. Three-Phase Adaptive Schedule:**
- **Stage I — Warm-up** (first 10% steps): all parameters trainable, high LR (2e-5). Initial adaptation.
- **Stage II — Stabilization** (10–60% steps): freeze irrelevant experts (identified by correlation matrix), train only adaptive router + domain-relevant experts. Medium LR (1e-5).
- **Stage III — Consolidation** (60–100% steps): freeze everything except final domain-specific experts. Low LR (5e-6). Polish and lock in.

### Implementation Sketch for Qwen3.5-35B-A3B

```python
# 256 experts, 40 layers, weights under model.language_model.layers.{i}.*

# 1. Save frozen copy of original routers (21M params × 2 = 42 MB overhead)
original_routers = {
    i: model.language_model.layers[i].mlp.gate.weight.clone().detach()
    for i in range(40)
}

# 2. Expert-domain correlation matrix (EMA-updated each step)
expert_domain_corr = torch.zeros(256, num_domains)

# 3. Per-step: compute routing distillation loss
routing_old = F.softmax(hidden_states @ original_routers[layer_i].T)
routing_new = F.softmax(hidden_states @ adaptive_routers[layer_i].T)
router_kd_loss = F.kl_div(routing_new.log(), routing_old, reduction="batchmean") * lambda_reg

# 4. Phase-based freezing schedule
if step < total * 0.1:    # Stage I: all trainable
    lr, freeze = 2e-5, None
elif step < total * 0.6:  # Stage II: freeze irrelevant
    lr = 1e-5
    irrelevant = get_irrelevant_experts(expert_domain_corr, current_domain)
    freeze_experts(model, irrelevant)
else:                      # Stage III: freeze all except domain-specific
    lr = 5e-6
    domain_experts = get_domain_experts(expert_domain_corr, current_domain)
    freeze_all_except(model, domain_experts)
```

Memory overhead: ~42 MB (router copies) + 256×N floats (correlation matrix). Negligible on 128GB.

### Comparison with Alternatives

| Method | Forgetting | Compute overhead | MoE-specific? | Complexity |
|--------|:---:|:---:|:---:|:---:|
| Replay (mix old data) | −58% | +10% (data loading) | No | Low |
| LoRA | −33% | 0 | No | Low |
| EAFT (entropy gating) | −50% | 0 | No | Medium |
| SSU (column freeze) | −60% | 0 | No | Medium |
| **DES-MoE** | **−89%** | +2% (corr matrix) | **Yes** | Medium-High |

---

## New Causes Identified (2025-2026)

### Catastrophic Overtraining (arXiv:2503.19206, ICML 2025)
Extended pre-training makes models **harder to fine-tune**. Systematic increase in parameter sensitivity. Qwen3 models (heavily pre-trained) require especially careful fine-tuning.

### LR Regulates Forgetting (arXiv:2604.13627, Apr 2026)
Large LR → sharper minima → more forgetting. Small LR → flatter minima → less forgetting. **Even at same SFT loss**, different LRs give different forgetting profiles.

### Mechanistic Analysis (arXiv:2601.18699, Jan 2026)
Forgetting is **not uniform across layers** — certain attention heads and MLP neurons are disproportionately responsible for retained capabilities. Tested on 109B-400B models.

### Mapping Post-Training Forgetting (arXiv:2510.17776, ICLR 2026)
Not all forgetting is equal — some examples are much more vulnerable. Enables targeted mitigation: identify and protect the most vulnerable knowledge.

---

## New Mitigation Methods (2025-2026)

### EAFT — Entropy-Adaptive Fine-Tuning (arXiv:2601.02151, Jan 2026)
Token-level entropy gating: distinguishes epistemic uncertainty (model doesn't know → learn) from knowledge conflict (model confidently disagrees → be careful). Down-weights destructive updates on conflicting tokens. **Lightweight — just add entropy gating to existing training loop.**

### Low-Perplexity Token Learning (arXiv:2501.14315, NeurIPS 2025)
Selective masking: train **only on tokens with low perplexity** (where model is already confident). LLM-generated data causes less forgetting than human-authored data because it stays closer to model's distribution.

### SSU — Source-Shielded Updates (arXiv:2512.04844, ACL 2026)
Column-wise freezing by source data importance scores. **More effective than PEFT, regularization, or model merging.** Open-source: `github.com/gucci-j/ssu`. Works under low-resource constraints (unlabeled target data only).

### Mask the Target (arXiv:2605.29498, CVPR 2026)
Plug-and-play regularizer for LoRA. Masking target tokens in regularization loss. **No architectural changes** — add to any LoRA pipeline.

### FAPM (arXiv:2509.08255, EMNLP 2025)
Pruning-based: **99.67% downstream accuracy with only 0.25% forgetting.** Pruning metrics along task vectors with forgetting risk awareness.

### GeRe (arXiv:2508.04676, Aug 2025)
Replay through generic pre-training text (not task-specific). Threshold-Based Margin Loss for activation consistency. **No original training data needed.** Code: `github.com/Qznan/GeRe`.

### Replaying Pre-Training Data Improves Fine-Tuning (arXiv:2603.04964, Stanford, Mar 2026)
**Counterintuitive:** replay general data not only prevents forgetting but **improves target domain performance 1.87x** (fine-tuning) and 2.06x (mid-training). Especially beneficial when target domain is scarce in pre-training.

### Nested Learning (arXiv:2512.24695, NeurIPS 2025)
Google Research. Model = nested multi-level optimization problems. Rapid updates → fast weights (new info), slow weights (long-term knowledge). **Forgetting reduced by 70%** at SOTA accuracy.

### SDFT — Self-Distillation FT (arXiv:2601.19897, MIT, Jan 2026)
Frozen base model = teacher → receives expert demonstrations → in-context learning → generates on-policy training signals. Student learns from self-generated signals, not directly from demonstrations. **True continual learning without forgetting.** MLX implementation: `github.com/szmoro/mlx-sdft`.

**🔥 VALIDATED ON OUR EXACT MODEL:** The Tinker platform tested SDFT on **Qwen3.5-35B-A3B + LoRA rank 64** in a continual learning experiment. Result: SDFT preserves previous skills (near-zero forgetting), while standard SFT shows severe forgetting. EMA-smoothed teacher (α=0.999). Interpreted as inverse RL — naturally compatible with GRPO. ~2.5× FLOPs (two forward passes), no replay buffer, no Fisher matrix. **This is the #1 recommended anti-forgetting method for Qwen3.5-35B-A3B.**

### SWE-RL — RL on Code Improves General Capabilities (arXiv:2502.18449, Meta, NeurIPS 2025)
RL on software engineering data not only preserves but **IMPROVES** general capabilities — math, reasoning, and language understanding all improved. The RL phase on code is not a forgetting risk but a potential booster.

### PRISM — Routing Does NOT Isolate Knowledge (arXiv:2605.01061)
In MoE-LoRA continual learning, routing does NOT isolate task-specific knowledge into disjoint experts as commonly assumed. Routing operates per-sample, while forgetting accumulates across the task sequence. Cannot rely on MoE routing for forgetting protection — need explicit per-expert subspace constraints.

### MoE Routers Exacerbate Forgetting (arXiv:2503.05029, TMLR 2025)
Systematic study: MoE routers DO exacerbate forgetting relative to dense models due to routing imbalance. Routers may not maintain balanced load on previous distributions after CPT. Must maintain load balancing loss during continual fine-tuning.

### LoRI — Reduced Interference (arXiv:2504.07448, COLM 2025)
Freeze A projection matrices as random projections, sparsify B matrices. Leverages orthogonality between adapter subspaces. Proven to preserve safety alignment in continual learning. Reduces trainable parameters. Simple modification: freeze A, mask B.

### Merge before Forget (arXiv:2512.23017, ICLR 2026)
Single LoRA pair throughout continual learning. After each task, merge new LoRA with existing one. Tested on Qwen2.5-7B. Memory-efficient (one pair, not N pairs). Outperforms methods that retain multiple frozen LoRAs.

### O-LoRA — Orthogonal Subspace (arXiv:2310.14152, EMNLP 2023)
Learns each new task in a low-rank subspace orthogonal to previously learned task subspaces. Orthogonality loss is composable with GRPO. Well-established, widely extended.

### DOC — Dynamic Orthogonal (arXiv:2509.23893)
Extends O-LoRA with online PCA to track functional direction drift during fine-tuning. Projects new updates orthogonally to updated components. Accounts for subspace drift during extended training.

### DOC — Dynamic Orthogonal Continual FT (arXiv:2509.23893, Sep 2025)
Online PCA tracks functional directions. New learning constrained to be **orthogonal** to previously important directions. Outperforms prior continual learning methods.

---

## Practical Anti-Forgetting Stack for DGX Spark (Priority-Ordered)

### Tier 1 — Always do:
1. **Use RL instead of pure SFT when possible** (arXiv:2509.04259, 2501.17161, 2507.05386). If must SFT, follow with RL stage to "heal" forgetting (arXiv:2509.12235)
2. **For MoE: DES-MoE expert specialization** (arXiv:2509.16882) — -89% forgetting
3. **Mix 10-30% general/pre-training data** (arXiv:2603.04964) — also improves target performance 1.87x
4. **Low learning rate** (arXiv:2604.13627) — small LR = flat minima = less forgetting
5. **Monitor: MMLU, HellaSwag, ARC before/after**

### Tier 2 — Stronger preservation:
6. **EAFT entropy gating** (arXiv:2601.02151) — lightweight, add to existing loop
7. **Low-Perplexity Token Masking** (arXiv:2501.14315) — train only on familiar tokens
8. **SSU column-wise freezing** (arXiv:2512.04844) — more effective than LoRA/regularization/merging
9. **Mask the Target regularizer** (arXiv:2605.29498) — plug-and-play for LoRA

### Tier 3 — Advanced:
10. **SDFT** (arXiv:2601.19897) for continual multi-domain learning
11. **Nested Learning** (arXiv:2512.24695) — -70% forgetting
12. **DOC orthogonal constraints** (arXiv:2509.23893)

### For Qwen3-4B (dense, 128GB):
- Full FT feasible (44GB) but prefer LoRA or RL
- If SFT: use EAFT + Low-Perplexity masking + 20% general data + low LR (1e-5)
- If RL: GRPO with execution rewards — natural anti-forgetting
- Post-training: DARE-TIES merge

### For Qwen3-35B MoE (128GB):
- **DES-MoE** is the primary recommendation (arXiv:2509.16882)
- QLoRA (20GB) or LoRA (74GB)
- SSU column-wise freezing for parameter protection
- Post-training: DARE-TIES merge via mergekit
