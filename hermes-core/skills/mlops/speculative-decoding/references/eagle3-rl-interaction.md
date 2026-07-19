# Eagle3 + RL Training: Detailed Research Findings

Research notes from investigating whether Eagle3 speculative decoding interferes
with model distillation and RL training. Compiled July 2026.

## Summary

| Question | Answer |
|---|---|
| Does Eagle3 interfere with distillation? | No — they are orthogonal. Eagle3 trains on student hidden states, not teacher. |
| Does Eagle3 complicate the pipeline? | Yes, moderately — adds ~2-4h training + hidden state extraction + offline pattern on single-GPU. |
| Does Eagle3 degrade RL quality? | YES, DANGEROUSLY — three confirmed mechanisms (ReSpec paper). Can corrupt RL policy. |

## Key Research Papers

### 1. ReSpec (arXiv:2510.26475, Oct 2025, under review MLSys)

**First systematic study of SD in end-to-end RL training of LLMs.**

Identifies three critical gaps that hinder naive SD integration into RL:

**GAP 1: Diminishing speedups at large batch sizes.**
RL training enlarges batch size to fit GPU utilization in the decoding phase.
When batch size is already large, GPUs operate near high utilization through
straightforward batching. The extra parallelism SD provides yields little
marginal benefit, and SD introduces additional overheads (draft cost +
verification synchronization) that can offset or exceed the speedup.

> "When the batch size in decoding is already large, GPUs are typically
> operating near high utilization... the extra parallelism that SD provides
> yields little marginal benefit."

**GAP 2: Drafter staleness under continual actor updates.**
The actor (target model) parameters are continually updated during RL. A
drafter distilled from an earlier snapshot becomes misaligned with the
evolving actor, leading to lower acceptance length. ReSpec Figure 4 shows
EAGLE-3 acceptance length decreasing as RL training advances on Qwen2.5-7B.

> "As training progresses, the EAGLE-3 drafter quickly becomes stale and its
> acceptance length drops."

**GAP 3: Drafter-induced degradation of actor performance (MOST DANGEROUS).**
Although the SD acceptance test preserves the marginal token distribution at
a single step, multi-token drafts have high variance that compounds
exponentially:

```
Var_{T~q}[prod_{t in T} p(t)/q(t)] = prod_{t in T} (1 + D_chi2(p(t)||q(t))) - 1
```

Where D_chi2 is the Chi-squared divergence. If approximated by constant delta,
variance = (1+delta)^|T| - 1, growing exponentially with sequence length.

As the target model distribution evolves during RL:
- Some tokens become increasingly unlikely to be drafted (p/q increases)
- Others are drafted often but rarely accepted (p/q decreases)
- This causes systematically impoverished trajectories
- Shifted rollout distribution degrades downstream rewards
- RL optimizer receives misleading gradients from corrupted rollouts

> "Naive application of EAGLE-3 leads to a measurable drop in reward,
> illustrating drafter-induced distributional bias during RL training."
> — ReSpec, Figure 5

**ReSpec solutions (three mechanisms):**
1. Dynamic SD config tuning — disables SD when batch is large (solves GAP 1)
2. On-policy KD — continuously retrains drafter on fresh rollout signals (solves GAP 2)
3. Reward-weighted KD — weights drafter updates by rollout quality (solves GAP 3)

**Results:** Up to 4.5x speedup on Qwen 3B-14B, reward convergence preserved.

### 2. EAGLE-3 (arXiv:2503.01840, Mar 2025)

The original EAGLE-3 paper. Key innovations:
- Abandons feature prediction in favor of direct token prediction
- Multi-layer feature fusion (layers 0, 1, 2 of target model)
- Training-Time Test (TTT) — simulates accept/reject during training
- Up to 6.5x speedup, 1.4x over EAGLE-2
- 1.38x throughput improvement at batch size 64 in SGLang

Note: EAGLE-3 training is itself a form of knowledge distillation (KL divergence
between target and draft distributions over reduced vocabulary). But this KD is
between the draft and the target (student) model, NOT between student and teacher.

### 3. AdaSPEC (arXiv:2510.19779)

Selective Knowledge Distillation for draft models. Key insight: conventional KD
aims to minimize KL divergence across ALL tokens, but this is misaligned with
the true SD objective (maximize token acceptance rate). AdaSPEC filters out
difficult-to-fit tokens during draft KD, improving acceptance rate up to 15%
over DistillSpec.

Relevance to distillation pipeline: When training Eagle3 on a distilled student,
the draft model inherits the student's distribution. If the student was distilled
from a cloud teacher, the draft captures the student's approximation of the
teacher, not the teacher directly. This is fine — the draft should match the
deployed model, not the teacher.

### 4. TIDE (arXiv:2602.05145)

Temporal Incremental Draft Engine — serving-engine-native framework for online
draft adaptation. Reuses target model hidden states from inference as training
signals → zero-overhead draft adaptation. Adaptive runtime control activates
speculation only when beneficial. Maps inference and training to appropriate
GPU classes (heterogeneous clusters).

Results: 1.15x throughput improvement over static SD, 1.67x faster draft training
vs approaches that recompute training signals.

### 5. NeMo RL + Eagle3 (NVIDIA, production)

NeMo RL documentation describes two modes for Eagle3 in RL:

**Offline draft model:** vLLM uses a fixed Eagle3 checkpoint for speculative
decoding, but the RL training loop does not update that draft model. This is
the naive approach — suffers from GAP 2 (staleness).

**Online draft training:** NeMo RL attaches an Eagle3 draft model to the
Megatron policy worker, trains it alongside the policy, and refits both policy
and draft weights into vLLM. This solves staleness but requires Megatron
backend (not HuggingFace) and adds system complexity.

Results on 8B reasoning workloads: 1.8x faster rollout generation, 1.4x faster
RL steps. Projected 2.5x at 235B scale.

Source: https://docs.nvidia.com/nemo/rl/nightly/guides/eagle3-speculative-decoding.html

### 6. Yandex Alice AI Tech Report (Habr, 2026)

Real-world Eagle3 deployment experience from Yandex:
- Eagle3 acceptance = 2.5 (3 draft tokens) vs Eagle1 acceptance = 2.1
- End-to-end speedup: x1.15 over Eagle1
- SpecForge max acceptance observed: 1.8

Source: https://habr.com/ru/companies/yandex/articles/974594/

## Pipeline Ordering Analysis

The correct order for a pipeline that includes distillation, RL, and Eagle3:

```
1. Distillation (cloud teacher → student)
   - GLM-5.2 / GPT-4o generates responses → SFT dataset
   - Student trained via SFT/LoRA/BAdam/QoRA on DGX Spark
   - Eagle3 NOT involved here

2. [Optional] RL training (GRPO/PPO/DAPO)
   - Use n-gram/prompt-lookup for speedup (safe, never stale)
   - Do NOT use static Eagle3 (staleness + policy degradation)
   - If using NeMo RL with online draft mode, Eagle3 is OK

3. Eagle3 draft training (on FINAL student model)
   - Offline pattern on DGX Spark: vLLM → hidden states → stop → train
   - 2-4h for 5K samples on 35B MoE
   - MUST be after all weight modifications

4. Deploy student + Eagle3
   - vLLM or llama.cpp with speculative config
   - 2-6x inference speedup, lossless for greedy decoding
```

### Why Eagle3 and Distillation Don't Interfere

- Eagle3 trains on the **student model's** hidden states (target model = the
  model being deployed)
- The cloud teacher (GLM-5.2) is NOT involved in Eagle3 training at all
- Eagle3's KL divergence is between draft and student, not draft and teacher
- The draft model learns to predict what the student will output, not what the
  teacher would output
- This makes them completely orthogonal — distillation changes the student's
  weights, Eagle3 learns to predict the student's behavior

### Why Eagle3 Must Come AFTER RL

- RL updates the actor's weights every step
- Eagle3 trained on pre-RL weights will have stale hidden state representations
- Post-RL acceptance rate drops proportionally to how much RL shifted the weights
- On DGX Spark specifically: cannot run Eagle3 online during RL (single GPU
  cannot serve vLLM + train draft + run RL simultaneously)

## DFlash + RL Analysis

Research from July 2026 investigating whether DFlash (block diffusion draft model,
arXiv:2602.06036) is safer than EAGLE-3 for RL training.

### Summary

| Question | Answer |
|---|---|
| Is DFlash immune to drafter staleness during RL? | **No** — same fundamental problem as EAGLE-3. |
| Does DFlash degrade slower than EAGLE-3 during RL? | **Yes** — 4 architectural advantages. |
| Is DFlash safe for RL rollout generation? | **No** — still recommend n-gram/prompt-lookup. |
| Is ReSpec GAP 3 (policy degradation) applicable? | **Yes**, but lower variance due to parallel drafting. |

### Why DFlash Degrades Slower Than EAGLE-3

DFlash, like EAGLE-3, is **conditioned on target model hidden states**. When RL
updates the target's weights → hidden states shift → draft loses accuracy. This
is the same fundamental staleness problem (ReSpec GAP 2).

However, DFlash has **4 architectural advantages** that slow degradation:

**1. 8 target layers (vs 1-3 for EAGLE-3)**
DFlash fuses context features from 8 target model layers. A weight shift in one
layer is diluted across 8 signals. EAGLE-3 uses 1-3 layers, so a shift in any
one layer has outsized impact.

**2. Parallel drafting (no error cascade)**
EAGLE-3 drafts autoregressively: t₁→t₂→t₃. If t₁ is wrong, t₂ and t₃ are likely
wrong too (error cascade → cluster of rejected tokens → higher variance).
DFlash drafts all tokens in parallel: each token is conditioned on target
context, NOT on other draft tokens. One wrong token does NOT corrupt the rest.
This means **lower per-token variance** in the acceptance probability product.

**3. Diffusion denoising (robust to perturbations)**
DFlash uses a diffusion model that denoises masked positions. Diffusion models
are inherently robust to small perturbations in input features — the denoising
process smooths over noise. Small shifts in hidden states have less impact on
draft quality than in EAGLE-3's direct prediction.

**4. Adapter role (not independent predictor)**
DFlash shares the target model's token embedding and LM head (frozen during
training). Only the 6 draft Transformer layers are trained. This makes DFlash
a lightweight **adapter** tightly aligned with the target's representation
space, not an independent predictor. When the target shifts, the shared
components (embedding, LM head) shift too — the adapter partially tracks the
target automatically through these shared components.

### ReSpec GAP 3 Applicability

The ReSpec variance formula applies to ANY multi-token draft, including DFlash:

```
Var[∏ p(t)/q(t)] = ∏(1 + D_χ²(p(t)||q(t))) - 1
```

However, the **practical impact differs**:

- **EAGLE-3 (autoregressive):** q(tᵢ | t₁...tᵢ₋₁) — errors compound because
  each draft token conditions on previous (potentially wrong) draft tokens.
  A single early error cascades, creating clusters of rejected tokens that
  shift the rollout distribution.

- **DFlash (parallel):** q(tᵢ | context) — each draft token is generated
  independently from the target's hidden states. One wrong token does NOT
  affect the others. The variance of the acceptance product is lower because
  errors are isolated, not cascading.

This means DFlash has **lower effective D_χ² per token** in practice, even
though the formula is the same. The exponential growth of variance is slower.

### Practical Recommendation

```
Phase 1: SFT/Distillation → DFlash not needed
Phase 2: RL training → n-gram/prompt-lookup for rollout (SAFE, zero staleness)
         [DFlash degrades slower than EAGLE-3 but still degrades — not worth the risk]
Phase 3: DFlash training on FINAL model → max acceptance
         [--speculator-type dflash, same offline pattern as EAGLE-3]
Phase 4: Deploy with DFlash → SGLang → 2-3x inference speedup
```

**If DFlash must be used during RL** (e.g. long-tail reasoning rollouts where
n-gram is ineffective):
- Degrades slower than EAGLE-3 — may remain useful for 100-200 RL steps
  (vs 50-100 for EAGLE-3, estimated)
- Periodically retrain DFlash on updated hidden states (online adaptation)
- Monitor acceptance rate — disable SD when it drops below threshold
- On single-GPU (DGX Spark): online adaptation during RL is not feasible
  (cannot serve vLLM + train draft + run RL simultaneously)

### Sources

- DFlash paper: arXiv:2602.06036 (Feb 2026) — "the draft model becomes a
  diffusion adapter that efficiently leverages the deep context features
  modeled by the large target model"
- ReSpec: arXiv:2510.26475 (Oct 2025) — three gaps analysis
- Cohere DSD blog (2026) — "We expect more recent methods, such as EAGLE-3
  or DFlash, to show clearer gains in this scenario [RL rollout]"
- Moonlight review (2026) — "The target model's weights constantly change
  during RL training, quickly rendering a static draft model stale"
