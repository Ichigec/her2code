# MoE Routing Stability During RL Training (2025-2026)

**Date:** 2026-07-13
**Context:** Deep research on whether LoRA on experts breaks the MoE router, whether to put LoRA on the router itself, and how to prevent routing collapse during RL. Core finding: **freeze the router, use R3 routing replay, and the router will NOT break.**

---

## The Root Problem: Top-K Is Non-Differentiable

The MoE router uses a Top-K operator to select which experts process each token. This creates two mathematical pathologies that break RL optimization (PPO/GRPO):

### Pathology 1: Gradient Blackout

For any unselected expert `u ∉ K(h)`:

```
∂π_θ(y_t | x, y<t) / ∂h_u = 0   almost everywhere
```

As long as `h_u < h_(K)` (the K-th largest logit), perturbing `h_u` does NOT change the selected expert set. The unselected expert's output doesn't contribute to the hidden state, and its logit doesn't enter the softmax normalization. Result: **exactly zero gradient** — not "weak," but mathematically zero.

Unlike ReLU (non-smooth but continuous, where subgradients work), Top-K is **discontinuous** at switching boundaries. The Clarke Generalized Gradient is undefined because the MoE output has jump discontinuities.

**Implication:** The router cannot learn from reward feedback which experts would produce better responses. Exploration is blind.

### Pathology 2: First-Order Approximation Failure

PPO/GRPO use a surrogate objective (first-order Taylor approximation of the true objective). This approximation requires the policy mapping to be smooth. Top-K routing violates this: an infinitesimal parameter change can cause a discrete expert switch, making the surrogate jump discontinuously.

The TRPO lower bound (theoretical foundation of PPO) assumes Lipschitz continuity. Top-K MoE output is **not locally Lipschitz** at switching boundaries. The surrogate gradient is systematically wrong at these points.

**Source:** [The Stability Gap: Why Top-K Routing Breaks RL Optimization](https://richardli.xyz/post/topk-routing-stability-gap/) (Li, Dec 2025) — rigorous mathematical analysis.

---

## Verdict: Freeze the Router

### Consensus across 2025-2026 literature and tooling

| Source | Approach | Router | Verdict |
|--------|----------|--------|---------|
| **ESFT** (arXiv:2407.01906, DeepSeek) | Select+train relevant experts | Frozen | "Matches or surpasses full FT" |
| **MoE-Sieve** (arXiv:2603.24044, Mar 2026) | LoRA on top-25% most-routed experts | Frozen | "Competitive with full LoRA, 70% less params" |
| **Unsloth** (Qwen3 docs) | Default MoE fine-tuning | **Frozen by default** | "Routers can destabilize training. Learned routing from pretraining tends to generalize well" |
| **DR-LoRA** (arXiv:2601.04823, Jan 2026) | Dynamic LoRA rank on experts | Frozen | Heterogeneous rank by routing frequency — router not trained |
| **ms-swift** (GitHub #5512, Aug 2025) | Feature request to add `--freeze_router` | Should be frozen | Unsloth's rationale cited as motivation |

### Why frozen router + LoRA on experts is safe

When LoRA is applied only to FFN experts (not the router) and the backbone is frozen:

1. **Router receives no gradients** → weights don't change → routing distribution is stable
2. **Train-inference consistency** preserved (same router → same expert selections)
3. **No gradient blackout problem** — we're not trying to learn expert selection, we're learning expert weights
4. **Pre-trained routing preserved** — Qwen3.5 saw code during pretraining, routing is already reasonable for code tasks

### Risk of routing collapse by approach (highest → lowest)

| Approach | Router | Phase | Collapse Risk |
|----------|--------|-------|:---:|
| Full FT + RL (router trainable) | Trainable | RL | ~90% |
| Full FT + SFT (router trainable) | Trainable | SFT | ~30% |
| LoRA on router + SFT | LoRA | SFT | ~15% |
| LoRA on experts + frozen router + RL | Frozen | RL | ~2% |
| **LoRA on experts + frozen router + RL + R3** | **Frozen** | **RL** | **<0.5%** |

---

## LoRA on the Router: When (Not) To Use

### For RL: Categorically NO

Three independent reasons:

1. **Gradient blackout** makes RL router training impossible — zero gradient for unselected experts means the router cannot learn from rewards
2. **Train-inference mismatch** is catastrophically amplified — if the router changes between rollout and training, importance sampling ratios explode (GPT-OSS case study, Jan 2026)
3. **Routing Replay (R2/R3/Pr²) is incompatible with trainable router** — replay assumes frozen routing decisions; if the router evolves, replayed routes diverge from current policy

### For SFT: Possible but not recommended without STE

If domain shift is so radical that pre-trained routing fails (e.g., formal verification with Coq/Lean), router adaptation is justified. Use:

- **DenseMixer** (OpenReview, Sep 2025): Straight-Through Estimator computes all experts' outputs during forward pass for precise router gradient. Cost: 2x compute on MoE layers. SFT only.
- **DES-MoE Phase A** (arXiv:2509.16882): Trainable router during warmup phase, then progressively frozen through stabilization → consolidation phases. By Phase C, router is always frozen.

### If LoRA on router is absolutely needed (SFT only, not RL)

```
Router LoRA (rank=4, very small):
  - Minimal influence on routing distribution
  - Gradient through Top-K: only for SELECTED experts (blackout for rest)
  - Risk: small routing changes amplify through 28+ MoE layers
  - Monitor: KL(router_lora || router_frozen) < 10⁻⁴
  - MUST freeze before any RL phase
```

---

## R3 (Rollout Routing Replay) — Needed Even With Frozen Router

**Source:** arXiv:2510.11370 (Oct 2025) — "Stabilizing MoE RL by Aligning Training and Inference Routers"

### Why R3 is needed even with frozen router

Even with identical frozen router weights, **numerical mismatch** between inference engine (vLLM, optimized for throughput, may use FP8, batch-invariant kernels disabled) and training engine (Megatron/VeRL, BF16, different kernels) can cause **completely different experts to be selected** for the same token.

> "Even under identical conditions, the routing framework can yield divergent expert selections across repeated forward passes." — R3 paper

### How R3 works

1. **During rollout (inference):** Record which experts the router selected for each token
2. **During training (gradient):** Replay those exact routing decisions — don't recompute them
3. Result: training-inference policy KL divergence drops significantly, preventing collapse

### R2 vs R3 vs Pr²

| Method | What it replays | Primary fix | When to use |
|--------|----------------|-------------|-------------|
| **R2** (Vanilla Routing Replay) | Routes from rollout policy in training engine | Policy staleness | On-policy / light off-policy |
| **R3** (Rollout Routing Replay) | Routes from inference engine in training engine | Train-inference discrepancy | Heavy off-policy |
| **Pr²** (Predictive Routing Replay, arXiv:2606.00395) | Predicts router evolution + replays predicted routes | Router staleness under off-policy | Advanced: when router evolves |

### Best practices (from arXiv:2512.01374)

- **On-policy / light off-policy:** MiniRL + R2 (sufficient, bias is small)
- **Heavy off-policy:** MiniRL + R3 (stability is paramount, R3 eliminates discrepancies)

---

## GPT-OSS Case Study: Importance Sampling Ratio Fix (Jan 2026)

**Source:** [Viqus AI analysis](https://viqus.ai/news/gpt-oss-unleashed-fixing-moe-instability-for-agen), based on HuggingFace blog

GPT-OSS MoE architecture had training-inference mismatch in log-probability calculations due to stochastic MoE routing. This triggered:
- Excessive PPO clipping
- Exploding gradient norms
- Stalled reward improvement

**Fix:** Logically override log-prob computation during on-policy training to force importance sampling ratio = 1. Validated on both GPT-OSS-20B and GPT-OSS-120B.

**Lesson:** This fix ONLY works when the router is frozen (so the mismatch is purely numerical, not from router weight changes). If the router were trainable, forcing ratio=1 would mask real policy divergence.

---

## Spectrum of Router Handling Strategies

```
← SAFER                                                    RISKIER →

1. FREEZE       2. FREEZE +       3. DENSEMIXER   4. DES-MoE
   ROUTER          ROUTING             (STE)         (PHASED)
   (default)       REPLAY

   Router:        Router:            Router:        Router:
   FROZEN          FROZEN             TRAINABLE      Phase A: ON
                  Replay routes      (with STE       Phase B: ↓
   LoRA on        from rollout →     gradient for    Phase C: OFF
   experts only   train with same    all experts)
                  routing            2x compute      LoRA on
                                                       experts + router
   ✅ Safe         ✅ Safe for RL     ⚠️ SFT only     ⚠️ Multi-domain
   ✅ Standard     ✅ Prevents        ⚠️ 2x compute   ⚠️ Complex
   ✅ No drift      mismatch                         ❌ RL requires freeze
                   ✅ R3/Pr² best
                    practice
```

### Strategy selection for our pipeline (CA1-MS)

**Strategy 1 + Strategy 2:** LoRA on experts + frozen router + R3 during RL. This is the optimal approach with <0.5% collapse risk.

If pre-trained routing proves inadequate for adversarial code-test tasks (unlikely — Qwen3.5 saw code during pretraining), add an optional **Phase 0.5: Router Adaptation** using DenseMixer STE during SFT only, then freeze before RL.

---

## Router Monitoring Checklist During RL

Even with frozen router, monitoring is critical:

```python
def monitor_routing_health(model, rollout_data, train_data):
    metrics = {}

    # 1. Train-Inference Routing Agreement
    rollout_routes = get_routes(model, rollout_data, engine="vllm")
    train_routes = get_routes(model, train_data, engine="training")
    metrics["route_agreement"] = topk_agreement(rollout_routes, train_routes)
    # THRESHOLD: > 99.5% (with R3), > 95% (without R3)

    # 2. Router KL Divergence (should be ~0 for frozen router)
    metrics["router_kl"] = kl_divergence(
        router_logits(model, train_data),
        router_logits(reference_model, train_data)
    )
    # THRESHOLD: < 1e-6 (frozen router = zero change)
    # If > 1e-4: something is training that shouldn't be!

    # 3. Expert Load Distribution (coefficient of variation)
    metrics["expert_cv"] = coefficient_of_variation(
        expert_activation_counts(model, train_data)
    )
    # THRESHOLD: CV < 2.0, should not change from baseline
    # Note: per-layer CV is typically 4.0-4.9x global CV — this is NORMAL (MoE-Sieve)

    # 4. Dead Experts (experts that stopped activating)
    metrics["dead_experts"] = count_experts_with_zero_activation(
        model, train_data, threshold=0.01  # <1% of tokens
    )
    # THRESHOLD: should not increase from baseline

    return metrics

# Alerts:
# route_agreement < 95% → ENABLE R3
# router_kl > 1e-4 → CHECK that router is actually frozen
# dead_experts increasing → possible routing collapse
```

### Monitoring tool: MOE-Patch

MOE-Patch (mentioned in Zhihu post by 燕雄飞的一天, Mar 2026) is a monkey-patching monitoring tool that captures routing distributions, expert load, token drop rates in real-time without modifying training/inference source code. Works with verl, ms-swift, vLLM.

---

## Aux Loss Tuning (for SFT, not router-specific)

When training MoE models (even with frozen router, if doing full FT of experts), the auxiliary load-balancing loss (`aux_loss`) needs tuning:

- **aux_loss too high** → forces uniform expert load but degrades model performance (eval loss increases)
- **aux_loss too low** → imbalanced experts, some overloaded, others idle
- **Sweet spot: weight = 0.001** (Qwen series)

**Loss-free balancing** (DeepSeek V3+): adds bias `b_i` to gating scores for top-K selection, but uses original scores for output computation. No auxiliary loss term needed.

---

## Five Mechanisms of Routing Collapse (Taxonomy)

When adding experts or training on MoE, routing collapse can occur through 5 distinct mechanisms. Each requires a different defense:

| # | Mechanism | Cause | Defense |
|---|-----------|-------|---------|
| 1 | **Softmax redistribution** | Adding expert columns → softmax denominator grows → old expert probabilities drop → discrete top-K switches | Beyond Sunk Costs: copy router weights for new experts (zero init loss) |
| 2 | **Train-inference discrepancy** | SGLang (rollout) vs Megatron (training) → 10% router disagreement, 94% tokens affected | R3 (Rollout Routing Replay) — cache + replay routing masks |
| 3 | **Expert collapse / dead experts** | Zero-init → never selected → no gradient → permanently dead. Copy-init → no symmetry breaking | SPRI (SVD-partitioned init) or noise-perturbed copy |
| 4 | **Routing drift during fine-tuning** | Router updates on new data → old token routing changes → positive feedback loop | SAME (orthogonal subspace) or DES-MoE (KL distillation on router) |
| 5 | **RL-specific routing collapse** | GRPO reward ignores routing → router concentrates on few experts → LoRA-MoE underutilization | RO-GRPO (routing entropy + load variance as reward) |

---

## RO-GRPO: Routing-Aware Reward for LoRA-MoE RL (ICLR 2026)

**Source:** RO-GRPO, OpenReview rhD7ZuFAjU, ICLR 2026 — "Balancing the Experts: Unlocking LoRA-MoE for GRPO via Mechanism-Aware Rewards"

**Problem:** Standard GRPO on LoRA-MoE causes routing collapse — router concentrates on 1-2 "confident" experts, rest become dead weight. Traditional load-balancing auxiliary loss is incompatible with GRPO objective.

**Solution:** Convert internal routing statistics into a scalar reward added to GRPO:

```
R_total = R_task + λ · R_routing

where R_routing = entropy_bonus - load_penalty
  entropy = -Σ p_e · log(p_e)  (routing entropy per token, higher = more diverse)
  load_variance = Var({load_e})  (expert load distribution, lower = more balanced)
```

**Advantages:** No auxiliary loss, no architecture changes, no extra training stages. Directly integrated into GRPO advantage estimation. First systematic study of LoRA-MoE in RFT framework.

**When to use:** ANY GRPO training on LoRA-MoE architectures. Without it, routing collapse is near-certain.

---

## EPnG: Adaptive Expert Prune-and-Grow (arXiv 2607.01789)

**Source:** EPnG, MobiSys 2026 — adaptive prune-and-grow for parameter-efficient MoE fine-tuning

**Problem:** Uniform LoRA allocation wastes capacity on under-used experts. Standard LoRA ignores MoE routing dynamics.

**Solution:** Dynamic reallocation of LoRA capacity based on router gate probabilities:

1. **Monitor:** `importance(e) = E[p_e]` (average routing probability per expert)
2. **Prune:** Remove LoRA from under-utilized experts (`importance < threshold`)
3. **Grow:** Expand LoRA rank for high-importance experts with **orthogonal initialization** (new columns ⊥ existing columns)
4. **Fixed budget:** Total LoRA parameters stay constant — pruned capacity redistributed

**Results:** 0.55-0.72% of parameters (140-180× fewer than full FT), outperforms uniform LoRA, comparable to full FT. Tested on OLMoE and Qwen1.5-MoE.

**When to use:** When LoRA budget is tight and some experts are clearly more important than others for the target task.

---

## SAME: Orthogonal Subspace Routing (arXiv 2602.01990)

**Source:** SAME — StAbilized Mixture-of-Experts for Multimodal Continual Instruction Tuning

**Problem:** Router drift — routing decisions become inconsistent over time as data distribution evolves. A query that previously activated expert A may route to expert B after learning new tasks.

**Solution:** Decompose routing dynamics into orthogonal subspaces:

1. **Router stabilization:** Decompose router weight updates into task-relevant and task-irrelevant directions. Update ONLY task-relevant directions; freeze irrelevant ones.
2. **Expert stabilization:** Curvature-aware scaling using historical input covariance (Fisher information). Scale gradient updates by inverse Fisher to prevent shared expert overwriting.
3. **Adaptive expert activation:** Freeze selected experts during training → reduces redundant computation + cross-task interference.

**When to use:** Continual learning scenarios where multiple tasks arrive sequentially and router drift is observed.

---

## Synergistic Regularization Losses (arXiv 2602.14159)

**Source:** Two plug-and-play losses, orthogonal to load-balancing, compatible with DeepSeekMoE and vanilla top-k MoE.

1. **Intra-layer specialization loss:** Penalizes cosine similarity between experts' SwiGLU activations on identical tokens → forces complementary specialization:
   ```
   L_intra = Σ_{e≠e'} cos_sim(act_e(h), act_{e'}(h))
   ```

2. **Cross-layer coupling loss:** Maximizes joint Top-k routing probabilities across adjacent layers → coherent expert pathways through depth:
   ```
   L_cross = -Σ P(e ∈ TopK_layer_l) · P(e ∈ TopK_layer_{l+1})
   ```

**When to use:** Always safe to add — plug-and-play, no architecture changes. Particularly useful when expert overlap/redundancy is detected.

---

## Safe Expert Addition Protocol (when adding new experts)

If LoRA on existing experts is insufficient and new experts must be added, follow this protocol:

### Step 1: Select experts for duplication (utility-based)
- DES-MoE warmup: record `A_d(e)` = how often expert `e` is selected for domain `d`
- Utility score: `u_G(e) = ‖∇_e L‖²` (gradient norm = sensitivity)
- Duplicate only HIGH-UTILITY experts (Expert Upcycling, arXiv 2604.19835)
- Non-uniform duplication triples gap closure vs uniform

### Step 2: Initialize new experts (SPRI method, arXiv 2606.16456)
- SVD decompose: `W_e = U·Σ·V^T`
- Partition singular values: `Σ → [Σ_new, Σ_residual]`
- `E_new = U·Σ_new·V^T` (spectral partition, not random noise)
- **+3.39 BLEU over noise-based upcycling** (SPRI vs Drop-Upcycling)
- Alternative: noise-perturbed copy `E' = E + ε, ε ~ N(0, σ²)` (simpler, slightly worse)

### Step 3: Extend router (Beyond Sunk Costs, arXiv 2510.08008)
- **Copy router weights** for new experts from originals → output IDENTICAL to pre-expansion → zero initialization loss
- `W_R_new = [W_R_old | W_R_copies]`
- Then CPT (continued pre-training) breaks symmetry naturally
- Expert Upcycling (2604.19835) formalizes: quality gap = capacity term + initialization term

### Step 4: Freeze originals (LLaVA-CMoE, arXiv 2503.21227)
- Freeze ALL original experts + original router weights
- Train ONLY new experts + new router columns
- **Guarantee:** old routing distribution preserved for old tasks
- LLaVA-CMoE "Extend" vs "w/o Extend": freeze+add = stable; unfreeze+retrain = catastrophic forgetting

### Step 5: R3 + RO-GRPO (for RL phase)
- R3: cache routing masks from rollout, replay in training
- RO-GRPO: routing entropy + load variance → scalar reward
- Monitor: `KL(R_trained || R_original) < 10⁻³`

### Step 6: DES-MoE three-phase schedule
- Phase A (warmup): train new experts, record correlations
- Phase B (specialization): freeze irrelevant experts based on correlation matrix
- Phase C (convergence): progressive freezing of converged experts

### Recommendation for Qwen3.5-35B-A3B + CA1-MS pipeline

**Do NOT add new experts.** Use LoRA on existing 128 experts. Reasons:
1. Router frozen → natural protection from routing collapse
2. LoRA on experts → capacity without structural changes
3. R3 + RO-GRPO → solve RL-specific routing problems
4. Memory: 79GB without new experts vs 85-95GB with them
5. If LoRA rank=64 is insufficient → first try rank=128, then EPnG, then add experts

---

## Additional Papers

| Paper | arXiv | Date | Key Contribution |
|-------|-------|------|-----------------|
| **R3 — Rollout Routing Replay** | 2510.11370 | Oct 2025 | Record inference routes, replay in training → fixes train-inference discrepancy |
| **RO-GRPO** | ICLR 2026 (rhD7ZuFAjU) | Jan 2026 | Routing entropy + load variance as GRPO reward → prevents LoRA-MoE routing collapse |
| **EPnG** | 2607.01789 | Jul 2026 | Adaptive prune-and-grow LoRA based on expert importance → 140× fewer params |
| **SAME** | 2602.01990 | Feb 2026 | Orthogonal subspace routing → prevents router drift in continual learning |
| **Synergistic Reg.** | 2602.14159 | Feb 2026 | Intra-layer + cross-layer specialization losses (plug-and-play) |
| **SPRI** | 2606.16456 | Jun 2026 | SVD-partitioned residual init for upcycling → +3.39 BLEU over noise |
| **Beyond Sunk Costs** | 2510.08008 | Oct 2025 | Copy router weights for new experts → zero init loss, 10.6% accuracy gain |
| **Expert Upcycling** | 2604.19835 | Apr 2026 | Theoretical framework: quality gap = capacity + initialization. Utility-based duplication |
| **Sticky Routing** | 2607.08780 | Jul 2026 | Routing consistency loss → 60% less expert switching, <4% perplexity cost |
| **Router Upcycling** | 2509.00679 | Sep 2025 | Initialize routers from attention heads during upcycling |
| **Continual Pre-training MoE** | 2503.05029 | Mar 2025 | MoE routers are surprisingly robust to distribution shift (Sinkhorn + Z-loss) |
| **MoE-LPR** | 2408.11396 | Aug 2024 | Language priors routing: freeze original, add new experts for new languages |
| **The Stability Gap** | [blog](https://richardli.xyz/post/topk-routing-stability-gap/) | Dec 2025 | Mathematical proof: Top-K creates gradient blackout + first-order approx failure |
| **DenseMixer** | [OpenReview](https://openreview.net/forum?id=4HGIIekCx3) | Sep 2025 | STE for precise router gradient (2x compute, SFT only) |
| **DES-MoE** | 2509.16882 | Sep 2025 | Phased router: warmup → stabilize → consolidate (always frozen by Phase C) |
| **Pr² — Predictive Routing Replay** | 2606.00395 | Jun 2026 | Predict router evolution for off-policy RL stability |
| **MoE-Sieve** | 2603.24044 | Mar 2026 | LoRA on top-25% most-routed experts only (frozen router) |
| **DR-LoRA** | 2601.04823 | Jan 2026 | Dynamic LoRA rank by expert saliency (frozen router) |
| **ESFT** | 2407.01906 | Jul 2024 | Select+train relevant experts, freeze rest + router |
| **GPT-OSS RL fix** | [HF blog](https://huggingface.co/blog) | Jan 2026 | Force IS ratio=1 for on-policy MoE RL (only works with frozen router) |
| **MoE Post-Training Challenges** | [Zhihu translation](https://www.tylerromero.com/translations/zhihu/moe-post-training-challenges-and-lessons/) | Mar 2026 | Practical guide: aux_loss tuning, R2/R3 selection, EP/ETP, MOE-Patch monitoring |
| **FP16 train-inference mismatch** | 2510.26788 | Oct 2025 | FP16 precision as source of numerical routing mismatch |
| **Unsloth MoE docs** | [qwen.readthedocs.io](https://qwen.readthedocs.io/en/latest/training/unsloth.html) | 2026 | "Router-layer fine-tuning is disabled by default" |
